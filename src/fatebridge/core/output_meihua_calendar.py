"""Projection contracts for explicit Mei Hua calendar-precision evidence."""

from typing import Dict, List, Optional

from pydantic import JsonValue

from .output_base import PartialOutput


class CalendarPrecisionSource(PartialOutput):
    id: Optional[str] = None
    publisher: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    raw_sha256: Optional[str] = None
    retrieved_on: Optional[str] = None


class CalendarReviewScopePolicy(PartialOutput):
    kind: Optional[str] = None
    start: Optional[str] = None
    end_exclusive: Optional[str] = None
    review_windows_are_not_published_hko_intervals: Optional[bool] = None
    other_published_month_anchors_assumed_fixed_for_review_scope: Optional[bool] = None
    no_shift_direction_probability_or_alternate_lunar_labels_inferred: Optional[
        bool
    ] = None
    unlisted_boundaries_are_not_certified_exact: Optional[bool] = None
    solar_term_dates_in_same_source_not_treated_as_lunar_month_starts: Optional[
        bool
    ] = None


class CalendarMonthReviewEvent(PartialOutput):
    id: Optional[str] = None
    published_new_moon_date: Optional[str] = None
    published_lunar_year: Optional[int] = None
    published_lunar_month: Optional[int] = None
    published_next_month_start: Optional[str] = None
    review_start: Optional[str] = None
    review_end_exclusive: Optional[str] = None
    review_scope_kind: Optional[str] = None
    review_window_is_not_a_published_hko_interval: Optional[bool] = None
    shift_direction_or_probability: Optional[str] = None
    alternate_calendar_computed: Optional[bool] = None


class MeihuaCalendarPrecision(PartialOutput):
    profile_id: Optional[str] = None
    version: Optional[str] = None
    selected_civil_date: Optional[str] = None
    status: Optional[str] = None
    source: Optional[CalendarPrecisionSource] = None
    source_scope: Optional[str] = None
    review_scope_policy: Optional[CalendarReviewScopePolicy] = None
    matched_events: Optional[List[CalendarMonthReviewEvent]] = None
    calculation_policy: Optional[str] = None
    date_label_revision_may_change_month_day_and_cast: Optional[bool] = None
    absence_of_named_event_certifies_exactness: Optional[bool] = None
    exact_astronomical_accuracy_established: Optional[bool] = None
    predictive_efficacy_established: Optional[bool] = None


class MeihuaSolarDateEvent(PartialOutput):
    event_name: Optional[str] = None
    fact_path: Optional[str] = None
    actual_datetime_with_offset: Optional[str] = None
    actual_resolution_provider: Optional[str] = None
    actual_ephemeris_model: Optional[str] = None
    actual_civil_time_method: Optional[str] = None
    computed_datetime_at_reference_offset: Optional[str] = None
    computed_date: Optional[str] = None
    published_date: Optional[str] = None
    date_difference_days: Optional[int] = None
    comparison_status: Optional[str] = None
    source: Optional[CalendarPrecisionSource] = None
    publisher_named_near_midnight: Optional[bool] = None


class MeihuaSolarDateReference(PartialOutput):
    profile_id: Optional[str] = None
    version: Optional[str] = None
    loaded_profile_sha256: Optional[str] = None
    comparison_offset: Optional[str] = None
    source_scope: Optional[Dict[str, JsonValue]] = None
    time_basis_source: Optional[CalendarPrecisionSource] = None
    caveat_source: Optional[CalendarPrecisionSource] = None
    events: Optional[List[MeihuaSolarDateEvent]] = None
    status: Optional[str] = None
    selected_record_paths: Optional[List[str]] = None
    compared_record_count: Optional[int] = None
    compared_reference_event_count: Optional[int] = None
    date_disagreement_count: Optional[int] = None
    publisher_named_event_count: Optional[int] = None
    all_selected_records_compared: Optional[bool] = None
    same_reference_event_has_multiple_instants: Optional[bool] = None
    source_uncertainty_interval_seconds: Optional[int] = None
    original_solar_instants_retained: Optional[bool] = None
    original_month_branch_retained: Optional[bool] = None
    original_lunar_seed_retained: Optional[bool] = None
    alternate_event_time_inferred: Optional[bool] = None
    published_date_match_certifies_exactness: Optional[bool] = None
    exact_astronomical_accuracy_established: Optional[bool] = None
    predictive_efficacy_established: Optional[bool] = None
