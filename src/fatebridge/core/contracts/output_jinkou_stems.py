"""Daily-stem facts, distinct from intrinsic god and branch-based motions."""

from typing import Literal

from pydantic import Field, StrictBool, field_validator, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.metaphysics.common import (
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    SIX_HARMONY_BRANCHES,
    branch_element_text,
    sexagenary_index_for,
    stem_element_text,
    xun_head_for_ganzhi,
)
from fatebridge.core.metaphysics.jinkou.patterns import STEM_COMBINES, wuzidun_stem
from fatebridge.utils.data import STEM_ELEMENTS


def ganzhi_pair_facts(left: str, right: str) -> dict[str, object]:
    el = STEM_COMBINES.get(frozenset((left[0], right[0])))
    lx, rx = xun_head_for_ganzhi(left), xun_head_for_ganzhi(right)
    return {
        "left_ganzhi": left,
        "right_ganzhi": right,
        "stem_harmony_matched": el is not None,
        "candidate_element": el,
        "branch_harmony_matched": SIX_HARMONY_BRANCHES[left[1]] == right[1],
        "both_harmonies_matched": el is not None
        and SIX_HARMONY_BRANCHES[left[1]] == right[1],
        "left_ganzhi_xun_head": lx,
        "right_ganzhi_xun_head": rx,
        "same_ganzhi_xun": lx == rx,
    }


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
    position: Literal["贵神", "将神"] | None = None
    name: str | None = None
    branch: Branch | None = None
    branch_element: Phase | None = None
    dun_stem: Stem | None = None
    dun_ganzhi: str | None = None
    dun_element: Phase | None = None
    branch_xun_kong: StrictBool | None = None
    branch_si_da_kong: StrictBool | None = None

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
    left_ganzhi: str | None = None
    right_ganzhi: str | None = None
    stem_harmony_matched: StrictBool | None = None
    canonical_stem_pair: list[Stem] | None = Field(
        default=None, min_length=2, max_length=2
    )
    candidate_element: Phase | None = None
    branch_harmony_matched: StrictBool | None = None
    both_harmonies_matched: StrictBool | None = None
    left_ganzhi_xun_head: str | None = None
    right_ganzhi_xun_head: str | None = None
    same_ganzhi_xun: StrictBool | None = None
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
    source_position: Literal["贵神", "将神"] | None = None
    target_position: Literal["贵神", "将神"] | None = None
    phase_relation: Literal["生", "克"] | None = None
    matched: StrictBool
    original_pdf_pages: list[int] | None = None

    @model_validator(mode="after")
    def clause_metadata_matches_identifier(self) -> "JinkouStemRule":
        return self


class JinkouStemRelations(PartialOutput):
    ruleset_id: Literal["jinkou_jingben_dun_stem_relations_v1"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    original_pdf_pages: list[int] | None = None
    day_stem: Stem | None = None
    dun_cycle_policy: Literal["single_cycle_zi_to_hai"] | None = None
    god: JinkouDunStemNode | None = None
    general: JinkouDunStemNode | None = None
    guishen_intrinsic_ganzhi: str | None = None
    relation: Relation | None = None
    motion_analogue: Literal["贼动同类", "财动同类"] | None = None
    rule_evaluations: list[JinkouStemRule] | None = Field(
        default=None, min_length=4, max_length=4
    )
    pair_facts: JinkouGanzhiPairFacts | None = None
    fenzu_heju_status: str | None = None
    named_wuhe_position_status: str | None = None
    complete_classical_conformance: StrictBool | None = None
    scope: str | None = None

    @field_validator("rule_evaluations")
    @classmethod
    def keep_all_four_rules(
        cls, value: list[JinkouStemRule] | None
    ) -> list[JinkouStemRule] | None:
        return value

    @field_validator("complete_classical_conformance", mode="before")
    @classmethod
    def no_full_book_claim(cls, value: object) -> bool | None:
        return value if value is None or type(value) is bool else False

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
