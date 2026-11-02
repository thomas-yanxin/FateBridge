"""Differentiate Moshier's complete apparent longitude, without an oracle.

This corrects a rate/position consistency problem; it does not improve the
underlying analytical position theory or turn it into a DE441 ephemeris.
"""

from __future__ import annotations

import math
from importlib.metadata import version
from typing import Any, Dict, Optional, Sequence, Tuple

from fatebridge.core.astro import runtime
from fatebridge.core.astro.lunar_motion import SOURCE_VERSION
from fatebridge.core.astro.native_coordinates import require_spherical_coordinates
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
    local_polynomial_stencil,
    longitude_stencil,
    one_sided_polynomial_stencil,
)
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.utils.errors import EphemerisSourceError

METHOD_ID = "fatebridge_moshier_apparent_position_derivative_v1"
SIDEREAL_METHOD_ID = "fatebridge_moshier_lahiri_position_derivative_v1"
TARGETS = frozenset(
    {
        "Sun",
        "Moon",
        "Mercury",
        "Venus",
        "Mars",
        "Jupiter",
        "Saturn",
        "Uranus",
        "Neptune",
        "Pluto",
    }
)
# Binary TT offsets remain exactly represented over the native Moshier range.
# Unlike compressed Swiss files, the analytical series has no daily interpolation
# cell. Coarser candidates reduce amplification of native coordinate/retarded-JD
# roundoff; the same refinement and directional criteria still decide acceptance.
STEPS_DAYS = tuple(2.0**-k for k in range(1, 12))


def complete_moshier_longitude_rate(
    planet: str,
    julian_day_tt: float,
    coordinates: Sequence[float],
    *,
    sidereal: bool = False,
    source_trace: Optional[PhysicalEphemerisTrace] = None,
) -> Tuple[Optional[float], Dict[str, Any]]:
    """Require consecutive refinement and a joint forward/backward check.

    Only Moshier and the inspected binding/native version are supported.
    Non-convergence leaves a visible unapplied receipt, never a substituted
    reference value. Frame/model/source failures remain errors.
    """
    swe = runtime.swe
    native_version = str(getattr(swe, "version", "unavailable"))
    binding = binding_distribution_version(swe, version)
    policy: Dict[str, Any] = {
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
        "selection_policy": "first_two_converged_pairs_and_parent_directional_joint_range",
        "source_url": "https://github.com/aloistr/swisseph/blob/v2.10.03/swemmoon.c#L915-L928",
        "scope": "Derivative of complete native Moshier apparent longitude. Native positions and their analytical theory remain unchanged. Internal agreement does not bound physical-model error, station time or real-world prediction.",
    }
    if planet not in TARGETS:
        return None, {**policy, "status": "not_applied", "reason": "unsupported_target"}
    if swe is None or (native_version, binding) != SOURCE_VERSION:
        return None, {
            **policy,
            "status": "not_applied",
            "reason": "unverified_native_version",
        }
    if (
        not math.isfinite(julian_day_tt)
        or len(coordinates) < 4
        or not all(math.isfinite(v) for v in coordinates[:4])
    ):
        raise EphemerisSourceError("coordinate_values_unavailable")
    trace = source_trace if source_trace is not None else PhysicalEphemerisTrace()
    contexts: Dict[str, Any] = {}
    attempts = []
    result: Optional[float] = None
    samples: Dict[float, float] = {0.0: float(coordinates[0])}
    with runtime.preserve_ephemeris_path():
        selected = configured_ephemeris_path()
        if sidereal:
            runtime.ephemeris_call("set_sid_mode", swe.SIDM_LAHIRI, 0.0, 0.0)
        flags = swe.FLG_MOSEPH | swe.FLG_SPEED | (swe.FLG_SIDEREAL if sidereal else 0)

        def sample(delta: float) -> float:
            if delta not in samples:
                epoch = julian_day_tt + delta
                if epoch - julian_day_tt != delta:
                    raise EphemerisSourceError("coordinate_motion_unavailable")
                state, returned = runtime.ephemeris_call(
                    "calc", epoch, PLANET_SWISSEPH_IDS[planet], flags
                )
                assert_physical_configuration(selected)
                if runtime.ephemeris_model_from_retflag(returned) != "moshier":
                    raise EphemerisSourceError("model_changed")
                longitude, _, _ = require_spherical_coordinates(
                    state, returned, native=swe, sidereal=sidereal
                )
                frame_tag = "lahiri_" if sidereal else ""
                factor = f"{planet}_moshier_motion_position_{frame_tag}{delta:+g}"
                contexts[factor] = trace.observe(factor, "moshier", record_factor=False)
                samples[delta] = longitude
            return samples[delta]

        for polynomial in (False, True):
            trial: Dict[str, Any] = {
                "stencil": (
                    "degree6_least_squares_25_point"
                    if polynomial
                    else "sixth_order_six_point"
                ),
                "steps_days": [],
                "rates_degrees_per_day": [],
                "pair_differences_arcsec_per_day": [],
                "directional_checks": [],
            }
            consecutive = 0
            rates = trial["rates_degrees_per_day"]
            for step in STEPS_DAYS:
                center = float(coordinates[0])
                rate = (
                    local_polynomial_stencil(
                        [sample(x * step) for x in LOCAL_NODES], center, step
                    )
                    if polynomial
                    else longitude_stencil(
                        [sample(x * step) for x in OFFSETS], center, step
                    )
                )
                trial["steps_days"].append(step)
                rates.append(rate)
                if len(rates) < 2:
                    continue
                error = abs(rate - rates[-2]) * 3600
                trial["pair_differences_arcsec_per_day"].append(error)
                consecutive = (
                    consecutive + 1 if error <= CONVERGENCE_LINE_ARCSEC_PER_DAY else 0
                )
                if consecutive < 2:
                    continue
                parent = 2 * step
                estimates = [
                    {
                        "sample_count": count,
                        "direction": direction,
                        "rate_degrees_per_day": one_sided_polynomial_stencil(
                            [sample(direction * x * parent) for x in nodes],
                            center,
                            parent,
                            direction,
                        ),
                    }
                    for count, (nodes, _) in DIRECTIONAL_POLYNOMIALS.items()
                    for direction in (-1, 1)
                ]
                values = rates[-3:] + [r["rate_degrees_per_day"] for r in estimates]
                spread = (max(values) - min(values)) * 3600
                passed = spread <= CONVERGENCE_LINE_ARCSEC_PER_DAY
                trial["directional_checks"].append(
                    {
                        "central_step_days": step,
                        "parent_step_days": parent,
                        "estimates": estimates,
                        "joint_spread_arcsec_per_day": spread,
                        "passed": passed,
                    }
                )
                if passed:
                    result = rate
                    break
            trial["consecutive_converged_pairs"] = consecutive
            trial["status"] = "converged" if result is not None else "not_converged"
            attempts.append(trial)
            if result is not None:
                break
        assert_physical_configuration(selected)
        if source_trace is None:
            trace.finish()
    return result, {
        **policy,
        "status": "applied" if result is not None else "not_applied",
        **({} if result is not None else {"reason": "position_motion_not_converged"}),
        "attempts": attempts,
        "sample_count": len(samples),
        "source_contexts": contexts,
    }
