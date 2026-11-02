"""Same-epoch continuous-frame evidence with exact native-state restoration.

The input position/velocity remain native apparent J2000 quantities. Reframing
them does not replace incomplete native orbital/relativistic derivatives or
certify an identity TT/TDB velocity map. The primary D1 factors stay explicit.
"""

from __future__ import annotations

import math
from importlib.metadata import version
from typing import Any, Dict, Sequence

from fatebridge.core.astro import runtime
from fatebridge.core.astro.continuous_lahiri import (
    COEFFICIENT_SHA256,
    METHOD_ID,
    cross,
    dot,
    project_state,
)
from fatebridge.core.astro.lunar_motion import SOURCE_VERSION
from fatebridge.core.astro.motion_source_window import observed_windows
from fatebridge.core.astro.native_identity import binding_distribution_version
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.ephemeris_runtime import (
    configured_ephemeris_path,
    configured_jpl_file,
    lock_ephemeris_configuration,
)
from fatebridge.utils.errors import EphemerisSourceError


def _angle_error(position: Sequence[float], coordinates: Sequence[float]) -> float:
    radius = math.hypot(*position)
    unit = tuple(v / radius for v in position)
    longitude, latitude = map(math.radians, coordinates[:2])
    native = (
        math.cos(latitude) * math.cos(longitude),
        math.cos(latitude) * math.sin(longitude),
        math.sin(latitude),
    )
    return (
        math.degrees(math.atan2(math.hypot(*cross(unit, native)), dot(unit, native)))
        * 3600
    )


def continuous_state_evidence(
    planet: str,
    julian_day_tt: float,
    coordinates: Sequence[float],
    returned_flags: int,
    model: str,
    *,
    source_trace: PhysicalEphemerisTrace,
) -> Dict[str, Any]:
    """Compute the continuous alternative while preserving the native center.

    Managed callers own traditional SIDM_LAHIRI. No path restoration or
    sidereal-mode mutation is introduced by this auxiliary transaction.
    """
    policy: Dict[str, Any] = {
        "model_id": METHOD_ID,
        "coefficient_sha256": COEFFICIENT_SHA256,
        "epoch_jd_tt": julian_day_tt,
        "ephemeris_model": model,
        "reference_frame": "continuous_scalar_obliquity_lahiri_ecliptic_of_date",
        "frame_derivative_variable": "TT Julian day",
        "vector_rate_scale": 1.0,
        "vector_rate_scale_basis": "declared_native_argument_day_identity; physical_TT_mapping_unqualified",
        "position_basis": "continuous_frame_applied_to_native_apparent_J2000_position",
        "velocity_basis": "native_apparent_J2000_velocity_plus_complete_continuous_frame_motion",
        "primary_D1_factors_changed": False,
        "complete_apparent_rate_certified": False,
        "physical_TT_clock_mapping_certified": False,
        "scope": "Continuous alternative Cartesian/spherical state with an explicit native input-velocity approximation. The complete frame term is included; the input physical derivative and clock map remain unqualified. This alternative does not drive primary D1 signs, factors or motion labels. Native-compatibility differences remain visible.",
    }
    swe = runtime.swe
    identity = (
        str(getattr(swe, "version", "unavailable")),
        binding_distribution_version(swe, version),
    )
    policy.update(native_version=identity[0], binding_version=identity[1])
    if swe is None or identity != SOURCE_VERSION:
        return {
            **policy,
            "status": "not_applied",
            "reason": "unverified_native_version",
        }
    if not math.isfinite(julian_day_tt):
        raise EphemerisSourceError("coordinate_values_unavailable")
    if not 1721425.5 <= julian_day_tt <= 5373485.5:
        return {
            **policy,
            "status": "not_applied",
            "reason": "outside_declared_frame_domain",
        }
    if planet not in PLANET_SWISSEPH_IDS or planet in {"Rahu", "Ketu"}:
        return {**policy, "status": "not_applied", "reason": "nonphysical_factor"}
    if len(coordinates) != 6 or not all(math.isfinite(v) for v in coordinates):
        raise EphemerisSourceError("coordinate_values_unavailable")
    with lock_ephemeris_configuration():
        selected_path, selected_jpl = configured_ephemeris_path(), configured_jpl_file()
        windows = observed_windows()
        center = source_trace.observe(
            f"{planet}_continuous_frame_center", model, record_factor=False
        )
        flags = (
            swe.FLG_SWIEPH
            | swe.FLG_SPEED
            | swe.FLG_NONUT
            | swe.FLG_J2000
            | swe.FLG_EQUATORIAL
            | swe.FLG_XYZ
        )
        try:
            inertial, inertial_flags = runtime.ephemeris_call(
                "calc", julian_day_tt, PLANET_SWISSEPH_IDS[planet], flags
            )
            required = (
                swe.FLG_SPEED
                | swe.FLG_NONUT
                | swe.FLG_J2000
                | swe.FLG_EQUATORIAL
                | swe.FLG_XYZ
            )
            forbidden = (
                swe.FLG_SIDEREAL
                | swe.FLG_RADIANS
                | swe.FLG_HELCTR
                | swe.FLG_BARYCTR
                | swe.FLG_TOPOCTR
                | swe.FLG_TRUEPOS
                | swe.FLG_NOABERR
            )
            if (
                inertial_flags < 0
                or inertial_flags & required != required
                or inertial_flags & forbidden
            ):
                raise EphemerisSourceError("coordinate_contract_changed")
            if runtime.ephemeris_model_from_retflag(inertial_flags) != model:
                raise EphemerisSourceError("coordinate_model_changed")
            if len(inertial) != 6 or not all(math.isfinite(v) for v in inertial):
                raise EphemerisSourceError("coordinate_values_unavailable")
            auxiliary = source_trace.observe(
                f"{planet}_continuous_frame_J2000", model, record_factor=False
            )
            if auxiliary != center or observed_windows() != windows:
                raise EphemerisSourceError("model_changed")
        finally:
            restored, restored_flags = runtime.ephemeris_call(
                "calc",
                julian_day_tt,
                PLANET_SWISSEPH_IDS[planet],
                swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED,
            )
            restored_context = source_trace.observe(
                f"{planet}_continuous_frame_restored", model, record_factor=False
            )
            if (
                tuple(restored) != tuple(coordinates)
                or restored_flags != returned_flags
                or restored_context != center
                or observed_windows() != windows
            ):
                raise EphemerisSourceError("model_changed")
            if (
                configured_ephemeris_path() != selected_path
                or configured_jpl_file() != selected_jpl
            ):
                raise EphemerisSourceError("physical_configuration_changed")
    try:
        value = project_state(
            julian_day_tt, inertial[:3], inertial[3:], vector_rate_scale=1.0
        )
    except ValueError as error:
        raise EphemerisSourceError("coordinate_values_unavailable") from error
    residual = _angle_error(value["position"], coordinates)
    return {
        **policy,
        "status": "partial",
        "position_status": "computed",
        "frame_derivative_status": "computed",
        "state": value,
        "native_J2000_state": list(inertial),
        "native_spherical_center": list(coordinates),
        "native_center_flags": returned_flags,
        "J2000_returned_flags": int(inertial_flags),
        "native_center_reproduced_exactly": True,
        "source_context_reproduced_exactly": True,
        "source_context": center,
        "native_position_difference_arcsec": residual,
        "native_position_reproduction_line_arcsec": 1e-7,
        "native_position_reproduced_within_line": residual <= 1e-7,
    }
