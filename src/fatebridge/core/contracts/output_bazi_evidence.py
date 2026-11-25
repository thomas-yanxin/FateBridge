"""Published, projection-compatible contracts for position-aware BaZi facts."""

from fractions import Fraction
from typing import Annotated, Literal

from pydantic import Field, model_validator

from fatebridge.core.contracts.output_base import (
    FULL_FACT,
    PRESENT_FACT,
    OpenJsonValue,
    PartialOutput,
)
from fatebridge.core.contracts.output_branch_candidates import (
    physical_branch_mapping,
    validate_punishment_resolution,
)
from fatebridge.core.contracts.output_bureau_season import BureauSeasonReference
from fatebridge.core.contracts.output_candidate_selection import (
    CandidateSelection,
    MonthStructureReference,
)
from fatebridge.core.contracts.output_clash_comparison import ClashComparison
from fatebridge.core.contracts.output_classical_force import (
    ClassicalForceAdjudication,
    ClassicalForceComponents,
    EngineeringStrengthIndex,
)
from fatebridge.core.contracts.output_classical_passage import ClassicalPassage
from fatebridge.core.contracts.output_classical_roots import ClassicalRootProfile
from fatebridge.core.contracts.output_classical_routes import ClassicalRoutes
from fatebridge.core.contracts.output_classical_seasonal import SeasonalClimateReference
from fatebridge.core.contracts.output_element_presence import ElementPresence
from fatebridge.core.contracts.output_energy_provenance import bind_assessment
from fatebridge.core.contracts.output_from_child import FromChildReference
from fatebridge.core.contracts.output_hidden_carriers import (
    HiddenCarrierRelations,
    TemporalHiddenCarrier,
)
from fatebridge.core.contracts.output_month_command import MonthCommand, coherent_months
from fatebridge.core.contracts.output_month_use import MonthUseMatch
from fatebridge.core.contracts.output_passage_relations import PassageRelationContext
from fatebridge.core.contracts.output_root_qualification import RootQualification
from fatebridge.core.contracts.output_star_occurrences import StarOccurrences
from fatebridge.core.contracts.output_stem_energy import StemEnergyAccounting
from fatebridge.core.contracts.output_storage_movement import StorageMovementEvent
from fatebridge.core.contracts.output_strength_thresholds import (
    StrengthThresholdArithmetic,
)
from fatebridge.core.contracts.output_timing_carriers import TimingCarrier
from fatebridge.utils.data import GENERATION_CYCLE


class RootEvidence(PartialOutput):
    pillar: str | None = None
    branch: str | None = None
    stem: str | None = None
    hidden_rank: int | None = Field(default=None, ge=0, le=2)
    kind: Literal["same_stem", "same_element"] | None = None


class GrowthPhaseRoot(PartialOutput):
    pillar: str | None = None
    branch: str | None = None
    stage: str | None = None
    kind: Literal["growth_phase_reference"] | None = None
    source_ref: str | None = None


class StarEvidence(PartialOutput):
    evidence_id: str | None = None
    pillar: str | None = None
    stem: str | None = None
    branch: str | None = None
    location: Literal["天干", "地支藏干"] | None = None
    roots: list[RootEvidence] | None = None
    growth_phase_roots: list[GrowthPhaseRoot] | None = None


class StrengthContext(PartialOutput):
    strength_level: str | None = None
    engineering_index: Annotated[EngineeringStrengthIndex | None, FULL_FACT] = None
    classical_adjudication: Annotated[ClassicalForceAdjudication | None, FULL_FACT] = (
        None
    )
    method_id: str | None = None
    status: str | None = None
    requires_special_structure_review: bool | None = None
    candidate_strengths: list[str] | None = None
    root_effect_policy: str | None = None
    storage_movement_effects: list[StorageMovementEvent] | None = None
    root_qualifications: list[RootQualification] | None = None
    stem_energy_accounting: StemEnergyAccounting | None = None
    clash_comparison: ClashComparison | None = None
    threshold_arithmetic: StrengthThresholdArithmetic | None = None

    @model_validator(mode="after")
    def coherent_engineering_index(self) -> "StrengthContext":
        index = self.engineering_index
        if index is None:
            return self
        else:
            pass
        if (
            self.method_id is not None
            and index.method_id is not None
            and self.method_id != index.method_id
        ) or (
            self.strength_level is not None
            and index.strength_level is not None
            and self.strength_level != index.strength_level
        ):
            raise ValueError("工程索引与同次旺衰政策结果不符")
        else:
            pass
        if (
            self.threshold_arithmetic is not None
            and self.threshold_arithmetic.numerical_label is not None
            and index.numerical_strength_level is not None
            and self.threshold_arithmetic.numerical_label
            != index.numerical_strength_level
        ):
            raise ValueError("工程索引数值档与同次精确账本不符")
        else:
            pass
        return self

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
        else:
            pass
        return self


class RelationEvidence(PartialOutput):
    kind: str | None = None
    level: Literal["stem", "branch"] | None = None
    positions: list[str] | None = None
    characters: list[str] | None = None
    distance: int | None = Field(default=None, ge=1, le=3)
    effect_status: Literal["relation_only"] | None = None


class GroupEvidence(PartialOutput):
    kind: Literal["三合", "三会", "三刑"] | None = None
    positions: list[str] | None = None
    branches: list[str] | None = None
    bureau: str | None = None
    effect_status: Literal["relation_only"] | None = None


class ConditionEvidence(PartialOutput):
    id: str | None = None
    status: Literal["matched", "not_matched", "unknown"] | None = None
    month_use_match: MonthUseMatch | None = None
    evidence: list[StarEvidence] | None = None
    required: bool | None = None
    model_observation: StrengthContext | None = None
    scope: str | None = None


class StructureCheck(PartialOutput):
    id: str | None = None
    label: str | None = None
    status: (
        Literal["not_applicable", "prerequisite_not_met", "pending_adjudication"] | None
    ) = None
    formation_status: Literal["not_adjudicated"] | None = None
    conditions: list[ConditionEvidence] | None = None
    source_ref: str | None = None
    formalization: str | None = None


class IncomingStar(PartialOutput):
    stem: str | None = None
    location: Literal["天干", "地支藏干"] | None = None
    ten_god: str | None = None
    in_topic: bool | None = None


class TimingLayer(PartialOutput):
    layer: Literal["dayun", "liunian"] | None = None
    pillar: str | None = None
    stars: list[IncomingStar] | None = None
    natal_relations: list[RelationEvidence] | None = None
    group_relations: list[GroupEvidence] | None = None
    palace_hits: list[RelationEvidence] | None = None


class TopicTiming(PartialOutput):
    scope: str | None = None
    pillar_carriers: list[TimingCarrier] | None = None
    carrier_source: dict[str, str] | None = None
    carrier_scope: str | None = None
    hidden_target_reference: HiddenCarrierRelations | None = None
    hidden_target_carriers: list[TemporalHiddenCarrier] | None = None
    layers: list[TimingLayer] | None = None
    between_layers: list[RelationEvidence] | None = None
    combined_groups: list[GroupEvidence] | None = None


class PalaceEvidence(PartialOutput):
    pillar: str | None = None
    relations: list[RelationEvidence] | None = None


class TopicMarker(PartialOutput):
    name: str | None = None
    anchor: str | None = None
    target_branch: str | None = None
    natal_positions: list[str] | None = None
    timing_layers: list[str] | None = None


class TopicFirstStar(PartialOutput):
    ten_god: str | None = None
    visible_in: list[str] | None = None
    hidden_in: list[str] | None = None


class TopicTimingSummary(PartialOutput):
    layer: Literal["dayun", "liunian"] | None = None
    pillar: str | None = None
    topic_stars: list[str] | None = None
    palace_relation_count: int | None = Field(default=None, ge=0)


class TopicFirstView(PartialOutput):
    selection_basis: str | None = None
    selection_policy: str | None = None
    natal_stars: list[TopicFirstStar] | None = None
    markers: list[TopicMarker] | None = None
    timing: list[TopicTimingSummary] | None = None


class TopicStorageMatch(PartialOutput):
    pillar: str | None = None
    branch: str | None = None
    element: str | None = None
    clashes: list[RelationEvidence] | None = None


class TopicEvidence(PartialOutput):
    first_view: TopicFirstView | None = None
    topic: str | None = None
    scope: str | None = None
    selection_basis: str | None = None
    selection_alternatives: dict[str, list[str]] | None = None
    markers: list[TopicMarker] | None = None
    storage_matches: list[TopicStorageMatch] | None = None
    stars: dict[str, list[StarEvidence]] | None = None
    palaces: dict[str, PalaceEvidence] | None = None
    timing: TopicTiming | None = None
    source_ref: str | None = None


class BaziEvidenceChain(PartialOutput):
    method_id: str | None = None
    rulesets: list[dict[str, OpenJsonValue]] | None = None
    ten_gods: dict[str, list[StarEvidence]] | None = None
    star_occurrences: StarOccurrences | None = None
    element_presence: ElementPresence | None = None
    bureau_season_reference: BureauSeasonReference | None = None
    relations: list[RelationEvidence] | None = None
    group_relations: list[GroupEvidence] | None = None
    month_command: MonthCommand | None = None
    seasonal_reference: SeasonalClimateReference | None = None
    classical_root_profile: ClassicalRootProfile | None = None
    force_components: ClassicalForceComponents | None = None
    classical_passage: ClassicalPassage | None = None
    classical_passage_relations: PassageRelationContext | None = None
    classical_routes: ClassicalRoutes | None = None
    candidate_selection: CandidateSelection | None = None
    from_child_reference: FromChildReference | None = None
    natal_hidden_carriers: HiddenCarrierRelations | None = None
    financial_seal_positions: list[dict[str, OpenJsonValue]] | None = None
    structure_checks: list[StructureCheck] | None = None
    strength_context: StrengthContext | None = None
    topic: TopicEvidence | None = None
    limitations: list[str] | None = None

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
        else:
            pass
        inventory = (
            relations.branch_combination_candidates if relations is not None else None
        )
        if inventory is None:
            return self
        else:
            pass
        if (
            self.strength_context is not None
            and self.strength_context.method_id is not None
            and inventory.strength_method_id is not None
            and self.strength_context.method_id != inventory.strength_method_id
        ):
            raise ValueError("通关候选与旺衰上下文须来自同次计算方法")
        else:
            pass
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
                else:
                    pass
        else:
            pass
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
        else:
            pass
        if self.classical_passage is not None:
            for node in self.classical_passage.nodes or []:
                pillar, plane = (
                    node.id.split(":")[:2]
                    if node.id is not None
                    else (node.pillar, node.plane)
                )
                if pillar == "month" and plane == "hidden" and node.branch is not None:
                    months.append(node.branch)
                else:
                    pass
        else:
            pass
        coherent_months(months)
        if months and self.month_command is not None:
            self.month_command.check_month(months[0])
        else:
            pass
        return self

    @model_validator(mode="after")
    def preserve_same_strength_and_force_receipt(self) -> "BaziEvidenceChain":
        context, force = self.strength_context, self.force_components
        if context is None or force is None:
            return self
        else:
            pass
        left, right = context.classical_adjudication, force.classical_adjudication
        if left is not None and right is not None:
            for name in left.model_fields_set & right.model_fields_set:
                if getattr(left, name) != getattr(right, name):
                    raise ValueError(
                        "原典力量裁定须来自同次日主结果，不得在证据层另行改判"
                    )
                else:
                    pass
        else:
            pass
        if force.energy_provenance is not None:
            bind_assessment(
                force.energy_provenance, context.model_dump(exclude_unset=True)
            )
        else:
            pass
        composition = force.engineering_composition
        if composition is not None:
            if (
                context.method_id is not None
                and composition.strength_method_id is not None
                and context.method_id != composition.strength_method_id
            ):
                raise ValueError("身印分量与旺衰上下文不能混用不同计算方法")
            else:
                pass
            if (
                context.strength_level is not None
                and composition.strength_level is not None
                and context.strength_level != composition.strength_level
            ):
                raise ValueError("同次身印分量与旺衰上下文等级不符")
            else:
                pass
        else:
            pass
        receipt = context.threshold_arithmetic
        if receipt is None or receipt.day_element is None:
            return self
        else:
            pass
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
            else:
                pass
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
            else:
                pass
        return self


class EngineeringPreferenceReference(PartialOutput):
    resolution_policy: Annotated[
        Literal["source_conditions_before_preference_v3"] | None, FULL_FACT
    ] = None
    assessment_status: Annotated[Literal["conditional"] | None, FULL_FACT] = None
    quantity_kind: Annotated[
        Literal["conditional_engineering_preference"] | None, FULL_FACT
    ] = None
    source_adjudication_used: Annotated[Literal[False] | None, FULL_FACT] = None
    useful_elements: Annotated[list[str] | None, FULL_FACT] = None
    avoid_elements: Annotated[list[str] | None, FULL_FACT] = None
    conditional_elements: Annotated[list[str] | None, FULL_FACT] = None
    neutral_elements: Annotated[list[str] | None, FULL_FACT] = None
    useful_ten_gods: Annotated[list[str] | None, FULL_FACT] = None
    scope: Annotated[str | None, FULL_FACT] = None


class HarmonyEffect(PartialOutput):
    type: Annotated[str | None, FULL_FACT] = None
    label: Annotated[str | None, FULL_FACT] = None
    branches: Annotated[list[str] | None, FULL_FACT] = None
    result_element: Annotated[str | None, PRESENT_FACT] = None
    strengthens: Annotated[list[str] | None, FULL_FACT] = None
    consumes: Annotated[list[str] | None, FULL_FACT] = None
    impact_on_day_master: Annotated[str | None, FULL_FACT] = None
    impact_on_structure: Annotated[str | None, FULL_FACT] = None
    classification: Annotated[
        Literal["supportive", "risk", "neutral", "tension"] | None, FULL_FACT
    ] = None


class EvidenceStructureProfile(PartialOutput):
    resolution_policy: Literal["source_force_before_preference_v4"] | None = None
    assessment_status: Annotated[
        Literal["not_adjudicated", "conditional"] | None, FULL_FACT
    ] = None
    classical_adjudication: Annotated[ClassicalForceAdjudication | None, FULL_FACT] = (
        None
    )
    engineering_reference: Annotated[
        EngineeringPreferenceReference | None, FULL_FACT
    ] = None
    harmony_effects_status: Annotated[
        Literal["not_adjudicated", "conditional"] | None, FULL_FACT
    ] = None
    harmony_effects: Annotated[list[HarmonyEffect] | None, FULL_FACT] = None
    engineering_harmony_effects: Annotated[list[HarmonyEffect] | None, FULL_FACT] = None
    useful_elements: Annotated[list[str] | None, FULL_FACT] = None
    avoid_elements: Annotated[list[str] | None, FULL_FACT] = None
    conditional_elements: Annotated[list[str] | None, FULL_FACT] = None
    neutral_elements: Annotated[list[str] | None, FULL_FACT] = None

    @model_validator(mode="after")
    def unknown_force_does_not_select_preferences(self) -> "EvidenceStructureProfile":
        if self.assessment_status == "not_adjudicated" and (
            self.useful_elements or self.avoid_elements or self.neutral_elements
        ):
            raise ValueError("来源喜忌未裁定时，工程参考不能回填已选喜忌或中性结论")
        else:
            pass
        return self

    dominant_structure: MonthStructureReference | None = None
    candidate_selection: CandidateSelection | None = None
    from_child_reference: FromChildReference | None = None
    evidence_chain: BaziEvidenceChain | None = None
