"""Projection-compatible facts for attributed Yi texts and Liu Yao evidence."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_liuyao_conditions import (
    DivinationSource,
    LiuyaoConditions,
)
from fatebridge.core.contracts.output_liuyao_fanfu import FanfuEvidence


class ClassicalLine(PartialOutput):
    position: int | None = None
    label: str | None = None
    text: str | None = None


class ClassicalHexagram(PartialOutput):
    corpus_id: str | None = None
    source_kind: str | None = None
    edition_status: str | None = None
    number: int | None = None
    name: str | None = None
    code: str | None = None
    guaci: str | None = None
    daxiang: str | None = None
    yaoci: list[ClassicalLine] | None = None
    special: ClassicalLine | None = None
    source_url: str | None = None
    source_revision: int | None = None
    source_wikitext_sha256: str | None = None


class ClassicalTextEvidence(PartialOutput):
    selection_policy: str | None = None
    base_guaci: str | None = None
    changed_guaci: str | None = None
    moving_yaoci: list[ClassicalLine] | None = None
    all_moving_special: ClassicalLine | None = None
    base_source_url: str | None = None
    changed_source_url: str | None = None
    scope: str | None = None


class BranchRelations(PartialOutput):
    is_xunkong: bool | None = None
    is_month_clash: bool | None = None
    is_day_clash: bool | None = None
    is_month_combination: bool | None = None
    is_day_combination: bool | None = None
    is_month_branch: bool | None = None
    is_day_branch: bool | None = None
    month_element_relation: str | None = None
    day_element_relation: str | None = None


class LineTransformation(BranchRelations):
    branch: str | None = None
    back_relation: str | None = None
    advance: bool | None = None
    retreat: bool | None = None


class LineEvidence(BranchRelations):
    position: int | None = None
    branch: str | None = None
    transformation: LineTransformation | None = None


class HiddenSpirit(PartialOutput):
    position: int | None = None
    branch: str | None = None
    element: str | None = None
    liuqin: str | None = None
    flying_branch: str | None = None
    flying_liuqin: str | None = None
    calendar_relations: BranchRelations | None = None
    flying_to_hidden_relation: str | None = None


class MonthModelBoundary(PartialOutput):
    name: str | None = None
    month_branch: str | None = None
    datetime_utc: str | None = None
    julian_day_tt: float | None = None
    ephemeris_model: str | None = None
    role: str | None = None
    native_retflags: list[int] | None = None


class ActiveMonthModelDifference(PartialOutput):
    name: str | None = None
    selected: MonthModelBoundary | None = None
    native: MonthModelBoundary | None = None
    selected_has_passed: bool | None = None
    native_has_passed: bool | None = None
    selected_minus_native_seconds_tt: float | None = None


class MonthModelComparison(PartialOutput):
    status: str | None = None
    calculation_month_branch: str | None = None
    native_month_branch: str | None = None
    month_changed: bool | None = None
    coverage_complete: bool | None = None
    primary_context_consistent: bool | None = None
    comparison_utc: str | None = None
    compared_month_boundaries: int | None = None
    missing_native_probes: list[str] | None = None
    selected_models: list[str] | None = None
    native_models: list[str] | None = None
    active_boundary_differences: list[ActiveMonthModelDifference] | None = None
    selected_previous_boundary: MonthModelBoundary | None = None
    selected_next_boundary: MonthModelBoundary | None = None
    native_previous_boundary: MonthModelBoundary | None = None
    native_next_boundary: MonthModelBoundary | None = None
    scope: str | None = None


class DivinationCalendarConventions(PartialOutput):
    month_model_comparison: MonthModelComparison | None = None
    cast_at: str | None = None
    year_boundary: str | None = None
    month_boundary: str | None = None
    day_boundary: str | None = None
    clock: str | None = None
    month_branch: str | None = None
    day_ganzhi: str | None = None
    xunkong: list[str] | None = None


class DivinationTrace(PartialOutput):
    rule_id: str | None = None
    fact_path: str | None = None
    inputs: dict[str, OpenJsonValue] | None = None
    sources: list[str] | None = None


class LiuyaoEvidence(PartialOutput):
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_kind: str | None = None
    conformance_scope: str | None = None
    calendar_conventions: DivinationCalendarConventions | None = None
    lines: list[LineEvidence] | None = None
    conditional_analysis: LiuyaoConditions | None = None
    fanfu: FanfuEvidence | None = None
    hidden_spirits: list[HiddenSpirit] | None = None
    hidden_policy: str | None = None
    rule_trace: list[DivinationTrace] | None = None
    sources: list[str] | None = None
    source_revisions: dict[str, DivinationSource] | None = None
    textual_corrections: list[str] | None = None
    pattern_detection_scope: str | None = None
    pending_judgments: list[str] | None = None
