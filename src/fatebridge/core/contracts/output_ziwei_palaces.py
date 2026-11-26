"""Ziwei palaces, stars, cycles, and ruleset output contracts."""

from typing import Annotated, Literal

from pydantic import Field

from fatebridge.core.contracts.output_base import (
    FULL_FACT,
    OpenJsonValue,
    PartialOutput,
)
from fatebridge.core.contracts.output_chinese_calendar import BranchName


class ZiweiPosition(BranchName):
    ganzhi: str | None = None


class ZiweiStar(PartialOutput):
    name: str | None = None
    label: str | None = None
    brightness: str | None = Field(
        default=None, description="庙旺表档位；null 表示所选表未给该星该支定档。"
    )
    brightness_source: str | None = None
    mutagen: str | None = None


class ZiweiStructuralEvidence(PartialOutput):
    major_stars: list[str] | None = None
    is_empty_main_palace: bool | None = None
    sanfang_sizheng_branches: list[str] | None = None
    opposite_stars_relocated: bool | None = None


class ZiweiBrightnessTableReceipt(PartialOutput):
    id: str | None = None
    source_kind: str | None = None
    source_url: str | None = None
    version: str | None = None
    branch_order: list[str] | None = None
    grade_scale: list[str] | None = None
    aliases: dict[str, str] | None = None
    blank_meaning: str | None = None


class ZiweiRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    school: str | None = None
    astro_type: str | None = None
    day_divide: Literal["current", "forward"] | None = None
    year_divide: Literal["normal", "exact"] | None = None
    horoscope_divide: Literal["normal", "exact"] | None = None
    age_divide: Literal["normal", "birthday"] | None = None
    leap_month_rule: (
        Literal["split_at_day_15", "all_current_month", "all_next_month"] | None
    ) = None
    target_leap_month_rule: str | None = None
    sihua_source: str | None = None
    sihua_rule: str | None = None
    brightness_rule: str | None = None
    brightness_table: ZiweiBrightnessTableReceipt | None = None
    overrides: list[str] | None = None


class ZiweiRuleTrace(PartialOutput):
    rule_id: str | None = None
    source: str | None = None
    inputs: dict[str, OpenJsonValue] | None = None
    outputs: dict[str, OpenJsonValue] | None = None


class ZiweiYearCyclePosition(PartialOutput):
    name: str
    branch: str


class ZiweiYearCycle(PartialOutput):
    system_id: Annotated[str | None, FULL_FACT] = None
    start_branch: Annotated[str | None, FULL_FACT] = None
    positions: Annotated[list[ZiweiYearCyclePosition] | None, FULL_FACT] = Field(
        default=None,
        min_length=12,
        max_length=12,
        json_schema_extra={"x-fatebridge-full-result-unique-by": "branch"},
    )


class ZiweiYearBranchCycles(PartialOutput):
    anchor_basis: Annotated[
        Literal["natal_lunar_year_branch", "target_lunar_year_branch"] | None, FULL_FACT
    ] = None
    year_branch: Annotated[str | None, FULL_FACT] = None
    direction: Annotated[Literal["forward"] | None, FULL_FACT] = None
    source: Annotated[str | None, FULL_FACT] = None
    suiqian: Annotated[ZiweiYearCycle | None, FULL_FACT] = None
    jiangqian: Annotated[ZiweiYearCycle | None, FULL_FACT] = None


class ZiweiCycleRules(PartialOutput):
    status: str | None = None
    changsheng_start: str | None = None
    changsheng_direction: str | None = None
    changsheng_rule: str | None = None
    boshi_start: str | None = None
    boshi_direction: str | None = None
    boshi_rule: str | None = None
    missing_gender_resolution: str | None = None
    gender_invariant_positions: dict[str, dict[str, str]] | None = None
    year_branch_cycles: Annotated[ZiweiYearBranchCycles | None, FULL_FACT] = None


class ZiweiChartMaster(PartialOutput):
    star: str | None = None
    selection_basis: str | None = None
    basis_branch: str | None = None
    natal_palace_name: str | None = None
    natal_branch: str | None = None


class ZiweiChartMasters(PartialOutput):
    life: ZiweiChartMaster | None = None
    body: ZiweiChartMaster | None = None


class ZiweiFlowingStar(PartialOutput):
    star: str | None = None
    scope: str | None = None
    branch: str | None = None
    scope_palace_name: str | None = None
    natal_palace_name: str | None = None
    rule_id: str | None = None
    stem: str | None = None
    basis_branch: str | None = None
    system_id: str | None = None
    year_branch: str | None = None
    source: str | None = None


class ZiweiAnnualThreeSha(PartialOutput):
    rule_id: str | None = None
    scope: str | None = None
    year_branch: str | None = None
    names_as_written: list[str] | None = None
    branches: list[str] | None = None
    source: str | None = None
