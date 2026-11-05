"""Published, projection-compatible contracts for position-aware BaZi facts."""

from fractions import Fraction
from typing import Any, Dict, List, Literal, Optional

from pydantic import Field, model_validator

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_branch_candidates import (
    physical_branch_mapping,
    validate_punishment_resolution,
)
from fatebridge.core.output_bureau_season import BureauSeasonReference
from fatebridge.core.output_candidate_selection import (
    CandidateSelection,
    MonthStructureReference,
)
from fatebridge.core.output_clash_comparison import ClashComparison
from fatebridge.core.output_classical_force import ClassicalForceComponents
from fatebridge.core.output_classical_passage import ClassicalPassage
from fatebridge.core.output_classical_roots import ClassicalRootProfile
from fatebridge.core.output_classical_routes import ClassicalRoutes
from fatebridge.core.output_classical_seasonal import SeasonalClimateReference
from fatebridge.core.output_element_presence import ElementPresence
from fatebridge.core.output_energy_provenance import bind_assessment
from fatebridge.core.output_from_child import FromChildReference
from fatebridge.core.output_hidden_carriers import (
    HiddenCarrierRelations,
    TemporalHiddenCarrier,
)
from fatebridge.core.output_month_command import MonthCommand, coherent_months
from fatebridge.core.output_passage_relations import PassageRelationContext
from fatebridge.core.output_root_qualification import RootQualification
from fatebridge.core.output_star_occurrences import StarOccurrences
from fatebridge.core.output_stem_energy import StemEnergyAccounting
from fatebridge.core.output_storage_movement import StorageMovementEvent
from fatebridge.core.output_strength_thresholds import StrengthThresholdArithmetic
from fatebridge.core.output_timing_carriers import TimingCarrier
from fatebridge.utils.data import GENERATION_CYCLE


class RootEvidence(PartialOutput):
    pillar: Optional[str] = None
    branch: Optional[str] = None
    stem: Optional[str] = None
    hidden_rank: Optional[int] = Field(default=None, ge=0, le=2)
    kind: Optional[Literal["same_stem", "same_element"]] = None


class GrowthPhaseRoot(PartialOutput):
    pillar: Optional[str] = None
    branch: Optional[str] = None
    stage: Optional[str] = None
    kind: Optional[Literal["growth_phase_reference"]] = None
    source_ref: Optional[str] = None


class StarEvidence(PartialOutput):
    evidence_id: Optional[str] = None
    pillar: Optional[str] = None
    stem: Optional[str] = None
    branch: Optional[str] = None
    location: Optional[Literal["天干", "地支藏干"]] = None
    roots: Optional[List[RootEvidence]] = None
    growth_phase_roots: Optional[List[GrowthPhaseRoot]] = None


class StrengthContext(PartialOutput):
    strength_level: Optional[str] = None
    method_id: Optional[str] = None
    status: Optional[str] = None
    requires_special_structure_review: Optional[bool] = None
    candidate_strengths: Optional[List[str]] = None
    root_effect_policy: Optional[str] = None
    storage_movement_effects: Optional[List[StorageMovementEvent]] = None
    root_qualifications: Optional[List[RootQualification]] = None
    stem_energy_accounting: Optional[StemEnergyAccounting] = None
    clash_comparison: Optional[ClashComparison] = None
    threshold_arithmetic: Optional[StrengthThresholdArithmetic] = None

    @model_validator(mode="after")
    def coherent_review_flag(self) -> "StrengthContext":
        receipt = self.threshold_arithmetic
        if (
            receipt is not None
            and receipt.requires_special_structure_review is not None
            and self.requires_special_structure_review is not None
            and receipt.requires_special_structure_review
            != self.requires_special_structure_review
        ):
            raise ValueError("特殊结构复核标记与同次精确回执不符")
        return self


class RelationEvidence(PartialOutput):
    kind: Optional[str] = None
    level: Optional[Literal["stem", "branch"]] = None
    positions: Optional[List[str]] = None
    characters: Optional[List[str]] = None
    distance: Optional[int] = Field(default=None, ge=1, le=3)
    effect_status: Optional[Literal["relation_only"]] = None


class GroupEvidence(PartialOutput):
    kind: Optional[Literal["三合", "三会", "三刑"]] = None
    positions: Optional[List[str]] = None
    branches: Optional[List[str]] = None
    bureau: Optional[str] = None
    effect_status: Optional[Literal["relation_only"]] = None


class ConditionEvidence(PartialOutput):
    id: Optional[str] = None
    status: Optional[Literal["matched", "not_matched", "unknown"]] = None
    evidence: Optional[List[StarEvidence]] = None
    required: Optional[bool] = None
    model_observation: Optional[StrengthContext] = None
    scope: Optional[str] = None


class StructureCheck(PartialOutput):
    id: Optional[str] = None
    label: Optional[str] = None
    status: Optional[
        Literal["not_applicable", "prerequisite_not_met", "pending_adjudication"]
    ] = None
    formation_status: Optional[Literal["not_adjudicated"]] = None
    conditions: Optional[List[ConditionEvidence]] = None
    source_ref: Optional[str] = None
    formalization: Optional[str] = None


class IncomingStar(PartialOutput):
    stem: Optional[str] = None
    location: Optional[Literal["天干", "地支藏干"]] = None
    ten_god: Optional[str] = None
    in_topic: Optional[bool] = None


class TimingLayer(PartialOutput):
    layer: Optional[Literal["dayun", "liunian"]] = None
    pillar: Optional[str] = None
    stars: Optional[List[IncomingStar]] = None
    natal_relations: Optional[List[RelationEvidence]] = None
    group_relations: Optional[List[GroupEvidence]] = None
    palace_hits: Optional[List[RelationEvidence]] = None


class TopicTiming(PartialOutput):
    scope: Optional[str] = None
    pillar_carriers: Optional[List[TimingCarrier]] = None
    carrier_source: Optional[Dict[str, str]] = None
    carrier_scope: Optional[str] = None
    hidden_target_reference: Optional[HiddenCarrierRelations] = None
    hidden_target_carriers: Optional[List[TemporalHiddenCarrier]] = None
    layers: Optional[List[TimingLayer]] = None
    between_layers: Optional[List[RelationEvidence]] = None
    combined_groups: Optional[List[GroupEvidence]] = None


class PalaceEvidence(PartialOutput):
    pillar: Optional[str] = None
    relations: Optional[List[RelationEvidence]] = None


class TopicEvidence(PartialOutput):
    first_view: Optional[Dict[str, Any]] = None
    topic: Optional[str] = None
    scope: Optional[str] = None
    selection_basis: Optional[str] = None
    selection_alternatives: Optional[Dict[str, List[str]]] = None
    stars: Optional[Dict[str, List[StarEvidence]]] = None
    palaces: Optional[Dict[str, PalaceEvidence]] = None
    timing: Optional[TopicTiming] = None
    source_ref: Optional[str] = None
    limitations: Optional[List[str]] = None


class BaziEvidenceChain(PartialOutput):
    method_id: Optional[str] = None
    rulesets: Optional[List[Dict[str, Any]]] = None
    ten_gods: Optional[Dict[str, List[StarEvidence]]] = None
    star_occurrences: Optional[StarOccurrences] = None
    element_presence: Optional[ElementPresence] = None
    bureau_season_reference: Optional[BureauSeasonReference] = None
    relations: Optional[List[RelationEvidence]] = None
    group_relations: Optional[List[GroupEvidence]] = None
    month_command: Optional[MonthCommand] = None
    seasonal_reference: Optional[SeasonalClimateReference] = None
    classical_root_profile: Optional[ClassicalRootProfile] = None
    force_components: Optional[ClassicalForceComponents] = None
    classical_passage: Optional[ClassicalPassage] = None
    classical_passage_relations: Optional[PassageRelationContext] = None
    classical_routes: Optional[ClassicalRoutes] = None
    candidate_selection: Optional[CandidateSelection] = None
    from_child_reference: Optional[FromChildReference] = None
    natal_hidden_carriers: Optional[HiddenCarrierRelations] = None
    financial_seal_positions: Optional[List[Dict[str, Any]]] = None
    structure_checks: Optional[List[StructureCheck]] = None
    strength_context: Optional[StrengthContext] = None
    topic: Optional[TopicEvidence] = None
    limitations: Optional[List[str]] = None

    @model_validator(mode="after")
    def preserve_candidate_branches(self) -> "BaziEvidenceChain":
        relations = self.classical_passage_relations
        if (
            self.strength_context is not None
            and relations is not None
            and relations.events is not None
            and all(
                e.id == f"assessment.relations:{i}" and e.receipt is not None
                for i, e in enumerate(relations.events)
            )
        ):
            validate_punishment_resolution(
                self.strength_context.method_id,
                [
                    e.receipt.model_dump(exclude_unset=True)
                    for e in relations.events
                    if e.receipt is not None
                ],
                (
                    physical_branch_mapping(
                        [
                            {
                                "pillar": (
                                    node.id.split(":")[0]
                                    if node.id is not None
                                    else node.pillar
                                ),
                                "branch": node.branch,
                            }
                            for node in (self.classical_passage.nodes or [])
                            if (
                                node.id.split(":")[1]
                                if node.id is not None
                                else node.plane
                            )
                            == "hidden"
                        ]
                    )
                    if self.classical_passage is not None
                    else {}
                ),
            )
        inventory = (
            relations.branch_combination_candidates if relations is not None else None
        )
        if inventory is None:
            return self
        if (
            self.strength_context is not None
            and self.strength_context.method_id is not None
            and inventory.strength_method_id is not None
            and self.strength_context.method_id != inventory.strength_method_id
        ):
            raise ValueError("通关候选与旺衰上下文须来自同次计算方法")
        if (
            self.classical_passage is not None
            and inventory.branches_by_position is not None
        ):
            for node in self.classical_passage.nodes or []:
                pillar, plane = (
                    node.id.split(":")[:2]
                    if node.id is not None
                    else (node.pillar, node.plane)
                )
                if (
                    plane == "hidden"
                    and pillar in inventory.branches_by_position
                    and node.branch is not None
                    and inventory.known_branches().get(str(pillar)) != node.branch
                ):
                    raise ValueError("通关候选不能混入另一四柱的物理藏支")
        return self

    @model_validator(mode="after")
    def preserve_same_known_month(self) -> "BaziEvidenceChain":
        months = (
            self.month_command.known_months() if self.month_command is not None else []
        )
        if (
            self.bureau_season_reference is not None
            and self.bureau_season_reference.month_branch is not None
        ):
            months.append(self.bureau_season_reference.month_branch)
        if self.classical_passage is not None:
            for node in self.classical_passage.nodes or []:
                pillar, plane = (
                    node.id.split(":")[:2]
                    if node.id is not None
                    else (node.pillar, node.plane)
                )
                if pillar == "month" and plane == "hidden" and node.branch is not None:
                    months.append(node.branch)
        coherent_months(months)
        if months and self.month_command is not None:
            self.month_command.check_month(months[0])
        return self

    @model_validator(mode="after")
    def preserve_same_strength_and_force_receipt(self) -> "BaziEvidenceChain":
        context, force = self.strength_context, self.force_components
        if context is None or force is None:
            return self
        if force.energy_provenance is not None:
            bind_assessment(
                force.energy_provenance, context.model_dump(exclude_unset=True)
            )
        composition = force.engineering_composition
        if composition is not None:
            if (
                context.method_id is not None
                and composition.strength_method_id is not None
                and context.method_id != composition.strength_method_id
            ):
                raise ValueError("身印分量与旺衰上下文不能混用不同计算方法")
            if (
                context.strength_level is not None
                and composition.strength_level is not None
                and context.strength_level != composition.strength_level
            ):
                raise ValueError("同次身印分量与旺衰上下文等级不符")
        receipt = context.threshold_arithmetic
        if receipt is None or receipt.day_element is None:
            return self
        body = receipt.day_element
        seal = next(
            e.value for e, child in GENERATION_CYCLE.items() if child.value == body
        )
        recorded_energies: dict[str, str] = {
            k: v for k, v in (receipt.energies_exact or {}).items()
        }
        for role, element, exact_field in [
            ("body", body, "body_energy_exact"),
            ("seal", seal, "seal_energy_exact"),
        ]:
            component = (
                getattr(force.components, role)
                if force.components is not None
                else None
            )
            if (
                component is not None
                and component.element is not None
                and component.element != element
            ):
                raise ValueError("身印五行角色必须忠于同次日主五行")
            energy = (
                getattr(composition, exact_field) if composition is not None else None
            )
            recorded = recorded_energies.get(element)
            if (
                energy is not None
                and recorded is not None
                and Fraction(energy) != Fraction(recorded)
            ):
                raise ValueError("身印精确分量必须沿用同次旺衰回执，不能拼接其他结果")
        return self


class EvidenceStructureProfile(PartialOutput):
    resolution_policy: Optional[Literal["source_conditions_before_preference_v3"]] = (
        None
    )
    dominant_structure: Optional[MonthStructureReference] = None
    candidate_selection: Optional[CandidateSelection] = None
    from_child_reference: Optional[FromChildReference] = None
    evidence_chain: Optional[BaziEvidenceChain] = None
