"""菲尔达利亚时主（Firdaria）推运法。"""

from __future__ import annotations

from datetime import datetime, timedelta
from fractions import Fraction
from itertools import cycle
from typing import Any

from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.predictive._common import (
    TROPICAL_YEAR_DAYS,
    determine_sect,
    planet_label,
    resolve_local_birthday_anniversary,
    sect_label,
)
from fatebridge.utils.civil_time import UTCCalendar, ZonedCalendar, utc_calendar
from fatebridge.utils.timezones import format_local_time_or_utc, validate_local_clock

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


def _validate_calendar_clock(moment: datetime, role: str) -> None:
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(f"法达公历周年模式的{role}必须带时区")
    validate_local_clock(moment, clock_label=f"法达公历周年模式的{role}")


def validate_calendar_firdaria_inputs(
    birth_info: AstroBirthInfo, analysis_datetime: datetime
) -> None:
    """Reject ambiguous clocks before the natal backend can silently resolve them."""
    _validate_calendar_clock(birth_info.local_datetime, "出生钟时")
    _validate_calendar_clock(analysis_datetime, "分析钟时")
    if utc_calendar(analysis_datetime) < birth_info.utc_calendar:
        raise ValueError("法达公历周年模式的分析时刻不能早于出生时刻")


def _calendar_anniversary(birth: datetime, nominal_age: int) -> datetime:
    # The shared anniversary helper clamps Feb 29 without losing the birth anchor.
    moment = resolve_local_birthday_anniversary(birth, birth.year + nominal_age)
    _validate_calendar_clock(moment, f"{nominal_age} 岁周年边界")
    return moment


def _calendar_period(start: datetime, end: datetime, planet: str) -> dict[str, Any]:
    return {
        "planet": planet,
        "planet_label": planet_label(planet),
        "start": format_local_time_or_utc(start),
        "end": format_local_time_or_utc(end),
        "start_display": format_local_time_or_utc(start, sep=" ", timespec="minutes"),
        "end_display": format_local_time_or_utc(end, sep=" ", timespec="minutes"),
    }


def _build_calendar_payload(
    birth_info: AstroBirthInfo,
    sequence: list[tuple[str, int]],
    sect: str,
    analysis_datetime: datetime,
    *,
    include_full_timelines: bool = True,
) -> dict[str, Any]:
    validate_calendar_firdaria_inputs(birth_info, analysis_datetime)
    birth = birth_info.local_datetime
    clock = ZonedCalendar.from_datetime(birth)
    target = utc_calendar(analysis_datetime)
    horizon = target.shifted(timedelta(days=90 * TROPICAL_YEAR_DAYS))
    microsecond = timedelta(microseconds=1)
    planet_order = [planet for planet, _ in sequence if "Node" not in planet]
    timeline: list[dict[str, Any]] = []
    current_major = None
    current_sub = None
    age = 0
    start, start_utc = birth, clock.utc

    for planet, years in cycle(sequence):
        if start_utc > horizon or (
            start_utc > target and (not include_full_timelines or len(timeline) >= 12)
        ):
            break
        end_age = age + years
        if birth.year + end_age > datetime.max.year:
            # Earlier preview periods and the current period are already complete.
            if start_utc > target and (
                not include_full_timelines or len(timeline) >= 12
            ):
                break
            raise ValueError(
                "Civil calendar label is outside Python datetime's year range"
            )
        end = _calendar_anniversary(birth, end_age)
        end_utc = utc_calendar(end)
        current = start_utc <= target < end_utc
        in_preview = include_full_timelines and len(timeline) < 12
        if not (current or in_preview):
            start, start_utc, age = end, end_utc, end_age
            continue
        major = {
            **_calendar_period(start, end, planet),
            "years": years,
            "nominal_start_age": age,
            "nominal_end_age": end_age,
            "subperiods": [],
        }
        if "Node" not in planet:
            index = planet_order.index(planet)
            order = planet_order[index:] + planet_order[:index]
            ticks = end_utc.elapsed_since(start_utc) // microsecond
            boundaries = [
                start_utc.shifted(round(Fraction(ticks * k, 7)) * microsecond)
                for k in range(8)
            ]
            for k, sub_planet in enumerate(order):
                sub = _calendar_period(
                    ZonedCalendar(boundaries[k], clock.zone).require_datetime(),
                    ZonedCalendar(boundaries[k + 1], clock.zone).require_datetime(),
                    sub_planet,
                )
                major["subperiods"].append(sub)
                if boundaries[k] <= target < boundaries[k + 1]:
                    current_sub = sub
        if current:
            current_major = major
        if in_preview:
            timeline.append(major)
        start, start_utc, age = end, end_utc, end_age

    payload: dict[str, Any] = {
        "sect": sect,
        "sect_label": sect_label(sect),
        "current_major": current_major,
        "current_sub": current_sub,
    }
    if include_full_timelines:
        payload["timeline"] = timeline
    return payload


def build_firdaria_payload(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    analysis_datetime: datetime,
    firdaria_night_order: str = "nodes_at_end",
    firdaria_year_basis: str = "fixed_365_2425",
    include_full_timelines: bool = True,
) -> dict[str, Any]:
    return build_firdaria_for_sect(
        birth_info,
        determine_sect(natal_subject),
        analysis_datetime=analysis_datetime,
        firdaria_night_order=firdaria_night_order,
        firdaria_year_basis=firdaria_year_basis,
        include_full_timelines=include_full_timelines,
    )


def build_firdaria_for_sect(
    birth_info: AstroBirthInfo,
    sect: str,
    *,
    analysis_datetime: datetime,
    firdaria_night_order: str = "nodes_at_end",
    firdaria_year_basis: str = "fixed_365_2425",
    include_full_timelines: bool = True,
) -> dict[str, Any]:
    """Calendar arithmetic with an explicit sect; no surrogate natal houses."""
    if sect not in {"day", "night"}:
        raise ValueError("法达计算需要明确的 day／night 宗派")
    if firdaria_night_order not in {"nodes_at_end", "nodes_after_mars"}:
        raise ValueError("无效的 firdaria_night_order")
    if firdaria_year_basis not in {"fixed_365_2425", "calendar_anniversary"}:
        raise ValueError("无效的 firdaria_year_basis")
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
        result = _build_calendar_payload(
            birth_info,
            sequence,
            sect,
            analysis_datetime,
            include_full_timelines=include_full_timelines,
        )
    else:
        result = _build_fixed_year_payload(
            birth_info,
            sequence,
            sect,
            analysis_datetime,
            include_full_timelines=include_full_timelines,
        )
    result["calculation_options"] = {
        "night_order": firdaria_night_order,
        "year_basis": firdaria_year_basis,
        "subperiod_basis": "utc_elapsed",
        "timezone": birth_info.timezone,
    }
    return result


def _build_fixed_year_payload(
    birth_info: AstroBirthInfo,
    sequence: list[tuple[str, int]],
    sect: str,
    analysis_datetime: datetime,
    *,
    include_full_timelines: bool = True,
) -> dict[str, Any]:
    """Fixed nominal days on UTC elapsed time, displayed in the birth timezone."""
    display_zone = ZonedCalendar.from_datetime(birth_info.local_datetime).zone

    def label(point: UTCCalendar) -> str:
        return format_local_time_or_utc(
            ZonedCalendar(point, display_zone).require_datetime()
        )

    sub_planet_order = [planet for planet, _ in sequence if "Node" not in planet]
    timeline: list[dict[str, Any]] = []
    cursor = birth_info.utc_calendar
    target = utc_calendar(analysis_datetime)
    horizon = target.shifted(timedelta(days=90 * TROPICAL_YEAR_DAYS))
    current_major = None
    current_sub = None

    for planet, years in cycle(sequence):
        if cursor > horizon or (
            cursor > target and (not include_full_timelines or len(timeline) == 12)
        ):
            break
        start = cursor
        duration = timedelta(days=years * TROPICAL_YEAR_DAYS)
        cursor = start.shifted(duration)
        current = start <= target < cursor
        in_preview = include_full_timelines and len(timeline) < 12
        if not (current or in_preview):
            continue

        main_period: dict[str, Any] = {
            "planet": planet,
            "planet_label": planet_label(planet),
            "start": label(start),
            "end": label(cursor),
            "years": years,
            "subperiods": [],
        }
        if "Node" not in planet:
            index = sub_planet_order.index(planet)
            order = sub_planet_order[index:] + sub_planet_order[:index]
            sub_duration = duration / 7
            sub_cursor = start
            for sub_planet in order:
                sub_end = sub_cursor.shifted(sub_duration)
                sub_period = {
                    "planet": sub_planet,
                    "planet_label": planet_label(sub_planet),
                    "start": label(sub_cursor),
                    "end": label(sub_end),
                }
                main_period["subperiods"].append(sub_period)
                if sub_cursor <= target < sub_end:
                    current_sub = sub_period
                sub_cursor = sub_end

        if current:
            current_major = main_period
        if in_preview:
            timeline.append(main_period)

    payload: dict[str, Any] = {
        "sect": sect,
        "sect_label": sect_label(sect),
        "current_major": current_major,
        "current_sub": current_sub,
    }
    if include_full_timelines:
        payload["timeline"] = timeline
    return payload
