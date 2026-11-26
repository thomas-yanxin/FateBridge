"""Optional nested fields for the explicitly bounded Liu Yao condition layer."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_liuyao_cessation import CessationConditions
from fatebridge.core.contracts.output_liuyao_clash import ClashConditions
from fatebridge.core.contracts.output_liuyao_control import ControlConditions
from fatebridge.core.contracts.output_liuyao_generation import GenerationConditions
from fatebridge.core.contracts.output_liuyao_growth import GrowthConditions
from fatebridge.core.contracts.output_liuyao_hidden import HiddenReception
from fatebridge.core.contracts.output_liuyao_penalty import PenaltyConditions
from fatebridge.core.contracts.output_liuyao_rescue import BackGenerationConditions
from fatebridge.core.contracts.output_liuyao_routing import RoutingConditions
from fatebridge.core.contracts.output_liuyao_stages import (
    HiddenStageConditions,
    StageKnowledge,
)
from fatebridge.core.contracts.output_liuyao_void import VoidConditions


class DivinationSource(PartialOutput):
    title: str | None = None
    revision: int | None = None
    source_url: str | None = None


class MonthlyStrength(PartialOutput):
    category: str | None = None
    monthly_supported: bool | None = None
    residual_qi: bool | None = None
    scope: str | None = None


class ProgressClause(PartialOutput):
    rule_id: str | None = None
    condition: str | None = None
    matched: bool | None = None
    raw_matched: bool | None = None
    status: str | None = None
    source_url: str | None = None


class ChangedCalendarStrength(PartialOutput):
    status: str | None = None
    is_supported: bool | None = None
    is_weak: bool | None = None
    scope: str | None = None


class ProgressConditions(PartialOutput):
    structural_pair: str | None = None
    original_branch: str | None = None
    changed_branch: str | None = None
    original_month_strength: str | None = None
    changed_month_strength: str | None = None
    has_void_or_month_break: bool | None = None
    has_current_void_or_month_obstruction: bool | None = None
    event_horizon: str | None = None
    state: str | None = None
    condition_now: bool | None = None
    original_supported: bool | None = None
    original_weak: bool | None = None
    original_strength_basis: str | None = None
    original_strength_source_path: str | None = None
    changed_calendar_strength: ChangedCalendarStrength | None = None
    clauses: list[ProgressClause] | None = None
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    adjudication: str | None = None
    source_url: str | None = None
    textual_issues: list[dict[str, OpenJsonValue]] | None = None
    scope: str | None = None


class ConditionalLine(PartialOutput):
    position: int | None = None
    monthly_strength: MonthlyStrength | None = None
    activity: str | None = None
    activity_condition_match: bool | None = None
    activity_condition_status: str | None = None
    supporting_moving_positions: list[int] | None = None
    supporting_static_positions: list[int] | None = None
    binding_cues: list[str] | None = None
    outgoing_obstructions: list[str] | None = None
    day_stage: str | None = None
    month_stage: str | None = None
    changed_stage: str | None = None
    stage_cautions: list[str] | None = None
    efficacy: str | None = None
    progress_conditions: ProgressConditions | None = None


class InteractionEdge(PartialOutput):
    metal_si_combined_effect_condition: bool | None = None
    raw_control_condition_match: bool | None = None
    metal_si_growth_condition: bool | None = None
    metal_si_growth_source_path: str | None = None
    qualified_back_control_condition: bool | None = None
    own_si_growth_source_path: str | None = None
    qualified_routing_condition: bool | None = None
    qualified_routing_status: str | None = None
    conditional_routing_chain_ids: list[str] | None = None
    rejected_routing_chain_ids: list[str] | None = None
    generation_status: str | None = None
    target_reception_status: str | None = None
    generation_condition_match: bool | None = None
    target_reception_condition: bool | None = None
    benefit_now: bool | None = None
    generation_source_path: str | None = None
    source_kind: str | None = None
    source_position: int | None = None
    target_kind: str | None = None
    target_position: int | None = None
    relation: str | None = None
    effect_status: str | None = None
    source_url: str | None = None
    routing_chain_ids: list[str] | None = None
    control_condition_match: bool | None = None
    control_status: str | None = None
    control_source_path: str | None = None


class FocusCandidate(PartialOutput):
    location: str | None = None
    position: int | None = None
    branch: str | None = None
    element: str | None = None
    liuqin: str | None = None
    moving: bool | None = None


class FocusRole(PartialOutput):
    location: str | None = None
    position: int | None = None
    branch: str | None = None
    role: str | None = None


class FocusEvidence(PartialOutput):
    status: str | None = None
    requested_kinship: str | None = None
    requested_kind: str | None = None
    selected: FocusCandidate | None = None
    candidates: list[FocusCandidate] | None = None
    roles: list[FocusRole] | None = None
    scope: str | None = None


class CivilInterval(PartialOutput):
    method: str | None = None
    wall_start: str | None = None
    wall_end: str | None = None
    interval_index: int | None = None
    interval_count: int | None = None
    start_utc: str | None = None
    end_utc: str | None = None
    duration_seconds: float | None = None
    timezone: str | None = None
    scope: str | None = None


class ExcludedCivilDay(PartialOutput):
    effective_date: str | None = None
    day_ganzhi: str | None = None
    wall_start: str | None = None
    wall_end: str | None = None
    matched_rules: list[str] | None = None
    status: str | None = None
    method: str | None = None


class ConditionWindow(PartialOutput):
    civil_interval: CivilInterval | None = None
    effective_date: str | None = None
    day_ganzhi: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    matched_rules: list[str] | None = None
    requires_month_reassessment: bool | None = None


class TimingCandidates(PartialOutput):
    calendar_exclusions: list[ExcludedCivilDay] | None = None
    status: str | None = None
    granularity: str | None = None
    requested_days: int | None = None
    windows: list[ConditionWindow] | None = None
    source_url: str | None = None
    scope: str | None = None


class ConditionActor(PartialOutput):
    raw_generation_condition_match: bool | None = None
    penalty_source_path: str | None = None
    generation_condition_match: bool | None = None
    generation_source_path: str | None = None
    location: str | None = None
    position: int | None = None
    branch: str | None = None
    relation: str | None = None
    effect_status: str | None = None
    control_condition_match: bool | None = None
    control_status: str | None = None
    control_source_path: str | None = None


class ConditionRule(PartialOutput):
    rule_id: str | None = None
    condition: str | None = None
    matched: bool | None = None
    raw_relation_match: bool | None = None
    qualified_matched: bool | None = None
    qualification_status: str | None = None
    qualification_source_path: str | None = None
    status: str | None = None
    actors: list[ConditionActor] | None = None
    notes: str | None = None


class HiddenSupport(PartialOutput):
    position: int | None = None
    branch: str | None = None
    flying_branch: str | None = None
    reception: HiddenReception | None = None
    stage_conditions: HiddenStageConditions | None = None
    monthly_strength: MonthlyStrength | None = None
    flying_monthly_strength: MonthlyStrength | None = None
    supporting_conditions: list[ConditionRule] | None = None
    obstructing_conditions: list[ConditionRule] | None = None
    table_gaps: list[str] | None = None
    adjudication: str | None = None
    source_url: str | None = None
    scope: str | None = None


class HarmonyMember(PartialOutput):
    location: str | None = None
    position: int | None = None
    branch: str | None = None
    element: str | None = None
    activity: str | None = None
    outgoing_obstructions: list[str] | None = None
    activity_condition_match: bool | None = None
    day_void_fill_condition: bool | None = None


class HarmonyObstruction(PartialOutput):
    condition: str | None = None
    location: str | None = None
    position: int | None = None
    branch: str | None = None
    actor_location: str | None = None
    actor_branch: str | None = None


class HarmonyCandidate(PartialOutput):
    candidate_id: str | None = None
    group_branches: list[str] | None = None
    element: str | None = None
    pattern: str | None = None
    status: str | None = None
    members: list[HarmonyMember] | None = None
    active_positions: list[int] | None = None
    qualified_active_positions: list[int] | None = None
    unresolved_activity_positions: list[int] | None = None
    structural_status: str | None = None
    missing_branches: list[str] | None = None
    calendar_completions: list[ConditionActor] | None = None
    completion_paths: list[str] | None = None
    obstructions: list[HarmonyObstruction] | None = None
    contains_shi: bool | None = None
    relation_to_focus: str | None = None


class HarmonyRelation(PartialOutput):
    source_id: str | None = None
    target_id: str | None = None
    relation: str | None = None
    scope: str | None = None


class HarmonyEvidence(PartialOutput):
    candidates: list[HarmonyCandidate] | None = None
    relations: list[HarmonyRelation] | None = None
    source_url: str | None = None
    scope: str | None = None


class ScanSource(PartialOutput):
    id: str | None = None
    title: str | None = None
    editor: str | None = None
    publisher: str | None = None
    publication_year: int | None = None
    institution: str | None = None
    catalog_id: str | None = None
    file: str | None = None
    page_count: int | None = None
    url: str | None = None
    description_url: str | None = None
    license: str | None = None
    method: str | None = None


class ScanCollation(PartialOutput):
    id: str | None = None
    chapter: str | None = None
    pdf_pages: list[int] | None = None
    printed_pages: list[str] | None = None
    quote: str | None = None
    additional_quotes: list[str] | None = None
    transcription_reading: str | None = None
    finding: str | None = None
    implementation: str | None = None


class ScanProfile(PartialOutput):
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source: ScanSource | None = None
    collations: list[ScanCollation] | None = None
    scope: str | None = None


class RoleCondition(PartialOutput):
    rule_id: str | None = None
    condition: str | None = None
    predicate: OpenJsonValue | None = None
    matched: bool | None = None
    status: str | None = None
    source_url: str | None = None
    progress_adjusted_matched: bool | None = None
    progress_adjusted_status: str | None = None
    conditional_matched: bool | None = None
    conditional_status: str | None = None


class RoleEffectLine(PartialOutput):
    growth_source_path: str | None = None
    cessation_source_path: str | None = None
    generation_source_path: str | None = None
    position: int | None = None
    branch: str | None = None
    role: str | None = None
    atom_values: dict[str, bool | None] | None = None
    actors: list[ConditionActor] | None = None
    binding_cues: list[str] | None = None
    monthly_strength: MonthlyStrength | None = None
    supporting_conditions: list[RoleCondition] | None = None
    obstructing_conditions: list[RoleCondition] | None = None
    adjudication: str | None = None
    strength_source_path: str | None = None
    progress_atom_values: dict[str, bool | None] | None = None
    progress_source_path: str | None = None
    conditional_atom_values: dict[str, bool | None] | None = None
    control_source_path: str | None = None
    clash_source_path: str | None = None


class RoleChain(PartialOutput):
    route_condition_match: bool | None = None
    route_status: str | None = None
    route_source_path: str | None = None
    chain_id: str | None = None
    positions: list[int] | None = None
    focus_location: str | None = None
    status: str | None = None
    binding_positions: list[int] | None = None
    obstructed_positions: list[int] | None = None
    uncertainties: list[str] | None = None
    source_url: str | None = None


class RoleEffects(PartialOutput):
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_url: str | None = None
    status: str | None = None
    lines: list[RoleEffectLine] | None = None
    chains: list[RoleChain] | None = None
    focus_robustness: str | None = None
    textual_issues: list[dict[str, OpenJsonValue]] | None = None
    scope: str | None = None


class StrengthActor(PartialOutput):
    metal_si_combined_effect_condition: bool | None = None
    metal_si_growth_condition: bool | None = None
    harm_condition_match: bool | None = None
    qualification_source_path: str | None = None
    back_generation_condition: bool | None = None
    back_generation_source_path: str | None = None
    generation_condition_match: bool | None = None
    target_reception_condition: bool | None = None
    benefit_now: bool | None = None
    generation_source_path: str | None = None
    location: str | None = None
    position: int | None = None
    branch: str | None = None
    reason: str | None = None
    grounded: bool | None = None
    held: bool | None = None
    source_grounded: bool | None = None
    activity_pending: bool | None = None
    control_condition_match: bool | None = None
    control_status: str | None = None
    control_source_path: str | None = None
    day_clash_break_condition: bool | None = None
    clash_source_path: str | None = None


class ClassicalStrength(PartialOutput):
    status: str | None = None
    is_supported: bool | None = None
    is_weak: bool | None = None
    is_failing: bool | None = None
    supports: list[StrengthActor] | None = None
    pending_supports: list[StrengthActor] | None = None
    blocked_supports: list[StrengthActor] | None = None
    blocked_oppositions: list[StrengthActor] | None = None
    oppositions: list[StrengthActor] | None = None
    source_url: str | None = None
    scope: str | None = None
    day_clash_break_condition: bool | None = None
    day_clash_break_status: str | None = None


class TombEvidence(PartialOutput):
    activity_condition_match: bool | None = None
    location: str | None = None
    position: int | None = None
    branch: str | None = None
    breakers: list[StrengthActor] | None = None
    pending_breakers: list[StrengthActor] | None = None
    ignored_breakers: list[StrengthActor] | None = None
    is_xunkong: bool | None = None
    is_true_tomb: bool | None = None
    status: str | None = None
    source_url: str | None = None


class ClassicalLineAssessment(PartialOutput):
    position: int | None = None
    branch: str | None = None
    strength: ClassicalStrength | None = None
    tomb_branch: str | None = None
    month_tomb_relation: bool | None = None
    tombs: list[TombEvidence] | None = None
    entered_tomb: bool | None = None


class ClassicalAssessment(PartialOutput):
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_url: str | None = None
    lines: list[ClassicalLineAssessment] | None = None
    focus: ClassicalLineAssessment | None = None
    resolution_notes: list[str] | None = None
    scope: str | None = None


class LiuyaoConditions(PartialOutput):
    month_break_conditions: dict[str, OpenJsonValue] | None = None
    penalty_conditions: PenaltyConditions | None = None
    growth_conditions: GrowthConditions | None = None
    cessation_conditions: CessationConditions | None = None
    stage_knowledge: StageKnowledge | None = None
    routing_conditions: RoutingConditions | None = None
    back_generation_conditions: BackGenerationConditions | None = None
    generation_conditions: GenerationConditions | None = None
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    lines: list[ConditionalLine] | None = None
    interaction_edges: list[InteractionEdge] | None = None
    role_effects: RoleEffects | None = None
    classical_assessment: ClassicalAssessment | None = None
    control_conditions: ControlConditions | None = None
    clash_conditions: ClashConditions | None = None
    void_conditions: VoidConditions | None = None
    focus: FocusEvidence | None = None
    timing_candidates: TimingCandidates | None = None
    three_harmony: HarmonyEvidence | None = None
    hidden_conditions: list[HiddenSupport] | None = None
    classical_scan: ScanProfile | None = None
    source_revisions: dict[str, DivinationSource] | None = None
    textual_issues: list[str] | None = None
    scope: str | None = None
