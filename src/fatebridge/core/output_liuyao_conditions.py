"""Optional nested fields for the explicitly bounded Liu Yao condition layer."""

from typing import Any, Dict, List, Optional

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_liuyao_cessation import CessationConditions
from fatebridge.core.output_liuyao_clash import ClashConditions
from fatebridge.core.output_liuyao_control import ControlConditions
from fatebridge.core.output_liuyao_generation import GenerationConditions
from fatebridge.core.output_liuyao_growth import GrowthConditions
from fatebridge.core.output_liuyao_hidden import HiddenReception
from fatebridge.core.output_liuyao_penalty import PenaltyConditions
from fatebridge.core.output_liuyao_rescue import BackGenerationConditions
from fatebridge.core.output_liuyao_routing import RoutingConditions
from fatebridge.core.output_liuyao_stages import HiddenStageConditions, StageKnowledge
from fatebridge.core.output_liuyao_void import VoidConditions


class DivinationSource(PartialOutput):
    title: Optional[str] = None
    revision: Optional[int] = None
    source_url: Optional[str] = None
    wikitext_sha256: Optional[str] = None


class MonthlyStrength(PartialOutput):
    category: Optional[str] = None
    monthly_supported: Optional[bool] = None
    residual_qi: Optional[bool] = None
    scope: Optional[str] = None


class ProgressClause(PartialOutput):
    rule_id: Optional[str] = None
    condition: Optional[str] = None
    matched: Optional[bool] = None
    raw_matched: Optional[bool] = None
    status: Optional[str] = None
    source_url: Optional[str] = None


class ChangedCalendarStrength(PartialOutput):
    status: Optional[str] = None
    is_supported: Optional[bool] = None
    is_weak: Optional[bool] = None
    scope: Optional[str] = None


class ProgressConditions(PartialOutput):
    structural_pair: Optional[str] = None
    original_branch: Optional[str] = None
    changed_branch: Optional[str] = None
    original_month_strength: Optional[str] = None
    changed_month_strength: Optional[str] = None
    has_void_or_month_break: Optional[bool] = None
    has_current_void_or_month_obstruction: Optional[bool] = None
    event_horizon: Optional[str] = None
    state: Optional[str] = None
    condition_now: Optional[bool] = None
    original_supported: Optional[bool] = None
    original_weak: Optional[bool] = None
    original_strength_basis: Optional[str] = None
    original_strength_source_path: Optional[str] = None
    changed_calendar_strength: Optional[ChangedCalendarStrength] = None
    clauses: Optional[List[ProgressClause]] = None
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    adjudication: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    textual_issues: Optional[List[Dict[str, Any]]] = None
    scope: Optional[str] = None


class ConditionalLine(PartialOutput):
    position: Optional[int] = None
    monthly_strength: Optional[MonthlyStrength] = None
    activity: Optional[str] = None
    activity_condition_match: Optional[bool] = None
    activity_condition_status: Optional[str] = None
    supporting_moving_positions: Optional[List[int]] = None
    supporting_static_positions: Optional[List[int]] = None
    binding_cues: Optional[List[str]] = None
    outgoing_obstructions: Optional[List[str]] = None
    day_stage: Optional[str] = None
    month_stage: Optional[str] = None
    changed_stage: Optional[str] = None
    stage_cautions: Optional[List[str]] = None
    efficacy: Optional[str] = None
    progress_conditions: Optional[ProgressConditions] = None


class InteractionEdge(PartialOutput):
    metal_si_combined_effect_condition: Optional[bool] = None
    raw_control_condition_match: Optional[bool] = None
    metal_si_growth_condition: Optional[bool] = None
    metal_si_growth_source_path: Optional[str] = None
    qualified_back_control_condition: Optional[bool] = None
    own_si_growth_source_path: Optional[str] = None
    qualified_routing_condition: Optional[bool] = None
    qualified_routing_status: Optional[str] = None
    conditional_routing_chain_ids: Optional[List[str]] = None
    rejected_routing_chain_ids: Optional[List[str]] = None
    generation_status: Optional[str] = None
    target_reception_status: Optional[str] = None
    generation_condition_match: Optional[bool] = None
    target_reception_condition: Optional[bool] = None
    benefit_now: Optional[bool] = None
    generation_source_path: Optional[str] = None
    source_kind: Optional[str] = None
    source_position: Optional[int] = None
    target_kind: Optional[str] = None
    target_position: Optional[int] = None
    relation: Optional[str] = None
    effect_status: Optional[str] = None
    source_url: Optional[str] = None
    routing_chain_ids: Optional[List[str]] = None
    control_condition_match: Optional[bool] = None
    control_status: Optional[str] = None
    control_source_path: Optional[str] = None


class FocusCandidate(PartialOutput):
    location: Optional[str] = None
    position: Optional[int] = None
    branch: Optional[str] = None
    element: Optional[str] = None
    liuqin: Optional[str] = None
    moving: Optional[bool] = None


class FocusRole(PartialOutput):
    location: Optional[str] = None
    position: Optional[int] = None
    branch: Optional[str] = None
    role: Optional[str] = None


class FocusEvidence(PartialOutput):
    status: Optional[str] = None
    requested_kinship: Optional[str] = None
    requested_kind: Optional[str] = None
    selected: Optional[FocusCandidate] = None
    candidates: Optional[List[FocusCandidate]] = None
    roles: Optional[List[FocusRole]] = None
    scope: Optional[str] = None


class CivilInterval(PartialOutput):
    method: Optional[str] = None
    wall_start: Optional[str] = None
    wall_end: Optional[str] = None
    interval_index: Optional[int] = None
    interval_count: Optional[int] = None
    start_utc: Optional[str] = None
    end_utc: Optional[str] = None
    duration_seconds: Optional[float] = None
    timezone: Optional[str] = None
    scope: Optional[str] = None


class ExcludedCivilDay(PartialOutput):
    effective_date: Optional[str] = None
    day_ganzhi: Optional[str] = None
    wall_start: Optional[str] = None
    wall_end: Optional[str] = None
    matched_rules: Optional[List[str]] = None
    status: Optional[str] = None
    method: Optional[str] = None


class ConditionWindow(PartialOutput):
    civil_interval: Optional[CivilInterval] = None
    effective_date: Optional[str] = None
    day_ganzhi: Optional[str] = None
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    matched_rules: Optional[List[str]] = None
    requires_month_reassessment: Optional[bool] = None


class TimingCandidates(PartialOutput):
    calendar_exclusions: Optional[List[ExcludedCivilDay]] = None
    status: Optional[str] = None
    granularity: Optional[str] = None
    requested_days: Optional[int] = None
    windows: Optional[List[ConditionWindow]] = None
    source_url: Optional[str] = None
    scope: Optional[str] = None


class ConditionActor(PartialOutput):
    raw_generation_condition_match: Optional[bool] = None
    penalty_source_path: Optional[str] = None
    generation_condition_match: Optional[bool] = None
    generation_source_path: Optional[str] = None
    location: Optional[str] = None
    position: Optional[int] = None
    branch: Optional[str] = None
    relation: Optional[str] = None
    effect_status: Optional[str] = None
    control_condition_match: Optional[bool] = None
    control_status: Optional[str] = None
    control_source_path: Optional[str] = None


class ConditionRule(PartialOutput):
    rule_id: Optional[str] = None
    condition: Optional[str] = None
    matched: Optional[bool] = None
    raw_relation_match: Optional[bool] = None
    qualified_matched: Optional[bool] = None
    qualification_status: Optional[str] = None
    qualification_source_path: Optional[str] = None
    status: Optional[str] = None
    actors: Optional[List[ConditionActor]] = None
    notes: Optional[str] = None


class HiddenSupport(PartialOutput):
    position: Optional[int] = None
    branch: Optional[str] = None
    flying_branch: Optional[str] = None
    reception: Optional[HiddenReception] = None
    stage_conditions: Optional[HiddenStageConditions] = None
    monthly_strength: Optional[MonthlyStrength] = None
    flying_monthly_strength: Optional[MonthlyStrength] = None
    supporting_conditions: Optional[List[ConditionRule]] = None
    obstructing_conditions: Optional[List[ConditionRule]] = None
    table_gaps: Optional[List[str]] = None
    adjudication: Optional[str] = None
    source_url: Optional[str] = None
    scope: Optional[str] = None


class HarmonyMember(PartialOutput):
    location: Optional[str] = None
    position: Optional[int] = None
    branch: Optional[str] = None
    element: Optional[str] = None
    activity: Optional[str] = None
    outgoing_obstructions: Optional[List[str]] = None
    activity_condition_match: Optional[bool] = None
    day_void_fill_condition: Optional[bool] = None


class HarmonyObstruction(PartialOutput):
    condition: Optional[str] = None
    location: Optional[str] = None
    position: Optional[int] = None
    branch: Optional[str] = None
    actor_location: Optional[str] = None
    actor_branch: Optional[str] = None


class HarmonyCandidate(PartialOutput):
    candidate_id: Optional[str] = None
    group_branches: Optional[List[str]] = None
    element: Optional[str] = None
    pattern: Optional[str] = None
    status: Optional[str] = None
    members: Optional[List[HarmonyMember]] = None
    active_positions: Optional[List[int]] = None
    qualified_active_positions: Optional[List[int]] = None
    unresolved_activity_positions: Optional[List[int]] = None
    structural_status: Optional[str] = None
    missing_branches: Optional[List[str]] = None
    calendar_completions: Optional[List[ConditionActor]] = None
    completion_paths: Optional[List[str]] = None
    obstructions: Optional[List[HarmonyObstruction]] = None
    contains_shi: Optional[bool] = None
    relation_to_focus: Optional[str] = None


class HarmonyRelation(PartialOutput):
    source_id: Optional[str] = None
    target_id: Optional[str] = None
    relation: Optional[str] = None
    scope: Optional[str] = None


class HarmonyEvidence(PartialOutput):
    candidates: Optional[List[HarmonyCandidate]] = None
    relations: Optional[List[HarmonyRelation]] = None
    source_url: Optional[str] = None
    scope: Optional[str] = None


class ScanSource(PartialOutput):
    id: Optional[str] = None
    title: Optional[str] = None
    editor: Optional[str] = None
    publisher: Optional[str] = None
    publication_year: Optional[int] = None
    institution: Optional[str] = None
    catalog_id: Optional[str] = None
    file: Optional[str] = None
    sha256: Optional[str] = None
    page_count: Optional[int] = None
    url: Optional[str] = None
    description_url: Optional[str] = None
    license: Optional[str] = None
    method: Optional[str] = None


class ScanCollation(PartialOutput):
    id: Optional[str] = None
    chapter: Optional[str] = None
    pdf_pages: Optional[List[int]] = None
    printed_pages: Optional[List[str]] = None
    quote: Optional[str] = None
    additional_quotes: Optional[List[str]] = None
    transcription_reading: Optional[str] = None
    finding: Optional[str] = None
    implementation: Optional[str] = None


class ScanProfile(PartialOutput):
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source: Optional[ScanSource] = None
    collations: Optional[List[ScanCollation]] = None
    scope: Optional[str] = None


class RoleCondition(PartialOutput):
    rule_id: Optional[str] = None
    condition: Optional[str] = None
    predicate: Optional[Any] = None
    matched: Optional[bool] = None
    status: Optional[str] = None
    source_url: Optional[str] = None
    progress_adjusted_matched: Optional[bool] = None
    progress_adjusted_status: Optional[str] = None
    conditional_matched: Optional[bool] = None
    conditional_status: Optional[str] = None


class RoleEffectLine(PartialOutput):
    growth_source_path: Optional[str] = None
    cessation_source_path: Optional[str] = None
    generation_source_path: Optional[str] = None
    position: Optional[int] = None
    branch: Optional[str] = None
    role: Optional[str] = None
    atom_values: Optional[Dict[str, Optional[bool]]] = None
    actors: Optional[List[ConditionActor]] = None
    binding_cues: Optional[List[str]] = None
    monthly_strength: Optional[MonthlyStrength] = None
    supporting_conditions: Optional[List[RoleCondition]] = None
    obstructing_conditions: Optional[List[RoleCondition]] = None
    adjudication: Optional[str] = None
    strength_source_path: Optional[str] = None
    progress_atom_values: Optional[Dict[str, Optional[bool]]] = None
    progress_source_path: Optional[str] = None
    conditional_atom_values: Optional[Dict[str, Optional[bool]]] = None
    control_source_path: Optional[str] = None
    clash_source_path: Optional[str] = None


class RoleChain(PartialOutput):
    route_condition_match: Optional[bool] = None
    route_status: Optional[str] = None
    route_source_path: Optional[str] = None
    chain_id: Optional[str] = None
    positions: Optional[List[int]] = None
    focus_location: Optional[str] = None
    status: Optional[str] = None
    binding_positions: Optional[List[int]] = None
    obstructed_positions: Optional[List[int]] = None
    uncertainties: Optional[List[str]] = None
    source_url: Optional[str] = None


class RoleEffects(PartialOutput):
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    status: Optional[str] = None
    lines: Optional[List[RoleEffectLine]] = None
    chains: Optional[List[RoleChain]] = None
    focus_robustness: Optional[str] = None
    textual_issues: Optional[List[Dict[str, Any]]] = None
    scope: Optional[str] = None


class StrengthActor(PartialOutput):
    metal_si_combined_effect_condition: Optional[bool] = None
    metal_si_growth_condition: Optional[bool] = None
    harm_condition_match: Optional[bool] = None
    qualification_source_path: Optional[str] = None
    back_generation_condition: Optional[bool] = None
    back_generation_source_path: Optional[str] = None
    generation_condition_match: Optional[bool] = None
    target_reception_condition: Optional[bool] = None
    benefit_now: Optional[bool] = None
    generation_source_path: Optional[str] = None
    location: Optional[str] = None
    position: Optional[int] = None
    branch: Optional[str] = None
    reason: Optional[str] = None
    grounded: Optional[bool] = None
    held: Optional[bool] = None
    source_grounded: Optional[bool] = None
    activity_pending: Optional[bool] = None
    control_condition_match: Optional[bool] = None
    control_status: Optional[str] = None
    control_source_path: Optional[str] = None
    day_clash_break_condition: Optional[bool] = None
    clash_source_path: Optional[str] = None


class ClassicalStrength(PartialOutput):
    status: Optional[str] = None
    is_supported: Optional[bool] = None
    is_weak: Optional[bool] = None
    is_failing: Optional[bool] = None
    supports: Optional[List[StrengthActor]] = None
    pending_supports: Optional[List[StrengthActor]] = None
    blocked_supports: Optional[List[StrengthActor]] = None
    blocked_oppositions: Optional[List[StrengthActor]] = None
    oppositions: Optional[List[StrengthActor]] = None
    source_url: Optional[str] = None
    scope: Optional[str] = None
    day_clash_break_condition: Optional[bool] = None
    day_clash_break_status: Optional[str] = None


class TombEvidence(PartialOutput):
    activity_condition_match: Optional[bool] = None
    location: Optional[str] = None
    position: Optional[int] = None
    branch: Optional[str] = None
    breakers: Optional[List[StrengthActor]] = None
    pending_breakers: Optional[List[StrengthActor]] = None
    ignored_breakers: Optional[List[StrengthActor]] = None
    is_xunkong: Optional[bool] = None
    is_true_tomb: Optional[bool] = None
    status: Optional[str] = None
    source_url: Optional[str] = None


class ClassicalLineAssessment(PartialOutput):
    position: Optional[int] = None
    branch: Optional[str] = None
    strength: Optional[ClassicalStrength] = None
    tomb_branch: Optional[str] = None
    month_tomb_relation: Optional[bool] = None
    tombs: Optional[List[TombEvidence]] = None
    entered_tomb: Optional[bool] = None


class ClassicalAssessment(PartialOutput):
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    lines: Optional[List[ClassicalLineAssessment]] = None
    focus: Optional[ClassicalLineAssessment] = None
    resolution_notes: Optional[List[str]] = None
    scope: Optional[str] = None


class LiuyaoConditions(PartialOutput):
    month_break_conditions: Optional[Dict[str, Any]] = None
    penalty_conditions: Optional[PenaltyConditions] = None
    growth_conditions: Optional[GrowthConditions] = None
    cessation_conditions: Optional[CessationConditions] = None
    stage_knowledge: Optional[StageKnowledge] = None
    routing_conditions: Optional[RoutingConditions] = None
    back_generation_conditions: Optional[BackGenerationConditions] = None
    generation_conditions: Optional[GenerationConditions] = None
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    lines: Optional[List[ConditionalLine]] = None
    interaction_edges: Optional[List[InteractionEdge]] = None
    role_effects: Optional[RoleEffects] = None
    classical_assessment: Optional[ClassicalAssessment] = None
    control_conditions: Optional[ControlConditions] = None
    clash_conditions: Optional[ClashConditions] = None
    void_conditions: Optional[VoidConditions] = None
    focus: Optional[FocusEvidence] = None
    timing_candidates: Optional[TimingCandidates] = None
    three_harmony: Optional[HarmonyEvidence] = None
    hidden_conditions: Optional[List[HiddenSupport]] = None
    classical_scan: Optional[ScanProfile] = None
    source_revisions: Optional[Dict[str, DivinationSource]] = None
    textual_issues: Optional[List[str]] = None
    scope: Optional[str] = None
