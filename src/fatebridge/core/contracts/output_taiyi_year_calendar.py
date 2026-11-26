"""Strict partial output for the explicitly selected historical year table."""

from typing import Literal

from fatebridge.core.contracts.output_base import PartialOutput


class TaiyiHistoricalLeapHypothesis(PartialOutput):
    method: str | None = None
    leap_month: int | None = None


class TaiyiHistoricalCalendarDisagreement(PartialOutput):
    id: str | None = None
    year: int | None = None
    printed_leap_month: int | None = None
    alternative_hypotheses: list[TaiyiHistoricalLeapHypothesis] | None = None
    adjudicated: Literal[False] | None = None
    affects_selected_year: bool | None = None
    scope: str | None = None


class TaiyiHistoricalYearCalendar(PartialOutput):
    profile_id: str | None = None
    year_label_basis: str | None = None
    source_disagreements: list[TaiyiHistoricalCalendarDisagreement] | None = None
    calendar_algorithm_identity_adjudicated: Literal[False] | None = None
    provider: str | None = None
    calendar_title: str | None = None
    calendar_authors: str | None = None
    calendar_edition: str | None = None
    source_url: str | None = None
    source_data_sha256: str | None = None
    calendar_tradition: str | None = None
    supported_start: str | None = None
    supported_end_exclusive: str | None = None
    civil_date: str | None = None
    year: int | None = None
    month: int | None = None
    day: int | None = None
    is_leap_month: bool | None = None
    year_ganzhi: str | None = None
    day_ganzhi: str | None = None
    weekday_sunday_zero: int | None = None
    printed_week_counter: int | None = None
    printed_cycle_counter: int | None = None
    source_month_start_julian: str | None = None
    month_start_gregorian: str | None = None
    next_month_start_gregorian: str | None = None
    source_year_start_julian: str | None = None
    year_start_gregorian: str | None = None
    source_next_year_start_julian: str | None = None
    next_year_start_gregorian: str | None = None
    source_pdf_page: int | None = None
    source_printed_page: int | None = None
    display: str | None = None
    counter_policy: str | None = None
    date_basis: str | None = None
    scope: str | None = None
