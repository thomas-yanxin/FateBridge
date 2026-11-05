"""西占推运共享底座：导入、常量与跨技法工具函数。"""

from __future__ import annotations

import math
from calendar import monthrange
from collections import Counter
from datetime import datetime, timedelta
from fractions import Fraction
from typing import Any, Dict, List, Mapping, Optional

from fatebridge.core.astro.birth import (
    AstroBirthInfo,
    build_astro_birth_info,
    require_resolved_birth_timezone,
)
from fatebridge.core.astro.geometry import (
    Angle,
    angular_separation_fraction,
    combine_longitudes,
    normalize_angle,
)
from fatebridge.core.astro.horizon import horizon_altitude
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.astrology_tables import (
    EGYPTIAN_BOUNDS_BY_SIGN as EGYPTIAN_BOUNDS_BY_SIGN,
)
from fatebridge.core.astrology_tables import (  # Predictive reference tables.
    RULER_BY_SIGN,
    SIGN_LABELS_ZH,
    SIGNS,
)
from fatebridge.core.ephemeris_runtime import (
    ephemeris_call,
    preserve_ephemeris_path,
    swe,
)
from fatebridge.core.execution_context import current_datetime
from fatebridge.utils.timezones import parse_timezone_name, validate_local_clock

TROPICAL_YEAR_DAYS = 365.2425
TIMING_POINT_NAMES = [
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Ascendant",
    "Medium_Coeli",
]
TRANSIT_POINT_NAMES = [
    *TIMING_POINT_NAMES,
    "Uranus",
    "Neptune",
    "Pluto",
]
TRADITIONAL_PLANETS = [
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
]

POINT_ATTRIBUTE_NAMES = {
    "Sun": "sun",
    "Moon": "moon",
    "Mercury": "mercury",
    "Venus": "venus",
    "Mars": "mars",
    "Jupiter": "jupiter",
    "Saturn": "saturn",
    "Uranus": "uranus",
    "Neptune": "neptune",
    "Pluto": "pluto",
    "Ascendant": "ascendant",
    "Medium_Coeli": "medium_coeli",
}

SIGN_ABBREVIATIONS = {
    "Ari": "Aries",
    "Tau": "Taurus",
    "Gem": "Gemini",
    "Can": "Cancer",
    "Leo": "Leo",
    "Vir": "Virgo",
    "Lib": "Libra",
    "Sco": "Scorpio",
    "Sag": "Sagittarius",
    "Cap": "Capricorn",
    "Aqu": "Aquarius",
    "Pis": "Pisces",
}

PLANET_LABELS = {
    "Sun": "太阳",
    "Moon": "月亮",
    "Mercury": "水星",
    "Venus": "金星",
    "Mars": "火星",
    "Jupiter": "木星",
    "Saturn": "土星",
    "Uranus": "天王星",
    "Neptune": "海王星",
    "Pluto": "冥王星",
    "Ascendant": "上升点",
    "Medium_Coeli": "天顶",
    "North Node": "北交点",
    "South Node": "南交点",
    "Fortune": "幸运点",
    "Spirit": "精神点",
}

HOUSE_NAME_TO_NUMBER = {
    "First_House": 1,
    "Second_House": 2,
    "Third_House": 3,
    "Fourth_House": 4,
    "Fifth_House": 5,
    "Sixth_House": 6,
    "Seventh_House": 7,
    "Eighth_House": 8,
    "Ninth_House": 9,
    "Tenth_House": 10,
    "Eleventh_House": 11,
    "Twelfth_House": 12,
}

ASPECT_DEGREES = [
    ("conjunction", "合相", 0.0),
    ("sextile", "六合", 60.0),
    ("square", "刑", 90.0),
    ("trine", "拱", 120.0),
    ("opposition", "冲", 180.0),
]
# Degree → (key, label) for O(1) aspect-meta lookup. ASPECT_DEGREES above stays
# the single source of truth; this index is derived from it once at import.
ASPECT_DEGREE_TO_META = {
    int(value): (key, label) for key, label, value in ASPECT_DEGREES
}
SWISSEPH_PLANET_IDS = {
    "Sun": 0,
    "Moon": 1,
    "Mercury": 2,
    "Venus": 3,
    "Mars": 4,
    "Jupiter": 5,
    "Saturn": 6,
}

LOT_LABELS = {
    "lot_of_fortune": "幸运点",
    "lot_of_spirit": "精神点",
}
LOT_POINT_NAMES = {
    "lot_of_fortune": "Fortune",
    "lot_of_spirit": "Spirit",
}
LOT_KEY_BY_POINT_NAME = {value: key for key, value in LOT_POINT_NAMES.items()}
ZR_PHASE_LABELS = {
    "angular": "角宫",
    "succedent": "续宫",
    "cadent": "衰宫",
}


def ensure_predictive_backend_available() -> None:
    if swe is None:
        raise ImportError("Swiss Ephemeris 未安装，无法启用西占推运能力。")


def build_predictive_birth_info(
    *,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int,
    birth_longitude: float,
    birth_latitude: float,
    birth_minute: int = 0,
    birth_timezone: Optional[str] = None,
    name: Optional[str] = None,
    birth_place: Optional[str] = None,
) -> AstroBirthInfo:
    return build_astro_birth_info(
        birth_year=birth_year,
        birth_month=birth_month,
        birth_day=birth_day,
        birth_hour=birth_hour,
        birth_minute=birth_minute,
        birth_timezone=birth_timezone,
        birth_longitude=birth_longitude,
        birth_latitude=birth_latitude,
        name=name,
        birth_place=birth_place,
        require_resolved_timezone=True,
    )


def build_analysis_datetime(
    birth_info: AstroBirthInfo,
    analysis_year: Optional[int] = None,
    analysis_month: Optional[int] = None,
    analysis_day: Optional[int] = None,
    analysis_hour: Optional[int] = None,
    analysis_minute: Optional[int] = None,
) -> datetime:
    """Resolve the target clock independently of the natal clock.

    Date-only callers retain the natal hour/minute. Each explicit clock part
    overrides that fallback, including zero; dates still use the call clock
    for missing components. The wall clock is interpreted in birth_timezone.
    """
    timezone_name = birth_info.timezone
    tzinfo = parse_timezone_name(timezone_name)
    now = current_datetime(tzinfo, timezone_name, now_provider=datetime.now)
    year = now.year if analysis_year is None else analysis_year
    month = now.month if analysis_month is None else analysis_month
    # A default day must fit the requested month (including leap-year changes).
    # Explicit days retain datetime's validation instead of being rewritten.
    day = (
        min(now.day, monthrange(year, month)[1])
        if analysis_day is None
        else analysis_day
    )
    target = datetime(
        year,
        month,
        day,
        birth_info.local_datetime.hour if analysis_hour is None else analysis_hour,
        (
            birth_info.local_datetime.minute
            if analysis_minute is None
            else analysis_minute
        ),
        tzinfo=tzinfo,
    )
    try:
        validate_local_clock(target)
    except ValueError as error:
        raise ValueError(str(error).replace("出生钟时", "分析钟时")) from error
    return target


def resolve_local_birthday_anniversary(
    birth_local_datetime: datetime,
    target_year: int,
    *,
    tzinfo: Optional[Any] = None,
) -> datetime:
    target_day = min(
        birth_local_datetime.day,
        monthrange(target_year, birth_local_datetime.month)[1],
    )
    return datetime(
        target_year,
        birth_local_datetime.month,
        target_day,
        birth_local_datetime.hour,
        birth_local_datetime.minute,
        birth_local_datetime.second,
        birth_local_datetime.microsecond,
        tzinfo=tzinfo or birth_local_datetime.tzinfo,
    )


def add_months(moment: datetime, months: int) -> datetime:
    month_index = (moment.month - 1) + months
    target_year = moment.year + (month_index // 12)
    target_month = (month_index % 12) + 1
    target_day = min(moment.day, monthrange(target_year, target_month)[1])
    return datetime(
        target_year,
        target_month,
        target_day,
        moment.hour,
        moment.minute,
        moment.second,
        moment.microsecond,
        tzinfo=moment.tzinfo,
    )


def normalize_sign_name(sign_name: str) -> str:
    return SIGN_ABBREVIATIONS.get(sign_name, sign_name)


def sign_label(sign_name: str) -> str:
    normalized = normalize_sign_name(sign_name)
    return f"{SIGN_LABELS_ZH.get(normalized, normalized)}座"


def resolve_egyptian_bound(sign_name: str, degree_in_sign: float) -> Dict[str, Any]:
    normalized_sign = normalize_sign_name(sign_name)
    normalized_degree = max(0.0, min(float(degree_in_sign), 29.9999))
    for lord, start_degree, end_degree in EGYPTIAN_BOUNDS_BY_SIGN[normalized_sign]:
        if start_degree <= normalized_degree < end_degree:
            return {
                "bound_lord": lord,
                "bound_lord_label": planet_label(lord),
                "segment_start_degree": round(start_degree, 4),
                "segment_end_degree": round(end_degree, 4),
            }
    fallback_lord, start_degree, end_degree = EGYPTIAN_BOUNDS_BY_SIGN[normalized_sign][
        -1
    ]
    return {
        "bound_lord": fallback_lord,
        "bound_lord_label": planet_label(fallback_lord),
        "segment_start_degree": round(start_degree, 4),
        "segment_end_degree": round(end_degree, 4),
    }


def planet_label(planet_name: str) -> str:
    return PLANET_LABELS.get(planet_name, planet_name)


def house_number(house_name: Optional[str]) -> Optional[int]:
    if house_name is None:
        return None
    return HOUSE_NAME_TO_NUMBER.get(house_name)


def house_label(house_name: Optional[str]) -> Optional[str]:
    number = house_number(house_name)
    if number is None:
        return None
    return f"第{number}宫"


def point_attribute_name(point_name: str) -> str:
    return POINT_ATTRIBUTE_NAMES.get(point_name, point_name.lower())


def point_absolute_position(subject: Any, point_name: str) -> float:
    point = getattr(subject, point_attribute_name(point_name))
    return float(point.abs_pos)


def point_to_dict(point_name: str, point: Any) -> Dict[str, Any]:
    sign_name = normalize_sign_name(getattr(point, "sign", ""))
    house_name = getattr(point, "house", None)
    return {
        "point": point_name,
        "point_label": planet_label(point_name),
        "sign": sign_name,
        "sign_label": sign_label(sign_name),
        "degree": float(getattr(point, "position", 0.0)),
        "absolute_degree": float(getattr(point, "abs_pos", 0.0)),
        "longitude": float(getattr(point, "abs_pos", 0.0)),
        "house": house_number(house_name),
        "house_label": house_label(house_name),
        "retrograde": bool(getattr(point, "retrograde", False)),
    }


def longitude_to_point_dict(point_name: str, absolute_degree: float) -> Dict[str, Any]:
    normalized_degree = normalize_angle(absolute_degree)
    sign_index = int(normalized_degree // 30)
    sign_name = SIGNS[sign_index]
    return {
        "point": point_name,
        "point_label": planet_label(point_name),
        "sign": sign_name,
        "sign_label": sign_label(sign_name),
        "degree": normalized_degree % 30,
        "absolute_degree": normalized_degree,
        "longitude": normalized_degree,
    }


def next_sign(sign_name: str) -> str:
    return SIGNS[(SIGNS.index(sign_name) + 1) % 12]


def opposite_sign(sign_name: str) -> str:
    return SIGNS[(SIGNS.index(sign_name) + 6) % 12]


def classify_releasing_phase(sign_name: str, root_sign: str) -> Dict[str, Any]:
    relative_index = ((SIGNS.index(sign_name) - SIGNS.index(root_sign)) % 12) + 1
    if relative_index in {1, 4, 7, 10}:
        phase = "angular"
    elif relative_index in {2, 5, 8, 11}:
        phase = "succedent"
    else:
        phase = "cadent"
    return {
        "relative_sign_index": relative_index,
        "phase": phase,
        "phase_label": ZR_PHASE_LABELS[phase],
        "is_peak_period": phase == "angular",
    }


def whole_sign_house_from_asc(asc_sign: str, target_sign: str) -> int:
    return ((SIGNS.index(target_sign) - SIGNS.index(asc_sign)) % 12) + 1


def build_lot_point_dict(
    lot_key: str,
    absolute_degree: float,
    *,
    asc_sign: str,
) -> Dict[str, Any]:
    point_name = LOT_POINT_NAMES[lot_key]
    payload = longitude_to_point_dict(point_name, absolute_degree)
    sign_name = payload["sign"]
    house = whole_sign_house_from_asc(asc_sign, sign_name)
    payload.update(
        {
            "lot": lot_key,
            "lot_label": LOT_LABELS[lot_key],
            "house": house,
            "house_label": f"第{house}宫",
        }
    )
    return payload


def build_lot_payloads(natal_subject: Any) -> Dict[str, Dict[str, Any]]:
    asc_sign = normalize_sign_name(natal_subject.ascendant.sign)
    sect = determine_sect(natal_subject)
    sun_longitude = point_absolute_position(natal_subject, "Sun")
    moon_longitude = point_absolute_position(natal_subject, "Moon")
    asc_longitude = point_absolute_position(natal_subject, "Ascendant")
    if sect == "day":
        fortune_longitude = combine_longitudes(
            asc_longitude, moon_longitude, -sun_longitude
        )
        spirit_longitude = combine_longitudes(
            asc_longitude, sun_longitude, -moon_longitude
        )
    else:
        fortune_longitude = combine_longitudes(
            asc_longitude, sun_longitude, -moon_longitude
        )
        spirit_longitude = combine_longitudes(
            asc_longitude, moon_longitude, -sun_longitude
        )
    return {
        "lot_of_fortune": build_lot_point_dict(
            "lot_of_fortune",
            fortune_longitude,
            asc_sign=asc_sign,
        ),
        "lot_of_spirit": build_lot_point_dict(
            "lot_of_spirit",
            spirit_longitude,
            asc_sign=asc_sign,
        ),
    }


def build_subject(
    *,
    name: str,
    local_datetime: datetime | None = None,
    longitude: float,
    latitude: float,
    timezone_name: str,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    physical_epoch: PhysicalEpoch | None = None,
) -> Any:
    ensure_predictive_backend_available()
    from .native_chart import build_native_subject

    return build_native_subject(
        name=name,
        local_datetime=local_datetime,
        longitude=longitude,
        latitude=latitude,
        timezone_name=timezone_name,
        house_system=house_system,
        zodiac_type=zodiac_type,
        physical_epoch=physical_epoch,
    )


def build_natal_subject(
    birth_info: AstroBirthInfo,
    *,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
) -> Any:
    require_resolved_birth_timezone(birth_info.timezone_source)
    return build_subject(
        name=birth_info.name,
        local_datetime=birth_info.local_datetime,
        longitude=birth_info.longitude,
        latitude=birth_info.latitude,
        timezone_name=birth_info.timezone,
        house_system=house_system,
        zodiac_type=zodiac_type,
    )


def determine_sect(subject: Any) -> str:
    from .native_chart import NativeSubject

    if isinstance(subject, NativeSubject):
        # Native charts already used the physical TT Sun and UT1 horizon.
        # Re-parsing a UTC display string would reject inserted second60.
        return "day" if subject.is_diurnal else "night"
    # Kerykeion's Sun in whole-sign house 1/7 is not a physical horizon test.
    # Fetch tropical coordinates even when the subject uses a sidereal zodiac.
    times = ephemeris_time(datetime.fromisoformat(subject.iso_formatted_utc_datetime))
    coordinates, retflag = ephemeris_call("calc", times.jd_tt, swe.SUN, swe.FLG_SWIEPH)
    if retflag < 0:
        raise ValueError("Cannot determine sect: solar ephemeris failed")
    altitude, _ = horizon_altitude(
        times.jd_ut1,
        subject.lng,
        subject.lat,
        float(coordinates[0]),
        float(coordinates[1]),
    )
    return "day" if altitude >= 0.0 else "night"


def sect_label(sect: str) -> str:
    return "日盘" if sect == "day" else "夜盘"


def calculate_age_years(
    birth_info: AstroBirthInfo,
    analysis_datetime: datetime,
) -> float:
    birth_utc = birth_info.require_utc_datetime
    analysis_utc = analysis_datetime.astimezone(parse_timezone_name("UTC"))
    delta = analysis_utc - birth_utc
    return delta.total_seconds() / (TROPICAL_YEAR_DAYS * 86400.0)


def calculate_age_years_int(
    birth_info: AstroBirthInfo,
    analysis_datetime: datetime,
) -> int:
    years = analysis_datetime.year - birth_info.local_datetime.year
    birthday_this_year = resolve_local_birthday_anniversary(
        birth_info.local_datetime,
        analysis_datetime.year,
        tzinfo=analysis_datetime.tzinfo,
    )
    if analysis_datetime < birthday_this_year:
        years -= 1
    return years


def extract_reference_points(subject: Any) -> Dict[str, Dict[str, Any]]:
    return extract_named_points(subject, TIMING_POINT_NAMES)


def extract_named_points(
    subject: Any,
    point_names: List[str],
) -> Dict[str, Dict[str, Any]]:
    result = {}
    for point_name in point_names:
        result[point_name.lower()] = point_to_dict(
            point_name,
            getattr(subject, point_attribute_name(point_name)),
        )
    return result


def extract_reference_longitudes(subject: Any) -> Dict[str, float]:
    return extract_named_longitudes(subject, TIMING_POINT_NAMES)


def extract_named_longitudes(
    subject: Any,
    point_names: List[str],
) -> Dict[str, float]:
    return {
        point_name: point_absolute_position(subject, point_name)
        for point_name in point_names
    }


def collect_aspect_hits(
    *,
    source_longitudes: Mapping[str, Angle],
    target_longitudes: Mapping[str, Angle],
    orb_limit: float = 1.5,
) -> List[Dict[str, Any]]:
    if not math.isfinite(orb_limit) or not 0 <= orb_limit <= 180:
        raise ValueError("Aspect orb must be finite and within 0..180 degrees")
    limit = Fraction(orb_limit)
    hits = []
    for source_name, source_longitude in source_longitudes.items():
        for target_name, target_longitude in target_longitudes.items():
            difference = angular_separation_fraction(source_longitude, target_longitude)
            for aspect_key, aspect_label_text, aspect_degree in ASPECT_DEGREES:
                orb = abs(difference - Fraction(aspect_degree))
                if orb <= limit:
                    hits.append(
                        (
                            orb,
                            {
                                "source": source_name,
                                "source_label": planet_label(source_name),
                                "target": target_name,
                                "target_label": planet_label(target_name),
                                "aspect": aspect_key,
                                "aspect_label": aspect_label_text,
                                "orb": float(orb),
                            },
                        )
                    )
    hits.sort(key=lambda item: item[0])
    return [row for _, row in hits]


def normalize_signed_angle(angle: float) -> float:
    normalized = normalize_angle(angle)
    if normalized >= 180.0:
        normalized -= 360.0
    return normalized
