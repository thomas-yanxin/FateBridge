"""Projection-safe month origin and selected historical month-label comparison."""

from typing import Optional

from .output_base import PartialOutput


class TaiyiMonthCalendarReference(PartialOutput):
    source_label: Optional[str] = None
    source_calendar_basis: Optional[str] = None
    comparison_hypothesis: Optional[str] = None
    lunar_month_start_julian: Optional[str] = None
    lunar_month_start_gregorian: Optional[str] = None
    next_lunar_month_start_gregorian: Optional[str] = None
    calendar_title: Optional[str] = None
    calendar_authors: Optional[str] = None
    calendar_edition: Optional[str] = None
    calendar_printed_page: Optional[int] = None
    calendar_source: Optional[str] = None
    source_month: Optional[int] = None
    actual_nominal_month: Optional[int] = None
    month_label_matches: Optional[bool] = None
    source_shortcut_count: Optional[int] = None
    actual_shortcut_count: Optional[int] = None
    counter_matches: Optional[bool] = None
    scope: Optional[str] = None


class TaiyiMonthOrigin(PartialOutput):
    profile: Optional[str] = None
    source: Optional[str] = None
    cycle_year: Optional[int] = None
    counted_year: Optional[int] = None
    counted_year_basis: Optional[str] = None
    counter_unit: Optional[str] = None
    mean_lunation_counter: Optional[bool] = None
    source_year_label_adjudicated: Optional[bool] = None
    month_offset: Optional[int] = None
    month_number_from_daxue: Optional[int] = None
    nominal_year: Optional[int] = None
    nominal_month: Optional[int] = None
    year_label_policy: Optional[str] = None
    source_epoch_year: Optional[int] = None
    source_epoch_accumulation: Optional[int] = None
    source_epoch_annual_accumulation: Optional[int] = None
    annual_accumulation: Optional[int] = None
    completed_annual_accumulation: Optional[int] = None
    months_per_year: Optional[int] = None
    tianzheng_preceding_months: Optional[int] = None
    tianzheng_month_offset: Optional[int] = None
    accumulation: Optional[int] = None
    shortcut_epoch_year: Optional[int] = None
    shortcut_inclusive_years: Optional[int] = None
    shortcut_completed_years: Optional[int] = None
    shortcut_completed_months: Optional[int] = None
    shortcut_count: Optional[int] = None
    full_minus_shortcut: Optional[int] = None
    shared_cycle_lcm: Optional[int] = None
    all_shared_cycles_aligned: Optional[bool] = None
    cycle360: Optional[int] = None
    palace_month_number: Optional[int] = None
    source_chart_ju_unadjudicated: Optional[int] = None
    calendar_reference: Optional[TaiyiMonthCalendarReference] = None
    scope: Optional[str] = None
