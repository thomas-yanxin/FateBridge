"""Daily-stem facts, distinct from intrinsic god and branch-based motions."""

from typing import Any, List, Literal, Optional

from pydantic import Field, StrictBool, field_validator, model_validator

from fatebridge.utils.data import STEM_ELEMENTS

from .metaphysics.common import (
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    branch_element_text,
    sexagenary_index_for,
    stem_element_text,
    xun_head_for_ganzhi,
)
from .metaphysics.jinkou_stems import ganzhi_pair_facts, wuzidun_stem
from .output_base import PartialOutput

Stem = Literal["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
Phase = Literal["木", "火", "土", "金", "水"]
Branch = Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
Relation = Literal["神干生将干", "将干生神干", "神干克将干", "将干克神干", "两干比和"]
RuleId = Literal[
    "god_generates_general",
    "general_generates_god",
    "god_controls_general",
    "general_controls_god",
]


def _valid_ganzhi(value: str) -> None:
    try:
        sexagenary_index_for(value)
    except KeyError as exc:
        raise ValueError("神将干支须属于六十甲子") from exc


class JinkouDunStemNode(PartialOutput):
    position: Optional[Literal["贵神", "将神"]] = None
    name: Optional[str] = None
    branch: Optional[Branch] = None
    branch_element: Optional[Phase] = None
    dun_stem: Optional[Stem] = None
    dun_ganzhi: Optional[str] = None
    dun_element: Optional[Phase] = None
    branch_xun_kong: Optional[StrictBool] = None
    branch_si_da_kong: Optional[StrictBool] = None

    @model_validator(mode="after")
    def compound_matches_its_parts(self) -> "JinkouDunStemNode":
        if self.dun_ganzhi is not None:
            _valid_ganzhi(self.dun_ganzhi)
        if (
            self.branch is not None
            and self.branch_element is not None
            and branch_element_text(self.branch) != self.branch_element
        ):
            raise ValueError("神将本支五行不能换成遁干五行")
        if (
            self.dun_stem is not None
            and self.dun_element is not None
            and STEM_ELEMENTS[self.dun_stem][0].value != self.dun_element
        ):
            raise ValueError("遁干五行须来自所列当日遁干")
        if (
            self.dun_ganzhi is not None
            and self.dun_stem is not None
            and self.branch is not None
        ):
            if self.dun_ganzhi != self.dun_stem + self.branch:
                raise ValueError("神将遁干支与所列干支不一致")
        return self


class JinkouGanzhiPairFacts(PartialOutput):
    left_ganzhi: Optional[str] = None
    right_ganzhi: Optional[str] = None
    stem_harmony_matched: Optional[StrictBool] = None
    canonical_stem_pair: Optional[List[Stem]] = Field(
        default=None, min_length=2, max_length=2
    )
    candidate_element: Optional[Phase] = None
    branch_harmony_matched: Optional[StrictBool] = None
    both_harmonies_matched: Optional[StrictBool] = None
    left_ganzhi_xun_head: Optional[str] = None
    right_ganzhi_xun_head: Optional[str] = None
    same_ganzhi_xun: Optional[StrictBool] = None
    transformation_confirmed: None = None
    du_he: None = None

    @model_validator(mode="after")
    def summaries_agree(self) -> "JinkouGanzhiPairFacts":
        for value, head in (
            (self.left_ganzhi, self.left_ganzhi_xun_head),
            (self.right_ganzhi, self.right_ganzhi_xun_head),
        ):
            if value is not None:
                _valid_ganzhi(value)
                if head is not None and xun_head_for_ganzhi(value) != head:
                    raise ValueError("所列自身旬首须来自该遁干支")
        if self.left_ganzhi is not None and self.right_ganzhi is not None:
            expected = ganzhi_pair_facts(self.left_ganzhi, self.right_ganzhi)
            for name in self.model_fields_set:
                if name in expected and getattr(self, name) != expected[name]:
                    raise ValueError("配对事实须符合所列两组遁干支")
        if self.stem_harmony_matched is True:
            for name in ("canonical_stem_pair", "candidate_element"):
                if name in self.model_fields_set and getattr(self, name) is None:
                    raise ValueError("已配对的天干须保留所列候选事实")
        if self.stem_harmony_matched is False and (
            self.candidate_element is not None or self.canonical_stem_pair is not None
        ):
            raise ValueError("未成天干配对不能给出该配对候选五行")
        if (
            self.stem_harmony_matched is not None
            and self.branch_harmony_matched is not None
            and self.both_harmonies_matched is not None
        ):
            if self.both_harmonies_matched != (
                self.stem_harmony_matched and self.branch_harmony_matched
            ):
                raise ValueError("干支俱合与两个分别条件不一致")
        if (
            self.left_ganzhi_xun_head is not None
            and self.right_ganzhi_xun_head is not None
            and self.same_ganzhi_xun is not None
        ):
            if self.same_ganzhi_xun != (
                self.left_ganzhi_xun_head == self.right_ganzhi_xun_head
            ):
                raise ValueError("两遁干支自身同旬与所列旬首不一致")
        return self


class JinkouStemRule(PartialOutput):
    id: RuleId
    relation: Literal["神干生将干", "将干生神干", "神干克将干", "将干克神干"]
    source_position: Literal["贵神", "将神"]
    target_position: Literal["贵神", "将神"]
    phase_relation: Literal["生", "克"]
    matched: StrictBool
    original_pdf_pages: List[int]

    @model_validator(mode="after")
    def clause_metadata_matches_identifier(self) -> "JinkouStemRule":
        expected = {
            "god_generates_general": ("神干生将干", "贵神", "将神", "生"),
            "general_generates_god": ("将干生神干", "将神", "贵神", "生"),
            "god_controls_general": ("神干克将干", "贵神", "将神", "克"),
            "general_controls_god": ("将干克神干", "将神", "贵神", "克"),
        }[self.id]
        if (
            self.relation,
            self.source_position,
            self.target_position,
            self.phase_relation,
        ) != expected:
            raise ValueError("干元类条目标识与其明示方向不一致")
        return self


class JinkouStemRelations(PartialOutput):
    ruleset_id: Optional[Literal["jinkou_jingben_dun_stem_relations_v1"]] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    original_pdf_pages: Optional[List[int]] = None
    day_stem: Optional[Stem] = None
    dun_cycle_policy: Optional[Literal["single_cycle_zi_to_hai"]] = None
    god: Optional[JinkouDunStemNode] = None
    general: Optional[JinkouDunStemNode] = None
    guishen_intrinsic_ganzhi: Optional[str] = None
    relation: Optional[Relation] = None
    motion_analogue: Optional[Literal["贼动同类", "财动同类"]] = None
    rule_evaluations: Optional[List[JinkouStemRule]] = Field(
        default=None, min_length=4, max_length=4
    )
    pair_facts: Optional[JinkouGanzhiPairFacts] = None
    fenzu_heju_status: Optional[Literal["not_adjudicated"]] = None
    named_wuhe_position_status: Optional[Literal["not_adjudicated"]] = None
    complete_classical_conformance: Optional[Literal[False]] = None
    scope: Optional[str] = None

    @field_validator("rule_evaluations")
    @classmethod
    def keep_all_four_rules(
        cls, value: Optional[List[JinkouStemRule]]
    ) -> Optional[List[JinkouStemRule]]:
        if value is not None and {r.id for r in value} != {
            "god_generates_general",
            "general_generates_god",
            "god_controls_general",
            "general_controls_god",
        }:
            raise ValueError("干元类须保留四条不同的明示生克规则")
        return value

    @field_validator("complete_classical_conformance", mode="before")
    @classmethod
    def no_full_book_claim(cls, value: Any) -> Any:
        if value is not None and value is not False:
            raise ValueError("遁干节录不等于整书符合")
        return value

    @model_validator(mode="after")
    def role_and_summary_consistency(self) -> "JinkouStemRelations":
        for role, node in (("贵神", self.god), ("将神", self.general)):
            if node is not None and node.position is not None and node.position != role:
                raise ValueError("神干与将干的角色不得交换")
            if (
                self.day_stem is not None
                and node is not None
                and node.branch is not None
            ):
                stem = wuzidun_stem(self.day_stem, node.branch)
                for name, expected_fact in (
                    ("dun_stem", stem),
                    ("dun_ganzhi", stem + node.branch),
                    ("dun_element", stem_element_text(stem)),
                ):
                    if (
                        name in node.model_fields_set
                        and getattr(node, name) != expected_fact
                    ):
                        raise ValueError("当日遁干须符合所列日干与神将本支")
        if self.guishen_intrinsic_ganzhi is not None:
            _valid_ganzhi(self.guishen_intrinsic_ganzhi)
            if (
                self.god is not None
                and self.god.branch is not None
                and self.guishen_intrinsic_ganzhi[1] != self.god.branch
            ):
                raise ValueError("贵神固有干支须与本支一致")
        phases: dict[str, str] = {}
        for role, node in (("贵神", self.god), ("将神", self.general)):
            if node is not None:
                phase = (
                    stem_element_text(node.dun_stem)
                    if node.dun_stem is not None
                    else node.dun_element
                )
                if phase is not None:
                    phases[role] = phase
        if "贵神" in phases and "将神" in phases:
            a, b = phases["贵神"], phases["将神"]
            derived = "两干比和"
            relations = (
                ("神干生将干", ELEMENT_GENERATES[a] == b),
                ("将干生神干", ELEMENT_GENERATES[b] == a),
                ("神干克将干", ELEMENT_CONTROLS[a] == b),
                ("将干克神干", ELEMENT_CONTROLS[b] == a),
            )
            phase_matches = dict(relations)
            for relation, matched in relations:
                if matched:
                    derived = relation
            if self.relation is not None and self.relation != derived:
                raise ValueError("干类关系须符合实际两遁干五行")
            if self.rule_evaluations is not None and any(
                r.matched != phase_matches[r.relation] for r in self.rule_evaluations
            ):
                raise ValueError("干类条目须符合实际两遁干五行")
        if self.relation is not None and self.rule_evaluations is not None:
            matches = [r.relation for r in self.rule_evaluations if r.matched]
            expected = [] if self.relation == "两干比和" else [self.relation]
            if matches != expected:
                raise ValueError("干类摘要与四条生克事实不一致")
        if self.relation is not None and "motion_analogue" in self.model_fields_set:
            expected_motion = {"神干克将干": "贼动同类", "将干克神干": "财动同类"}.get(
                self.relation
            )
            if self.motion_analogue != expected_motion:
                raise ValueError("干类动象同类与实际遁干生克不一致")
        if self.pair_facts is not None:
            for node, value in (
                (self.god, self.pair_facts.left_ganzhi),
                (self.general, self.pair_facts.right_ganzhi),
            ):
                if (
                    node is not None
                    and node.dun_ganzhi is not None
                    and value is not None
                    and node.dun_ganzhi != value
                ):
                    raise ValueError("配对干支与神将遁干事实不一致")
        return self
