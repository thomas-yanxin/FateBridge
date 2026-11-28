"""西占推运共享常量与跨技法计算函数。"""

from __future__ import annotations

import math
from calendar import monthrange
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from datetime import tzinfo as DateTimeZone
from fractions import Fraction
from typing import Any, Literal

from fatebridge.core.astro.angle_definitions import is_ascendant_resolved
from fatebridge.core.astro.astrology_tables import (
    EGYPTIAN_BOUNDS_BY_SIGN as EGYPTIAN_BOUNDS_BY_SIGN,
)
from fatebridge.core.astro.astrology_tables import SIGNS
from fatebridge.core.astro.birth import (
    AstroBirthInfo,
    build_astro_birth_info,
    require_resolved_birth_timezone,
)
from fatebridge.core.astro.event_reference import ASC_INDEPENDENT_HOUSES
from fatebridge.core.astro.geometry import (
    Angle,
    combine_longitudes_exact,
    longitude_float,
    normalize_angle,
)
from fatebridge.core.astro.native_chart import (
    NativeSubject,
    build_native_subject,
)
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.western_points import (
    ASPECT_DEGREE_TO_META as ASPECT_DEGREE_TO_META,
)
from fatebridge.core.astro.western_points import ASPECT_DEGREES as ASPECT_DEGREES
from fatebridge.core.astro.western_points import (
    HOUSE_NAME_TO_NUMBER as HOUSE_NAME_TO_NUMBER,
)
from fatebridge.core.astro.western_points import PLANET_LABELS as PLANET_LABELS
from fatebridge.core.astro.western_points import (
    POINT_ATTRIBUTE_NAMES as POINT_ATTRIBUTE_NAMES,
)
from fatebridge.core.astro.western_points import (
    SIGN_ABBREVIATIONS as SIGN_ABBREVIATIONS,
)
from fatebridge.core.astro.western_points import (
    SWISSEPH_PLANET_IDS as SWISSEPH_PLANET_IDS,
)
from fatebridge.core.astro.western_points import (
    TIMING_POINT_NAMES as TIMING_POINT_NAMES,
)
from fatebridge.core.astro.western_points import (
    TRANSIT_POINT_NAMES as TRANSIT_POINT_NAMES,
)
from fatebridge.core.astro.western_points import (
    collect_aspect_hits as collect_aspect_hits,
)
from fatebridge.core.astro.western_points import house_label as house_label
from fatebridge.core.astro.western_points import house_number as house_number
from fatebridge.core.astro.western_points import (
    longitude_to_point_dict as longitude_to_point_dict,
)
from fatebridge.core.astro.western_points import (
    normalize_sign_name as normalize_sign_name,
)
from fatebridge.core.astro.western_points import planet_label as planet_label
from fatebridge.core.astro.western_points import (
    point_absolute_position as point_absolute_position,
)
from fatebridge.core.astro.western_points import (
    point_attribute_name as point_attribute_name,
)
from fatebridge.core.astro.western_points import point_to_dict as point_to_dict
from fatebridge.core.astro.western_points import (
    resolve_egyptian_bound as resolve_egyptian_bound,
)
from fatebridge.core.astro.western_points import sign_label as sign_label
from fatebridge.core.astro.western_points import (
    source_arc_positions as source_arc_positions,
)
from fatebridge.core.ephemeris_runtime import swe
from fatebridge.core.execution_context import current_datetime
from fatebridge.utils.civil_time import ZonedCalendar, utc_calendar
from fatebridge.utils.timezones import (
    parse_timezone_name,
    require_defined_gap_offsets,
    validate_local_clock,
)

TROPICAL_YEAR_DAYS = 365.2425

LOT_LABELS = {
    "lot_of_fortune": "幸运点",
    "lot_of_spirit": "精神点",
    "lot_of_eros": "爱神点",
}
LOT_POINT_NAMES = {
    "lot_of_fortune": "Fortune",
    "lot_of_spirit": "Spirit",
    "lot_of_eros": "Eros",
}
LOT_KEY_BY_POINT_NAME = {value: key for key, value in LOT_POINT_NAMES.items()}
ZR_PHASE_LABELS = {
    "angular": "角宫",
    "succedent": "续宫",
    "cadent": "衰宫",
}


def ensure_predictive_backend_available() -> None:
    if swe is None:
        raise ModuleNotFoundError("Swiss Ephemeris 未安装，无法启用西占推运能力。")


def build_predictive_birth_info(
    *,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int,
    birth_longitude: float,
    birth_latitude: float,
    birth_minute: int = 0,
    birth_timezone: str | None = None,
    name: str | None = None,
    birth_place: str | None = None,
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
    analysis_year: int | None = None,
    analysis_month: int | None = None,
    analysis_day: int | None = None,
    analysis_hour: int | None = None,
    analysis_minute: int | None = None,
) -> datetime:
    """Resolve the target clock independently of the natal clock.

    Date-only callers retain the natal hour/minute. Each explicit clock part
    overrides that fallback, including zero; dates still use the call clock
    for missing components. The wall clock is interpreted in birth_timezone.
    """
    timezone_name = birth_info.timezone
    tzinfo = parse_timezone_name(timezone_name)
    year, month, day = analysis_year, analysis_month, analysis_day
    if year is None or month is None or day is None:
        now = current_datetime(tzinfo, timezone_name, now_provider=datetime.now)
        year = now.year if year is None else year
        month = now.month if month is None else month
        if day is None:
            day = min(now.day, monthrange(year, month)[1])
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
    validate_local_clock(target, clock_label="分析钟时")
    return target


def resolve_local_birthday_anniversary(
    birth_local_datetime: datetime,
    target_year: int,
    *,
    tzinfo: DateTimeZone | None = None,
    clock_policy: Literal["preserve_wall", "compatible"] = "preserve_wall",
) -> datetime:
    """Reconstruct the original birthday; callers select generated-clock policy.

    Strict calendar Firdaria validates the preserved wall clock itself.
    Profections use Temporal-compatible generated anniversaries: earlier on
    backward transitions, forward by the gap on forward transitions.
    """
    target_day = min(
        birth_local_datetime.day,
        monthrange(target_year, birth_local_datetime.month)[1],
    )
    moment = datetime(
        target_year,
        birth_local_datetime.month,
        target_day,
        birth_local_datetime.hour,
        birth_local_datetime.minute,
        birth_local_datetime.second,
        birth_local_datetime.microsecond,
        tzinfo=tzinfo or birth_local_datetime.tzinfo,
    )
    if clock_policy == "compatible":
        require_defined_gap_offsets(moment, clock_label="计算所得的周年钟时")
        moment = ZonedCalendar.from_datetime(moment).require_datetime()
        validate_local_clock(
            moment, allow_ambiguous=True, clock_label="计算所得的周年钟时"
        )
    return moment


@dataclass(frozen=True)
class BirthdayAnniversary:
    analysis_datetime: datetime
    nominal_year: int
    start: datetime


def resolve_last_birthday(
    birth_info: AstroBirthInfo, *, analysis_datetime: datetime
) -> BirthdayAnniversary:
    """Locate the anniversary by exact instant and retain its nominal year.

    A date-line gap can move a December anniversary into January, so the
    displayed year cannot be used to choose the next birthday or the age.
    """
    analysis_utc = utc_calendar(analysis_datetime)
    if analysis_utc < birth_info.utc_calendar:
        raise ValueError("分析时刻不能早于出生时刻。")
    zone = parse_timezone_name(birth_info.timezone)
    analysis_local = ZonedCalendar(analysis_utc, zone).require_datetime()
    birth_local = birth_info.local_datetime
    nominal_year = analysis_local.year
    anniversary = resolve_local_birthday_anniversary(
        birth_info.local_datetime,
        nominal_year,
        tzinfo=analysis_local.tzinfo,
        clock_policy="compatible",
    )
    while analysis_utc < utc_calendar(anniversary):
        nominal_year -= 1
        anniversary = resolve_local_birthday_anniversary(
            birth_info.local_datetime,
            nominal_year,
            tzinfo=analysis_local.tzinfo,
            clock_policy="compatible",
        )
    return BirthdayAnniversary(
        analysis_local,
        nominal_year,
        birth_local if nominal_year == birth_local.year else anniversary,
    )


def next_sign(sign_name: str) -> str:
    return SIGNS[(SIGNS.index(sign_name) + 1) % 12]


def opposite_sign(sign_name: str) -> str:
    return SIGNS[(SIGNS.index(sign_name) + 6) % 12]


def classify_releasing_phase(sign_name: str, fortune_sign: str) -> dict[str, Any]:
    relative_index = ((SIGNS.index(sign_name) - SIGNS.index(fortune_sign)) % 12) + 1
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
    absolute_degree: Angle,
    *,
    asc_sign: str,
) -> dict[str, Any]:
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


def build_lot_longitudes(natal_subject: NativeSubject) -> dict[str, Fraction]:
    if not is_ascendant_resolved(natal_subject):
        return {}
    sun = point_absolute_position(natal_subject, "Sun")
    moon = point_absolute_position(natal_subject, "Moon")
    venus = point_absolute_position(natal_subject, "Venus")
    asc = point_absolute_position(natal_subject, "Ascendant")
    is_day = determine_sect(natal_subject) == "day"
    added, subtracted = (moon, sun) if is_day else (sun, moon)
    fortune = combine_longitudes_exact(asc, added, -subtracted)
    spirit = combine_longitudes_exact(asc, subtracted, -added)
    eros = (
        combine_longitudes_exact(asc, venus, -spirit)
        if is_day
        else combine_longitudes_exact(asc, spirit, -venus)
    )
    return {
        "lot_of_fortune": fortune,
        "lot_of_spirit": spirit,
        "lot_of_eros": eros,
    }


def build_lot_payloads(natal_subject: NativeSubject) -> dict[str, dict[str, Any]]:
    asc_sign = normalize_sign_name(natal_subject.ascendant.sign)
    return {
        lot_key: build_lot_point_dict(
            lot_key, longitude_float(longitude), asc_sign=asc_sign
        )
        for lot_key, longitude in build_lot_longitudes(natal_subject).items()
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
    high_latitude_fallback: str = "error",
) -> NativeSubject:
    ensure_predictive_backend_available()

    return build_native_subject(
        name=name,
        local_datetime=local_datetime,
        longitude=longitude,
        latitude=latitude,
        timezone_name=timezone_name,
        house_system=house_system,
        zodiac_type=zodiac_type,
        physical_epoch=physical_epoch,
        high_latitude_fallback=high_latitude_fallback,
    )


def build_natal_subject(
    birth_info: AstroBirthInfo,
    *,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    high_latitude_fallback: str = "error",
) -> NativeSubject:
    require_resolved_birth_timezone(birth_info.timezone_source)
    return build_subject(
        name=birth_info.name,
        local_datetime=(
            birth_info.local_datetime if birth_info.native_epoch is None else None
        ),
        longitude=birth_info.longitude,
        latitude=birth_info.latitude,
        timezone_name=birth_info.timezone,
        house_system=house_system,
        zodiac_type=zodiac_type,
        physical_epoch=birth_info.native_epoch,
        high_latitude_fallback=high_latitude_fallback,
    )


def determine_sect(subject: NativeSubject) -> str:
    return "day" if subject.is_diurnal else "night"


def sect_label(sect: str) -> str:
    return "日盘" if sect == "day" else "夜盘"


def calculate_age_years(
    birth_info: AstroBirthInfo,
    analysis_datetime: datetime,
) -> float:
    delta = utc_calendar(analysis_datetime).elapsed_since(birth_info.utc_calendar)
    return delta.total_seconds() / (TROPICAL_YEAR_DAYS * 86400.0)


def extract_reference_points(subject: NativeSubject) -> dict[str, dict[str, Any]]:
    return extract_named_points(subject, TIMING_POINT_NAMES)


def extract_named_points(
    subject: NativeSubject,
    point_names: list[str],
) -> dict[str, dict[str, Any]]:
    ascendant_resolved = is_ascendant_resolved(subject)
    houses_resolved = ascendant_resolved or (
        subject.houses_system_identifier in ASC_INDEPENDENT_HOUSES
    )
    result = {}
    for point_name in point_names:
        point = point_to_dict(
            point_name, getattr(subject, point_attribute_name(point_name))
        )
        if point_name == "Ascendant" and not ascendant_resolved:
            point = {
                key: value if key in {"point", "point_label"} else None
                for key, value in point.items()
            }
            point["status"] = "underdetermined_ascendant"
        elif not houses_resolved:
            point.update(house=None, house_label=None)
        result[point_name.lower()] = point
    return result


def extract_reference_longitudes(subject: NativeSubject) -> dict[str, float]:
    return extract_named_longitudes(subject, TIMING_POINT_NAMES)


def extract_named_longitudes(
    subject: NativeSubject,
    point_names: list[str],
) -> dict[str, float]:
    ascendant_resolved = is_ascendant_resolved(subject)
    return {
        point_name: point_absolute_position(subject, point_name)
        for point_name in point_names
        if ascendant_resolved or point_name != "Ascendant"
    }


def normalize_signed_angle(angle: float) -> float:
    normalized = normalize_angle(angle)
    if normalized >= 180.0:
        normalized -= 360.0
    return normalized
