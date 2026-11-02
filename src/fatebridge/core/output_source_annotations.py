"""Typed source-comparison facts, distinct from a calculated strength grade."""

from typing import Dict, List, Literal, Optional

from pydantic import JsonValue, field_validator, model_validator

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_branch_candidates import (
    BranchCombinationCandidates,
    physical_branch_mapping,
    validate_effect_links,
    validate_punishment_resolution,
)
from fatebridge.core.output_energy_provenance import EnergyProvenance, bind_assessment
from fatebridge.core.output_source_conditions import SourceConditionReview
from fatebridge.core.punishment_resolution import POLICY as PUNISHMENT_POLICY
from fatebridge.core.punishment_resolution import (
    PREVIOUS_POLICY as PREVIOUS_PUNISHMENT_POLICY,
)
from fatebridge.core.punishment_resolution import (
    PREVIOUS_STRENGTH_METHOD as PREVIOUS_PUNISHMENT_METHOD,
)
from fatebridge.core.punishment_resolution import STRENGTH_METHOD as PUNISHMENT_METHOD

Grade = Literal["强", "中和", "弱"]


class SourceReference(PartialOutput):
    title: Optional[str] = None
    edition: Optional[str] = None
    url: Optional[str] = None
    source_id: Optional[str] = None
    pdf_pages: Optional[List[int]] = None
    locator: Optional[str] = None
    registered_document: Optional[str] = None
    registered_document_sha256: Optional[str] = None
    whole_pdf_sha256: Optional[str] = None
    identity_evidence: Optional[str] = None
    identity_evidence_sha256: Optional[str] = None
    registered_document_scope: Optional[
        Literal["original_transcription_before_input_revision"]
    ] = None


class SourceInputReadingRevision(PartialOutput):
    revision_id: Optional[Literal["ditian_1947_six_reviewed_inputs_v1"]] = None
    source_input_plan_path: Optional[str] = None
    source_input_plan_sha256: Optional[str] = None
    review_path: Optional[str] = None
    review_sha256: Optional[str] = None
    reason: Optional[str] = None
    old_image_sha256: Optional[str] = None
    additional_image_sha256: Optional[str] = None
    original_pdf_page: Optional[int] = None
    additional_scan_leaf: Optional[int] = None
    original_source_record: Optional[Dict[str, JsonValue]] = None
    original_index_record: Optional[Dict[str, JsonValue]] = None
    source_strength_label_assigned: Optional[Literal[False]] = None
    independent_edition_or_expert_review: Optional[Literal[False]] = None
    new_independent_validation_credit: Optional[Literal[0]] = None


class SourceStrengthConstraint(PartialOutput):
    constraint_id: Optional[str] = None
    reference_id: Optional[str] = None
    annotation_location: Optional[str] = None
    forbidden_strengths: Optional[List[Grade]] = None
    retained_anchor: Optional[str] = None
    retained_context: Optional[str] = None
    source_reference: Optional[SourceReference] = None
    original_annotation: Optional[Dict[str, JsonValue]] = None
    does_not_assign_an_exact_source_label: Optional[Literal[True]] = None
    comparison: Optional[Literal["current_grade_missing", "violates", "satisfies"]] = (
        None
    )


class SourceEditorialAnnotationProvenance(PartialOutput):
    content_kind: Optional[Literal["registered_editorial_annotation"]] = None
    registered_document: Optional[str] = None
    registered_document_sha256: Optional[str] = None
    case_id: Optional[str] = None
    source_field_pointer: Optional[str] = None
    source_record_sha256: Optional[str] = None
    annotation_sha256: Optional[str] = None
    previous_index_record_sha256: Optional[str] = None
    source_label_kind: Optional[str] = None
    previous_strength_annotation: Optional[Grade] = None
    is_verbatim_original_text: Optional[Literal[False]] = None
    strength_label_assigned_or_regraded: Optional[Literal[False]] = None
    new_independent_validation_credit: Optional[Literal[0]] = None


class SourceNameCorrection(PartialOutput):
    legacy_registered_name: Optional[str] = None
    name_as_printed: Optional[str] = None
    source_pdf_page: Optional[Literal[73]] = None
    source_image_sha256: Optional[str] = None
    legacy_case_identifier_retained: Optional[Literal[True]] = None
    historical_person_identity_asserted: Optional[Literal[False]] = None

    @field_validator(
        "legacy_case_identifier_retained",
        "historical_person_identity_asserted",
        mode="before",
    )
    @classmethod
    def exact_boolean_facts(cls, value: object) -> object:
        if value is not None and type(value) is not bool:
            raise ValueError("姓名校读的布尔事实必须保留JSON布尔类型")
        return value


class SourceIdentityRevision(PartialOutput):
    revision_id: Optional[Literal["ziping_witness_identity_v1"]] = None
    original_record_sha256: Optional[str] = None
    original_edition: Optional[str] = None
    publisher_as_printed: Optional[str] = None
    source_pdf_page: Optional[Literal[1]] = None
    source_image_sha256: Optional[str] = None
    source_strength_label_assigned_or_regraded: Optional[Literal[False]] = None
    independent_expert_review: Optional[Literal["not_completed"]] = None
    new_independent_validation_credit: Optional[Literal[0]] = None
    name_correction: Optional[SourceNameCorrection] = None

    @field_validator(
        "source_pdf_page", "new_independent_validation_credit", mode="before"
    )
    @classmethod
    def exact_integer_facts(cls, value: object) -> object:
        if value is not None and type(value) is not int:
            raise ValueError("来源校读的整数事实必须保留JSON整数类型")
        return value

    @field_validator("source_strength_label_assigned_or_regraded", mode="before")
    @classmethod
    def exact_boolean_fact(cls, value: object) -> object:
        if value is not None and type(value) is not bool:
            raise ValueError("来源校读的布尔事实必须保留JSON布尔类型")
        return value


class BoundedStrengthComparison(PartialOutput):
    status: Optional[
        Literal[
            "no_registered_bounds",
            "contradictory_registered_bounds",
            "current_grade_missing",
            "violates_registered_bounds",
            "satisfies_registered_bounds",
        ]
    ] = None
    claim_count: Optional[int] = None
    satisfied_count: Optional[int] = None
    violated_count: Optional[int] = None
    uncompared_count: Optional[int] = None
    remaining_strengths_under_all_bounds: Optional[List[Grade]] = None
    conflicts_with_retained_exact_annotations: Optional[bool] = None
    claims: Optional[List[SourceStrengthConstraint]] = None
    exact_strength_label_assigned: Optional[Literal[False]] = None
    new_independent_validation_credit: Optional[Literal[0]] = None
    scope: Optional[str] = None


class RegisteredSourceRecord(PartialOutput):
    reference_id: Optional[str] = None
    group: Optional[str] = None
    case_id: Optional[str] = None
    name_as_printed: Optional[str] = None
    pillars: Optional[List[str]] = None
    retained_strength_annotation: Optional[Grade] = None
    annotation_status: Optional[str] = None
    annotation_basis: Optional[str] = None
    retained_anchor: Optional[str] = None
    retained_context: Optional[str] = None
    source_reference: Optional[SourceReference] = None
    bounded_strength_constraints: Optional[List[SourceStrengthConstraint]] = None
    input_reading_revision: Optional[SourceInputReadingRevision] = None
    editorial_annotation_provenance: Optional[SourceEditorialAnnotationProvenance] = (
        None
    )
    source_identity_revision: Optional[SourceIdentityRevision] = None
    source_condition_review: Optional[SourceConditionReview] = None
    independent_annotation_review: Optional[Literal["not_certified"]] = None
    comparison: Optional[
        Literal["unadjudicated", "current_grade_missing", "agrees", "differs"]
    ] = None

    @model_validator(mode="after")
    def preserve_condition_record_identity(self) -> "RegisteredSourceRecord":
        review = self.source_condition_review
        if review is not None:
            if self.reference_id is not None and review.review_id is not None:
                from fatebridge.core.source_conditions import validate_review_record

                validate_review_record(
                    self.reference_id,
                    review.review_id,
                    (
                        review.provenance.parent_index_record_sha256
                        if review.provenance is not None
                        else None
                    ),
                )
            if (
                self.case_id is not None
                and review.case_id is not None
                and self.case_id != review.case_id
            ):
                raise ValueError("原典条件不可接到另一来源记录")
            if (
                self.pillars is not None
                and review.pillars is not None
                and len(self.pillars) == len(review.pillars) == 4
                and self.pillars != review.pillars
            ):
                raise ValueError("来源记录与条件校读四柱不符")
        return self


class SourceIndexContext(PartialOutput):
    source_condition_review_method_id: Optional[
        Literal["original19_source_conditions_public_v1"]
    ] = None
    source_condition_review_sha256: Optional[str] = None
    total_registered_source_condition_reviews: Optional[Literal[19]] = None
    total_records_with_source_condition_review: Optional[Literal[21]] = None
    method_id: Optional[
        Literal[
            "registered_literal_source_annotations_v3",
            "registered_literal_source_annotations_with_bounds_v4",
            "registered_literal_source_annotations_reviewed_inputs_v5",
        ]
    ] = None
    index_sha256: Optional[str] = None
    registry_sha256: Optional[str] = None
    total_registered_records: Optional[int] = None
    total_registered_literal_inputs: Optional[int] = None
    total_registered_strength_constraints: Optional[int] = None
    all_records_previously_exposed: Optional[Literal[True]] = None
    total_registered_input_reading_revisions: Optional[int] = None
    input_reading_plan_sha256: Optional[str] = None
    data_revision: Optional[
        Literal[
            "source_annotations_v7_editorial_projection",
            "source_annotations_v8_witness_identity",
        ]
    ] = None
    total_registered_editorial_annotations: Optional[int] = None
    editorial_annotation_projection_sha256: Optional[str] = None
    source_identity_plan_sha256: Optional[str] = None
    total_registered_source_identity_revisions: Optional[int] = None
    total_registered_printed_name_corrections: Optional[int] = None


class SourceAnnotationComparison(PartialOutput):
    status: Optional[
        Literal[
            "no_registered_literal_case",
            "conflicting_registered_annotations",
            "unadjudicated_records_only",
            "current_grade_missing",
            "known_annotation_mismatch",
            "agrees_with_known_annotations",
        ]
    ] = None
    computed_strength: Optional[Grade] = None
    literal_match_count: Optional[int] = None
    known_annotation_count: Optional[int] = None
    unknown_or_unannotated_count: Optional[int] = None
    agreeing_known_count: Optional[int] = None
    differing_known_count: Optional[int] = None
    retained_expected_strengths: Optional[List[Grade]] = None
    records: Optional[List[RegisteredSourceRecord]] = None
    bounded_comparison: Optional[BoundedStrengthComparison] = None
    reference_index: Optional[SourceIndexContext] = None
    calculation_overridden: Optional[Literal[False]] = None
    exact_literal_match_only: Optional[Literal[True]] = None
    independent_annotation_review: Optional[Literal["not_certified"]] = None
    full_original_text_conformance_certified: Optional[Literal[False]] = None
    historical_identity_asserted: Optional[Literal[False]] = None
    new_independent_validation_credit: Optional[Literal[0]] = None
    scope: Optional[str] = None


class SourceCurrentCalculation(PartialOutput):
    strength_level: Optional[Grade] = None
    method_id: Optional[str] = None
    assessment: Optional[Dict[str, JsonValue]] = None
    energy_provenance: Optional[EnergyProvenance] = None
    calculation_overridden: Optional[Literal[False]] = None
    branch_combination_candidates: Optional[BranchCombinationCandidates] = None

    @model_validator(mode="after")
    def preserve_energy_sources(self) -> "SourceCurrentCalculation":
        if self.energy_provenance is not None:
            bind_assessment(
                self.energy_provenance, self.assessment or {}, self.method_id
            )
        return self

    @model_validator(mode="after")
    def preserve_known_punishment_status(self) -> "SourceCurrentCalculation":
        assessment = self.assessment or {}
        method = self.method_id or assessment.get("method_id")
        if method in {PREVIOUS_PUNISHMENT_METHOD, PUNISHMENT_METHOD}:
            policy = assessment.get("punishment_resolution_policy")
            expected_policy = (
                PUNISHMENT_POLICY
                if method == PUNISHMENT_METHOD
                else PREVIOUS_PUNISHMENT_POLICY
            )
            if policy is not None and policy != expected_policy:
                raise ValueError("解刑策略须忠于已声明的旺衰版本")
            relations = assessment.get("relations")
            if isinstance(relations, list):
                raw_ledger = assessment.get("hidden_stem_ledger")
                branches = (
                    physical_branch_mapping(raw_ledger)
                    if isinstance(raw_ledger, list)
                    else {}
                )
                if self.branch_combination_candidates is not None:
                    for (
                        p,
                        b,
                    ) in self.branch_combination_candidates.known_branches().items():
                        if p in branches and branches[p] != b:
                            raise ValueError("候选与同次物理根账本不能混用四支")
                        branches[p] = b
                validate_punishment_resolution(str(method), relations, branches)
        return self

    @model_validator(mode="after")
    def preserve_candidate_receipt(self) -> "SourceCurrentCalculation":
        inventory = self.branch_combination_candidates
        if inventory is None:
            return self
        assessment = self.assessment or {}
        methods = [
            m
            for m in (
                self.method_id,
                inventory.strength_method_id,
                assessment.get("method_id"),
            )
            if m is not None
        ]
        if methods and any(m != methods[0] for m in methods):
            raise ValueError("候选清单与旺衰计算不能混用不同方法")
        relations = assessment.get("relations")
        if isinstance(relations, list):
            validate_effect_links(inventory, relations)
        ledger = assessment.get("hidden_stem_ledger")
        if isinstance(ledger, list) and inventory.branches_by_position is not None:
            for row in ledger:
                if isinstance(row, dict):
                    pillar, branch = row.get("pillar"), row.get("branch")
                    if (
                        pillar in inventory.branches_by_position
                        and branch is not None
                        and inventory.known_branches().get(str(pillar)) != branch
                    ):
                        raise ValueError("候选四支须忠于同次物理根账本")
        return self


class LiteralSourceInputContext(PartialOutput):
    input_kind: Optional[Literal["literal_four_pillars"]] = None
    birth_datetime_reconstructed: Optional[Literal[False]] = None
    calendar_accuracy_assessed: Optional[Literal[False]] = None
    sexagenary_pairs: Optional[bool] = None
    month_stem_matches_recorded_year: Optional[bool] = None
    hour_stem_matches_recorded_day: Optional[bool] = None
    all_three_modern_checks_match: Optional[bool] = None
    expected_month_stem_under_modern_rule: Optional[str] = None
    expected_hour_stem_under_modern_rule: Optional[str] = None
    zi_hour_clock_and_day_boundary_unresolved: Optional[bool] = None
    literal_source_changed: Optional[Literal[False]] = None
    historical_birth_datetime_verified: Optional[Literal[False]] = None
    scope: Optional[str] = None
