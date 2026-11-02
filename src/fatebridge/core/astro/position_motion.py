"""Differentiate the complete apparent position for the inner planets/Sun.

The inspected native planetary speed uses a previous-day approximation to
the derivative of light time. A bounded sixth-order stencil of the *complete*
position includes that chain, deflection, aberration and the moving frame.
It is not an independent accuracy oracle. In particular it is NOT used for
the Moon, whose short-period/native rounding noise needs a different method.
"""

from __future__ import annotations

import math
from fractions import Fraction
from importlib.metadata import version
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from fatebridge.core.astro import runtime
from fatebridge.core.astro.lunar_motion import SOURCE_VERSION
from fatebridge.core.astro.motion_source_window import (
    CenterWindowProbe,
    observed_windows,
)
from fatebridge.core.astro.native_coordinates import require_spherical_coordinates
from fatebridge.core.astro.native_identity import binding_distribution_version
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.astro.retarded_epoch import stabilized_longitude_sample
from fatebridge.core.astro.solar_decimal import (
    FRAME_BODIES,
)
from fatebridge.core.astro.solar_decimal import METHOD_ID as DECIMAL_REDUCTION_ID
from fatebridge.core.astro.solar_decimal import (
    PRECISION,
    PROFILE_SHA256,
    reduced_longitude,
)
from fatebridge.core.astro.solar_motion_branch import solar_interpolation_branch
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.utils.errors import EphemerisSourceError

METHOD_ID = "fatebridge_complete_position_derivative_v8"
TARGETS = frozenset({"Sun", "Mercury", "Venus", "Mars"})
# Binary fractions give exactly represented equal TT offsets even at AD9999.
STEPS_DAYS = (0.125, 0.0625)
REFINEMENT_STEPS_DAYS = tuple(2.0**-k for k in range(5, 12))
OFFSETS = (-3, -2, -1, 1, 2, 3)
WEIGHTS = (-1, 9, -45, 45, -9, 1)
ONE_SIDED_WEIGHTS = (6.0, -7.5, 20 / 3, -3.75, 1.2, -1 / 6)
CONVERGENCE_LINE_ARCSEC_PER_DAY = 0.0002


class AuxiliaryPositionModelChange(EphemerisSourceError):
    """A derivative sample used another backend; the center may still be valid.

    This remains a model_changed error for strict callers. A caller retaining
    the native center rate may handle this exact condition only after proving
    that its original center state and file context can be reproduced.
    """

    def __init__(self, epoch: float, requested: str, actual: str) -> None:
        super().__init__("model_changed")
        self.sample_epoch_jd_tt = epoch
        self.requested_model = requested
        self.actual_model = actual


def _local_polynomial_weights() -> Tuple[float, ...]:
    """Exact degree-six least-squares derivative on 25 symmetric nodes.

    Odd columns x,x^3,x^5 suffice by symmetry. These coefficients depend only
    on the node geometry, never on native samples or reference rates.
    """
    nodes = [Fraction(i, 4) for i in range(-12, 13)]
    powers = (1, 3, 5)
    matrix = [
        [Fraction(sum(x ** (i + j) for x in nodes)) for j in powers]
        + [Fraction(int(i == 1))]
        for i in powers
    ]
    for j in range(3):
        pivot = matrix[j][j]
        matrix[j] = [Fraction(v / pivot) for v in matrix[j]]
        for k in range(3):
            if k != j:
                factor = matrix[k][j]
                matrix[k] = [
                    Fraction(v - factor * w) for v, w in zip(matrix[k], matrix[j])
                ]
    coefficients = [row[-1] for row in matrix]
    return tuple(
        float(sum(c * x**i for c, i in zip(coefficients, powers))) for x in nodes
    )


LOCAL_NODES = tuple(i / 4 for i in range(-12, 13))
LOCAL_WEIGHTS = _local_polynomial_weights()


def local_polynomial_stencil(
    values: Sequence[float], center: float, step: float
) -> float:
    """Redundant local derivative on the same total radius 3*step."""
    if (
        len(values) != 25
        or not math.isfinite(step)
        or step <= 0
        or not math.isfinite(center)
        or not all(math.isfinite(v) for v in values)
    ):
        raise EphemerisSourceError("coordinate_values_unavailable")
    differences = [math.remainder(v - center, 360) for v in values]
    if any(abs(v) >= 90 for v in differences):
        raise EphemerisSourceError("coordinate_motion_unavailable")
    return math.fsum(w * v for w, v in zip(LOCAL_WEIGHTS, differences)) / step


def longitude_stencil(values: Sequence[float], center: float, step: float) -> float:
    """Sixth-order derivative of locally unwrapped longitude, in degrees/day."""
    if (
        len(values) != 6
        or not math.isfinite(center)
        or not math.isfinite(step)
        or step <= 0
        or not all(math.isfinite(v) for v in values)
    ):
        raise EphemerisSourceError("coordinate_values_unavailable")
    differences = [math.remainder(v - center, 360) for v in values]
    # The local branch must be unambiguous; no inference across half a circle.
    if any(abs(v) >= 90 for v in differences):
        raise EphemerisSourceError("coordinate_motion_unavailable")
    return math.fsum(w * v for w, v in zip(WEIGHTS, differences)) / (60 * step)


def one_sided_longitude_stencil(
    values: Sequence[float], center: float, step: float, direction: int
) -> float:
    if direction not in {-1, 1}:
        raise EphemerisSourceError("coordinate_motion_unavailable")
    longitude_stencil(values, center, step)  # Domain and branch checks.
    differences = [math.remainder(v - center, 360) for v in values]
    return math.fsum(w * v for w, v in zip(ONE_SIDED_WEIGHTS, differences)) / (
        direction * step
    )


def _one_sided_weights(count: int) -> Tuple[Tuple[float, ...], Tuple[float, ...]]:
    """Degree-six LS derivative at zero on a fixed [0,6] node geometry.

    Normal equations are solved exactly over rationals. The coefficients
    depend only on node geometry, never on a planet, epoch or expected rate.
    """
    nodes = tuple(Fraction(6 * i, count - 1) for i in range(count))
    powers = range(7)
    matrix = [
        [sum((x ** (i + j) for x in nodes), Fraction(0)) for j in powers]
        + [Fraction(int(i == 1))]
        for i in powers
    ]
    for j in powers:
        pivot = matrix[j][j]
        matrix[j] = [Fraction(v / pivot) for v in matrix[j]]
        for k in powers:
            if k != j:
                factor = matrix[k][j]
                matrix[k] = [v - factor * w for v, w in zip(matrix[k], matrix[j])]
    coefficients = [row[-1] for row in matrix]
    weights = tuple(
        float(sum(c * x**i for i, c in enumerate(coefficients))) for x in nodes
    )
    return tuple(float(x) for x in nodes), weights


DIRECTIONAL_POLYNOMIALS = {count: _one_sided_weights(count) for count in (13, 25)}
DIRECTIONAL_GUARD_ID = "degree6_parent_step_one_sided_ls13_ls25_joint_range_v1"


def one_sided_polynomial_stencil(
    values: Sequence[float], center: float, step: float, direction: int
) -> float:
    if len(values) not in DIRECTIONAL_POLYNOMIALS or direction not in {-1, 1}:
        raise EphemerisSourceError("coordinate_motion_unavailable")
    if (
        not math.isfinite(step)
        or step <= 0
        or not math.isfinite(center)
        or not all(math.isfinite(v) for v in values)
    ):
        raise EphemerisSourceError("coordinate_values_unavailable")
    differences = [math.remainder(v - center, 360) for v in values]
    if any(abs(v) >= 90 for v in differences):
        raise EphemerisSourceError("coordinate_motion_unavailable")
    weights = DIRECTIONAL_POLYNOMIALS[len(values)][1]
    return math.fsum(w * v for w, v in zip(weights, differences)) / (direction * step)


def refinement_budget(
    epoch: float, longitude: float
) -> Tuple[Tuple[float, ...], Dict[str, Any]]:
    """Bound finer sampling by time representability and coordinate quantization.

    The scale estimates floating output quantization, not physical/source error.
    A parent-step one-sided fit has twice the candidate step. The sum of the
    two half-ULP directional scales gives L1*ULP/(2*candidate_step).
    """
    if not math.isfinite(epoch) or not math.isfinite(longitude):
        raise EphemerisSourceError("coordinate_values_unavailable")
    epoch_ulp = math.ulp(epoch)
    coordinate_ulp = max(math.ulp(longitude), math.ulp(1.0))
    norm = max(
        math.fsum(abs(w) for w in item[1]) for item in DIRECTIONAL_POLYNOMIALS.values()
    )
    floor = max(
        64 * epoch_ulp,
        norm * coordinate_ulp * 3600 / (2 * CONVERGENCE_LINE_ARCSEC_PER_DAY),
    )
    step = STEPS_DAYS[0]
    steps = []
    while step >= floor:
        steps.append(step)
        step /= 2
    if not steps:
        raise EphemerisSourceError("coordinate_motion_unavailable")
    return tuple(steps), {
        "method_id": "binary_epoch_and_coordinate_quantization_budget_v1",
        "epoch_ulp_days": epoch_ulp,
        "coordinate_quantization_degrees": coordinate_ulp,
        "minimum_epoch_ulps": 64,
        "directional_l1_norm": norm,
        "estimated_roundoff_floor_days": floor,
        "minimum_step_days": steps[-1],
        "scope": "Representability and floating-output quantization scale only; not a bound on native ephemeris, relativistic, interpolation or physical error",
    }


def homogeneous_side_derivative(
    steps: Sequence[float],
    provider: Callable[[float], float],
    branch: Callable[[float], Dict[str, Any]],
) -> Dict[str, Any]:
    """Use all sampled homogeneous directions, with three agreeing levels.

    A direction crossing a known source knot is ineligible. A direction with
    disagreeing rates cannot be silently excluded. Unknown center geometry
    and changes in the eligible direction set reset convergence evidence.
    """
    center_branch = branch(0.0)
    result: Dict[str, Any] = {
        "method_id": "source_homogeneous_side_ls13_ls25_three_levels_v1",
        "source_function": "Swiss2.10.03 swi_deflect_light/meff",
        "center": center_branch,
        "status": "not_converged",
        "levels": [],
        "required_consecutive_levels": 3,
        "candidate_steps_days": list(steps),
        "convergence_line_arcsec_per_day": CONVERGENCE_LINE_ARCSEC_PER_DAY,
        "scope": "Finite sampled single interpolation-cell support. Interior center plus agreeing side fits, not continuous interval completeness or physical error certification",
    }
    if center_branch.get("cell") is None:
        return result
    center = provider(0.0)
    run: List[Dict[str, Any]] = []
    for step in steps:
        sides = []
        estimates = []
        valid = []
        for direction in (1, -1):
            nodes = DIRECTIONAL_POLYNOMIALS[25][0]
            cells = [branch(direction * x * step).get("cell") for x in nodes]
            eligible = all(cell == center_branch["cell"] for cell in cells)
            sides.append(dict(direction=direction, node_cells=cells, eligible=eligible))
            if eligible:
                valid.append(direction)
                for count, (fit_nodes, _) in DIRECTIONAL_POLYNOMIALS.items():
                    value = one_sided_polynomial_stencil(
                        [provider(direction * x * step) for x in fit_nodes],
                        center,
                        step,
                        direction,
                    )
                    estimates.append(
                        dict(direction=direction, sample_count=count, rate=value)
                    )
        level: Dict[str, Any] = dict(
            step_days=step,
            sides=sides,
            estimates=estimates,
            eligible_directions=valid,
            passed=False,
        )
        result["levels"].append(level)
        if not valid:
            run = []
            continue
        if run and run[-1]["eligible_directions"] != valid:
            run = []
        # Both fit densities take part in acceptance. Every eligible direction
        # contributes symmetrically to the finest 25-node returned estimate.
        level["rate"] = math.fsum(
            e["rate"] for e in estimates if e["sample_count"] == 25
        ) / len(valid)
        run.append(level)
        if len(run) < 3:
            continue
        values = [e["rate"] for item in run[-3:] for e in item["estimates"]]
        spread = (max(values) - min(values)) * 3600
        passed = math.isfinite(spread) and spread <= CONVERGENCE_LINE_ARCSEC_PER_DAY
        level.update(disagreement_arcsec_per_day=spread, passed=passed)
        if passed:
            result.update(
                status="converged",
                selected_step_days=step,
                eligible_directions=valid,
                selected_rate=level["rate"],
                steps_days=[item["step_days"] for item in run],
                rates=[item["rate"] for item in run],
                pair_differences_arcsec_per_day=[
                    abs(a["rate"] - b["rate"]) * 3600 for a, b in zip(run, run[1:])
                ],
                consecutive_converged_pairs=2,
            )
            break
    return result


def complete_position_rate(
    planet: str,
    julian_day_tt: float,
    coordinates: Sequence[float],
    model: str,
    *,
    sidereal: bool = False,
    source_trace: Optional[PhysicalEphemerisTrace] = None,
) -> Tuple[Optional[float], Dict[str, Any]]:
    """Refine a wide stencil locally, rejecting model drift or non-convergence.

    No reference samples, date-specific coefficients or residuals enter this
    service. Central stencils require two consecutive pairs and a joint
    directional guard. A separately reported homogeneous-source-side fallback
    requires an interior source cell and three jointly agreeing levels.
    No external reference controls selection. Every tried pair is retained.
    """
    swe = runtime.swe
    native_version = str(getattr(swe, "version", "unavailable"))
    binding = binding_distribution_version(swe, version)
    policy: Dict[str, Any] = {
        "method_id": METHOD_ID,
        "native_version": native_version,
        "binding_version": binding,
        "ephemeris_model": model,
        "epoch_jd_tt": julian_day_tt,
        "reference_frame": (
            "lahiri_sidereal_ecliptic_of_date"
            if sidereal
            else "tropical_ecliptic_of_date"
        ),
        "candidate_steps_days": list(STEPS_DAYS + REFINEMENT_STEPS_DAYS),
        "selection_policy": "first_two_converged_pairs_and_parent_directional_joint_range",
        "directional_guard_method_id": DIRECTIONAL_GUARD_ID,
        "convergence_line_arcsec_per_day": CONVERGENCE_LINE_ARCSEC_PER_DAY,
        "source_url": "https://www.astro.com/swisseph/swephprg.htm",
        "numerical_source_url": "https://www.colorado.edu/amath/sites/default/files/attached-files/mathcomp_88_fd_formulas.pdf",
        "scope": "Derivative of complete apparent longitude; displayed native positions are unchanged. Previously successful sampling paths retain their order. A witnessed compressed-file switch can use an exactly replayed center-file derivative with three agreeing homogeneous-side fit levels, additionally retaining the solar interpolation cell for planets. An unresolved Sun can extend central refinement within its numerical representability budget. Unresolved finite-Sun planetary samples can use a separately reported decimal reduction of checked shared compressed or JPL geometric states. Its stable cross-product source cell, three-level and convergence guards remain required. Internal step agreement is not an independent accuracy bound, continuous-interval proof or prediction validation.",
    }
    if planet not in TARGETS or model not in {"swieph", "jpl"}:
        return None, {
            **policy,
            "status": "not_applied",
            "reason": "unsupported_target_or_model",
        }
    if swe is None or (native_version, binding) != SOURCE_VERSION:
        return None, {
            **policy,
            "status": "not_applied",
            "reason": "unverified_native_version",
        }
    if not math.isfinite(julian_day_tt):
        raise EphemerisSourceError("coordinate_values_unavailable")
    if model == "jpl" and planet in {"Mercury", "Venus"}:
        from fatebridge.core.astro.inner_motion import complete_inner_rate

        analytic, analytic_policy = complete_inner_rate(
            planet,
            julian_day_tt,
            coordinates,
            model,
            sidereal=sidereal,
            source_trace=source_trace,
        )
        if analytic is not None:
            return analytic, analytic_policy
        # A knot, isolated frame shortcut or other unqualified analytic domain
        # remains visible even if the older sampled derivative is available.
        policy["analytic_source_attempt"] = analytic_policy
    trace = source_trace if source_trace is not None else PhysicalEphemerisTrace()
    samples: Dict[float, float] = {0.0: float(coordinates[0])}
    contexts = {}
    rates = []
    tried_steps = []
    pair_differences = []
    difference = math.inf
    primary_attempt: Dict[str, Any] = {}
    selected_stencil = "sixth_order_six_point"
    stabilization: Dict[str, Any] = {}
    source_branch_motion: Dict[str, Any] = {}
    with runtime.preserve_ephemeris_path():
        selected = configured_ephemeris_path()
        center_windows = observed_windows() if model == "swieph" else None
        center_source = (
            trace.observe("motion_center_source", model, record_factor=False)
            if model in {"swieph", "jpl"}
            else {}
        )
        if sidereal:
            runtime.ephemeris_call("set_sid_mode", swe.SIDM_LAHIRI, 0.0, 0.0)
        flags = swe.FLG_SWIEPH | swe.FLG_SPEED | (swe.FLG_SIDEREAL if sidereal else 0)

        def sample(delta: float) -> float:
            if delta not in samples:
                epoch = julian_day_tt + delta
                if epoch - julian_day_tt != delta:
                    raise EphemerisSourceError("coordinate_motion_unavailable")
                state, returned = runtime.ephemeris_call(
                    "calc", epoch, PLANET_SWISSEPH_IDS[planet], flags
                )
                assert_physical_configuration(selected)
                actual_model = runtime.ephemeris_model_from_retflag(returned)
                if actual_model != model:
                    raise AuxiliaryPositionModelChange(epoch, model, actual_model)
                lon, _, _ = require_spherical_coordinates(
                    state, returned, native=swe, sidereal=sidereal
                )
                factor = f"{planet}_motion_position_{'lahiri' if sidereal else 'tropical'}_{delta:+g}"
                contexts[factor] = trace.observe(factor, model, record_factor=False)
                samples[delta] = lon
            return samples[delta]

        def run_stencil(
            steps: Sequence[float], provider: Any, polynomial: bool = False
        ) -> Dict[str, Any]:
            trial_rates: List[float] = []
            trial_steps: List[float] = []
            pair_errors: List[float] = []
            checks: List[Dict[str, Any]] = []
            consecutive_pairs = 0
            for h in steps:
                if polynomial:
                    rate = local_polynomial_stencil(
                        [provider(x * h) for x in LOCAL_NODES], float(coordinates[0]), h
                    )
                else:
                    rate = longitude_stencil(
                        [provider(x * h) for x in OFFSETS], float(coordinates[0]), h
                    )
                trial_rates.append(rate)
                trial_steps.append(h)
                if len(trial_rates) < 2:
                    continue
                error = abs(trial_rates[-2] - rate) * 3600
                pair_errors.append(error)
                consecutive_pairs = (
                    consecutive_pairs + 1
                    if math.isfinite(error) and error <= CONVERGENCE_LINE_ARCSEC_PER_DAY
                    else 0
                )
                if consecutive_pairs < 2:
                    continue
                center = provider(0.0)
                parent = 2 * h
                estimates = []
                for count, (nodes, _) in DIRECTIONAL_POLYNOMIALS.items():
                    sides = [
                        one_sided_polynomial_stencil(
                            [provider(direction * x * parent) for x in nodes],
                            center,
                            parent,
                            direction,
                        )
                        for direction in (1, -1)
                    ]
                    estimates.append(
                        dict(
                            sample_count=count,
                            forward_rate=sides[0],
                            backward_rate=sides[1],
                        )
                    )
                values = trial_rates[-3:] + [
                    row[k]
                    for row in estimates
                    for k in ("forward_rate", "backward_rate")
                ]
                spread = (max(values) - min(values)) * 3600
                passed = (
                    math.isfinite(spread) and spread <= CONVERGENCE_LINE_ARCSEC_PER_DAY
                )
                # Preserve the former six-point guard as diagnostic evidence;
                # it is not the better-conditioned redundant acceptance fit.
                legacy_sides = [
                    one_sided_longitude_stencil(
                        [provider(direction * k * h) for k in range(1, 7)],
                        center,
                        h,
                        direction,
                    )
                    for direction in (1, -1)
                ]
                legacy_error = (
                    max(
                        abs(legacy_sides[0] - legacy_sides[1]),
                        *(abs(v - rate) for v in legacy_sides),
                    )
                    * 3600
                )
                checks.append(
                    dict(
                        method_id=DIRECTIONAL_GUARD_ID,
                        step_days=parent,
                        central_step_days=h,
                        estimates=estimates,
                        forward_rate=estimates[-1]["forward_rate"],
                        backward_rate=estimates[-1]["backward_rate"],
                        central_rates=trial_rates[-3:],
                        disagreement_arcsec_per_day=spread,
                        passed=passed,
                        legacy_six_point_forward_rate=legacy_sides[0],
                        legacy_six_point_backward_rate=legacy_sides[1],
                        legacy_disagreement_arcsec_per_day=legacy_error,
                        legacy_passed=legacy_error <= CONVERGENCE_LINE_ARCSEC_PER_DAY,
                    )
                )
                if passed:
                    break
            return dict(
                steps_days=trial_steps,
                rates=trial_rates,
                pair_differences_arcsec_per_day=pair_errors,
                directional_checks=checks,
                consecutive_converged_pairs=consecutive_pairs,
                status=(
                    "converged" if checks and checks[-1]["passed"] else "not_converged"
                ),
            )

        def replayed_file_attempt() -> Optional[Dict[str, Any]]:
            # A finite difference must sample one source function. At an
            # overlapping compressed-file join, replay the actual center's
            # files and require three jointly agreeing homogeneous-side fits.
            # A file switch is necessary evidence; unrelated failures do not
            # gain a permissive generic one-sided fallback.
            switched = center_source.get("file_ids") and any(
                value.get("file_ids") != center_source["file_ids"]
                for value in contexts.values()
            )
            if center_windows is not None and switched:
                probe = CenterWindowProbe(
                    planet,
                    julian_day_tt,
                    coordinates,
                    center_windows,
                    center_source,
                    trace,
                    sidereal=sidereal,
                )
                source_grid, budget = refinement_budget(
                    julian_day_tt, float(coordinates[0])
                )
                result = homogeneous_side_derivative(
                    source_grid, probe.value, probe.branch
                )
                result.update(
                    method_id="center_file_homogeneous_side_ls13_ls25_three_levels_v1",
                    source_function="Swiss compressed file contexts and solar interpolation cells",
                    center_file_replay=probe.receipt(),
                    refinement_budget=budget,
                )
                policy.setdefault("center_file_replay_attempts", []).append(result)
                return result
            return None

        grid = STEPS_DAYS + REFINEMENT_STEPS_DAYS
        attempt = run_stencil(grid, sample)
        if attempt["status"] != "converged":
            primary_attempt = attempt
            selected_stencil = "degree6_least_squares_25_point"
            attempt = run_stencil(grid, sample, polynomial=True)
        if attempt["status"] != "converged":
            replayed = replayed_file_attempt()
            if replayed is not None:
                source_branch_motion = replayed
                if replayed["status"] == "converged":
                    selected_stencil = "center_file_homogeneous_side_degree6_ls13_ls25"
                    attempt = {
                        key: replayed[key]
                        for key in (
                            "status",
                            "rates",
                            "steps_days",
                            "pair_differences_arcsec_per_day",
                            "consecutive_converged_pairs",
                        )
                    }
                    attempt["directional_checks"] = []
        if attempt["status"] != "converged" and planet == "Sun":
            # Preserve all successful original paths. Only an unresolved Sun
            # needs this additional representability-bounded central attempt;
            # planetary light-time stabilization keeps its established order.
            extended_grid, grid_budget = refinement_budget(
                julian_day_tt, float(coordinates[0])
            )
            policy["sun_extension_previous_attempt"] = attempt
            policy["candidate_steps_days"] = list(extended_grid)
            policy["refinement_budget"] = grid_budget
            attempt = run_stencil(extended_grid, sample)
            selected_stencil = "bounded_extended_sixth_order_six_point"
        if attempt["status"] != "converged":
            if planet not in {"Mercury", "Venus", "Mars"}:
                raise EphemerisSourceError("position_motion_not_converged")
            unstabilized_attempt = {"selected_stencil": selected_stencil, **attempt}
            selected_stencil = "retarded_epoch_stabilized_sixth_order"
            stable_samples: Dict[float, float] = {}
            policies = []

            def stable_sample(delta: float) -> float:
                if delta not in stable_samples:
                    epoch = julian_day_tt + delta
                    if epoch - julian_day_tt != delta:
                        raise EphemerisSourceError("coordinate_motion_unavailable")
                    raw, returned = runtime.ephemeris_call(
                        "calc", epoch, PLANET_SWISSEPH_IDS[planet], flags
                    )
                    assert_physical_configuration(selected)
                    actual_model = runtime.ephemeris_model_from_retflag(returned)
                    if actual_model != model:
                        raise AuxiliaryPositionModelChange(epoch, model, actual_model)
                    require_spherical_coordinates(
                        raw, returned, native=swe, sidereal=sidereal
                    )
                    factor = f"{planet}_motion_stabilized_{delta:+g}"
                    contexts[factor] = trace.observe(factor, model, record_factor=False)
                    lon, receipt = stabilized_longitude_sample(
                        planet,
                        epoch,
                        raw,
                        model,
                        sidereal=sidereal,
                        source_trace=trace,
                        contexts=contexts,
                        factor_prefix=factor,
                    )
                    stable_samples[delta] = lon
                    policies.append(receipt)
                return stable_samples[delta]

            stable_grid, budget = refinement_budget(
                julian_day_tt, float(coordinates[0])
            )
            attempt = run_stencil(stable_grid, stable_sample)
            symmetric_attempt = attempt
            if attempt["status"] != "converged":
                branches: Dict[float, Dict[str, Any]] = {}

                def branch(delta: float) -> Dict[str, Any]:
                    if delta not in branches:
                        epoch = julian_day_tt + delta
                        if epoch - julian_day_tt != delta:
                            raise EphemerisSourceError("coordinate_motion_unavailable")
                        branches[delta] = solar_interpolation_branch(
                            planet,
                            epoch,
                            model,
                            trace,
                            contexts,
                            f"{planet}_motion_source_cell_{delta:+g}",
                        )
                    return branches[delta]

                source_branch_motion = homogeneous_side_derivative(
                    stable_grid[2:], stable_sample, branch
                )
                source_branch_motion["probe_count"] = len(branches)
                if source_branch_motion["status"] == "converged":
                    selected_stencil = "source_homogeneous_side_degree6_ls13_ls25"
                    attempt = {
                        k: source_branch_motion[k]
                        for k in (
                            "status",
                            "rates",
                            "steps_days",
                            "pair_differences_arcsec_per_day",
                            "consecutive_converged_pairs",
                        )
                    }
                    attempt["directional_checks"] = []
            rates = attempt["rates"]
            tried_steps = attempt["steps_days"]
            pair_differences = attempt["pair_differences_arcsec_per_day"]
            consecutive = attempt["consecutive_converged_pairs"]
            stabilization = {
                "method_id": "native_retarded_epoch_remainder_linearization_v1",
                "unstabilized_attempt": unstabilized_attempt,
                "symmetric_stabilized_attempt": symmetric_attempt,
                "candidate_steps_days": list(stable_grid),
                "refinement_budget": budget,
                "directional_guard_method_id": (
                    source_branch_motion.get("method_id", DIRECTIONAL_GUARD_ID)
                    if source_branch_motion.get("status") == "converged"
                    else DIRECTIONAL_GUARD_ID
                ),
                "required_consecutive_converged_pairs": 2,
                "consecutive_converged_pairs": consecutive,
                "one_sided_checks": symmetric_attempt["directional_checks"],
                "acceptance_scope": (
                    "source_homogeneous_side_receipt"
                    if source_branch_motion.get("status") == "converged"
                    else "symmetric_parent_directional_joint_range"
                ),
                "sample_count": len(policies),
                "maximum_epoch_remainder_days": max(
                    abs(p["epoch_remainder_days"]) for p in policies
                ),
                "maximum_sampling_shift_arcseconds": max(
                    abs(p["sampling_longitude_shift_arcseconds"]) for p in policies
                ),
                "displayed_native_position_changed": False,
                "scope": "First-order recovery of lost retarded-epoch fractions in auxiliary derivative samples only. Native frame-velocity and apparent-position Jacobian cross terms remain approximation limits; multi-step agreement is not an independent error bound.",
            }
        if attempt["status"] != "converged":
            replayed = replayed_file_attempt()
            if replayed is not None:
                source_branch_motion = replayed
                if replayed["status"] == "converged":
                    selected_stencil = "center_file_homogeneous_side_degree6_ls13_ls25"
                    attempt = {
                        key: replayed[key]
                        for key in (
                            "status",
                            "rates",
                            "steps_days",
                            "pair_differences_arcsec_per_day",
                            "consecutive_converged_pairs",
                        )
                    }
                    attempt["directional_checks"] = []
        if (
            attempt["status"] != "converged"
            and model in {"swieph", "jpl"}
            and planet in {"Mercury", "Venus", "Mars"}
            and center_source.get("file_ids")
        ):
            decimal_samples: Dict[float, Tuple[float, Dict[str, Any]]] = {}

            def decimal_sample(delta: float) -> float:
                if delta not in decimal_samples:
                    epoch = julian_day_tt + delta
                    if epoch - julian_day_tt != delta:
                        raise EphemerisSourceError("coordinate_motion_unavailable")
                    decimal_samples[delta] = reduced_longitude(
                        planet,
                        epoch,
                        sidereal=sidereal,
                        trace=trace,
                        contexts=contexts,
                        prefix=f"{planet}_decimal_{delta:+g}",
                        center_source=center_source,
                        model=model,
                    )
                return decimal_samples[delta][0]

            def decimal_branch(delta: float) -> Dict[str, Any]:
                decimal_sample(delta)
                branch: Dict[str, Any] = decimal_samples[delta][1][
                    "solar_interpolation_branch"
                ]
                return branch

            # This branch belongs to the stable auxiliary function itself.
            # An exact knot/unknown domain still cannot authorize a side fit.
            cell = decimal_branch(0.0).get("cell")
            if type(cell) is int and 0 <= cell < 100:
                policy["decimal_reduction_previous_attempt"] = source_branch_motion
                decimal_grid, budget = refinement_budget(
                    julian_day_tt, float(coordinates[0])
                )
                result = homogeneous_side_derivative(
                    decimal_grid[2:], decimal_sample, decimal_branch
                )
                result.update(
                    method_id="decimal_reduction_homogeneous_side_ls13_ls25_three_levels_v2",
                    source_function="Swiss2.10.03 geometric states, finite-Sun deflection, aberration and checked frame reduction",
                    refinement_budget=budget,
                    probe_count=len(decimal_samples),
                    decimal_reduction={
                        "method_id": DECIMAL_REDUCTION_ID,
                        "ephemeris_model": model,
                        "center_interpolation_branch": decimal_branch(0.0),
                        "precision_decimal_digits": PRECISION,
                        "solar_mass_profile_sha256": PROFILE_SHA256,
                        "frame_basis_bodies": list(FRAME_BODIES),
                        "sample_count": len(decimal_samples),
                        "maximum_frame_orthogonality_error": max(
                            v[1]["frame_orthogonality_error"]
                            for v in decimal_samples.values()
                        ),
                        "maximum_epoch_remainder_days": max(
                            abs(v[1]["epoch_remainder_days"])
                            for v in decimal_samples.values()
                        ),
                        "center_sampling_shift_arcseconds": math.remainder(
                            decimal_sample(0.0) - float(coordinates[0]), 360.0
                        )
                        * 3600,
                        "displayed_native_position_changed": False,
                        "independent_astronomical_accuracy_certified": False,
                        "scope": "50-digit equivalent source reduction of shared native geometric states; retarded fractional epoch restored to first order. Native geometric and frame error, source-model approximations and physical accuracy remain uncertified.",
                    },
                )
                source_branch_motion = result
                if result["status"] == "converged":
                    selected_stencil = (
                        "decimal_reduction_homogeneous_side_degree6_ls13_ls25"
                    )
                    attempt = {
                        key: result[key]
                        for key in (
                            "status",
                            "rates",
                            "steps_days",
                            "pair_differences_arcsec_per_day",
                            "consecutive_converged_pairs",
                        )
                    }
                    attempt["directional_checks"] = []
        if attempt["status"] != "converged":
            raise EphemerisSourceError("position_motion_not_converged")
        rates = attempt["rates"]
        tried_steps = attempt["steps_days"]
        pair_differences = attempt["pair_differences_arcsec_per_day"]
        difference = pair_differences[-1]
        assert_physical_configuration(selected)
        if source_trace is None:
            trace.finish()
    return rates[-1], {
        **policy,
        "status": "applied",
        "selected_stencil": selected_stencil,
        "primary_attempt": primary_attempt,
        "sampling_stabilization": stabilization,
        "source_branch_motion": source_branch_motion,
        "candidate_steps_days": (
            source_branch_motion.get("candidate_steps_days", [])
            if source_branch_motion.get("status") == "converged"
            else stabilization.get(
                "candidate_steps_days", policy["candidate_steps_days"]
            )
        ),
        "directional_guard_method_id": (
            source_branch_motion["method_id"]
            if source_branch_motion.get("status") == "converged"
            else DIRECTIONAL_GUARD_ID
        ),
        "selection_policy": (
            "first_three_same_cell_levels_all_eligible_sides_ls13_ls25_joint_range"
            if source_branch_motion.get("status") == "converged"
            else policy["selection_policy"]
        ),
        "directional_checks": attempt["directional_checks"],
        "steps_days": tried_steps,
        "chosen_step_days": tried_steps[-1],
        "pair_differences_arcsec_per_day": pair_differences,
        "step_rates_degrees_per_day": rates,
        "step_difference_arcsec_per_day": difference,
        "source_contexts": contexts,
    }
