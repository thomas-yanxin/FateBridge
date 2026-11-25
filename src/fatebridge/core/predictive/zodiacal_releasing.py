"""黄道释放（Zodiacal Releasing）推运法。"""

from __future__ import annotations

from datetime import datetime, timedelta, tzinfo
from typing import Any

from fatebridge.core.astro.angle_definitions import is_ascendant_resolved
from fatebridge.core.astro.astrology_tables import RULER_BY_SIGN, SIGNS
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.predictive._common import (
    LOT_LABELS,
    LOT_POINT_NAMES,
    build_lot_payloads,
    classify_releasing_phase,
    next_sign,
    opposite_sign,
    planet_label,
    sign_label,
)
from fatebridge.core.predictive.native_chart import NativeSubject
from fatebridge.utils.civil_time import UTCCalendar, ZonedCalendar, utc_calendar
from fatebridge.utils.timezones import format_local_time_or_utc, parse_timezone_name

# 各星座的释放年数（黄道释放法）
ZR_SIGN_PERIODS = {
    "Aries": 15,
    "Taurus": 8,
    "Gemini": 20,
    "Cancer": 25,
    "Leo": 19,
    "Virgo": 20,
    "Libra": 8,
    "Scorpio": 15,
    "Sagittarius": 12,
    "Capricorn": 27,
    "Aquarius": 30,
    "Pisces": 12,
}

# 各层级的单位天数及标签
ZR_LEVEL_UNIT_DAYS = {
    1: 360.0,
    2: 30.0,
    3: 2.5,
    4: 5.0 / 24.0,
}
# Labels name the granularity of one step at each level. They must match
# ZR_LEVEL_UNIT_DAYS above: L3 steps are 2.5 days (day-scale, NOT weeks) and L4
# steps are 5 hours (hour-scale, NOT days) under the standard /12 fractal
# subdivision, so calling them "weeks"/"days" misrepresented the magnitude.
ZR_LEVEL_UNIT_LABELS = {
    1: "years",
    2: "months",
    3: "days",
    4: "hours",
}
ZR_LEVEL_UNIT_LABELS_ZH = {
    1: "年",
    2: "月",
    3: "日",
    4: "时",
}


def build_zodiacal_releasing_period(
    *,
    sign_name: str,
    period_start: UTCCalendar,
    period_end: UTCCalendar,
    fortune_sign: str,
    parent_sign: str,
    level: int,
    analysis_utc: UTCCalendar,
    loosing_of_bond: bool = False,
) -> dict[str, Any]:
    ruler = RULER_BY_SIGN[sign_name]
    phase = classify_releasing_phase(sign_name, fortune_sign)
    # Nominal full-sign duration in the displayed unit, before parent clipping.
    # L3's small-year count multiplies2.5 days; L4 multiplies5 hours.
    duration_value = float(ZR_SIGN_PERIODS[sign_name])
    if level == 3:
        duration_value *= ZR_LEVEL_UNIT_DAYS[level]
    elif level == 4:
        duration_value *= ZR_LEVEL_UNIT_DAYS[level] * 24
    return {
        "sign": sign_name,
        "sign_label": sign_label(sign_name),
        "ruler": ruler,
        "ruler_label": planet_label(ruler),
        "level": level,
        "duration_value": duration_value,
        "duration_unit": ZR_LEVEL_UNIT_LABELS[level],
        "duration_unit_label": ZR_LEVEL_UNIT_LABELS_ZH[level],
        "start": period_start,
        "end": period_end,
        "loosing_of_bond": loosing_of_bond,
        "parent_sign": parent_sign,
        "parent_sign_label": sign_label(parent_sign),
        "active": period_start <= analysis_utc < period_end,
        **phase,
    }


def build_releasing_level_preview(
    *,
    start_sign: str,
    period_start: UTCCalendar,
    fortune_sign: str,
    parent_sign: str,
    level: int,
    analysis_utc: UTCCalendar,
    preview_after_active: int = 4,
    max_periods: int = 24,
) -> list[dict[str, Any]]:
    periods: list[dict[str, Any]] = []
    current_sign = start_sign
    cursor = period_start
    active_found = False
    future_slots_remaining = preview_after_active

    for _ in range(max_periods):
        duration_days = ZR_SIGN_PERIODS[current_sign] * ZR_LEVEL_UNIT_DAYS[level]
        next_cursor = cursor.shifted(timedelta(days=duration_days))
        period = build_zodiacal_releasing_period(
            sign_name=current_sign,
            period_start=cursor,
            period_end=next_cursor,
            fortune_sign=fortune_sign,
            parent_sign=parent_sign,
            level=level,
            analysis_utc=analysis_utc,
        )
        periods.append(period)
        if period["active"]:
            active_found = True
        elif active_found:
            future_slots_remaining -= 1
            if future_slots_remaining <= 0:
                break
        cursor = next_cursor
        current_sign = next_sign(current_sign)

    return periods


def build_releasing_level_within_interval(
    *,
    start_sign: str,
    period_start: UTCCalendar,
    period_end: UTCCalendar,
    fortune_sign: str,
    parent_sign: str,
    level: int,
    analysis_utc: UTCCalendar,
    max_periods: int = 24,
) -> list[dict[str, Any]]:
    periods: list[dict[str, Any]] = []
    current_sign = start_sign
    cursor = period_start
    cycle_start_sign = start_sign
    loosing_used = False
    pending_loosing_of_bond = False

    for _ in range(max_periods):
        if cursor >= period_end:
            break
        duration_days = ZR_SIGN_PERIODS[current_sign] * ZR_LEVEL_UNIT_DAYS[level]
        next_cursor = min(period_end, cursor.shifted(timedelta(days=duration_days)))
        loosing_of_bond = pending_loosing_of_bond
        pending_loosing_of_bond = False
        periods.append(
            build_zodiacal_releasing_period(
                sign_name=current_sign,
                period_start=cursor,
                period_end=next_cursor,
                fortune_sign=fortune_sign,
                parent_sign=parent_sign,
                level=level,
                analysis_utc=analysis_utc,
                loosing_of_bond=loosing_of_bond,
            )
        )
        cursor = next_cursor
        next_sign_name = next_sign(current_sign)
        if (
            level > 1
            and not loosing_used
            and next_sign_name == cycle_start_sign
            and cursor < period_end
        ):
            current_sign = opposite_sign(cycle_start_sign)
            loosing_used = True
            pending_loosing_of_bond = True
        else:
            current_sign = next_sign_name

    return periods


def clean_releasing_period(
    period: dict[str, Any] | None,
    *,
    display_timezone: tzinfo,
) -> dict[str, Any] | None:
    if period is None:
        return None
    return {
        **period,
        "start": format_local_time_or_utc(
            ZonedCalendar(period["start"], display_timezone).require_datetime()
        ),
        "end": format_local_time_or_utc(
            ZonedCalendar(period["end"], display_timezone).require_datetime()
        ),
    }


def clean_releasing_timeline(
    periods: list[dict[str, Any]], *, display_timezone: tzinfo
) -> list[dict[str, Any]]:
    # clean_releasing_period only returns None for a None input; periods here are
    # always real dicts, so the filter keeps every entry and satisfies the type.
    cleaned = [
        clean_releasing_period(period, display_timezone=display_timezone)
        for period in periods
    ]
    return [period for period in cleaned if period is not None]


def peak_signs_from_fortune(fortune_sign: str) -> list[dict[str, str]]:
    fortune_index = SIGNS.index(fortune_sign)
    offsets = [0, 3, 6, 9]
    signs = [SIGNS[(fortune_index + offset) % 12] for offset in offsets]
    return [
        {
            "sign": sign_name,
            "sign_label": sign_label(sign_name),
        }
        for sign_name in signs
    ]


def build_zodiacal_releasing_for_lot(
    lot_key: str,
    lot_payload: dict[str, Any],
    *,
    birth_utc: UTCCalendar,
    analysis_utc: UTCCalendar,
    display_timezone: tzinfo,
    start_sign: str,
    fortune_sign: str,
) -> dict[str, Any]:
    level_one_timeline = build_releasing_level_preview(
        start_sign=start_sign,
        period_start=birth_utc,
        fortune_sign=fortune_sign,
        parent_sign=start_sign,
        level=1,
        analysis_utc=analysis_utc,
    )
    current_level_1 = next(
        (item for item in level_one_timeline if item["active"]), None
    )

    level_two_timeline: list[dict[str, Any]] = []
    current_level_2 = None
    if current_level_1 is not None:
        level_two_timeline = build_releasing_level_within_interval(
            start_sign=current_level_1["sign"],
            period_start=current_level_1["start"],
            period_end=current_level_1["end"],
            fortune_sign=fortune_sign,
            parent_sign=current_level_1["sign"],
            level=2,
            analysis_utc=analysis_utc,
        )
        current_level_2 = next(
            (item for item in level_two_timeline if item["active"]), None
        )

    level_three_timeline: list[dict[str, Any]] = []
    current_level_3 = None
    if current_level_2 is not None:
        level_three_timeline = build_releasing_level_within_interval(
            start_sign=current_level_2["sign"],
            period_start=current_level_2["start"],
            period_end=current_level_2["end"],
            fortune_sign=fortune_sign,
            parent_sign=current_level_2["sign"],
            level=3,
            analysis_utc=analysis_utc,
        )
        current_level_3 = next(
            (item for item in level_three_timeline if item["active"]),
            None,
        )

    return {
        "base_point": LOT_POINT_NAMES[lot_key],
        "base_point_label": LOT_LABELS[lot_key],
        "lot": lot_payload,
        "release_start_sign": start_sign,
        "release_start_sign_label": sign_label(start_sign),
        "start_sign_adjusted": start_sign != lot_payload["sign"],
        "angular_reference_sign": fortune_sign,
        "peak_signs": peak_signs_from_fortune(fortune_sign),
        "current_level_1": clean_releasing_period(
            current_level_1, display_timezone=display_timezone
        ),
        "current_level_2": clean_releasing_period(
            current_level_2, display_timezone=display_timezone
        ),
        "current_level_3": clean_releasing_period(
            current_level_3, display_timezone=display_timezone
        ),
        "level_1_timeline": clean_releasing_timeline(
            level_one_timeline, display_timezone=display_timezone
        ),
        "level_2_timeline": clean_releasing_timeline(
            level_two_timeline, display_timezone=display_timezone
        ),
        "level_3_timeline": clean_releasing_timeline(
            level_three_timeline, display_timezone=display_timezone
        ),
    }


def _unresolved_lot_payload(lot_key: str) -> dict[str, Any]:
    return {
        "point": LOT_POINT_NAMES[lot_key],
        "point_label": LOT_LABELS[lot_key],
        "lot": lot_key,
        "lot_label": LOT_LABELS[lot_key],
        "sign": None,
        "sign_label": None,
        "degree": None,
        "absolute_degree": None,
        "longitude": None,
        "house": None,
        "house_label": None,
        "status": "underdetermined_ascendant",
    }


def _unresolved_releasing_track(lot_key: str) -> dict[str, Any]:
    return {
        "status": "underdetermined_ascendant",
        "ascendant_resolved": False,
        "unavailable_reason": "lot_requires_resolved_ascendant",
        "base_point": LOT_POINT_NAMES[lot_key],
        "base_point_label": LOT_LABELS[lot_key],
        "lot": _unresolved_lot_payload(lot_key),
        "release_start_sign": None,
        "release_start_sign_label": None,
        "start_sign_adjusted": None,
        "angular_reference_sign": None,
        "peak_signs": [],
        "current_level_1": None,
        "current_level_2": None,
        "current_level_3": None,
        "level_1_timeline": [],
        "level_2_timeline": [],
        "level_3_timeline": [],
    }


def _zr_calculation_basis(fortune_sign: str | None) -> dict[str, Any]:
    return {
        "method_id": "brennan_schaim_zodiacal_releasing_2019_v1",
        "source_authors": ["Chris Brennan", "Leisa Schaim"],
        "source_title": "Zodiacal Releasing: An Ancient Timing Technique, episode192",
        "source_date": "2019-02-11",
        "source_url": "https://theastrologypodcast.com/2019/02/11/zodiacal-releasing-an-ancient-timing-technique/",
        "year_basis": "egyptian_360_day",
        "year_days": ZR_LEVEL_UNIT_DAYS[1],
        "interval_time_basis": "elapsed_utc_days",
        "angular_reference_point": LOT_POINT_NAMES["lot_of_fortune"],
        "angular_reference_sign": fortune_sign,
        "spirit_same_sign_rule": "advance_spirit_one_sign",
        "published_levels": [1, 2, 3],
        "whole_procedure_certified": False,
    }


def build_zodiacal_releasing_payload(
    birth_info: AstroBirthInfo,
    natal_subject: NativeSubject,
    *,
    analysis_datetime: datetime,
) -> dict[str, Any]:
    if not is_ascendant_resolved(natal_subject):
        basis = _zr_calculation_basis(None)
        basis["status"] = "underdetermined_ascendant"
        return {
            "status": "underdetermined_ascendant",
            "ascendant_resolved": False,
            "unavailable_reason": "lot_of_fortune_and_lot_of_spirit_require_resolved_ascendant",
            "calculation_basis": basis,
            "spirit": _unresolved_releasing_track("lot_of_spirit"),
            "fortune": _unresolved_releasing_track("lot_of_fortune"),
        }

    # Fixed elapsed periods use UTC coordinates, including auxiliary years.
    # The birth zone applies only when labeling the selected endpoints.
    birth_utc = birth_info.utc_calendar
    analysis_utc = utc_calendar(analysis_datetime)
    display_timezone = parse_timezone_name(birth_info.timezone)
    lots = build_lot_payloads(natal_subject)
    # Selected reconstruction: Brennan/Schaim, episode192 (2019-02-11),
    # "Calculating Zodiacal Releasing Periods" and "Peak Periods":
    # https://theastrologypodcast.com/2019/02/11/zodiacal-releasing-an-ancient-timing-technique/
    # The origin advances only for coincident Spirit/Fortune signs. Natal lot
    # longitudes stay unchanged; every track's angular reference is Fortune.
    fortune_sign = lots["lot_of_fortune"]["sign"]
    spirit_start_sign = lots["lot_of_spirit"]["sign"]
    if spirit_start_sign == fortune_sign:
        spirit_start_sign = next_sign(spirit_start_sign)
    return {
        "calculation_basis": _zr_calculation_basis(fortune_sign),
        "spirit": build_zodiacal_releasing_for_lot(
            "lot_of_spirit",
            lots["lot_of_spirit"],
            birth_utc=birth_utc,
            analysis_utc=analysis_utc,
            display_timezone=display_timezone,
            start_sign=spirit_start_sign,
            fortune_sign=fortune_sign,
        ),
        "fortune": build_zodiacal_releasing_for_lot(
            "lot_of_fortune",
            lots["lot_of_fortune"],
            birth_utc=birth_utc,
            analysis_utc=analysis_utc,
            display_timezone=display_timezone,
            start_sign=fortune_sign,
            fortune_sign=fortune_sign,
        ),
    }
