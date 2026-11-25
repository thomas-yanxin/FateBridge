"""原始向运法（Primary Directions）推运法。"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from fractions import Fraction
from typing import Any, SupportsAbs

from fatebridge.core.astro.angle_definitions import is_ascendant_resolved
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.earth_attitude import earth_attitude
from fatebridge.core.astro.geometry import (
    Angle,
    angle_fraction,
    angular_separation_fraction,
    combine_longitudes_exact,
    longitude_float,
    normalize_angle,
)
from fatebridge.core.astro.reference import TRADITIONAL_PLANETS
from fatebridge.core.astro.reference_frames import rotate_spherical
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.core.ephemeris_runtime import ephemeris_call, swe
from fatebridge.core.predictive._common import (
    ASPECT_DEGREE_TO_META,
    LOT_KEY_BY_POINT_NAME,
    LOT_LABELS,
    LOT_POINT_NAMES,
    SWISSEPH_PLANET_IDS,
    TIMING_POINT_NAMES,
    TROPICAL_YEAR_DAYS,
    build_lot_longitudes,
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
from fatebridge.utils.civil_time import ZonedCalendar, utc_calendar
from fatebridge.utils.timezones import format_local_time_or_utc

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


def primary_direction_coordinate_meta(
    pd_method: str,
) -> tuple[str, str]:
    if pd_method not in PRIMARY_DIRECTION_METHOD_COORDINATES:
        raise ValueError(
            "未知主限方法，请使用 astroapp_alchabitius、equatorial 或 fatebridge_mundane_semiarc"
        )
    else:
        pass
    if (
        pd_method
        in {
            "equatorial",
            "fatebridge_mundane_semiarc",
        }
        and swe is None
    ):
        return PRIMARY_DIRECTION_METHOD_COORDINATES["astroapp_alchabitius"]
    else:
        pass
    return PRIMARY_DIRECTION_METHOD_COORDINATES[pd_method]


def primary_direction_approximation_meta(pd_method: str) -> tuple[str, str]:
    if pd_method == "fatebridge_mundane_semiarc":
        return "mundane_semiarc_static_key", "半弧 mundane static key 近似"
    else:
        pass
    return "axis_static_key", "轴点 static key 近似"


def primary_direction_coordinate_runtime_meta(pd_method: str) -> tuple[str, str]:
    if pd_method == "equatorial":
        if swe is not None:
            return "equatorial_runtime_projection", "swisseph_equatorial_projection"
        else:
            pass
        return (
            "ecliptic_runtime_reference_fallback",
            "native_ecliptic_reference_fallback",
        )
    else:
        pass
    if pd_method == "fatebridge_mundane_semiarc":
        if swe is not None:
            return "mundane_runtime_projection", "swisseph_mundane_semiarc_projection"
        else:
            pass
        return (
            "ecliptic_runtime_reference_fallback",
            "native_ecliptic_reference_fallback",
        )
    else:
        pass
    return "ephemeris_runtime_model", "fatebridge_native_subject_abs_pos"


@dataclass(frozen=True)
class PrimaryDirectionEquatorialContext:
    ut1: UT1Instant
    tt: TTInstant
    obliquity: float
    longitude_origin: float
    armc: float

    @property
    def julian_day(self) -> float:
        """Scalar interoperability/display projection of the retained UT1."""
        return self.ut1.as_float()


def build_primary_direction_equatorial_context(
    birth_info: AstroBirthInfo,
) -> PrimaryDirectionEquatorialContext:
    times = birth_info.time_scales
    if times.tt is None:
        raise ModuleNotFoundError(
            "Swiss Ephemeris is required for equatorial directions"
        )
    else:
        pass
    attitude = earth_attitude(swe, times.ut1, julian_day_tt=times.tt)
    armc = (attitude.house_sidereal_degrees + birth_info.longitude) % 360
    return PrimaryDirectionEquatorialContext(
        times.ut1,
        times.tt,
        attitude.reduction.house_obliquity,
        attitude.reduction.house_longitude_origin,
        float(armc),
    )


def project_absolute_degree_to_equatorial(
    absolute_degree: float,
    *,
    obliquity: float,
    longitude_origin: float = 0.0,
) -> tuple[float, float]:
    right_ascension, declination, _ = swe.cotrans(
        (normalize_angle(absolute_degree - longitude_origin), 0.0, 1.0),
        -obliquity,
    )
    return float(right_ascension), float(declination)


def point_equatorial_position(
    point_name: str,
    natal_subject: Any,
    *,
    context: PrimaryDirectionEquatorialContext,
) -> tuple[float, float]:
    if point_name in SWISSEPH_PLANET_IDS:
        equatorial, retflag = ephemeris_call(
            "calc",
            context.tt.as_float(),
            SWISSEPH_PLANET_IDS[point_name],
            swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_EQUATORIAL,
        )
        if retflag < 0:
            raise ValueError("Primary direction equatorial ephemeris failed")
        else:
            pass
        attitude = earth_attitude(swe, context.ut1, julian_day_tt=context.tt)
        return rotate_spherical(
            attitude.reduction.native_to_house,
            float(equatorial[0]),
            float(equatorial[1]),
        )
    else:
        pass
    # MC is on the ecliptic, not on the equator: its RA is ARMC but its
    # declination is generally nonzero. Preserve the physical chart point.
    offset = getattr(natal_subject, "calculation_basis", {}).get(
        "ayanamsha_degrees", 0.0
    )
    return project_absolute_degree_to_equatorial(
        point_absolute_position(natal_subject, point_name) + offset,
        obliquity=context.obliquity,
        longitude_origin=context.longitude_origin,
    )


def project_equatorial_to_ecliptic(
    right_ascension: float,
    declination: float,
    *,
    obliquity: float,
    zodiac_offset: float = 0.0,
    longitude_origin: float = 0.0,
) -> tuple[float, float]:
    longitude, latitude, _ = swe.cotrans(
        (normalize_angle(right_ascension), declination, 1.0),
        obliquity,
    )
    return normalize_angle(float(longitude) + longitude_origin - zodiac_offset), float(
        latitude
    )


def build_reprojected_primary_direction_chart_layers(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    arc_degrees: float,
) -> tuple[
    dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]
]:
    equatorial_context = build_primary_direction_equatorial_context(birth_info)
    obliquity = equatorial_context.obliquity
    natal_lots = build_lot_payloads(natal_subject)
    asc_sign = normalize_sign_name(natal_subject.ascendant.sign)

    directed_points: dict[str, dict[str, Any]] = {}
    for point_name in extract_reference_longitudes(natal_subject):
        right_ascension, declination = point_equatorial_position(
            point_name,
            natal_subject,
            context=equatorial_context,
        )
        longitude, _latitude = project_equatorial_to_ecliptic(
            right_ascension + arc_degrees,
            declination,
            obliquity=obliquity,
            longitude_origin=equatorial_context.longitude_origin,
            zodiac_offset=natal_subject.calculation_basis["ayanamsha_degrees"],
        )
        directed_points[point_name] = longitude_to_point_dict(point_name, longitude)

    directed_lots: dict[str, dict[str, Any]] = {}
    for lot_key, payload in natal_lots.items():
        right_ascension, declination = project_absolute_degree_to_equatorial(
            float(payload.get("longitude", payload["absolute_degree"]))
            + natal_subject.calculation_basis["ayanamsha_degrees"],
            obliquity=obliquity,
            longitude_origin=equatorial_context.longitude_origin,
        )
        longitude, _latitude = project_equatorial_to_ecliptic(
            right_ascension + arc_degrees,
            declination,
            obliquity=obliquity,
            longitude_origin=equatorial_context.longitude_origin,
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
        if point_name in directed_points
    }
    return directed_points, directed_lots, directed_axes


def semiarc_degrees_for_declination(latitude: float, declination: float) -> float:
    latitude_radians = math.radians(latitude)
    declination_radians = math.radians(declination)
    horizon_term = -math.tan(latitude_radians) * math.tan(declination_radians)
    if horizon_term <= -1.0:
        return 180.0
    else:
        pass
    if horizon_term >= 1.0:
        return 0.0
    else:
        pass
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
    else:
        pass
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
    else:
        pass
    clamped_semiarc = semiarc_degrees
    nocturnal_semiarc = 180.0 - clamped_semiarc

    if normalized_coordinate <= 90.0:
        return ((normalized_coordinate / 90.0) * clamped_semiarc) - clamped_semiarc
    else:
        pass
    if normalized_coordinate <= 180.0:
        return ((normalized_coordinate - 90.0) / 90.0) * clamped_semiarc
    else:
        pass
    if normalized_coordinate <= 270.0:
        return clamped_semiarc + (
            ((normalized_coordinate - 180.0) / 90.0) * nocturnal_semiarc
        )
    else:
        pass
    return -180.0 + (((normalized_coordinate - 270.0) / 90.0) * nocturnal_semiarc)


def build_reprojected_mundane_primary_direction_chart_layers(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    arc_degrees: float,
) -> tuple[
    dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]
]:
    equatorial_context = build_primary_direction_equatorial_context(birth_info)
    obliquity = equatorial_context.obliquity
    armc = equatorial_context.armc
    natal_lots = build_lot_payloads(natal_subject)
    asc_sign = normalize_sign_name(natal_subject.ascendant.sign)

    directed_points: dict[str, dict[str, Any]] = {}
    for point_name in TRADITIONAL_PLANETS:
        right_ascension, declination = point_equatorial_position(
            point_name,
            natal_subject,
            context=equatorial_context,
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
            longitude_origin=equatorial_context.longitude_origin,
            zodiac_offset=natal_subject.calculation_basis["ayanamsha_degrees"],
        )
        directed_points[point_name] = longitude_to_point_dict(point_name, longitude)

    for point_name, base_coordinate in (("Ascendant", 0.0), ("Medium_Coeli", 90.0)):
        if point_name == "Ascendant" and not is_ascendant_resolved(natal_subject):
            continue
        _, declination = point_equatorial_position(
            point_name,
            natal_subject,
            context=equatorial_context,
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
            longitude_origin=equatorial_context.longitude_origin,
            zodiac_offset=natal_subject.calculation_basis["ayanamsha_degrees"],
        )
        directed_points[point_name] = longitude_to_point_dict(point_name, longitude)

    directed_lots: dict[str, dict[str, Any]] = {}
    for lot_key, payload in natal_lots.items():
        right_ascension, declination = project_absolute_degree_to_equatorial(
            float(payload.get("longitude", payload["absolute_degree"]))
            + natal_subject.calculation_basis["ayanamsha_degrees"],
            obliquity=obliquity,
            longitude_origin=equatorial_context.longitude_origin,
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
            longitude_origin=equatorial_context.longitude_origin,
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
        if point_name in directed_points
    }
    return directed_points, directed_lots, directed_axes


def quadrant_for_mundane_coordinate(coordinate_degrees: float) -> str:
    normalized = normalize_angle(coordinate_degrees)
    if math.isclose(normalized, 0.0, abs_tol=1e-6) or math.isclose(
        normalized, 360.0, abs_tol=1e-6
    ):
        return "horizon_east"
    else:
        pass
    if math.isclose(normalized, 90.0, abs_tol=1e-6):
        return "upper_meridian"
    else:
        pass
    if math.isclose(normalized, 180.0, abs_tol=1e-6):
        return "horizon_west"
    else:
        pass
    if math.isclose(normalized, 270.0, abs_tol=1e-6):
        return "lower_meridian"
    else:
        pass
    if normalized < 90.0:
        return "above_east"
    else:
        pass
    if normalized < 180.0:
        return "above_west"
    else:
        pass
    if normalized < 270.0:
        return "below_west"
    else:
        pass
    return "below_east"


def build_primary_direction_coordinate_entry(
    *,
    item_key: str,
    item_label: str,
    coordinate_degrees: Angle,
    coordinate_system: str,
    coordinate_label: str,
    arc_applied_degrees: Angle = 0.0,
) -> dict[str, Any]:
    normalized_coordinate = (
        longitude_float(coordinate_degrees)
        if isinstance(coordinate_degrees, Fraction)
        else normalize_angle(coordinate_degrees)
    )
    entry = {
        "key": item_key,
        "label": item_label,
        "coordinate_system": coordinate_system,
        "coordinate_label": coordinate_label,
        "coordinate_degrees": normalized_coordinate,
        "arc_applied_degrees": float(arc_applied_degrees),
    }
    if coordinate_system == "mundane_semiarc":
        quadrant = quadrant_for_mundane_coordinate(normalized_coordinate)
        entry.update(
            {
                "quadrant": quadrant,
                "quadrant_label": PRIMARY_DIRECTION_QUADRANT_LABELS[quadrant],
                "phase_within_quadrant_degrees": normalized_coordinate % 90.0,
            }
        )
    else:
        pass
    return entry


def _shift_primary_direction_coordinate(coordinate: Angle, arc: Angle) -> Angle:
    if isinstance(coordinate, Fraction):
        return combine_longitudes_exact(coordinate, arc)
    else:
        pass
    return coordinate + float(arc)


def build_primary_direction_coordinate_rings(
    coordinate_map: Mapping[str, Angle],
    *,
    coordinate_system: str,
    coordinate_label: str,
    arc_applied_degrees: Angle = 0.0,
) -> dict[str, dict[str, dict[str, Any]]]:
    def entry(name: str, label: str) -> dict[str, Any]:
        return build_primary_direction_coordinate_entry(
            item_key=name,
            item_label=label,
            coordinate_degrees=_shift_primary_direction_coordinate(
                coordinate_map[name], arc_applied_degrees
            ),
            coordinate_system=coordinate_system,
            coordinate_label=coordinate_label,
            arc_applied_degrees=arc_applied_degrees,
        )

    return {
        "points": {
            name: entry(name, planet_label(name))
            for name in TIMING_POINT_NAMES
            if name in coordinate_map
        },
        "lots": {
            lot_key: entry(LOT_POINT_NAMES[lot_key], LOT_LABELS[lot_key])
            for lot_key in LOT_POINT_NAMES
            if LOT_POINT_NAMES[lot_key] in coordinate_map
        },
    }


def resolve_primary_direction_coordinate_entry(
    point_name: str,
    *,
    coordinate_points: dict[str, dict[str, Any]],
    coordinate_lots: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if point_name in coordinate_points:
        return coordinate_points[point_name]
    else:
        pass
    lot_key = LOT_KEY_BY_POINT_NAME.get(point_name)
    if lot_key:
        return coordinate_lots.get(lot_key)
    else:
        pass
    return None


def build_primary_direction_hit_coordinate_context(
    hit: dict[str, Any],
    *,
    natal_coordinates: Mapping[str, Angle],
    coordinate_system: str,
    coordinate_label: str,
    natal_coordinate_points: dict[str, dict[str, Any]],
    natal_coordinate_lots: dict[str, dict[str, Any]],
    arc_applied_degrees: Angle,
) -> dict[str, Any]:
    promissor_natal = resolve_primary_direction_coordinate_entry(
        hit["promissor"],
        coordinate_points=natal_coordinate_points,
        coordinate_lots=natal_coordinate_lots,
    )
    significator_natal = resolve_primary_direction_coordinate_entry(
        hit["significator"],
        coordinate_points=natal_coordinate_points,
        coordinate_lots=natal_coordinate_lots,
    )
    assert promissor_natal is not None
    assert significator_natal is not None
    shifted_promissor = _shift_primary_direction_coordinate(
        natal_coordinates[hit["promissor"]], arc_applied_degrees
    )
    promissor_current = build_primary_direction_coordinate_entry(
        item_key=hit["promissor"],
        item_label=promissor_natal["label"],
        coordinate_degrees=shifted_promissor,
        coordinate_system=coordinate_system,
        coordinate_label=coordinate_label,
        arc_applied_degrees=arc_applied_degrees,
    )
    aspect_target_degrees: Angle
    if isinstance(shifted_promissor, Fraction):
        aspect_target_degrees = combine_longitudes_exact(
            natal_coordinates[hit["significator"]], hit["aspect_variant_degrees"]
        )
        current_orb = float(
            angular_separation_fraction(shifted_promissor, aspect_target_degrees)
        )
    else:
        aspect_target_degrees = normalize_angle(
            significator_natal["coordinate_degrees"] + hit["aspect_variant_degrees"]
        )
        difference = promissor_current["coordinate_degrees"] - aspect_target_degrees
        current_orb = min(normalize_angle(difference), normalize_angle(-difference))
    aspect_target = build_primary_direction_coordinate_entry(
        item_key=f"{hit['significator']}_{hit['aspect']}",
        item_label=f"{hit['significator_label']} {hit['aspect_label']}",
        coordinate_degrees=aspect_target_degrees,
        coordinate_system=coordinate_system,
        coordinate_label=coordinate_label,
    )
    return {
        "promissor_natal": promissor_natal,
        "promissor_current": promissor_current,
        "significator_natal": significator_natal,
        "aspect_target": aspect_target,
        "current_orb_degrees": current_orb,
    }


def _relative_years_distance(relative_years: SupportsAbs[Angle]) -> Angle:
    return abs(relative_years)


def primary_direction_timing_phase(relative_years: Angle) -> tuple[str, str]:
    if _relative_years_distance(relative_years) <= PRIMARY_DIRECTION_EXACT_WINDOW_YEARS:
        phase = "exact"
    elif relative_years < 0:
        phase = "past"
    else:
        phase = "future"
    return phase, PRIMARY_DIRECTION_TIMING_PHASE_LABELS[phase]


def enrich_primary_direction_hit_with_coordinate_context(
    hit: dict[str, Any],
    *,
    natal_coordinates: Mapping[str, Angle],
    coordinate_system: str,
    coordinate_label: str,
    natal_coordinate_points: dict[str, dict[str, Any]],
    natal_coordinate_lots: dict[str, dict[str, Any]],
    arc_applied_degrees: Angle,
) -> dict[str, Any]:
    return {
        **hit,
        "coordinate_context": build_primary_direction_hit_coordinate_context(
            hit,
            natal_coordinates=natal_coordinates,
            coordinate_system=coordinate_system,
            coordinate_label=coordinate_label,
            natal_coordinate_points=natal_coordinate_points,
            natal_coordinate_lots=natal_coordinate_lots,
            arc_applied_degrees=arc_applied_degrees,
        ),
    }


def normalize_primary_direction_aspects(
    pd_aspects: list[int] | None,
) -> list[int]:
    if not pd_aspects:
        return PRIMARY_DIRECTION_DEFAULT_ASPECTS.copy()
    else:
        pass
    normalized: list[int] = []
    for value in pd_aspects:
        try:
            degree = int(float(value)) % 360
        except (TypeError, ValueError):
            continue
        if degree not in normalized:
            normalized.append(degree)
        else:
            pass
    return normalized or PRIMARY_DIRECTION_DEFAULT_ASPECTS.copy()


def primary_direction_aspect_variants(aspect_degree: int) -> list[float]:
    if aspect_degree in {0, 180}:
        return [float(aspect_degree)]
    else:
        pass
    return [float(aspect_degree), float((360 - aspect_degree) % 360)]


def primary_direction_aspect_meta(aspect_degree: int) -> tuple[str, str]:
    meta = ASPECT_DEGREE_TO_META.get(aspect_degree)
    if meta is not None:
        return meta
    else:
        pass
    return f"{aspect_degree}deg", f"{aspect_degree}°"


def build_primary_direction_targets_with_coordinates(
    coordinate_map: Mapping[str, Angle],
) -> list[dict[str, Any]]:
    targets = [
        {
            "name": point_name,
            "label": planet_label(point_name),
            "longitude": coordinate_map[point_name],
        }
        for point_name in TIMING_POINT_NAMES
        if point_name in coordinate_map
    ]
    for lot_key, point_name in LOT_POINT_NAMES.items():
        if point_name not in coordinate_map:
            continue
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
) -> dict[str, Any]:
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
    else:
        pass

    if pd_method not in {
        "equatorial",
        "fatebridge_mundane_semiarc",
    }:
        return result
    else:
        pass

    equatorial_context = build_primary_direction_equatorial_context(birth_info)
    obliquity = equatorial_context.obliquity
    armc = equatorial_context.armc

    if pd_method == "equatorial":
        diagnostics: dict[str, dict[str, Any]] = {}
        for point_name in TIMING_POINT_NAMES:
            if point_name not in coordinate_map:
                continue
            right_ascension, declination = point_equatorial_position(
                point_name,
                natal_subject,
                context=equatorial_context,
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
                longitude_origin=equatorial_context.longitude_origin,
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
    else:
        pass

    if "Ascendant" in coordinate_map:
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

    if "Ascendant" not in coordinate_map:
        del diagnostics["Ascendant"]

    for point_name in diagnostics:
        right_ascension, declination = point_equatorial_position(
            point_name,
            natal_subject,
            context=equatorial_context,
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
            context=equatorial_context,
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
            longitude_origin=equatorial_context.longitude_origin,
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
    arc_degrees: Angle,
) -> dict[str, dict[str, Any]]:
    natal_longitudes = extract_reference_longitudes(natal_subject)
    return {
        point_name: longitude_to_point_dict(
            point_name,
            combine_longitudes_exact(natal_longitudes[point_name], arc_degrees),
        )
        for point_name in PRIMARY_DIRECTION_PROMISSORS
        if point_name in natal_longitudes
    }


def build_shifted_reference_points(
    natal_subject: Any,
    *,
    arc_degrees: Angle,
) -> dict[str, dict[str, Any]]:
    return {
        name: longitude_to_point_dict(
            name, combine_longitudes_exact(longitude, arc_degrees)
        )
        for name, longitude in extract_reference_longitudes(natal_subject).items()
    }


def build_shifted_lot_payloads(
    natal_subject: Any,
    *,
    arc_degrees: Angle,
) -> dict[str, dict[str, Any]]:
    asc_sign = normalize_sign_name(natal_subject.ascendant.sign)
    return {
        lot_key: build_lot_point_dict(
            lot_key, combine_longitudes_exact(longitude, arc_degrees), asc_sign=asc_sign
        )
        for lot_key, longitude in build_lot_longitudes(natal_subject).items()
    }


def build_sign_change_payloads(
    natal_points: dict[str, dict[str, Any]],
    directed_points: dict[str, dict[str, Any]],
    natal_lots: dict[str, dict[str, Any]],
    directed_lots: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []

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
        directed_payload = directed_points.get(directed_name)
        if directed_payload is None:
            continue
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
        else:
            pass

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
        else:
            pass

    return changes


def build_bounds_entry_payload(
    item_key: str,
    payload: dict[str, Any],
    *,
    item_label: str | None = None,
) -> dict[str, Any]:
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
    directed_points: dict[str, dict[str, Any]],
    directed_lots: dict[str, dict[str, Any]],
    *,
    enabled: bool,
) -> dict[str, Any]:
    if not enabled:
        return {
            "system": PRIMARY_DIRECTION_BOUNDS_SYSTEM,
            "system_label": PRIMARY_DIRECTION_BOUNDS_LABEL,
            "enabled": False,
            "points": {},
            "lots": {},
        }
    else:
        pass

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


@dataclass(frozen=True)
class _PrimaryDirectionEvent:
    chronological_key: tuple[Angle, Angle, str, str]
    relative_years: Angle
    payload: dict[str, object]

    @property
    def proximity_key(self) -> tuple[Angle, Angle, Angle]:
        age_years, arc, _, _ = self.chronological_key
        return _relative_years_distance(self.relative_years), age_years, arc


@dataclass(frozen=True)
class PrimaryDirectionAnalysis:
    payload: dict[str, Any]
    current_arc: Angle


def build_primary_directions_payload(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    analysis_datetime: datetime,
    pd_method: str,
    pd_time_key: str,
    pd_type: int = 0,
    pd_aspects: list[int] | None = None,
    max_age_years: float = PRIMARY_DIRECTION_MAX_AGE_YEARS,
    current_window_size: int = 12,
) -> dict[str, Any]:
    return build_primary_direction_analysis(
        birth_info,
        natal_subject,
        analysis_datetime=analysis_datetime,
        pd_method=pd_method,
        pd_time_key=pd_time_key,
        pd_type=pd_type,
        pd_aspects=pd_aspects,
        max_age_years=max_age_years,
        current_window_size=current_window_size,
    ).payload


def build_primary_direction_analysis(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    analysis_datetime: datetime,
    pd_method: str,
    pd_time_key: str,
    pd_type: int = 0,
    pd_aspects: list[int] | None = None,
    max_age_years: float = PRIMARY_DIRECTION_MAX_AGE_YEARS,
    current_window_size: int = 12,
) -> PrimaryDirectionAnalysis:
    birth_utc = birth_info.utc_calendar
    birth_zone = birth_info.local_datetime.tzinfo
    assert birth_zone is not None
    time_key_rate = PRIMARY_DIRECTION_TIME_KEY_RATES[pd_time_key]
    coordinate_system, coordinate_label = primary_direction_coordinate_meta(pd_method)
    aspects = normalize_primary_direction_aspects(pd_aspects)
    coordinate_payload = extract_primary_direction_coordinate_payload(
        birth_info,
        natal_subject,
        pd_method=pd_method,
    )
    natal_coordinates = coordinate_payload["coordinates"]
    is_ecliptic = coordinate_system == "ecliptic_longitude"
    working_coordinates: Mapping[str, Angle] = natal_coordinates
    working_time_key_rate: Angle = time_key_rate
    working_current_age: Angle
    if is_ecliptic:
        working_coordinates = {
            name: angle_fraction(value) for name, value in natal_coordinates.items()
        } | {
            LOT_POINT_NAMES[key]: longitude
            for key, longitude in build_lot_longitudes(natal_subject).items()
        }
        working_time_key_rate = Fraction(time_key_rate)
        # Compare the event age with the exact UTC duration on the same fixed year axis.
        elapsed = utc_calendar(analysis_datetime).elapsed_since(birth_utc)
        working_current_age = Fraction(
            elapsed // timedelta.resolution,
            timedelta(days=TROPICAL_YEAR_DAYS) // timedelta.resolution,
        )
    else:
        working_current_age = calculate_age_years(birth_info, analysis_datetime)
    coordinate_rings = build_primary_direction_coordinate_rings(
        working_coordinates,
        coordinate_system=coordinate_system,
        coordinate_label=coordinate_label,
    )
    targets = build_primary_direction_targets_with_coordinates(working_coordinates)
    direction_mode = "converse" if pd_type == 1 else "direct"
    direction_mode_label = "逆推" if pd_type == 1 else "顺推"
    direction = -1 if pd_type == 1 else 1
    unsigned_current_arc = working_current_age * working_time_key_rate
    # A converse calculation at birth delivers the existing negative zero arc.
    current_arc = (unsigned_current_arc or 0.0) * direction
    events: list[_PrimaryDirectionEvent] = []
    seen_hits = set()

    promissors = [
        name for name in PRIMARY_DIRECTION_PROMISSORS if name in working_coordinates
    ]
    for promissor in promissors:
        promissor_longitude = working_coordinates[promissor]
        for target in targets:
            for aspect_degree in aspects:
                aspect_key, aspect_label_text = primary_direction_aspect_meta(
                    aspect_degree
                )
                for variant in primary_direction_aspect_variants(aspect_degree):
                    working_arc: Angle
                    if is_ecliptic:
                        # Test the window before rounding the circular arc or age.
                        if pd_type == 1:
                            working_arc = combine_longitudes_exact(
                                promissor_longitude, -target["longitude"], -variant
                            )
                        else:
                            working_arc = combine_longitudes_exact(
                                target["longitude"], variant, -promissor_longitude
                            )
                    else:
                        target_longitude = (target["longitude"] + variant) % 360.0
                        working_arc = (
                            (promissor_longitude - target_longitude) % 360.0
                            if pd_type == 1
                            else (target_longitude - promissor_longitude) % 360.0
                        )
                    working_age_years = working_arc / working_time_key_rate
                    if working_age_years <= 0.05 or working_age_years > max_age_years:
                        continue
                    else:
                        pass
                    arc = float(working_arc)
                    event_age_years = float(working_age_years)
                    dedupe_key = (
                        promissor,
                        target["name"],
                        aspect_key,
                        round(event_age_years, 6),
                    )
                    if dedupe_key in seen_hits:
                        continue
                    else:
                        pass
                    seen_hits.add(dedupe_key)
                    # Event labels and ages share the same nominal UTC-duration axis.
                    event_datetime = ZonedCalendar(
                        birth_utc.shifted(
                            timedelta(days=event_age_years * TROPICAL_YEAR_DAYS)
                        ),
                        birth_zone,
                    ).require_datetime()
                    relative_years = working_age_years - working_current_age
                    timing_phase, timing_phase_label = primary_direction_timing_phase(
                        relative_years
                    )
                    arc_applied_degrees = -arc if pd_type == 1 else arc
                    relative_arc = (
                        relative_years * working_time_key_rate * direction
                        if is_ecliptic
                        else arc_applied_degrees - current_arc
                    )
                    payload = {
                        "arc_degrees": arc,
                        "arc_applied_degrees": arc_applied_degrees,
                        "promissor": promissor,
                        "promissor_label": planet_label(promissor),
                        "significator": target["name"],
                        "significator_label": target["label"],
                        "aspect": aspect_key,
                        "aspect_label": aspect_label_text,
                        "aspect_degree": aspect_degree,
                        "aspect_variant_degrees": variant,
                        "event_age_years": event_age_years,
                        # The event label is a presentation on the fixed duration axis.
                        "event_datetime": format_local_time_or_utc(
                            event_datetime, timespec="seconds"
                        ),
                        "direction_mode": direction_mode,
                        "direction_mode_label": direction_mode_label,
                        "coordinate_system": coordinate_system,
                        "coordinate_label": coordinate_label,
                        "relative_years_from_current": float(relative_years),
                        "relative_arc_from_current": float(relative_arc),
                        "timing_phase": timing_phase,
                        "timing_phase_label": timing_phase_label,
                        "distance_from_current_years": float(
                            _relative_years_distance(relative_years)
                        ),
                    }
                    events.append(
                        _PrimaryDirectionEvent(
                            (working_age_years, working_arc, promissor, target["name"]),
                            relative_years,
                            payload,
                        )
                    )

    events.sort(key=lambda event: event.chronological_key)
    timeline = [
        enrich_primary_direction_hit_with_coordinate_context(
            event.payload,
            natal_coordinates=working_coordinates,
            coordinate_system=coordinate_system,
            coordinate_label=coordinate_label,
            natal_coordinate_points=coordinate_rings["points"],
            natal_coordinate_lots=coordinate_rings["lots"],
            arc_applied_degrees=event.chronological_key[1] * direction,
        )
        for event in events
    ]
    current_window = [
        enrich_primary_direction_hit_with_coordinate_context(
            event.payload,
            natal_coordinates=working_coordinates,
            coordinate_system=coordinate_system,
            coordinate_label=coordinate_label,
            natal_coordinate_points=coordinate_rings["points"],
            natal_coordinate_lots=coordinate_rings["lots"],
            arc_applied_degrees=current_arc,
        )
        for event in sorted(events, key=lambda event: event.proximity_key)[
            :current_window_size
        ]
    ]
    phase_window_size = max(3, current_window_size // 2)
    past_window = [
        enrich_primary_direction_hit_with_coordinate_context(
            event.payload,
            natal_coordinates=working_coordinates,
            coordinate_system=coordinate_system,
            coordinate_label=coordinate_label,
            natal_coordinate_points=coordinate_rings["points"],
            natal_coordinate_lots=coordinate_rings["lots"],
            arc_applied_degrees=current_arc,
        )
        for event in sorted(
            (event for event in events if event.payload["timing_phase"] == "past"),
            key=lambda event: event.chronological_key[0],
            reverse=True,
        )[:phase_window_size]
    ]
    future_window = [
        enrich_primary_direction_hit_with_coordinate_context(
            event.payload,
            natal_coordinates=working_coordinates,
            coordinate_system=coordinate_system,
            coordinate_label=coordinate_label,
            natal_coordinate_points=coordinate_rings["points"],
            natal_coordinate_lots=coordinate_rings["lots"],
            arc_applied_degrees=current_arc,
        )
        for event in [
            event
            for event in events
            if event.payload["timing_phase"] in ("future", "exact")
        ][:phase_window_size]
    ]
    exact_window = [
        enrich_primary_direction_hit_with_coordinate_context(
            event.payload,
            natal_coordinates=working_coordinates,
            coordinate_system=coordinate_system,
            coordinate_label=coordinate_label,
            natal_coordinate_points=coordinate_rings["points"],
            natal_coordinate_lots=coordinate_rings["lots"],
            arc_applied_degrees=current_arc,
        )
        for event in sorted(
            (event for event in events if event.payload["timing_phase"] == "exact"),
            key=lambda event: event.proximity_key,
        )[:current_window_size]
    ]
    current_coordinate_rings = build_primary_direction_coordinate_rings(
        working_coordinates,
        coordinate_system=coordinate_system,
        coordinate_label=coordinate_label,
        arc_applied_degrees=current_arc,
    )

    payload = {
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
        "promissors": promissors,
        "aspects": aspects,
        "current_age_years": float(working_current_age),
        "current_arc_degrees": float(current_arc),
        "current_arc_absolute_degrees": abs(float(current_arc)),
        "current_window": current_window,
        "past_window": past_window,
        "future_window": future_window,
        "exact_window": exact_window,
        "timeline": timeline,
    }
    return PrimaryDirectionAnalysis(payload=payload, current_arc=current_arc)


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
    coordinate_diagnostics: dict[str, dict[str, Any]],
    coordinate_points: dict[str, dict[str, Any]],
    coordinate_lots: dict[str, dict[str, Any]],
    current_coordinate_points: dict[str, dict[str, Any]],
    current_coordinate_lots: dict[str, dict[str, Any]],
    current_arc_degrees: Angle,
    current_hits: list[dict[str, Any]],
    show_pd_bounds: bool,
) -> dict[str, Any]:
    natal_points = extract_reference_points(natal_subject)
    natal_lots = build_lot_payloads(natal_subject)
    if coordinate_system == "right_ascension" and swe is not None:
        directed_points, directed_lots, directed_axes = (
            build_reprojected_primary_direction_chart_layers(
                birth_info,
                natal_subject,
                arc_degrees=float(current_arc_degrees),
            )
        )
    elif coordinate_system == "mundane_semiarc" and swe is not None:
        directed_points, directed_lots, directed_axes = (
            build_reprojected_mundane_primary_direction_chart_layers(
                birth_info,
                natal_subject,
                arc_degrees=float(current_arc_degrees),
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
        "current_arc_degrees": float(current_arc_degrees),
        "current_arc_absolute_degrees": abs(float(current_arc_degrees)),
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
        "directed_ascendant": directed_axes.get("Ascendant"),
        "directed_medium_coeli": directed_axes["Medium_Coeli"],
        "hits": current_hits[:8],
    }
