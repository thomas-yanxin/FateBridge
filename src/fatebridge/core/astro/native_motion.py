"""Require the requested native daily motion before interpreting its sign."""

import math
from typing import Any, Dict, Optional, Sequence

from fatebridge.utils.errors import EphemerisSourceError


def require_longitude_speed(
    coordinates: Sequence[float], returned_flags: int, speed_flag: int
) -> float:
    if returned_flags < 0 or not returned_flags & speed_flag:
        raise EphemerisSourceError("coordinate_motion_unavailable")
    try:
        speed = float(coordinates[3])
    except (IndexError, TypeError, ValueError) as error:
        raise EphemerisSourceError("coordinate_motion_unavailable") from error
    if not math.isfinite(speed):
        raise EphemerisSourceError("coordinate_motion_unavailable")
    return speed


def context_motion(
    name: str,
    rates: Dict[str, Optional[float]],
    models: Dict[str, str],
    reference_frame: str,
    provenance: Optional[Dict[str, float]] = None,
    *,
    derivative_policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Describe supplied display-frame rates without inventing derivatives."""
    if name == "Pars Fortuna":
        rate = None
        basis = "ascendant_rate_not_computed"
        model = None
    elif name == "South Node":
        rate = rates.get("North Node")
        basis = (
            "opposite_point_inherits_same_longitude_rate"
            if rate is not None
            else "north_node_rate_not_computed"
        )
        model = models.get("North Node")
    else:
        rate = rates.get(name)
        basis = (
            "core_display_frame_rate"
            if rate is not None
            else "source_rate_not_computed"
        )
        model = models.get(name)
    if rate is not None and not math.isfinite(rate):
        raise EphemerisSourceError("coordinate_motion_unavailable")
    result = {
        "longitude_speed": rate,
        "unit": "degree_per_day",
        "direction": (
            "not_computed"
            if rate is None
            else (
                "retrograde"
                if rate < 0
                else "direct" if rate > 0 else "zero_instantaneous_rate"
            )
        ),
        "reference_frame": reference_frame,
        "basis": basis,
        "source_model": model,
    }
    if (
        provenance is not None
        and "longitude_speed_native" in provenance
        and rate is not None
    ):
        result["native_longitude_speed"] = provenance["longitude_speed_native"]
        light = provenance.get("longitude_speed_light_time_correction")
        spatial = provenance.get("longitude_speed_spatial_aberration_correction")
        lunar_source = provenance.get(
            "longitude_speed_lunar_source_remainder_correction"
        )
        rotation = provenance.get("longitude_speed_rotation_correction")
        analytic_frame = provenance.get("longitude_speed_analytic_frame_correction")
        position = provenance.get("longitude_speed_position_derivative_correction")
        origin = provenance.get("longitude_speed_sidereal_origin_wrap_correction")
        if light is not None:
            result["light_time_correction"] = light
        if spatial is not None:
            result["spatial_aberration_correction"] = spatial
        if lunar_source is not None:
            result["lunar_source_remainder_correction"] = lunar_source
        if rotation is not None:
            result["rotation_correction"] = rotation
        if analytic_frame is not None:
            result["analytic_frame_correction"] = analytic_frame
        if position is not None:
            result["position_derivative_correction"] = position
        if origin is not None:
            result["sidereal_origin_wrap_correction"] = origin
        result["method_id"] = (
            (derivative_policy or {}).get(
                "method_id", "complete_position_derivative_method_unavailable"
            )
            if position is not None
            else (
                "fatebridge_apparent_longitude_motion_v4"
                if light is not None or rotation is not None or origin is not None
                else "native_display_frame_rate"
            )
        )
        result["correction_status"] = (
            "partial"
            if name == "Moon" and light is None and position is None and origin is None
            else (
                "applied"
                if light is not None
                or rotation is not None
                or position is not None
                or origin is not None
                else "native_only"
            )
        )
        if name != "South Node" and (
            light is not None
            or rotation is not None
            or position is not None
            or origin is not None
        ):
            result["basis"] = "native_rate_plus_source_derived_motion_corrections"
        if analytic_frame is not None:
            result["method_id"] = "fatebridge_lunar_analytic_tropical_frame_v1"
            result["basis"] = (
                "fixed_reception_source_plus_analytic_tropical_frame_derivative"
            )
    return result
