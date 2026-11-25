"""Projection contracts for explicit Mei Hua calendar-precision evidence."""

from pydantic import JsonValue

from fatebridge.core.contracts.output_base import PartialOutput


class CalendarPrecisionSource(PartialOutput):
    id: str | None = None
    publisher: str | None = None
    title: str | None = None
    url: str | None = None
    raw_sha256: str | None = None
    retrieved_on: str | None = None


class CalendarReviewScopePolicy(PartialOutput):
    kind: str | None = None
    start: str | None = None
    end_exclusive: str | None = None
    review_windows_are_not_published_hko_intervals: bool | None = None
    other_published_month_anchors_assumed_fixed_for_review_scope: bool | None = None
    no_shift_direction_probability_or_alternate_lunar_labels_inferred: bool | None = (
        None
    )
    unlisted_boundaries_are_not_certified_exact: bool | None = None
    solar_term_dates_in_same_source_not_treated_as_lunar_month_starts: bool | None = (
        None
    )


class CalendarMonthReviewEvent(PartialOutput):
    id: str | None = None
    published_new_moon_date: str | None = None
    published_lunar_year: int | None = None
    published_lunar_month: int | None = None
    published_next_month_start: str | None = None
    review_start: str | None = None
    review_end_exclusive: str | None = None
    review_scope_kind: str | None = None
    review_window_is_not_a_published_hko_interval: bool | None = None
    shift_direction_or_probability: str | None = None
    alternate_calendar_computed: bool | None = None


class MeihuaCalendarPrecision(PartialOutput):
    profile_id: str | None = None
    version: str | None = None
    selected_civil_date: str | None = None
    status: str | None = None
    source: CalendarPrecisionSource | None = None
    source_scope: str | None = None
    review_scope_policy: CalendarReviewScopePolicy | None = None
    matched_events: list[CalendarMonthReviewEvent] | None = None
    calculation_policy: str | None = None
    date_label_revision_may_change_month_day_and_cast: bool | None = None
    absence_of_named_event_certifies_exactness: bool | None = None
    exact_astronomical_accuracy_established: bool | None = None
    predictive_efficacy_established: bool | None = None


class MeihuaSolarDateEvent(PartialOutput):
    event_name: str | None = None
    fact_path: str | None = None
    actual_datetime_with_offset: str | None = None
    actual_resolution_provider: str | None = None
    actual_ephemeris_model: str | None = None
    actual_civil_time_method: str | None = None
    computed_datetime_at_reference_offset: str | None = None
    computed_date: str | None = None
    published_date: str | None = None
    date_difference_days: int | None = None
    comparison_status: str | None = None
    source: CalendarPrecisionSource | None = None
    publisher_named_near_midnight: bool | None = None


class MeihuaSolarDateReference(PartialOutput):
    profile_id: str | None = None
    version: str | None = None
    loaded_profile_sha256: str | None = None
    comparison_offset: str | None = None
    source_scope: dict[str, JsonValue] | None = None
    time_basis_source: CalendarPrecisionSource | None = None
    caveat_source: CalendarPrecisionSource | None = None
    events: list[MeihuaSolarDateEvent] | None = None
    status: str | None = None
    selected_record_paths: list[str] | None = None
    compared_record_count: int | None = None
    compared_reference_event_count: int | None = None
    date_disagreement_count: int | None = None
    publisher_named_event_count: int | None = None
    all_selected_records_compared: bool | None = None
    same_reference_event_has_multiple_instants: bool | None = None
    source_uncertainty_interval_seconds: int | None = None
    original_solar_instants_retained: bool | None = None
    original_month_branch_retained: bool | None = None
    original_lunar_seed_retained: bool | None = None
    alternate_event_time_inferred: bool | None = None
    published_date_match_certifies_exactness: bool | None = None
    exact_astronomical_accuracy_established: bool | None = None
    predictive_efficacy_established: bool | None = None
