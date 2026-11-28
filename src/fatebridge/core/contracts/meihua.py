"""Projection-compatible output contracts for Yijing hexagrams and Mei Hua Yi Shu."""

from __future__ import annotations

from pydantic import JsonValue

from fatebridge.core.contracts.base import PartialOutput, ProjectedOutput
from fatebridge.core.receipt_models import Object, RunMetadata


class ClassicalLine(PartialOutput):
    position: int | None = None
    label: str | None = None
    text: str | None = None


class ClassicalHexagram(PartialOutput):
    corpus_id: str | None = None
    source_kind: str | None = None
    edition_status: str | None = None
    number: int | None = None
    name: str | None = None
    code: str | None = None
    guaci: str | None = None
    daxiang: str | None = None
    yaoci: list[ClassicalLine] | None = None
    special: ClassicalLine | None = None
    source_revision: int | None = None


class CalendarPrecisionSource(PartialOutput):
    id: str | None = None
    publisher: str | None = None
    title: str | None = None
    url: str | None = None
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


class MeihuaSource(PartialOutput):
    id: str | None = None
    title: str | None = None
    revision: int | None = None
    url: str | None = None


class MeihuaRule(PartialOutput):
    id: str | None = None
    source_id: str | None = None
    section: str | None = None
    kind: str | None = None
    quote: str | None = None
    statement: str | None = None


class MeihuaRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    title: str | None = None
    edition: str | None = None
    sources: list[MeihuaSource] | None = None
    rules: list[MeihuaRule] | None = None
    scope: str | None = None


class MeihuaCalendarPolicy(PartialOutput):
    civil_clock_resolution: dict[str, JsonValue] | None = None
    label_precision: MeihuaCalendarPrecision | None = None
    solar_term_date_reference: MeihuaSolarDateReference | None = None
    context_status: str | None = None
    lunar_year: int | None = None
    year_boundary: str | None = None
    day_boundary: str | None = None
    is_leap_month: bool | None = None
    leap_month_rule: str | None = None
    timezone: str | None = None
    date_basis: str | None = None
    hour_basis: str | None = None
    true_solar_time_applied: bool | None = None
    minute_role: str | None = None
    rule_kind: str | None = None


class MeihuaTraceStep(PartialOutput):
    rule_id: str | None = None
    operation: str | None = None
    inputs: dict[str, JsonValue] | None = None
    result: JsonValue | None = None


class MeihuaStageRelation(PartialOutput):
    role: str | None = None
    stage: str | None = None
    body: str | None = None
    body_element: str | None = None
    trigram: str | None = None
    element: str | None = None
    relation: str | None = None
    traditional_tendency: str | None = None
    meaning: str | None = None
    fact_path: str | None = None
    rule_id: str | None = None


class MeihuaSeasonalTrigram(PartialOutput):
    role: str | None = None
    trigram: str | None = None
    element: str | None = None
    strength: str | None = None
    fact_path: str | None = None


class MeihuaSeasonalStrength(PartialOutput):
    month_branch: str | None = None
    season: str | None = None
    basis: str | None = None
    rule_id: str | None = None
    convention_rule_id: str | None = None
    trigrams: list[MeihuaSeasonalTrigram] | None = None


class MeihuaEvidenceScope(PartialOutput):
    calculation_status: str | None = None
    text_count_basis: dict[str, JsonValue] | None = None
    text_tone_basis: dict[str, JsonValue] | None = None
    missing_context: list[str] | None = None
    classical_coverage: str | None = None
    implemented: list[str] | None = None
    not_implemented: list[str] | None = None
    interpretation_basis: str | None = None
    authority_certified: bool | None = None


class MeihuaCountingVariant(PartialOutput):
    line_sum_basis: str | None = None
    selected: bool | None = None
    moving_line: int | None = None
    changed_code: str | None = None
    body: str | None = None
    use: str | None = None
    moving_palace: str | None = None
    body_use_relation: str | None = None


class Trigram(PartialOutput):
    name: str | None = None
    cname: str | None = None
    element: str | None = None
    elem: str | None = None
    lines: list[int] | None = None
    nature: str | None = None
    symbol: str | None = None
    value: list[int] | None = None


class Hexagram(PartialOutput):
    classical: ClassicalHexagram | None = None
    name: str | None = None
    binary_code: str | None = None
    code: str | None = None
    lookup_type: str | None = None
    matched_query: str | None = None
    lines: list[int] | None = None
    lower: Trigram | None = None
    upper: Trigram | None = None
    moving_line: int | None = None
    symbol: str | None = None


class GuaLookupResult(Hexagram):
    element: str | None = None
    nature: str | None = None


class MeihuaSeed(PartialOutput):
    casting_method: str | None = None
    parameters: Object | None = None
    ignored_components: Object | None = None
    raw_upper_number: int | None = None
    raw_lower_number: int | None = None
    line_sum: int | None = None
    line_sum_basis: str | None = None
    alternate_moving_line: int | None = None
    count_boundary_status: str | None = None
    text_count_basis: Object | None = None
    text_tone_basis: Object | None = None
    hour_branch: str | None = None
    year_branch: str | None = None
    lunar_day: int | None = None
    lunar_month: int | None = None
    moving_line: int | None = None
    upper_number: int | None = None
    lower_number: int | None = None


class Meihua(PartialOutput):
    counting_variants: list[MeihuaCountingVariant] | None = None
    version: str | None = None
    ruleset: MeihuaRuleset | None = None
    calendar_policy: MeihuaCalendarPolicy | None = None
    stage_relations: list[MeihuaStageRelation] | None = None
    seasonal_strength: MeihuaSeasonalStrength | None = None
    ruleset_id: str | None = None
    year_boundary: str | None = None
    leap_month_rule: str | None = None
    mutual_rule: str | None = None
    source_url: str | None = None
    method: str | None = None
    seed: MeihuaSeed | None = None
    base_hexagram: Hexagram | None = None
    changed_hexagram: Hexagram | None = None
    mutual_hexagram: Hexagram | None = None
    cuo_hexagram: Hexagram | None = None
    zong_hexagram: Hexagram | None = None
    body_trigram: Trigram | None = None
    use_trigram: Trigram | None = None
    body_use_relation: str | None = None
    body_use_summary: str | None = None
    element_relation: str | None = None
    moving_palace: str | None = None
    summary: str | None = None


class MeihuaCastOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_type: str | None = None
    analysis_context: dict[str, JsonValue] | None = None
    meihua: Meihua | None = None
    interpretation: dict[str, JsonValue] | None = None
    summary: str | None = None
