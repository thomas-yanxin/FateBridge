"""Heluo annual timing and source clock contracts."""

from typing import Annotated, Any, Literal

from pydantic import BeforeValidator, Field, JsonValue, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.heluo.timing import CYCLE


class HeluoTimingRow(PartialOutput):
    gua: str | None = None
    lines: list[int] | None = None
    pos: int | None = None
    changed_pos: int | None = None
    input_lines: list[int] | None = None
    ordinal_in_period: int | None = None
    age: int | None = None
    year_label: int | None = None
    ganzhi: str | None = None
    phase: str | None = None
    period_index: int | None = None
    period_pos: int | None = None
    period_start_yang: bool | None = None
    month_index: int | None = None
    parent_month_index: int | None = None
    rule_id: str | None = None
    block_index: int | None = None
    day_index: int | None = None


def _boolean_without_numeric_coercion(value: object) -> bool:
    if type(value) is not bool:
        raise ValueError("布尔事实不能用0/1或字符串替代。")
    return value


def _not_a_boolean_number(value: Any) -> Any:
    if type(value) is bool:
        raise ValueError("刻数不能用布尔替代。")
    return value


_KnownTrue = Annotated[
    Literal[True], BeforeValidator(_boolean_without_numeric_coercion)
]


_KnownFalse = Annotated[
    Literal[False], BeforeValidator(_boolean_without_numeric_coercion)
]


class HeluoTimingYearContext(PartialOutput):
    cycle_year: int | None = None
    birth_ganzhi: str | None = None
    expected_ganzhi: str | None = None
    matches: _KnownTrue | None = None
    basis: (
        Literal["selected_pillar_year_label; not_civil_birth_year_substitution"] | None
    ) = None

    @model_validator(mode="after")
    def consistent_year(self) -> "HeluoTimingYearContext":

        for gz in (self.birth_ganzhi, self.expected_ganzhi):
            if gz is not None and gz not in CYCLE:
                raise ValueError("岁运年上下文须用有效六十甲子。")
            if (
                gz is not None
                and self.cycle_year is not None
                and gz != CYCLE[(self.cycle_year - 4) % 60]
            ):
                raise ValueError("岁运年标签与年柱不一致。")
        if (
            self.birth_ganzhi is not None
            and self.expected_ganzhi is not None
            and self.birth_ganzhi != self.expected_ganzhi
        ):
            raise ValueError("岁运实际与预期年柱不一致。")
        return self


class HeluoClockRatio(PartialOutput):
    numerator: int | None = None
    denominator: int | None = Field(default=None, gt=0)


class HeluoClockBranch(PartialOutput):
    branch: (
        Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
        | None
    ) = None
    length_ke: Literal[8, 9] | None = None

    @model_validator(mode="after")
    def source_length(self) -> "HeluoClockBranch":
        if (
            self.branch is not None
            and self.length_ke is not None
            and self.length_ke != (9 if self.branch in "寅申巳亥" else 8)
        ):
            raise ValueError("卷一九刻支组不能换成等长或其他支组。")
        return self


class HeluoClockDailyExtra(PartialOutput):
    ke: Annotated[Literal[1], BeforeValidator(_not_a_boolean_number)] | None = None
    fen: Literal[7] | None = None
    fen_per_ke: None = None


class HeluoClockAnnualExtra(PartialOutput):
    nominal_days: Literal[360] | None = None
    printed_days: Literal[365] | None = None
    monthly_extra_shi: Literal[5] | None = None
    months: Literal[12] | None = None
    annual_extra_shi: Literal[60] | None = None


class HeluoClockProjection(PartialOutput):
    extra_ke_per_nominal_day: HeluoClockRatio | None = None
    fen_per_ke_required_for_numeric_closure: HeluoClockRatio | None = None
    derived_only: _KnownTrue | None = None
    source_fen_scale_verified: _KnownFalse | None = None

    @model_validator(mode="after")
    def only_a_conditional_projection(self) -> "HeluoClockProjection":
        for value, n, d in (
            (self.extra_ke_per_nominal_day, 25, 18),
            (self.fen_per_ke_required_for_numeric_closure, 18, 1),
        ):
            if (
                value is not None
                and value.numerator is not None
                and value.denominator is not None
                and (value.numerator, value.denominator) != (n, d)
            ):
                raise ValueError("等时条件推算与所列年余量不一致。")
        return self


class HeluoClockBranchShift(PartialOutput):
    year_blocks: Literal[60] | None = None
    extra_shi: Literal[60] | None = None
    extra_ke: Literal[500] | None = None
    total_source_days: HeluoClockRatio | None = None
    origin_basis: (
        Literal["full_cycles_total_invariant; no_physical_origin_selected"] | None
    ) = None
    branch_start_only: _KnownTrue | None = None
    derived_only: _KnownTrue | None = None
    source_fen_scale_selected: _KnownFalse | None = None
    daily_internal_distribution_resolved: _KnownFalse | None = None

    @model_validator(mode="after")
    def conditional_total(self) -> "HeluoClockBranchShift":
        value = self.total_source_days
        if (
            value is not None
            and value.numerator is not None
            and value.denominator is not None
            and (value.numerator, value.denominator) != (365, 1)
        ):
            raise ValueError("六十支移位的源刻总量与所列大数年不一致。")
        return self


class HeluoSourceClock(PartialOutput):
    ruleset_id: Literal["heluo_wenming_baike_clock_v1"] | None = None
    version: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_pdf_pages: list[int] | None = None
    review_status: str | None = None
    scope: str | None = None
    day_ke: Literal[100] | None = None
    base_ke: Literal[96] | None = None
    extra_ke: Literal[4] | None = None
    branch_lengths: list[HeluoClockBranch] | None = None
    extra_branches_in_printed_order: list[str] | None = None
    physical_origin_branch: None = None
    daily_extra_literal: HeluoClockDailyExtra | None = None
    annual_extra_literal: HeluoClockAnnualExtra | None = None
    branch_shift_projection: HeluoClockBranchShift | None = None
    equal_shi_projection: HeluoClockProjection | None = None
    physical_clock_applied: _KnownFalse | None = None
    calendar_mapping_complete: _KnownFalse | None = None
    constraints: list[str] | None = None

    @model_validator(mode="after")
    def source_counts_and_unresolved_origin(self) -> "HeluoSourceClock":
        if (
            self.extra_branches_in_printed_order is not None
            and self.extra_branches_in_printed_order != ["寅", "申", "巳", "亥"]
        ):
            raise ValueError("应保留原印寅申巳亥组及次序。")
        if self.branch_lengths is not None:
            if len(self.branch_lengths) != 12:
                raise ValueError("百刻循环须保留十二支。")
            if all(b.branch is not None for b in self.branch_lengths) and [
                b.branch for b in self.branch_lengths
            ] != list("子丑寅卯辰巳午未申酉戌亥"):
                raise ValueError("展示用循环支序不能混换。")
            if (
                all(b.length_ke is not None for b in self.branch_lengths)
                and sum(
                    b.length_ke for b in self.branch_lengths if b.length_ke is not None
                )
                != 100
            ):
                raise ValueError("十二支原刻总数须为一百。")
        return self


class HeluoTiming(PartialOutput):
    year_context: HeluoTimingYearContext | None = None
    source_clock: HeluoSourceClock | None = None
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_pdf_pages: list[int] | None = None
    scope: str | None = None
    calendar_policy: dict[str, str] | None = None
    annual_rows: list[HeluoTimingRow] | None = None
    selected_annual: HeluoTimingRow | None = None
    monthly_rows: list[HeluoTimingRow] | None = None
    selected_month: HeluoTimingRow | None = None
    daily_template: list[HeluoTimingRow] | None = None
    selected_day: HeluoTimingRow | None = None
    selected_texts: list[dict[str, JsonValue]] | None = None
