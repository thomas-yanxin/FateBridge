"""Projection-compatible facts for attributed Yi texts and Liu Yao evidence."""

from typing import Any, Dict, List, Optional

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_liuyao_conditions import DivinationSource, LiuyaoConditions
from fatebridge.core.output_liuyao_fanfu import FanfuEvidence


class ClassicalLine(PartialOutput):
    position: Optional[int] = None
    label: Optional[str] = None
    text: Optional[str] = None


class ClassicalHexagram(PartialOutput):
    corpus_id: Optional[str] = None
    source_kind: Optional[str] = None
    edition_status: Optional[str] = None
    number: Optional[int] = None
    name: Optional[str] = None
    code: Optional[str] = None
    guaci: Optional[str] = None
    daxiang: Optional[str] = None
    yaoci: Optional[List[ClassicalLine]] = None
    special: Optional[ClassicalLine] = None
    source_url: Optional[str] = None
    source_revision: Optional[int] = None
    source_wikitext_sha256: Optional[str] = None


class ClassicalTextEvidence(PartialOutput):
    selection_policy: Optional[str] = None
    base_guaci: Optional[str] = None
    changed_guaci: Optional[str] = None
    moving_yaoci: Optional[List[ClassicalLine]] = None
    all_moving_special: Optional[ClassicalLine] = None
    base_source_url: Optional[str] = None
    changed_source_url: Optional[str] = None
    scope: Optional[str] = None


class BranchRelations(PartialOutput):
    is_xunkong: Optional[bool] = None
    is_month_clash: Optional[bool] = None
    is_day_clash: Optional[bool] = None
    is_month_combination: Optional[bool] = None
    is_day_combination: Optional[bool] = None
    is_month_branch: Optional[bool] = None
    is_day_branch: Optional[bool] = None
    month_element_relation: Optional[str] = None
    day_element_relation: Optional[str] = None


class LineTransformation(BranchRelations):
    branch: Optional[str] = None
    back_relation: Optional[str] = None
    advance: Optional[bool] = None
    retreat: Optional[bool] = None


class LineEvidence(BranchRelations):
    position: Optional[int] = None
    branch: Optional[str] = None
    transformation: Optional[LineTransformation] = None


class HiddenSpirit(PartialOutput):
    position: Optional[int] = None
    branch: Optional[str] = None
    element: Optional[str] = None
    liuqin: Optional[str] = None
    flying_branch: Optional[str] = None
    flying_liuqin: Optional[str] = None
    calendar_relations: Optional[BranchRelations] = None
    flying_to_hidden_relation: Optional[str] = None


class MonthModelBoundary(PartialOutput):
    name: Optional[str] = None
    month_branch: Optional[str] = None
    datetime_utc: Optional[str] = None
    julian_day_tt: Optional[float] = None
    ephemeris_model: Optional[str] = None
    role: Optional[str] = None
    native_retflags: Optional[List[int]] = None


class ActiveMonthModelDifference(PartialOutput):
    name: Optional[str] = None
    selected: Optional[MonthModelBoundary] = None
    native: Optional[MonthModelBoundary] = None
    selected_has_passed: Optional[bool] = None
    native_has_passed: Optional[bool] = None
    selected_minus_native_seconds_tt: Optional[float] = None


class MonthModelComparison(PartialOutput):
    status: Optional[str] = None
    calculation_month_branch: Optional[str] = None
    native_month_branch: Optional[str] = None
    month_changed: Optional[bool] = None
    coverage_complete: Optional[bool] = None
    primary_context_consistent: Optional[bool] = None
    comparison_utc: Optional[str] = None
    compared_month_boundaries: Optional[int] = None
    missing_native_probes: Optional[List[str]] = None
    selected_models: Optional[List[str]] = None
    native_models: Optional[List[str]] = None
    active_boundary_differences: Optional[List[ActiveMonthModelDifference]] = None
    selected_previous_boundary: Optional[MonthModelBoundary] = None
    selected_next_boundary: Optional[MonthModelBoundary] = None
    native_previous_boundary: Optional[MonthModelBoundary] = None
    native_next_boundary: Optional[MonthModelBoundary] = None
    scope: Optional[str] = None


class DivinationCalendarConventions(PartialOutput):
    month_model_comparison: Optional[MonthModelComparison] = None
    cast_at: Optional[str] = None
    year_boundary: Optional[str] = None
    month_boundary: Optional[str] = None
    day_boundary: Optional[str] = None
    clock: Optional[str] = None
    month_branch: Optional[str] = None
    day_ganzhi: Optional[str] = None
    xunkong: Optional[List[str]] = None


class DivinationTrace(PartialOutput):
    rule_id: Optional[str] = None
    fact_path: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    sources: Optional[List[str]] = None


class PredictionValidation(PartialOutput):
    status: Optional[str] = None
    real_world_sample_count: Optional[int] = None
    scope: Optional[str] = None


class LiuyaoEvidence(PartialOutput):
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_kind: Optional[str] = None
    conformance_scope: Optional[str] = None
    calendar_conventions: Optional[DivinationCalendarConventions] = None
    lines: Optional[List[LineEvidence]] = None
    conditional_analysis: Optional[LiuyaoConditions] = None
    fanfu: Optional[FanfuEvidence] = None
    hidden_spirits: Optional[List[HiddenSpirit]] = None
    hidden_policy: Optional[str] = None
    rule_trace: Optional[List[DivinationTrace]] = None
    sources: Optional[List[str]] = None
    source_revisions: Optional[Dict[str, DivinationSource]] = None
    textual_corrections: Optional[List[str]] = None
    pattern_detection_scope: Optional[str] = None
    pending_judgments: Optional[List[str]] = None
    prediction_validation: Optional[PredictionValidation] = None
