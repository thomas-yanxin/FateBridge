"""Stable nested facts, with projection-compatible optional fields.

Validate existing payloads without reserialization; dynamic map keys and
extension fields remain open. Definitions follow the service builders.
"""

from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BeforeValidator, JsonValue

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_guolao import GuolaoBoundary, GuolaoMansion


class SukuyoMonthTableVariant(PartialOutput):
    ruleset_id: Optional[str] = None
    lunar_month: Optional[int] = None
    lunar_day: Optional[int] = None
    literal_mansion: Optional[str] = None
    table_mansion_28: Optional[str] = None
    reference_month_day_mansion_27: Optional[str] = None
    reference_is_primary_result: Optional[bool] = None
    differs_from_selected_27: Optional[bool] = None
    applied_to_sanjiu: Optional[bool] = None
    locator: Optional[str] = None
    source_url: Optional[str] = None


class SukuyoDayClassification(PartialOutput):
    witness: Optional[str] = None
    assessment: Optional[str] = None
    locator: Optional[str] = None


class SukuyoTimeRestriction(PartialOutput):
    witness: Optional[str] = None
    phase: Optional[str] = None
    assessment_before_release: Optional[str] = None
    release_after: Optional[str] = None
    locator: Optional[str] = None
    source_excerpt: Optional[str] = None
    literal_lunar_day: Optional[int] = None
    interpreted_lunar_day: Optional[int] = None
    interpretation_status: Optional[str] = None
    annotation_locator: Optional[str] = None
    release_locator: Optional[str] = None
    release_excerpt: Optional[str] = None


class SukuyoVerseResolution(PartialOutput):
    id: Optional[str] = None
    locator: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    source_excerpt: Optional[str] = None
    xml_kind: Optional[str] = None
    literal_expression: Optional[str] = None
    literal_lunar_day: Optional[int] = None
    interpreted_lunar_day: Optional[int] = None
    resolution_status: Optional[str] = None
    applies_to_current_lunar_day: Optional[bool] = None
    scope: Optional[str] = None


class SukuyoComparativeTimeReference(PartialOutput):
    id: Optional[str] = None
    source_bundle_sha256: Optional[str] = None
    witnesses: Optional[List[Dict[str, Any]]] = None
    applied_to_runtime_clock: Optional[bool] = None
    t1299_day_eight_night_eight_replaced: Optional[bool] = None
    modern_clock_conversion_established: Optional[bool] = None
    solar_altitude_degrees: Optional[float] = None
    hinoo_half_mapping_established: Optional[bool] = None
    scope: Optional[str] = None


class SukuyoClockDoctrine(PartialOutput):
    source_specific_time_calibration: Optional[Dict[str, Any]] = None
    kenyu_printed_reference: Optional[Dict[str, Any]] = None
    textual_position_reference: Optional[Dict[str, Any]] = None
    historical_clock_arithmetic: Optional[Dict[str, Any]] = None
    id: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    locator: Optional[str] = None
    source_excerpt: Optional[str] = None
    day_parts: Optional[int] = None
    night_parts: Optional[int] = None
    starting_boundary_literal: Optional[str] = None
    next_boundary_literal: Optional[str] = None
    intradaily_luminary_order: Optional[List[str]] = None
    comparative_time_systems: Optional[SukuyoComparativeTimeReference] = None
    physical_clock_mapping_status: Optional[str] = None
    western_24_hora_applied: Optional[bool] = None
    source_claim_is_empirical_validation: Optional[bool] = None
    scope: Optional[str] = None


class SukuyoCalendarDay(PartialOutput):
    lunar_day: Optional[int] = None
    lunar_half: Optional[str] = None
    half_day: Optional[int] = None
    upper_name: Optional[str] = None
    lower_name: Optional[str] = None
    upper_name_locator: Optional[str] = None
    lower_name_locator: Optional[str] = None
    classifications: Optional[List[SukuyoDayClassification]] = None
    time_restrictions: Optional[List[SukuyoTimeRestriction]] = None
    name_variant: Optional[bool] = None
    classification_variant: Optional[bool] = None
    prose_verse_time_variant: Optional[bool] = None
    prose_verse_time_semantic_conflict: Optional[bool] = None
    verse_abbreviation_resolution: Optional[SukuyoVerseResolution] = None
    clock_evaluation_status: Optional[str] = None
    clock_scope: Optional[str] = None
    clock_doctrine: Optional[SukuyoClockDoctrine] = None
    japanese_selected_reference: Optional[Dict[str, Any]] = None


class SukuyoDateInterval(PartialOutput):
    calendar_date: Optional[str] = None
    start_utc_inclusive: Optional[str] = None
    end_utc_exclusive: Optional[str] = None
    start_utc_epoch_seconds: Optional[int] = None
    end_utc_epoch_seconds: Optional[int] = None
    start_utc_epoch_microseconds: Optional[str] = None
    end_utc_epoch_microseconds: Optional[str] = None


class SukuyoDateSupport(PartialOutput):
    calendar_reference_timezone: Optional[str] = None
    utc_endpoints_use_astronomical_year_numbering: Optional[bool] = None
    method_id: Optional[str] = None
    local_date: Optional[str] = None
    input_timezone: Optional[str] = None
    possible_calendar_dates: Optional[List[str]] = None
    utc_support_intervals: Optional[List[SukuyoDateInterval]] = None
    civil_support_seconds: Optional[int] = None
    enumeration_resolution_seconds: Optional[int] = None
    interval_resolution_microseconds: Optional[int] = None
    fixed_offset_microseconds: Optional[int] = None
    timezone_rules: Optional[Dict[str, str]] = None
    complete_under_loaded_timezone_rules: Optional[bool] = None
    birth_time_imputed: Optional[bool] = None
    scope: Optional[str] = None


class SukuyoFullmoonCalculation(PartialOutput):
    ruleset_id: Optional[str] = None
    lunar_month: Optional[int] = None
    lunar_day: Optional[int] = None
    fullmoon_day: Optional[int] = None
    fullmoon_mansion: Optional[str] = None
    signed_day_offset: Optional[int] = None
    direct_mansion: Optional[str] = None
    shortcut_inclusive_count: Optional[int] = None
    shortcut_one_based_remainder: Optional[int] = None
    shortcut_mansion: Optional[str] = None
    methods_agree: Optional[bool] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    source_bundle_sha256: Optional[str] = None
    direct_locator: Optional[str] = None
    shortcut_locator: Optional[str] = None
    scope: Optional[str] = None


class SukuyoCalendarProfile(PartialOutput):
    source_bundle_sha256: Optional[str] = None
    calendar_profile: Optional[str] = None
    mansion_method_id: Optional[str] = None
    host_calculation: Optional[SukuyoFullmoonCalculation] = None
    requested_leap_month_policy: Optional[str] = None
    effective_leap_month_policy: Optional[str] = None
    calendar_day_part: Optional[str] = None
    resolved: Optional[bool] = None
    resolution_reason: Optional[str] = None
    natal_su27: Optional[str] = None
    candidate_su27: Optional[str] = None
    candidate_su27s: Optional[List[str]] = None
    candidate_set_complete_under_declared_reconstructions: Optional[bool] = None
    short_month_assignment: Optional[Dict[str, Any]] = None
    hinoo_source: Optional[Dict[str, Any]] = None
    historical_calendar_reconstruction: Optional[bool] = None
    classical_full_profile_acceptance: Optional[bool] = None


class SukuyoDayCycleAnchor(PartialOutput):
    civil_ordinal: Optional[int] = None
    day_ganzhi: Optional[str] = None
    source_lunar_year_query: Optional[int] = None
    source_response_sha256: Optional[str] = None


class SukuyoHistoricalDayReference(PartialOutput):
    name: Optional[str] = None
    method_id: Optional[str] = None
    source_anchor: Optional[SukuyoDayCycleAnchor] = None
    elapsed_civil_days: Optional[int] = None
    reference_boundary: Optional[str] = None
    historical_day_boundary_accepted: Optional[bool] = None
    bazi_day_pillar_evaluated: Optional[bool] = None


class SukuyoCalendarReference(PartialOutput):
    manuscript_month_header: Optional[Dict[str, Any]] = None
    manuscript_daily_annotations: Optional[Dict[str, Any]] = None
    id: Optional[str] = None
    provider_calendar_id: Optional[str] = None
    source_url: Optional[str] = None
    calendar_metadata_url: Optional[str] = None
    source_archive_sha256: Optional[str] = None
    source_bundle_sha256: Optional[str] = None
    source_response_sha256: Optional[str] = None
    source_month_start_ordinal: Optional[int] = None
    source_month_length_days: Optional[int] = None
    day_cycle_anchor: Optional[SukuyoDayCycleAnchor] = None
    day_ganzhi_reference: Optional[SukuyoHistoricalDayReference] = None
    month_truncated_by_calendar_reform: Optional[bool] = None
    cross_source_comparison: Optional[Dict[str, Any]] = None
    cross_source_disagreement_dates: Optional[int] = None
    retained_disagreement_interval_count: Optional[int] = None
    complete_provider_advertised_historical_range: Optional[bool] = None
    public_datetime_year_zero_and_bce_inputs_supported: Optional[bool] = None
    supported_range_inclusive: Optional[List[str]] = None
    methodology_advertised_range_inclusive: Optional[List[str]] = None
    reference_day_count: Optional[int] = None
    source_provenance: Optional[List[Dict[str, Any]]] = None
    monthly_endpoint_reconciliation: Optional[List[Dict[str, Any]]] = None
    source_discrepancies_retained: Optional[List[str]] = None
    date_source_uri: Optional[str] = None
    date_provenance: Optional[str] = None
    calendar_reference_timezone: Optional[str] = None
    historical_local_time_reconstruction: Optional[bool] = None
    printed_lunar_year: Optional[int] = None
    lunar_year_is_gregorian_era_year: Optional[bool] = None
    historical_calendar_acceptance: Optional[bool] = None
    independent_whole_range_verification: Optional[bool] = None
    scope: Optional[str] = None


class SukuyoCalendar(PartialOutput):
    input_timezone_rules: Optional[Dict[str, str]] = None
    calendar_basis: Optional[str] = None
    calendar_reference: Optional[SukuyoCalendarReference] = None
    status: Optional[str] = None
    calendar_date: Optional[str] = None
    calendar_timezone: Optional[str] = None
    lunar_year: Optional[int] = None
    lunar_month: Optional[int] = None
    lunar_day: Optional[int] = None
    is_leap_month: Optional[bool] = None
    birth_time_known: Optional[bool] = None
    natal_su27: Optional[str] = None
    candidate_su27: Optional[str] = None
    candidate_su27s: Optional[List[str]] = None
    calendar_profile: Optional[str] = None
    mansion_method_id: Optional[str] = None
    calendar_day_part: Optional[str] = None
    resolution_reason: Optional[str] = None
    profile_calculation: Optional[SukuyoCalendarProfile] = None
    leap_month_policy: Optional[str] = None
    source_table_variant: Optional[SukuyoMonthTableVariant] = None
    printed_edition_reference: Optional[Dict[str, Any]] = None
    rule_trace: Optional[List[Dict[str, Any]]] = None
    date_support: Optional[SukuyoDateSupport] = None
    calendar_candidates: Optional[List[Dict[str, Any]]] = None
    out_of_range_calendar_dates: Optional[List[str]] = None


class SukuyoDetailMatch(PartialOutput):
    required_any_of: Optional[List[str]] = None
    required_all_of: Optional[List[str]] = None
    satisfied_details: Optional[List[str]] = None
    declared_satisfied_details: Optional[List[str]] = None
    implied_satisfied_details: Optional[List[str]] = None
    missing_all_of: Optional[List[str]] = None
    any_of_satisfied: Optional[bool] = None
    all_of_satisfied: Optional[bool] = None
    textual_reading_resolved: Optional[bool] = None
    applied_to_aggregate: Optional[bool] = None


class SukuyoActivityRule(PartialOutput):
    source_passages: Optional[List[Dict[str, Any]]] = None
    source_layer_bundle_sha256: Optional[str] = None
    rule_id: Optional[str] = None
    layer: Optional[str] = None
    selectors: Optional[List[Any]] = None
    activities: Optional[List[str]] = None
    assessment: Optional[str] = None
    locator: Optional[str] = None
    source_url: Optional[str] = None
    source_excerpt: Optional[str] = None
    source_excerpts: Optional[List[str]] = None
    meaning: Optional[str] = None
    volume: Optional[str] = None
    applicability: Optional[str] = None
    topic_condition: Optional[str] = None
    applicability_status: Optional[str] = None
    applied_to_aggregate: Optional[bool] = None
    activity_detail_any_of: Optional[List[str]] = None
    activity_detail_all_of: Optional[List[str]] = None
    matched_activity_details: Optional[List[str]] = None
    requires_textual_review: Optional[bool] = None
    activity_conditions: Optional[Dict[str, Any]] = None
    detail_match: Optional[SukuyoDetailMatch] = None
    direction: Optional[str] = None
    direction_binding_basis: Optional[str] = None
    direction_locator: Optional[str] = None
    literal_palace_ordinal: Optional[int] = None
    literal_palace_name: Optional[str] = None
    unparsed_selector_literals: Optional[List[str]] = None
    textual_variants: Optional[List[Dict[str, Any]]] = None
    textual_assessment_variant: Optional[bool] = None
    auspicious_time_cannot_release: Optional[bool] = None
    source_witness: Optional[str] = None


class SukuyoActivityLayer(PartialOutput):
    layer: Optional[str] = None
    status: Optional[str] = None
    rule_ids: Optional[List[str]] = None
    conditional_rule_ids: Optional[List[str]] = None


class SukuyoActivityAssessment(PartialOutput):
    clothing_source_bundle_sha256: Optional[str] = None
    activity: Optional[str] = None
    activity_details: Optional[List[str]] = None
    effective_activity_details: Optional[List[str]] = None
    detail_inferences: Optional[List[Dict[str, str]]] = None
    evidence_status: Optional[str] = None
    layers: Optional[List[SukuyoActivityLayer]] = None
    matched_rules: Optional[List[SukuyoActivityRule]] = None
    conditional_rules: Optional[List[SukuyoActivityRule]] = None
    conditional_rules_applied_to_aggregate: Optional[bool] = None
    textual_issues: Optional[List[Dict[str, Any]]] = None
    travel_direction_source_bundle_sha256: Optional[str] = None
    special_day_source_bundle_sha256: Optional[str] = None
    sanjiu_day_source_bundle_sha256: Optional[str] = None
    unresolved_source_rules_present: Optional[bool] = None


class SukuyoSpecialRow(PartialOutput):
    label: Optional[str] = None
    weekday_index: Optional[int] = None
    luminary: Optional[str] = None
    literal_mansion: Optional[str] = None
    mansion: Optional[str] = None
    source_main_literal: Optional[str] = None
    source_main_weekday_index: Optional[int] = None
    source_clause: Optional[str] = None
    locator: Optional[str] = None
    apparatus: Optional[List[Dict[str, Any]]] = None
    reading_status: Optional[str] = None
    witness_basis: Optional[str] = None
    source_clause_is_witness_reading: Optional[bool] = None
    candidate_readings: Optional[List[str]] = None
    candidate_readings_accepted_as_mansion: Optional[bool] = None


class SukuyoSpecialWitness(PartialOutput):
    witness: Optional[str] = None
    volume: Optional[str] = None
    edition: Optional[str] = None
    matched_labels: Optional[List[str]] = None
    matched_rows: Optional[List[SukuyoSpecialRow]] = None
    rows_for_weekday: Optional[List[SukuyoSpecialRow]] = None
    unresolved_rows: Optional[List[SukuyoSpecialRow]] = None
    labels_complete_for_selected_day: Optional[bool] = None
    applied_to_primary: Optional[bool] = None
    disagrees_with_primary: Optional[bool] = None
    source_reference: Optional[Dict[str, Any]] = None


class SukuyoSpecialCandidate(PartialOutput):
    mansion: Optional[str] = None
    matched_labels: Optional[List[str]] = None
    applied_to_primary: Optional[bool] = None


class SukuyoSpecialDays(PartialOutput):
    textual_position_reference: Optional[Dict[str, Any]] = None
    ruleset_id: Optional[str] = None
    status: Optional[str] = None
    mansion: Optional[str] = None
    weekday_index: Optional[int] = None
    primary: Optional[SukuyoSpecialWitness] = None
    comparisons: Optional[List[SukuyoSpecialWitness]] = None
    direct_printed_comparisons: Optional[List[SukuyoSpecialWitness]] = None
    candidate_primary: Optional[List[SukuyoSpecialCandidate]] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    source_bundle_sha256: Optional[str] = None
    selected_primary: Optional[str] = None
    selected_lower_activity_witness: Optional[str] = None
    weekday_basis: Optional[str] = None
    physical_lunar_conjunction_evaluated: Optional[bool] = None
    classical_daybreak_boundary_acceptance: Optional[bool] = None
    scope: Optional[str] = None


class SukuyoDirectionCandidate(PartialOutput):
    mansion: Optional[str] = None
    records: Optional[List[SukuyoActivityRule]] = None
    applied_to_primary: Optional[bool] = None


class SukuyoDirectionalTravel(PartialOutput):
    ruleset_id: Optional[str] = None
    status: Optional[str] = None
    mansion: Optional[str] = None
    selected_records: Optional[List[SukuyoActivityRule]] = None
    candidate_records: Optional[List[SukuyoDirectionCandidate]] = None
    basis: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    source_bundle_sha256: Optional[str] = None
    locator: Optional[str] = None
    selected_text: Optional[str] = None
    textual_issues: Optional[List[Dict[str, Any]]] = None
    direction_inferred: Optional[bool] = None
    physical_palace_computed: Optional[bool] = None
    scope: Optional[str] = None


class SukuyoNatureGroup(PartialOutput):
    name: Optional[str] = None
    literal_heading: Optional[str] = None
    members: Optional[List[str]] = None
    locator: Optional[str] = None
    source_excerpts: Optional[List[str]] = None
    textual_variants: Optional[List[Dict[str, Any]]] = None


class SukuyoLowerNature(PartialOutput):
    status: Optional[str] = None
    mansion: Optional[str] = None
    selected_group: Optional[SukuyoNatureGroup] = None
    upper_nature: Optional[str] = None
    membership_differs_from_upper: Optional[bool] = None
    membership_basis: Optional[str] = None
    cow_reference_not_applied_to_calendar: Optional[bool] = None


class SukuyoLowerWeekday(PartialOutput):
    luminary: Optional[str] = None
    literal_title: Optional[str] = None
    locator: Optional[str] = None
    basis: Optional[str] = None
    classical_daybreak_boundary_acceptance: Optional[bool] = None


class SukuyoLowerMethods(PartialOutput):
    ruleset_id: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    source_bundle_sha256: Optional[str] = None
    selected_text: Optional[str] = None
    nature: Optional[SukuyoLowerNature] = None
    weekday: Optional[SukuyoLowerWeekday] = None
    scope: Optional[str] = None


class SukuyoLowerMansion(PartialOutput):
    status: Optional[str] = None
    mansion: Optional[str] = None
    ruleset_id: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    locator: Optional[str] = None
    topic_rules: Optional[List[SukuyoActivityRule]] = None
    textual_issues: Optional[List[Dict[str, Any]]] = None
    mapping_notes: Optional[List[str]] = None
    scope: Optional[str] = None


class SukuyoConjunctionGroup(PartialOutput):
    id: Optional[str] = None
    label: Optional[str] = None
    members: Optional[List[str]] = None
    membership_basis: Optional[str] = None
    locator: Optional[str] = None
    meaning: Optional[str] = None


class SukuyoConjunctionCandidate(PartialOutput):
    mansion: Optional[str] = None
    group: Optional[SukuyoConjunctionGroup] = None
    applied_to_primary: Optional[bool] = None


class SukuyoConjunctionDoctrine(PartialOutput):
    ruleset_id: Optional[str] = None
    status: Optional[str] = None
    mansion: Optional[str] = None
    selected_group: Optional[SukuyoConjunctionGroup] = None
    candidate_groups: Optional[List[SukuyoConjunctionCandidate]] = None
    basis: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    locator: Optional[str] = None
    angular_offset_degrees: Optional[float] = None
    physical_evaluation_status: Optional[str] = None
    applied_to_physical_moon: Optional[bool] = None
    scope: Optional[str] = None


class SukuyoPalace(PartialOutput):
    ordinal: Optional[int] = None
    name: Optional[str] = None
    literal_name: Optional[str] = None
    ruler_literal: Optional[str] = None
    ruler_luminary: Optional[str] = None
    division: Optional[str] = None
    locator: Optional[str] = None
    textual_variants: Optional[List[Dict[str, Any]]] = None


class SukuyoPadaCell(PartialOutput):
    mansion: Optional[str] = None
    pada: Optional[int] = None
    palace_ordinal: Optional[int] = None
    palace_name: Optional[str] = None
    ruler_luminary: Optional[str] = None
    locator: Optional[str] = None


class SukuyoPalaceReference(PartialOutput):
    ruleset_id: Optional[str] = None
    status: Optional[str] = None
    basis: Optional[str] = None
    mansion: Optional[str] = None
    mansion_candidates: Optional[List[str]] = None
    textual_pada: Optional[int] = None
    candidate_set_complete_within_calendar_profile: Optional[bool] = None
    selected_palace: Optional[SukuyoPalace] = None
    candidate_palaces: Optional[List[SukuyoPalace]] = None
    rows: Optional[List[SukuyoPadaCell]] = None
    pada_numbering_basis: Optional[str] = None
    pada_ordinals_explicit_in_source: Optional[bool] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    locator: Optional[str] = None
    applied_to_calendar_mansion: Optional[bool] = None
    applied_to_sanjiu: Optional[bool] = None
    applied_to_modern_chart: Optional[bool] = None
    birth_pada_established: Optional[bool] = None
    physical_longitude_status: Optional[str] = None
    scope: Optional[str] = None


class SukuyoSanjiuDayWitness(PartialOutput):
    volume: Optional[str] = None
    source_witness: Optional[str] = None
    locator: Optional[str] = None
    source_excerpts: Optional[List[str]] = None
    meaning: Optional[str] = None
    primary_paragraph_id: Optional[str] = None


class SukuyoSanjiuDayEvidence(PartialOutput):
    ruleset_id: Optional[str] = None
    relation: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    source_bundle_sha256: Optional[str] = None
    witnesses: Optional[List[SukuyoSanjiuDayWitness]] = None
    upper_day_entry_individually_listed: Optional[bool] = None
    priority_clause: Optional[SukuyoSanjiuDayWitness] = None
    priority_clause_applied_to_aggregate: Optional[bool] = None
    scope: Optional[str] = None


class SukuyoPersonalDay(PartialOutput):
    relation: Optional[Dict[str, Any]] = None
    source_day_evidence: Optional[SukuyoSanjiuDayEvidence] = None
    upper_volume: Optional[Dict[str, Any]] = None
    textual_conflict: Optional[bool] = None
    lower_volume_variant: Optional[Dict[str, Any]] = None
    scope: Optional[str] = None


class SukuyoSixPalaceMember(PartialOutput):
    name: Optional[str] = None
    inclusive_ordinal: Optional[int] = None
    mansion: Optional[str] = None
    locator: Optional[str] = None


class SukuyoJointReadingRequirement(PartialOutput):
    source_excerpt: Optional[str] = None
    locator: Optional[str] = None
    evaluated: Optional[bool] = None


class SukuyoSixPalaceReference(PartialOutput):
    ruleset_id: Optional[str] = None
    status: Optional[str] = None
    natal_mansion: Optional[str] = None
    members: Optional[List[SukuyoSixPalaceMember]] = None
    counting_basis: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    source_bundle_sha256: Optional[str] = None
    locator: Optional[str] = None
    counting_excerpt: Optional[str] = None
    joint_reading_requirement: Optional[SukuyoJointReadingRequirement] = None
    seven_luminary_transits_evaluated: Optional[bool] = None
    applied_to_day_assessment: Optional[bool] = None
    scope: Optional[str] = None


class SukuyoTaibaiWitness(PartialOutput):
    witness: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None
    horizontal_direction: Optional[str] = None
    realm: Optional[str] = None
    source_excerpt: Optional[str] = None
    locator: Optional[str] = None
    reading_complete_for_selected_day: Optional[bool] = None
    applied_to_primary: Optional[bool] = None


class SukuyoTaibaiReference(PartialOutput):
    ruleset_id: Optional[str] = None
    status: Optional[str] = None
    lunar_day: Optional[int] = None
    selected_witness: Optional[str] = None
    location: Optional[str] = None
    horizontal_direction: Optional[str] = None
    realm: Optional[str] = None
    row_id: Optional[str] = None
    row_lunar_days: Optional[List[int]] = None
    witnesses: Optional[List[SukuyoTaibaiWitness]] = None
    witnesses_agree_for_selected_day: Optional[bool] = None
    title_literal: Optional[str] = None
    table_apparatus: Optional[List[Dict[str, Any]]] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    source_bundle_sha256: Optional[str] = None
    locator: Optional[str] = None
    publisher_primary: Optional[Dict[str, Any]] = None
    doctrine: Optional[Dict[str, Any]] = None
    physical_venus_position_evaluated: Optional[bool] = None
    astronomical_retrograde_evaluated: Optional[bool] = None
    movement_alignment_evaluated: Optional[bool] = None
    applied_to_activity_assessment: Optional[bool] = None
    independent_ming_edition_collated: Optional[bool] = None
    scope: Optional[str] = None


class SukuyoClothingVerse(PartialOutput):
    mansion: Optional[str] = None
    literal_mansion: Optional[str] = None
    taisho_text: Optional[str] = None
    ming_apparatus_text: Optional[str] = None
    locator: Optional[str] = None


class SukuyoClothingWitness(PartialOutput):
    witness: Optional[str] = None
    membership: Optional[str] = None
    assessment: Optional[str] = None
    source_excerpt: Optional[str] = None
    applied_to_primary: Optional[bool] = None
    unlisted_complement_assessment: Optional[str] = None


class SukuyoClothingCandidate(PartialOutput):
    mansion: Optional[str] = None
    verse: Optional[SukuyoClothingVerse] = None
    upper_literal_cutting_statement: Optional[Dict[str, Any]] = None
    primary_assessment: Optional[str] = None
    comparisons: Optional[List[SukuyoClothingWitness]] = None


class SukuyoClothingReference(PartialOutput):
    ruleset_id: Optional[str] = None
    status: Optional[str] = None
    mansion: Optional[str] = None
    candidate_mansions: Optional[List[str]] = None
    candidate_set_complete_under_declared_profile: Optional[bool] = None
    primary_assessment: Optional[str] = None
    selected_witness: Optional[str] = None
    candidate_references: Optional[List[SukuyoClothingCandidate]] = None
    primary_positive_mansions: Optional[List[str]] = None
    ming_literal_list: Optional[List[str]] = None
    ming_unresolved_tokens: Optional[List[str]] = None
    ming_unlisted_complement_assessment: Optional[str] = None
    verse_and_literal_forecasts_applied_to_aggregate: Optional[bool] = None
    independent_ming_edition_collated: Optional[bool] = None
    historical_clock_mapping_evaluated: Optional[bool] = None
    real_world_event_prediction_evaluated: Optional[bool] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    source_bundle_sha256: Optional[str] = None
    locator: Optional[str] = None
    unmapped_clothing_predicates: Optional[List[Dict[str, Any]]] = None
    scope: Optional[str] = None


class SukuyoDay(PartialOutput):
    kenyu_lingbi_reference: Optional[Dict[str, Any]] = None
    clothing_reference: Optional[SukuyoClothingReference] = None
    calendar: Optional[SukuyoCalendar] = None
    calendar_day: Optional[SukuyoCalendarDay] = None
    day_mansion: Optional[str] = None
    nature: Optional[str] = None
    lunar_half: Optional[str] = None
    half_day: Optional[int] = None
    weekday: Optional[Dict[str, Any]] = None
    special_day_labels: Optional[List[str]] = None
    special_day_evidence: Optional[SukuyoSpecialDays] = None
    rule_trace: Optional[List[Dict[str, Any]]] = None
    personal_day: Optional[SukuyoPersonalDay] = None
    six_palace_reference: Optional[SukuyoSixPalaceReference] = None
    taibai_direction_reference: Optional[SukuyoTaibaiReference] = None
    activity_assessment: Optional[SukuyoActivityAssessment] = None
    lower_mansion_day: Optional[SukuyoLowerMansion] = None
    lower_methods: Optional[SukuyoLowerMethods] = None
    directional_travel: Optional[SukuyoDirectionalTravel] = None
    conjunction_doctrine: Optional[SukuyoConjunctionDoctrine] = None
    palace_reference: Optional[SukuyoPalaceReference] = None
    reading_text: Optional[str] = None
    candidate_days: Optional[List[Dict[str, Any]]] = None
    candidate_mansion_days: Optional[List[Dict[str, Any]]] = None


class SuzhanAstronomyBody(PartialOutput):
    id: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    right_ascension: Optional[float] = None
    declination: Optional[float] = None
    mansion: Optional[GuolaoMansion] = None


class SuzhanAstronomy(PartialOutput):
    method_id: Optional[str] = None
    coordinate_frame: Optional[str] = None
    julian_day_tt: Optional[float] = None
    julian_day_ut1: Optional[float] = None
    utc_datetime: Optional[str] = None
    bodies: Optional[List[SuzhanAstronomyBody]] = None
    boundaries: Optional[List[GuolaoBoundary]] = None
    classical_boundary_acceptance: Optional[bool] = None


class SukuyoPerson(PartialOutput):
    name: Optional[str] = None
    natal_su27: Optional[str] = None
    calendar: Optional[SukuyoCalendar] = None
    palace_reference: Optional[SukuyoPalaceReference] = None


class SukuyoRelation(PartialOutput):
    relation: Optional[str] = None
    pair: Optional[str] = None
    distance: Optional[str] = None
    meaning: Optional[str] = None
    self_su27: Optional[str] = None
    other_su27: Optional[str] = None
    offset: Optional[int] = None
    sequence_group: Optional[int] = None
    traditional_assessment: Optional[str] = None
    rule_trace: Optional[List[Dict[str, Any]]] = None


class SukuyoJointPersonSupport(PartialOutput):
    calendar_date: Optional[str] = None
    calendar_day_part: Optional[str] = None
    natal_su27: Optional[str] = None
    assignment_origin: Optional[str] = None


class SukuyoJointSupport(PartialOutput):
    reconstruction_id: Optional[str] = None
    person1: Optional[SukuyoJointPersonSupport] = None
    person2: Optional[SukuyoJointPersonSupport] = None


class SukuyoSharedReconstruction(PartialOutput):
    method_id: Optional[str] = None
    status: Optional[str] = None
    model_ids: Optional[List[str]] = None
    model_identity: Optional[Dict[str, Any]] = None
    assumption: Optional[str] = None
    person_half_days_independent: Optional[bool] = None
    source_priority_established: Optional[bool] = None
    historical_uniformity_established: Optional[bool] = None
    unconstrained_row_count: Optional[int] = None
    supported_row_count: Optional[int] = None
    unsupported_row_count: Optional[int] = None
    support_coverage_complete: Optional[bool] = None
    resolved_support: Optional[List[SukuyoJointSupport]] = None
    reason: Optional[str] = None


class SukuyoCandidateRelation(PartialOutput):
    person1_su27: Optional[str] = None
    person2_su27: Optional[str] = None
    person1_to_person2: Optional[SukuyoRelation] = None
    person2_to_person1: Optional[SukuyoRelation] = None
    pair: Optional[str] = None
    applied_to_primary: Optional[bool] = None
    person1_calendar_dates: Optional[List[str]] = None
    person2_calendar_dates: Optional[List[str]] = None
    shared_reconstruction_ids: Optional[List[str]] = None
    joint_support_status: Optional[str] = None
    joint_support: Optional[List[SukuyoJointSupport]] = None


class SukuyoCandidateAnalysis(PartialOutput):
    status: Optional[str] = None
    candidate_set_complete_within_profile: Optional[bool] = None
    rows: Optional[List[SukuyoCandidateRelation]] = None
    scope: Optional[str] = None
    calendar_date_uncertainty_remains: Optional[bool] = None
    unconstrained_rows: Optional[List[SukuyoCandidateRelation]] = None
    shared_reconstruction_analysis: Optional[SukuyoSharedReconstruction] = None


class KnowledgeCategory(PartialOutput):
    name: Optional[str] = None
    count: Optional[int] = None
    keys: Optional[List[str]] = None
    keys_sample: Optional[List[str]] = None
    supports: Optional[List[str]] = None
    keys_complete: Optional[bool] = None
    key_format: Optional[str] = None
    reference_only: Optional[bool] = None
    coverage: Optional[Dict[str, JsonValue]] = None


class KnowledgeCoverage(PartialOutput):
    domain: Optional[str] = None
    categories: Optional[List[KnowledgeCategory]] = None
    missing_categories: Optional[List[str]] = None
    fallback_categories: Optional[List[str]] = None


def _reference_boolean(value: Any) -> Any:
    if type(value) is not bool:
        raise ValueError("来源参考布尔事实不能用数字或字符串替代。")
    return value


ReferenceTrue = Annotated[Literal[True], BeforeValidator(_reference_boolean)]
ReferenceFalse = Annotated[Literal[False], BeforeValidator(_reference_boolean)]


class KnowledgeSourceRecord(PartialOutput):
    domain: Optional[str] = None
    key: Optional[str] = None
    source_path: Optional[str] = None
    canonical_content_sha256: Optional[str] = None
    loaded_file_sha256: Optional[str] = None
    source_kind: Optional[str] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    source_pdf_sha256: Optional[str] = None
    source_revision: Optional[JsonValue] = None
    review_status: Optional[str] = None
    scope: Optional[str] = None
    source_witnesses: Optional[JsonValue] = None


class NumerologyKnowledgeDetails(PartialOutput):
    policy_id: Optional[Literal["numerology_source_reference_v1"]] = None
    reference_only: Optional[ReferenceTrue] = None
    personal_applicability_assessed: Optional[ReferenceFalse] = None
    record: Optional[Dict[str, JsonValue]] = None


class HumanDesignKnowledgeDetails(PartialOutput):
    policy_id: Optional[Literal["human_design_line_reference_v1"]] = None
    reference_only: Optional[ReferenceTrue] = None
    personal_applicability_assessed: Optional[ReferenceFalse] = None
    record: Optional[Dict[str, JsonValue]] = None


class KnowledgeProvenance(PartialOutput):
    source_domain: Optional[str] = None
    domain: Optional[str] = None
    category: Optional[str] = None
    key: Optional[str] = None
    build_timestamp: Optional[str] = None
    upstream_source_marker: Optional[str] = None
    bundle_version: Optional[int] = None
    coverage: Optional[KnowledgeCoverage] = None
    reference_policy_id: Optional[
        Literal["numerology_source_reference_v1", "human_design_line_reference_v1"]
    ] = None
    source_catalogue_version: Optional[int] = None
    source_catalogue_content_sha256: Optional[str] = None
    source_records: Optional[List[KnowledgeSourceRecord]] = None
    reference_only: Optional[ReferenceTrue] = None
    personal_applicability_assessed: Optional[ReferenceFalse] = None
    whole_books_collated: Optional[ReferenceFalse] = None
    independent_whole_corpus_review_completed: Optional[ReferenceFalse] = None
    real_world_efficacy_validated: Optional[ReferenceFalse] = None
    scope: Optional[str] = None


class KnowledgeDomain(PartialOutput):
    domain: Optional[str] = None
    source: Optional[str] = None
    bundle_version: Optional[int] = None
    provenance: Optional[KnowledgeProvenance] = None
    categories: Optional[List[KnowledgeCategory]] = None


class KnowledgeQuery(PartialOutput):
    key: Optional[str] = None
    object_a: Optional[str] = None
    object_b: Optional[str] = None
    jiang_name: Optional[str] = None
    tian_branch: Optional[str] = None
    di_branch: Optional[str] = None


class PlanetInfoSetting(PartialOutput):
    showHouse: Optional[int] = None
    showRuler: Optional[int] = None


class AstroMeaningSetting(PartialOutput):
    enabled: Optional[int] = None


class ExportSettingsTemplate(PartialOutput):
    sections: Optional[List[str]] = None
    planetInfo: Optional[PlanetInfoSetting] = None
    astroMeaning: Optional[AstroMeaningSetting] = None


class ExportTechnique(PartialOutput):
    key: Optional[str] = None
    label: Optional[str] = None
    astro_meaning_title: Optional[str] = None
    astro_meaning_checkbox: Optional[str] = None
    preset_sections: Optional[List[str]] = None
    forbidden_sections: Optional[List[str]] = None
    supports_planet_info: Optional[bool] = None
    supports_astro_meaning: Optional[bool] = None
    supports_hover_meaning: Optional[bool] = None
    planet_info_default: Optional[PlanetInfoSetting] = None
    astro_meaning_default: Optional[AstroMeaningSetting] = None
    settings_template: Optional[ExportSettingsTemplate] = None


class NormalizedExportSettings(PartialOutput):
    version: Optional[int] = None
    sections: Optional[Dict[str, List[str]]] = None
    planetInfo: Optional[Dict[str, PlanetInfoSetting]] = None
    astroMeaning: Optional[Dict[str, AstroMeaningSetting]] = None


class ExportSection(PartialOutput):
    index: Optional[int] = None
    raw_title: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    included: Optional[bool] = None


class SnapshotExport(PartialOutput):
    technique: Optional[ExportTechnique] = None
    settings_used: Optional[NormalizedExportSettings] = None
    selected_sections: Optional[List[str]] = None
    section_titles_detected: Optional[List[str]] = None
    unknown_detected_sections: Optional[List[str]] = None
    missing_selected_sections: Optional[List[str]] = None
    sections: Optional[List[ExportSection]] = None
    export_text: Optional[str] = None


REFERENCE_TOOL_FIELDS: Dict[str, Dict[str, Any]] = {
    "suzhan": {"sukuyo": SukuyoDay, "astronomy": SuzhanAstronomy},
    "sukuyo_compatibility": {
        "calendar_basis": str,
        "status": str,
        "person1": SukuyoPerson,
        "person2": SukuyoPerson,
        "person1_to_person2": SukuyoRelation,
        "person2_to_person1": SukuyoRelation,
        "candidate_relation_analysis": SukuyoCandidateAnalysis,
        "pair": str,
        "summary": str,
    },
    "knowledge_registry": {
        "domains": List[KnowledgeDomain],
        "provenance": KnowledgeProvenance,
    },
    "knowledge_read": {
        "query_normalized": KnowledgeQuery,
        "provenance": KnowledgeProvenance,
        "lines": List[str],
        "tips": List[str],
        "reference_only": ReferenceTrue,
        "reference_details": Union[
            NumerologyKnowledgeDetails, HumanDesignKnowledgeDetails
        ],
    },
    "export_registry": {
        "techniques": List[ExportTechnique],
        "selected_technique": ExportTechnique,
        "planet_info_default": PlanetInfoSetting,
        "astro_meaning_default": AstroMeaningSetting,
        "default_normalized_settings": NormalizedExportSettings,
        "jieqi_split_keys": List[str],
    },
    "export_parse": {
        "technique": ExportTechnique,
        "settings_used": NormalizedExportSettings,
        "sections": List[ExportSection],
        "selected_sections": List[str],
        "section_titles_detected": List[str],
        "unknown_detected_sections": List[str],
        "missing_selected_sections": List[str],
    },
}
