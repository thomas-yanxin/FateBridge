"""Authentic spherical Primary Directions (Placidus, Regiomontanus, Campanus, Alcabitius, Equatorial)."""

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
from fatebridge.core.astro.ephemeris import fast_swe_call
from fatebridge.core.astro.geometry import (
    Angle,
    combine_longitudes_exact,
    normalize_angle,
)
from fatebridge.core.astro.reference import TRADITIONAL_PLANETS
from fatebridge.core.astro.reference_frames import Matrix, rotate_spherical
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.core.ephemeris_runtime import swe
from fatebridge.core.predictive._common import (
    ASPECT_DEGREE_TO_META,
    HOUSE_NAME_TO_NUMBER,
    LOT_KEY_BY_POINT_NAME,
    LOT_LABELS,
    LOT_POINT_NAMES,
    SWISSEPH_PLANET_IDS,
    TIMING_POINT_NAMES,
    TROPICAL_YEAR_DAYS,
    build_lot_payloads,
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
from fatebridge.utils.civil_time import ZonedCalendar
from fatebridge.utils.timezones import format_local_time_or_utc

PRIMARY_DIRECTION_METHODS = (
    "placidus",
    "regiomontanus",
    "campanus",
    "alcabitius",
    "equatorial",
    "astroapp_alchabitius",
    "fatebridge_mundane_semiarc",
)

PRIMARY_DIRECTION_METHOD_LABELS = {
    "placidus": "Placidus 半弧主限",
    "regiomontanus": "Regiomontanus 位置圈主限",
    "campanus": "Campanus 主垂圈主限",
    "alcabitius": "Alcabitius 时辰弧主限",
    "equatorial": "赤道赤经主限",
    "astroapp_alchabitius": "Alcabitius 时辰弧主限",
    "fatebridge_mundane_semiarc": "Placidus 半弧主限",
}

PRIMARY_DIRECTION_METHOD_COORDINATES = {
    "placidus": ("mundane_semiarc", "半弧度"),
    "regiomontanus": ("circle_of_position", "位置圈赤经"),
    "campanus": ("prime_vertical", "主垂圈度"),
    "alcabitius": ("alcabitius_pole", "斜升度"),
    "equatorial": ("right_ascension", "赤经"),
    "astroapp_alchabitius": ("alcabitius_pole", "斜升度"),
    "fatebridge_mundane_semiarc": ("mundane_semiarc", "半弧度"),
}

PRIMARY_DIRECTION_TIME_KEY_RATES: dict[str, float] = {
    "Ptolemy": 1.0,
    "Naibod": 0.98564733,
    "Cardan": 0.98666667,
    "Solar_Arc": 0.98564733,
    "Van_Dam": 0.98564733,
}

PRIMARY_DIRECTION_BOUNDS_SYSTEM = "egyptian_bounds"
PRIMARY_DIRECTION_BOUNDS_LABEL = "埃及界限"
PRIMARY_DIRECTION_DEFAULT_ASPECTS = [0, 60, 90, 120, 180]
PRIMARY_DIRECTION_PROMISSORS = [
    *TRADITIONAL_PLANETS,
    "Ascendant",
    "Medium_Coeli",
    "Fortune",
]
PRIMARY_DIRECTION_SIGNIFICATOR_CUSPS = [
    "Second_House",
    "Third_House",
    "Fourth_House",
    "Fifth_House",
    "Sixth_House",
    "Seventh_House",
    "Eighth_House",
    "Ninth_House",
    "Eleventh_House",
    "Twelfth_House",
]
PRIMARY_DIRECTION_MAX_AGE_YEARS = 100.0
PRIMARY_DIRECTION_EXACT_WINDOW_YEARS = 0.01

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

PRIMARY_DIRECTION_TIMING_PHASE_LABELS = {
    "past": "已发生",
    "future": "即将发生",
    "exact": "当前触发",
}


def _canonical_pd_method(pd_method: str) -> str:
    if pd_method == "astroapp_alchabitius":
        return "alcabitius"
    if pd_method == "fatebridge_mundane_semiarc":
        return "placidus"
    return pd_method


def primary_direction_method_label(method_name: str) -> str:
    return PRIMARY_DIRECTION_METHOD_LABELS.get(method_name, method_name)


def primary_direction_coordinate_meta(pd_method: str) -> tuple[str, str]:
    if pd_method not in PRIMARY_DIRECTION_METHOD_COORDINATES:
        raise ValueError(
            "未知主限方法，请使用 placidus、regiomontanus、campanus、alcabitius 或 equatorial"
        )
    if swe is None and pd_method != "equatorial":
        return ("ecliptic_longitude", "Arc")
    return PRIMARY_DIRECTION_METHOD_COORDINATES[pd_method]


def primary_direction_approximation_meta(pd_method: str) -> tuple[str, str]:
    canonical = _canonical_pd_method(pd_method)
    return f"spherical_{canonical}", primary_direction_method_label(canonical)


def primary_direction_coordinate_runtime_meta(pd_method: str) -> tuple[str, str]:
    if swe is not None:
        return f"spherical_{_canonical_pd_method(pd_method)}", "swisseph_spherical_pd"
    return "ecliptic_runtime_reference_fallback", "native_ecliptic_reference_fallback"


@dataclass(frozen=True)
class PrimaryDirectionEquatorialContext:
    ut1: UT1Instant
    tt: TTInstant
    obliquity: float
    longitude_origin: float
    armc: float
    native_to_house: Matrix | None = None

    @property
    def julian_day(self) -> float:
        return self.ut1.as_float()


def build_primary_direction_equatorial_context(
    birth_info: AstroBirthInfo,
) -> PrimaryDirectionEquatorialContext:
    times = birth_info.time_scales
    if times.tt is None:
        raise ModuleNotFoundError("Swiss Ephemeris is required for primary directions")
    attitude = earth_attitude(swe, times.ut1, julian_day_tt=times.tt)
    armc = (attitude.house_sidereal_degrees + birth_info.longitude) % 360
    return PrimaryDirectionEquatorialContext(
        times.ut1,
        times.tt,
        attitude.reduction.house_obliquity,
        attitude.reduction.house_longitude_origin,
        float(armc),
        attitude.reduction.native_to_house,
    )


def project_absolute_degree_to_equatorial(
    absolute_degree: float,
    *,
    obliquity: float,
    longitude_origin: float = 0.0,
    ecliptic_latitude: float = 0.0,
) -> tuple[float, float]:
    right_ascension, declination, _ = swe.cotrans(
        (normalize_angle(absolute_degree - longitude_origin), ecliptic_latitude, 1.0),
        -obliquity,
    )
    return float(right_ascension) % 360.0, float(declination)


def point_equatorial_position(
    point_name: str,
    natal_subject: Any,
    *,
    context: PrimaryDirectionEquatorialContext,
) -> tuple[float, float]:
    if point_name in SWISSEPH_PLANET_IDS:
        equatorial, retflag = fast_swe_call(
            "calc",
            context.tt.as_float(),
            SWISSEPH_PLANET_IDS[point_name],
            swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_EQUATORIAL,
        )
        if retflag < 0:
            raise ValueError("Primary direction equatorial ephemeris failed")
        native_to_house = context.native_to_house
        if native_to_house is None:
            native_to_house = earth_attitude(
                swe, context.ut1, julian_day_tt=context.tt
            ).reduction.native_to_house
        return rotate_spherical(
            native_to_house,
            float(equatorial[0]),
            float(equatorial[1]),
        )
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


def semiarc_degrees_for_declination(latitude: float, declination: float) -> float:
    horizon_term = -math.tan(math.radians(latitude)) * math.tan(
        math.radians(declination)
    )
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


def _dynamic_time_key_rate(
    pd_time_key: str,
    context: PrimaryDirectionEquatorialContext,
    natal_subject: Any,
) -> float:
    if pd_time_key not in PRIMARY_DIRECTION_TIME_KEY_RATES:
        raise ValueError(
            "未知时间键，请使用 Ptolemy、Naibod、Cardan、Solar_Arc 或 Van_Dam"
        )
    if pd_time_key == "Solar_Arc":
        sun_point = getattr(natal_subject, "sun", None)
        speed = getattr(sun_point, "speed", None)
        if speed is not None and math.isfinite(speed) and speed > 0:
            return float(speed)
        if swe is not None:
            coords, flag = fast_swe_call(
                "calc", context.tt.as_float(), swe.SUN, swe.FLG_SWIEPH | swe.FLG_SPEED
            )
            if flag >= 0:
                return float(coords[3])
    elif pd_time_key == "Van_Dam" and swe is not None:
        tt0 = context.tt.as_float()
        c0, f0 = fast_swe_call(
            "calc", tt0, swe.SUN, swe.FLG_SWIEPH | swe.FLG_EQUATORIAL
        )
        c1, f1 = fast_swe_call(
            "calc", tt0 + 1.0, swe.SUN, swe.FLG_SWIEPH | swe.FLG_EQUATORIAL
        )
        if f0 >= 0 and f1 >= 0:
            diff = normalize_signed_angle(float(c1[0]) - float(c0[0]))
            if diff > 0:
                return diff
    return PRIMARY_DIRECTION_TIME_KEY_RATES[pd_time_key]


def _spherical_direct_arc(
    prom_ra: float,
    prom_dec: float,
    sig_ra: float,
    sig_dec: float,
    *,
    method: str,
    armc: float,
    latitude: float,
    sig_name: str,
) -> tuple[float | None, str | None]:
    """Return exact direct RA arc [0, 360) for promissor to reach significator's circle.

    Returns (None, "circumpolar") when a point does not rise/set or reach the target circle.
    """
    canon = _canonical_pd_method(method)
    if sig_name == "Medium_Coeli":
        return (prom_ra - armc) % 360.0, None
    if sig_name == "Imum_Coeli":
        return (prom_ra - (armc + 180.0)) % 360.0, None

    phi = math.radians(latitude)
    tan_phi = math.tan(phi)
    dec_p = math.radians(prom_dec)
    dec_s = math.radians(sig_dec)
    raic = (armc + 180.0) % 360.0

    if canon == "equatorial":
        if sig_name in {"Ascendant", "First_House"}:
            term = tan_phi * math.tan(dec_p)
            if abs(term) >= 1.0:
                return None, "circumpolar"
            oa_p = (prom_ra - math.degrees(math.asin(term))) % 360.0
            oa_asc = (armc + 90.0) % 360.0
            return (oa_p - oa_asc) % 360.0, None
        if sig_name in {"Descendant", "Seventh_House"}:
            term = tan_phi * math.tan(dec_p)
            if abs(term) >= 1.0:
                return None, "circumpolar"
            od_p = (prom_ra + math.degrees(math.asin(term))) % 360.0
            od_dsc = (armc + 270.0) % 360.0
            return (od_p - od_dsc) % 360.0, None
        return (prom_ra - sig_ra) % 360.0, None

    if canon == "placidus":
        dsa_s = semiarc_degrees_for_declination(latitude, sig_dec)
        dsa_p = semiarc_degrees_for_declination(latitude, prom_dec)
        if sig_name in {"Ascendant", "First_House"}:
            if dsa_p <= 0.0 or dsa_p >= 180.0:
                return None, "circumpolar"
            return (prom_ra - dsa_p - armc) % 360.0, None
        if sig_name in {"Descendant", "Seventh_House"}:
            if dsa_p <= 0.0 or dsa_p >= 180.0:
                return None, "circumpolar"
            return (prom_ra + dsa_p - armc) % 360.0, None
        e_s = normalize_signed_angle(sig_ra - armc)
        if dsa_s <= 0.0 or dsa_s >= 180.0:
            if abs(e_s) <= 1e-6:
                return (prom_ra - armc) % 360.0, None
            return None, "circumpolar"
        above_horizon = abs(e_s) <= dsa_s + 1e-9
        if above_horizon:
            k_s = e_s / dsa_s
            if abs(k_s) > 1e-9 and (dsa_p <= 0.0 or dsa_p >= 180.0):
                return None, "circumpolar"
            e_target = k_s * dsa_p
            return (prom_ra - e_target - armc) % 360.0, None
        nsa_s = 180.0 - dsa_s
        nsa_p = 180.0 - dsa_p
        e_ic = normalize_signed_angle(sig_ra - raic)
        k_s = e_ic / nsa_s
        if abs(k_s) > 1e-9 and (nsa_p <= 0.0 or nsa_p >= 180.0):
            return None, "circumpolar"
        e_target = k_s * nsa_p
        return (prom_ra - e_target - raic) % 360.0, None

    if canon == "regiomontanus":
        if sig_name in {"Ascendant", "First_House"}:
            m_rad = math.pi / 2.0
        elif sig_name in {"Descendant", "Seventh_House"}:
            m_rad = -math.pi / 2.0
        else:
            e_s_rad = math.radians(normalize_signed_angle(sig_ra - armc))
            m_rad = math.atan2(
                math.sin(e_s_rad),
                math.cos(e_s_rad) + tan_phi * math.tan(dec_s),
            )
        u_p = tan_phi * math.sin(m_rad) * math.tan(dec_p)
        if abs(u_p) >= 1.0:
            return None, "circumpolar"
        e_p_deg = math.degrees(m_rad + math.asin(u_p))
        return (prom_ra - armc - e_p_deg) % 360.0, None

    if canon == "campanus":
        if sig_name in {"Ascendant", "First_House"}:
            c_rad = math.pi / 2.0
        elif sig_name in {"Descendant", "Seventh_House"}:
            c_rad = -math.pi / 2.0
        else:
            e_s_rad = math.radians(normalize_signed_angle(sig_ra - armc))
            east_s = math.cos(dec_s) * math.sin(e_s_rad)
            zen_s = math.sin(phi) * math.sin(dec_s) + math.cos(phi) * math.cos(
                dec_s
            ) * math.cos(e_s_rad)
            c_rad = math.atan2(east_s, zen_s)
        cos_c = math.cos(c_rad)
        sin_c = math.sin(c_rad)
        r_den = math.hypot(cos_c, sin_c * math.cos(phi))
        if r_den < 1e-12:
            return None, "circumpolar"
        theta = math.atan2(sin_c * math.cos(phi), cos_c)
        u_p = (sin_c * math.sin(phi) * math.tan(dec_p)) / r_den
        if abs(u_p) >= 1.0:
            return None, "circumpolar"
        e_p_deg = math.degrees(theta + math.asin(u_p))
        return (prom_ra - armc - e_p_deg) % 360.0, None

    # Alcabitius (Gansten Ch. 3): proportional pole on semi-arc + Asc/MC oblique ascension
    if sig_name in {"Ascendant", "First_House"}:
        term = tan_phi * math.tan(dec_p)
        if abs(term) >= 1.0:
            return None, "circumpolar"
        oa_p = (prom_ra - math.degrees(math.asin(term))) % 360.0
        oa_asc = (armc + 90.0) % 360.0
        return (oa_p - oa_asc) % 360.0, None
    if sig_name in {"Descendant", "Seventh_House"}:
        term = tan_phi * math.tan(dec_p)
        if abs(term) >= 1.0:
            return None, "circumpolar"
        od_p = (prom_ra + math.degrees(math.asin(term))) % 360.0
        od_dsc = (armc + 270.0) % 360.0
        return (od_p - od_dsc) % 360.0, None
    dsa_s = semiarc_degrees_for_declination(latitude, sig_dec)
    if dsa_s <= 0.0 or dsa_s >= 180.0:
        return None, "circumpolar"
    e_s = normalize_signed_angle(sig_ra - armc)
    if abs(e_s) <= dsa_s + 1e-9:
        k_ratio = e_s / dsa_s
        tan_pole = tan_phi * min(1.0, abs(k_ratio))
        hem_sign = 1.0 if e_s >= 0.0 else -1.0
    else:
        nsa_s = 180.0 - dsa_s
        e_ic = normalize_signed_angle(sig_ra - raic)
        k_ratio = e_ic / nsa_s
        tan_pole = tan_phi * min(1.0, abs(k_ratio))
        hem_sign = -1.0 if e_ic >= 0.0 else 1.0
    u_s = hem_sign * tan_pole * math.tan(dec_s)
    u_p = hem_sign * tan_pole * math.tan(dec_p)
    if abs(u_s) >= 1.0 or abs(u_p) >= 1.0:
        return None, "circumpolar"
    oa_s = (sig_ra - math.degrees(math.asin(u_s))) % 360.0
    oa_p = (prom_ra - math.degrees(math.asin(u_p))) % 360.0
    return (oa_p - oa_s) % 360.0, None


def _mundane_circle_coordinate(
    ra: float,
    dec: float,
    *,
    method: str,
    armc: float,
    latitude: float,
) -> float | None:
    """Compute a 0..360 mundane circle angle (Asc=0, MC=90, Dsc=180, IC=270)."""
    canon = _canonical_pd_method(method)
    e_deg = normalize_signed_angle(ra - armc)
    if canon == "campanus":
        phi = math.radians(latitude)
        dec_r = math.radians(dec)
        e_r = math.radians(e_deg)
        east = math.cos(dec_r) * math.sin(e_r)
        zen = math.sin(phi) * math.sin(dec_r) + math.cos(phi) * math.cos(
            dec_r
        ) * math.cos(e_r)
        return normalize_angle(90.0 - math.degrees(math.atan2(east, zen)))
    if canon == "regiomontanus":
        phi = math.radians(latitude)
        e_r = math.radians(e_deg)
        m_deg = math.degrees(
            math.atan2(
                math.sin(e_r),
                math.cos(e_r) + math.tan(phi) * math.tan(math.radians(dec)),
            )
        )
        return normalize_angle(90.0 - m_deg)
    dsa = semiarc_degrees_for_declination(latitude, dec)
    if dsa <= 0.0 or dsa >= 180.0:
        return None
    hour_angle = normalize_signed_angle(armc - ra)
    pos, _ = mundane_semiarc_position(hour_angle=hour_angle, semiarc_degrees=dsa)
    return pos


def primary_direction_aspect_meta(aspect_degree: int) -> tuple[str, str]:
    meta = ASPECT_DEGREE_TO_META.get(aspect_degree)
    if meta is not None:
        return meta
    return f"{aspect_degree}deg", f"{aspect_degree}°"


def normalize_primary_direction_aspects(pd_aspects: list[int] | None) -> list[int]:
    if not pd_aspects:
        return PRIMARY_DIRECTION_DEFAULT_ASPECTS.copy()
    normalized: list[int] = []
    for value in pd_aspects:
        try:
            degree = int(float(value)) % 360
        except (TypeError, ValueError):
            continue
        if degree not in normalized:
            normalized.append(degree)
    return normalized or PRIMARY_DIRECTION_DEFAULT_ASPECTS.copy()


def primary_direction_aspect_variants(aspect_degree: int) -> list[float]:
    if aspect_degree in {0, 180}:
        return [float(aspect_degree)]
    return [float(aspect_degree), float((360 - aspect_degree) % 360)]


def build_primary_direction_coordinate_entry(
    *,
    item_key: str,
    item_label: str,
    coordinate_degrees: Angle,
    coordinate_system: str,
    coordinate_label: str,
    arc_applied_degrees: Angle = 0.0,
) -> dict[str, Any]:
    normalized_coordinate = normalize_angle(float(coordinate_degrees))
    return {
        "key": item_key,
        "label": item_label,
        "coordinate_system": coordinate_system,
        "coordinate_label": coordinate_label,
        "coordinate_degrees": normalized_coordinate,
        "arc_applied_degrees": float(arc_applied_degrees),
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


def _extract_all_natal_points(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    context: PrimaryDirectionEquatorialContext | None,
    *,
    natal_lots: Mapping[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, float], dict[str, float], dict[str, tuple[float, float]]]:
    """Return (ecliptic_longitudes, ecliptic_latitudes, ra_dec_pairs) for all PD points."""
    longitudes = extract_reference_longitudes(natal_subject)
    latitudes: dict[str, float] = {}
    for name in TIMING_POINT_NAMES:
        attr = name.lower() if name in {"Ascendant", "Medium_Coeli"} else name.lower()
        pt = getattr(natal_subject, attr, None)
        latitudes[name] = float(getattr(pt, "latitude", 0.0) or 0.0)
    if is_ascendant_resolved(natal_subject):
        lots = (
            dict(natal_lots)
            if natal_lots is not None
            else build_lot_payloads(natal_subject)
        )
        for lot_key, payload in lots.items():
            p_name = LOT_POINT_NAMES[lot_key]
            longitudes[p_name] = float(
                payload.get("longitude", payload["absolute_degree"])
            )
            latitudes[p_name] = 0.0
    for cusp_name in PRIMARY_DIRECTION_SIGNIFICATOR_CUSPS:
        pt = getattr(natal_subject, cusp_name.lower(), None)
        if pt is not None:
            longitudes[cusp_name] = normalize_angle(float(pt.abs_pos))
            latitudes[cusp_name] = 0.0

    equatorial: dict[str, tuple[float, float]] = {}
    offset = getattr(natal_subject, "calculation_basis", {}).get(
        "ayanamsha_degrees", 0.0
    )
    if context is not None and swe is not None:
        for name, lon in longitudes.items():
            if name in SWISSEPH_PLANET_IDS:
                equatorial[name] = point_equatorial_position(
                    name, natal_subject, context=context
                )
            elif name == "Medium_Coeli":
                equatorial[name] = project_absolute_degree_to_equatorial(
                    lon + offset,
                    obliquity=context.obliquity,
                    longitude_origin=context.longitude_origin,
                )
            else:
                equatorial[name] = project_absolute_degree_to_equatorial(
                    lon + offset,
                    obliquity=context.obliquity,
                    longitude_origin=context.longitude_origin,
                )
    return longitudes, latitudes, equatorial


@dataclass(frozen=True)
class _PrimaryDirectionEvent:
    chronological_key: tuple[float, float, str, str]
    relative_years: float
    payload: dict[str, Any]

    @property
    def proximity_key(self) -> tuple[float, float, float]:
        age_years, arc, _, _ = self.chronological_key
        return abs(self.relative_years), age_years, arc


@dataclass(frozen=True)
class PrimaryDirectionAnalysis:
    payload: dict[str, Any]
    current_arc: float
    context: PrimaryDirectionEquatorialContext | None = None
    equatorial: Mapping[str, tuple[float, float]] | None = None
    natal_lots: Mapping[str, dict[str, Any]] | None = None


def build_primary_directions_payload(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    analysis_datetime: datetime,
    pd_method: str = "placidus",
    pd_time_key: str = "Ptolemy",
    pd_type: int = 0,
    pd_aspects: list[int] | None = None,
    max_age_years: float = PRIMARY_DIRECTION_MAX_AGE_YEARS,
    current_window_size: int = 6,
    nearby_years: float = 5.0,
    timeline_limit: int = 25,
    direction_mode: str = "zodiacal",
    natal_lots: Mapping[str, dict[str, Any]] | None = None,
    include_full_timelines: bool = True,
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
        nearby_years=nearby_years,
        timeline_limit=timeline_limit,
        direction_mode=direction_mode,
        natal_lots=natal_lots,
        include_full_timelines=include_full_timelines,
    ).payload


def build_primary_direction_analysis(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    analysis_datetime: datetime,
    pd_method: str = "placidus",
    pd_time_key: str = "Ptolemy",
    pd_type: int = 0,
    pd_aspects: list[int] | None = None,
    max_age_years: float = PRIMARY_DIRECTION_MAX_AGE_YEARS,
    current_window_size: int = 6,
    nearby_years: float = 5.0,
    timeline_limit: int = 25,
    direction_mode: str = "zodiacal",
    natal_lots: Mapping[str, dict[str, Any]] | None = None,
    include_full_timelines: bool = True,
) -> PrimaryDirectionAnalysis:
    coordinate_system, coordinate_label = primary_direction_coordinate_meta(pd_method)
    approximation, approximation_label = primary_direction_approximation_meta(pd_method)
    precision, backend = primary_direction_coordinate_runtime_meta(pd_method)
    birth_utc = birth_info.utc_calendar
    birth_zone = birth_info.local_datetime.tzinfo
    assert birth_zone is not None
    aspects = normalize_primary_direction_aspects(pd_aspects)
    context = (
        build_primary_direction_equatorial_context(birth_info)
        if swe is not None
        else None
    )
    time_key_rate = (
        _dynamic_time_key_rate(pd_time_key, context, natal_subject)
        if context is not None
        else PRIMARY_DIRECTION_TIME_KEY_RATES.get(pd_time_key, 1.0)
    )
    current_age = calculate_age_years(birth_info, analysis_datetime)
    direction_label = "converse" if pd_type == 1 else "direct"
    direction_label_zh = "逆推" if pd_type == 1 else "顺推"
    sign_mult = -1.0 if pd_type == 1 else 1.0
    current_arc = (current_age * time_key_rate or 0.0) * sign_mult

    resolved_natal_lots = (
        dict(natal_lots)
        if natal_lots is not None
        else (
            build_lot_payloads(natal_subject)
            if is_ascendant_resolved(natal_subject)
            else {}
        )
    )
    longitudes, latitudes, equatorial = _extract_all_natal_points(
        birth_info, natal_subject, context, natal_lots=resolved_natal_lots
    )
    offset = getattr(natal_subject, "calculation_basis", {}).get(
        "ayanamsha_degrees", 0.0
    )

    coord_points: dict[str, dict[str, Any]] = {}
    coord_lots: dict[str, dict[str, Any]] = {}
    curr_coord_points: dict[str, dict[str, Any]] = {}
    curr_coord_lots: dict[str, dict[str, Any]] = {}
    diagnostics: dict[str, dict[str, Any]] = {}

    for name in [*TIMING_POINT_NAMES, *LOT_POINT_NAMES.values()]:
        if name not in longitudes:
            continue
        if name in equatorial and context is not None:
            ra, dec = equatorial[name]
            dsa = semiarc_degrees_for_declination(birth_info.latitude, dec)
            diagnostics[name] = {
                "right_ascension": round(ra, 4),
                "declination": round(dec, 4),
                "semiarc_degrees": round(dsa, 4),
                "circumpolar": dsa <= 0.0 or dsa >= 180.0,
            }
            base_val = ra
        else:
            base_val = longitudes[name]
        lbl = LOT_LABELS.get(LOT_KEY_BY_POINT_NAME.get(name, ""), planet_label(name))
        entry_n = build_primary_direction_coordinate_entry(
            item_key=name,
            item_label=lbl,
            coordinate_degrees=base_val,
            coordinate_system=coordinate_system,
            coordinate_label=coordinate_label,
        )
        entry_c = build_primary_direction_coordinate_entry(
            item_key=name,
            item_label=lbl,
            coordinate_degrees=base_val + current_arc,
            coordinate_system=coordinate_system,
            coordinate_label=coordinate_label,
            arc_applied_degrees=current_arc,
        )
        if name in LOT_KEY_BY_POINT_NAME:
            lk = LOT_KEY_BY_POINT_NAME[name]
            coord_lots[lk] = entry_n
            curr_coord_lots[lk] = entry_c
        else:
            coord_points[name] = entry_n
            curr_coord_points[name] = entry_c

    promissors = [p for p in PRIMARY_DIRECTION_PROMISSORS if p in longitudes]
    significators = [
        s
        for s in [*TIMING_POINT_NAMES, "Fortune", *PRIMARY_DIRECTION_SIGNIFICATOR_CUSPS]
        if s in longitudes
    ]

    events: list[_PrimaryDirectionEvent] = []
    skipped_circumpolar: list[dict[str, str]] = []
    seen_hits: set[tuple[str, str, str, float]] = set()
    canon_method = _canonical_pd_method(pd_method)

    for prom in promissors:
        prom_lon = longitudes[prom]
        prom_lat = latitudes.get(prom, 0.0)
        for sig in significators:
            if prom == sig:
                continue
            is_cusp_sig = sig in HOUSE_NAME_TO_NUMBER
            aspect_list = [0] if is_cusp_sig else aspects
            sig_ra, sig_dec = equatorial.get(sig, (longitudes[sig], 0.0))
            for aspect_deg in aspect_list:
                aspect_key, aspect_label_text = primary_direction_aspect_meta(
                    aspect_deg
                )
                for variant in primary_direction_aspect_variants(aspect_deg):
                    if prom == sig and variant == 0.0:
                        continue
                    arc_deg: float | None = None
                    if context is not None and swe is not None:
                        if direction_mode == "mundane":
                            prom_ra, prom_dec = equatorial[prom]
                            c_prom = _mundane_circle_coordinate(
                                prom_ra,
                                prom_dec,
                                method=canon_method,
                                armc=context.armc,
                                latitude=birth_info.latitude,
                            )
                            c_sig = _mundane_circle_coordinate(
                                sig_ra,
                                sig_dec,
                                method=canon_method,
                                armc=context.armc,
                                latitude=birth_info.latitude,
                            )
                            if c_prom is None or c_sig is None:
                                skipped_circumpolar.append(
                                    {
                                        "promissor": prom,
                                        "significator": sig,
                                        "reason": "circumpolar",
                                    }
                                )
                                continue
                            # In mundane mode, 90° equals 1 quadrant (semi-arc)
                            target_c = (c_sig + variant) % 360.0
                            direct_arc = (c_prom - target_c) % 360.0
                            arc_deg = (
                                (-direct_arc) % 360.0 if pd_type == 1 else direct_arc
                            )
                        else:
                            # Zodiacal aspect point on ecliptic (exact latitude on conjunction)
                            target_prom_lon = (prom_lon + variant) % 360.0
                            target_prom_lat = prom_lat if aspect_deg == 0 else 0.0
                            if aspect_deg == 0 and prom in equatorial:
                                p_ra, p_dec = equatorial[prom]
                            else:
                                p_ra, p_dec = project_absolute_degree_to_equatorial(
                                    target_prom_lon + offset,
                                    obliquity=context.obliquity,
                                    longitude_origin=context.longitude_origin,
                                    ecliptic_latitude=target_prom_lat,
                                )
                            spherical_arc, skip_reason = _spherical_direct_arc(
                                p_ra,
                                p_dec,
                                sig_ra,
                                sig_dec,
                                method=canon_method,
                                armc=context.armc,
                                latitude=birth_info.latitude,
                                sig_name=sig,
                            )
                            if spherical_arc is None:
                                if len(skipped_circumpolar) < 50:
                                    skipped_circumpolar.append(
                                        {
                                            "promissor": prom,
                                            "significator": sig,
                                            "reason": skip_reason or "circumpolar",
                                        }
                                    )
                                continue
                            arc_deg = (
                                (-spherical_arc) % 360.0
                                if pd_type == 1
                                else spherical_arc
                            )
                    else:
                        target_lon = (longitudes[sig] + variant) % 360.0
                        arc_deg = (
                            (prom_lon - target_lon) % 360.0
                            if pd_type == 1
                            else (target_lon - prom_lon) % 360.0
                        )

                    if arc_deg is None:
                        continue
                    age_years = arc_deg / time_key_rate
                    if age_years <= 0.05 or age_years > max_age_years:
                        continue
                    dedupe = (prom, sig, aspect_key, round(age_years, 5))
                    if dedupe in seen_hits:
                        continue
                    seen_hits.add(dedupe)
                    event_dt = ZonedCalendar(
                        birth_utc.shifted(
                            timedelta(days=age_years * TROPICAL_YEAR_DAYS)
                        ),
                        birth_zone,
                    ).require_datetime()
                    rel_years = age_years - current_age
                    phase, phase_lbl = primary_direction_timing_phase(rel_years)
                    arc_applied = -arc_deg if pd_type == 1 else arc_deg
                    sig_lbl = (
                        f"第{HOUSE_NAME_TO_NUMBER[sig]}宫宫头"
                        if is_cusp_sig
                        else LOT_LABELS.get(
                            LOT_KEY_BY_POINT_NAME.get(sig, ""), planet_label(sig)
                        )
                    )
                    prom_lbl = LOT_LABELS.get(
                        LOT_KEY_BY_POINT_NAME.get(prom, ""), planet_label(prom)
                    )
                    hit_payload: dict[str, Any] = {
                        "arc_degrees": arc_deg,
                        "arc_applied_degrees": arc_applied,
                        "promissor": prom,
                        "promissor_label": prom_lbl,
                        "significator": sig,
                        "significator_label": sig_lbl,
                        "aspect": aspect_key,
                        "aspect_label": aspect_label_text,
                        "aspect_degree": aspect_deg,
                        "aspect_variant_degrees": variant,
                        "event_age_years": age_years,
                        "event_datetime": format_local_time_or_utc(
                            event_dt, timespec="seconds"
                        ),
                        "direction_mode": direction_label,
                        "direction_mode_label": direction_label_zh,
                        "pd_direction_mode": direction_mode,
                        "coordinate_system": coordinate_system,
                        "coordinate_label": coordinate_label,
                        "relative_years_from_current": rel_years,
                        "relative_arc_from_current": arc_applied - current_arc,
                        "timing_phase": phase,
                        "timing_phase_label": phase_lbl,
                        "distance_from_current_years": abs(rel_years),
                    }
                    events.append(
                        _PrimaryDirectionEvent(
                            (age_years, arc_deg, prom, sig),
                            rel_years,
                            hit_payload,
                        )
                    )

    events.sort(key=lambda item: item.chronological_key)
    full_timeline = [e.payload for e in events]
    total_timeline_count = len(full_timeline)
    if include_full_timelines:
        timeline = full_timeline
    else:
        nearby = [
            item
            for item in full_timeline
            if abs(item["relative_years_from_current"]) <= nearby_years
        ]
        if len(nearby) > timeline_limit:
            closest_indices = sorted(
                range(len(nearby)),
                key=lambda idx: (
                    nearby[idx]["distance_from_current_years"],
                    nearby[idx]["event_age_years"],
                    idx,
                ),
            )[:timeline_limit]
            nearby = [nearby[idx] for idx in sorted(closest_indices)]
        timeline = nearby
    all_proximity = sorted(events, key=lambda item: item.proximity_key)
    current_window = [e.payload for e in all_proximity[:current_window_size]]
    current_window_total_count = len(all_proximity)
    phase_size = max(3, current_window_size // 2)
    all_past = sorted(
        (e for e in events if e.payload["timing_phase"] == "past"),
        key=lambda item: item.chronological_key[0],
        reverse=True,
    )
    past_window = [e.payload for e in all_past[:phase_size]]
    past_window_total_count = len(all_past)
    all_future = [e for e in events if e.payload["timing_phase"] in ("future", "exact")]
    future_window = [e.payload for e in all_future[:phase_size]]
    future_window_total_count = len(all_future)
    all_exact = sorted(
        (e for e in events if e.payload["timing_phase"] == "exact"),
        key=lambda item: item.proximity_key,
    )
    exact_window = [e.payload for e in all_exact[:current_window_size]]
    exact_window_total_count = len(all_exact)

    payload = {
        "method": pd_method,
        "canonical_method": canon_method,
        "method_label": primary_direction_method_label(pd_method),
        "time_key": pd_time_key,
        "time_key_label": pd_time_key,
        "time_key_rate": time_key_rate,
        "pd_type": pd_type,
        "direction_mode": direction_label,
        "direction_mode_label": direction_label_zh,
        "pd_direction_mode": direction_mode,
        "coordinate_system": coordinate_system,
        "coordinate_label": coordinate_label,
        "approximation": approximation,
        "approximation_label": approximation_label,
        "coordinate_precision": precision,
        "coordinate_backend": backend,
        "coordinate_diagnostics": diagnostics,
        "coordinate_points": coord_points,
        "coordinate_lots": coord_lots,
        "current_coordinate_points": curr_coord_points,
        "current_coordinate_lots": curr_coord_lots,
        "promissors": promissors,
        "significators": significators,
        "aspects": aspects,
        "current_age_years": float(current_age),
        "current_arc_degrees": float(current_arc),
        "current_arc_absolute_degrees": abs(float(current_arc)),
        "current_window": current_window,
        "current_window_total_count": current_window_total_count,
        "past_window": past_window,
        "past_window_total_count": past_window_total_count,
        "future_window": future_window,
        "future_window_total_count": future_window_total_count,
        "exact_window": exact_window,
        "exact_window_total_count": exact_window_total_count,
        "timeline": timeline,
        "total_timeline_count": total_timeline_count,
        "skipped_circumpolar_count": len(skipped_circumpolar),
    }
    if not include_full_timelines:
        payload["timeline_truncated"] = len(timeline) < total_timeline_count
    return PrimaryDirectionAnalysis(
        payload=payload,
        current_arc=float(current_arc),
        context=context,
        equatorial=equatorial,
        natal_lots=resolved_natal_lots,
    )


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
    exact_hits: list[dict[str, Any]] | None = None,
    hits_total_count: int | None = None,
    exact_hits_total_count: int | None = None,
    natal_lots: Mapping[str, dict[str, Any]] | None = None,
    context: PrimaryDirectionEquatorialContext | None = None,
    equatorial: Mapping[str, tuple[float, float]] | None = None,
    embedded_in_western_timing: bool = False,
    include_shared_primary_directions: bool = False,
) -> dict[str, Any]:
    natal_points = extract_reference_points(natal_subject)
    resolved_natal_lots = (
        dict(natal_lots)
        if natal_lots is not None
        else (
            build_lot_payloads(natal_subject)
            if is_ascendant_resolved(natal_subject)
            else {}
        )
    )
    arc_float = float(current_arc_degrees)
    asc_sign = normalize_sign_name(natal_subject.ascendant.sign)
    resolved_context = (
        context
        if context is not None
        else (
            build_primary_direction_equatorial_context(birth_info)
            if swe is not None
            else None
        )
    )
    offset = getattr(natal_subject, "calculation_basis", {}).get(
        "ayanamsha_degrees", 0.0
    )

    directed_points: dict[str, dict[str, Any]] = {}
    for pt_name in extract_reference_longitudes(natal_subject):
        if resolved_context is not None and swe is not None:
            if equatorial is not None and pt_name in equatorial:
                ra, dec = equatorial[pt_name]
            else:
                ra, dec = point_equatorial_position(
                    pt_name, natal_subject, context=resolved_context
                )
            lon, _ = project_equatorial_to_ecliptic(
                ra + arc_float,
                dec,
                obliquity=resolved_context.obliquity,
                longitude_origin=resolved_context.longitude_origin,
                zodiac_offset=offset,
            )
        else:
            lon = normalize_angle(
                point_absolute_position(natal_subject, pt_name) + arc_float
            )
        directed_points[pt_name] = longitude_to_point_dict(pt_name, lon)

    directed_lots: dict[str, dict[str, Any]] = {}
    for lot_key, lot_data in resolved_natal_lots.items():
        base_lon = float(lot_data.get("longitude", lot_data["absolute_degree"]))
        lot_point_name = LOT_POINT_NAMES[lot_key]
        if resolved_context is not None and swe is not None:
            if equatorial is not None and lot_point_name in equatorial:
                ra, dec = equatorial[lot_point_name]
            else:
                ra, dec = project_absolute_degree_to_equatorial(
                    base_lon + offset,
                    obliquity=resolved_context.obliquity,
                    longitude_origin=resolved_context.longitude_origin,
                )
            lon, _ = project_equatorial_to_ecliptic(
                ra + arc_float,
                dec,
                obliquity=resolved_context.obliquity,
                longitude_origin=resolved_context.longitude_origin,
                zodiac_offset=offset,
            )
        else:
            lon = normalize_angle(base_lon + arc_float)
        directed_lots[lot_key] = {
            **longitude_to_point_dict(lot_point_name, lon),
            "lot": lot_key,
            "lot_label": LOT_LABELS[lot_key],
        }

    sign_changes: list[dict[str, Any]] = []
    for pt_name in TIMING_POINT_NAMES:
        np = natal_points.get(pt_name.lower())
        dp = directed_points.get(pt_name)
        if np and dp and np["sign"] != dp["sign"]:
            sign_changes.append(
                {
                    "point": pt_name,
                    "point_label": planet_label(pt_name),
                    "from_sign": np["sign"],
                    "from_sign_label": np["sign_label"],
                    "to_sign": dp["sign"],
                    "to_sign_label": dp["sign_label"],
                }
            )

    bounds_overlay: dict[str, Any] = {
        "system": PRIMARY_DIRECTION_BOUNDS_SYSTEM,
        "system_label": PRIMARY_DIRECTION_BOUNDS_LABEL,
        "enabled": show_pd_bounds,
        "points": {},
        "lots": {},
    }
    if show_pd_bounds:
        bounds_overlay["points"] = {
            name: {
                "key": name,
                "label": p.get("point_label"),
                "sign": p["sign"],
                "degree": p["degree"],
                **resolve_egyptian_bound(p["sign"], p["degree"]),
            }
            for name, p in directed_points.items()
        }
        bounds_overlay["lots"] = {
            lk: {
                "key": lk,
                "label": l.get("lot_label"),
                "sign": l["sign"],
                "degree": l["degree"],
                **resolve_egyptian_bound(l["sign"], l["degree"]),
            }
            for lk, l in directed_lots.items()
        }

    resolved_exact_hits = (
        list(exact_hits)
        if exact_hits is not None
        else [item for item in current_hits if item.get("timing_phase") == "exact"]
    )
    resolved_hits = list(current_hits)
    payload: dict[str, Any] = {
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
        "current_arc_degrees": arc_float,
        "current_arc_absolute_degrees": abs(arc_float),
        "show_pd_bounds": show_pd_bounds,
        "approximation": approximation,
        "approximation_label": approximation_label,
        "coordinate_precision": coordinate_precision,
        "coordinate_backend": coordinate_backend,
        "exact_hits": resolved_exact_hits,
        "exact_hits_total_count": (
            exact_hits_total_count
            if exact_hits_total_count is not None
            else len(resolved_exact_hits)
        ),
        "bounds_overlay": bounds_overlay,
        "directed_points": directed_points,
        "directed_lots": directed_lots,
        "sign_changes": sign_changes,
        "directed_ascendant": directed_points.get("Ascendant"),
        "directed_medium_coeli": directed_points.get("Medium_Coeli"),
        "hits": resolved_hits,
        "hits_total_count": (
            hits_total_count if hits_total_count is not None else len(resolved_hits)
        ),
        "asc_sign": asc_sign,
    }
    if not embedded_in_western_timing:
        payload.update(
            {
                "coordinate_diagnostics": coordinate_diagnostics,
                "natal_coordinate_points": coordinate_points,
                "natal_coordinate_lots": coordinate_lots,
                "directed_coordinate_points": current_coordinate_points,
                "directed_coordinate_lots": current_coordinate_lots,
                "coordinate_hits": resolved_hits,
            }
        )
    elif not include_shared_primary_directions:
        payload.update(
            {
                "coordinate_diagnostics": coordinate_diagnostics,
                "directed_coordinate_points": current_coordinate_points,
                "directed_coordinate_lots": current_coordinate_lots,
            }
        )
    return payload
