"""Public layered contract, including projection-compatible optional fields."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, ValidationInfo, model_validator

from fatebridge.core.contracts.output_base import FULL_FACT
from fatebridge.core.fengshui.spatial_outputs import MeasuredLayoutOutput
from fatebridge.core.response_models import (
    Object,
    PartialOutput,
    ProjectedOutput,
    RunMetadata,
)


class RuleSource(PartialOutput):
    title: str | None = None
    url: str | None = None
    kind: str | None = None
    author: str | None = None
    author_identity_url: str | None = None
    edition: str | None = None
    isbn: str | None = None


class Ruleset(PartialOutput):
    ruleset_id: str | None = None
    version: str | None = None
    method: str | None = None
    source_ids: list[str] | None = None
    source_citations: dict[str, Object] | None = None
    scope: str | None = None
    conventions: list[str] | None = None
    bundle_version: str | None = None


class Star(PartialOutput):
    name: str | None = None
    element: str | None = None
    polarity: Literal["auspicious", "inauspicious"] | None = None


class Palace(PartialOutput):
    direction: str | None = None
    palace_number: int | None = None
    trigram: str | None = None
    annual_star_number: int | None = None
    annual_star: Star | None = None
    star: Star | None = None
    you_nian_trace: Object | None = None
    palace_star_relationship: Object | None = None
    subject_id: str | None = None
    rule_id: str | None = None
    source_ids: list[str] | None = None


class MingguaCandidate(PartialOutput):
    gender_convention: Literal["male", "female"] | None = None
    raw_number: int | None = None
    palace_number: int | None = None
    substitution: bool | None = None
    trigram: str | None = None
    group: Literal["east", "west"] | None = None
    sectors: dict[str, Palace] | None = None


class PersonalChart(PartialOutput):
    status: Literal["complete", "partial"] | None = None
    subject_id: str | None = None
    candidates: list[MingguaCandidate] | None = None
    time_context: Object | None = None
    missing_inputs: list[str] | None = None


class HouseChart(PartialOutput):
    object_id: str | None = None
    sitting_trigram: str | None = None
    north_reference: Literal["magnetic", "true"] | None = None
    sectors: dict[str, Palace] | None = None
    candidate_id: str | None = None
    candidate_only: bool | None = None
    bearing_support: Object | None = None


class Layer(PersonalChart):
    geomagnetic_reference: Object | None = None
    ruleset: Ruleset | None = None
    house: HouseChart | None = None
    house_candidates: list[HouseChart] | None = None
    house_orientation_context: Object | None = None
    occupants: list[PersonalChart] | None = None
    placement_findings: list[Object] | None = None
    feature_findings: list[Object] | None = None
    preferences: dict[str, Object] | None = None
    palaces: dict[str, Palace] | None = None
    effective_year: int | None = None
    center_star_number: int | None = None
    current_period: Object | None = None
    directions: dict[str, Object] | None = None
    bearing: Object | None = None


class NatalPalace(PartialOutput):
    direction: str | None = None
    palace_number: int | None = None
    period_star_number: int | None = None
    mountain_star_number: int | None = None
    facing_star_number: int | None = None


class NatalCandidate(PartialOutput):
    candidate_id: str | None = None
    period_number: int | None = None
    facing: Object | None = None
    sitting: Object | None = None
    chart_mode: Literal["lower", "replacement"] | None = None
    mode_reason: str | None = None
    bearing_support: Object | None = None
    palaces: dict[str, NatalPalace] | None = None
    period_chart: dict[str, int] | None = None
    mountain_chart: dict[str, int] | None = None
    facing_chart: dict[str, int] | None = None
    trace: dict[str, Object] | None = None
    flight_path: list[str] | None = None
    structure: Object | None = None


class NatalLayer(PartialOutput):
    source_comparison: Object | None = None
    city_gate_analysis: Object | None = None
    interpretation: NatalInterpretation | None = None
    status: Literal["complete", "partial"] | None = None
    subject_id: str | None = None
    ruleset: Ruleset | None = None
    period_context: Object | None = None
    orientation_context: Object | None = None
    chart: NatalCandidate | None = None
    candidates: list[NatalCandidate] | None = None
    missing_inputs: list[str] | None = None
    interpretation_scope: str | None = None
    mountain_registry: list[Object] | None = None


class MonthlyPalace(PartialOutput):
    direction: str | None = None
    label: str | None = None
    palace_number: int | None = None
    trigram: str | None = None
    element: str | None = None
    monthly_star_number: int | None = None
    monthly_star: Object | None = None
    method: str | None = None
    rule_id: str | None = None
    source_ids: list[str] | None = None


class MonthlyLayer(PartialOutput):
    status: Literal["complete", "partial"] | None = None
    ruleset: Ruleset | None = None
    time_context: Object | None = None
    year_branch: str | None = None
    year_group: Object | None = None
    center_star_number: int | None = None
    palaces: dict[str, MonthlyPalace] | None = None
    flight_path: list[str] | None = None
    trace: Object | None = None
    position_reading: Object | None = None
    missing_inputs: list[str] | None = None
    interpretation_scope: str | None = None
    limitations: list[str] | None = None


class Layers(PartialOutput):
    directions: Layer | None = None
    minggua: Layer | None = None
    bazhai: Layer | None = None
    jinsuo: Layer | None = None
    annual_stars: Layer | None = None
    monthly_stars: MonthlyLayer | None = None
    xuankong_natal: NatalLayer | None = None


class NatalInterpretation(PartialOutput):
    status: Literal["complete", "partial"] | None = None
    ruleset_id: str | None = None
    timeliness_ruleset: Ruleset | None = None
    fixed_lingzheng_analysis: Object | None = None
    current_period_context: Object | None = None
    candidates: list[Object] | None = None
    missing_inputs: list[str] | None = None
    unsupported_queries: list[Object] | None = None
    rule_coverage_status: str | None = None
    overall_auspiciousness: str | None = None
    rule_trace: list[Object] | None = None
    limitations: list[str] | None = None


class PendingConfirmation(PartialOutput):
    path: str | None = None
    reason: str | None = None
    object_id: str | None = None
    item_id: str | None = None
    action_id: str | None = None
    required_for: Literal["assessment", "action", "optional_action"] | None = None


class RuleCoverageCounts(PartialOutput):
    supported: int | None = Field(default=None, ge=0)
    confirmed_unsupported: int | None = Field(default=None, ge=0)
    unknown: int | None = Field(default=None, ge=0)


class ActionCounts(PartialOutput):
    ready: int | None = Field(default=None, ge=0)
    conditional: int | None = Field(default=None, ge=0)
    candidate: int | None = Field(default=None, ge=0)
    blocked: int | None = Field(default=None, ge=0)


class ConsultationFollowUp(PartialOutput):
    conclusion_candidates: list[str] | None = Field(
        default=None,
        description="引用pending_confirmations.path；仅在会改变当前结论时择要追问，不是必补清单或新请求参数",
    )
    execution_only: list[str] | None = Field(
        default=None,
        description="引用pending_confirmations.path；仅用于落实动作，不阻塞普通解释或条件式建议",
    )
    selection_policy: Literal["ask_only_if_changes_requested_conclusion"] | None = None
    unsupported_policy: (
        Literal["explain_limit_without_requesting_more_input"] | None
    ) = None


class AnalysisProgress(PartialOutput):
    interpretation_status: (
        Literal["available", "conditional", "scope_only", "insufficient_evidence"]
        | None
    ) = Field(
        default=None,
        description="已有依据可解释／仅条件式解释／仅说明未覆盖范围／尚无事实依据；独立于计算完整性和执行状态",
    )
    follow_up: ConsultationFollowUp | None = None
    calculation_status: Literal["complete", "partial"] | None = None
    rule_coverage_status: (
        Literal["reviewed", "needs_confirmation", "limited"] | None
    ) = None
    assessment_complete: bool | None = None
    rule_coverage_count_unit: (
        Literal["surface_items", "surface_items_and_layout_checks"] | None
    ) = None
    rule_coverage_counts: RuleCoverageCounts | None = None
    action_readiness: (
        Literal[
            "no_action_needed",
            "not_evaluated",
            "ready",
            "needs_confirmation",
            "blocked",
            "mixed",
        ]
        | None
    ) = None
    action_count_unit: Literal["candidate_actions"] | None = None
    action_counts: ActionCounts | None = None
    optional_action_count: int | None = Field(default=None, ge=0)
    pending_confirmations: list[PendingConfirmation] | None = None


class SurfaceItemFinding(PartialOutput):
    object_id: str | None = None
    status: str | None = None
    rule_coverage_status: (
        Literal["reviewed_supported", "reviewed_unsupported", "needs_confirmation"]
        | None
    ) = None


class SurfaceAction(PartialOutput):
    action_id: str | None = None
    item_id: str | None = None
    optional: bool | None = None
    action: str | None = None
    status: (
        Literal["ready", "conditional_option", "candidate_only", "blocked"] | None
    ) = None
    pending_confirmations: list[PendingConfirmation] | None = None


class SurfaceFinding(PartialOutput):
    object_id: str | None = None
    item_findings: list[SurfaceItemFinding] | None = None
    action_options: list[SurfaceAction] | None = None


class SurfaceAnalysis(PartialOutput):
    status: Literal["complete", "partial"] | None = None
    analysis_progress: AnalysisProgress | None = None
    findings: list[SurfaceFinding] | None = None
    missing_inputs: list[str] | None = None
    uncovered_item_ids: list[str] | None = None


class Coverage(PartialOutput):
    measured_workstation: Object | None = None
    city_gate_status: Literal["complete", "partial"] | None = None
    city_gate_calculation_status: Literal["complete", "partial"] | None = None
    city_gate_missing_inputs: list[str] | None = None
    method_priority_review: Object | None = None
    environmental_context_status: Literal["complete", "partial"] | None = None
    environmental_context_missing_inputs: list[str] | None = None
    natal_interpretation_status: Literal["complete", "partial"] | None = None
    natal_interpretation_missing_inputs: list[str] | None = None
    scene_scope: Object | None = None
    analysis_progress: AnalysisProgress | None = None
    implemented_layers: list[str] | None = None
    missing_inputs: list[str] | None = None
    unavailable_layers: list[str] | None = None
    not_requested_layers: list[str] | None = None
    supplemental_rulesets: list[str] | None = None
    layout_status: Literal["complete", "partial"] | None = None
    layout_missing_inputs: list[str] | None = None
    requested_analysis_status: Literal["complete", "partial"] | None = None


class FengshuiOutput(ProjectedOutput):
    calculation_reading: Object | None = None
    method_policy: Object | None = None
    method_details: Object | None = None
    analysis_type: str | None = None
    engine: str | None = None
    status: Literal["complete", "partial"] | None = None
    layers: Annotated[Layers | None, FULL_FACT] = None
    rulesets: list[Ruleset] | None = None
    source_catalog: dict[str, RuleSource] | None = None
    coverage: Coverage | None = None
    conflicts: list[Object] | None = None
    rule_trace: list[Object] | None = None
    summary: str | None = None
    run_metadata: RunMetadata | None = None
    layout_analysis: LayoutAnalysis | None = None

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
    workstation_layout_analysis: MeasuredLayoutOutput | None = None
    environmental_context: Object | None = None
    interior_analysis: Object | None = None
    material_analysis: Object | None = None
    workstation_analysis: Object | None = None
    natal_interpretation: NatalInterpretation | None = None
    alternatives_analysis: Object | None = None
    surface_analysis: SurfaceAnalysis | None = None
    analysis_progress: AnalysisProgress | None = None
    status: Literal["complete", "partial"] | None = None
    calculation_scope: str | None = None
    placement_findings: list[Object] | None = None
    adjustment_options: list[Object] | None = None
    environment_adjustments: list[Object] | None = None
    element_relationships: list[Object] | None = None
    missing_inputs: list[str] | None = None
    unsupported_queries: list[str] | None = None
    limitations: list[str] | None = None
    form_analysis: Object | None = None
    element_remedies: list[Object] | None = None
    annual_remedies: Object | None = None
    supplemental_rulesets: list[Ruleset] | None = None
    supplement_statuses: Object | None = None
    method_disagreements: list[Object] | None = None
