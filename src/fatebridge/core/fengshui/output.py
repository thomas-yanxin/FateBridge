"""Public layered contract, including projection-compatible optional fields."""

from typing import Dict, List, Literal, Optional

from pydantic import Field, ValidationInfo, model_validator

from fatebridge.core.output_base import FullFact
from fatebridge.core.response_models import (
    Object,
    PartialOutput,
    ProjectedOutput,
    RunMetadata,
    SnapshotExport,
)

from .spatial_outputs import MeasuredLayoutOutput


class RuleSource(PartialOutput):
    # Only exposed as array items: projections select sources whole.
    source_id: str
    title: str
    url: str
    kind: str
    scope: str


class Ruleset(PartialOutput):
    ruleset_id: Optional[str] = None
    version: Optional[str] = None
    method: Optional[str] = None
    source_ids: Optional[List[str]] = None
    sources: Optional[List[RuleSource]] = None
    scope: Optional[str] = None
    conventions: Optional[List[str]] = None
    bundle_version: Optional[str] = None


class Star(PartialOutput):
    name: Optional[str] = None
    element: Optional[str] = None
    polarity: Optional[Literal["auspicious", "inauspicious"]] = None


class Palace(PartialOutput):
    direction: Optional[str] = None
    palace_number: Optional[int] = None
    trigram: Optional[str] = None
    annual_star_number: Optional[int] = None
    annual_star: Optional[Star] = None
    star: Optional[Star] = None
    you_nian_trace: Optional[Object] = None
    palace_star_relationship: Optional[Object] = None
    subject_id: Optional[str] = None
    rule_id: Optional[str] = None
    source_ids: Optional[List[str]] = None


class MingguaCandidate(PartialOutput):
    gender_convention: Optional[Literal["male", "female"]] = None
    raw_number: Optional[int] = None
    palace_number: Optional[int] = None
    substitution: Optional[bool] = None
    trigram: Optional[str] = None
    group: Optional[Literal["east", "west"]] = None
    sectors: Optional[Dict[str, Palace]] = None


class PersonalChart(PartialOutput):
    status: Optional[Literal["complete", "partial"]] = None
    subject_id: Optional[str] = None
    candidates: Optional[List[MingguaCandidate]] = None
    time_context: Optional[Object] = None
    missing_inputs: Optional[List[str]] = None


class HouseChart(PartialOutput):
    object_id: Optional[str] = None
    sitting_trigram: Optional[str] = None
    north_reference: Optional[Literal["magnetic", "true"]] = None
    sectors: Optional[Dict[str, Palace]] = None
    candidate_id: Optional[str] = None
    candidate_only: Optional[bool] = None
    bearing_support: Optional[Object] = None


class Layer(PersonalChart):
    geomagnetic_reference: Optional[Object] = None
    ruleset: Optional[Ruleset] = None
    house: Optional[HouseChart] = None
    house_candidates: Optional[List[HouseChart]] = None
    house_orientation_context: Optional[Object] = None
    occupants: Optional[List[PersonalChart]] = None
    placement_findings: Optional[List[Object]] = None
    feature_findings: Optional[List[Object]] = None
    preferences: Optional[Dict[str, Object]] = None
    palaces: Optional[Dict[str, Palace]] = None
    effective_year: Optional[int] = None
    center_star_number: Optional[int] = None
    current_period: Optional[Object] = None
    directions: Optional[Dict[str, Object]] = None
    bearing: Optional[Object] = None


class NatalPalace(PartialOutput):
    direction: Optional[str] = None
    palace_number: Optional[int] = None
    period_star_number: Optional[int] = None
    mountain_star_number: Optional[int] = None
    facing_star_number: Optional[int] = None


class NatalCandidate(PartialOutput):
    candidate_id: Optional[str] = None
    period_number: Optional[int] = None
    facing: Optional[Object] = None
    sitting: Optional[Object] = None
    chart_mode: Optional[Literal["lower", "replacement"]] = None
    mode_reason: Optional[str] = None
    bearing_support: Optional[Object] = None
    palaces: Optional[Dict[str, NatalPalace]] = None
    period_chart: Optional[Dict[str, int]] = None
    mountain_chart: Optional[Dict[str, int]] = None
    facing_chart: Optional[Dict[str, int]] = None
    trace: Optional[Dict[str, Object]] = None
    flight_path: Optional[List[str]] = None
    structure: Optional[Object] = None


class NatalLayer(PartialOutput):
    source_comparison: Optional[Object] = None
    city_gate_analysis: Optional[Object] = None
    interpretation: Optional["NatalInterpretation"] = None
    status: Optional[Literal["complete", "partial"]] = None
    subject_id: Optional[str] = None
    ruleset: Optional[Ruleset] = None
    period_context: Optional[Object] = None
    orientation_context: Optional[Object] = None
    chart: Optional[NatalCandidate] = None
    candidates: Optional[List[NatalCandidate]] = None
    missing_inputs: Optional[List[str]] = None
    interpretation_scope: Optional[str] = None
    mountain_registry: Optional[List[Object]] = None


class MonthlyPalace(PartialOutput):
    direction: Optional[str] = None
    label: Optional[str] = None
    palace_number: Optional[int] = None
    trigram: Optional[str] = None
    element: Optional[str] = None
    monthly_star_number: Optional[int] = None
    monthly_star: Optional[Object] = None
    method: Optional[str] = None
    rule_id: Optional[str] = None
    source_ids: Optional[List[str]] = None


class MonthlyLayer(PartialOutput):
    status: Optional[Literal["complete", "partial"]] = None
    ruleset: Optional[Ruleset] = None
    time_context: Optional[Object] = None
    year_branch: Optional[str] = None
    year_group: Optional[Object] = None
    center_star_number: Optional[int] = None
    palaces: Optional[Dict[str, MonthlyPalace]] = None
    flight_path: Optional[List[str]] = None
    trace: Optional[Object] = None
    position_reading: Optional[Object] = None
    missing_inputs: Optional[List[str]] = None
    interpretation_scope: Optional[str] = None
    limitations: Optional[List[str]] = None


class Layers(PartialOutput):
    directions: Optional[Layer] = None
    minggua: Optional[Layer] = None
    bazhai: Optional[Layer] = None
    jinsuo: Optional[Layer] = None
    annual_stars: Optional[Layer] = None
    monthly_stars: Optional[MonthlyLayer] = None
    xuankong_natal: Optional[NatalLayer] = None


class NatalInterpretation(PartialOutput):
    status: Optional[Literal["complete", "partial"]] = None
    ruleset_id: Optional[str] = None
    timeliness_ruleset: Optional[Ruleset] = None
    fixed_lingzheng_analysis: Optional[Object] = None
    current_period_context: Optional[Object] = None
    candidates: Optional[List[Object]] = None
    missing_inputs: Optional[List[str]] = None
    unsupported_queries: Optional[List[Object]] = None
    rule_coverage_status: Optional[str] = None
    overall_auspiciousness: Optional[str] = None
    rule_trace: Optional[List[Object]] = None
    limitations: Optional[List[str]] = None


class PendingConfirmation(PartialOutput):
    path: Optional[str] = None
    reason: Optional[str] = None
    object_id: Optional[str] = None
    item_id: Optional[str] = None
    action_id: Optional[str] = None
    required_for: Optional[Literal["assessment", "action", "optional_action"]] = None


class RuleCoverageCounts(PartialOutput):
    supported: Optional[int] = Field(default=None, ge=0)
    confirmed_unsupported: Optional[int] = Field(default=None, ge=0)
    unknown: Optional[int] = Field(default=None, ge=0)


class ActionCounts(PartialOutput):
    ready: Optional[int] = Field(default=None, ge=0)
    conditional: Optional[int] = Field(default=None, ge=0)
    candidate: Optional[int] = Field(default=None, ge=0)
    blocked: Optional[int] = Field(default=None, ge=0)


class ConsultationFollowUp(PartialOutput):
    conclusion_candidates: Optional[List[str]] = Field(
        default=None,
        description="引用pending_confirmations.path；仅在会改变当前结论时择要追问，不是必补清单或新请求参数",
    )
    execution_only: Optional[List[str]] = Field(
        default=None,
        description="引用pending_confirmations.path；仅用于落实动作，不阻塞普通解释或条件式建议",
    )
    selection_policy: Optional[Literal["ask_only_if_changes_requested_conclusion"]] = (
        None
    )
    unsupported_policy: Optional[
        Literal["explain_limit_without_requesting_more_input"]
    ] = None


class AnalysisProgress(PartialOutput):
    interpretation_status: Optional[
        Literal["available", "conditional", "scope_only", "insufficient_evidence"]
    ] = Field(
        default=None,
        description="已有依据可解释／仅条件式解释／仅说明未覆盖范围／尚无事实依据；独立于计算完整性和执行状态",
    )
    follow_up: Optional[ConsultationFollowUp] = None
    calculation_status: Optional[Literal["complete", "partial"]] = None
    rule_coverage_status: Optional[
        Literal["reviewed", "needs_confirmation", "limited"]
    ] = None
    assessment_complete: Optional[bool] = None
    rule_coverage_count_unit: Optional[
        Literal["surface_items", "surface_items_and_layout_checks"]
    ] = None
    rule_coverage_counts: Optional[RuleCoverageCounts] = None
    action_readiness: Optional[
        Literal[
            "no_action_needed",
            "not_evaluated",
            "ready",
            "needs_confirmation",
            "blocked",
            "mixed",
        ]
    ] = None
    action_count_unit: Optional[Literal["candidate_actions"]] = None
    action_counts: Optional[ActionCounts] = None
    optional_action_count: Optional[int] = Field(default=None, ge=0)
    pending_confirmations: Optional[List[PendingConfirmation]] = None


class SurfaceItemFinding(PartialOutput):
    object_id: Optional[str] = None
    status: Optional[str] = None
    rule_coverage_status: Optional[
        Literal["reviewed_supported", "reviewed_unsupported", "needs_confirmation"]
    ] = None


class SurfaceAction(PartialOutput):
    action_id: Optional[str] = None
    item_id: Optional[str] = None
    optional: Optional[bool] = None
    action: Optional[str] = None
    status: Optional[
        Literal["ready", "conditional_option", "candidate_only", "blocked"]
    ] = None
    pending_confirmations: Optional[List[PendingConfirmation]] = None


class SurfaceFinding(PartialOutput):
    object_id: Optional[str] = None
    item_findings: Optional[List[SurfaceItemFinding]] = None
    action_options: Optional[List[SurfaceAction]] = None


class SurfaceAnalysis(PartialOutput):
    status: Optional[Literal["complete", "partial"]] = None
    analysis_progress: Optional[AnalysisProgress] = None
    findings: Optional[List[SurfaceFinding]] = None
    missing_inputs: Optional[List[str]] = None
    uncovered_item_ids: Optional[List[str]] = None


class Coverage(PartialOutput):
    measured_workstation: Optional[Object] = None
    city_gate_status: Optional[Literal["complete", "partial"]] = None
    city_gate_calculation_status: Optional[Literal["complete", "partial"]] = None
    city_gate_missing_inputs: Optional[List[str]] = None
    method_priority_review: Optional[Object] = None
    environmental_context_status: Optional[Literal["complete", "partial"]] = None
    environmental_context_missing_inputs: Optional[List[str]] = None
    natal_interpretation_status: Optional[Literal["complete", "partial"]] = None
    natal_interpretation_missing_inputs: Optional[List[str]] = None
    scene_scope: Optional[Object] = None
    analysis_progress: Optional[AnalysisProgress] = None
    implemented_layers: Optional[List[str]] = None
    missing_inputs: Optional[List[str]] = None
    unavailable_layers: Optional[List[str]] = None
    not_requested_layers: Optional[List[str]] = None
    supplemental_rulesets: Optional[List[str]] = None
    layout_status: Optional[Literal["complete", "partial"]] = None
    layout_missing_inputs: Optional[List[str]] = None
    requested_analysis_status: Optional[Literal["complete", "partial"]] = None


class FengshuiOutput(ProjectedOutput):
    calculation_reading: Optional[Object] = None
    method_policy: Optional[Object] = None
    method_details: Optional[Object] = None
    analysis_type: Optional[str] = None
    engine: Optional[str] = None
    status: Optional[Literal["complete", "partial"]] = None
    layers: FullFact[Optional[Layers]] = None
    rulesets: Optional[List[Ruleset]] = None
    coverage: Optional[Coverage] = None
    conflicts: Optional[List[Object]] = None
    rule_trace: Optional[List[Object]] = None
    summary: Optional[str] = None
    snapshot_text: Optional[str] = None
    snapshot_export: Optional[SnapshotExport] = None
    run_metadata: Optional[RunMetadata] = None
    layout_analysis: Optional["LayoutAnalysis"] = None

    @model_validator(mode="after")
    def require_declared_layers(self, info: ValidationInfo) -> "FengshuiOutput":
        if info.context and info.context.get("full_result") and self.coverage:
            actual = (
                {
                    name
                    for name in self.layers.model_fields_set
                    if getattr(self.layers, name) is not None
                }
                if self.layers is not None
                else set()
            )
            if set(self.coverage.implemented_layers or []) - actual:
                raise ValueError("完整风水结果缺少已声明计算的图层")
        return self


class LayoutAnalysis(PartialOutput):
    workstation_layout_analysis: Optional[MeasuredLayoutOutput] = None
    environmental_context: Optional[Object] = None
    interior_analysis: Optional[Object] = None
    material_analysis: Optional[Object] = None
    workstation_analysis: Optional[Object] = None
    natal_interpretation: Optional[NatalInterpretation] = None
    alternatives_analysis: Optional[Object] = None
    surface_analysis: Optional[SurfaceAnalysis] = None
    analysis_progress: Optional[AnalysisProgress] = None
    status: Optional[Literal["complete", "partial"]] = None
    calculation_scope: Optional[str] = None
    placement_findings: Optional[List[Object]] = None
    adjustment_options: Optional[List[Object]] = None
    environment_adjustments: Optional[List[Object]] = None
    element_relationships: Optional[List[Object]] = None
    missing_inputs: Optional[List[str]] = None
    unsupported_queries: Optional[List[str]] = None
    limitations: Optional[List[str]] = None
    form_analysis: Optional[Object] = None
    element_remedies: Optional[List[Object]] = None
    annual_remedies: Optional[Object] = None
    supplemental_rulesets: Optional[List[Ruleset]] = None
    supplement_statuses: Optional[Object] = None
    method_disagreements: Optional[List[Object]] = None
