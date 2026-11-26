"""Typed partial views keep literal readings, reconstructions and dates apart."""

from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.heluo.judgment import _jiehou_form as _form
from fatebridge.core.heluo.judgment import nominal_hou_day, term_assignment
from fatebridge.core.heluo.texts import _gua_tables, gua_lines, yao_name


def _bool(value: object) -> bool:
    if type(value) is not bool:
        raise ValueError("不能用0／1替代节候来源布尔事实。")
    return value


KnownTrue = Annotated[Literal[True], BeforeValidator(_bool)]
KnownFalse = Annotated[Literal[False], BeforeValidator(_bool)]
NominalModel = Literal["continuous_yao_from_yi_four", "six_days_per_gua_caption_first"]


class JiehouForm(PartialOutput):
    gua: str | None = None
    lines: list[int] | None = Field(default=None, min_length=6, max_length=6)
    position: int | None = Field(default=None, ge=1, le=6)
    yao: str | None = None

    @model_validator(mode="after")
    def coherent_form(self) -> "JiehouForm":

        if self.lines is not None and any(n not in (0, 1) for n in self.lines):
            raise ValueError("节候卦形须为自下而上的六个0／1。")
        lines: list[int] | None = self.lines
        if self.gua is not None:
            pair = _gua_tables()[0].get(self.gua)
            if pair is None:
                raise ValueError("节候卦名无对应卦形。")
            lines = gua_lines(pair["up"], pair["low"])
            if self.lines is not None and self.lines != lines:
                raise ValueError("节候卦名与六爻不一致。")
        if (
            lines is not None
            and self.position is not None
            and self.yao is not None
            and self.yao != yao_name(lines, self.position)
        ):
            raise ValueError("推演用爻名与卦形不一致；原印标签应另存。")
        return self


class JiehouTerm(JiehouForm):
    term: str | None = None
    source_pdf_page: int | None = None

    @model_validator(mode="after")
    def named_assignment(self) -> "JiehouTerm":
        if self.term is not None:

            actual = term_assignment(self.term)
            for key in ("gua", "position", "source_pdf_page"):
                value = getattr(self, key)
                if value is not None and value != actual[key]:
                    raise ValueError("节气名与所选底本节卦不一致。")
        return self


class JiehouLiteral(PartialOutput):
    term: str | None = None
    entry_in_group: int | None = Field(default=None, ge=1, le=3)
    short_name: str | None = None
    gua: str | None = None
    raw_yao: Literal["六四", "初六", "初九"] | None = None
    source_pdf_page: int | None = None
    printed_position: int | None = Field(default=None, ge=1, le=6)
    canonical_yao: str | None = None
    yao_polarity_agrees: bool | None = None

    @model_validator(mode="after")
    def retain_literal_difference(self) -> "JiehouLiteral":
        if self.raw_yao is not None and self.printed_position is not None:
            if self.printed_position != (4 if self.raw_yao == "六四" else 1):
                raise ValueError("原印爻名与所列原印位置不一致。")
        if self.gua is not None and self.printed_position is not None:

            canonical = _form(self.gua, self.printed_position)["yao"]
            if self.canonical_yao is not None and self.canonical_yao != canonical:
                raise ValueError("候卦形的爻名不一致。")
        else:
            canonical = self.canonical_yao
        if (
            self.raw_yao is not None
            and canonical is not None
            and self.yao_polarity_agrees is not None
            and self.yao_polarity_agrees != (self.raw_yao == canonical)
        ):
            raise ValueError("原印与卦形的差异不能被反转。")
        return self


class JiehouNominalDay(JiehouForm):
    model: NominalModel | None = None
    day_offset: int | None = Field(default=None, ge=0, lt=360)
    origin: Literal["printed_winter_solstice_yi_six_four; no_civil_instant"] | None = (
        None
    )
    basis: (
        Literal["sixty_gua_order_and_one_yao_per_nominal_day_reconstruction"] | None
    ) = None
    derived_only: KnownTrue | None = None
    physical_date_applied: KnownFalse | None = None
    extra_ke_applied: KnownFalse | None = None

    @model_validator(mode="after")
    def coherent_nominal_slot(self) -> "JiehouNominalDay":
        if self.day_offset is not None and self.model is not None:

            row = nominal_hou_day(self.day_offset, model=self.model)
            for key in ("gua", "position", "yao", "lines"):
                value = getattr(self, key)
                if value is not None and value != row[key]:
                    raise ValueError("名义日序与六日重建的卦爻不一致。")
        return self


class JiehouPrintedDay(PartialOutput):
    day_label: int | None = None
    gua: str | None = None
    position: int | None = Field(default=None, ge=1, le=6)


class JiehouCaptionComparison(PartialOutput):
    printed: JiehouPrintedDay | None = None
    derived: JiehouNominalDay | None = None
    agrees: bool | None = None

    @model_validator(mode="after")
    def faithful_comparison(self) -> "JiehouCaptionComparison":
        p, d = self.printed, self.derived
        if (
            p is not None
            and d is not None
            and self.agrees is not None
            and all(v is not None for v in (p.gua, p.position, d.gua, d.position))
            and self.agrees != ((p.gua, p.position) == (d.gua, d.position))
        ):
            raise ValueError("原例与六日重建的比较事实不一致。")
        return self


class JiehouTermStartComparison(PartialOutput):
    term: str | None = None
    printed_gua: str | None = None
    printed_yao: str | None = None
    printed_position: int | None = Field(default=None, ge=1, le=6)
    derived: JiehouNominalDay | None = None
    gua_agrees: bool | None = None
    position_agrees: bool | None = None
    interpretation_of_heading_unresolved: KnownTrue | None = None

    @model_validator(mode="after")
    def faithful_position_comparison(self) -> "JiehouTermStartComparison":
        d = self.derived
        if (
            self.printed_gua is not None
            and d is not None
            and d.gua is not None
            and self.gua_agrees is not None
            and self.gua_agrees != (self.printed_gua == d.gua)
        ):
            raise ValueError("表头与十五名义日模型的卦名比较不一致。")
        if (
            self.printed_position is not None
            and d is not None
            and d.position is not None
            and self.position_agrees is not None
            and self.position_agrees != (self.printed_position == d.position)
        ):
            raise ValueError("表头与十五名义日模型的位置比较不一致。")
        return self


class JiehouModelComparison(PartialOutput):
    model: NominalModel | None = None
    status: Literal["conditional_reconstruction; no_preferred_model"] | None = None
    caption_comparison: list[JiehouCaptionComparison] | None = Field(
        default=None, min_length=6, max_length=6
    )
    caption_difference_count: int | None = Field(default=None, ge=0, le=6)
    term_start_position_difference_count: int | None = Field(default=None, ge=0, le=24)
    term_start_gua_difference_count: int | None = Field(default=None, ge=0, le=24)
    selected_term_start_comparison: JiehouTermStartComparison | None = None

    @model_validator(mode="after")
    def count_actual_comparisons(self) -> "JiehouModelComparison":
        start = self.selected_term_start_comparison
        if (
            self.model is not None
            and start is not None
            and start.derived is not None
            and start.derived.model is not None
            and self.model != start.derived.model
        ):
            raise ValueError("交节点比较不能混用不同日序模型。")
        rows = self.caption_comparison
        if rows is not None:
            if self.model is not None and any(
                r.derived is not None
                and r.derived.model is not None
                and r.derived.model != self.model
                for r in rows
            ):
                raise ValueError("示例比较不能混用不同日序模型。")
            if (
                self.caption_difference_count is not None
                and all(r.agrees is not None for r in rows)
                and self.caption_difference_count
                != sum(r.agrees is False for r in rows)
            ):
                raise ValueError("原例差异计数与逐项比较不一致。")
        return self


class JiehouCounts(PartialOutput):
    term_rows: int | None = Field(default=None, ge=24, le=24)
    literal_hou_rows: int | None = Field(default=None, ge=72, le=72)
    distinct_hou_gua: int | None = Field(default=None, ge=60, le=60)
    nominal_gua_days: int | None = Field(default=None, ge=6, le=6)
    nominal_hou_days: int | None = Field(default=None, ge=5, le=5)
    nominal_term_line_days: int | None = Field(default=None, ge=15, le=15)
    nominal_quarter_days: int | None = Field(default=None, ge=90, le=90)
    nominal_year_days: int | None = Field(default=None, ge=360, le=360)


class HeluoJiehouEvidence(PartialOutput):
    ruleset_id: Literal["heluo_wenming_jiehou_v1"] | None = None
    version: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_pdf_pages: list[int] | None = None
    review_status: str | None = None
    selection_basis: (
        Literal["already_computed_term_label; modern_calendar_convention"] | None
    ) = None
    upstream_term_label: str | None = None
    anchor_utc: str | None = None
    anchor_precision: Literal["birth_instant", "date_midnight_approximation"] | None = (
        None
    )
    selected_term_gua: JiehouTerm | None = None
    literal_hou_group: list[JiehouLiteral] | None = Field(
        default=None, min_length=3, max_length=3
    )
    selected_hou: None = None
    huagong_assessment: None = None
    counts: JiehouCounts | None = None
    literal_yao_conflicts: list[JiehouLiteral] | None = None
    reconstruction_models: list[JiehouModelComparison] | None = Field(
        default=None, min_length=2, max_length=2
    )
    selected_reconstruction_model: None = None
    printed_total_yao_phrase: str | None = None
    historical_term_instants_established: KnownFalse | None = None
    hou_physical_date_mapping_complete: KnownFalse | None = None
    interpretation_constraints: list[str] | None = None

    @model_validator(mode="after")
    def same_term_context(self) -> "HeluoJiehouEvidence":
        if self.reconstruction_models is not None:
            names = [r.model for r in self.reconstruction_models]
            if all(name is not None for name in names) and names != [
                "continuous_yao_from_yi_four",
                "six_days_per_gua_caption_first",
            ]:
                raise ValueError("须保留两种具名重建，不能重复或删去一种。")
        if self.upstream_term_label is not None:

            actual = term_assignment(self.upstream_term_label)
            term = actual["term"]
            if self.reconstruction_models is not None and any(
                r.selected_term_start_comparison is not None
                and r.selected_term_start_comparison.term is not None
                and r.selected_term_start_comparison.term != term
                for r in self.reconstruction_models
            ):
                raise ValueError("模型交节点比较与本次节气不一致。")
            if self.selected_term_gua is not None:
                for key in ("gua", "position"):
                    value = getattr(self.selected_term_gua, key)
                    if value is not None and value != actual[key]:
                        raise ValueError("本次节气与已知节卦事实不一致。")
            if (
                self.selected_term_gua is not None
                and self.selected_term_gua.term is not None
            ):
                if term != self.selected_term_gua.term:
                    raise ValueError("本次节气标签与所选节卦不一致。")
            if self.literal_hou_group is not None and any(
                row.term is not None and row.term != term
                for row in self.literal_hou_group
            ):
                raise ValueError("原候卦组与本次节气不一致。")
        return self
