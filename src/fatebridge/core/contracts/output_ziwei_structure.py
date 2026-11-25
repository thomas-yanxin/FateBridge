"""Ziwei natal structure and interpretation evidence."""

from typing import Annotated, Literal

from pydantic import Field

from fatebridge.core.contracts.output_base import (
    FULL_FACT,
    OpenJsonValue,
    PartialOutput,
)
from fatebridge.core.contracts.output_chinese_calendar import LunarDate
from fatebridge.core.contracts.output_ziwei_calendar import ZiweiCalendarBasis
from fatebridge.core.contracts.output_ziwei_palaces import (
    ZiweiChartMasters,
    ZiweiCycleRules,
    ZiweiCycleSourceComparison,
    ZiweiPosition,
    ZiweiRuleset,
    ZiweiRuleTrace,
    ZiweiSihuaSourceComparison,
    ZiweiStar,
    ZiweiStructuralEvidence,
    ZiweiSymbolicProperties,
)


class ZiweiMingEntity(PartialOutput):
    kind: str | None = None
    name: str | None = None


class ZiweiMingDefinition(PartialOutput):
    id: str | None = None
    frame: int | None = None
    quote: str | None = None
    elements: list[str] | None = None
    entities: list[ZiweiMingEntity] | None = None
    glyph_note: str | None = None
    source_names: list[str] | None = None
    name_mapping: str | None = None
    identity_note: str | None = None
    quote_scope: str | None = None
    unresolved_tail_candidates: list[str] | None = None
    unresolved_tail_note: str | None = None
    element_status: str | None = None


class ZiweiMingOccurrence(PartialOutput):
    kind: str | None = None
    name: str | None = None
    definition_id: str | None = None
    star: str | None = None
    natal_palace_name: str | None = None
    natal_branch: str | None = None
    natal_mutagen: str | None = None
    calculation_path: str | None = None


class ZiweiLianzhenReading(PartialOutput):
    definition_id: str | None = None
    frame: int | None = None
    quote: str | None = None
    calculation_path: str | None = None
    natal_palace_name: str | None = None
    natal_branch: str | None = None
    at_career_palace: bool | None = None
    at_ming_branch: bool | None = None
    at_shen_branch: bool | None = None
    selected_mingshen_reading: str | None = None
    mingshen_reading_independently_adjudicated: bool | None = None
    applicable_terms_given_selected_reading: list[str] | None = None
    terms_are_new_palace_names: bool | None = None


class ZiweiQishaReading(PartialOutput):
    definition_id: str | None = None
    frame: int | None = None
    quote: str | None = None
    qisha_calculation_path: str | None = None
    ziwei_calculation_path: str | None = None
    separation_steps: int | None = None
    same_palace: bool | None = None
    opposite_palace: bool | None = None
    trine: bool | None = None
    source_encounter_geometry_defined: bool | None = None
    condition_match: bool | None = None
    unresolved_reason: str | None = None
    actual_qisha_mutagen: str | None = None
    symbolic_quan_is_new_sihua_assignment: bool | None = None


class ZiweiMingConditionalReadings(PartialOutput):
    lianzhen: ZiweiLianzhenReading | None = None
    qisha: ZiweiQishaReading | None = None


class ZiweiMingCountNote(PartialOutput):
    printed_quote: str | None = None
    printed_count: int | None = None
    enumerated_modern_star_names: int | None = None
    status: str | None = None


class ZiweiUnresolvedRelation(PartialOutput):
    definition_id: str | None = None
    source_phrase: str | None = None
    condition_match: bool | None = None
    status: str | None = None


class ZiweiMingProperties(PartialOutput):
    method_id: str | None = None
    version: str | None = None
    source: str | None = None
    source_title: str | None = None
    printed_volume: str | None = None
    source_section: str | None = None
    manual_reader_count: int | None = None
    scope: str | None = None
    definitions: dict[str, ZiweiMingDefinition] | None = None
    occurrences: list[ZiweiMingOccurrence] | None = None
    unlocated_natal_source_stars: list[str] | None = None
    unresolved_boshi_labels: list[str] | None = None
    unassigned_source_labels: list[str] | None = None
    conditional_readings: ZiweiMingConditionalReadings | None = None
    unresolved_relational_definitions: list[ZiweiUnresolvedRelation] | None = None
    name_mapping: dict[str, str] | None = None
    positive_star_count_note: ZiweiMingCountNote | None = None
    source_elements_replace_bureau_or_star_brightness: bool | None = None
    source_taxonomy_applied_to_modern_classification: bool | None = None
    symbolic_verbs_create_sihua_assignments: bool | None = None
    actual_assignments_modified: bool | None = None
    full_section_transcription_certified: bool | None = None
    whole_book_acceptance_passed: bool | None = None


class ZiweiXunVoid(PartialOutput):
    source_branches: list[str] | None = None
    displayed_star_branches: list[str] | None = None
    display_rule: str | None = None
    source: str | None = None


class ZiweiVoidSystems(PartialOutput):
    xun: ZiweiXunVoid | None = None
    source_name_mapping: dict[str, str] | None = None


class ZiweiPalace(PartialOutput):
    name: Annotated[str | None, FULL_FACT] = None
    ganzhi: Annotated[str | None, FULL_FACT] = None
    daxian: str | None = None
    daxian_period: int | None = None
    stars: list[str] | None = None
    stars_detail: list[ZiweiStar] | None = None
    structural_evidence: ZiweiStructuralEvidence | None = None
    changsheng12: str | None = None
    boshi12: str | None = None


class ZiweiReadingPalace(PartialOutput):
    name: str | None = None
    ganzhi: str | None = None
    stars: list[ZiweiStar] | None = None
    major_stars: list[str] | None = None
    sanfang_sizheng_branches: list[str] | None = None
    changsheng12: str | None = None
    boshi12: str | None = None
    daxian: str | None = None


class ZiweiReadingView(PartialOutput):
    schema_version: str | None = None
    null_star_fields_omitted: list[str] | None = None
    sanfang_branch_order: list[str] | None = None
    palaces: list[ZiweiReadingPalace] | None = None
    star_occurrence_count: int | None = None
    distinct_star_count: int | None = None


class ZiweiCalendarRules(PartialOutput):
    late_zi: str | None = None
    leap_month: str | None = None
    year_boundary: str | None = None
    effective_birth_month: int | None = None


class WuxingJu(PartialOutput):
    element: str | None = None
    label: str | None = None
    nayin: str | None = None
    number: int | None = None


class ZiweiAuxPlacementSourceRow(PartialOutput):
    star: str | None = None
    basis_id: str | None = None
    actual_branch: str | None = None
    expected_branch: str | None = None
    matches_source_rule: bool | None = None
    calculation_path: str | None = None
    unresolved_reason: str | None = None


class ZiweiAuxPlacementSources(PartialOutput):
    method_id: str | None = None
    version: str | None = None
    source: str | None = None
    printed_volume: str | None = None
    scope: str | None = None
    inputs: dict[str, OpenJsonValue] | None = None
    methods: dict[str, OpenJsonValue] | None = None
    placements: list[ZiweiAuxPlacementSourceRow] | None = None
    source_name_mapping: dict[str, str] | None = None
    unchecked_star_names: list[str] | None = None
    manual_reader_count: int | None = None
    compared_rules_applied: bool | None = None
    whole_book_conformance_claimed: bool | None = None


class ZiweiConditionOccurrence(PartialOutput):
    star: str | None = None
    natal_palace_name: str | None = None
    natal_branch: str | None = None
    natal_mutagen: str | None = None
    calculation_path: str | None = None


class ZiweiConditionExample(PartialOutput):
    ming: str | None = None
    positions: dict[str, str] | None = None


class ZiweiStructuralConditionIndex(PartialOutput):
    id: str | None = None
    source_frame: int | None = None
    source_quote: str | None = None
    geometry_match: bool | None = None
    evaluated_necessary_premises_match: bool | None = None
    source_literal_example_matches: bool | None = None
    source_qualifications_not_evaluated: list[str] | None = None
    full_traditional_judgment: None = None
    source_outcome_claim_adopted: Literal[False] | None = None


class ZiweiConditionAnnotationRevision(PartialOutput):
    prior_annotation: str | None = None
    reader_annotations: list[str] | None = None
    status: (
        Literal[
            "unresolved_after_independent_rereading",
            "corrected_after_independent_rereading",
        ]
        | None
    ) = None
    reason: str | None = None


class ZiweiConditionSourceRevision(PartialOutput):
    id: str | None = None
    source_manifest_sha256: str | None = None
    first_reading_sha256: str | None = None
    primary_review_sha256: str | None = None
    peer_review_sha256: str | None = None
    prior_collation_sha256: str | None = None
    prior_compiled_sha256: str | None = None
    changed_clause_ids: list[str] | None = None
    isolated_model_readers: int | None = None
    external_human_experts: Literal[0] | None = None
    new_witnesses: Literal[0] | None = None
    numeric_or_geometric_rules_modified: Literal[False] | None = None
    whole_book_acceptance_passed: Literal[False] | None = None


class ZiweiStructuralConditionRecord(ZiweiStructuralConditionIndex):
    source_annotation: str | None = None
    annotation_revision: ZiweiConditionAnnotationRevision | None = None
    geometry_rule: str | None = None
    actual_occurrences: dict[str, list[ZiweiConditionOccurrence]] | None = None
    ming_branch_requirement_met: bool | None = None
    year_stem_requirement_met: bool | None = None
    literal_example: ZiweiConditionExample | None = None
    missing_or_duplicated_stars: list[str] | None = None


class ZiweiStructuralConditions(PartialOutput):
    method_id: str | None = None
    version: str | None = None
    source: str | None = None
    source_title: str | None = None
    source_section: str | None = None
    source_section_is_editorial_label: bool | None = None
    source_status: str | None = None
    manual_reader_count: int | None = None
    source_revision: ZiweiConditionSourceRevision | None = None
    ming_branch: str | None = None
    year_stem: str | None = None
    adjacent_branches: list[str] | None = None
    flanking_reading: str | None = None
    index: list[ZiweiStructuralConditionIndex] | None = None
    records: list[ZiweiStructuralConditionRecord] | None = None
    scope: str | None = None
    actual_assignments_modified: Literal[False] | None = None
    whole_book_acceptance_passed: Literal[False] | None = None
    real_world_efficacy: str | None = None


class ZiweiBirth(PartialOutput):
    engine: Annotated[str | None, FULL_FACT] = None
    calendar_basis: Annotated[ZiweiCalendarBasis | None, FULL_FACT] = None
    calendar_rules: Annotated[ZiweiCalendarRules | None, FULL_FACT] = None
    ruleset: Annotated[ZiweiRuleset | None, FULL_FACT] = None
    rule_trace: Annotated[list[ZiweiRuleTrace] | None, FULL_FACT] = None
    reading_view: ZiweiReadingView | None = None
    symbolic_properties: ZiweiSymbolicProperties | None = None
    ming_textual_properties: ZiweiMingProperties | None = None
    ming_structural_conditions: ZiweiStructuralConditions | None = None
    sihua_source_comparison: ZiweiSihuaSourceComparison | None = None
    auxiliary_placement_sources: ZiweiAuxPlacementSources | None = None
    void_systems: ZiweiVoidSystems | None = None
    chart_masters: ZiweiChartMasters | None = None
    calendar_cycles: ZiweiCycleRules | None = None
    cycle_source_comparison: ZiweiCycleSourceComparison | None = None
    daxian_direction: str | None = None
    hour_branch: str | None = None
    lunar_date: LunarDate | None = None
    ming_gong: Annotated[ZiweiPosition | None, FULL_FACT] = None
    shen_gong: Annotated[ZiweiPosition | None, FULL_FACT] = None
    palaces: Annotated[list[ZiweiPalace] | None, FULL_FACT] = Field(
        default=None,
        min_length=12,
        max_length=12,
        json_schema_extra={"x-fatebridge-full-result-unique-by": "name"},
    )
    sihua: dict[str, str] | None = None
    time_algorithm: str | None = None
    wuxing_ju: Annotated[WuxingJu | None, FULL_FACT] = None
    year_stem: str | None = None
