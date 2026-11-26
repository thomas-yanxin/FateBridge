"""Sukuyo activities, source rules and special days."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput


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
    source_layer_bundle_sha256: str | None = None
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
    clothing_source_bundle_sha256: str | None = None
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
    travel_direction_source_bundle_sha256: str | None = None
    special_day_source_bundle_sha256: str | None = None
    sanjiu_day_source_bundle_sha256: str | None = None
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
    source_sha256: str | None = None
    source_bundle_sha256: str | None = None
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
    source_sha256: str | None = None
    source_bundle_sha256: str | None = None
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
    source_sha256: str | None = None
    source_bundle_sha256: str | None = None
    selected_text: str | None = None
    nature: SukuyoLowerNature | None = None
    weekday: SukuyoLowerWeekday | None = None
    scope: str | None = None


class SukuyoLowerMansion(PartialOutput):
    status: str | None = None
    mansion: str | None = None
    ruleset_id: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
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
    source_sha256: str | None = None
    locator: str | None = None
    angular_offset_degrees: float | None = None
    physical_evaluation_status: str | None = None
    applied_to_physical_moon: bool | None = None
    scope: str | None = None
