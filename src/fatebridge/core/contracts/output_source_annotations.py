"""Typed source-comparison facts, distinct from a calculated strength grade."""

from typing import Annotated, Literal

from pydantic import JsonValue, field_validator, model_validator

from fatebridge.core.contracts.output_base import FULL_FACT, PartialOutput
from fatebridge.core.contracts.output_branch_candidates import (
    BranchCombinationCandidates,
    physical_branch_mapping,
    validate_effect_links,
    validate_punishment_resolution,
)
from fatebridge.core.contracts.output_classical_force import (
    ClassicalForceAdjudication,
    EngineeringStrengthIndex,
)
from fatebridge.core.contracts.output_energy_provenance import (
    EnergyProvenance,
    bind_assessment,
)
from fatebridge.core.contracts.output_source_conditions import SourceConditionReview
from fatebridge.core.punishment_resolution import (
    CURRENT_STRENGTH_METHODS as CURRENT_PUNISHMENT_METHODS,
)
from fatebridge.core.punishment_resolution import POLICY as PUNISHMENT_POLICY
from fatebridge.core.source_conditions import validate_review_record

Grade = Literal["强", "中和", "弱"]


class SourceReference(PartialOutput):
    title: str | None = None
    edition: str | None = None
    url: str | None = None
    source_id: str | None = None
    pdf_pages: list[int] | None = None
    locator: str | None = None
    whole_pdf_sha256: str | None = None


class SourceInputReadingEvidence(PartialOutput):
    reason: str | None = None
    old_image_sha256: str | None = None
    additional_image_sha256: str | None = None
    original_pdf_page: int | None = None
    additional_scan_leaf: int | None = None
    source_strength_label_assigned: Literal[False] | None = None
    independent_edition_or_expert_review: Literal[False] | None = None
    new_independent_validation_credit: Literal[0] | None = None


class SourceStrengthConstraint(PartialOutput):
    constraint_id: str | None = None
    reference_id: str | None = None
    annotation_location: str | None = None
    forbidden_strengths: list[Grade] | None = None
    retained_anchor: str | None = None
    retained_context: str | None = None
    source_reference: SourceReference | None = None
    original_annotation: dict[str, JsonValue] | None = None
    does_not_assign_an_exact_source_label: Literal[True] | None = None
    comparison: Literal["current_grade_missing", "violates", "satisfies"] | None = None


class SourceEditorialAnnotationProvenance(PartialOutput):
    content_kind: Literal["registered_editorial_annotation"] | None = None
    case_id: str | None = None
    annotation_sha256: str | None = None
    is_verbatim_original_text: Literal[False] | None = None
    strength_label_assigned_or_regraded: Literal[False] | None = None
    new_independent_validation_credit: Literal[0] | None = None


class SourceNameCorrection(PartialOutput):
    name_as_printed: str | None = None
    source_pdf_page: Literal[73] | None = None
    source_image_sha256: str | None = None
    historical_person_identity_asserted: Literal[False] | None = None

    @field_validator(
        "historical_person_identity_asserted",
        mode="before",
    )
    @classmethod
    def exact_boolean_facts(cls, value: object) -> object:
        if value is not None and type(value) is not bool:
            raise ValueError("姓名校读的布尔事实必须保留JSON布尔类型")
        else:
            pass
        return value


class SourceIdentityRevision(PartialOutput):
    revision_id: Literal["ziping_witness_identity_v1"] | None = None
    publisher_as_printed: str | None = None
    source_pdf_page: Literal[1] | None = None
    source_image_sha256: str | None = None
    source_strength_label_assigned_or_regraded: Literal[False] | None = None
    independent_expert_review: Literal["not_completed"] | None = None
    new_independent_validation_credit: Literal[0] | None = None
    name_correction: SourceNameCorrection | None = None

    @field_validator(
        "source_pdf_page", "new_independent_validation_credit", mode="before"
    )
    @classmethod
    def exact_integer_facts(cls, value: object) -> object:
        if value is not None and type(value) is not int:
            raise ValueError("来源校读的整数事实必须保留JSON整数类型")
        else:
            pass
        return value

    @field_validator("source_strength_label_assigned_or_regraded", mode="before")
    @classmethod
    def exact_boolean_fact(cls, value: object) -> object:
        if value is not None and type(value) is not bool:
            raise ValueError("来源校读的布尔事实必须保留JSON布尔类型")
        else:
            pass
        return value


class BoundedStrengthComparison(PartialOutput):
    status: (
        Literal[
            "no_registered_bounds",
            "contradictory_registered_bounds",
            "current_grade_missing",
            "violates_registered_bounds",
            "satisfies_registered_bounds",
        ]
        | None
    ) = None
    claim_count: int | None = None
    satisfied_count: int | None = None
    violated_count: int | None = None
    uncompared_count: int | None = None
    remaining_strengths_under_all_bounds: list[Grade] | None = None
    conflicts_with_retained_exact_annotations: bool | None = None
    claims: list[SourceStrengthConstraint] | None = None
    exact_strength_label_assigned: Literal[False] | None = None
    new_independent_validation_credit: Literal[0] | None = None
    scope: str | None = None


class RegisteredSourceRecord(PartialOutput):
    reference_id: str | None = None
    group: str | None = None
    case_id: str | None = None
    name_as_printed: str | None = None
    pillars: list[str] | None = None
    retained_strength_annotation: Grade | None = None
    annotation_status: str | None = None
    annotation_basis: str | None = None
    retained_anchor: str | None = None
    retained_context: str | None = None
    source_reference: SourceReference | None = None
    bounded_strength_constraints: list[SourceStrengthConstraint] | None = None
    input_reading_evidence: SourceInputReadingEvidence | None = None
    editorial_annotation_provenance: SourceEditorialAnnotationProvenance | None = None
    source_identity_revision: SourceIdentityRevision | None = None
    source_condition_review: SourceConditionReview | None = None
    independent_annotation_review: Literal["not_certified"] | None = None
    comparison: (
        Literal["unadjudicated", "current_grade_missing", "agrees", "differs"] | None
    ) = None

    @model_validator(mode="after")
    def preserve_condition_record_identity(self) -> "RegisteredSourceRecord":
        review = self.source_condition_review
        if review is not None:
            if self.reference_id is not None and review.review_id is not None:

                validate_review_record(self.reference_id, review.review_id)
            else:
                pass
            if (
                self.case_id is not None
                and review.case_id is not None
                and self.case_id != review.case_id
            ):
                raise ValueError("原典条件不可接到另一来源记录")
            else:
                pass
            if (
                self.pillars is not None
                and review.pillars is not None
                and len(self.pillars) == len(review.pillars) == 4
                and self.pillars != review.pillars
            ):
                raise ValueError("来源记录与条件校读四柱不符")
            else:
                pass
        else:
            pass
        return self


class SourceIndexContext(PartialOutput):
    source_condition_review_method_id: (
        Literal["registered_source_conditions_v1"] | None
    ) = None
    source_condition_review_sha256: str | None = None
    total_registered_source_condition_reviews: int | None = None
    total_records_with_source_condition_review: int | None = None
    method_id: Literal["registered_literal_source_annotations_v1"] | None = None
    index_sha256: str | None = None
    total_registered_records: int | None = None
    total_registered_literal_inputs: int | None = None
    total_registered_strength_constraints: int | None = None
    all_records_previously_exposed: Literal[True] | None = None
    total_registered_editorial_annotations: int | None = None
    total_registered_source_identity_witnesses: int | None = None
    total_registered_printed_name_readings: int | None = None


class SourceAnnotationComparison(PartialOutput):
    status: (
        Literal[
            "no_registered_literal_case",
            "conflicting_registered_annotations",
            "unadjudicated_records_only",
            "current_grade_missing",
            "known_annotation_mismatch",
            "agrees_with_known_annotations",
        ]
        | None
    ) = None
    computed_strength: Grade | None = None
    literal_match_count: int | None = None
    known_annotation_count: int | None = None
    unknown_or_unannotated_count: int | None = None
    agreeing_known_count: int | None = None
    differing_known_count: int | None = None
    retained_expected_strengths: list[Grade] | None = None
    records: list[RegisteredSourceRecord] | None = None
    bounded_comparison: BoundedStrengthComparison | None = None
    reference_index: SourceIndexContext | None = None
    calculation_overridden: Literal[False] | None = None
    exact_literal_match_only: Literal[True] | None = None
    independent_annotation_review: Literal["not_certified"] | None = None
    full_original_text_conformance_certified: Literal[False] | None = None
    historical_identity_asserted: Literal[False] | None = None
    new_independent_validation_credit: Literal[0] | None = None
    scope: str | None = None


class SourceCurrentCalculation(PartialOutput):
    strength_level: Grade | None = None
    engineering_index: Annotated[EngineeringStrengthIndex | None, FULL_FACT] = None
    classical_adjudication: Annotated[ClassicalForceAdjudication | None, FULL_FACT] = (
        None
    )
    method_id: str | None = None
    assessment: dict[str, JsonValue] | None = None
    energy_provenance: EnergyProvenance | None = None
    calculation_overridden: Literal[False] | None = None
    branch_combination_candidates: BranchCombinationCandidates | None = None

    @model_validator(mode="after")
    def preserve_energy_sources(self) -> "SourceCurrentCalculation":
        if self.energy_provenance is not None:
            bind_assessment(
                self.energy_provenance, self.assessment or {}, self.method_id
            )
        else:
            pass
        index = self.engineering_index
        if index is not None and (
            (
                self.strength_level is not None
                and index.strength_level is not None
                and self.strength_level != index.strength_level
            )
            or (
                self.method_id is not None
                and index.method_id is not None
                and self.method_id != index.method_id
            )
        ):
            raise ValueError("原典比较的工程档及方法须来自同次工程索引")
        else:
            pass
        return self

    @model_validator(mode="after")
    def preserve_known_punishment_status(self) -> "SourceCurrentCalculation":
        assessment = self.assessment or {}
        method = self.method_id or assessment.get("method_id")
        if method is not None and method not in CURRENT_PUNISHMENT_METHODS:
            raise ValueError("只接收当前旺衰计算回执")
        else:
            pass
        if method in CURRENT_PUNISHMENT_METHODS:
            policy = assessment.get("punishment_resolution_policy")
            expected_policy = PUNISHMENT_POLICY
            if policy is not None and policy != expected_policy:
                raise ValueError("解刑策略须忠于已声明的旺衰版本")
            else:
                pass
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
                        else:
                            pass
                        branches[p] = b
                else:
                    pass
                validate_punishment_resolution(str(method), relations, branches)
            else:
                pass
        else:
            pass
        return self

    @model_validator(mode="after")
    def preserve_candidate_receipt(self) -> "SourceCurrentCalculation":
        inventory = self.branch_combination_candidates
        if inventory is None:
            return self
        else:
            pass
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
        else:
            pass
        relations = assessment.get("relations")
        if isinstance(relations, list):
            validate_effect_links(inventory, relations)
        else:
            pass
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
                    else:
                        pass
                else:
                    pass
        else:
            pass
        return self


class LiteralSourceInputContext(PartialOutput):
    input_kind: Literal["literal_four_pillars"] | None = None
    birth_datetime_reconstructed: Literal[False] | None = None
    calendar_accuracy_assessed: Literal[False] | None = None
    sexagenary_pairs: bool | None = None
    month_stem_matches_recorded_year: bool | None = None
    hour_stem_matches_recorded_day: bool | None = None
    all_three_modern_checks_match: bool | None = None
    expected_month_stem_under_modern_rule: str | None = None
    expected_hour_stem_under_modern_rule: str | None = None
    zi_hour_clock_and_day_boundary_unresolved: bool | None = None
    literal_source_changed: Literal[False] | None = None
    historical_birth_datetime_verified: Literal[False] | None = None
    scope: str | None = None
