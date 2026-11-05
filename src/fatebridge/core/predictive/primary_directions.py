"""原始向运法（Primary Directions）推运法。"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.geometry import normalize_angle
from fatebridge.core.astro.reference import TRADITIONAL_PLANETS
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.ephemeris_runtime import ephemeris_call, swe

from ._common import (
    ASPECT_DEGREE_TO_META,
    LOT_KEY_BY_POINT_NAME,
    LOT_LABELS,
    LOT_POINT_NAMES,
    SWISSEPH_PLANET_IDS,
    TIMING_POINT_NAMES,
    TROPICAL_YEAR_DAYS,
    build_lot_payloads,
    build_lot_point_dict,
    calculate_age_years,
    extract_reference_longitudes,
    extract_reference_points,
    longitude_to_point_dict,
    normalize_sign_name,
    normalize_signed_angle,
    planet_label,
    point_absolute_position,
    resolve_egyptian_bound,
)

# 方法标签与坐标系映射
PRIMARY_DIRECTION_METHOD_LABELS = {
    "astroapp_alchabitius": "AstroAPP-Alchabitius",
    "equatorial": "赤经推运",
    "fatebridge_mundane_semiarc": "FateBridge-Mundane-SemiArc",
}
PRIMARY_DIRECTION_METHOD_COORDINATES = {
    "astroapp_alchabitius": ("ecliptic_longitude", "Arc"),
    "equatorial": ("right_ascension", "赤经"),
    "fatebridge_mundane_semiarc": ("mundane_semiarc", "SemiArc"),
}

# 时间键推进速率
PRIMARY_DIRECTION_TIME_KEY_RATES = {
    "Ptolemy": 1.0,
    "Naibod": 0.98564733,
    "Cardan": 0.98666667,
}

# 界限系统
PRIMARY_DIRECTION_BOUNDS_SYSTEM = "egyptian_bounds"
PRIMARY_DIRECTION_BOUNDS_LABEL = "埃及界限"

# 默认相位列表与承诺星
PRIMARY_DIRECTION_DEFAULT_ASPECTS = [0, 60, 90, 120, 180]
PRIMARY_DIRECTION_PROMISSORS = ["Ascendant", "Medium_Coeli"]

# 年龄与窗口限制
PRIMARY_DIRECTION_MAX_AGE_YEARS = 100.0
PRIMARY_DIRECTION_EXACT_WINDOW_YEARS = 0.01

# 宫位象限标签
PRIMARY_DIRECTION_QUADRANT_LABELS = {
    "above_east": "地平上东侧",
    "above_west": "地平上西侧",
    "below_west": "地平下西侧",
    "below_east": "地平下东侧",
    "horizon_east": "东方地平",
    "horizon_west": "西方地平",
    "upper_meridian": "上中天",
    "lower_meridian": "下中天",
}

# 时间相位标签
PRIMARY_DIRECTION_TIMING_PHASE_LABELS = {
    "past": "已发生",
    "future": "即将发生",
    "exact": "当前触发",
}


def primary_direction_method_label(method_name: str) -> str:
    return PRIMARY_DIRECTION_METHOD_LABELS.get(method_name, method_name)


def primary_direction_time_key_rate(time_key: str) -> float:
    return PRIMARY_DIRECTION_TIME_KEY_RATES.get(time_key, 1.0)


def primary_direction_coordinate_meta(
    pd_method: str,
) -> tuple[str, str]:
    if pd_method not in PRIMARY_DIRECTION_METHOD_COORDINATES:
        raise ValueError(
            "未知主限方法，请使用 astroapp_alchabitius、equatorial 或 fatebridge_mundane_semiarc"
        )
    if (
        pd_method
        in {
            "equatorial",
            "fatebridge_mundane_semiarc",
        }
        and swe is None
    ):
        return PRIMARY_DIRECTION_METHOD_COORDINATES["astroapp_alchabitius"]
    return PRIMARY_DIRECTION_METHOD_COORDINATES[pd_method]


def primary_direction_approximation_meta(pd_method: str) -> tuple[str, str]:
    if pd_method == "fatebridge_mundane_semiarc":
        return "mundane_semiarc_static_key", "半弧 mundane static key 近似"
    return "axis_static_key", "轴点 static key 近似"


def primary_direction_coordinate_runtime_meta(pd_method: str) -> tuple[str, str]:
    if pd_method == "equatorial":
        if swe is not None:
            return "equatorial_runtime_projection", "swisseph_equatorial_projection"
        return (
            "ecliptic_runtime_reference_fallback",
            "native_ecliptic_reference_fallback",
        )
    if pd_method == "fatebridge_mundane_semiarc":
        if swe is not None:
            return "mundane_runtime_projection", "swisseph_mundane_semiarc_projection"
        return (
            "ecliptic_runtime_reference_fallback",
            "native_ecliptic_reference_fallback",
        )
    return "ephemeris_runtime_model", "fatebridge_native_subject_abs_pos"


def build_primary_direction_equatorial_context(
    birth_info: AstroBirthInfo,
) -> Dict[str, float]:
    times = ephemeris_time(birth_info.require_utc_datetime)
    if times.jd_tt is None:
        raise ImportError("Swiss Ephemeris is required for equatorial directions")
    obliquity = ephemeris_call("calc", times.jd_tt, swe.ECL_NUT)[0][0]
    armc = (ephemeris_call("sidtime", times.jd_ut1) * 15 + birth_info.longitude) % 360
    return {
        "julian_day": times.jd_ut1,
        "julian_day_tt": float(times.jd_tt),
        "obliquity": float(obliquity),
        "armc": float(armc),
    }


def project_absolute_degree_to_equatorial(
    absolute_degree: float,
    *,
    obliquity: float,
) -> tuple[float, float]:
    right_ascension, declination, _ = swe.cotrans(
        (normalize_angle(absolute_degree), 0.0, 1.0),
        -obliquity,
    )
    return float(right_ascension), float(declination)


def point_equatorial_position(
    point_name: str,
    natal_subject: Any,
    *,
    julian_day: float,
    obliquity: float,
    armc: float,
    julian_day_tt: Optional[float] = None,
) -> tuple[float, float]:
    if point_name in SWISSEPH_PLANET_IDS:
        equatorial, retflag = ephemeris_call(
            "calc" if julian_day_tt is not None else "calc_ut",
            julian_day_tt if julian_day_tt is not None else julian_day,
            SWISSEPH_PLANET_IDS[point_name],
            swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_EQUATORIAL,
        )
        if retflag < 0:
            raise ValueError("Primary direction equatorial ephemeris failed")
        return float(equatorial[0]), float(equatorial[1])
    # MC is on the ecliptic, not on the equator: its RA is ARMC but its
    # declination is generally nonzero. Preserve the physical chart point.
    offset = getattr(natal_subject, "calculation_basis", {}).get(
        "ayanamsha_degrees", 0.0
    )
    return project_absolute_degree_to_equatorial(
        point_absolute_position(natal_subject, point_name) + offset,
        obliquity=obliquity,
    )


def project_equatorial_to_ecliptic(
    right_ascension: float,
    declination: float,
    *,
    obliquity: float,
    zodiac_offset: float = 0.0,
) -> tuple[float, float]:
    longitude, latitude, _ = swe.cotrans(
        (normalize_angle(right_ascension), declination, 1.0),
        obliquity,
    )
    return normalize_angle(float(longitude) - zodiac_offset), float(latitude)


def build_reprojected_primary_direction_chart_layers(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    arc_degrees: float,
) -> tuple[
    Dict[str, Dict[str, Any]],
    Dict[str, Dict[str, Any]],
    Dict[str, Dict[str, Any]],
]:
    equatorial_context = build_primary_direction_equatorial_context(birth_info)
    julian_day = equatorial_context["julian_day"]
    obliquity = equatorial_context["obliquity"]
    armc = equatorial_context["armc"]
    natal_lots = build_lot_payloads(natal_subject)
    asc_sign = normalize_sign_name(natal_subject.ascendant.sign)

    directed_points: Dict[str, Dict[str, Any]] = {}
    for point_name in TIMING_POINT_NAMES:
        right_ascension, declination = point_equatorial_position(
            point_name,
            natal_subject,
            julian_day=julian_day,
            julian_day_tt=equatorial_context["julian_day_tt"],
            obliquity=obliquity,
            armc=armc,
        )
        longitude, _latitude = project_equatorial_to_ecliptic(
            right_ascension + arc_degrees,
            declination,
            obliquity=obliquity,
            zodiac_offset=natal_subject.calculation_basis["ayanamsha_degrees"],
        )
        directed_points[point_name] = longitude_to_point_dict(point_name, longitude)

    directed_lots: Dict[str, Dict[str, Any]] = {}
    for lot_key, payload in natal_lots.items():
        right_ascension, declination = project_absolute_degree_to_equatorial(
            float(payload.get("longitude", payload["absolute_degree"]))
            + natal_subject.calculation_basis["ayanamsha_degrees"],
            obliquity=obliquity,
        )
        longitude, _latitude = project_equatorial_to_ecliptic(
            right_ascension + arc_degrees,
            declination,
            obliquity=obliquity,
            zodiac_offset=natal_subject.calculation_basis["ayanamsha_degrees"],
        )
        directed_lots[lot_key] = build_lot_point_dict(
            lot_key,
            longitude,
            asc_sign=asc_sign,
        )

    directed_axes = {
        point_name: directed_points[point_name]
        for point_name in PRIMARY_DIRECTION_PROMISSORS
    }
    return directed_points, directed_lots, directed_axes


def semiarc_degrees_for_declination(latitude: float, declination: float) -> float:
    latitude_radians = math.radians(latitude)
    declination_radians = math.radians(declination)
    horizon_term = -math.tan(latitude_radians) * math.tan(declination_radians)
    if horizon_term <= -1.0:
        return 180.0
    if horizon_term >= 1.0:
        return 0.0
    return math.degrees(math.acos(horizon_term))


def mundane_semiarc_position(
    *,
    hour_angle: float,
    semiarc_degrees: float,
) -> tuple[float, str]:
    if not math.isfinite(semiarc_degrees) or not 0 < semiarc_degrees < 180:
        raise ValueError(
            "Mundane semiarc projection is undefined for circumpolar points"
        )
    clamped_semiarc = semiarc_degrees
    nocturnal_semiarc = 180.0 - clamped_semiarc

    if -clamped_semiarc <= hour_angle <= 0.0:
        position = ((hour_angle + clamped_semiarc) / clamped_semiarc) * 90.0
        quadrant = "above_east"
    elif 0.0 < hour_angle <= clamped_semiarc:
        position = 90.0 + (hour_angle / clamped_semiarc) * 90.0
        quadrant = "above_west"
    elif hour_angle > clamped_semiarc:
        position = 180.0 + ((hour_angle - clamped_semiarc) / nocturnal_semiarc) * 90.0
        quadrant = "below_west"
    else:
        position = 270.0 + ((hour_angle + 180.0) / nocturnal_semiarc) * 90.0
        quadrant = "below_east"

    return normalize_angle(position), quadrant


def hour_angle_from_mundane_coordinate(
    coordinate_degrees: float,
    *,
    semiarc_degrees: float,
) -> float:
    normalized_coordinate = normalize_angle(coordinate_degrees)
    if not math.isfinite(semiarc_degrees) or not 0 < semiarc_degrees < 180:
        raise ValueError(
            "Mundane semiarc projection is undefined for circumpolar points"
        )
    clamped_semiarc = semiarc_degrees
    nocturnal_semiarc = 180.0 - clamped_semiarc

    if normalized_coordinate <= 90.0:
        return ((normalized_coordinate / 90.0) * clamped_semiarc) - clamped_semiarc
    if normalized_coordinate <= 180.0:
        return ((normalized_coordinate - 90.0) / 90.0) * clamped_semiarc
    if normalized_coordinate <= 270.0:
        return clamped_semiarc + (
            ((normalized_coordinate - 180.0) / 90.0) * nocturnal_semiarc
        )
    return -180.0 + (((normalized_coordinate - 270.0) / 90.0) * nocturnal_semiarc)


def build_reprojected_mundane_primary_direction_chart_layers(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    arc_degrees: float,
) -> tuple[
    Dict[str, Dict[str, Any]],
    Dict[str, Dict[str, Any]],
    Dict[str, Dict[str, Any]],
]:
    equatorial_context = build_primary_direction_equatorial_context(birth_info)
    julian_day = equatorial_context["julian_day"]
    obliquity = equatorial_context["obliquity"]
    armc = equatorial_context["armc"]
    natal_lots = build_lot_payloads(natal_subject)
    asc_sign = normalize_sign_name(natal_subject.ascendant.sign)

    directed_points: Dict[str, Dict[str, Any]] = {}
    for point_name in TRADITIONAL_PLANETS:
        right_ascension, declination = point_equatorial_position(
            point_name,
            natal_subject,
            julian_day=julian_day,
            julian_day_tt=equatorial_context["julian_day_tt"],
            obliquity=obliquity,
            armc=armc,
        )
        semiarc = semiarc_degrees_for_declination(birth_info.latitude, declination)
        natal_hour_angle = normalize_signed_angle(armc - right_ascension)
        natal_coordinate, _quadrant = mundane_semiarc_position(
            hour_angle=natal_hour_angle,
            semiarc_degrees=semiarc,
        )
        target_coordinate = normalize_angle(natal_coordinate + arc_degrees)
        directed_hour_angle = hour_angle_from_mundane_coordinate(
            target_coordinate,
            semiarc_degrees=semiarc,
        )
        directed_right_ascension = normalize_angle(armc - directed_hour_angle)
        longitude, _latitude = project_equatorial_to_ecliptic(
            directed_right_ascension,
            declination,
            obliquity=obliquity,
            zodiac_offset=natal_subject.calculation_basis["ayanamsha_degrees"],
        )
        directed_points[point_name] = longitude_to_point_dict(point_name, longitude)

    for point_name, base_coordinate in (("Ascendant", 0.0), ("Medium_Coeli", 90.0)):
        _, declination = point_equatorial_position(
            point_name,
            natal_subject,
            julian_day=julian_day,
            julian_day_tt=equatorial_context["julian_day_tt"],
            obliquity=obliquity,
            armc=armc,
        )
        semiarc = semiarc_degrees_for_declination(birth_info.latitude, declination)
        target_coordinate = normalize_angle(base_coordinate + arc_degrees)
        directed_hour_angle = hour_angle_from_mundane_coordinate(
            target_coordinate,
            semiarc_degrees=semiarc,
        )
        directed_right_ascension = normalize_angle(armc - directed_hour_angle)
        longitude, _latitude = project_equatorial_to_ecliptic(
            directed_right_ascension,
            declination,
            obliquity=obliquity,
            zodiac_offset=natal_subject.calculation_basis["ayanamsha_degrees"],
        )
        directed_points[point_name] = longitude_to_point_dict(point_name, longitude)

    directed_lots: Dict[str, Dict[str, Any]] = {}
    for lot_key, payload in natal_lots.items():
        right_ascension, declination = project_absolute_degree_to_equatorial(
            float(payload.get("longitude", payload["absolute_degree"]))
            + natal_subject.calculation_basis["ayanamsha_degrees"],
            obliquity=obliquity,
        )
        semiarc = semiarc_degrees_for_declination(birth_info.latitude, declination)
        natal_hour_angle = normalize_signed_angle(armc - right_ascension)
        natal_coordinate, _quadrant = mundane_semiarc_position(
            hour_angle=natal_hour_angle,
            semiarc_degrees=semiarc,
        )
        target_coordinate = normalize_angle(natal_coordinate + arc_degrees)
        directed_hour_angle = hour_angle_from_mundane_coordinate(
            target_coordinate,
            semiarc_degrees=semiarc,
        )
        directed_right_ascension = normalize_angle(armc - directed_hour_angle)
        longitude, _latitude = project_equatorial_to_ecliptic(
            directed_right_ascension,
            declination,
            obliquity=obliquity,
            zodiac_offset=natal_subject.calculation_basis["ayanamsha_degrees"],
        )
        directed_lots[lot_key] = build_lot_point_dict(
            lot_key,
            longitude,
            asc_sign=asc_sign,
        )

    directed_axes = {
        point_name: directed_points[point_name]
        for point_name in PRIMARY_DIRECTION_PROMISSORS
    }
    return directed_points, directed_lots, directed_axes


def quadrant_for_mundane_coordinate(coordinate_degrees: float) -> str:
    normalized = normalize_angle(coordinate_degrees)
    if math.isclose(normalized, 0.0, abs_tol=1e-6) or math.isclose(
        normalized, 360.0, abs_tol=1e-6
    ):
        return "horizon_east"
    if math.isclose(normalized, 90.0, abs_tol=1e-6):
        return "upper_meridian"
    if math.isclose(normalized, 180.0, abs_tol=1e-6):
        return "horizon_west"
    if math.isclose(normalized, 270.0, abs_tol=1e-6):
        return "lower_meridian"
    if normalized < 90.0:
        return "above_east"
    if normalized < 180.0:
        return "above_west"
    if normalized < 270.0:
        return "below_west"
    return "below_east"


def build_primary_direction_coordinate_entry(
    *,
    item_key: str,
    item_label: str,
    coordinate_degrees: float,
    coordinate_system: str,
    coordinate_label: str,
    arc_applied_degrees: float = 0.0,
) -> Dict[str, Any]:
    normalized_coordinate = normalize_angle(coordinate_degrees)
    entry = {
        "key": item_key,
        "label": item_label,
        "coordinate_system": coordinate_system,
        "coordinate_label": coordinate_label,
        "coordinate_degrees": round(normalized_coordinate, 4),
        "arc_applied_degrees": round(arc_applied_degrees, 4),
    }
    if coordinate_system == "mundane_semiarc":
        quadrant = quadrant_for_mundane_coordinate(normalized_coordinate)
        entry.update(
            {
                "quadrant": quadrant,
                "quadrant_label": PRIMARY_DIRECTION_QUADRANT_LABELS[quadrant],
                "phase_within_quadrant_degrees": round(normalized_coordinate % 90.0, 4),
            }
        )
    return entry


def build_primary_direction_coordinate_rings(
    coordinate_map: Dict[str, float],
    *,
    coordinate_system: str,
    coordinate_label: str,
    arc_applied_degrees: float = 0.0,
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    return {
        "points": {
            point_name: build_primary_direction_coordinate_entry(
                item_key=point_name,
                item_label=planet_label(point_name),
                coordinate_degrees=coordinate_map[point_name] + arc_applied_degrees,
                coordinate_system=coordinate_system,
                coordinate_label=coordinate_label,
                arc_applied_degrees=arc_applied_degrees,
            )
            for point_name in TIMING_POINT_NAMES
        },
        "lots": {
            lot_key: build_primary_direction_coordinate_entry(
                item_key=LOT_POINT_NAMES[lot_key],
                item_label=LOT_LABELS[lot_key],
                coordinate_degrees=coordinate_map[LOT_POINT_NAMES[lot_key]]
                + arc_applied_degrees,
                coordinate_system=coordinate_system,
                coordinate_label=coordinate_label,
                arc_applied_degrees=arc_applied_degrees,
            )
            for lot_key in LOT_POINT_NAMES
        },
    }


def resolve_primary_direction_coordinate_entry(
    point_name: str,
    *,
    coordinate_points: Dict[str, Dict[str, Any]],
    coordinate_lots: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if point_name in coordinate_points:
        return coordinate_points[point_name]
    lot_key = LOT_KEY_BY_POINT_NAME.get(point_name)
    if lot_key:
        return coordinate_lots.get(lot_key)
    return None


def build_primary_direction_hit_coordinate_context(
    hit: Dict[str, Any],
    *,
    coordinate_system: str,
    coordinate_label: str,
    natal_coordinate_points: Dict[str, Dict[str, Any]],
    natal_coordinate_lots: Dict[str, Dict[str, Any]],
    current_coordinate_points: Dict[str, Dict[str, Any]],
    current_coordinate_lots: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    promissor_natal = resolve_primary_direction_coordinate_entry(
        hit["promissor"],
        coordinate_points=natal_coordinate_points,
        coordinate_lots=natal_coordinate_lots,
    )
    promissor_current = resolve_primary_direction_coordinate_entry(
        hit["promissor"],
        coordinate_points=current_coordinate_points,
        coordinate_lots=current_coordinate_lots,
    )
    significator_natal = resolve_primary_direction_coordinate_entry(
        hit["significator"],
        coordinate_points=natal_coordinate_points,
        coordinate_lots=natal_coordinate_lots,
    )
    # A hit always references resolvable promissor/significator coordinates, so
    # these lookups are non-None on every real call; assert to narrow the Optional.
    assert promissor_current is not None
    assert significator_natal is not None
    aspect_target_degrees = normalize_angle(
        significator_natal["coordinate_degrees"] + hit["aspect_variant_degrees"]
    )
    aspect_target = build_primary_direction_coordinate_entry(
        item_key=f"{hit['significator']}_{hit['aspect']}",
        item_label=f"{hit['significator_label']} {hit['aspect_label']}",
        coordinate_degrees=aspect_target_degrees,
        coordinate_system=coordinate_system,
        coordinate_label=coordinate_label,
    )
    current_orb = min(
        normalize_angle(
            promissor_current["coordinate_degrees"]
            - aspect_target["coordinate_degrees"]
        ),
        normalize_angle(
            aspect_target["coordinate_degrees"]
            - promissor_current["coordinate_degrees"]
        ),
    )
    return {
        "promissor_natal": promissor_natal,
        "promissor_current": promissor_current,
        "significator_natal": significator_natal,
        "aspect_target": aspect_target,
        "current_orb_degrees": round(current_orb, 4),
    }


def primary_direction_arc_applied_degrees(hit: Dict[str, Any]) -> float:
    arc_degrees = float(hit.get("arc_degrees", 0.0))
    if hit.get("direction_mode") == "converse":
        return -arc_degrees
    return arc_degrees


def primary_direction_timing_phase(relative_years: float) -> tuple[str, str]:
    if abs(relative_years) <= PRIMARY_DIRECTION_EXACT_WINDOW_YEARS:
        phase = "exact"
    elif relative_years < 0:
        phase = "past"
    else:
        phase = "future"
    return phase, PRIMARY_DIRECTION_TIMING_PHASE_LABELS[phase]


def enrich_primary_direction_hit_with_coordinate_context(
    hit: Dict[str, Any],
    *,
    natal_coordinates: Dict[str, float],
    coordinate_system: str,
    coordinate_label: str,
    natal_coordinate_points: Dict[str, Dict[str, Any]],
    natal_coordinate_lots: Dict[str, Dict[str, Any]],
    arc_applied_degrees: float,
) -> Dict[str, Any]:
    current_coordinate_rings = build_primary_direction_coordinate_rings(
        natal_coordinates,
        coordinate_system=coordinate_system,
        coordinate_label=coordinate_label,
        arc_applied_degrees=arc_applied_degrees,
    )
    return {
        **hit,
        "coordinate_context": build_primary_direction_hit_coordinate_context(
            hit,
            coordinate_system=coordinate_system,
            coordinate_label=coordinate_label,
            natal_coordinate_points=natal_coordinate_points,
            natal_coordinate_lots=natal_coordinate_lots,
            current_coordinate_points=current_coordinate_rings["points"],
            current_coordinate_lots=current_coordinate_rings["lots"],
        ),
    }


def normalize_primary_direction_aspects(
    pd_aspects: Optional[List[int]],
) -> List[int]:
    if not pd_aspects:
        return PRIMARY_DIRECTION_DEFAULT_ASPECTS.copy()
    normalized: List[int] = []
    for value in pd_aspects:
        try:
            degree = int(float(value)) % 360
        except (TypeError, ValueError):
            continue
        if degree not in normalized:
            normalized.append(degree)
    return normalized or PRIMARY_DIRECTION_DEFAULT_ASPECTS.copy()


def primary_direction_aspect_variants(aspect_degree: int) -> List[float]:
    if aspect_degree in {0, 180}:
        return [float(aspect_degree)]
    return [float(aspect_degree), float((360 - aspect_degree) % 360)]


def primary_direction_aspect_meta(aspect_degree: int) -> tuple[str, str]:
    meta = ASPECT_DEGREE_TO_META.get(aspect_degree)
    if meta is not None:
        return meta
    return f"{aspect_degree}deg", f"{aspect_degree}°"


def build_primary_direction_targets_with_coordinates(
    natal_subject: Any,
    *,
    coordinate_map: Dict[str, float],
) -> List[Dict[str, Any]]:
    targets = [
        {
            "name": point_name,
            "label": planet_label(point_name),
            "longitude": coordinate_map[point_name],
        }
        for point_name in TIMING_POINT_NAMES
    ]
    for lot_key, payload in build_lot_payloads(natal_subject).items():
        point_name = LOT_POINT_NAMES[lot_key]
        targets.append(
            {
                "name": point_name,
                "label": LOT_LABELS[lot_key],
                "longitude": coordinate_map[point_name],
            }
        )
    return targets


def extract_primary_direction_coordinate_payload(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    pd_method: str,
) -> Dict[str, Any]:
    coordinate_system, _coordinate_label = primary_direction_coordinate_meta(pd_method)
    coordinate_precision, coordinate_backend = (
        primary_direction_coordinate_runtime_meta(pd_method)
    )
    coordinate_map = extract_reference_longitudes(natal_subject)
    lot_payloads = build_lot_payloads(natal_subject)
    for lot_key, payload in lot_payloads.items():
        coordinate_map[LOT_POINT_NAMES[lot_key]] = float(
            payload.get("longitude", payload["absolute_degree"])
        )

    approximation_method = (
        pd_method if coordinate_system == "mundane_semiarc" else "astroapp_alchabitius"
    )
    approximation, approximation_label = primary_direction_approximation_meta(
        approximation_method
    )
    result = {
        "coordinates": coordinate_map,
        "diagnostics": {},
        "approximation": approximation,
        "approximation_label": approximation_label,
        "coordinate_precision": coordinate_precision,
        "coordinate_backend": coordinate_backend,
    }

    if swe is None:
        return result

    if pd_method not in {
        "equatorial",
        "fatebridge_mundane_semiarc",
    }:
        return result

    equatorial_context = build_primary_direction_equatorial_context(birth_info)
    julian_day = equatorial_context["julian_day"]
    obliquity = equatorial_context["obliquity"]
    armc = equatorial_context["armc"]

    if pd_method == "equatorial":
        diagnostics: Dict[str, Dict[str, Any]] = {}
        for point_name in TIMING_POINT_NAMES:
            right_ascension, declination = point_equatorial_position(
                point_name,
                natal_subject,
                julian_day=julian_day,
                julian_day_tt=equatorial_context["julian_day_tt"],
                obliquity=obliquity,
                armc=armc,
            )
            coordinate_map[point_name] = right_ascension
            diagnostics[point_name] = {
                "projection": "equatorial",
                "projection_label": "赤道坐标投影",
                "right_ascension": round(right_ascension, 4),
                "declination": round(declination, 4),
            }

        for lot_key, payload in lot_payloads.items():
            point_name = LOT_POINT_NAMES[lot_key]
            right_ascension, declination = project_absolute_degree_to_equatorial(
                float(payload.get("longitude", payload["absolute_degree"]))
                + natal_subject.calculation_basis["ayanamsha_degrees"],
                obliquity=obliquity,
            )
            coordinate_map[point_name] = right_ascension
            diagnostics[point_name] = {
                "projection": "equatorial",
                "projection_label": "赤道坐标投影",
                "right_ascension": round(right_ascension, 4),
                "declination": round(declination, 4),
            }

        result["diagnostics"] = diagnostics
        return result

    coordinate_map["Ascendant"] = 0.0
    coordinate_map["Medium_Coeli"] = 90.0
    diagnostics = {
        "Ascendant": {
            "projection": "mundane_semiarc",
            "projection_label": "半弧坐标投影",
            "quadrant": "horizon_east",
            "quadrant_label": PRIMARY_DIRECTION_QUADRANT_LABELS["horizon_east"],
            "mundane_position_degrees": 0.0,
        },
        "Medium_Coeli": {
            "projection": "mundane_semiarc",
            "projection_label": "半弧坐标投影",
            "quadrant": "upper_meridian",
            "quadrant_label": PRIMARY_DIRECTION_QUADRANT_LABELS["upper_meridian"],
            "mundane_position_degrees": 90.0,
        },
    }

    for point_name in PRIMARY_DIRECTION_PROMISSORS:
        right_ascension, declination = point_equatorial_position(
            point_name,
            natal_subject,
            julian_day=julian_day,
            julian_day_tt=equatorial_context["julian_day_tt"],
            obliquity=obliquity,
            armc=armc,
        )
        semiarc = semiarc_degrees_for_declination(birth_info.latitude, declination)
        diagnostics[point_name].update(
            {
                "right_ascension": round(right_ascension, 4),
                "declination": round(declination, 4),
                "hour_angle_degrees": round(
                    normalize_signed_angle(armc - right_ascension), 4
                ),
                "semiarc_degrees": round(semiarc, 4),
                "nocturnal_semiarc_degrees": round(180.0 - semiarc, 4),
            }
        )

    for point_name in TRADITIONAL_PLANETS:
        right_ascension, declination = point_equatorial_position(
            point_name,
            natal_subject,
            julian_day=julian_day,
            julian_day_tt=equatorial_context["julian_day_tt"],
            obliquity=obliquity,
            armc=armc,
        )
        semiarc = semiarc_degrees_for_declination(birth_info.latitude, declination)
        hour_angle = normalize_signed_angle(armc - right_ascension)
        mundane_position, quadrant = mundane_semiarc_position(
            hour_angle=hour_angle,
            semiarc_degrees=semiarc,
        )
        coordinate_map[point_name] = mundane_position
        diagnostics[point_name] = {
            "projection": "mundane_semiarc",
            "projection_label": "半弧坐标投影",
            "right_ascension": round(right_ascension, 4),
            "declination": round(declination, 4),
            "hour_angle_degrees": round(hour_angle, 4),
            "semiarc_degrees": round(semiarc, 4),
            "nocturnal_semiarc_degrees": round(180.0 - semiarc, 4),
            "quadrant": quadrant,
            "quadrant_label": PRIMARY_DIRECTION_QUADRANT_LABELS[quadrant],
            "mundane_position_degrees": round(mundane_position, 4),
        }

    for lot_key, payload in lot_payloads.items():
        point_name = LOT_POINT_NAMES[lot_key]
        right_ascension, declination = project_absolute_degree_to_equatorial(
            float(payload.get("longitude", payload["absolute_degree"]))
            + natal_subject.calculation_basis["ayanamsha_degrees"],
            obliquity=obliquity,
        )
        semiarc = semiarc_degrees_for_declination(birth_info.latitude, declination)
        hour_angle = normalize_signed_angle(armc - right_ascension)
        mundane_position, quadrant = mundane_semiarc_position(
            hour_angle=hour_angle,
            semiarc_degrees=semiarc,
        )
        coordinate_map[point_name] = mundane_position
        diagnostics[point_name] = {
            "projection": "mundane_semiarc",
            "projection_label": "半弧坐标投影",
            "right_ascension": round(right_ascension, 4),
            "declination": round(declination, 4),
            "hour_angle_degrees": round(hour_angle, 4),
            "semiarc_degrees": round(semiarc, 4),
            "nocturnal_semiarc_degrees": round(180.0 - semiarc, 4),
            "quadrant": quadrant,
            "quadrant_label": PRIMARY_DIRECTION_QUADRANT_LABELS[quadrant],
            "mundane_position_degrees": round(mundane_position, 4),
        }

    result["diagnostics"] = diagnostics
    return result


def build_primary_direction_points(
    natal_subject: Any,
    *,
    arc_degrees: float,
) -> Dict[str, Dict[str, Any]]:
    natal_longitudes = extract_reference_longitudes(natal_subject)
    return {
        point_name: longitude_to_point_dict(
            point_name,
            natal_longitudes[point_name] + arc_degrees,
        )
        for point_name in PRIMARY_DIRECTION_PROMISSORS
    }


def build_shifted_reference_points(
    natal_subject: Any,
    *,
    arc_degrees: float,
) -> Dict[str, Dict[str, Any]]:
    natal_longitudes = extract_reference_longitudes(natal_subject)
    return {
        point_name: longitude_to_point_dict(
            point_name,
            natal_longitudes[point_name] + arc_degrees,
        )
        for point_name in TIMING_POINT_NAMES
    }


def build_shifted_lot_payloads(
    natal_subject: Any,
    *,
    arc_degrees: float,
) -> Dict[str, Dict[str, Any]]:
    natal_lots = build_lot_payloads(natal_subject)
    asc_sign = normalize_sign_name(natal_subject.ascendant.sign)
    return {
        lot_key: build_lot_point_dict(
            lot_key,
            float(payload.get("longitude", payload["absolute_degree"])) + arc_degrees,
            asc_sign=asc_sign,
        )
        for lot_key, payload in natal_lots.items()
    }


def build_sign_change_payloads(
    natal_points: Dict[str, Dict[str, Any]],
    directed_points: Dict[str, Dict[str, Any]],
    natal_lots: Dict[str, Dict[str, Any]],
    directed_lots: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    changes: List[Dict[str, Any]] = []

    for point_name in TIMING_POINT_NAMES:
        natal_payload = natal_points[point_name.lower()]
        directed_name = next(
            (
                candidate
                for candidate in directed_points
                if candidate.lower() == point_name.lower()
            ),
            point_name,
        )
        directed_payload = directed_points[directed_name]
        if natal_payload["sign"] != directed_payload["sign"]:
            changes.append(
                {
                    "point": directed_name,
                    "point_label": planet_label(directed_name),
                    "from_sign": natal_payload["sign"],
                    "from_sign_label": natal_payload["sign_label"],
                    "to_sign": directed_payload["sign"],
                    "to_sign_label": directed_payload["sign_label"],
                }
            )

    for lot_key, natal_payload in natal_lots.items():
        directed_payload = directed_lots[lot_key]
        if natal_payload["sign"] != directed_payload["sign"]:
            changes.append(
                {
                    "point": LOT_POINT_NAMES[lot_key],
                    "point_label": LOT_LABELS[lot_key],
                    "from_sign": natal_payload["sign"],
                    "from_sign_label": natal_payload["sign_label"],
                    "to_sign": directed_payload["sign"],
                    "to_sign_label": directed_payload["sign_label"],
                }
            )

    return changes


def build_bounds_entry_payload(
    item_key: str,
    payload: Dict[str, Any],
    *,
    item_label: Optional[str] = None,
) -> Dict[str, Any]:
    bound_payload = resolve_egyptian_bound(payload["sign"], payload["degree"])
    return {
        "key": item_key,
        "label": item_label or payload.get("point_label") or payload.get("lot_label"),
        "sign": payload["sign"],
        "sign_label": payload["sign_label"],
        "degree": payload["degree"],
        "absolute_degree": payload["absolute_degree"],
        **bound_payload,
    }


def build_primary_direction_bounds_overlay(
    directed_points: Dict[str, Dict[str, Any]],
    directed_lots: Dict[str, Dict[str, Any]],
    *,
    enabled: bool,
) -> Dict[str, Any]:
    if not enabled:
        return {
            "system": PRIMARY_DIRECTION_BOUNDS_SYSTEM,
            "system_label": PRIMARY_DIRECTION_BOUNDS_LABEL,
            "enabled": False,
            "points": {},
            "lots": {},
        }

    return {
        "system": PRIMARY_DIRECTION_BOUNDS_SYSTEM,
        "system_label": PRIMARY_DIRECTION_BOUNDS_LABEL,
        "enabled": True,
        "points": {
            point_name: build_bounds_entry_payload(point_name, payload)
            for point_name, payload in directed_points.items()
        },
        "lots": {
            lot_key: build_bounds_entry_payload(
                lot_key,
                payload,
                item_label=payload.get("lot_label"),
            )
            for lot_key, payload in directed_lots.items()
        },
    }


def build_primary_directions_payload(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    analysis_datetime: datetime,
    pd_method: str,
    pd_time_key: str,
    pd_type: int = 0,
    pd_aspects: Optional[List[int]] = None,
    max_age_years: float = PRIMARY_DIRECTION_MAX_AGE_YEARS,
    current_window_size: int = 12,
) -> Dict[str, Any]:
    age_years = calculate_age_years(birth_info, analysis_datetime)
    time_key_rate = primary_direction_time_key_rate(pd_time_key)
    coordinate_system, coordinate_label = primary_direction_coordinate_meta(pd_method)
    aspects = normalize_primary_direction_aspects(pd_aspects)
    coordinate_payload = extract_primary_direction_coordinate_payload(
        birth_info,
        natal_subject,
        pd_method=pd_method,
    )
    natal_coordinates = coordinate_payload["coordinates"]
    coordinate_rings = build_primary_direction_coordinate_rings(
        natal_coordinates,
        coordinate_system=coordinate_system,
        coordinate_label=coordinate_label,
    )
    targets = build_primary_direction_targets_with_coordinates(
        natal_subject,
        coordinate_map=natal_coordinates,
    )
    direction_mode = "converse" if pd_type == 1 else "direct"
    direction_mode_label = "逆推" if pd_type == 1 else "顺推"
    current_arc = age_years * time_key_rate * (-1 if pd_type == 1 else 1)
    timeline: List[Dict[str, Any]] = []
    seen_hits = set()

    for promissor in PRIMARY_DIRECTION_PROMISSORS:
        promissor_longitude = natal_coordinates[promissor]
        for target in targets:
            for aspect_degree in aspects:
                aspect_key, aspect_label_text = primary_direction_aspect_meta(
                    aspect_degree
                )
                for variant in primary_direction_aspect_variants(aspect_degree):
                    target_longitude = (target["longitude"] + variant) % 360.0
                    if pd_type == 1:
                        arc = (promissor_longitude - target_longitude) % 360.0
                    else:
                        arc = (target_longitude - promissor_longitude) % 360.0
                    event_age_years = arc / time_key_rate if time_key_rate else 0.0
                    if event_age_years <= 0.05 or event_age_years > max_age_years:
                        continue
                    dedupe_key = (
                        promissor,
                        target["name"],
                        aspect_key,
                        round(event_age_years, 6),
                    )
                    if dedupe_key in seen_hits:
                        continue
                    seen_hits.add(dedupe_key)
                    event_datetime = birth_info.local_datetime + timedelta(
                        days=event_age_years * TROPICAL_YEAR_DAYS
                    )
                    relative_years = round(event_age_years - age_years, 4)
                    timing_phase, timing_phase_label = primary_direction_timing_phase(
                        relative_years
                    )
                    arc_applied_degrees = round(
                        (-arc if pd_type == 1 else arc),
                        4,
                    )
                    timeline.append(
                        {
                            "arc_degrees": round(arc, 4),
                            "arc_applied_degrees": arc_applied_degrees,
                            "promissor": promissor,
                            "promissor_label": planet_label(promissor),
                            "significator": target["name"],
                            "significator_label": target["label"],
                            "aspect": aspect_key,
                            "aspect_label": aspect_label_text,
                            "aspect_degree": aspect_degree,
                            "aspect_variant_degrees": round(variant, 4),
                            "event_age_years": round(event_age_years, 4),
                            # Truncate to whole seconds: the directed arc is an
                            # approximation, so sub-second precision is noise that
                            # jitters at the microsecond level between ephemeris
                            # dependency micro-versions and would break the golden
                            # byte-lock without carrying any real signal.
                            "event_datetime": event_datetime.replace(
                                microsecond=0
                            ).isoformat(),
                            "direction_mode": direction_mode,
                            "direction_mode_label": direction_mode_label,
                            "coordinate_system": coordinate_system,
                            "coordinate_label": coordinate_label,
                            "relative_years_from_current": relative_years,
                            "relative_arc_from_current": round(
                                arc_applied_degrees - current_arc,
                                4,
                            ),
                            "timing_phase": timing_phase,
                            "timing_phase_label": timing_phase_label,
                            "distance_from_current_years": round(
                                abs(relative_years),
                                4,
                            ),
                        }
                    )

    timeline.sort(
        key=lambda item: (
            item["event_age_years"],
            item["arc_degrees"],
            item["promissor"],
            item["significator"],
        )
    )
    timeline = [
        enrich_primary_direction_hit_with_coordinate_context(
            item,
            natal_coordinates=natal_coordinates,
            coordinate_system=coordinate_system,
            coordinate_label=coordinate_label,
            natal_coordinate_points=coordinate_rings["points"],
            natal_coordinate_lots=coordinate_rings["lots"],
            arc_applied_degrees=primary_direction_arc_applied_degrees(item),
        )
        for item in timeline
    ]
    current_window = sorted(
        timeline,
        key=lambda item: (
            item["distance_from_current_years"],
            item["event_age_years"],
            item["arc_degrees"],
        ),
    )[:current_window_size]
    current_window = [
        enrich_primary_direction_hit_with_coordinate_context(
            item,
            natal_coordinates=natal_coordinates,
            coordinate_system=coordinate_system,
            coordinate_label=coordinate_label,
            natal_coordinate_points=coordinate_rings["points"],
            natal_coordinate_lots=coordinate_rings["lots"],
            arc_applied_degrees=current_arc,
        )
        for item in current_window
    ]
    phase_window_size = max(3, current_window_size // 2)
    past_window = [
        enrich_primary_direction_hit_with_coordinate_context(
            item,
            natal_coordinates=natal_coordinates,
            coordinate_system=coordinate_system,
            coordinate_label=coordinate_label,
            natal_coordinate_points=coordinate_rings["points"],
            natal_coordinate_lots=coordinate_rings["lots"],
            arc_applied_degrees=current_arc,
        )
        for item in sorted(
            (
                timeline_item
                for timeline_item in timeline
                if timeline_item["timing_phase"] == "past"
            ),
            key=lambda item: item["event_age_years"],
            reverse=True,
        )[:phase_window_size]
    ]
    future_window = [
        enrich_primary_direction_hit_with_coordinate_context(
            item,
            natal_coordinates=natal_coordinates,
            coordinate_system=coordinate_system,
            coordinate_label=coordinate_label,
            natal_coordinate_points=coordinate_rings["points"],
            natal_coordinate_lots=coordinate_rings["lots"],
            arc_applied_degrees=current_arc,
        )
        for item in sorted(
            (
                timeline_item
                for timeline_item in timeline
                if timeline_item["timing_phase"] in {"future", "exact"}
            ),
            key=lambda item: item["event_age_years"],
        )[:phase_window_size]
    ]
    exact_window = [
        enrich_primary_direction_hit_with_coordinate_context(
            item,
            natal_coordinates=natal_coordinates,
            coordinate_system=coordinate_system,
            coordinate_label=coordinate_label,
            natal_coordinate_points=coordinate_rings["points"],
            natal_coordinate_lots=coordinate_rings["lots"],
            arc_applied_degrees=current_arc,
        )
        for item in sorted(
            (
                timeline_item
                for timeline_item in timeline
                if timeline_item["timing_phase"] == "exact"
            ),
            key=lambda item: (
                item["distance_from_current_years"],
                item["event_age_years"],
                item["arc_degrees"],
            ),
        )[:current_window_size]
    ]
    current_coordinate_rings = build_primary_direction_coordinate_rings(
        natal_coordinates,
        coordinate_system=coordinate_system,
        coordinate_label=coordinate_label,
        arc_applied_degrees=current_arc,
    )

    return {
        "method": pd_method,
        "method_label": primary_direction_method_label(pd_method),
        "time_key": pd_time_key,
        "time_key_label": pd_time_key,
        "pd_type": pd_type,
        "direction_mode": direction_mode,
        "direction_mode_label": direction_mode_label,
        "coordinate_system": coordinate_system,
        "coordinate_label": coordinate_label,
        "approximation": coordinate_payload["approximation"],
        "approximation_label": coordinate_payload["approximation_label"],
        "coordinate_precision": coordinate_payload["coordinate_precision"],
        "coordinate_backend": coordinate_payload["coordinate_backend"],
        "coordinate_diagnostics": coordinate_payload["diagnostics"],
        "coordinate_points": coordinate_rings["points"],
        "coordinate_lots": coordinate_rings["lots"],
        "current_coordinate_points": current_coordinate_rings["points"],
        "current_coordinate_lots": current_coordinate_rings["lots"],
        "promissors": PRIMARY_DIRECTION_PROMISSORS,
        "aspects": aspects,
        "current_age_years": round(age_years, 4),
        "current_arc_degrees": round(current_arc, 4),
        "current_arc_absolute_degrees": round(abs(current_arc), 4),
        "current_window": current_window,
        "past_window": past_window,
        "future_window": future_window,
        "exact_window": exact_window,
        "timeline": timeline,
    }


def build_primary_direction_chart_payload(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    analysis_datetime: datetime,
    pd_method: str,
    pd_time_key: str,
    pd_type: int,
    coordinate_system: str,
    coordinate_label: str,
    approximation: str,
    approximation_label: str,
    coordinate_precision: str,
    coordinate_backend: str,
    coordinate_diagnostics: Dict[str, Dict[str, Any]],
    coordinate_points: Dict[str, Dict[str, Any]],
    coordinate_lots: Dict[str, Dict[str, Any]],
    current_coordinate_points: Dict[str, Dict[str, Any]],
    current_coordinate_lots: Dict[str, Dict[str, Any]],
    current_arc_degrees: float,
    current_hits: List[Dict[str, Any]],
    show_pd_bounds: bool,
) -> Dict[str, Any]:
    natal_points = extract_reference_points(natal_subject)
    natal_lots = build_lot_payloads(natal_subject)
    if coordinate_system == "right_ascension" and swe is not None:
        directed_points, directed_lots, directed_axes = (
            build_reprojected_primary_direction_chart_layers(
                birth_info,
                natal_subject,
                arc_degrees=current_arc_degrees,
            )
        )
    elif coordinate_system == "mundane_semiarc" and swe is not None:
        directed_points, directed_lots, directed_axes = (
            build_reprojected_mundane_primary_direction_chart_layers(
                birth_info,
                natal_subject,
                arc_degrees=current_arc_degrees,
            )
        )
    else:
        directed_points = build_shifted_reference_points(
            natal_subject,
            arc_degrees=current_arc_degrees,
        )
        directed_lots = build_shifted_lot_payloads(
            natal_subject,
            arc_degrees=current_arc_degrees,
        )
        directed_axes = build_primary_direction_points(
            natal_subject,
            arc_degrees=current_arc_degrees,
        )
    bounds_overlay = build_primary_direction_bounds_overlay(
        directed_points,
        directed_lots,
        enabled=show_pd_bounds,
    )
    return {
        "analysis_datetime": analysis_datetime.isoformat(),
        "method": pd_method,
        "method_label": primary_direction_method_label(pd_method),
        "time_key": pd_time_key,
        "time_key_label": pd_time_key,
        "pd_type": pd_type,
        "direction_mode": "converse" if pd_type == 1 else "direct",
        "direction_mode_label": "逆推" if pd_type == 1 else "顺推",
        "coordinate_system": coordinate_system,
        "coordinate_label": coordinate_label,
        "current_arc_degrees": round(current_arc_degrees, 4),
        "current_arc_absolute_degrees": round(abs(current_arc_degrees), 4),
        "show_pd_bounds": show_pd_bounds,
        "approximation": approximation,
        "approximation_label": approximation_label,
        "coordinate_precision": coordinate_precision,
        "coordinate_backend": coordinate_backend,
        "coordinate_diagnostics": coordinate_diagnostics,
        "natal_coordinate_points": coordinate_points,
        "natal_coordinate_lots": coordinate_lots,
        "directed_coordinate_points": current_coordinate_points,
        "directed_coordinate_lots": current_coordinate_lots,
        "coordinate_hits": current_hits[:8],
        "exact_hits": [
            item for item in current_hits[:8] if item.get("timing_phase") == "exact"
        ],
        "bounds_overlay": bounds_overlay,
        "directed_points": directed_points,
        "directed_lots": directed_lots,
        "sign_changes": build_sign_change_payloads(
            natal_points,
            directed_points,
            natal_lots,
            directed_lots,
        ),
        "directed_ascendant": directed_axes["Ascendant"],
        "directed_medium_coeli": directed_axes["Medium_Coeli"],
        "hits": current_hits[:8],
    }
