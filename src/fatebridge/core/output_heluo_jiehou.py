"""Typed partial views keep literal readings, reconstructions and dates apart."""

from typing import Annotated, Any, List, Literal, Optional

from pydantic import BeforeValidator, Field, model_validator

from fatebridge.core.output_base import PartialOutput


def _bool(value: Any) -> Any:
    if type(value) is not bool:
        raise ValueError("不能用0／1替代节候来源布尔事实。")
    return value


KnownTrue = Annotated[Literal[True], BeforeValidator(_bool)]
KnownFalse = Annotated[Literal[False], BeforeValidator(_bool)]
NominalModel = Literal["continuous_yao_from_yi_four", "six_days_per_gua_caption_first"]


class JiehouForm(PartialOutput):
    gua: Optional[str] = None
    lines: Optional[List[int]] = Field(default=None, min_length=6, max_length=6)
    position: Optional[int] = Field(default=None, ge=1, le=6)
    yao: Optional[str] = None

    @model_validator(mode="after")
    def coherent_form(self) -> "JiehouForm":
        from fatebridge.core.heluo import yao_name
        from fatebridge.core.heluo_hexagrams import _gua_tables, gua_lines

        if self.lines is not None and any(n not in (0, 1) for n in self.lines):
            raise ValueError("节候卦形须为自下而上的六个0／1。")
        lines: Optional[List[int]] = self.lines
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
    term: Optional[str] = None
    source_pdf_page: Optional[int] = None

    @model_validator(mode="after")
    def named_assignment(self) -> "JiehouTerm":
        if self.term is not None:
            from fatebridge.core.heluo_jiehou import term_assignment

            actual = term_assignment(self.term)
            for key in ("gua", "position", "source_pdf_page"):
                value = getattr(self, key)
                if value is not None and value != actual[key]:
                    raise ValueError("节气名与所选底本节卦不一致。")
        return self


class JiehouLiteral(PartialOutput):
    term: Optional[str] = None
    entry_in_group: Optional[int] = Field(default=None, ge=1, le=3)
    short_name: Optional[str] = None
    gua: Optional[str] = None
    raw_yao: Optional[Literal["六四", "初六", "初九"]] = None
    source_pdf_page: Optional[int] = None
    printed_position: Optional[int] = Field(default=None, ge=1, le=6)
    canonical_yao: Optional[str] = None
    yao_polarity_agrees: Optional[bool] = None

    @model_validator(mode="after")
    def retain_literal_difference(self) -> "JiehouLiteral":
        if self.raw_yao is not None and self.printed_position is not None:
            if self.printed_position != (4 if self.raw_yao == "六四" else 1):
                raise ValueError("原印爻名与所列原印位置不一致。")
        if self.gua is not None and self.printed_position is not None:
            from fatebridge.core.heluo_jiehou import _form

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
    model: Optional[NominalModel] = None
    day_offset: Optional[int] = Field(default=None, ge=0, lt=360)
    origin: Optional[
        Literal["printed_winter_solstice_yi_six_four; no_civil_instant"]
    ] = None
    basis: Optional[
        Literal["sixty_gua_order_and_one_yao_per_nominal_day_reconstruction"]
    ] = None
    derived_only: Optional[KnownTrue] = None
    physical_date_applied: Optional[KnownFalse] = None
    extra_ke_applied: Optional[KnownFalse] = None

    @model_validator(mode="after")
    def coherent_nominal_slot(self) -> "JiehouNominalDay":
        if self.day_offset is not None and self.model is not None:
            from fatebridge.core.heluo_jiehou import nominal_hou_day

            row = nominal_hou_day(self.day_offset, model=self.model)
            for key in ("gua", "position", "yao", "lines"):
                value = getattr(self, key)
                if value is not None and value != row[key]:
                    raise ValueError("名义日序与六日重建的卦爻不一致。")
        return self


class JiehouPrintedDay(PartialOutput):
    day_label: Optional[int] = None
    gua: Optional[str] = None
    position: Optional[int] = Field(default=None, ge=1, le=6)


class JiehouCaptionComparison(PartialOutput):
    printed: Optional[JiehouPrintedDay] = None
    derived: Optional[JiehouNominalDay] = None
    agrees: Optional[bool] = None

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
    term: Optional[str] = None
    printed_gua: Optional[str] = None
    printed_yao: Optional[str] = None
    printed_position: Optional[int] = Field(default=None, ge=1, le=6)
    derived: Optional[JiehouNominalDay] = None
    gua_agrees: Optional[bool] = None
    position_agrees: Optional[bool] = None
    interpretation_of_heading_unresolved: Optional[KnownTrue] = None

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
    model: Optional[NominalModel] = None
    status: Optional[Literal["conditional_reconstruction; no_preferred_model"]] = None
    caption_comparison: Optional[List[JiehouCaptionComparison]] = Field(
        default=None, min_length=6, max_length=6
    )
    caption_difference_count: Optional[int] = Field(default=None, ge=0, le=6)
    term_start_position_difference_count: Optional[int] = Field(
        default=None, ge=0, le=24
    )
    term_start_gua_difference_count: Optional[int] = Field(default=None, ge=0, le=24)
    selected_term_start_comparison: Optional[JiehouTermStartComparison] = None

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
    term_rows: Optional[int] = Field(default=None, ge=24, le=24)
    literal_hou_rows: Optional[int] = Field(default=None, ge=72, le=72)
    distinct_hou_gua: Optional[int] = Field(default=None, ge=60, le=60)
    nominal_gua_days: Optional[int] = Field(default=None, ge=6, le=6)
    nominal_hou_days: Optional[int] = Field(default=None, ge=5, le=5)
    nominal_term_line_days: Optional[int] = Field(default=None, ge=15, le=15)
    nominal_quarter_days: Optional[int] = Field(default=None, ge=90, le=90)
    nominal_year_days: Optional[int] = Field(default=None, ge=360, le=360)


class HeluoJiehouEvidence(PartialOutput):
    ruleset_id: Optional[Literal["heluo_wenming_jiehou_v1"]] = None
    version: Optional[str] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    source_pdf_sha256: Optional[str] = None
    source_pdf_pages: Optional[List[int]] = None
    review_status: Optional[str] = None
    loaded_sha256: Optional[str] = None
    selection_basis: Optional[
        Literal["already_computed_term_label; modern_calendar_convention"]
    ] = None
    upstream_term_label: Optional[str] = None
    anchor_utc: Optional[str] = None
    anchor_precision: Optional[
        Literal["birth_instant", "date_midnight_approximation"]
    ] = None
    selected_term_gua: Optional[JiehouTerm] = None
    literal_hou_group: Optional[List[JiehouLiteral]] = Field(
        default=None, min_length=3, max_length=3
    )
    selected_hou: None = None
    huagong_assessment: None = None
    counts: Optional[JiehouCounts] = None
    literal_yao_conflicts: Optional[List[JiehouLiteral]] = None
    reconstruction_models: Optional[List[JiehouModelComparison]] = Field(
        default=None, min_length=2, max_length=2
    )
    selected_reconstruction_model: None = None
    printed_total_yao_phrase: Optional[str] = None
    historical_term_instants_established: Optional[KnownFalse] = None
    hou_physical_date_mapping_complete: Optional[KnownFalse] = None
    interpretation_constraints: Optional[List[str]] = None

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
            from fatebridge.core.heluo_jiehou import term_assignment

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
