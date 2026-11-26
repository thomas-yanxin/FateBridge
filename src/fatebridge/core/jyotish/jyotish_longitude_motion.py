"""D1 instantaneous longitude motion, distinct from classical mean motions."""

from __future__ import annotations

from typing import Any, Sequence

from fatebridge.core.astro import runtime
from fatebridge.core.astro.longitude_motion import corrected_longitude_motion
from fatebridge.core.astro.motion_source_window import observed_windows
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.position_motion import AuxiliaryPositionModelChange
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.utils.errors import EphemerisSourceError

RULE = "jyotish.longitude_motion.v2"
METHOD = "jyotish_d1_apparent_longitude_motion_v1"


def _file_ids(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value.get("file_ids", [])) | {
            identity for child in value.values() for identity in _file_ids(child)
        }
    if isinstance(value, (tuple, list)):
        return {identity for child in value for identity in _file_ids(child)}
    return set()


def longitude_motion(
    planet: str,
    julian_day_tt: float,
    coordinates: Sequence[float],
    model: str,
    *,
    source_trace: PhysicalEphemerisTrace,
) -> dict[str, Any]:
    """Use the shared motion calculation and retain its exact applicability.

    A missing qualification is reported as native-only, never a complete-rate
    certificate. An auxiliary backend gap can retain the original rate only
    after exact center/context reproduction. Other source failures propagate.
    """
    metadata: dict[str, Any] = {}
    center_windows = observed_windows()
    center_source = source_trace.observe(
        f"{planet}_D1_motion_center", model, record_factor=False
    )
    try:
        values = corrected_longitude_motion(
            planet,
            julian_day_tt,
            coordinates,
            model,
            sidereal=True,
            source_trace=source_trace,
            context=metadata,
        )
    except AuxiliaryPositionModelChange as error:
        # Preserve a valid displayed position when only its finite-difference
        # neighbourhood lacks files. Never accept a rate across two models.
        swe = runtime.swe
        restored, flags = runtime.ephemeris_call(
            "calc",
            julian_day_tt,
            PLANET_SWISSEPH_IDS[planet],
            swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL,
        )
        restored_source = source_trace.observe(
            f"{planet}_D1_motion_restored", model, record_factor=False
        )
        if (
            runtime.ephemeris_model_from_retflag(flags) != model
            or tuple(restored) != tuple(coordinates)
            or observed_windows() != center_windows
            or restored_source != center_source
        ):
            raise EphemerisSourceError("model_changed") from error
        metadata.setdefault("complete_position_derivatives", {})[f"{planet}:lahiri"] = {
            "status": "not_applied",
            "reason": "auxiliary_sample_backend_changed",
            "sample_epoch_jd_tt": error.sample_epoch_jd_tt,
            "requested_model": error.requested_model,
            "actual_sample_model": error.actual_model,
            "center_native_state_reproduced_exactly": True,
            "center_file_context_reproduced_exactly": True,
        }
        origin = metadata.get("traditional_sidereal_origin_wrap", {})
        origin_correction = (
            float(origin["longitude_speed_correction"])
            if origin.get("status") == "applied"
            else 0.0
        )
        values = {
            "longitude_speed": float(coordinates[3]) + origin_correction,
            "longitude_speed_native": float(coordinates[3]),
        }
        if origin_correction:
            values["longitude_speed_sidereal_origin_wrap_correction"] = (
                origin_correction
            )
    complete = metadata.get("complete_position_derivatives", {}).get(
        f"{planet}:lahiri",
        {
            "status": "not_applied",
            "reason": "unsupported_target",
        },
    )
    lunar = metadata.get("lunar_light_time")
    if complete["status"] == "applied":
        basis = "complete_apparent_position_derivative"
    elif "longitude_speed_lunar_source_remainder_correction" in values:
        basis = "native_plus_lunar_fixed_frame_source_derivative"
    elif lunar is not None and lunar["status"] == "applied":
        basis = "native_plus_lunar_light_time_and_spatial_chain"
    elif "longitude_speed_sidereal_origin_wrap_correction" in values:
        basis = "native_with_traditional_sidereal_origin_wrap_removed"
    else:
        basis = "native_only"
    identities = _file_ids(metadata) | set(center_source["file_ids"])
    files = [
        item for item in source_trace.snapshot()["files"] if item["id"] in identities
    ]
    if identities != {item["id"] for item in files}:
        raise RuntimeError("D1 motion source identities are not resolvable")
    return {
        "longitude_speed_degrees_per_day": values["longitude_speed"],
        "longitude_speed_native_degrees_per_day": values["longitude_speed_native"],
        "longitude_motion_context": {
            "method_id": METHOD,
            "rule_id": RULE,
            "shared_method_id": metadata["method_id"],
            "epoch_jd_tt": julian_day_tt,
            "reference_frame": "native_traditional_lahiri_ecliptic_of_date",
            "independent_variable": "TT Julian day",
            "ephemeris_model": model,
            "rate_basis": basis,
            "center_source_context": center_source,
            "source_files": files,
            "source_scope": "Observed center and derivative auxiliary contexts. File hashes are checked again at the outer calculation endpoint; not an atomic read-set proof.",
            "corrections_degrees_per_day": {
                name.removeprefix("longitude_speed_"): value
                for name, value in values.items()
                if name not in {"longitude_speed", "longitude_speed_native"}
            },
            "complete_position_derivative": complete,
            **(
                {
                    "traditional_sidereal_origin_wrap": metadata[
                        "traditional_sidereal_origin_wrap"
                    ]
                }
                if "traditional_sidereal_origin_wrap" in metadata
                else {}
            ),
            **({"lunar_light_time": lunar} if lunar is not None else {}),
            "daily_mean_motion_used": False,
            "station_time_accuracy_certified": False,
            "scope": "Instantaneous D1 angular rate used for motion sign and the selected author's solar-orb branch. Complete derivative coverage is per body/backend. An eligible lunar fixed-frame source derivative includes observer acceleration; complete moving-frame derivatives, binary identity and physical TT-clock mapping remain unqualified. Native rates remain visible. Not classical daily mean motion, Cheshta Bala, an observational error bound or prediction evidence.",
        },
    }


def node_motion(
    julian_day_tt: float,
    speed: float,
    node_mode: str,
    *,
    antipode: bool = False,
    origin_wrap_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Nodes keep their declared native theory; Ketu is the Rahu antipode."""
    correction = (
        float(origin_wrap_policy["longitude_speed_correction"])
        if origin_wrap_policy is not None
        and origin_wrap_policy.get("status") == "applied"
        else 0.0
    )
    return {
        "longitude_speed_degrees_per_day": speed + correction,
        "longitude_speed_native_degrees_per_day": speed,
        "longitude_motion_context": {
            "method_id": METHOD,
            "rule_id": RULE,
            "epoch_jd_tt": julian_day_tt,
            "reference_frame": "native_traditional_lahiri_ecliptic_of_date",
            "independent_variable": "TT Julian day",
            "rate_basis": (
                "derived_antipode_of_Rahu"
                if antipode
                else (
                    "native_analytical_node_with_origin_wrap_removed"
                    if correction
                    else "native_analytical_node"
                )
            ),
            **(
                {
                    "traditional_sidereal_origin_wrap": origin_wrap_policy,
                    "corrections_degrees_per_day": (
                        {"sidereal_origin_wrap_correction": correction}
                        if correction
                        else {}
                    ),
                }
                if origin_wrap_policy is not None
                else {}
            ),
            "node_mode": node_mode,
            "complete_position_derivative": {
                "status": "not_applied",
                "reason": "nonphysical_factor",
            },
            "daily_mean_motion_used": False,
            "station_time_accuracy_certified": False,
            "scope": "Derivative of the declared analytical node longitude; Ketu shares Rahu's angular rate. Not the velocity of a physical body or Cheshta Bala.",
        },
    }
