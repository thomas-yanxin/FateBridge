"""Normalize explicit Julian dates and compare selected Taiyi historical dates."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal, TypeGuard

from pydantic import TypeAdapter
from typing_extensions import TypedDict

from fatebridge.core.ephemeris_runtime import swe


class HistoricalCalendarSource(TypedDict):
    title: str
    authors: str
    edition: str
    url: str
    calendar_policy_source: str
    policy: str
    pdf_page: int
    printed_page: int


class HistoricalCalendarRow(TypedDict):
    id: str
    chinese_date: str
    julian_date: str
    gregorian_date: str
    day_ganzhi: str


class HistoricalMonthStart(HistoricalCalendarRow):
    role: Literal["independent_month_start_anchor"]
    printed_cycle_index: int
    printed_weekday_monday_zero: int


class HistoricalCalculatedDate(HistoricalCalendarRow):
    expected_accumulation: int
    representative_clock: str
    source_time_scope: str


class HistoricalDayExample(HistoricalCalculatedDate):
    mode: Literal["day"]


class HistoricalHourExample(HistoricalCalculatedDate):
    mode: Literal["hour"]
    expected_day_number: int
    source_hour_branch: str


class HistoricalCalendarRecords(TypedDict):
    id: str
    source: HistoricalCalendarSource
    records: list[HistoricalMonthStart | HistoricalDayExample | HistoricalHourExample]
    scope: str


class HistoricalDateComparison(TypedDict):
    case_id: str
    source_date: str
    western_source_date: str
    western_source_calendar: str
    normalized_gregorian_date: str
    calendar_table_title: str
    calendar_table_authors: str
    calendar_table_edition: str
    calendar_table_source: str
    source_day_ganzhi: str
    actual_day_ganzhi: str
    scope: str
    calendar_table_printed_page: int
    source_accumulation: int
    actual_accumulation: int
    day_ganzhi_matches: bool
    counter_matches: bool
    source_hour_branch: str | None
    actual_hour_branch: str | None
    hour_branch_matches: bool | None


def julian_to_proleptic_gregorian(year: int, month: int, day: int) -> date:
    if (
        any(type(n) is not int for n in (year, month, day))
        or not 1 <= year <= 9999
        or not 1 <= month <= 12
        or not 1 <= day <= 31
    ):
        raise ValueError("须明确给出有效的正整数儒略历年月日")
    if swe is None:
        raise ValueError("儒略历转换需要 Swiss Ephemeris 的日历算术接口")
    julian_day_at_noon = swe.julday(year, month, day, 12.0, swe.JUL_CAL)
    # note (date validation): Swiss Ephemeris normalizes overflowing dates such as February 30.
    if swe.revjul(julian_day_at_noon, swe.JUL_CAL)[:3] != (year, month, day):
        raise ValueError("无效儒略历日期，不能自动进位")
    gregorian_year, gregorian_month, gregorian_day, _ = swe.revjul(
        julian_day_at_noon, swe.GREG_CAL
    )
    try:
        return date(gregorian_year, gregorian_month, gregorian_day)
    except ValueError as exc:
        raise ValueError("转换后的推算公历日期超出可表达范围") from exc


@lru_cache(maxsize=1)
def historical_date_records() -> HistoricalCalendarRecords:
    path = (
        Path(__file__).resolve().parents[2]
        / "data/classical/taiyi-key-historical-dates-v1.json"
    )
    return TypeAdapter(HistoricalCalendarRecords).validate_json(
        path.read_bytes(), strict=True
    )


def is_historical_calculation_example(
    calendar_row: HistoricalMonthStart | HistoricalDayExample | HistoricalHourExample,
) -> TypeGuard[HistoricalDayExample | HistoricalHourExample]:
    return "mode" in calendar_row


def source_date_reference(
    selected_date: date,
    mode: str,
    counter: int,
    day_ganzhi: str,
    hour_branch: str | None = None,
) -> HistoricalDateComparison | None:
    historical_calendar = historical_date_records()
    date_label = selected_date.isoformat()
    row = next(
        (
            calendar_row
            for calendar_row in historical_calendar["records"]
            if is_historical_calculation_example(calendar_row)
            and calendar_row["mode"] == mode
            and calendar_row["gregorian_date"] == date_label
        ),
        None,
    )
    if row is None:
        return None
    source_hour_branch = row["source_hour_branch"] if row["mode"] == "hour" else None
    return {
        "case_id": row["id"],
        "source_date": row["chinese_date"],
        "western_source_date": row["julian_date"],
        "western_source_calendar": "julian",
        "normalized_gregorian_date": row["gregorian_date"],
        "calendar_table_title": historical_calendar["source"]["title"],
        "calendar_table_authors": historical_calendar["source"]["authors"],
        "calendar_table_edition": historical_calendar["source"]["edition"],
        "calendar_table_source": historical_calendar["source"]["url"],
        "calendar_table_printed_page": historical_calendar["source"]["printed_page"],
        "source_day_ganzhi": row["day_ganzhi"],
        "actual_day_ganzhi": day_ganzhi,
        "day_ganzhi_matches": day_ganzhi == row["day_ganzhi"],
        "source_accumulation": row["expected_accumulation"],
        "actual_accumulation": counter,
        "counter_matches": counter == row["expected_accumulation"],
        "source_hour_branch": source_hour_branch,
        "actual_hour_branch": hour_branch,
        "hour_branch_matches": (
            hour_branch == source_hour_branch
            if source_hour_branch is not None
            else None
        ),
        "scope": row["source_time_scope"]
        + "这里只核对选定日期与现代适配计数，不认证完整古历或全盘原典符合。",
    }
