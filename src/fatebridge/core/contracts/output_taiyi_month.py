"""Projection-safe month origin and selected historical month-label comparison."""

from fatebridge.core.contracts.output_base import PartialOutput


class TaiyiMonthCalendarReference(PartialOutput):
    source_label: str | None = None
    source_calendar_basis: str | None = None
    comparison_hypothesis: str | None = None
    lunar_month_start_julian: str | None = None
    lunar_month_start_gregorian: str | None = None
    next_lunar_month_start_gregorian: str | None = None
    calendar_title: str | None = None
    calendar_authors: str | None = None
    calendar_edition: str | None = None
    calendar_printed_page: int | None = None
    calendar_source: str | None = None
    source_month: int | None = None
    actual_nominal_month: int | None = None
    month_label_matches: bool | None = None
    source_shortcut_count: int | None = None
    actual_shortcut_count: int | None = None
    counter_matches: bool | None = None
    scope: str | None = None


class TaiyiMonthOrigin(PartialOutput):
    profile: str | None = None
    source: str | None = None
    cycle_year: int | None = None
    counted_year: int | None = None
    counted_year_basis: str | None = None
    counter_unit: str | None = None
    mean_lunation_counter: bool | None = None
    source_year_label_adjudicated: bool | None = None
    month_offset: int | None = None
    month_number_from_daxue: int | None = None
    nominal_year: int | None = None
    nominal_month: int | None = None
    year_label_policy: str | None = None
    source_epoch_year: int | None = None
    source_epoch_accumulation: int | None = None
    source_epoch_annual_accumulation: int | None = None
    annual_accumulation: int | None = None
    completed_annual_accumulation: int | None = None
    months_per_year: int | None = None
    tianzheng_preceding_months: int | None = None
    tianzheng_month_offset: int | None = None
    accumulation: int | None = None
    shortcut_epoch_year: int | None = None
    shortcut_inclusive_years: int | None = None
    shortcut_completed_years: int | None = None
    shortcut_completed_months: int | None = None
    shortcut_count: int | None = None
    full_minus_shortcut: int | None = None
    shared_cycle_lcm: int | None = None
    all_shared_cycles_aligned: bool | None = None
    cycle360: int | None = None
    palace_month_number: int | None = None
    source_chart_ju_unadjudicated: int | None = None
    calendar_reference: TaiyiMonthCalendarReference | None = None
    scope: str | None = None
