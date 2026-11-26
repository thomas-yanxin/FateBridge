"""Ziwei natal structure, flying SiHua matrix, and pattern output contracts."""

from typing import Annotated, Literal

from pydantic import Field

from fatebridge.core.contracts.output_base import (
    FULL_FACT,
    OpenJsonValue,
    PartialOutput,
)
from fatebridge.core.contracts.output_chinese_calendar import LunarDate
from fatebridge.core.contracts.output_ziwei_calendar import ZiweiCalendarBasis
from fatebridge.core.contracts.output_ziwei_palaces import (
    ZiweiChartMasters,
    ZiweiCycleRules,
    ZiweiPosition,
    ZiweiRuleset,
    ZiweiRuleTrace,
    ZiweiStar,
    ZiweiStructuralEvidence,
)


class ZiweiConditionSourceRevision(PartialOutput):
    """Retained placeholder symbol for output_chinese.py until Wave 3 cleanup."""


class ZiweiStructuralConditionRecord(PartialOutput):
    """Retained placeholder symbol for output_chinese.py until Wave 3 cleanup."""


class ZiweiXunVoid(PartialOutput):
    source_branches: list[str] | None = None
    displayed_star_branches: list[str] | None = None
    display_rule: str | None = None


class ZiweiVoidSystems(PartialOutput):
    xun: ZiweiXunVoid | None = None


class ZiweiPalace(PartialOutput):
    name: Annotated[str | None, FULL_FACT] = None
    ganzhi: Annotated[str | None, FULL_FACT] = None
    is_original_palace: bool | None = None
    daxian: str | None = None
    daxian_period: int | None = None
    stars: list[str] | None = None
    stars_detail: list[ZiweiStar] | None = None
    structural_evidence: ZiweiStructuralEvidence | None = None
    changsheng12: str | None = None
    boshi12: str | None = None


class ZiweiReadingPalace(PartialOutput):
    name: str | None = None
    ganzhi: str | None = None
    stars: list[ZiweiStar] | None = None
    major_stars: list[str] | None = None
    sanfang_sizheng_branches: list[str] | None = None
    changsheng12: str | None = None
    boshi12: str | None = None
    daxian: str | None = None


class ZiweiReadingView(PartialOutput):
    schema_version: str | None = None
    null_star_fields_omitted: list[str] | None = None
    sanfang_branch_order: list[str] | None = None
    palaces: list[ZiweiReadingPalace] | None = None
    star_occurrence_count: int | None = None
    distinct_star_count: int | None = None


class ZiweiCalendarRules(PartialOutput):
    late_zi: str | None = None
    day_divide: Literal["current", "forward"] | None = None
    year_divide: Literal["normal", "exact"] | None = None
    leap_month: str | None = None
    year_boundary: str | None = None
    effective_birth_month: int | None = None


class WuxingJu(PartialOutput):
    element: str | None = None
    label: str | None = None
    nayin: str | None = None
    number: int | None = None


class ZiweiPalaceSihuaOccurrence(PartialOutput):
    palace_name: str
    branch: str
    calculation_path: str


class ZiweiPalaceSihuaOrigin(PartialOutput):
    source_palace: str
    source_stem: str
    source_branch: str
    self_transformation: bool | None = None


class ZiweiPalaceSihuaGroup(PartialOutput):
    transformation: Literal["化禄", "化权", "化科", "化忌"]
    target_star: str
    target_occurrences: list[ZiweiPalaceSihuaOccurrence]
    origins: list[ZiweiPalaceSihuaOrigin] = Field(min_length=1)


class ZiweiPalaceSihuaRelations(PartialOutput):
    policy: Literal["selected_natal_table_reused_for_palace_stems"] | None = None
    sihua_rule: str | None = None
    groups: list[ZiweiPalaceSihuaGroup] | None = None


class ZiweiFlyingMatrixRow(PartialOutput):
    palace: str | None = None
    ganzhi: str | None = None
    is_original_palace: bool | None = None
    transforms: dict[str, str] | None = None
    outward_self: list[str] | None = None
    inward_self: list[str] | None = None
    ji_clash: str | None = None
    lu_to_ji: str | None = None
    ji_to_ji: str | None = None


class ZiweiFlyingSihua(PartialOutput):
    sihua_rule: str | None = None
    laiyin_gong: ZiweiPosition | None = None
    matrix: list[ZiweiFlyingMatrixRow] | None = None


class ZiweiPatternRecord(PartialOutput):
    id: str | None = None
    name: str | None = None
    category: str | None = None
    matched: bool | None = None
    conditions: dict[str, bool] | None = None
    borrowed_opposite_palace: str | None = None
    borrowed_opposite_branch: str | None = None
    borrowed_opposite_major_stars: list[str] | None = None


class ZiweiNamedPatternEvidence(PartialOutput):
    method_id: str | None = None
    total_checked: int | None = None
    matched_count: int | None = None
    matched: list[ZiweiPatternRecord] | None = None
    unmatched_ids: list[str] | None = None


class ZiweiBirth(PartialOutput):
    engine: Annotated[str | None, FULL_FACT] = None
    school: str | None = None
    astro_type: str | None = None
    calendar_basis: Annotated[ZiweiCalendarBasis | None, FULL_FACT] = None
    calendar_rules: Annotated[ZiweiCalendarRules | None, FULL_FACT] = None
    ruleset: Annotated[ZiweiRuleset | None, FULL_FACT] = None
    rule_trace: Annotated[list[ZiweiRuleTrace] | None, FULL_FACT] = None
    reading_view: ZiweiReadingView | None = None
    named_patterns: ZiweiNamedPatternEvidence | None = None
    flying_sihua: ZiweiFlyingSihua | None = None
    palace_sihua_relations: ZiweiPalaceSihuaRelations | None = None
    void_systems: ZiweiVoidSystems | None = None
    chart_masters: ZiweiChartMasters | None = None
    calendar_cycles: Annotated[ZiweiCycleRules | None, FULL_FACT] = None
    daxian_direction: str | None = None
    hour_branch: str | None = None
    zidou_branch: str | None = None
    laiyin_gong: ZiweiPosition | None = None
    lunar_date: LunarDate | None = None
    ming_gong: Annotated[ZiweiPosition | None, FULL_FACT] = None
    shen_gong: Annotated[ZiweiPosition | None, FULL_FACT] = None
    palaces: Annotated[list[ZiweiPalace] | None, FULL_FACT] = Field(
        default=None,
        min_length=12,
        max_length=12,
        json_schema_extra={"x-fatebridge-full-result-unique-by": "name"},
    )
    sihua: dict[str, str] | None = None
    time_algorithm: str | None = None
    wuxing_ju: Annotated[WuxingJu | None, FULL_FACT] = None
    year_stem: str | None = None
