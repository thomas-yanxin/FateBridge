"""Decennials: schematic months and exact proportional subdivisions.

Valens VI.5–7 and IX transmit different subdivisions and inconsistent tables.
This module implements the explicitly declared proportional reconstruction,
also used by Morinus, rather than claiming to reproduce every textual variant.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, tzinfo
from fractions import Fraction
from typing import TypedDict

from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.predictive._common import (
    determine_sect,
    planet_label,
    point_absolute_position,
)
from fatebridge.core.predictive.native_chart import NativeSubject
from fatebridge.utils.civil_time import UTCCalendar, ZonedCalendar, utc_calendar
from fatebridge.utils.timezones import format_local_time_or_utc

DECENNIAL_START_MODE_SECT_LIGHT = "sect_light"
DECENNIAL_ORDER_ZODIACAL = "zodiacal"
DECENNIAL_ORDER_CHALDEAN = "chaldean"
DECENNIAL_DAY_METHOD_VALENS = "valens"
DECENNIAL_CALENDAR_TRADITIONAL = "calendar_360"
DECENNIAL_CALENDAR_ACTUAL = "calendar_365_25"
DECENNIAL_TRADITIONAL_PLANETS = [
    "Saturn",
    "Jupiter",
    "Mars",
    "Sun",
    "Venus",
    "Mercury",
    "Moon",
]
DECENNIAL_PLANET_BASE_MONTHS = {
    "Saturn": 30,
    "Jupiter": 12,
    "Mars": 15,
    "Sun": 19,
    "Venus": 8,
    "Mercury": 20,
    "Moon": 25,
}
DECENNIAL_TOTAL_BASE_MONTHS = 129
DECENNIAL_TOTAL_L1_DAYS = DECENNIAL_TOTAL_BASE_MONTHS * 30
DECENNIAL_MINUTES_PER_DAY = 1440
DECENNIAL_MINUTES_PER_MONTH = 30 * DECENNIAL_MINUTES_PER_DAY
DECENNIAL_MINUTES_PER_YEAR = 12 * DECENNIAL_MINUTES_PER_MONTH


class DecennialExactOffset(TypedDict):
    numerator: int
    denominator: int


class _DecennialPeriodRequired(TypedDict):
    key: str
    level: int
    planet: str
    planet_label: str
    date: str
    nominal: str
    start: str
    end: str
    active: bool
    start_offset_minutes: int
    end_offset_minutes: int
    start_offset_exact_minutes: DecennialExactOffset
    end_offset_exact_minutes: DecennialExactOffset


class DecennialPeriod(_DecennialPeriodRequired, total=False):
    sublevel: list[DecennialPeriod]


class DecennialCalculationOptions(TypedDict):
    start_mode: str
    order_type: str
    day_method: str
    calendar_type: str
    time_basis: str
    timestamp_rounding: str
    offset_minutes_rounding: str
    timezone: str


class _DecennialsPayloadRequired(TypedDict):
    resolved_start_planet: str
    resolved_start_planet_label: str
    base_order: list[str]
    current_level_1: DecennialPeriod | None
    current_level_2: DecennialPeriod | None
    current_level_3: DecennialPeriod | None
    calculation_options: DecennialCalculationOptions


class DecennialsPayload(_DecennialsPayloadRequired, total=False):
    timeline: list[DecennialPeriod]


def _rotate_items(items: list[str], start_value: str) -> list[str]:
    index = items.index(start_value)
    return items[index:] + items[:index]


def _build_decennial_zodiacal_order(subject: NativeSubject) -> list[str]:
    ranked = [
        (point_absolute_position(subject, planet), index, planet)
        for index, planet in enumerate(DECENNIAL_TRADITIONAL_PLANETS)
    ]
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [planet for _, _, planet in ranked]


def resolve_decennial_start_planet(subject: NativeSubject, start_mode: str) -> str:
    if start_mode != DECENNIAL_START_MODE_SECT_LIGHT:
        return start_mode
    return "Sun" if determine_sect(subject) == "day" else "Moon"


def get_decennial_order(
    subject: NativeSubject, start_planet: str, order_type: str
) -> list[str]:
    base = (
        list(DECENNIAL_TRADITIONAL_PLANETS)
        if order_type == DECENNIAL_ORDER_CHALDEAN
        else _build_decennial_zodiacal_order(subject)
    )
    return _rotate_items(base, start_planet)


def _format_nominal_offset(total_minutes: int, level: int) -> str:
    minutes = total_minutes
    years, minutes = divmod(minutes, DECENNIAL_MINUTES_PER_YEAR)
    months, minutes = divmod(minutes, DECENNIAL_MINUTES_PER_MONTH)
    days, minutes = divmod(minutes, DECENNIAL_MINUTES_PER_DAY)
    hours, minutes = divmod(minutes, 60)
    if level >= 4:
        prefix = ""
        if years:
            prefix += f"{years}年"
        if months:
            prefix += f"{months}个月"
        if days:
            prefix += f"{days}天"
        return f"{prefix or '0天'} {hours:02d}:{minutes:02d}"
    if level == 3:
        parts = []
        if years:
            parts.append(f"{years}年")
        if months:
            parts.append(f"{months}个月")
        if days or not parts:
            parts.append(f"{days}天")
        return "".join(parts)
    parts = []
    if years:
        parts.append(f"{years}年")
    if months or not parts:
        parts.append(f"{months}个月")
    return "".join(parts)


@dataclass(frozen=True)
class _DecennialInterval:
    key: str
    level: int
    planet: str
    start_minutes: Fraction
    end_minutes: Fraction

    def children(self, base_order: list[str]) -> list[_DecennialInterval]:
        """Divide exact nominal time; never round a parent before subdividing."""
        order = _rotate_items(base_order, self.planet)
        unit = (
            Fraction(DECENNIAL_MINUTES_PER_MONTH)
            if self.level == 1
            else (self.end_minutes - self.start_minutes) / DECENNIAL_TOTAL_BASE_MONTHS
        )
        cursor = self.start_minutes
        result = []
        for index, planet in enumerate(order):
            end = cursor + unit * DECENNIAL_PLANET_BASE_MONTHS[planet]
            result.append(
                _DecennialInterval(
                    f"{self.key}_l{self.level + 1}_{index}",
                    self.level + 1,
                    planet,
                    cursor,
                    end,
                )
            )
            cursor = end
        return result

    def payload(
        self,
        birth_utc: UTCCalendar,
        display_zone: tzinfo,
        analysis_utc: UTCCalendar,
        calendar_scale: Fraction,
        *,
        include_sublevel: bool = True,
    ) -> DecennialPeriod:
        # Round the absolute rational offset once to the civil microsecond grid.
        # Local civil labels never participate in the elapsed-time arithmetic.
        start_utc = birth_utc.shifted(
            timedelta(
                microseconds=round(self.start_minutes * calendar_scale * 60_000_000)
            )
        )
        end_utc = birth_utc.shifted(
            timedelta(
                microseconds=round(self.end_minutes * calendar_scale * 60_000_000)
            )
        )
        start = ZonedCalendar(start_utc, display_zone).require_datetime()
        end = ZonedCalendar(end_utc, display_zone).require_datetime()
        display_start = round(self.start_minutes)
        display_end = round(self.end_minutes)
        result: DecennialPeriod = {
            "key": self.key,
            "level": self.level,
            "planet": self.planet,
            "planet_label": planet_label(self.planet),
            "date": f"{start:%Y-%m-%d} - {end:%Y-%m-%d}",
            "nominal": (
                f"{_format_nominal_offset(display_start, self.level)} - "
                f"{_format_nominal_offset(display_end, self.level)}"
            ),
            "start": format_local_time_or_utc(start),
            "end": format_local_time_or_utc(end),
            "active": start_utc <= analysis_utc < end_utc,
            "start_offset_minutes": display_start,
            "end_offset_minutes": display_end,
            "start_offset_exact_minutes": {
                "numerator": self.start_minutes.numerator,
                "denominator": self.start_minutes.denominator,
            },
            "end_offset_exact_minutes": {
                "numerator": self.end_minutes.numerator,
                "denominator": self.end_minutes.denominator,
            },
        }
        if include_sublevel:
            result["sublevel"] = []
        return result


def build_decennials_payload(
    birth_info: AstroBirthInfo,
    natal_subject: NativeSubject,
    *,
    analysis_datetime: datetime,
    start_mode: str = DECENNIAL_START_MODE_SECT_LIGHT,
    order_type: str = DECENNIAL_ORDER_ZODIACAL,
    day_method: str = DECENNIAL_DAY_METHOD_VALENS,
    calendar_type: str = DECENNIAL_CALENDAR_TRADITIONAL,
    include_full_timelines: bool = True,
) -> DecennialsPayload:
    """Build the seven-period preview and the current path, not a discarded tree.

    Only the default settings are exposed by the public request schemas. The
    former, unattributed hephaistio candidate did not conserve parent time;
    it is rejected rather than normalized or presented as an accepted method.
    """
    if start_mode not in [
        DECENNIAL_START_MODE_SECT_LIGHT,
        *DECENNIAL_TRADITIONAL_PLANETS,
    ]:
        raise ValueError(f"Unsupported decennial start mode: {start_mode}")
    if order_type not in (DECENNIAL_ORDER_ZODIACAL, DECENNIAL_ORDER_CHALDEAN):
        raise ValueError(f"Unsupported decennial order: {order_type}")
    if day_method != DECENNIAL_DAY_METHOD_VALENS:
        raise ValueError(f"Unverified decennial day method: {day_method}")
    if calendar_type not in (DECENNIAL_CALENDAR_TRADITIONAL, DECENNIAL_CALENDAR_ACTUAL):
        raise ValueError(f"Unsupported decennial calendar: {calendar_type}")

    birth_utc = birth_info.utc_calendar
    analysis_utc = utc_calendar(analysis_datetime)
    display_zone = ZonedCalendar.from_datetime(birth_info.local_datetime).zone
    calendar_scale = (
        Fraction(487, 480)
        if calendar_type == DECENNIAL_CALENDAR_ACTUAL
        else Fraction(1)
    )
    start_planet = resolve_decennial_start_planet(natal_subject, start_mode)
    base_order = get_decennial_order(natal_subject, start_planet, order_type)
    l1_minutes = DECENNIAL_TOTAL_L1_DAYS * DECENNIAL_MINUTES_PER_DAY
    elapsed = analysis_utc.elapsed_since(birth_utc)
    elapsed_minutes = Fraction(
        (elapsed.days * 86400 + elapsed.seconds) * 1_000_000 + elapsed.microseconds,
        60_000_000,
    )
    current_index = elapsed_minutes // (l1_minutes * calendar_scale)
    indices = list(range(7))
    if current_index >= 7:
        indices.append(current_index)
    intervals = [
        _DecennialInterval(
            f"l1_{index}",
            1,
            base_order[index % 7],
            Fraction(l1_minutes * index),
            Fraction(l1_minutes * (index + 1)),
        )
        for index in indices
    ]
    timeline = (
        [
            interval.payload(birth_utc, display_zone, analysis_utc, calendar_scale)
            for interval in intervals[:7]
        ]
        if include_full_timelines
        else []
    )
    current: list[DecennialPeriod | None] = [None, None, None]
    active = next(
        (interval for interval in intervals if interval.key == f"l1_{current_index}"),
        None,
    )
    for index in range(3):
        if active is None:
            break
        node = active.payload(
            birth_utc,
            display_zone,
            analysis_utc,
            calendar_scale,
            include_sublevel=include_full_timelines,
        )
        children = active.children(base_order)
        sublevel = [
            child.payload(birth_utc, display_zone, analysis_utc, calendar_scale)
            for child in children
        ]
        if include_full_timelines:
            node["sublevel"] = sublevel
        current[index] = node
        active = next(
            (child for child, output in zip(children, sublevel) if output["active"]),
            None,
        )
    result: DecennialsPayload = {
        "resolved_start_planet": start_planet,
        "resolved_start_planet_label": planet_label(start_planet),
        "base_order": base_order,
        "current_level_1": current[0],
        "current_level_2": current[1],
        "current_level_3": current[2],
        "calculation_options": {
            "start_mode": start_mode,
            "order_type": order_type,
            "day_method": "exact_proportional",
            "calendar_type": calendar_type,
            "time_basis": "UTC_nominal_elapsed_days",
            "timestamp_rounding": "nearest_microsecond_ties_to_even_from_birth",
            "offset_minutes_rounding": "nearest_minute_ties_to_even_display_only",
            "timezone": birth_info.timezone,
        },
    }
    if include_full_timelines:
        result["timeline"] = timeline
    return result
