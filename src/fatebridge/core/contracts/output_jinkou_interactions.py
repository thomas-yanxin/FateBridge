"""Complete arrays and projection-compatible roots for ordered clauses."""

from itertools import combinations
from typing import Literal

from pydantic import Field, StrictBool, field_validator, model_validator

from fatebridge.core.contracts.output_base import PartialOutput

Position = Literal["人元", "贵神", "将神", "地分"]
Phase = Literal["木", "火", "土", "金", "水"]
RuleId = Literal[
    "outer_battle",
    "inner_battle",
    "heju",
    "top_down_generation",
    "bottom_up_generation",
    "top_down_control",
    "bottom_up_control",
    "lower_pair_controls_god",
    "upper_pair_controls_general",
    "zheng_bi",
    "jin_bi",
    "yuan_bi",
    "ci_bi",
    "he_bi",
]
RULE_IDS = frozenset(
    (
        "outer_battle",
        "inner_battle",
        "heju",
        "top_down_generation",
        "bottom_up_generation",
        "top_down_control",
        "bottom_up_control",
        "lower_pair_controls_god",
        "upper_pair_controls_general",
        "zheng_bi",
        "jin_bi",
        "yuan_bi",
        "ci_bi",
        "he_bi",
    )
)


class JinkouPositionPair(PartialOutput):
    upper_position: Position
    lower_position: Position
    upper_element: Phase
    lower_element: Phase
    adjacent: StrictBool
    relation: Literal["比和", "上生下", "下生上", "上克下", "下克上"]


class JinkouInteractionCondition(PartialOutput):
    source_position: Position
    target_position: Position
    source_element: Phase
    target_element: Phase
    relation: Literal["生", "克", "比和"]
    matched: StrictBool


class JinkouInteractionRule(PartialOutput):
    id: RuleId
    name: str
    quantifier: Literal["all", "any"]
    matched: StrictBool
    condition_checks: list[JinkouInteractionCondition] | None = None
    original_pdf_pages: list[int] | None = None

    @model_validator(mode="after")
    def matches_its_conditions(self) -> "JinkouInteractionRule":
        if self.condition_checks is not None:
            values = [c.matched for c in self.condition_checks]
            expected = any(values) if self.quantifier == "any" else all(values)
            if self.matched != expected:
                raise ValueError("四位结构判断与所列条件不一致")
        return self


class JinkouPositionInteractions(PartialOutput):
    ruleset_id: Literal["jinkou_jingben_position_interactions_v1"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    original_pdf_pages: list[int] | None = None
    position_order: list[Position] | None = None
    pairs: list[JinkouPositionPair] | None = Field(
        default=None, min_length=6, max_length=6
    )
    source_rule_count: Literal[14] | None = None
    rule_evaluations: list[JinkouInteractionRule] | None = Field(
        default=None, min_length=14, max_length=14
    )
    matched_rule_ids: list[RuleId] | None = None
    has_any_control: StrictBool | None = None
    complete_classical_conformance: StrictBool | None = None
    scope: str | None = None

    @field_validator("position_order")
    @classmethod
    def canonical_position_order(
        cls, value: list[Position] | None
    ) -> list[Position] | None:
        if value is not None and value != ["人元", "贵神", "将神", "地分"]:
            raise ValueError("四位上下次序不得颠倒")
        return value

    @field_validator("pairs")
    @classmethod
    def all_six_ordered_pairs(
        cls, value: list[JinkouPositionPair] | None
    ) -> list[JinkouPositionPair] | None:
        if value is not None:
            expected = set(combinations(("人元", "贵神", "将神", "地分"), 2))
            if {(p.upper_position, p.lower_position) for p in value} != expected:
                raise ValueError("四位关系须列全六对不同位置")
            order = ["人元", "贵神", "将神", "地分"]
            if any(
                p.adjacent
                != (order.index(p.lower_position) - order.index(p.upper_position) == 1)
                for p in value
            ):
                raise ValueError("相邻与隔位标识须符合四位次序")
        return value

    @field_validator("rule_evaluations")
    @classmethod
    def all_fourteen_clauses(
        cls, value: list[JinkouInteractionRule] | None
    ) -> list[JinkouInteractionRule] | None:
        if value is not None and {r.id for r in value} != RULE_IDS:
            raise ValueError("四位关系须保留十四条不同来源规则")
        return value

    @field_validator("complete_classical_conformance", mode="before")
    @classmethod
    def no_full_book_claim(cls, value: object) -> bool | None:
        return value if value is None or type(value) is bool else False

    @model_validator(mode="after")
    def summary_matches_facts(self) -> "JinkouPositionInteractions":
        if self.matched_rule_ids is not None:
            if len(self.matched_rule_ids) != len(set(self.matched_rule_ids)):
                raise ValueError("命中规则标识不得重复")
            if self.rule_evaluations is not None and set(self.matched_rule_ids) != {
                r.id for r in self.rule_evaluations if r.matched
            }:
                raise ValueError("命中清单与十四条逐项事实不一致")
        if self.pairs is not None and self.has_any_control is not None:
            if self.has_any_control != any(
                p.relation in {"上克下", "下克上"} for p in self.pairs
            ):
                raise ValueError("有克标识与六对生克事实不一致")
        return self
