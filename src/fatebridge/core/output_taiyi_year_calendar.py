"""Strict partial output for the explicitly selected historical year table."""

from typing import List, Literal, Optional

from .output_base import PartialOutput


class TaiyiHistoricalLeapHypothesis(PartialOutput):
    method: Optional[str] = None
    leap_month: Optional[int] = None


class TaiyiHistoricalCalendarDisagreement(PartialOutput):
    id: Optional[str] = None
    year: Optional[int] = None
    printed_leap_month: Optional[int] = None
    alternative_hypotheses: Optional[List[TaiyiHistoricalLeapHypothesis]] = None
    adjudicated: Optional[Literal[False]] = None
    affects_selected_year: Optional[bool] = None
    scope: Optional[str] = None


class TaiyiHistoricalYearCalendar(PartialOutput):
    profile_id: Optional[str] = None
    year_label_basis: Optional[str] = None
    source_disagreements: Optional[List[TaiyiHistoricalCalendarDisagreement]] = None
    calendar_algorithm_identity_adjudicated: Optional[Literal[False]] = None
    provider: Optional[str] = None
    calendar_title: Optional[str] = None
    calendar_authors: Optional[str] = None
    calendar_edition: Optional[str] = None
    source_url: Optional[str] = None
    source_data_sha256: Optional[str] = None
    calendar_tradition: Optional[str] = None
    supported_start: Optional[str] = None
    supported_end_exclusive: Optional[str] = None
    civil_date: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    is_leap_month: Optional[bool] = None
    year_ganzhi: Optional[str] = None
    day_ganzhi: Optional[str] = None
    weekday_sunday_zero: Optional[int] = None
    printed_week_counter: Optional[int] = None
    printed_cycle_counter: Optional[int] = None
    source_month_start_julian: Optional[str] = None
    month_start_gregorian: Optional[str] = None
    next_month_start_gregorian: Optional[str] = None
    source_year_start_julian: Optional[str] = None
    year_start_gregorian: Optional[str] = None
    source_next_year_start_julian: Optional[str] = None
    next_year_start_gregorian: Optional[str] = None
    source_pdf_page: Optional[int] = None
    source_printed_page: Optional[int] = None
    display: Optional[str] = None
    counter_policy: Optional[str] = None
    date_basis: Optional[str] = None
    scope: Optional[str] = None
