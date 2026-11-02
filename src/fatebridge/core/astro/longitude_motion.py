"""Source-derived corrections to native apparent ecliptic longitude motion."""

from __future__ import annotations

import math
from importlib.metadata import version
from typing import Any, Dict, Optional, Sequence, Tuple, Union

from fatebridge.core.astro import moshier_motion, runtime
from fatebridge.core.astro.lunar_motion import (
    SOURCE_VERSION,
    lunar_light_time_correction,
)
from fatebridge.core.astro.native_identity import binding_distribution_version
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.position_motion import TARGETS, complete_position_rate
from fatebridge.core.astro.sidereal_origin_motion import traditional_lahiri_origin_wrap
from fatebridge.utils.errors import EphemerisSourceError

METHOD_ID = "fatebridge_apparent_longitude_motion_v4"
LunarAdjustment = Union[
    Tuple[float, str, float], Tuple[float, str, float, Optional[float]]
]
NUTATION_STEP_DAYS = 0.0001  # NUT_SPEED_INTV in the inspected native source.


def nutation_obliquity_rate(
    julian_day_tt: float, context: Dict[str, Any]
) -> Optional[float]:
    swe = runtime.swe
    native_version = str(getattr(swe, "version", "unavailable"))
    binding_version = binding_distribution_version(swe, version)
    previous = context.get("tropical_rotation")
    if (
        previous is not None
        and previous["epoch_jd_tt"] == julian_day_tt
        and previous.get("native_version") == native_version
        and previous.get("binding_version") == binding_version
    ):
        cached = previous.get("nutation_obliquity_rate_degrees_per_day")
        return float(cached) if cached is not None else None
    policy: Dict[str, Any] = {
        "method_id": "native_nutation_ecliptic_rotation_derivative_v1",
        "epoch_jd_tt": julian_day_tt,
        "native_version": native_version,
        "binding_version": binding_version,
        "source_function": "pyswisseph2.10.3.2/libswe/sweph.c:app_pos_rest,swi_nutate",
        "source_url": "https://www.astro.com/swisseph/swephprg.htm",
        "step_days": NUTATION_STEP_DAYS,
        "scope": "Nutation-in-obliquity part of the final ecliptic rotation derivative. Native NONUT/sidereal rates do not receive this term. Not a complete precession or apparent-speed certification.",
    }
    if swe is None or (native_version, binding_version) != SOURCE_VERSION:
        context["tropical_rotation"] = {
            **policy,
            "status": "not_applied",
            "reason": "unverified_native_version",
        }
        return None
    values = []
    for epoch in (julian_day_tt, julian_day_tt - NUTATION_STEP_DAYS):
        coordinates, flags = runtime.ephemeris_call(
            "calc", epoch, swe.ECL_NUT, swe.FLG_SWIEPH
        )
        if (
            flags < 0
            or len(coordinates) < 4
            or not all(math.isfinite(x) for x in coordinates[:4])
        ):
            raise EphemerisSourceError("coordinate_values_unavailable")
        values.append(float(coordinates[3]))
    rate = (values[0] - values[1]) / NUTATION_STEP_DAYS
    context["tropical_rotation"] = {
        **policy,
        "status": "applied",
        "nutation_obliquity_rate_degrees_per_day": rate,
    }
    return rate


def display_rotation_rate_change(
    longitude: float, latitude: float, obliquity_rate: float
) -> float:
    if (
        not all(math.isfinite(x) for x in (longitude, latitude, obliquity_rate))
        or not -90 < latitude < 90
    ):
        raise EphemerisSourceError("coordinate_values_unavailable")
    return (
        obliquity_rate
        * math.cos(math.radians(longitude))
        * math.tan(math.radians(latitude))
    )


def corrected_longitude_motion(
    planet: str,
    julian_day_tt: float,
    coordinates: Sequence[float],
    model: str,
    *,
    sidereal: bool = False,
    source_trace: Optional[PhysicalEphemerisTrace] = None,
    context: Optional[Dict[str, Any]] = None,
    lunar_adjustment: Optional[LunarAdjustment] = None,
) -> Dict[str, float]:
    """Keep native motion and each correction visible.

    Managed sidereal callers establish traditional SIDM_LAHIRI under the
    runtime lock; fixed-ecliptic auxiliary states must not enter this path.
    """
    metadata = context if context is not None else {}
    metadata["method_id"] = METHOD_ID
    native = float(coordinates[3])
    if not math.isfinite(native):
        raise EphemerisSourceError("coordinate_motion_unavailable")
    result = {"longitude_speed_native": native}
    origin_wrap = 0.0
    if sidereal:
        # Both managed sidereal callers establish traditional SIDM_LAHIRI.
        # Fixed-ecliptic auxiliary states never enter this branch.
        origin_wrap = traditional_lahiri_origin_wrap(julian_day_tt, metadata) or 0.0
        if origin_wrap:
            result["longitude_speed_sidereal_origin_wrap_correction"] = origin_wrap
    light = 0.0
    spatial = 0.0
    source_remainder: Optional[float] = None
    if planet == "Moon":
        if lunar_adjustment is not None:
            if len(lunar_adjustment) == 4:
                light, source_model, spatial, source_remainder = lunar_adjustment
            else:
                # Legacy internal triples explicitly carry the prior terms.
                light, source_model, spatial = lunar_adjustment
            if source_model != model:
                raise EphemerisSourceError("coordinate_model_changed")
            if not all(math.isfinite(value) for value in (light, spatial)):
                raise EphemerisSourceError("coordinate_motion_unavailable")
            result["longitude_speed_light_time_correction"] = light
            result["longitude_speed_spatial_aberration_correction"] = spatial
        else:
            correction, policy = lunar_light_time_correction(
                julian_day_tt, coordinates, model, source_trace=source_trace
            )
            metadata["lunar_light_time"] = policy
            if correction is not None:
                light = correction
                result["longitude_speed_light_time_correction"] = light
                spatial = policy["spatial_aberration"]["longitude_speed_correction"]
                result["longitude_speed_spatial_aberration_correction"] = spatial
                fixed = policy["fixed_frame_source_derivative"]
                if fixed["status"] == "applied":
                    source_remainder = float(fixed["longitude_speed_correction"])
        if source_remainder is not None:
            if not math.isfinite(source_remainder):
                raise EphemerisSourceError("coordinate_motion_unavailable")
            result["longitude_speed_lunar_source_remainder_correction"] = (
                source_remainder
            )
    rotation = 0.0
    if not sidereal:
        rate = nutation_obliquity_rate(julian_day_tt, metadata)
        if rate is not None:
            rotation = display_rotation_rate_change(
                float(coordinates[0]), float(coordinates[1]), rate
            )
            result["longitude_speed_rotation_correction"] = rotation
    result["longitude_speed"] = (
        math.fsum(
            (native, origin_wrap, light, spatial, source_remainder or 0.0, rotation)
        )
        if origin_wrap
        else native + light + spatial + (source_remainder or 0.0) + rotation
    )
    if planet == "Moon" and not sidereal:
        from fatebridge.core.astro.lunar_tropical_frame import (
            complete_lunar_tropical_rate,
        )

        fixed = metadata.get("lunar_light_time", {}).get(
            "fixed_frame_source_derivative"
        )
        complete, frame_policy = complete_lunar_tropical_rate(
            julian_day_tt, coordinates, model, fixed, result["longitude_speed"]
        )
        metadata["lunar_tropical_frame"] = frame_policy
        if complete is not None:
            correction = complete - result["longitude_speed"]
            result["longitude_speed_analytic_frame_correction"] = correction
            result["longitude_speed"] += correction
    if model == "moshier" and planet in moshier_motion.TARGETS:
        rate, policy = moshier_motion.complete_moshier_longitude_rate(
            planet,
            julian_day_tt,
            coordinates,
            sidereal=sidereal,
            source_trace=source_trace,
        )
    elif planet in TARGETS:
        rate, policy = complete_position_rate(
            planet,
            julian_day_tt,
            coordinates,
            model,
            sidereal=sidereal,
            source_trace=source_trace,
        )
    else:
        return result
    frame = "lahiri" if sidereal else "tropical"
    metadata.setdefault("complete_position_derivatives", {})[
        f"{planet}:{frame}"
    ] = policy
    if rate is not None:
        # This is the remainder needed after the explicit v1 terms;
        # the complete position stencil ALREADY includes frame motion.
        remainder = rate - result["longitude_speed"]
        result["longitude_speed_position_derivative_correction"] = remainder
        result["longitude_speed"] += remainder
    return result
