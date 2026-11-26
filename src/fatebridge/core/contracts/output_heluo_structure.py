"""Heluo source structure and line condition contracts."""

from typing import Annotated, Literal

from pydantic import Field, JsonValue, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_heluo_month import (
    HeluoMonthAffinity,
    HeluoNajiaAssessment,
    HeluoSeasonalNumbers,
)
from fatebridge.core.contracts.output_heluo_qi import HeluoBodyEvidence, HeluoPhaseQi
from fatebridge.core.heluo.heluo_structure import OPERATORS, _name


class HeluoRulerMinisterSeat(PartialOutput):
    source_pdf_page: int | None = None
    positions: list[int] | None = None
    match: bool | None = None
    scope: str | None = None


class HeluoZhongzong(PartialOutput):
    source_pdf_page: int | None = None
    yang_count: int | None = Field(default=None, ge=0, le=6)
    yin_count: int | None = Field(default=None, ge=0, le=6)
    # note (schema): Preserve the published order when the opposite literal is cached.
    minority_polarity: Annotated[Literal["yang", "yin"], Field()] | None = None
    minority_pos: int | None = Field(default=None, ge=1, le=6)
    match: bool | None = None


class HeluoSourceYouyuan(PartialOutput):
    rule_id: Literal["wenming_yin_yuantang_yang_corresponding_v1"] | None = None
    source_pdf_page: int | None = None
    selected_pos: int | None = Field(default=None, ge=1, le=6)
    selected_yang: bool | None = None
    corresponding_pos: int | None = Field(default=None, ge=1, le=6)
    corresponding_yang: bool | None = None
    polarity_opposed: bool | None = None
    required_selected_yang: Literal[False] | None = None
    required_corresponding_yang: Literal[True] | None = None
    clause_match: bool | None = None
    scope: (
        Literal[
            "named_primary_yin_line_yang_corresponding_clause_only; not_full_ten_condition_verdict"
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def coherent_correspondence_and_clause(self) -> "HeluoSourceYouyuan":
        if self.selected_pos is not None and self.corresponding_pos is not None:
            expected = (
                self.selected_pos + 3
                if self.selected_pos <= 3
                else self.selected_pos - 3
            )
            if self.corresponding_pos != expected:
                raise ValueError("有援原句须使用同卦实际对应爻位。")
        if self.selected_yang is not None and self.corresponding_yang is not None:
            if self.polarity_opposed is not None and self.polarity_opposed != (
                self.selected_yang != self.corresponding_yang
            ):
                raise ValueError("相应阴阳事实不一致。")
            if self.clause_match is not None and self.clause_match != (
                not self.selected_yang and self.corresponding_yang
            ):
                raise ValueError("有援所选主本原句不能用通用相应或反向相应替代。")
        return self


class HeluoLineConditionRow(PartialOutput):
    phase: Literal["xian", "hou"] | None = None
    gua: str | None = None
    lines: list[Annotated[int, Field(ge=0, le=1)]] | None = None
    pos: int | None = Field(default=None, ge=1, le=6)
    yang: bool | None = None
    position_polarity_match: bool | None = None
    position_preference_order: int | None = Field(default=None, ge=1, le=4)
    ruler_minister_seat: HeluoRulerMinisterSeat | None = None
    zhongzong: HeluoZhongzong | None = None
    source_youyuan: HeluoSourceYouyuan | None = None

    @model_validator(mode="after")
    def coherent_selected_phase_support(self) -> "HeluoLineConditionRow":
        aid = self.source_youyuan
        if aid is None:
            return self
        if (
            self.pos is not None
            and aid.selected_pos is not None
            and self.pos != aid.selected_pos
        ):
            raise ValueError("有援原句的元堂须属于本阶段。")
        if (
            self.yang is not None
            and aid.selected_yang is not None
            and self.yang != aid.selected_yang
        ):
            raise ValueError("有援原句的元堂阴阳须属于本阶段。")
        if self.lines is not None:
            if len(self.lines) != 6:
                raise ValueError("有援原句需要同卦六爻事实。")
            for pos, yang in [
                (aid.selected_pos, aid.selected_yang),
                (aid.corresponding_pos, aid.corresponding_yang),
            ]:
                if (
                    pos is not None
                    and yang is not None
                    and bool(self.lines[pos - 1]) != yang
                ):
                    raise ValueError("有援原句的爻阴阳与本阶段六爻不一致。")
        return self


class HeluoSourceDangwei(PartialOutput):
    source_pdf_page: int | None = None
    literal_condition: str | None = None
    status: Literal["yinyue_definition_pending"] | None = None
    month_polarity: None = None
    match: None = None
    line_index_parity_substituted: Literal[False] | None = None
    solstice_half_year_substituted: Literal[False] | None = None


class HeluoLineConditions(PartialOutput):
    ruleset_id: str | None = None
    version: str | None = None
    source_url: str | None = None
    source_pdf_sha256: str | None = None
    collation_sha256: str | None = None
    source_pdf_pages: list[int] | None = None
    review_status: str | None = None
    literal_clauses: dict[str, dict[str, JsonValue]] | None = None
    position_preference_policy: str | None = None
    phases: list[HeluoLineConditionRow] | None = None
    source_dangwei: HeluoSourceDangwei | None = None
    complete_assessment: Literal[False] | None = None
    ten_condition_score: None = None
    scope: str | None = None
    constraints: list[str] | None = None


class HeluoStructureRecord(PartialOutput):
    kind: (
        Literal[
            "lower",
            "upper",
            "lower_reversed",
            "upper_reversed",
            "upper_nuclear",
            "lower_nuclear",
            "third_to_top",
            "reverse_then_third_to_top",
        ]
        | None
    ) = None
    arity: Literal[3, 6] | None = None
    original_positions: list[Annotated[int, Field(ge=1, le=6)]] | None = None
    lines: list[Annotated[int, Field(ge=0, le=1)]] | None = None
    name: str | None = None

    @model_validator(mode="after")
    def coherent_operator(self) -> "HeluoStructureRecord":

        arities = [
            len(value)
            for value in (self.original_positions, self.lines)
            if value is not None
        ]
        if self.arity is not None:
            arities.append(self.arity)
        if self.kind is not None:
            expected = dict(OPERATORS)[self.kind]
            arities.append(len(expected))
            if self.original_positions is not None and self.original_positions != list(
                expected
            ):
                raise ValueError("卦体结构须保留实际取爻次序。")
        if any(arity not in (3, 6) for arity in arities) or len(set(arities)) > 1:
            raise ValueError("卦体结构的种类、爻数、原位与爻形不能混用三爻或六爻。")
        if self.lines is not None and self.name is not None:
            if _name(self.lines) != self.name:
                raise ValueError("卦体结构名称与爻形不一致。")
        return self


class HeluoWholeReversal(PartialOutput):
    original_positions: list[Annotated[int, Field(ge=1, le=6)]] | None = None
    lines: list[Annotated[int, Field(ge=0, le=1)]] | None = None
    name: str | None = None

    @model_validator(mode="after")
    def coherent_reversal(self) -> "HeluoWholeReversal":

        if self.original_positions is not None and self.original_positions != [
            6,
            5,
            4,
            3,
            2,
            1,
        ]:
            raise ValueError("全卦倒序须保留六爻次序。")
        if self.lines is not None:
            if len(self.lines) != 6 or (
                self.name is not None and _name(self.lines) != self.name
            ):
                raise ValueError("全卦倒序名称与六爻不一致。")
        return self


class HeluoStructurePhase(PartialOutput):
    phase: Literal["xian", "hou"] | None = None
    gua: str | None = None
    input_lines: list[Annotated[int, Field(ge=0, le=1)]] | None = None
    records: list[HeluoStructureRecord] | None = None
    record_count: Literal[8] | None = None
    whole_reversal: HeluoWholeReversal | None = None
    literal_case_match: bool | None = None
    literal_names_reproduced: bool | None = None
    source_application: (
        Literal[
            "named_jian_paragraph",
            "permutation_derivation; not_this_hexagrams_literal_source_example",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def coherent_phase(self) -> "HeluoStructurePhase":

        if self.gua is not None and self.literal_case_match is not None:
            if self.literal_case_match != (self.gua == "風山漸"):
                raise ValueError("不能把其他卦标为所核渐卦原例。")
        if (
            self.literal_case_match is False
            and self.literal_names_reproduced is not None
        ):
            raise ValueError("其他卦的推演不冒充新增原例核对。")
        if self.literal_case_match is not None and self.source_application is not None:
            expected_basis = (
                "named_jian_paragraph"
                if self.literal_case_match
                else "permutation_derivation; not_this_hexagrams_literal_source_example"
            )
            if self.source_application != expected_basis:
                raise ValueError("原例与算子推演的来源标签不一致。")
        if self.records is not None:
            if len(self.records) != 8:
                raise ValueError("所列结构应保留八条记录，包括重复名称。")
            for row, (kind, _) in zip(self.records, OPERATORS):
                if row.kind is not None and row.kind != kind:
                    raise ValueError("结构记录次序不一致。")
            if (
                self.literal_case_match is True
                and self.literal_names_reproduced is not None
                and all(row.name is not None for row in self.records)
                and self.whole_reversal is not None
                and self.whole_reversal.name is not None
            ):
                reproduced = [row.name for row in self.records] == [
                    "艮",
                    "巽",
                    "震",
                    "兌",
                    "離",
                    "坎",
                    "天地否",
                    "地天泰",
                ] and self.whole_reversal.name == "雷澤歸妹"
                if self.literal_names_reproduced != reproduced:
                    raise ValueError("原例复现标记与实际结构名称不一致。")
        if self.input_lines is not None:
            if len(self.input_lines) != 6 or (
                self.gua is not None and _name(self.input_lines) != self.gua
            ):
                raise ValueError("同阶段卦名与输入六爻不一致。")
            for row in self.records or []:
                if row.original_positions is not None and row.lines is not None:
                    if row.lines != [
                        self.input_lines[p - 1] for p in row.original_positions
                    ]:
                        raise ValueError("结构记录不能借用另一阶段爻形或翻转阴阳。")
            if (
                self.whole_reversal is not None
                and self.whole_reversal.lines is not None
            ):
                if self.whole_reversal.lines != self.input_lines[::-1]:
                    raise ValueError("全卦倒序不能变爻。")
        return self


class HeluoFiveMingTerminology(PartialOutput):
    symbol_readings: dict[str, str] | None = None
    source_pdf_pages: list[int] | None = None
    selected_pillar: None = None
    nayin_substituted: Literal[False] | None = None
    scope: (
        Literal["literal_symbol_lists_only; no_global_person_element_selection"] | None
    ) = None


class HeluoBodyStructure(PartialOutput):
    ruleset_id: Literal["heluo_wenming_jian_structure_v1"] | None = None
    version: str | None = None
    source_url: str | None = None
    source_pdf_sha256: str | None = None
    source_pdf_pages: list[int] | None = None
    calculation_source_pdf_pages: list[int] | None = None
    collation_sha256: str | None = None
    review_status: str | None = None
    wording_variants: list[dict[str, str]] | None = None
    phases: list[HeluoStructurePhase] | None = None
    five_ming_terminology: HeluoFiveMingTerminology | None = None
    scope: str | None = None
    complete_futi_assessment: Literal[False] | None = None
    complete_assessment: Literal[False] | None = None
    constraints: list[str] | None = None


class HeluoSelectedYuantang(PartialOutput):
    pos: Literal[1, 2, 3, 4, 5, 6] | None = None
    yang: bool | None = None
    position_polarity_match: bool | None = None
    youYing: bool | None = None
    youYing_policy: str | None = None
    heLi: bool | None = None
    heLi_policy: str | None = None


class HeluoJudge(PartialOutput):
    assessment_status: str | None = None
    xie_policy: str | None = None
    deSheng_policy: str | None = None
    deTime_policy: str | None = None
    deTi_policy: str | None = None
    najia: list[HeluoNajiaAssessment] | None = None
    deSheng: bool | None = None
    deTime: bool | None = None
    month_affinity: HeluoMonthAffinity | None = None
    xie: bool | None = None
    yuan: dict[str, JsonValue] | None = None
    fanYuan: dict[str, JsonValue] | None = None
    fanYuan_policy: str | None = None
    huagong: dict[str, JsonValue] | None = None
    fanhua: dict[str, JsonValue] | None = None
    qi_phases: HeluoPhaseQi | None = None
    deTi: HeluoBodyEvidence | None = None
    erShu: dict[str, JsonValue] | None = None
    seasonal_numbers: HeluoSeasonalNumbers | None = None
    yuanTang: HeluoSelectedYuantang | None = None
    line_conditions: HeluoLineConditions | None = None
    body_structure: HeluoBodyStructure | None = None
