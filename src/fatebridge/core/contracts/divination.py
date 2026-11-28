"""Projection-compatible output contracts for Yi, Liuyao, Meihua time cast, and Tongshefa."""

from __future__ import annotations

from pydantic import JsonValue

from fatebridge.core.contracts.base import OpenJsonValue, PartialOutput, ProjectedOutput
from fatebridge.core.contracts.common import (
    AnalysisContext,
    CalendarContext,
    FourPillars,
)
from fatebridge.core.contracts.meihua import (
    ClassicalLine,
    GuaLookupResult,
    Hexagram,
    Meihua,
    MeihuaSeed,
)
from fatebridge.core.receipt_models import Object, RunMetadata


class FanfuRegion(PartialOutput):
    region: str | None = None
    base_trigram_code: str | None = None
    changed_trigram_code: str | None = None
    trigram_changed: bool | None = None
    base_branches: list[str] | None = None
    changed_chart_branches: list[str] | None = None
    nazhi_relation: str | None = None
    moving_positions: list[int] | None = None
    static_comparison_positions: list[int] | None = None
    source_url: str | None = None
    scope: str | None = None


class FanfuLine(PartialOutput):
    position: int | None = None
    original_branch: str | None = None
    changed_branch: str | None = None
    nazhi_relation: str | None = None


class FanfuBodyExample(PartialOutput):
    base_code: str | None = None
    changed_code: str | None = None
    kind: str | None = None
    pdf_page: int | None = None
    source_url: str | None = None
    basis: str | None = None


class FanfuEvidence(PartialOutput):
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_url: str | None = None
    regions: list[FanfuRegion] | None = None
    moving_line_relations: list[FanfuLine] | None = None
    explicit_body_example: FanfuBodyExample | None = None
    body_classification: str | None = None
    efficacy: str | None = None
    textual_issues: list[dict[str, OpenJsonValue]] | None = None
    scope: str | None = None


class ClassicalTextEvidence(PartialOutput):
    selection_policy: str | None = None
    base_guaci: str | None = None
    changed_guaci: str | None = None
    moving_yaoci: list[ClassicalLine] | None = None
    all_moving_special: ClassicalLine | None = None
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
    month_strength: str | None = None
    day_growth_stage: str | None = None
    shensha: list[str] | None = None
    is_month_broken: bool | None = None
    is_void_clashed: bool | None = None
    is_dark_moving: bool | None = None
    is_day_broken: bool | None = None
    day_clash_status: str | None = None
    transformation: LineTransformation | None = None


class HiddenSpirit(PartialOutput):
    position: int | None = None
    branch: str | None = None
    element: str | None = None
    liuqin: str | None = None
    flying_branch: str | None = None
    flying_liuqin: str | None = None
    present_in_changed: bool | None = None
    changed_positions: list[int] | None = None
    calendar_relations: BranchRelations | None = None
    flying_to_hidden_relation: str | None = None


class ShenshaEntry(PartialOutput):
    branches: list[str] | None = None
    positions: list[int] | None = None


class MovingFocusGuidance(PartialOutput):
    moving_count: int | None = None
    moving_positions: list[int] | None = None
    static_positions: list[int] | None = None
    mode: str | None = None
    primary_focus_positions: list[int] | None = None
    rule: str | None = None


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


class LiuyaoEvidence(PartialOutput):
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    month_model_comparison: MonthModelComparison | None = None
    lines: list[LineEvidence] | None = None
    fanfu: FanfuEvidence | None = None
    hidden_spirits: list[HiddenSpirit] | None = None
    hidden_policy: str | None = None
    shensha: dict[str, ShenshaEntry] | None = None
    three_harmony: list[dict[str, OpenJsonValue]] | None = None
    moving_focus_guidance: MovingFocusGuidance | None = None
    focus: dict[str, OpenJsonValue] | None = None
    timing_candidates: dict[str, OpenJsonValue] | None = None


class SixyaoLine(PartialOutput):
    changed_branch: str | None = None
    changed_liuqin: str | None = None
    is_fuyin_line: bool | None = None
    branch: str | None = None
    change: bool | None = None
    element: str | None = None
    god: str | None = None
    liuqin: str | None = None
    liushen: str | None = None
    name: str | None = None
    position: int | None = None
    shi_ying: str | None = None
    value: int | None = None


class SixyaoTimeRuleset(PartialOutput):
    ruleset_id: str | None = None
    year_boundary: str | None = None
    source_url: str | None = None
    seed: MeihuaSeed | None = None


class SixyaoCoinToss(PartialOutput):
    position: int | None = None
    name: str | None = None
    sum: int | None = None
    yao: str | None = None
    symbol: str | None = None
    moving: bool | None = None


class SixyaoCast(PartialOutput):
    method: str | None = None
    source: str | None = None
    seed: int | None = None
    coin_source: str | None = None
    tosses: list[SixyaoCoinToss] | None = None
    time_ruleset: SixyaoTimeRuleset | None = None


class GuaShenInfo(PartialOutput):
    branch: str | None = None
    element: str | None = None
    liuqin: str | None = None
    shi_line: int | None = None
    shi_yin_yang: str | None = None
    present_positions: list[int] | None = None


class SixyaoHexagramInfo(PartialOutput):
    changed_palace: str | None = None
    changed_palace_element: str | None = None
    changed_position: str | None = None
    current_palace: str | None = None
    current_palace_element: str | None = None
    current_position: str | None = None
    shi_line: int | None = None
    ying_line: int | None = None
    gua_shen: GuaShenInfo | None = None


class SixyaoDescription(PartialOutput):
    code: str | None = None
    name: str | None = None
    卦辞: str | None = None
    象曰: str | None = None
    raw: Hexagram | None = None


class SixyaoFlags(PartialOutput):
    liuchong_base: bool | None = None
    liuchong_changed: bool | None = None
    liuhe_base: bool | None = None
    liuhe_changed: bool | None = None


class Tongshefa(PartialOutput):
    baseLeft: Hexagram | None = None
    baseRight: Hexagram | None = None
    mutualLeft: Hexagram | None = None
    mutualRight: Hexagram | None = None
    oppositeLeft: Hexagram | None = None
    oppositeRight: Hexagram | None = None
    relation: str | None = None
    main_relation: str | None = None
    lower_relation: str | None = None
    mutual_relations: dict[str, str] | None = None
    opposite_relations: dict[str, str] | None = None
    left_elem: str | None = None
    right_elem: str | None = None
    lower_left_elem: str | None = None
    lower_right_elem: str | None = None


class GuaLookupOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_type: str | None = None
    lookup_mode: str | None = None
    queries: list[str] | None = None
    results: dict[str, GuaLookupResult] | None = None
    summary: str | None = None


class MeihuaTimeCastOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    calendar_context: CalendarContext | None = None
    four_pillars: FourPillars | None = None
    interpretation: Object | None = None
    meihua: Meihua | None = None
    summary: Object | list[JsonValue] | str | None = None


class CombineFourGuaOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    summary: Object | list[JsonValue] | str | None = None
    tongshefa: Tongshefa | None = None


class LiuyaoOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    calendar_context: CalendarContext | None = None
    cast: SixyaoCast | None = None
    changed_code: str | None = None
    changed_hexagram: Hexagram | None = None
    current_code: str | None = None
    current_hexagram: Hexagram | None = None
    descriptions: dict[str, SixyaoDescription] | None = None
    hexagram_info: SixyaoHexagramInfo | None = None
    lines: list[SixyaoLine] | None = None
    liuyao_evidence: LiuyaoEvidence | None = None
    moving_lines: list[int] | None = None
    nongli: Object | str | None = None
    pattern_flags: SixyaoFlags | None = None
    patterns: Object | list[JsonValue] | None = None
    question: JsonValue | str | None = None
    summary: Object | list[JsonValue] | str | None = None
