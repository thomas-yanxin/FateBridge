"""Output contracts for Sukuyo (27/28-mansion calendar, Suzhan, and compatibility)."""

from __future__ import annotations

from pydantic import JsonValue

from fatebridge.core.contracts.astro import GuolaoBoundary, GuolaoMansion, LocalChart
from fatebridge.core.contracts.base import OpenJsonValue, PartialOutput, ProjectedOutput
from fatebridge.core.contracts.common import AnalysisContext, Object
from fatebridge.core.receipt_models import RunMetadata


class SukuyoDetailMatch(PartialOutput):
    required_any_of: list[str] | None = None
    required_all_of: list[str] | None = None
    satisfied_details: list[str] | None = None
    declared_satisfied_details: list[str] | None = None
    implied_satisfied_details: list[str] | None = None
    missing_all_of: list[str] | None = None
    any_of_satisfied: bool | None = None
    all_of_satisfied: bool | None = None
    textual_reading_resolved: bool | None = None
    applied_to_aggregate: bool | None = None


class SukuyoActivityRule(PartialOutput):
    source_passages: list[dict[str, OpenJsonValue]] | None = None
    rule_id: str | None = None
    layer: str | None = None
    selectors: list[OpenJsonValue] | None = None
    activities: list[str] | None = None
    assessment: str | None = None
    locator: str | None = None
    source_url: str | None = None
    source_excerpt: str | None = None
    source_excerpts: list[str] | None = None
    meaning: str | None = None
    volume: str | None = None
    applicability: str | None = None
    topic_condition: str | None = None
    applicability_status: str | None = None
    applied_to_aggregate: bool | None = None
    activity_detail_any_of: list[str] | None = None
    activity_detail_all_of: list[str] | None = None
    matched_activity_details: list[str] | None = None
    requires_textual_review: bool | None = None
    activity_conditions: dict[str, OpenJsonValue] | None = None
    detail_match: SukuyoDetailMatch | None = None
    direction: str | None = None
    direction_binding_basis: str | None = None
    direction_locator: str | None = None
    literal_palace_ordinal: int | None = None
    literal_palace_name: str | None = None
    unparsed_selector_literals: list[str] | None = None
    textual_variants: list[dict[str, OpenJsonValue]] | None = None
    textual_assessment_variant: bool | None = None
    auspicious_time_cannot_release: bool | None = None
    source_witness: str | None = None


class SukuyoActivityLayer(PartialOutput):
    layer: str | None = None
    status: str | None = None
    rule_ids: list[str] | None = None
    conditional_rule_ids: list[str] | None = None


class SukuyoActivityAssessment(PartialOutput):
    activity: str | None = None
    activity_details: list[str] | None = None
    effective_activity_details: list[str] | None = None
    detail_inferences: list[dict[str, str]] | None = None
    evidence_status: str | None = None
    layers: list[SukuyoActivityLayer] | None = None
    matched_rules: list[SukuyoActivityRule] | None = None
    conditional_rules: list[SukuyoActivityRule] | None = None
    conditional_rules_applied_to_aggregate: bool | None = None
    textual_issues: list[dict[str, OpenJsonValue]] | None = None
    unresolved_source_rules_present: bool | None = None


class SukuyoSpecialRow(PartialOutput):
    label: str | None = None
    weekday_index: int | None = None
    luminary: str | None = None
    literal_mansion: str | None = None
    mansion: str | None = None
    source_main_literal: str | None = None
    source_main_weekday_index: int | None = None
    source_clause: str | None = None
    locator: str | None = None
    apparatus: list[dict[str, OpenJsonValue]] | None = None
    reading_status: str | None = None
    witness_basis: str | None = None
    source_clause_is_witness_reading: bool | None = None
    candidate_readings: list[str] | None = None
    candidate_readings_accepted_as_mansion: bool | None = None


class SukuyoSpecialWitness(PartialOutput):
    witness: str | None = None
    volume: str | None = None
    edition: str | None = None
    matched_labels: list[str] | None = None
    matched_rows: list[SukuyoSpecialRow] | None = None
    rows_for_weekday: list[SukuyoSpecialRow] | None = None
    unresolved_rows: list[SukuyoSpecialRow] | None = None
    labels_complete_for_selected_day: bool | None = None
    applied_to_primary: bool | None = None
    disagrees_with_primary: bool | None = None
    source_reference: dict[str, OpenJsonValue] | None = None


class SukuyoSpecialCandidate(PartialOutput):
    mansion: str | None = None
    matched_labels: list[str] | None = None
    applied_to_primary: bool | None = None


class SukuyoSpecialDays(PartialOutput):
    ruleset_id: str | None = None
    status: str | None = None
    mansion: str | None = None
    weekday_index: int | None = None
    primary: SukuyoSpecialWitness | None = None
    comparisons: list[SukuyoSpecialWitness] | None = None
    direct_printed_comparisons: list[SukuyoSpecialWitness] | None = None
    candidate_primary: list[SukuyoSpecialCandidate] | None = None
    source_url: str | None = None
    selected_primary: str | None = None
    selected_lower_activity_witness: str | None = None
    weekday_basis: str | None = None
    physical_lunar_conjunction_evaluated: bool | None = None
    classical_daybreak_boundary_acceptance: bool | None = None
    scope: str | None = None


class SukuyoDirectionCandidate(PartialOutput):
    mansion: str | None = None
    records: list[SukuyoActivityRule] | None = None
    applied_to_primary: bool | None = None


class SukuyoDirectionalTravel(PartialOutput):
    ruleset_id: str | None = None
    status: str | None = None
    mansion: str | None = None
    selected_records: list[SukuyoActivityRule] | None = None
    candidate_records: list[SukuyoDirectionCandidate] | None = None
    basis: str | None = None
    source_url: str | None = None
    locator: str | None = None
    selected_text: str | None = None
    textual_issues: list[dict[str, OpenJsonValue]] | None = None
    direction_inferred: bool | None = None
    physical_palace_computed: bool | None = None
    scope: str | None = None


class SukuyoNatureGroup(PartialOutput):
    name: str | None = None
    literal_heading: str | None = None
    members: list[str] | None = None
    locator: str | None = None
    source_excerpts: list[str] | None = None
    textual_variants: list[dict[str, OpenJsonValue]] | None = None


class SukuyoLowerNature(PartialOutput):
    status: str | None = None
    mansion: str | None = None
    selected_group: SukuyoNatureGroup | None = None
    upper_nature: str | None = None
    membership_differs_from_upper: bool | None = None
    membership_basis: str | None = None
    cow_reference_not_applied_to_calendar: bool | None = None


class SukuyoLowerWeekday(PartialOutput):
    luminary: str | None = None
    literal_title: str | None = None
    locator: str | None = None
    basis: str | None = None
    classical_daybreak_boundary_acceptance: bool | None = None


class SukuyoLowerMethods(PartialOutput):
    ruleset_id: str | None = None
    source_url: str | None = None
    selected_text: str | None = None
    nature: SukuyoLowerNature | None = None
    weekday: SukuyoLowerWeekday | None = None
    scope: str | None = None


class SukuyoLowerMansion(PartialOutput):
    status: str | None = None
    mansion: str | None = None
    ruleset_id: str | None = None
    source_url: str | None = None
    locator: str | None = None
    topic_rules: list[SukuyoActivityRule] | None = None
    textual_issues: list[dict[str, OpenJsonValue]] | None = None
    mapping_notes: list[str] | None = None
    scope: str | None = None


class SukuyoConjunctionGroup(PartialOutput):
    id: str | None = None
    label: str | None = None
    members: list[str] | None = None
    membership_basis: str | None = None
    locator: str | None = None
    meaning: str | None = None


class SukuyoConjunctionCandidate(PartialOutput):
    mansion: str | None = None
    group: SukuyoConjunctionGroup | None = None
    applied_to_primary: bool | None = None


class SukuyoConjunctionDoctrine(PartialOutput):
    ruleset_id: str | None = None
    status: str | None = None
    mansion: str | None = None
    selected_group: SukuyoConjunctionGroup | None = None
    candidate_groups: list[SukuyoConjunctionCandidate] | None = None
    basis: str | None = None
    source_url: str | None = None
    locator: str | None = None
    angular_offset_degrees: float | None = None
    physical_evaluation_status: str | None = None
    applied_to_physical_moon: bool | None = None
    scope: str | None = None


class SukuyoMonthTableVariant(PartialOutput):
    ruleset_id: str | None = None
    lunar_month: int | None = None
    lunar_day: int | None = None
    literal_mansion: str | None = None
    table_mansion_28: str | None = None
    reference_month_day_mansion_27: str | None = None
    reference_is_primary_result: bool | None = None
    differs_from_selected_27: bool | None = None
    applied_to_sanjiu: bool | None = None
    locator: str | None = None
    source_url: str | None = None


class SukuyoDayClassification(PartialOutput):
    witness: str | None = None
    assessment: str | None = None
    locator: str | None = None


class SukuyoTimeRestriction(PartialOutput):
    witness: str | None = None
    phase: str | None = None
    assessment_before_release: str | None = None
    release_after: str | None = None
    locator: str | None = None
    source_excerpt: str | None = None
    literal_lunar_day: int | None = None
    interpreted_lunar_day: int | None = None
    interpretation_status: str | None = None
    annotation_locator: str | None = None
    release_locator: str | None = None
    release_excerpt: str | None = None


class SukuyoVerseResolution(PartialOutput):
    id: str | None = None
    locator: str | None = None
    source_url: str | None = None
    source_excerpt: str | None = None
    xml_kind: str | None = None
    literal_expression: str | None = None
    literal_lunar_day: int | None = None
    interpreted_lunar_day: int | None = None
    resolution_status: str | None = None
    applies_to_current_lunar_day: bool | None = None
    scope: str | None = None


class SukuyoComparativeTimeReference(PartialOutput):
    id: str | None = None
    witnesses: list[dict[str, OpenJsonValue]] | None = None
    applied_to_runtime_clock: bool | None = None
    t1299_day_eight_night_eight_replaced: bool | None = None
    modern_clock_conversion_established: bool | None = None
    solar_altitude_degrees: float | None = None
    hinoo_half_mapping_established: bool | None = None
    scope: str | None = None


class SukuyoClockDoctrine(PartialOutput):
    source_specific_time_calibration: dict[str, OpenJsonValue] | None = None
    kenyu_printed_reference: dict[str, OpenJsonValue] | None = None
    textual_position_reference: dict[str, OpenJsonValue] | None = None
    historical_clock_arithmetic: dict[str, OpenJsonValue] | None = None
    id: str | None = None
    source_url: str | None = None
    locator: str | None = None
    source_excerpt: str | None = None
    day_parts: int | None = None
    night_parts: int | None = None
    starting_boundary_literal: str | None = None
    next_boundary_literal: str | None = None
    intradaily_luminary_order: list[str] | None = None
    comparative_time_systems: SukuyoComparativeTimeReference | None = None
    physical_clock_mapping_status: str | None = None
    western_24_hora_applied: bool | None = None
    scope: str | None = None


class SukuyoCalendarDay(PartialOutput):
    lunar_day: int | None = None
    lunar_half: str | None = None
    half_day: int | None = None
    upper_name: str | None = None
    lower_name: str | None = None
    upper_name_locator: str | None = None
    lower_name_locator: str | None = None
    classifications: list[SukuyoDayClassification] | None = None
    time_restrictions: list[SukuyoTimeRestriction] | None = None
    name_variant: bool | None = None
    classification_variant: bool | None = None
    prose_verse_time_variant: bool | None = None
    prose_verse_time_semantic_conflict: bool | None = None
    verse_abbreviation_resolution: SukuyoVerseResolution | None = None
    clock_evaluation_status: str | None = None
    clock_scope: str | None = None
    clock_doctrine: SukuyoClockDoctrine | None = None
    japanese_selected_reference: dict[str, OpenJsonValue] | None = None


class SukuyoDateInterval(PartialOutput):
    calendar_date: str | None = None
    start_utc_inclusive: str | None = None
    end_utc_exclusive: str | None = None
    start_utc_epoch_seconds: int | None = None
    end_utc_epoch_seconds: int | None = None
    start_utc_epoch_microseconds: str | None = None
    end_utc_epoch_microseconds: str | None = None


class SukuyoDateSupport(PartialOutput):
    calendar_reference_timezone: str | None = None
    utc_endpoints_use_astronomical_year_numbering: bool | None = None
    method_id: str | None = None
    local_date: str | None = None
    input_timezone: str | None = None
    possible_calendar_dates: list[str] | None = None
    utc_support_intervals: list[SukuyoDateInterval] | None = None
    civil_support_seconds: int | None = None
    enumeration_resolution_seconds: int | None = None
    interval_resolution_microseconds: int | None = None
    fixed_offset_microseconds: int | None = None
    timezone_rules: dict[str, str] | None = None
    complete_under_loaded_timezone_rules: bool | None = None
    birth_time_imputed: bool | None = None
    scope: str | None = None


class SukuyoFullmoonCalculation(PartialOutput):
    ruleset_id: str | None = None
    lunar_month: int | None = None
    lunar_day: int | None = None
    fullmoon_day: int | None = None
    fullmoon_mansion: str | None = None
    signed_day_offset: int | None = None
    direct_mansion: str | None = None
    shortcut_inclusive_count: int | None = None
    shortcut_one_based_remainder: int | None = None
    shortcut_mansion: str | None = None
    methods_agree: bool | None = None
    source_url: str | None = None
    direct_locator: str | None = None
    shortcut_locator: str | None = None
    scope: str | None = None


class SukuyoCalendarProfile(PartialOutput):
    calendar_profile: str | None = None
    mansion_method_id: str | None = None
    host_calculation: SukuyoFullmoonCalculation | None = None
    requested_leap_month_policy: str | None = None
    effective_leap_month_policy: str | None = None
    calendar_day_part: str | None = None
    resolved: bool | None = None
    resolution_reason: str | None = None
    natal_su27: str | None = None
    candidate_su27: str | None = None
    candidate_su27s: list[str] | None = None
    candidate_set_complete_under_declared_reconstructions: bool | None = None
    short_month_assignment: dict[str, OpenJsonValue] | None = None
    hinoo_source: dict[str, OpenJsonValue] | None = None
    historical_calendar_reconstruction: bool | None = None
    classical_full_profile_acceptance: bool | None = None


class SukuyoDayCycleAnchor(PartialOutput):
    civil_ordinal: int | None = None
    day_ganzhi: str | None = None
    source_lunar_year_query: int | None = None


class SukuyoHistoricalDayReference(PartialOutput):
    name: str | None = None
    method_id: str | None = None
    source_anchor: SukuyoDayCycleAnchor | None = None
    elapsed_civil_days: int | None = None
    reference_boundary: str | None = None
    historical_day_boundary_accepted: bool | None = None
    bazi_day_pillar_evaluated: bool | None = None


class SukuyoCalendarReference(PartialOutput):
    manuscript_month_header: dict[str, OpenJsonValue] | None = None
    manuscript_daily_annotations: dict[str, OpenJsonValue] | None = None
    id: str | None = None
    provider_calendar_id: str | None = None
    source_url: str | None = None
    calendar_metadata_url: str | None = None
    source_month_start_ordinal: int | None = None
    source_month_length_days: int | None = None
    day_cycle_anchor: SukuyoDayCycleAnchor | None = None
    day_ganzhi_reference: SukuyoHistoricalDayReference | None = None
    month_truncated_by_calendar_reform: bool | None = None
    cross_source_comparison: dict[str, OpenJsonValue] | None = None
    cross_source_disagreement_dates: int | None = None
    retained_disagreement_interval_count: int | None = None
    complete_provider_advertised_historical_range: bool | None = None
    public_datetime_year_zero_and_bce_inputs_supported: bool | None = None
    supported_range_inclusive: list[str] | None = None
    methodology_advertised_range_inclusive: list[str] | None = None
    reference_day_count: int | None = None
    source_provenance: list[dict[str, OpenJsonValue]] | None = None
    monthly_endpoint_reconciliation: list[dict[str, OpenJsonValue]] | None = None
    source_discrepancies_retained: list[str] | None = None
    date_source_uri: str | None = None
    date_provenance: str | None = None
    calendar_reference_timezone: str | None = None
    historical_local_time_reconstruction: bool | None = None
    printed_lunar_year: int | None = None
    lunar_year_is_gregorian_era_year: bool | None = None
    historical_calendar_acceptance: bool | None = None
    independent_whole_range_verification: bool | None = None
    scope: str | None = None


class SukuyoCalendar(PartialOutput):
    input_timezone_rules: dict[str, str] | None = None
    calendar_basis: str | None = None
    calendar_reference: SukuyoCalendarReference | None = None
    status: str | None = None
    calendar_date: str | None = None
    calendar_timezone: str | None = None
    lunar_year: int | None = None
    lunar_month: int | None = None
    lunar_day: int | None = None
    is_leap_month: bool | None = None
    birth_time_known: bool | None = None
    natal_su27: str | None = None
    candidate_su27: str | None = None
    candidate_su27s: list[str] | None = None
    calendar_profile: str | None = None
    mansion_method_id: str | None = None
    calendar_day_part: str | None = None
    resolution_reason: str | None = None
    profile_calculation: SukuyoCalendarProfile | None = None
    leap_month_policy: str | None = None
    source_table_variant: SukuyoMonthTableVariant | None = None
    printed_edition_reference: dict[str, OpenJsonValue] | None = None
    date_support: SukuyoDateSupport | None = None
    calendar_candidates: list[dict[str, OpenJsonValue]] | None = None
    out_of_range_calendar_dates: list[str] | None = None


class SukuyoPalace(PartialOutput):
    ordinal: int | None = None
    name: str | None = None
    literal_name: str | None = None
    ruler_literal: str | None = None
    ruler_luminary: str | None = None
    division: str | None = None
    locator: str | None = None
    textual_variants: list[dict[str, OpenJsonValue]] | None = None


class SukuyoPadaCell(PartialOutput):
    mansion: str | None = None
    pada: int | None = None
    palace_ordinal: int | None = None
    palace_name: str | None = None
    ruler_luminary: str | None = None
    locator: str | None = None


class SukuyoPalaceReference(PartialOutput):
    ruleset_id: str | None = None
    status: str | None = None
    basis: str | None = None
    mansion: str | None = None
    mansion_candidates: list[str] | None = None
    textual_pada: int | None = None
    candidate_set_complete_within_calendar_profile: bool | None = None
    selected_palace: SukuyoPalace | None = None
    candidate_palaces: list[SukuyoPalace] | None = None
    rows: list[SukuyoPadaCell] | None = None
    pada_numbering_basis: str | None = None
    pada_ordinals_explicit_in_source: bool | None = None
    source_url: str | None = None
    locator: str | None = None
    applied_to_calendar_mansion: bool | None = None
    applied_to_sanjiu: bool | None = None
    applied_to_modern_chart: bool | None = None
    birth_pada_established: bool | None = None
    physical_longitude_status: str | None = None
    scope: str | None = None


class SukuyoSanjiuDayWitness(PartialOutput):
    volume: str | None = None
    source_witness: str | None = None
    locator: str | None = None
    source_excerpts: list[str] | None = None
    meaning: str | None = None
    primary_paragraph_id: str | None = None


class SukuyoSanjiuDayEvidence(PartialOutput):
    ruleset_id: str | None = None
    relation: str | None = None
    source_url: str | None = None
    witnesses: list[SukuyoSanjiuDayWitness] | None = None
    upper_day_entry_individually_listed: bool | None = None
    priority_clause: SukuyoSanjiuDayWitness | None = None
    priority_clause_applied_to_aggregate: bool | None = None
    scope: str | None = None


class SukuyoPersonalDay(PartialOutput):
    relation: dict[str, OpenJsonValue] | None = None
    source_day_evidence: SukuyoSanjiuDayEvidence | None = None
    upper_volume: dict[str, OpenJsonValue] | None = None
    textual_conflict: bool | None = None
    lower_volume_variant: dict[str, OpenJsonValue] | None = None
    scope: str | None = None


class SukuyoSixPalaceMember(PartialOutput):
    name: str | None = None
    inclusive_ordinal: int | None = None
    mansion: str | None = None
    locator: str | None = None


class SukuyoJointReadingRequirement(PartialOutput):
    source_excerpt: str | None = None
    locator: str | None = None
    evaluated: bool | None = None


class SukuyoSixPalaceReference(PartialOutput):
    ruleset_id: str | None = None
    status: str | None = None
    natal_mansion: str | None = None
    members: list[SukuyoSixPalaceMember] | None = None
    counting_basis: str | None = None
    source_url: str | None = None
    locator: str | None = None
    counting_excerpt: str | None = None
    joint_reading_requirement: SukuyoJointReadingRequirement | None = None
    seven_luminary_transits_evaluated: bool | None = None
    applied_to_day_assessment: bool | None = None
    scope: str | None = None


class SukuyoTaibaiWitness(PartialOutput):
    witness: str | None = None
    status: str | None = None
    location: str | None = None
    horizontal_direction: str | None = None
    realm: str | None = None
    source_excerpt: str | None = None
    locator: str | None = None
    reading_complete_for_selected_day: bool | None = None
    applied_to_primary: bool | None = None


class SukuyoTaibaiReference(PartialOutput):
    ruleset_id: str | None = None
    status: str | None = None
    lunar_day: int | None = None
    selected_witness: str | None = None
    location: str | None = None
    horizontal_direction: str | None = None
    realm: str | None = None
    row_id: str | None = None
    row_lunar_days: list[int] | None = None
    witnesses: list[SukuyoTaibaiWitness] | None = None
    witnesses_agree_for_selected_day: bool | None = None
    title_literal: str | None = None
    table_apparatus: list[dict[str, OpenJsonValue]] | None = None
    source_url: str | None = None
    locator: str | None = None
    publisher_primary: dict[str, OpenJsonValue] | None = None
    doctrine: dict[str, OpenJsonValue] | None = None
    physical_venus_position_evaluated: bool | None = None
    astronomical_retrograde_evaluated: bool | None = None
    movement_alignment_evaluated: bool | None = None
    applied_to_activity_assessment: bool | None = None
    independent_ming_edition_collated: bool | None = None
    scope: str | None = None


class SukuyoClothingVerse(PartialOutput):
    mansion: str | None = None
    literal_mansion: str | None = None
    taisho_text: str | None = None
    ming_apparatus_text: str | None = None
    locator: str | None = None


class SukuyoClothingWitness(PartialOutput):
    witness: str | None = None
    membership: str | None = None
    assessment: str | None = None
    source_excerpt: str | None = None
    applied_to_primary: bool | None = None
    unlisted_complement_assessment: str | None = None


class SukuyoClothingCandidate(PartialOutput):
    mansion: str | None = None
    verse: SukuyoClothingVerse | None = None
    upper_literal_cutting_statement: dict[str, OpenJsonValue] | None = None
    primary_assessment: str | None = None
    comparisons: list[SukuyoClothingWitness] | None = None


class SukuyoClothingReference(PartialOutput):
    ruleset_id: str | None = None
    status: str | None = None
    mansion: str | None = None
    candidate_mansions: list[str] | None = None
    candidate_set_complete_under_declared_profile: bool | None = None
    primary_assessment: str | None = None
    selected_witness: str | None = None
    candidate_references: list[SukuyoClothingCandidate] | None = None
    primary_positive_mansions: list[str] | None = None
    ming_literal_list: list[str] | None = None
    ming_unresolved_tokens: list[str] | None = None
    ming_unlisted_complement_assessment: str | None = None
    verse_and_literal_forecasts_applied_to_aggregate: bool | None = None
    independent_ming_edition_collated: bool | None = None
    historical_clock_mapping_evaluated: bool | None = None
    source_url: str | None = None
    locator: str | None = None
    unmapped_clothing_predicates: list[dict[str, OpenJsonValue]] | None = None
    scope: str | None = None


class SukuyoDay(PartialOutput):
    kenyu_lingbi_reference: dict[str, OpenJsonValue] | None = None
    clothing_reference: SukuyoClothingReference | None = None
    calendar: SukuyoCalendar | None = None
    calendar_day: SukuyoCalendarDay | None = None
    day_mansion: str | None = None
    nature: str | None = None
    lunar_half: str | None = None
    half_day: int | None = None
    weekday: dict[str, OpenJsonValue] | None = None
    special_day_labels: list[str] | None = None
    special_day_evidence: SukuyoSpecialDays | None = None
    personal_day: SukuyoPersonalDay | None = None
    six_palace_reference: SukuyoSixPalaceReference | None = None
    taibai_direction_reference: SukuyoTaibaiReference | None = None
    activity_assessment: SukuyoActivityAssessment | None = None
    lower_mansion_day: SukuyoLowerMansion | None = None
    lower_methods: SukuyoLowerMethods | None = None
    directional_travel: SukuyoDirectionalTravel | None = None
    conjunction_doctrine: SukuyoConjunctionDoctrine | None = None
    palace_reference: SukuyoPalaceReference | None = None
    reading_text: str | None = None
    candidate_days: list[dict[str, OpenJsonValue]] | None = None
    candidate_mansion_days: list[dict[str, OpenJsonValue]] | None = None


class SuzhanAstronomyBody(PartialOutput):
    id: str | None = None
    longitude: float | None = None
    latitude: float | None = None
    right_ascension: float | None = None
    declination: float | None = None
    mansion: GuolaoMansion | None = None


class SuzhanAstronomy(PartialOutput):
    method_id: str | None = None
    coordinate_frame: str | None = None
    julian_day_tt: float | None = None
    julian_day_ut1: float | None = None
    utc_datetime: str | None = None
    bodies: list[SuzhanAstronomyBody] | None = None
    boundaries: list[GuolaoBoundary] | None = None
    classical_boundary_acceptance: bool | None = None


class SukuyoPerson(PartialOutput):
    name: str | None = None
    natal_su27: str | None = None
    calendar: SukuyoCalendar | None = None
    palace_reference: SukuyoPalaceReference | None = None


class SukuyoRelation(PartialOutput):
    relation: str | None = None
    pair: str | None = None
    distance: str | None = None
    meaning: str | None = None
    self_su27: str | None = None
    other_su27: str | None = None
    offset: int | None = None
    sequence_group: int | None = None
    traditional_assessment: str | None = None


class SukuyoJointPersonSupport(PartialOutput):
    calendar_date: str | None = None
    calendar_day_part: str | None = None
    natal_su27: str | None = None
    assignment_origin: str | None = None


class SukuyoJointSupport(PartialOutput):
    reconstruction_id: str | None = None
    person1: SukuyoJointPersonSupport | None = None
    person2: SukuyoJointPersonSupport | None = None


class SukuyoSharedReconstruction(PartialOutput):
    method_id: str | None = None
    status: str | None = None
    model_ids: list[str] | None = None
    model_identity: dict[str, OpenJsonValue] | None = None
    assumption: str | None = None
    person_half_days_independent: bool | None = None
    source_priority_established: bool | None = None
    historical_uniformity_established: bool | None = None
    unconstrained_row_count: int | None = None
    supported_row_count: int | None = None
    unsupported_row_count: int | None = None
    support_coverage_complete: bool | None = None
    resolved_support: list[SukuyoJointSupport] | None = None
    reason: str | None = None


class SukuyoCandidateRelation(PartialOutput):
    person1_su27: str | None = None
    person2_su27: str | None = None
    person1_to_person2: SukuyoRelation | None = None
    person2_to_person1: SukuyoRelation | None = None
    pair: str | None = None
    applied_to_primary: bool | None = None
    person1_calendar_dates: list[str] | None = None
    person2_calendar_dates: list[str] | None = None
    shared_reconstruction_ids: list[str] | None = None
    joint_support_status: str | None = None
    joint_support: list[SukuyoJointSupport] | None = None


class SukuyoCandidateAnalysis(PartialOutput):
    status: str | None = None
    candidate_set_complete_within_profile: bool | None = None
    rows: list[SukuyoCandidateRelation] | None = None
    scope: str | None = None
    calendar_date_uncertainty_remains: bool | None = None
    unconstrained_rows: list[SukuyoCandidateRelation] | None = None
    shared_reconstruction_analysis: SukuyoSharedReconstruction | None = None


class SuzhanOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    astronomy: SuzhanAstronomy | None = None
    chart: LocalChart | None = None
    params: Object | None = None
    sukuyo: SukuyoDay | None = None
    summary: Object | list[JsonValue] | str | None = None
    validation: Object | None = None


class SukuyoCompatibilityOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_type: str | None = None
    candidate_relation_analysis: SukuyoCandidateAnalysis | None = None
    pair: str | None = None
    person1: SukuyoPerson | None = None
    person1_to_person2: SukuyoRelation | None = None
    person2: SukuyoPerson | None = None
    person2_to_person1: SukuyoRelation | None = None
    status: str | None = None
    su27_basis: str | None = None
    summary: str | None = None
