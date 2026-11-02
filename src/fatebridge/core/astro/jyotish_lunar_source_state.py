"""A separately identified continuous state from the declared lunar formula.

This consumes already checked source evidence and introduces no native query.
Source differentiation is not physical ephemeris or TT/TDB qualification.
"""

from __future__ import annotations

import math
from typing import Any, Dict

from fatebridge.core.astro.continuous_lahiri import (
    COEFFICIENT_SHA256,
)
from fatebridge.core.astro.continuous_lahiri import METHOD_ID as FRAME_METHOD_ID
from fatebridge.core.astro.continuous_lahiri import (
    cross,
    decode_native_fixed_reception_state,
    dot,
    project_state,
)
from fatebridge.core.astro.lunar_motion import SOURCE_VERSION
from fatebridge.core.astro.lunar_observer import FIXED_FRAME_ID, METHOD_ID
from fatebridge.utils.errors import EphemerisSourceError

SOURCE_STATE_METHOD_ID = "continuous_lahiri_lunar_source_state_v1"


def source_derivative_state_evidence(
    julian_day_tt: float, continuous: Dict[str, Any], source: Dict[str, Any]
) -> Dict[str, Any]:
    """Reframe qualified source vectors, preserving the earlier native state."""
    if isinstance(julian_day_tt, bool) or not math.isfinite(julian_day_tt):
        raise EphemerisSourceError("coordinate_values_unavailable")
    policy = {
        "model_id": SOURCE_STATE_METHOD_ID,
        "frame_model_id": FRAME_METHOD_ID,
        "coefficient_sha256": COEFFICIENT_SHA256,
        "epoch_jd_tt": julian_day_tt,
        "source_method_id": METHOD_ID,
        "position_basis": "declared_lunar_source_formula_in_held_reception_frame",
        "velocity_basis": "source_formula_including_light_time_and_observer_beta_derivative",
        "vector_rate_scale": 1.0,
        "vector_rate_scale_basis": "declared_native_argument_day_identity; physical_TT_mapping_unqualified",
        "frame_derivative_variable": "TT Julian day",
        "primary_D1_factors_changed": False,
        "complete_apparent_rate_certified": False,
        "physical_TT_clock_mapping_certified": False,
        "scope": "The checked fixed-frame source-formula vector derivative is decoded with its held input basis and projected into the continuous TT frame. Native source velocity/acceleration and the physical time map remain unqualified. This separate alternative does not replace the earlier native-velocity state or primary D1 factors.",
    }
    if continuous.get("status") == "not_applied":
        return {
            **policy,
            "status": "not_applied",
            "reason": "continuous_input_unavailable",
            "input_reason": continuous.get("reason"),
        }
    if source.get("status") != "applied":
        return {
            **policy,
            "status": "not_applied",
            "reason": "fixed_frame_source_derivative_unavailable",
            "input_status": source.get("status", "unavailable"),
            "input_reason": source.get("reason"),
        }
    if (
        continuous.get("status") != "partial"
        or continuous.get("model_id") != FRAME_METHOD_ID
        or continuous.get("coefficient_sha256") != COEFFICIENT_SHA256
        or (continuous.get("native_version"), continuous.get("binding_version"))
        != SOURCE_VERSION
        or continuous.get("epoch_jd_tt") != julian_day_tt
        or source.get("epoch_jd_tt") != julian_day_tt
        or source.get("fixed_frame_epoch_jd_tt") != julian_day_tt
        or source.get("method_id") != METHOD_ID
        or source.get("fixed_frame_id") != FIXED_FRAME_ID
        or source.get("input_frame_held_fixed") is not True
        or source.get("input_velocity_time_variable") != "native_numeric_argument_day"
        or source.get("ephemeris_model") not in {"swieph", "jpl"}
        or source.get("ephemeris_model") != continuous.get("ephemeris_model")
        or source.get("center_native_states_reproduced_exactly") is not True
        or source.get("center_file_context_reproduced_exactly") is not True
        or continuous.get("native_center_reproduced_exactly") is not True
        or continuous.get("source_context_reproduced_exactly") is not True
        or "source_context" not in continuous
    ):
        raise EphemerisSourceError("coordinate_contract_changed")
    try:
        for name, line in (
            ("source_position_reproduction_arcsec", 1e-7),
            ("source_radius_reproduction_error_au", 1e-12),
        ):
            value = source[name]
            if (
                isinstance(value, bool)
                or not math.isfinite(value)
                or not 0 <= value <= line
            ):
                raise ValueError("Unqualified source position")
        decoded = decode_native_fixed_reception_state(
            julian_day_tt,
            source["full_fixed_frame_apparent_position_au"],
            source["full_fixed_frame_velocity_au_per_native_argument_day"],
        )
        native = continuous["native_J2000_state"]
        if len(native) != 6 or not all(
            not isinstance(x, bool) and math.isfinite(x) for x in native
        ):
            raise ValueError("Invalid native comparison state")
        position = decoded["position"]
        a = tuple(x / math.hypot(*position) for x in position)
        b = tuple(x / math.hypot(*native[:3]) for x in native[:3])
        angle = math.degrees(math.atan2(math.hypot(*cross(a, b)), dot(a, b))) * 3600
        radius = abs(math.hypot(*position) - math.hypot(*native[:3]))
        if angle > 1e-7 or radius > 1e-12:
            raise EphemerisSourceError("lunar_motion_position_mismatch")
        state = project_state(
            julian_day_tt,
            position,
            decoded["velocity_per_native_argument_day"],
            vector_rate_scale=1.0,
        )
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
        raise EphemerisSourceError("coordinate_values_unavailable") from error
    return {
        **policy,
        "status": "partial",
        "ephemeris_model": source["ephemeris_model"],
        "decoded_J2000_source_state": decoded,
        "state": state,
        "native_J2000_position_difference_arcsec": angle,
        "native_J2000_radius_difference_au": radius,
        "native_J2000_position_reproduction_line_arcsec": 1e-7,
        "native_J2000_radius_reproduction_line_au": 1e-12,
        "source_context": continuous["source_context"],
        "source_context_reproduced_exactly": True,
        "native_center_reproduced_exactly": True,
    }
