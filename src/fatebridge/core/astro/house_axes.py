"""Keep public sky axes distinct from a house system's polar axis branch.

Swiss documentation 6.4 and swehouse.c describe antipodal axis exchanges for
some polar houses. E supplies the eastern horizon intersection and the
meridian/ecliptic point whose RA is ARMC, independently of those house choices.
Noncritical native coordinates are retained. Near a polar grazing direction,
the eastern endpoint and supported cusp geometry receive a precision check.
"""

from __future__ import annotations

import math
from types import ModuleType
from typing import Any, Dict, Optional, Sequence, Tuple

from fatebridge.core.astro import runtime
from fatebridge.core.astro.angle_definitions import INTERSECTION_RESOLUTION_GUARD
from fatebridge.core.astro.horizon_precision import (
    CONVERGENCE_DEGREES,
    METHOD_ID,
    SELECTOR_WORK_GATE,
    HorizonGeometry,
    aligned_longitude,
    horizon_geometry,
)
from fatebridge.utils.errors import EphemerisSourceError


def _precision_geometry(
    julian_day_ut1: float, latitude: float, common: Sequence[float]
) -> tuple[HorizonGeometry, dict[str, Any]] | None:
    if not isinstance(runtime.swe, ModuleType) or abs(latitude) == 90:
        return None
    if not all(math.isfinite(v) for v in (julian_day_ut1, latitude, *common[:3])):
        raise EphemerisSourceError("horizon_direction_model_unavailable")
    gap = abs((common[0] - common[1] + 180) % 360 - 180)
    # A native intersection may be snapped to a cardinal longitude even when
    # its reported ASC is far from MC/IC. |A| also screens for a small horizon
    # normal without needing another ephemeris call for ordinary geometries.
    phi, theta = map(math.radians, (latitude, common[2]))
    a = math.cos(phi) * math.cos(theta)
    if min(gap, 180 - gap) > 1.0 and abs(a) > SELECTOR_WORK_GATE:
        return None
    try:
        auxiliary_tt = julian_day_ut1 + float(
            runtime.ephemeris_call("deltat_ex", julian_day_ut1, 0)
        )
        if not math.isfinite(auxiliary_tt):
            raise EphemerisSourceError("horizon_direction_model_unavailable")
        coordinates, returned = runtime.ephemeris_call(
            "calc", auxiliary_tt, runtime.swe.ECL_NUT, 0
        )
        if returned < 0 or not math.isfinite(coordinates[0]):
            raise EphemerisSourceError("horizon_direction_model_unavailable")
        eps = float(coordinates[0])
    except EphemerisSourceError:
        raise
    except Exception as error:
        raise EphemerisSourceError("horizon_direction_model_unavailable") from error
    phi, theta, e = map(math.radians, (latitude, common[2], eps))
    a = math.cos(phi) * math.cos(theta)
    b = math.fsum(
        [math.cos(phi) * math.sin(theta) * math.cos(e), math.sin(phi) * math.sin(e)]
    )
    selector = math.fsum(
        [math.cos(phi) * math.cos(e), math.sin(phi) * math.sin(e) * math.sin(theta)]
    )
    norm = math.hypot(a, b)
    # Keep the existing unresolved-input convention. sqrt(epsilon) diagnoses
    # conditioning; it is not the resolution guard and must not suppress a
    # resolvable intersection that needs higher precision.
    if norm <= INTERSECTION_RESOLUTION_GUARD:
        return None
    if norm > SELECTOR_WORK_GATE and abs(selector) > SELECTOR_WORK_GATE:
        return None
    try:
        model = horizon_geometry(latitude, float(common[2]), eps)
    except Exception as error:
        raise EphemerisSourceError("horizon_direction_precision_unavailable") from error
    return model, {
        "method_id": METHOD_ID,
        "working_decimal_digits": list(model.working_digits),
        "convergence_degrees": CONVERGENCE_DEGREES,
        "geographic_latitude": latitude,
        "armc": float(common[2]),
        "true_obliquity": eps,
        "house_auxiliary_tt": auxiliary_tt,
        "eastern_selector": model.eastern_selector,
        "intersection_normal_norm": model.intersection_norm,
        "tropical_model_ascendant": model.tropical_ascendant,
        "input_precision_scope": "exact_supplied_binary64_native_house_angle_parameters",
        "maximum_physical_error_arcseconds": None,
        "source_url": "https://aa.usno.navy.mil/faq/alt_az",
        "source_scope": "scalar altitude and eastern-direction equations; numerical model consistency only",
    }


def _canonical_house_axes(
    *,
    julian_day_ut1: float,
    latitude: float,
    longitude: float,
    house_code: bytes,
    native_angles: Sequence[float],
    flags: int = 0,
) -> tuple[
    tuple[float, ...], dict[str, Any] | None, HorizonGeometry | None, Sequence[float]
]:
    """Select common sky axes; retain any opposite native house-axis branch."""
    if house_code == b"E":
        physical = native_angles
    else:
        with runtime.preserve_ephemeris_path():
            _, physical = runtime.ephemeris_call(
                "houses_ex", julian_day_ut1, latitude, longitude, b"E", flags
            )
    precision = _precision_geometry(julian_day_ut1, latitude, physical)
    model = precision[0] if precision else None
    corrected = float(physical[0])
    if precision:
        assert model is not None
        corrected, action = aligned_longitude(
            corrected, float(physical[1]), model.ascendant_phase_from_midheaven
        )
        precision[1].update(
            native_common_ascendant=float(physical[0]),
            delivered_ascendant=corrected,
            ascendant_action=action,
            corrected_cusps=[],
            coordinate_frame=(
                "native_sidereal_zodiac"
                if flags & runtime.swe.FLG_SIDEREAL
                else "tropical"
            ),
        )
    public = (corrected, float(physical[1]), *native_angles[2:])
    separation = abs((native_angles[1] - public[1] + 180) % 360 - 180)
    ascendant_separation = abs((native_angles[0] - public[0] + 180) % 360 - 180)
    # These are the two branches of a plane intersection, not a numerical
    # accuracy threshold. Always retain the common physical-axis calculation.
    if separation <= 90 and ascendant_separation <= 90 and precision is None:
        return public, None, model, physical
    exchanged = "／".join(
        name
        for name, distance in (("ASC", ascendant_separation), ("MC", separation))
        if distance > 90
    )
    receipt: dict[str, Any] = {
        "policy_id": "fatebridge_sky_axes_separate_from_house_branch_v1",
        "house_code": house_code.decode("ascii"),
        "longitude_frame": (
            "native_sidereal_zodiac"
            if runtime.swe is not None and flags & runtime.swe.FLG_SIDEREAL
            else "tropical"
        ),
        "public_midheaven_definition": "ecliptic_meridian_intersection_with_right_ascension_equal_to_ARMC",
        "public_ascendant_definition": "eastern_ecliptic_horizon_intersection_subject_to_angle_definition",
        "public_midheaven": public[1],
        "native_house_midheaven": float(native_angles[1]),
        "public_ascendant": public[0],
        "native_house_ascendant": float(native_angles[0]),
        "meridian_branch_separation_degrees": separation,
        "ascendant_branch_separation_degrees": ascendant_separation,
        "native_cusps_and_projection_retained": True,
        "source_url": "https://www.astro.com/swisseph/swisseph.htm",
        "source_section": "6.4; swehouse.c polar branches",
        "note_zh": (
            f"公开四轴采用统一天球交点；此宫制在极区使用的{exchanged}制宫分支与公开天球轴相反。原宫头及落宫投影保留，两种轴须分别读取。"
            if exchanged
            else "公开四轴采用统一天球交点。"
        ),
    }
    if precision:
        receipt["policy_id"] = "fatebridge_sky_axes_and_eastern_precision_v2"
        receipt["eastern_direction_precision"] = precision[1]
        receipt["note_zh"] = (
            "公开四轴采用统一天球交点；原生制宫轴与修正前坐标另列。极区近切触的东方交点已用高精度复核，"
            + {
                "antipodal_endpoint": "修正了原生ASC的相反端点。",
                "high_precision_intersection": "修正了原生ASC的交点坐标。",
                "native_coordinate_retained": "原生ASC坐标保留。",
            }[precision[1]["ascendant_action"]]
            + "交点方向对时地输入高度敏感，此处核对的是声明的角度模型。"
        )
    return public, receipt, model, physical


def canonical_house_axes(
    *,
    julian_day_ut1: float,
    latitude: float,
    longitude: float,
    house_code: bytes,
    native_angles: Sequence[float],
    flags: int = 0,
) -> Tuple[Tuple[float, ...], Optional[Dict[str, Any]]]:
    public, receipt, _, _ = _canonical_house_axes(
        julian_day_ut1=julian_day_ut1,
        latitude=latitude,
        longitude=longitude,
        house_code=house_code,
        native_angles=native_angles,
        flags=flags,
    )
    return public, receipt


def canonical_house_geometry(
    *,
    julian_day_ut1: float,
    latitude: float,
    longitude: float,
    house_code: bytes,
    native_cusps: Sequence[float],
    native_angles: Sequence[float],
    flags: int = 0,
) -> tuple[tuple[float, ...], tuple[float, ...], dict[str, Any] | None]:
    public, receipt, model, common = _canonical_house_axes(
        julian_day_ut1=julian_day_ut1,
        latitude=latitude,
        longitude=longitude,
        house_code=house_code,
        native_angles=native_angles,
        flags=flags,
    )
    cusps = tuple(native_cusps)
    if model is None or receipt is None:
        return cusps, public, receipt
    changed = []
    phases = model.regiomontanus_phases if house_code == b"R" else model.campanus_phases
    if house_code in (b"R", b"C"):
        values = []
        for index, (value, phase) in enumerate(zip(cusps, phases)):
            corrected, action = aligned_longitude(float(value), float(common[1]), phase)
            values.append(corrected)
            if action != "native_coordinate_retained":
                changed.append(index + 1)
        cusps = tuple(values)
    elif house_code == b"W":
        cusps = tuple(
            (math.floor(public[0] / 30) * 30 + index * 30) % 360 for index in range(12)
        )
        changed = [
            index + 1
            for index, (old, new) in enumerate(zip(native_cusps, cusps))
            if old != new
        ]
    elif house_code in (b"E", b"V"):
        repaired, action = aligned_longitude(
            float(native_angles[0]),
            float(common[1]),
            model.ascendant_phase_from_midheaven,
        )
        if action != "native_coordinate_retained":
            shift = repaired - float(native_angles[0])
            from fatebridge.core.astro.geometry import combine_longitudes

            cusps = tuple(combine_longitudes(float(v), shift) for v in cusps)
            changed = list(range(1, 13))
    elif house_code == b"P":
        # Placidus cusp1/7 are the horizon endpoints. The intermediate time-
        # fraction cusps remain native; they are not reconstructed by linear
        # longitude interpolation or relabelled as another house method.
        values = list(cusps)
        for index, shift in ((0, 0), (6, 180)):
            corrected, action = aligned_longitude(
                float(values[index]),
                float(common[1]),
                (model.ascendant_phase_from_midheaven + shift) % 360,
            )
            values[index] = corrected
            if action != "native_coordinate_retained":
                changed.append(index + 1)
        cusps = tuple(values)
        receipt["source_section"] = "6.2.1; swehouse.c CalcH ASC/DSC identities"
    receipt["eastern_direction_precision"]["corrected_cusps"] = changed
    receipt["eastern_direction_precision"]["native_cusps"] = list(native_cusps)
    receipt["eastern_direction_precision"]["delivered_cusps"] = list(cusps)
    receipt["eastern_direction_precision"]["house_cusp_scope"] = (
        "placidus_horizon_endpoints1_7_checked_intermediate_native_time_fraction_cusps_retained"
        if house_code == b"P"
        else (
            "spatial_R_C_or_equal_E_V_W_endpoint_correction"
            if house_code in (b"R", b"C", b"E", b"V", b"W")
            else "other_native_house_cusps_retained_not_requalified"
        )
    )
    if changed:
        receipt["native_cusps_and_projection_retained"] = False
        receipt[
            "note_zh"
        ] += " 本次相应宫头端点已一并修正；原生落宫投影的声明政策另列。"
    return cusps, public, receipt
