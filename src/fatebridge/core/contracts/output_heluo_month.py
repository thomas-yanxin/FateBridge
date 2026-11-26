"""Heluo Na Jia and calendar-month source contracts."""

from typing import Annotated, Literal

from pydantic import Field, JsonValue

from fatebridge.core.contracts.output_base import PartialOutput


class HeluoNajiaSource(PartialOutput):
    basis: Literal["hexagram_entry", "pure_trigram_rule"] | None = None
    source_hexagram: str | None = None
    source_pdf_page: int | None = Field(default=None, ge=1)
    source_assignment_index: int | None = Field(default=None, ge=1, le=6)


class HeluoNajiaLine(PartialOutput):
    pos: int | None = Field(default=None, ge=1, le=6)
    trigram: str | None = None
    direct: str | None = None
    borrowed: list[str] | None = None
    source: HeluoNajiaSource | None = None


class HeluoNajiaMatch(PartialOutput):
    pos: int | None = Field(default=None, ge=1, le=6)
    kind: Literal["direct", "borrowed"] | None = None


class HeluoNajiaAssessment(PartialOutput):
    phase: Literal["xian", "hou"] | None = None
    gua: str | None = None
    year_ganzhi: str | None = None
    lines: list[HeluoNajiaLine] | None = None
    matches: list[HeluoNajiaMatch] | None = None
    present: bool | None = None

    source_scope: str | None = None
    source_issues: list[dict[str, JsonValue]] | None = None


class HeluoNumberFact(PartialOutput):
    value: int | None = Field(default=None, gt=0)
    reference: int | None = None
    difference: int | None = None
    comparison: Literal["正数", "不足", "有余"] | None = None
    extreme_band: Literal["至弱", "太过"] | None = None
    extreme_band_status: str | None = None
    weak_range: list[int] | None = None
    high_lower_bound: int | None = None
    high_upper_bound: int | None = None
    source_pdf_pages: list[int] | None = None
    scope: str | None = None


class HeluoNumericalCondition(PartialOutput):
    rule_id: str | None = None
    label: str | None = None
    source_pdf_page: int | None = None
    condition: str | None = None
    matched: bool | None = None


class HeluoSeasonWindow(PartialOutput):
    rule_id: str | None = None
    label: str | None = None
    axis: Literal["tian", "di"] | None = None
    source_pdf_page: int | None = None
    start_term: str | None = None
    end_term: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    start_provider: str | None = None
    end_provider: str | None = None
    start_source: dict[str, JsonValue] | None = None
    end_source: dict[str, JsonValue] | None = None
    active: bool | None = None
    numeric_condition: str | None = None
    numeric_band_match: bool | None = None
    numeric_band_status: str | None = None
    scope: str | None = None


class HeluoSeasonalNumbers(PartialOutput):
    context_timezone: str | None = None
    context_local_year: int | None = None
    ruleset_id: str | None = None
    version: str | None = None
    source_url: str | None = None
    source_pdf_sha256: str | None = None
    source_pdf_pages: list[int] | None = None
    assessment_status: str | None = None
    numbers: dict[str, HeluoNumberFact] | None = None
    numerical_conditions: list[HeluoNumericalCondition] | None = None
    matched_pattern_ids: list[str] | None = None
    seasonal_status: str | None = None
    birth_instant_utc: str | None = None
    seasonal_windows: list[HeluoSeasonWindow] | None = None
    overlap_policy: str | None = None
    boundary_policy: str | None = None
    complete_assessment: Literal[False] | None = None
    unresolved: list[str] | None = None


class HeluoNatalNajiaClause(PartialOutput):
    rule_id: str | None = None
    source_pdf_page: int | None = Field(default=None, ge=1)
    literal: str | None = None
    month_numbers: list[Annotated[int, Field(ge=1, le=12)]] | None = None
    month_label_match: bool | None = None
    najia: HeluoNajiaAssessment | None = None
    qualifier_status: (
        Literal["current_phase_facts_available", "not_evaluated_missing_najia"] | None
    ) = None
    connector_status: Literal["source_ji_scope_unresolved"] | None = None
    match: None = None
    scope: str | None = None


class HeluoAdditionalMonthWindow(PartialOutput):
    rule_id: str | None = None
    source_pdf_page: int | None = Field(default=None, ge=1)
    literal: str | None = None
    kind: Literal["continuous_range", "discrete_months", "season_set"] | None = None
    meaning: (
        Literal[
            "timely", "untimely", "named_favorable_months", "named_months_with_najia"
        ]
        | None
    ) = None
    month_numbers: list[Annotated[int, Field(ge=1, le=12)]] | None = None
    uncertain_month_numbers: list[Annotated[int, Field(ge=1, le=12)]] | None = None
    month_label_match: bool | None = None
    qualifiers: list[str] | None = None
    natal_najia_clause_id: str | None = None
    qualifier_status: Literal["none", "not_evaluated"] | None = None
    first_month_number: int | None = Field(default=None, ge=1, le=12)
    last_month_number: int | None = Field(default=None, ge=1, le=12)
    first_month_inclusive: bool | None = None
    last_month_inclusive: bool | None = None
    match: bool | None = None
    status: str | None = None


class HeluoMonthSourceReading(PartialOutput):
    section: Literal["hexagram_intro", "volume_one_table"] | None = None
    month_number: int | None = Field(default=None, ge=1, le=12)
    source_pdf_page: int | None = Field(default=None, ge=1)
    literal: str | None = Field(
        default=None,
        description="卷首月号读标，卦名沿用系统规范字形并线性化；不是原页逐字转写。卦条未收逐字引文时为null。",
    )
    month_label_match: bool | None = None
    status: Literal["explicit_month", "month_not_explicit"] | None = None


class HeluoMonthAssignmentConflict(PartialOutput):
    gua: str | None = None
    intro_month: int | None = Field(default=None, ge=1, le=12)
    intro_pdf_page: int | None = Field(default=None, ge=1)
    table_month: int | None = Field(default=None, ge=1, le=12)
    table_pdf_page: int | None = Field(default=None, ge=1)


class HeluoAssignedMonth(PartialOutput):
    phase: Literal["xian", "hou"] | None = None
    gua: str | None = None
    assigned_month_number: int | None = Field(default=None, ge=1, le=12)
    assigned_month_branch: str | None = None
    assigned_month_match: bool | None = None
    selected_month_source: Literal["hexagram_intro", "volume_one_table"] | None = None
    source_readings: list[HeluoMonthSourceReading] | None = None
    source_months_agree: bool | None = None
    source_consensus_match: bool | None = None
    source_status: str | None = None
    source_pdf_page: int | None = Field(default=None, ge=1)
    additional_windows: list[HeluoAdditionalMonthWindow] | None = None
    natal_najia_clause: HeluoNatalNajiaClause | None = None
    opposed_month_conditions: bool | None = None
    conflict_rule_ids: list[str] | None = None


class HeluoMonthAffinity(PartialOutput):
    assignment_method: Literal["intro_preferred_v1", "volume_one_table_v1"] | None = (
        None
    )
    volume_one_explicit_months: int | None = Field(default=None, ge=0, le=64)
    volume_one_collation_sha256: str | None = None
    intro_fact_sha256: str | None = None
    volume_one_fact_sha256: str | None = None
    source_assignment_conflicts: list[HeluoMonthAssignmentConflict] | None = None
    source_consensus_match: bool | None = Field(
        default=None,
        description="逐阶段两处来源对本月匹配结论的三值或；不是比较两个完整方法的deTime是否相同。缺号或阶段分歧保留null。",
    )
    ruleset_id: str | None = None
    version: str | None = None
    collation_version: str | None = None
    source_url: str | None = None
    source_pdf_sha256: str | None = None
    collation_sha256: str | None = None
    review_status: str | None = None
    reviewed_hexagram_introductions: int | None = Field(default=None, ge=0, le=64)
    explicit_assigned_months: int | None = Field(default=None, ge=0, le=64)
    additional_month_clauses: int | None = Field(default=None, ge=0)
    registered_natal_najia_clauses: int | None = Field(default=None, ge=0, le=64)
    birth_month_branch: str | None = None
    birth_month_number: int | None = Field(default=None, ge=1, le=12)
    month_number_policy: str | None = None
    phases: list[HeluoAssignedMonth] | None = None
    complete_assessment: Literal[False] | None = None
    scope: str | None = None
    unresolved: list[str] | None = None
