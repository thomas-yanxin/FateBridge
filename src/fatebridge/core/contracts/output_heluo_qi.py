"""Heluo body relations, seasonal qi and line placement."""

from typing import Annotated, Literal

from pydantic import Field, JsonValue, model_validator

from fatebridge.core.contracts.output_base import PartialOutput

# note (schema): Keep the Heluo order distinct from the shared five-element order.
HeluoBodyElement = Annotated[Literal["金", "木", "水", "火", "土"], Field()]


class HeluoBodyRelation(PartialOutput):
    body_id: str | None = None
    phase: Literal["xian", "hou"] | None = None
    gua: str | None = None
    kind: Literal["lower", "lower_nuclear", "upper_nuclear", "upper"] | None = None
    line_positions: list[Annotated[int, Field(ge=1, le=6)]] | None = None
    trigram: str | None = None
    element: HeluoBodyElement | None = None
    relation: (
        Literal[
            "same_element",
            "body_generates_nayin",
            "nayin_generates_body",
            "body_controls_nayin",
            "nayin_controls_body",
        ]
        | None
    ) = None
    yuanqi_kinds: list[Literal["tian", "di"]] | None = None


class HeluoGeneratingQi(PartialOutput):
    source_pdf_page: int | None = None
    direction: Literal["body_generates_nayin"] | None = None
    body_ids: list[str] | None = None
    relation_present: bool | None = None
    yuanqi_absence_required: Literal[True] | None = None
    condition_match: bool | None = None


class HeluoMutualGeneration(PartialOutput):
    source_pdf_page: int | None = None
    body_generates_nayin_ids: list[str] | None = None
    nayin_generates_body_ids: list[str] | None = None
    relation_present: bool | None = None
    scope: str | None = None


class HeluoBodyEvidence(PartialOutput):
    ruleset_id: str | None = None
    version: str | None = None
    source_url: str | None = None
    source_pdf_sha256: str | None = None
    source_pdf_pages: list[int] | None = None
    assessment_status: str | None = None
    year_ganzhi: str | None = None
    nayin: str | None = None
    nayin_element: HeluoBodyElement | None = None
    nayin_policy: str | None = None
    body_scope_policy: str | None = None
    bodies: list[HeluoBodyRelation] | None = None
    same_element_body_ids: list[str] | None = None
    yuanqi_absent: bool | None = None
    generating_qi: HeluoGeneratingQi | None = None
    mutual_generation: HeluoMutualGeneration | None = None
    present: None = None
    complete_assessment: Literal[False] | None = None
    review_status: str | None = None
    unresolved: list[str] | None = None


class HeluoQiBody(PartialOutput):
    body_id: str | None = None
    gua: str | None = None
    kind: Literal["lower", "lower_nuclear", "upper_nuclear", "upper"] | None = None
    line_positions: list[Annotated[int, Field(ge=1, le=6)]] | None = None
    trigram: str | None = None


class HeluoQiMatch(PartialOutput):
    trigrams: list[str] | None = None
    direct_body_ids: list[str] | None = None
    nuclear_body_ids: list[str] | None = None
    present: bool | None = None


class HeluoQiMatches(PartialOutput):
    yuan_tian: HeluoQiMatch | None = None
    yuan_di: HeluoQiMatch | None = None
    fan_yuan_tian: HeluoQiMatch | None = None
    fan_yuan_di: HeluoQiMatch | None = None
    huagong: HeluoQiMatch | None = None
    fanhua: HeluoQiMatch | None = None


class HeluoQiPhase(PartialOutput):
    phase: Literal["xian", "hou"] | None = None
    gua: str | None = None
    bodies: list[HeluoQiBody] | None = None
    matches: HeluoQiMatches | None = None


class HeluoQiTransition(PartialOutput):
    kind: (
        Literal[
            "yuan_tian", "yuan_di", "fan_yuan_tian", "fan_yuan_di", "huagong", "fanhua"
        ]
        | None
    ) = None
    xian_present: bool | None = None
    hou_present: bool | None = None
    change: Literal["retained", "lost", "gained", "absent", "not_evaluated"] | None = (
        None
    )


class HeluoYuanqiOppositionCondition(PartialOutput):
    kind: Literal["tian", "di"] | None = None
    yuan_trigram: str | None = None
    fan_trigram: str | None = None
    yuan_body_ids: list[str] | None = None
    fan_body_ids: list[str] | None = None
    yuan_absent: bool | None = None
    fan_present: bool | None = None
    condition_match: bool | None = None
    direct_only_condition_match: bool | None = None
    rescue_match: Literal[None] = None

    @model_validator(mode="after")
    def preserve_known_premises(self) -> "HeluoYuanqiOppositionCondition":
        if self.yuan_body_ids is not None and self.yuan_absent is not None:
            if self.yuan_absent != (not self.yuan_body_ids):
                raise ValueError("元气缺席须与实际卦体位置一致。")
        if self.fan_body_ids is not None and self.fan_present is not None:
            if self.fan_present != bool(self.fan_body_ids):
                raise ValueError("反候选命中须与实际卦体位置一致。")
        if all(
            v is not None
            for v in (self.yuan_absent, self.fan_present, self.condition_match)
        ):
            if self.condition_match != (self.yuan_absent and self.fan_present):
                raise ValueError("无正而有反式不能省略无正前提。")
        return self


class HeluoYuanqiOppositionPhase(PartialOutput):
    phase: Literal["xian", "hou"] | None = None
    gua: str | None = None
    conditions: list[HeluoYuanqiOppositionCondition] | None = None


class HeluoYuanqiOpposition(PartialOutput):
    ruleset_id: str | None = None
    version: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_pdf_sha256: str | None = None
    source_pdf_pages: list[int] | None = None
    review_status: str | None = None
    year_context_literal: str | None = None
    absence_literal: str | None = None
    rescue_literal: str | None = None
    collation_sha256: str | None = None
    content_sha256: str | None = None
    year_ganzhi: str | None = None
    body_scope_policy: str | None = None
    direct_only_policy: str | None = None
    phases: list[HeluoYuanqiOppositionPhase] | None = None
    full_rescue_assessment: Literal[False] | None = None
    unresolved: list[str] | None = None
    scope: str | None = None


class HeluoPhaseQi(PartialOutput):
    ruleset_id: str | None = None
    version: str | None = None
    source_url: str | None = None
    source_pdf_sha256: str | None = None
    source_pdf_pages: list[int] | None = None
    candidate_basis: str | None = None
    birth_instant_utc: str | None = None
    fanhua_rule_ids: list[str] | None = None
    phases: list[HeluoQiPhase] | None = None
    transitions: list[HeluoQiTransition] | None = None
    yuanqi_opposition: HeluoYuanqiOpposition | None = None
    complete_assessment: Literal[False] | None = None
    scope: str | None = None
    unresolved: list[str] | None = None


class HeluoYuantangPlacement(PartialOutput):
    rule_id: str | None = None
    hour_zhi: str | None = None
    hour_half: Literal["yang", "yin"] | None = None
    hour_index: int | None = Field(default=None, ge=1, le=6)
    matching_positions: list[int] | None = None
    other_positions: list[int] | None = None
    slot_positions: list[int] | None = None
    selected_pos: int | None = Field(default=None, ge=1, le=6)
    pure_direction: Literal["ascending", "descending"] | None = None
    source_pdf_pages: list[int] | None = None


class HeluoHalfYearCounterfactual(PartialOutput):
    yang_ling: bool | None = None
    xian_yuan: int | None = Field(default=None, ge=1, le=6)
    hou_name: str | None = None
    hou_yuan: int | None = Field(default=None, ge=1, le=6)
    hou_lines: list[int] | None = None


class HeluoHalfYearResolution(PartialOutput):
    value: bool | None = None
    basis: str | None = None
    birth_instant_utc: str | None = None
    candidate_values: list[bool] | None = None
    yuantang_depends_on_half_year: bool | None = None
    houtian_depends_on_half_year: bool | None = None
    counterfactuals: list[HeluoHalfYearCounterfactual] | None = None
    result_selection: (
        Literal["resolved_half_year", "invariant_under_both_halves"] | None
    ) = None


class HeluoYuantangDerivation(PartialOutput):
    ruleset_id: str | None = None
    version: str | None = None
    source_url: str | None = None
    source_pdf_sha256: str | None = None
    source_pdf_pages: list[int] | None = None
    review_status: str | None = None
    gender: Literal["男", "女"] | None = None
    half_year: HeluoHalfYearResolution | None = None
    placement: HeluoYuantangPlacement | None = None
    houtian_transform: dict[str, JsonValue] | None = None
    scope: str | None = None
