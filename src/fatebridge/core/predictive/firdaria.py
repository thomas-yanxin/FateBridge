"""菲尔达利亚时主（Firdaria）推运法。"""

from __future__ import annotations

from dataclasses import replace
from datetime import timezone
from fractions import Fraction
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil import tz

from ._common import (
    TROPICAL_YEAR_DAYS,
    Any,
    AstroBirthInfo,
    Dict,
    datetime,
    determine_sect,
    planet_label,
    resolve_local_birthday_anniversary,
    sect_label,
    timedelta,
)

# 日盘与夜盘的行星时主顺序（planet, years）
FIRDARIA_DAY_SEQUENCE = [
    ("Sun", 10),
    ("Venus", 8),
    ("Mercury", 13),
    ("Moon", 9),
    ("Saturn", 11),
    ("Jupiter", 12),
    ("Mars", 7),
    ("North Node", 3),
    ("South Node", 2),
]
FIRDARIA_NIGHT_SEQUENCE = [
    ("Moon", 9),
    ("Saturn", 11),
    ("Jupiter", 12),
    ("Mars", 7),
    ("Sun", 10),
    ("Venus", 8),
    ("Mercury", 13),
    ("North Node", 3),
    ("South Node", 2),
]
FIRDARIA_NIGHT_NODES_AFTER_MARS_SEQUENCE = [
    *FIRDARIA_NIGHT_SEQUENCE[:4],
    *FIRDARIA_NIGHT_SEQUENCE[-2:],
    *FIRDARIA_NIGHT_SEQUENCE[4:-2],
]


def normalize_calendar_firdaria_birth(birth_info: AstroBirthInfo) -> AstroBirthInfo:
    """Use IANA recurrence rules beyond TZif's last explicit DST transition.

    Keep this opt-in: legacy arithmetic must retain its original timezone object.
    Fixed-offset spellings are already normalized by the shared birth builder.
    """
    try:
        zone = ZoneInfo(birth_info.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return birth_info
    local = birth_info.local_datetime.replace(tzinfo=zone)
    return replace(
        birth_info,
        local_datetime=local,
        utc_datetime=local.astimezone(timezone.utc),
    )


def _validate_calendar_clock(moment: datetime, role: str) -> None:
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(f"法达公历周年模式的{role}必须带时区")
    if not tz.datetime_exists(moment):
        raise ValueError(
            f"法达公历周年模式的{role}为 nonexistent local time，请确认有效钟时"
        )
    if tz.datetime_ambiguous(moment):
        raise ValueError(
            f"法达公历周年模式的{role}为 ambiguous local time，请确认明确偏移"
        )


def validate_calendar_firdaria_inputs(
    birth_info: AstroBirthInfo, analysis_datetime: datetime
) -> None:
    """Reject ambiguous clocks before the natal backend can silently resolve them."""
    _validate_calendar_clock(birth_info.local_datetime, "出生钟时")
    _validate_calendar_clock(analysis_datetime, "分析钟时")
    if analysis_datetime.astimezone(timezone.utc) < birth_info.utc_datetime:
        raise ValueError("法达公历周年模式的分析时刻不能早于出生时刻")


def _calendar_anniversary(birth: datetime, nominal_age: int) -> datetime:
    # The shared anniversary helper clamps Feb 29 without losing the birth anchor.
    moment = resolve_local_birthday_anniversary(birth, birth.year + nominal_age)
    _validate_calendar_clock(moment, f"{nominal_age} 岁周年边界")
    return moment


def _calendar_period(start: datetime, end: datetime, planet: str) -> Dict[str, Any]:
    return {
        "planet": planet,
        "planet_label": planet_label(planet),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "start_display": start.isoformat(sep=" ", timespec="minutes"),
        "end_display": end.isoformat(sep=" ", timespec="minutes"),
    }


def _build_calendar_payload(
    birth_info: AstroBirthInfo,
    sequence: list[tuple[str, int]],
    sect: str,
    analysis_datetime: datetime,
) -> Dict[str, Any]:
    birth_info = normalize_calendar_firdaria_birth(birth_info)
    validate_calendar_firdaria_inputs(birth_info, analysis_datetime)
    birth = birth_info.local_datetime
    target = analysis_datetime.astimezone(timezone.utc)
    horizon = target + timedelta(days=90 * TROPICAL_YEAR_DAYS)
    microsecond = timedelta(microseconds=1)
    planet_order = [planet for planet, _ in sequence if "Node" not in planet]
    timeline = []
    current_major = None
    current_sub = None
    age = 0
    start = birth

    while start.astimezone(timezone.utc) <= horizon:
        for planet, years in sequence:
            end = _calendar_anniversary(birth, age + years)
            start_utc, end_utc = start.astimezone(timezone.utc), end.astimezone(
                timezone.utc
            )
            major = {
                **_calendar_period(start, end, planet),
                "years": years,
                "nominal_start_age": age,
                "nominal_end_age": age + years,
                "subperiods": [],
            }
            if "Node" not in planet:
                index = planet_order.index(planet)
                order = planet_order[index:] + planet_order[:index]
                ticks = (end_utc - start_utc) // microsecond
                boundaries = [
                    start_utc + round(Fraction(ticks * k, 7)) * microsecond
                    for k in range(8)
                ]
                for k, sub_planet in enumerate(order):
                    sub = _calendar_period(
                        boundaries[k].astimezone(birth.tzinfo),
                        boundaries[k + 1].astimezone(birth.tzinfo),
                        sub_planet,
                    )
                    major["subperiods"].append(sub)
                    if boundaries[k] <= target < boundaries[k + 1]:
                        current_sub = sub
            if start_utc <= target < end_utc:
                current_major = major
            timeline.append(major)
            start, age = end, age + years
            if end_utc > horizon:
                break
        else:
            continue
        break

    return {
        "sect": sect,
        "sect_label": sect_label(sect),
        "current_major": current_major,
        "current_sub": current_sub,
        "timeline": timeline[:12],
    }


def build_firdaria_payload(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    analysis_datetime: datetime,
    firdaria_night_order: str = "nodes_at_end",
    firdaria_year_basis: str = "fixed_365_2425",
) -> Dict[str, Any]:
    if firdaria_night_order not in {"nodes_at_end", "nodes_after_mars"}:
        raise ValueError("无效的 firdaria_night_order")
    if firdaria_year_basis not in {"fixed_365_2425", "calendar_anniversary"}:
        raise ValueError("无效的 firdaria_year_basis")
    sect = determine_sect(natal_subject)
    sequence = (
        FIRDARIA_DAY_SEQUENCE
        if sect == "day"
        else (
            FIRDARIA_NIGHT_SEQUENCE
            if firdaria_night_order == "nodes_at_end"
            else FIRDARIA_NIGHT_NODES_AFTER_MARS_SEQUENCE
        )
    )
    if firdaria_year_basis == "calendar_anniversary":
        result = _build_calendar_payload(birth_info, sequence, sect, analysis_datetime)
    else:
        result = _build_fixed_year_payload(
            birth_info, sequence, sect, analysis_datetime
        )
    # Preserve default payloads, including exported snapshots and business hashes.
    if (firdaria_night_order, firdaria_year_basis) != (
        "nodes_at_end",
        "fixed_365_2425",
    ):
        result["calculation_options"] = {
            "night_order": firdaria_night_order,
            "year_basis": firdaria_year_basis,
            "subperiod_basis": (
                "utc_elapsed"
                if firdaria_year_basis == "calendar_anniversary"
                else "local_wall_time"
            ),
            "timezone": birth_info.timezone,
        }
    return result


def _build_fixed_year_payload(
    birth_info: AstroBirthInfo,
    sequence: list[tuple[str, int]],
    sect: str,
    analysis_datetime: datetime,
) -> Dict[str, Any]:
    """Existing local-wall arithmetic, retained byte-for-byte for default calls."""
    sub_planet_order = [planet for planet, _ in sequence if "Node" not in planet]

    timeline = []
    cursor = birth_info.local_datetime
    current_major = None
    current_sub = None

    while cursor <= analysis_datetime + timedelta(days=90 * TROPICAL_YEAR_DAYS):
        for planet, years in sequence:
            start = cursor
            end = start + timedelta(days=years * TROPICAL_YEAR_DAYS)
            main_period: Dict[str, Any] = {
                "planet": planet,
                "planet_label": planet_label(planet),
                "start": start.isoformat(),
                "end": end.isoformat(),
                "years": years,
                "subperiods": [],
            }

            if "Node" not in planet:
                order = (
                    sub_planet_order[sub_planet_order.index(planet) :]
                    + sub_planet_order[: sub_planet_order.index(planet)]
                )
                sub_years = years / 7.0
                sub_cursor = start
                for sub_planet in order:
                    sub_end = sub_cursor + timedelta(
                        days=sub_years * TROPICAL_YEAR_DAYS
                    )
                    sub_period = {
                        "planet": sub_planet,
                        "planet_label": planet_label(sub_planet),
                        "start": sub_cursor.isoformat(),
                        "end": sub_end.isoformat(),
                    }
                    main_period["subperiods"].append(sub_period)
                    if sub_cursor <= analysis_datetime < sub_end:
                        current_sub = sub_period
                    sub_cursor = sub_end

            if start <= analysis_datetime < end:
                current_major = main_period

            timeline.append(main_period)
            cursor = end
            if cursor > analysis_datetime + timedelta(days=90 * TROPICAL_YEAR_DAYS):
                break
        else:
            continue
        break

    return {
        "sect": sect,
        "sect_label": sect_label(sect),
        "current_major": current_major,
        "current_sub": current_sub,
        "timeline": timeline[:12],
    }
