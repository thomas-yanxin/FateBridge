"""Differentiate Moshier's apparent model with checked source arithmetic.

This corrects a rate/position consistency problem; it does not improve the
underlying analytical position theory or turn it into a DE441 ephemeris.
"""

from __future__ import annotations

import math
from importlib.metadata import version
from typing import Any, Callable, Sequence

from fatebridge.core.astro import runtime
from fatebridge.core.astro.lunar_motion import SOURCE_VERSION
from fatebridge.core.astro.native_identity import binding_distribution_version
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.astro.position_motion import (
    CONVERGENCE_LINE_ARCSEC_PER_DAY,
    DIRECTIONAL_POLYNOMIALS,
    LOCAL_NODES,
    OFFSETS,
    homogeneous_side_derivative,
    local_polynomial_stencil,
    longitude_stencil,
    one_sided_polynomial_stencil,
)
from fatebridge.core.astro.solar_decimal import (
    MOSHIER_LUNAR_METHOD_ID,
    MOSHIER_METHOD_ID,
    MOSHIER_SOURCE_TARGETS,
    MoshierGeometricStates,
    ReductionReceipt,
    reduced_longitude,
)
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.utils.errors import EphemerisSourceError

METHOD_ID = "fatebridge_moshier_apparent_position_derivative_v4"
SIDEREAL_METHOD_ID = "fatebridge_moshier_lahiri_position_derivative_v4"
TARGETS = MOSHIER_SOURCE_TARGETS
# Requested offsets are binary fractions; actual whole-JD sums are observed.
# Unlike compressed Swiss files, the analytical series has no daily interpolation
# cell. Coarser candidates reduce amplification of native coordinate/retarded-JD
# roundoff; the same refinement and directional criteria still decide acceptance.
STEPS_DAYS = tuple(2.0**-k for k in range(1, 12))
SOURCE_STEPS_DAYS = (0.125, 0.0625)
SOURCE_POSITION_LINE_ARCSEC = 0.02
NATIVE_RANGE_JD_TT = (625000.5, 2818000.5)
GEOMETRIC_PADDING_DAYS = 0.3
LUNAR_GEOMETRIC_PADDING_DAYS = 0.2


def complete_moshier_longitude_rate(
    planet: str,
    julian_day_tt: float,
    coordinates: Sequence[float],
    *,
    sidereal: bool = False,
    source_trace: PhysicalEphemerisTrace | None = None,
) -> tuple[float | None, dict[str, Any]]:
    """Require two source steps and their declared stencil convergence.

    Only Moshier and the inspected binding/native version are supported.
    Non-convergence leaves a visible unapplied receipt, never a substituted
    reference value. Frame/model/source failures remain errors.
    """
    swe = runtime.swe
    native_version = str(getattr(swe, "version", "unavailable"))
    binding = binding_distribution_version(swe, version)
    policy: dict[str, Any] = {
        "method_id": SIDEREAL_METHOD_ID if sidereal else METHOD_ID,
        "native_version": native_version,
        "binding_version": binding,
        "ephemeris_model": "moshier",
        "epoch_jd_tt": julian_day_tt,
        "reference_frame": (
            "lahiri_sidereal_ecliptic_of_date"
            if sidereal
            else "tropical_ecliptic_of_date"
        ),
        "candidate_steps_days": list(STEPS_DAYS),
        "convergence_line_arcsec_per_day": CONVERGENCE_LINE_ARCSEC_PER_DAY,
        "selection_policy": "two_source_steps_full_stencil_or_range_qualified_homogeneous_sides",
        "source_url": (
            "https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/sweph.c"
            if planet == "Sun"
            else (
                "https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/swemmoon.c"
                if planet == "Moon"
                else "https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/swemplan.c"
            )
        ),
        "position_reduction_source_url": "https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/sweph.c",
        "scope": "Derivative of the selected continuous Moshier apparent-position source model. Eight planets use stable geometric evaluation of the original short backward source-speed operator, with two checked source steps, one linearized light-time iteration and the same finite-Sun/aberration/date-frame reduction. The Sun uses negative geometric Earth, no solar light-time iteration or self-deflection, and the same stable Earth-source-speed aberration. The Moon uses its original forward-biased three-point lunar source-speed operator, backward Earth source speed, geocentric linear light time and no solar deflection, with the Earth terms cancelled before numerical reduction. Displayed native positions and analytical theory remain unchanged. Step agreement does not certify the exact rounded binary64 map, physical-model error, station time or prediction.",
    }
    if planet not in TARGETS:
        return None, {**policy, "status": "not_applied", "reason": "unsupported_target"}
    else:
        pass
    if swe is None or (native_version, binding) != SOURCE_VERSION:
        return None, {
            **policy,
            "status": "not_applied",
            "reason": "unverified_native_version",
        }
    else:
        pass
    if (
        not math.isfinite(julian_day_tt)
        or len(coordinates) < 4
        or not all(math.isfinite(v) for v in coordinates[:4])
    ):
        raise EphemerisSourceError("coordinate_values_unavailable")
    else:
        pass
    trace = source_trace if source_trace is not None else PhysicalEphemerisTrace()
    contexts: dict[str, Any] = {}
    attempts: list[dict[str, object]] = []
    result: float | None = None
    with runtime.preserve_ephemeris_path():
        selected = configured_ephemeris_path()
        if sidereal:
            runtime.ephemeris_call("set_sid_mode", swe.SIDM_LAHIRI, 0.0, 0.0)
        else:
            pass

        def run_stencils(
            provider: Callable[[float], float],
            center: float,
            steps: Sequence[float],
        ) -> tuple[float | None, list[dict[str, object]]]:
            selected_rate: float | None = None
            trials: list[dict[str, object]] = []
            for polynomial in (False, True):
                rates: list[float] = []
                tried_steps: list[float] = []
                differences: list[float] = []
                checks: list[dict[str, object]] = []
                consecutive = 0
                for step in steps:
                    rate = (
                        local_polynomial_stencil(
                            [provider(x * step) for x in LOCAL_NODES],
                            center,
                            step,
                            abscissas_days=[
                                (julian_day_tt + x * step) - julian_day_tt
                                for x in LOCAL_NODES
                            ],
                        )
                        if polynomial
                        else longitude_stencil(
                            [provider(x * step) for x in OFFSETS],
                            center,
                            step,
                            abscissas_days=[
                                (julian_day_tt + x * step) - julian_day_tt
                                for x in OFFSETS
                            ],
                        )
                    )
                    tried_steps.append(step)
                    rates.append(rate)
                    if len(rates) < 2:
                        continue
                    else:
                        pass
                    error = abs(rate - rates[-2]) * 3600
                    differences.append(error)
                    consecutive = (
                        consecutive + 1
                        if error <= CONVERGENCE_LINE_ARCSEC_PER_DAY
                        else 0
                    )
                    if consecutive < 2:
                        continue
                    else:
                        pass
                    parent = 2 * step
                    estimates: list[dict[str, object]] = []
                    directional_rates = []
                    for count, (nodes, _) in DIRECTIONAL_POLYNOMIALS.items():
                        for direction in (-1, 1):
                            value = one_sided_polynomial_stencil(
                                [provider(direction * x * parent) for x in nodes],
                                center,
                                parent,
                                direction,
                                abscissas_days=[
                                    (julian_day_tt + direction * x * parent)
                                    - julian_day_tt
                                    for x in nodes
                                ],
                            )
                            directional_rates.append(value)
                            estimates.append(
                                {
                                    "sample_count": count,
                                    "direction": direction,
                                    "rate_degrees_per_day": value,
                                }
                            )
                    values = rates[-3:] + directional_rates
                    spread = (max(values) - min(values)) * 3600
                    passed = spread <= CONVERGENCE_LINE_ARCSEC_PER_DAY
                    checks.append(
                        {
                            "central_step_days": step,
                            "parent_step_days": parent,
                            "estimates": estimates,
                            "joint_spread_arcsec_per_day": spread,
                            "passed": passed,
                        }
                    )
                    if passed:
                        selected_rate = rate
                        break
                    else:
                        pass
                trials.append(
                    {
                        "stencil": (
                            "degree6_least_squares_25_point"
                            if polynomial
                            else "sixth_order_six_point"
                        ),
                        "steps_days": tried_steps,
                        "rates_degrees_per_day": rates,
                        "pair_differences_arcsec_per_day": differences,
                        "directional_checks": checks,
                        "consecutive_converged_pairs": consecutive,
                        "status": (
                            "converged"
                            if selected_rate is not None
                            else "not_converged"
                        ),
                    }
                )
                if selected_rate is not None:
                    break
                else:
                    pass
            return selected_rate, trials

        # A complete trial includes its parent-step one-sided checks. Select
        # executable geometries before sampling, independently of their rates.
        parent_reach = 2 * max(
            x for nodes, _ in DIRECTIONAL_POLYNOMIALS.values() for x in nodes
        )
        padding = (
            LUNAR_GEOMETRIC_PADDING_DAYS if planet == "Moon" else GEOMETRIC_PADDING_DAYS
        )
        lower = NATIVE_RANGE_JD_TT[0] - padding
        upper = NATIVE_RANGE_JD_TT[1] + padding
        radius = min(julian_day_tt - lower, upper - julian_day_tt)
        source_step = SOURCE_STEPS_DAYS[0]
        while 3 * source_step >= radius and source_step > STEPS_DAYS[-1]:
            source_step /= 2
        source_radius = 3 * source_step
        steps = tuple(
            h
            for h in STEPS_DAYS
            if julian_day_tt - parent_reach * h - source_radius >= lower
            and julian_day_tt + parent_reach * h + source_radius <= upper
        )
        policy["candidate_steps_days"] = list(steps)
        policy["sampling_time_geometry"] = "actual_native_TT_abscissas"
        policy["sampling_domain"] = {
            "native_published_range_jd_tt": list(NATIVE_RANGE_JD_TT),
            "source_range_jd_tt": [lower, upper],
            "geometric_padding_days": padding,
            "parent_reach_in_steps": parent_reach,
            "geometric_source_radius_days": source_radius,
            "source_url": (
                policy["source_url"]
                if planet == "Moon"
                else "https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/swemplan.c"
            ),
        }
        center_source = trace.observe(
            "moshier_geometric_source", "moshier", record_factor=False
        )
        source_rates = []
        source_checks: list[dict[str, object]] = []
        centers_agree = True
        sample_count = 0
        geometric_states: MoshierGeometricStates = {}
        source_steps = (source_step, source_step / 2) if radius >= source_radius else ()
        for source_step in source_steps:
            reduced_samples: dict[float, tuple[float, ReductionReceipt]] = {}

            def source_sample(delta: float) -> float:
                if delta not in reduced_samples:
                    epoch = julian_day_tt + delta
                    reduced_samples[delta] = reduced_longitude(
                        planet,
                        epoch,
                        sidereal=sidereal,
                        trace=trace,
                        contexts=contexts,
                        prefix=f"{planet}_moshier_source_{source_step:g}",
                        center_source=center_source,
                        model="moshier",
                        source_step_days=source_step,
                        moshier_geometric_states=geometric_states,
                    )
                else:
                    pass
                return reduced_samples[delta][0]

            center = source_sample(0.0)
            rate, trials = run_stencils(source_sample, center, steps)
            if len(steps) < len(STEPS_DAYS):
                # The endpoint truncates bilateral support to short,
                # noise-amplifying steps. Use the available homogeneous
                # span uniformly in this source geometry, retaining the
                # bilateral trials as diagnostics. Every direction whose
                # whole support exists still participates.
                def source_branch(delta: float) -> dict[str, object]:
                    epoch = julian_day_tt + delta
                    if epoch - source_radius < lower or epoch + source_radius > upper:
                        return {"cell": None}
                    else:
                        pass
                    source_sample(delta)
                    return reduced_samples[delta][1]["solar_interpolation_branch"]

                sided = homogeneous_side_derivative(
                    STEPS_DAYS, source_sample, source_branch
                )
                trials.append(
                    {
                        "stencil": "source_range_homogeneous_side_degree6_ls13_ls25",
                        "steps_days": sided.get("steps_days", []),
                        "rates_degrees_per_day": sided.get("rates", []),
                        "pair_differences_arcsec_per_day": sided.get(
                            "pair_differences_arcsec_per_day", []
                        ),
                        "directional_checks": sided["levels"],
                        "consecutive_converged_pairs": sided.get(
                            "consecutive_converged_pairs", 0
                        ),
                        "status": sided["status"],
                        "source_range_homogeneous_sides": sided,
                    }
                )
                rate = (
                    sided["selected_rate"] if sided["status"] == "converged" else None
                )
            else:
                pass
            shift = math.remainder(center - float(coordinates[0]), 360) * 3600
            centers_agree = centers_agree and abs(shift) <= SOURCE_POSITION_LINE_ARCSEC
            for trial in trials:
                trial["source_interpolation_step_days"] = source_step
            attempts.extend(trials)
            if rate is not None:
                source_rates.append(rate)
            else:
                pass
            sample_count += len(reduced_samples)
            source_checks.append(
                {
                    "source_interpolation_step_days": source_step,
                    "status": "converged" if rate is not None else "not_converged",
                    "selected_rate_degrees_per_day": rate,
                    "center_sampling_shift_arcseconds": shift,
                    "source_velocity": reduced_samples[0.0][1]["source_velocity"],
                    "sample_count": len(reduced_samples),
                    "maximum_frame_orthogonality_error": max(
                        receipt["frame_orthogonality_error"]
                        for _, receipt in reduced_samples.values()
                    ),
                }
            )
        difference = (
            abs(source_rates[0] - source_rates[1]) * 3600
            if len(source_rates) == 2
            else None
        )
        if (
            difference is not None
            and difference <= CONVERGENCE_LINE_ARCSEC_PER_DAY
            and centers_agree
        ):
            result = source_rates[-1]
        else:
            pass
        policy["source_reduction"] = {
            "method_id": (
                MOSHIER_LUNAR_METHOD_ID if planet == "Moon" else MOSHIER_METHOD_ID
            ),
            "source_step_checks": source_checks,
            "source_step_disagreement_arcsec_per_day": difference,
            "position_equivalence_line_arcsec": SOURCE_POSITION_LINE_ARCSEC,
            "centers_within_position_line": (centers_agree if source_checks else None),
            "status": "applied" if result is not None else "not_applied",
            "displayed_native_position_changed": False,
            "source_context_recording": "coherent_native_builtin_by_role",
            "scope": "Stable evaluation of the published source-speed operators: backward Earth/planet differences and the forward-biased three-point Moon difference. Both source steps meet their declared convergence guards. A witnessed native range restriction selects the existing homogeneous-side method with 13/25 fits, three levels and every eligible direction; bilateral trials stay in attempts. Auxiliary center agreement is a source-model diagnostic, not observed accuracy. No coefficients or expected rates are fitted to an epoch.",
        }
        assert_physical_configuration(selected)
        if source_trace is None:
            trace.finish()
        else:
            pass
    return result, {
        **policy,
        "status": "applied" if result is not None else "not_applied",
        **({} if result is not None else {"reason": "position_motion_not_converged"}),
        "attempts": attempts,
        "sample_count": sample_count,
        "source_contexts": contexts,
    }
