"""Output contracts and validators for Jin Kou Jue."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import combinations
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    ValidationInfo,
    field_validator,
    model_validator,
)

from fatebridge.core.contracts.base import PartialOutput
from fatebridge.core.contracts.common import BranchName
from fatebridge.core.contracts.liuren import (
    RenCalendarPolicy,
    RenDiurnalEvidence,
    RenRuleset,
    compare_selection,
)
from fatebridge.core.metaphysics.jinkou.board import (
    STEM_PAIRS,
    _jinkou_pick_use_position,
    build_jinkou_qi,
    internal_strength,
    seasonal_power,
    seasonal_power_basis,
)
from fatebridge.core.metaphysics.jinkou.patterns import (
    CALENDAR_CONTEXTS,
    JUE_CONTEXTS,
)
from fatebridge.core.metaphysics.jinkou.patterns import (
    MONTH_STAR_TARGETS as MONTH_TARGETS,
)
from fatebridge.core.metaphysics.jinkou.patterns import MONTHS_ORDER as MONTHS
from fatebridge.core.metaphysics.jinkou.patterns import SI_BAI, SI_JUE, TIANSHE_TARGETS
from fatebridge.core.metaphysics.jinkou.patterns import (
    WRITTEN_BREAK_PAIRS as WRITTEN_PAIRS,
)
from fatebridge.core.metaphysics.jinkou.patterns import (
    branch_breaks,
    branch_stars,
    definition_evidence,
    natal_absolute,
    pattern_identity,
    pattern_metadata,
    patterns_from_symbols,
    structural_relations,
    use_evidence,
    wuzidun_stem,
)
from fatebridge.core.metaphysics.jinkou.year_fate import (
    confirmed_natal_branch,
    natal_course_metadata,
    ordinal_year_fate,
)
from fatebridge.utils.data import (
    EARTHLY_BRANCHES,
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    HEAVENLY_STEMS,
    SEXAGENARY_INDEX,
    SIX_CLASH_BRANCHES,
    SIX_HARMONY_BRANCHES,
    STEM_ELEMENTS,
    branch_element_text,
    sexagenary_index_for,
    stem_element_text,
    xun_head_for_ganzhi,
)

POSITIONS = ("人元", "贵神", "将神", "地分")
STAR_POSITIONS = ("贵神", "将神", "地分")
BREAK_CONTEXTS = (
    ("god_general", 1, 2),
    ("god_ground", 1, 3),
    ("general_ground", 2, 3),
)
TEXT_FIELDS = frozenset({"basis", "scope", "note", "source_section"})
MONTH_DEPENDENTS = ("month_offset", "month_qi_label", "month_qi_status")
QI_SECTION = "卷上·四绝/四败/岁君建破"
EXPECTED_EVIDENCE_KEYS = frozenset({"internal_strength", "use_evidence", "qi_evidence"})
ROW_FIELDS = (
    "label",
    "content",
    "element",
    "polarity",
    "seasonal_power",
    "internal_power",
    "xun_kong",
    "si_da_kong",
    "month_break",
    "is_use",
)
INTERACTION_RULE_IDS = frozenset(
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
_STEM_COMBINE_MAP = {
    frozenset(pair): (list(pair), element) for pair, element in STEM_PAIRS
}

Branch = Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
Stem = Literal["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
Phase = Literal["木", "火", "土", "金", "水"]
Position = Literal["人元", "贵神", "将神", "地分"]
StarPosition = Literal["贵神", "将神", "地分"]
PatternId = Literal["P52", "P53", "P56", "P57", "P58", "P59"]
InteractionRuleId = Literal[
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
StemRelation = Literal[
    "神干生将干", "将干生神干", "神干克将干", "将干克神干", "两干比和"
]
StemRuleId = Literal[
    "god_generates_general",
    "general_generates_god",
    "god_controls_general",
    "general_controls_god",
]


def compare_present(actual: object, expected: object, path: str = "") -> None:
    """Preserve projections and free prose, reject incompatible computed facts."""
    if isinstance(actual, dict) and isinstance(expected, dict):
        if path.endswith("powers") and set(actual) - set(expected):
            raise ValueError("课内旺衰不能添加不存在的位置")
        for key in actual.keys() & expected.keys():
            if key not in TEXT_FIELDS:
                compare_present(actual[key], expected[key], path + "." + key)
    elif isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError("金口诀旺衰或取用条件的完整队列不一致")
        for a, b in zip(actual, expected):
            compare_present(a, b, path)
    elif type(actual) is not type(expected) or actual != expected:
        raise ValueError("金口诀旺衰、得气或用位条件与本次四位不一致")


def _compare_breaks(
    actual: object, expected: object, *, complete: bool = False
) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or (
            complete and expected.keys() - actual.keys()
        ):
            raise ValueError("完整破支事实缺少原文或同课依据")
        for key in actual.keys() & expected.keys():
            _compare_breaks(actual[key], expected[key], complete=complete)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError("破支事实须保留所列完整队列")
        for a, b in zip(actual, expected):
            _compare_breaks(a, b, complete=complete)
    elif type(actual) is not type(expected) or actual != expected:
        raise ValueError("破支事实与所选原文或本课本支不一致")


def _pair_facts(a: str, b: str) -> dict[str, object]:
    matched = f"{a}{b}" in WRITTEN_PAIRS or f"{b}{a}" in WRITTEN_PAIRS
    return {"left_branch": a, "right_branch": b, "source_pair_present": matched}


def _breaks_metadata() -> dict[str, str]:
    return {"ruleset_id": "jinkou_jingben_printed_break_pairs_v1"}


def _as_dict(value: object) -> dict[str, object]:
    if isinstance(value, BaseModel):
        return value.model_dump(exclude_unset=True)
    if isinstance(value, dict):
        return dict(value)
    return {}


class BreakPairWitness(PartialOutput):
    id: str | None = None
    title: str | None = None
    source_url: str | None = None
    source_bytes: StrictInt | None = None
    source_pdf_pages: StrictInt | None = None
    reviewed_pdf_pages: list[StrictInt] | None = None
    phrase_pdf_page: StrictInt | None = None
    literal_break_sequence: str | None = None
    extra_phrase_present: StrictBool | None = None
    reading_status: (
        Literal["literal_phrase_readable", "unresolved_dense_handwriting"] | None
    ) = None
    enumerated_pair_count: None = None
    note: str | None = None

    @model_validator(mode="after")
    def readable_phrase_is_not_an_effect_claim(self) -> BreakPairWitness:
        if (
            self.literal_break_sequence is not None
            and self.extra_phrase_present is not None
        ):
            if self.extra_phrase_present is not (
                "寅破巳" in self.literal_break_sequence
            ):
                raise ValueError("字句旁证须符合实际转写，不增写第二个寅")
        if (
            "literal_break_sequence" in self.model_fields_set
            and self.literal_break_sequence is None
        ):
            if self.extra_phrase_present is not None:
                raise ValueError("未读清的见证不能改成支持或否定")
        return self


class BreakPairWitnessEvidence(PartialOutput):
    method_id: Literal["jinkou_break_pair_textual_witnesses_v1"] | None = None
    reader_count: StrictInt | None = None
    blinded: StrictBool | None = None
    independent_expert_review: StrictBool | None = None
    independent_transmission_established: StrictBool | None = None
    witnesses: list[BreakPairWitness] | None = None
    extra_phrase_corroborated: StrictBool | None = None
    readable_corroboration_count: StrictInt | None = None
    unresolved_witness_count: StrictInt | None = None
    author_intent: None = None
    effective_break: None = None
    effect_direction: None = None
    whole_book_conformance: StrictBool | None = None
    new_independent_real_events: StrictInt | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def no_false_source_certification(self) -> BreakPairWitnessEvidence:
        for key in (
            "blinded",
            "independent_expert_review",
            "independent_transmission_established",
            "whole_book_conformance",
        ):
            if key in self.model_fields_set and getattr(self, key) is not False:
                raise ValueError("本次目读未建立盲验、独立专家、传承独立或全书符合")
        if self.witnesses is not None and all(
            "extra_phrase_present" in w.model_fields_set for w in self.witnesses
        ):
            positive = sum(w.extra_phrase_present is True for w in self.witnesses)
            unknown = sum(w.extra_phrase_present is None for w in self.witnesses)
            if (
                self.readable_corroboration_count is not None
                and self.readable_corroboration_count != positive
            ):
                raise ValueError("可读旁证计数不一致")
            if (
                self.unresolved_witness_count is not None
                and self.unresolved_witness_count != unknown
            ):
                raise ValueError("未读清见证不能从分母删除")
        return self


class JinkouBreakPair(PartialOutput):
    id: Literal["god_general", "god_ground", "general_ground"] | None = None
    left_position: str | None = None
    right_position: str | None = None
    left_branch: Branch | None = None
    right_branch: Branch | None = None
    source_pair_present: StrictBool | None = None
    source_written_pair: list[Branch] | None = Field(
        default=None, min_length=2, max_length=2
    )
    source_order: Literal["left_then_right", "right_then_left"] | None = None
    effective_break: None = None
    effect_direction: None = None

    @model_validator(mode="after")
    def present_facts_agree(self) -> JinkouBreakPair:
        value = self.model_dump(exclude_unset=True)
        if self.id is not None:
            _, i, j = next(c for c in BREAK_CONTEXTS if c[0] == self.id)
            _compare_breaks(
                value, dict(left_position=POSITIONS[i], right_position=POSITIONS[j])
            )
        if self.left_branch is not None and self.right_branch is not None:
            _compare_breaks(value, _pair_facts(self.left_branch, self.right_branch))
        elif any(
            k in value and value[k] is None for k in ("left_branch", "right_branch")
        ):
            if self.source_pair_present is not None:
                raise ValueError("明确未知的本支不能判定破支配对")
        return self


class JinkouBranchBreaks(PartialOutput):
    ruleset_id: Literal["jinkou_jingben_printed_break_pairs_v1"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    original_pdf_page: StrictInt | None = None
    written_pairs: list[list[Branch]] | None = None
    transcription_url: str | None = None
    transcription_written_pairs: list[list[Branch]] | None = None
    scan_extra_pairs: list[list[Branch]] | None = None
    extra_pair_author_intent: None = None
    witness_evidence: BreakPairWitnessEvidence | None = None
    membership_policy: str | None = None
    rows: list[JinkouBreakPair] | None = Field(default=None, min_length=3, max_length=3)
    effect_direction: None = None
    effective_break: None = None
    complete_classical_conformance: StrictBool | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def same_source_and_queue(self) -> JinkouBranchBreaks:
        value = self.model_dump(exclude_unset=True)
        _compare_breaks(value, _breaks_metadata())
        if self.rows is not None:
            _compare_breaks(
                value["rows"],
                [
                    dict(
                        id=identifier,
                        left_position=POSITIONS[i],
                        right_position=POSITIONS[j],
                    )
                    for identifier, i, j in BREAK_CONTEXTS
                ],
            )
        return self


def align_branch_breaks(value: object, *, complete: bool = False) -> None:
    board = _as_dict(value)
    rows = board.get("rows")
    expected = None
    if isinstance(rows, list):
        by_role = {
            r.get("label"): r.get("content") for r in rows if isinstance(r, dict)
        }
        star_branches = [by_role.get(p) for p in STAR_POSITIONS]
        if all(isinstance(b, str) for b in star_branches):
            b0, b1, b2 = star_branches
            if isinstance(b0, str) and isinstance(b1, str) and isinstance(b2, str):
                expected = branch_breaks(b0, b1, b2)
    block = board.get("branch_breaks")
    if complete:
        if expected is None or block is None:
            raise ValueError("完整金口诀须保留三组破支事实")
        _compare_breaks(block, expected, complete=True)
    elif expected is not None and block is not None:
        _compare_breaks(block, expected)


class JinkouBranchStarCheck(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    id: Literal["tianxi", "tianma", "yima", "sangche", "sangmen", "diaoke", "tianshe"]
    name: str
    category: Literal["month_building", "year_branch", "season_and_day"]
    target_kind: Literal["branch", "day_ganzhi"]
    target: str
    matched_positions: list[StarPosition]
    matched_day: StrictBool | None
    original_pdf_page: Literal[118, 119, 120] | None = None

    @model_validator(mode="after")
    def whole_item(self) -> JinkouBranchStarCheck:
        day = self.id == "tianshe"
        if (
            self.target_kind != ("day_ganzhi" if day else "branch")
            or (day and (self.matched_positions or type(self.matched_day) is not bool))
            or (not day and self.matched_day is not None)
            or self.matched_positions
            != [p for p in STAR_POSITIONS if p in self.matched_positions]
        ):
            raise ValueError("京本神煞条目的目标、匹配范围或位置重复不一致")
        names = dict(
            zip(
                ("tianxi", "tianma", "yima", "sangche", "sangmen", "diaoke", "tianshe"),
                ("天喜", "天马", "驿马", "丧车", "丧门", "吊客", "天赦"),
            )
        )
        category = (
            "season_and_day"
            if day
            else "year_branch" if self.id in {"sangmen", "diaoke"} else "month_building"
        )
        page = (
            118
            if self.id in {"tianxi", "tianshe"}
            else 119 if self.id in {"tianma", "yima"} else 120
        )
        if (
            self.name != names[self.id]
            or self.category != category
            or (self.original_pdf_page is not None and self.original_pdf_page != page)
        ):
            raise ValueError("京本神煞条目的名称、来源页或锚点类别不一致")

        if (day and self.target not in SEXAGENARY_INDEX) or (
            not day and (len(self.target) != 1 or self.target not in EARTHLY_BRANCHES)
        ):
            raise ValueError("京本神煞目标需要有效支或完整日干支")
        allowed = (
            set(TIANSHE_TARGETS)
            if day
            else (
                set(MONTH_TARGETS[self.id])
                if self.id in MONTH_TARGETS
                else set(EARTHLY_BRANCHES)
            )
        )
        if self.target not in allowed:
            raise ValueError("京本所选条目不存在该目标")
        return self


class JinkouBranchStars(PartialOutput):
    ruleset_id: Literal["jinkou_jingben_branch_stars_v1"] | None = None
    original_pdf_pages: list[int] | None = None
    year_branch: Branch | None = None
    month_building_branch: Branch | None = None
    day_ganzhi: str | None = None
    nominal_month: int | None = None
    season_partition: Literal["春", "夏", "秋", "冬"] | None = None
    month_profile: Literal["declared_term_month_ordinal_v1"] | None = None
    input_branches: dict[StarPosition, Branch] | None = None
    checks: list[JinkouBranchStarCheck] | None = None
    yima_anchor: Literal["month_building_branch"] | None = None
    comprehensive_effect: None = None
    complete_classical_conformance: StrictBool | None = None
    scope: str | None = None

    @field_validator("complete_classical_conformance", mode="before")
    @classmethod
    def no_false_certification(cls, v: object) -> bool | None:
        return v if v is None or type(v) is bool else False

    @model_validator(mode="after")
    def compatible_facts(self) -> JinkouBranchStars:
        if self.day_ganzhi is not None and self.day_ganzhi not in SEXAGENARY_INDEX:
            raise ValueError("神煞日序须为有效六十甲子")
        if self.month_building_branch is not None:
            i = MONTHS.index(self.month_building_branch)
            if self.nominal_month is not None and self.nominal_month != i + 1:
                raise ValueError("神煞名义月序须对应实际月建")
            if (
                self.season_partition is not None
                and self.season_partition != "春夏秋冬"[i // 3]
            ):
                raise ValueError("本节四季按三个月序分组，不借用土旺月五态分组")
        if self.checks is not None:
            if [c.id for c in self.checks] != [
                "tianxi",
                "tianma",
                "yima",
                "sangche",
                "sangmen",
                "diaoke",
                "tianshe",
            ]:
                raise ValueError("京本所选七项神煞须完整有序")
            for c in self.checks:
                if c.target_kind == "branch" and self.input_branches is not None:
                    for p, b in self.input_branches.items():
                        if (p in c.matched_positions) != (b == c.target):
                            raise ValueError("神煞匹配位置与实际本支不一致")
                if (
                    c.target_kind == "day_ganzhi"
                    and self.day_ganzhi is not None
                    and c.matched_day != (self.day_ganzhi == c.target)
                ):
                    raise ValueError("天赦须与实际占日完整干支核对")
        if (
            self.year_branch is not None
            and self.month_building_branch is not None
            and self.day_ganzhi is not None
            and self.input_branches is not None
            and set(self.input_branches) == set(STAR_POSITIONS)
        ):
            inputs: dict[str, str] = {
                position: branch for position, branch in self.input_branches.items()
            }
            expected = branch_stars(
                year_branch=self.year_branch,
                month_branch=self.month_building_branch,
                day_ganzhi=self.day_ganzhi,
                input_branches=inputs,
            )
            compare_present(self.model_dump(exclude_unset=True), expected)
        return self


def align_branch_stars(board: Mapping[str, object]) -> None:
    value = board.get("branch_stars")
    if not isinstance(value, dict):
        return
    rows = board.get("rows")
    if not isinstance(rows, list):
        return
    raw_inputs = value.get("input_branches")
    inputs = raw_inputs if isinstance(raw_inputs, dict) else {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        p = row.get("label")
        if p in inputs and "content" in row and inputs[p] != row["content"]:
            raise ValueError("京本神煞须使用同课贵神、将神、地分本支")


def require_complete_branch_stars(board: Mapping[str, object]) -> None:
    value = board.get("branch_stars")
    if not isinstance(value, dict):
        raise ValueError("完整金口诀须保留京本神煞定位依据")
    JinkouBranchStars.model_validate(value)
    try:
        expected = branch_stars(
            year_branch=value["year_branch"],
            month_branch=value["month_building_branch"],
            day_ganzhi=value["day_ganzhi"],
            input_branches=value["input_branches"],
        )
    except KeyError as exc:
        raise ValueError("完整京本神煞定位缺少同次输入") from exc
    if value != expected:
        raise ValueError("完整京本神煞定位须保留全部计算事实")
    align_branch_stars(board)


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
    id: InteractionRuleId
    name: str
    quantifier: Literal["all", "any"]
    matched: StrictBool
    condition_checks: list[JinkouInteractionCondition] | None = None
    original_pdf_pages: list[int] | None = None

    @model_validator(mode="after")
    def matches_its_conditions(self) -> JinkouInteractionRule:
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
    matched_rule_ids: list[InteractionRuleId] | None = None
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
        if value is not None and {r.id for r in value} != INTERACTION_RULE_IDS:
            raise ValueError("四位关系须保留十四条不同来源规则")
        return value

    @field_validator("complete_classical_conformance", mode="before")
    @classmethod
    def no_full_book_claim(cls, value: object) -> bool | None:
        return value if value is None or type(value) is bool else False

    @model_validator(mode="after")
    def summary_matches_facts(self) -> JinkouPositionInteractions:
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


def chapter_provenance() -> dict[str, str]:
    return {"id": "waseda_book6"}


class ChapterHeading(PartialOutput):
    occurrence_id: str | None = None
    pdf_page: int | None = Field(default=None, ge=1)
    side: Literal["R", "L"] | None = None
    raw_heading: str | None = None
    selected_definition: str | None = None
    selected_alias: str | None = None
    reading_note: str | None = None


class ChapterObservation(PartialOutput):
    id: str | None = None
    occurrences: list[str] | None = None
    observation: str | None = None


class JinkouChapterInventory(PartialOutput):
    inventory_id: Literal["waseda_jinkou_chapter_v1"] | None = None
    source_pdf_pages: int | None = Field(default=None, ge=1)
    reviewed_pdf_pages: list[int] | None = None
    chapter_heading: str | None = None
    chapter_start_pdf_page: int | None = Field(default=None, ge=1)
    chapter_end_pdf_page: int | None = Field(default=None, ge=1)
    observed_heading_occurrences: int | None = Field(default=None, ge=0)
    unique_raw_headings: int | None = Field(default=None, ge=0)
    duplicate_raw_headings: list[str] | None = None
    headings: list[ChapterHeading] | None = None
    direct_observations: list[ChapterObservation] | None = None
    chapter_heading_inventory_complete: Literal[True] | None = None
    whole_volume_transcription_complete: Literal[False] | None = None
    all_definitions_transcribed: Literal[False] | None = None
    all_diagrams_transcribed: Literal[False] | None = None
    independent_transmission_established: Literal[False] | None = None
    chronological_priority_established: Literal[False] | None = None
    classical_predicates_adjudicated: Literal[0] | None = None
    full_classical_conformance: Literal[False] | None = None
    scope: str | None = None


class DefinitionWitness(PartialOutput):
    id: Literal["cnts_v2", "waseda_book6"] | None = None
    title: str | None = None
    catalog_id: str | None = None
    catalog_url: str | None = None
    scan_url: str | None = None
    chronology: str | None = None
    full_scan_url: str | None = None
    chapter_inventory: JinkouChapterInventory | None = None


class DefinitionReading(PartialOutput):
    witness_id: Literal["cnts_v2", "waseda_book6"] | None = None
    locator: str | None = None
    raw_heading: str | None = None
    raw_alias: str | None = None
    raw_definition: str | None = None
    literal_day_ganzhi: str | None = None
    literal_hour_branch: str | None = None
    literal_four_positions: list[str] | None = Field(
        default=None, min_length=4, max_length=4
    )


class UnresolvedDefinition(PartialOutput):
    pattern_id: PatternId | None = None
    name: str | None = None
    witness_readings: list[DefinitionReading] | None = Field(
        default=None, min_length=2, max_length=2
    )
    status: Literal["unresolved"] | None = None
    adjudicated_match: None = None
    unresolved_reason: str | None = None


class GenerationHypothesis(PartialOutput):
    pattern_id: Literal["P52", "P53"] | None = None
    hypothesis_id: Literal["outer_inner", "adjacent_pairs", "conjunction"] | None = None
    condition_checks: list[JinkouInteractionCondition] | None = None
    all_conditions_met: StrictBool | None = None
    adjudicated_predicate: None = None

    @model_validator(mode="after")
    def conjunction_matches_checks(self) -> GenerationHypothesis:
        if self.condition_checks is not None and self.all_conditions_met is not None:
            flags = [c.matched for c in self.condition_checks]
            if all(f is not None for f in flags) and self.all_conditions_met != all(
                flags
            ):
                raise ValueError("隔生候选的合取值与所列条件不一致")
        return self


class DayNightCandidate(PartialOutput):
    mode: Literal["day", "night"] | None = None
    assumed_is_diurnal: StrictBool | None = None
    selected_under_current_policy: StrictBool | None = None
    start_branch: str | None = None
    ground_branch: str | None = None
    god_name: str | None = None
    intrinsic_ganzhi: str | None = None
    ground_clockwise_steps: int | None = Field(default=None, ge=0, le=11)
    ground_counterclockwise_steps: int | None = Field(default=None, ge=0, le=11)


class DingRoute(PartialOutput):
    route_id: (
        Literal["intrinsic_god", "daily_god", "daily_general", "human_redun_at_ground"]
        | None
    ) = None
    anchor_stem: str | None = None
    target_branch: str | None = None
    stem: str | None = None
    element: str | None = None
    is_ding: StrictBool | None = None
    controls_human: StrictBool | None = None
    controls_ground: StrictBool | None = None
    identified_by_original_clause: None = None


class JinkouDefinitionEvidence(PartialOutput):
    ruleset_id: (
        Literal[
            "jinkou_definition_evidence_v2", "jinkou_unresolved_definition_evidence_v1"
        ]
        | None
    ) = None
    day_stem: str | None = None
    hour_branch: str | None = None
    selected_is_diurnal: StrictBool | None = None
    witnesses: list[DefinitionWitness] | None = None
    entries: list[UnresolvedDefinition] | None = None
    cross_generation_hypotheses: list[GenerationHypothesis] | None = None
    day_night_candidates: list[DayNightCandidate] | None = Field(
        default=None, min_length=2, max_length=2
    )
    ground_equals_day_start: StrictBool | None = None
    ground_equals_night_start: StrictBool | None = None
    ground_equals_other_start: StrictBool | None = None
    ding_routes: list[DingRoute] | None = Field(
        default=None, min_length=4, max_length=4
    )
    observed_twilight_transition: None = None
    front_back_predicate: None = None
    complete_classical_conformance: StrictBool | None = None
    scope: str | None = None

    @field_validator("entries")
    @classmethod
    def fixed_unresolved_inventory(
        cls, value: list[UnresolvedDefinition] | None
    ) -> list[UnresolvedDefinition] | None:
        if value is not None and [e.pattern_id for e in value] != [
            "P52",
            "P53",
            "P56",
            "P57",
            "P58",
            "P59",
        ]:
            raise ValueError("六条疑义课式不得遗漏、重排或重复")
        return value


def compare_present_definition_facts(actual: object, expected: object) -> None:
    """Allow arbitrary projections; reject contradictory facts that are present."""
    if isinstance(actual, dict) and isinstance(expected, dict):
        for key, value in actual.items():
            if key in expected:
                compare_present_definition_facts(value, expected[key])
    elif isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError("课钤疑义依据的队列与本课不一致")
        for a, b in zip(actual, expected):
            compare_present_definition_facts(a, b)
    elif actual != expected:
        raise ValueError("课钤疑义依据与本课四位、日干或昼夜条件不一致")


def require_complete_chapter_witness(board: Mapping[str, object]) -> None:
    raw_definitions = board.get("definition_evidence")
    definitions = raw_definitions if isinstance(raw_definitions, dict) else {}
    raw_witnesses = definitions.get("witnesses")
    witnesses = raw_witnesses if isinstance(raw_witnesses, list) else []
    selected = [
        w for w in witnesses if isinstance(w, dict) and w.get("id") == "waseda_book6"
    ]
    if len(selected) != 1:
        raise ValueError("完整金口诀须保留唯一的早稻田原典见证")
    expected = chapter_provenance()
    if any(selected[0].get(key) != value for key, value in expected.items()):
        raise ValueError("完整金口诀须保留连续课钤书影清单及全部未裁定说明")


class JinkouNatalAbsolute(PartialOutput):
    left_position: Literal["将神"] | None = None
    right_position: Literal["命支"] | None = None
    left_branch: Branch | None = None
    right_branch: Branch | None = None
    classification: Literal["大绝"] | None = None
    matched: bool | None = None
    element: Literal["木", "火", "金", "水"] | None = None
    status: Literal["computed", "missing_birth_branch"] | None = None
    input_source: (
        Literal["explicit_natal_branch", "explicit_birth_year_ganzhi", "not_provided"]
        | None
    ) = None
    original_pdf_page: Literal[109] | None = None
    basis: str | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def declared_natal_branch_controls_knownness(self) -> JinkouNatalAbsolute:
        if "right_branch" not in self.model_fields_set:
            return self
        provided = self.right_branch is not None
        allowed_sources = (
            {"explicit_natal_branch", "explicit_birth_year_ganzhi"}
            if provided
            else {"not_provided"}
        )
        if (
            "input_source" in self.model_fields_set
            and self.input_source not in allowed_sources
        ):
            raise ValueError("本命年支的明确来源与已知状态不一致")
        source = self.input_source or (
            "explicit_natal_branch" if provided else "not_provided"
        )
        known: dict[str, object] = {
            "status": "computed" if provided else "missing_birth_branch",
            "input_source": source,
        }
        if not provided:
            known.update(matched=None, element=None)
        if self.left_branch is not None:
            known.update(
                natal_absolute(self.left_branch, self.right_branch, input_source=source)
            )
        actual = self.model_dump(exclude_unset=True)
        if any(actual[k] != value for k, value in known.items() if k in actual):
            raise ValueError("将命大绝与本命支、京本配对或未知状态不一致")
        return self


def _qi_metadata() -> dict[str, str]:
    return {"ruleset_id": "jinkou_yuejian_richen_excerpt_v1"}


def offset_qi_facts(offset: int) -> dict[str, object]:
    label = {0: "建旺", 1: "进气相", 2: "进气相", 6: "月破", 11: "退气"}.get(offset)
    return {
        "month_offset": offset,
        "month_qi_label": label,
        "month_qi_status": "matched_excerpt" if label else "not_classified_by_excerpt",
    }


def month_qi_facts(month: str, general: str) -> dict[str, object]:
    offset = (EARTHLY_BRANCHES.index(general) - EARTHLY_BRANCHES.index(month)) % 12
    return {
        "month_building_branch": month,
        "jiangshen_branch": general,
        **offset_qi_facts(offset),
    }


def day_qi_facts(day: str, general: str) -> dict[str, object]:
    day_el, gen_el = branch_element_text(day), branch_element_text(general)
    return {
        "day_branch": day,
        "day_element": day_el,
        "jiangshen_element": gen_el,
        "day_generates_general": ELEMENT_GENERATES[day_el] == gen_el,
    }


def qi_basis(month: str, general: str, day: str) -> str:
    m = month_qi_facts(month, general)
    d = day_qi_facts(day, general)
    return (
        f"月建{month}、将神{general}相距{m['month_offset']}支"
        f"（{m['month_qi_label'] or '平'}）；"
        f"日支{day}({d['day_element']}){'生' if d['day_generates_general'] else '未生'}"
        f"将神({d['jiangshen_element']})。"
    )


def _compare_qi(actual: object, expected: object) -> None:
    if isinstance(actual, dict) and isinstance(expected, dict):
        for key in actual.keys() & expected.keys():
            _compare_qi(actual[key], expected[key])
    elif isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError("月建日辰得气队列不一致")
        for a, b in zip(actual, expected):
            _compare_qi(a, b)
    elif type(actual) is not type(expected) or actual != expected:
        raise ValueError("月建日辰得气说明或事实与实际依据不一致")


def validate_qi_fields(value: Mapping[str, object]) -> None:
    _compare_qi(value, _qi_metadata())
    month = value.get("month_building_branch")
    general = value.get("jiangshen_branch")
    day = value.get("day_branch")
    for key, dependents in (
        ("month_building_branch", MONTH_DEPENDENTS),
        (
            "jiangshen_branch",
            (*MONTH_DEPENDENTS, "jiangshen_element", "day_generates_general"),
        ),
        ("day_branch", ("day_element", "day_generates_general")),
    ):
        if (
            key in value
            and value[key] is None
            and any(value.get(k) is not None for k in dependents)
        ):
            raise ValueError("明确未知的得气依据不能产生已知结论")
    month_offset = value.get("month_offset")
    if isinstance(month_offset, int) and not isinstance(month_offset, bool):
        _compare_qi(value, offset_qi_facts(month_offset))
    if isinstance(month, str) and isinstance(general, str):
        _compare_qi(value, month_qi_facts(month, general))
    for key, branch_val in (("day_element", day), ("jiangshen_element", general)):
        if isinstance(branch_val, str) and key in value:
            _compare_qi(value[key], branch_element_text(branch_val))
    if isinstance(day, str) and isinstance(general, str):
        _compare_qi(value, day_qi_facts(day, general))
    else:
        day_el = value.get("day_element")
        gen_el = value.get("jiangshen_element")
        if isinstance(day_el, str) and isinstance(gen_el, str):
            _compare_qi(
                value,
                dict(day_generates_general=ELEMENT_GENERATES[day_el] == gen_el),
            )
    if (
        isinstance(month, str)
        and isinstance(general, str)
        and isinstance(day, str)
        and "basis" in value
    ):
        _compare_qi(value["basis"], qi_basis(month, general, day))


def month_building_metadata() -> dict[str, str]:
    return {}


def month_building_check(position: str, branch: str, month: str) -> dict[str, object]:
    return {
        "position": position,
        "branch": branch,
        "month_building_branch": month,
        "matched": branch == month,
    }


class JinkouInternalRelation(PartialOutput):
    source_position: str | None = None
    target_position: str | None = None
    source_element: str | None = None
    target_element: str | None = None
    relation: str | None = None


class JinkouMonthBuildingCheck(PartialOutput):
    position: Literal["贵神", "将神"] | None = None
    branch: str | None = None
    month_building_branch: str | None = None
    matched: StrictBool | None = None


class JinkouQiEvidence(PartialOutput):
    ruleset_id: str | None = None
    month_building_branch: Branch | None = None
    month_building_checks: list[JinkouMonthBuildingCheck] | None = None
    month_building_basis: str | None = None
    month_building_scan_url: str | None = None
    month_building_pdf_page: int | None = None
    month_building_scope: str | None = None
    jiangshen_branch: Branch | None = None
    month_offset: StrictInt | None = Field(default=None, ge=0, le=11)
    month_qi_label: Literal["建旺", "进气相", "月破", "退气"] | None = None
    month_qi_status: Literal["matched_excerpt", "not_classified_by_excerpt"] | None = (
        None
    )
    day_branch: Branch | None = None
    day_element: Literal["木", "火", "土", "金", "水"] | None = None
    jiangshen_element: Literal["木", "火", "土", "金", "水"] | None = None
    day_generates_general: StrictBool | None = None
    interposition_generations: list[JinkouInternalRelation] | None = None
    source_url: str | None = None
    source_section: str | None = None
    basis: str | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def building_follows_present_anchors(self) -> JinkouQiEvidence:
        validate_qi_fields(self.model_dump(exclude_unset=True))
        compare_present(self.model_dump(exclude_unset=True), month_building_metadata())
        positions = []
        for item in self.month_building_checks or []:
            if item.position is not None:
                positions.append(item.position)
            month = item.month_building_branch or self.month_building_branch
            if (
                item.month_building_branch is not None
                and self.month_building_branch is not None
            ):
                compare_present(item.month_building_branch, self.month_building_branch)
            if (
                item.position is not None
                and item.branch is not None
                and month is not None
            ):
                expected = month_building_check(item.position, item.branch, month)
                compare_present(item.model_dump(exclude_unset=True), expected)
        if len(positions) != len(set(positions)):
            raise ValueError("神将建旺不可重复同一位置")
        return self


def validate_course_qi(board: Mapping[str, object]) -> None:
    block = board.get("qi_evidence")
    if isinstance(block, dict):
        JinkouQiEvidence.model_validate(block)


def absolute_check(left: str, right: str, a: str, b: str) -> dict[str, object]:
    phase = SI_JUE.get(frozenset((a, b)))
    ctx = next(c for c in JUE_CONTEXTS if c[0] == left and c[1] == right)
    return {
        "left_position": left,
        "right_position": right,
        "left_branch": a,
        "right_branch": b,
        "classification": ctx[2],
        "matched": phase is not None,
        "element": phase,
    }


def defeat_check(position: str, phase: str, seat: str) -> dict[str, object]:
    target = SI_BAI[phase]
    return {
        "position": position,
        "element": phase,
        "seat_branch": seat,
        "bai_branch": target,
        "matched": seat == target,
    }


def calendar_target(rid: str, ref: str) -> str:
    return ref if rid.endswith("build") else SIX_CLASH_BRANCHES[ref]


def calendar_check(rid: str, position: str, a: str, b: str) -> dict[str, object]:
    ctx = next(c for c in CALENDAR_CONTEXTS if c[0] == rid)
    return {
        "rule_id": rid,
        "name": ctx[1],
        "position": position,
        "branch": a,
        "reference_branch": b,
        "matched": a == calendar_target(rid, b),
    }


def _compare_relations(
    actual: object, expected: object, path: str = "", *, complete: bool = False
) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or (
            complete and expected.keys() - actual.keys()
        ):
            raise ValueError("完整京本结构关系缺少原始依据或判定")
        for key in actual.keys() & expected.keys():
            _compare_relations(
                actual[key], expected[key], path + "." + key, complete=complete
            )
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError("京本结构关系须保留所选完整队列")
        if path.endswith(".checks") and expected:
            first = expected[0]
            keys = (
                ("left_position", "right_position")
                if isinstance(first, dict) and "left_position" in first
                else (
                    ("rule_id", "position")
                    if isinstance(first, dict) and "rule_id" in first
                    else ("position",)
                )
            )
            if all(
                isinstance(r, dict) and all(isinstance(r.get(k), str) for k in keys)
                for r in actual
            ):
                observed = {tuple(r[k] for k in keys): r for r in actual}
                canonical = {tuple(r[k] for k in keys): r for r in expected}
                if len(observed) != len(actual) or observed.keys() != canonical.keys():
                    raise ValueError("京本结构关系的角色／规则不可重复或替换")
                for identity, row in observed.items():
                    _compare_relations(
                        row, canonical[identity], path, complete=complete
                    )
                return
        for a, e in zip(actual, expected, strict=True):
            _compare_relations(a, e, path, complete=complete)
    elif type(actual) is not type(expected) or actual != expected:
        raise ValueError("京本四绝、四败或岁日关系与同次原始依据不一致")


def _same_rel(value: Mapping[str, object], key: str, expected: object) -> None:
    if key in value:
        _compare_relations(value[key], expected)


def _branch_rel(value: Mapping[str, object], key: str) -> str | None:
    v = value.get(key)
    if v is not None and (not isinstance(v, str) or v not in SIX_CLASH_BRANCHES):
        raise ValueError("京本结构关系须使用单个明确地支")
    return v if isinstance(v, str) else None


def _unknown_is_not_a_verdict(
    value: Mapping[str, object], anchors: tuple[str, ...]
) -> None:
    if (
        any(k in value and value[k] is None for k in anchors)
        and value.get("matched") is not None
    ):
        raise ValueError("明确缺失的关系输入不能判为命中或不命中")


def validate_absolute_row(value: Mapping[str, object]) -> None:
    left, right = value.get("left_position"), value.get("right_position")
    a, b = _branch_rel(value, "left_branch"), _branch_rel(value, "right_branch")
    if right == "命支":
        _same_rel(value, "left_position", "将神")
        _same_rel(value, "classification", "大绝")
        _same_rel(value, "original_pdf_page", 109)
        if b is None:
            _same_rel(value, "matched", None)
            _same_rel(value, "element", None)
        return
    contexts = [
        c
        for c in JUE_CONTEXTS
        if (left is None or c[0] == left) and (right is None or c[1] == right)
    ]
    if not contexts:
        raise ValueError("所选四绝不存在该角色配对")
    if len(contexts) == 1:
        _same_rel(value, "classification", contexts[0][2])
    if a is not None and b is not None:
        phase = SI_JUE.get(frozenset((a, b)))
        _same_rel(value, "matched", phase is not None)
        _same_rel(value, "element", phase)
        if isinstance(left, str) and isinstance(right, str):
            _compare_relations(value, absolute_check(left, right, a, b))
    elif (
        any(k in value and value[k] is None for k in ("left_branch", "right_branch"))
        and value.get("matched") is not None
    ):
        raise ValueError("明确缺失的四绝输入不能判为命中或不命中")


def validate_defeat_row(value: Mapping[str, object]) -> None:
    _unknown_is_not_a_verdict(value, ("element", "seat_branch"))
    position, phase = value.get("position"), value.get("element")
    if position is not None and position not in POSITIONS[:3]:
        raise ValueError("所选四败仅核对人元、贵神、将神临共同地分")
    if phase is not None and (not isinstance(phase, str) or phase not in SI_BAI):
        raise ValueError("四败须使用明确的五行")
    seat = _branch_rel(value, "seat_branch")
    _branch_rel(value, "bai_branch")
    if isinstance(phase, str):
        _same_rel(value, "bai_branch", SI_BAI[phase])
        if seat is not None:
            _same_rel(value, "matched", seat == SI_BAI[phase])
            if isinstance(position, str):
                _compare_relations(value, defeat_check(position, phase, seat))


def validate_calendar_row(value: Mapping[str, object]) -> None:
    _unknown_is_not_a_verdict(value, ("rule_id", "branch", "reference_branch"))
    rid, position = value.get("rule_id"), value.get("position")
    a, b = _branch_rel(value, "branch"), _branch_rel(value, "reference_branch")
    if rid is None:
        return
    context = next((c for c in CALENDAR_CONTEXTS if c[0] == rid), None)
    if context is None or (position is not None and position not in context[2]):
        raise ValueError("岁建仅神将、日建仅将神；不能替换适用位置")
    _same_rel(value, "name", context[1])
    if isinstance(rid, str) and a is not None and b is not None:
        _same_rel(value, "matched", a == calendar_target(rid, b))
        if isinstance(position, str):
            _compare_relations(value, calendar_check(rid, position, a, b))


def validate_queue(value: Mapping[str, object], group: str) -> None:
    checks = value.get("checks")
    if checks is None:
        return
    if group == "si_jue":
        expected = [
            dict(left_position=a, right_position=b, classification=c)
            for a, b, c in JUE_CONTEXTS
        ]
        check = validate_absolute_row
    elif group == "si_bai":
        expected = [dict(position=p) for p in POSITIONS[:3]]
        check = validate_defeat_row
    else:
        expected = [
            dict(rule_id=rid, name=name, position=p)
            for rid, name, positions, _ in CALENDAR_CONTEXTS
            for p in positions
        ]
        check = validate_calendar_row
    _compare_relations(checks, expected, "." + group + ".checks")
    if isinstance(checks, list):
        for row in checks:
            if isinstance(row, Mapping):
                check(row)


def _bind_anchor(anchors: dict[str, object], key: str, value: object) -> None:
    if value is None:
        return
    if key in anchors:
        _compare_relations(value, anchors[key])
    anchors[key] = value


def relation_anchors(value: Mapping[str, object]) -> dict[str, object]:
    anchors: dict[str, object] = {}
    raw_calendar = value.get("calendar")
    calendar = raw_calendar if isinstance(raw_calendar, dict) else {}
    for key in ("year_branch", "day_branch"):
        _bind_anchor(anchors, key, _branch_rel(calendar, key))
    for row in calendar.get("checks") or []:
        if not isinstance(row, dict):
            continue
        if isinstance(row.get("position"), str):
            _bind_anchor(anchors, row["position"], _branch_rel(row, "branch"))
        rid = row.get("rule_id")
        if isinstance(rid, str) and rid in {c[0] for c in CALENDAR_CONTEXTS}:
            _bind_anchor(
                anchors,
                "year_branch" if rid.startswith("year") else "day_branch",
                _branch_rel(row, "reference_branch"),
            )
    raw_si_jue = value.get("si_jue")
    for row in (
        raw_si_jue.get("checks") if isinstance(raw_si_jue, dict) else None
    ) or []:
        if not isinstance(row, dict):
            continue
        for role, fact in (
            ("left_position", "left_branch"),
            ("right_position", "right_branch"),
        ):
            role_val = row.get(role)
            if isinstance(role_val, str):
                key = {"日支": "day_branch", "时支": "hour_branch"}.get(
                    role_val, role_val
                )
                _bind_anchor(anchors, key, _branch_rel(row, fact))
    raw_si_bai = value.get("si_bai")
    for row in (
        raw_si_bai.get("checks") if isinstance(raw_si_bai, dict) else None
    ) or []:
        if isinstance(row, dict):
            _bind_anchor(anchors, "地分", _branch_rel(row, "seat_branch"))
    return anchors


def validate_relations(value: Mapping[str, object]) -> None:
    for key, expected in dict(
        ruleset_id="jinkou_jingben_relations_v1",
        source_section=QI_SECTION,
    ).items():
        _same_rel(value, key, expected)
    if "transcription_variants" in value:
        _compare_relations(
            value["transcription_variants"],
            [
                dict(
                    branches=["午", "亥"],
                    scan_element="火",
                    transcription_element="水",
                    original_pdf_page=109,
                ),
                dict(
                    branches=["子", "巳"],
                    scan_element="水",
                    transcription_element="火",
                    original_pdf_page=109,
                ),
            ],
        )
    for group in ("si_jue", "si_bai", "calendar"):
        if (
            group in value
            and value[group] is not None
            and not isinstance(value[group], dict)
        ):
            raise ValueError("京本结构关系的已给出分组须为对象")
        group_val = value.get(group)
        if isinstance(group_val, dict):
            validate_queue(group_val, group)
    relation_anchors(value)


def validate_relation_anchors(
    board: Mapping[str, object], *, complete: bool = False
) -> None:
    primary = board.get("relations")
    nodes = [primary] if isinstance(primary, dict) else []
    if complete and not isinstance(primary, dict):
        raise ValueError("完整金口诀须保留京本结构关系")
    anchors: dict[str, object] = {}
    for node in nodes:
        validate_relations(node)
        for key, val in relation_anchors(node).items():
            _bind_anchor(anchors, key, val)
    raw_stars = board.get("branch_stars")
    stars = raw_stars if isinstance(raw_stars, dict) else {}
    _bind_anchor(anchors, "year_branch", stars.get("year_branch"))
    raw_policy = board.get("calendar_policy")
    day = (
        raw_policy.get("effective_day_ganzhi") if isinstance(raw_policy, dict) else None
    )
    if isinstance(day, str) and len(day) == 2:
        _bind_anchor(anchors, "day_branch", day[1])
    for name in ("qi_evidence", "combinations"):
        child = board.get(name)
        if isinstance(child, dict):
            _bind_anchor(anchors, "day_branch", child.get("day_branch"))
    raw_overview = board.get("overview")
    overview = raw_overview if isinstance(raw_overview, dict) else {}
    diurnal_ev = overview.get("diurnal_evidence")
    _bind_anchor(
        anchors,
        "hour_branch",
        diurnal_ev.get("hour_branch") if isinstance(diurnal_ev, dict) else None,
    )
    raw_de = board.get("definition_evidence")
    _bind_anchor(
        anchors,
        "hour_branch",
        raw_de.get("hour_branch") if isinstance(raw_de, dict) else None,
    )
    rows = board.get("rows")
    canonical: list[dict[str, object]] = []
    if (
        isinstance(rows, list)
        and len(rows) == 4
        and all(isinstance(r, dict) for r in rows)
        and [r.get("label") for r in rows] == list(POSITIONS)
    ):
        for i, row in enumerate(rows):
            content = row.get("content")
            if content is None:
                break
            if not isinstance(content, str):
                raise ValueError("京本结构关系须使用本课人元干及三支")
            try:
                phase = (stem_element_text if i == 0 else branch_element_text)(content)
            except (KeyError, TypeError) as exc:
                raise ValueError("京本结构关系须使用本课人元干及三支") from exc
            canonical.append(dict(row, element=phase))
            if i:
                _bind_anchor(anchors, POSITIONS[i], content)
        if len(canonical) == 4:
            for node in nodes:
                si_bai = node.get("si_bai")
                checks = si_bai.get("checks") if isinstance(si_bai, dict) else None
                for c in checks or []:
                    if isinstance(c, dict) and c.get("position") in POSITIONS[:3]:
                        p = POSITIONS.index(c["position"])
                        _same_rel(c, "element", canonical[p]["element"])
    for node in nodes:
        if primary is not None:
            _compare_relations(node, primary)
    year = _branch_rel(anchors, "year_branch")
    day = _branch_rel(anchors, "day_branch")
    hour = _branch_rel(anchors, "hour_branch")
    if len(canonical) != 4 or year is None or day is None or hour is None:
        if complete:
            raise ValueError("完整京本结构关系缺少本课四位或年月日时依据")
        return
    natal_known = False
    natal: object = None
    source: object = None
    for node in nodes:
        si_jue = node.get("si_jue")
        n = si_jue.get("natal") if isinstance(si_jue, dict) else None
        if isinstance(n, dict) and "right_branch" in n:
            if natal_known:
                _compare_relations(n["right_branch"], natal)
            natal_known = True
            natal = n["right_branch"]
            if "input_source" in n:
                if source is not None:
                    _compare_relations(n["input_source"], source)
                source = n["input_source"]
    if complete and not natal_known:
        raise ValueError("完整京本结构关系须保留可空本命支依据")
    expected = structural_relations(
        canonical,
        year_branch=year,
        day_branch=day,
        hour_branch=hour,
        natal_branch=natal if isinstance(natal, str) else None,
        natal_branch_source=source if isinstance(source, str) else None,
    )
    if not natal_known:
        expected["si_jue"].pop("natal")
        expected["si_jue"].pop("unavailable")
    for node in nodes:
        _compare_relations(node, expected, complete=(complete and node is primary))


def require_complete_relations(board: Mapping[str, object]) -> None:
    validate_relation_anchors(board, complete=True)


class JinkouJueCheck(PartialOutput):
    left_position: str | None = None
    right_position: str | None = None
    left_branch: str | None = None
    right_branch: str | None = None
    element: str | None = None
    classification: str | None = None
    matched: bool | None = None
    status: str | None = None
    reason: str | None = None
    original_pdf_page: int | None = None
    basis: str | None = None

    @model_validator(mode="after")
    def named_pair_matches_facts(self) -> JinkouJueCheck:
        validate_absolute_row(self.model_dump(exclude_unset=True))
        return self


class JinkouJue(PartialOutput):
    checks: list[JinkouJueCheck] | None = None
    natal: JinkouNatalAbsolute | None = None
    unavailable: list[JinkouJueCheck] | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def complete_selected_pair_catalog(self) -> JinkouJue:
        validate_queue(self.model_dump(exclude_unset=True), "si_jue")
        return self

    @model_validator(mode="after")
    def missing_natal_is_not_a_false_or_unavailable_known_branch(self) -> JinkouJue:
        if self.natal is None or self.unavailable is None:
            return self
        if "right_branch" not in self.natal.model_fields_set:
            return self
        if self.natal.right_branch is not None:
            if self.unavailable:
                raise ValueError("明确本命支的大绝不能仍列为缺失本命支")
        elif len(self.unavailable) != 1 or any(
            r.matched is not None or r.status != "missing_birth_branch"
            for r in self.unavailable
        ):
            raise ValueError("本命支缺失时大绝必须保留未算状态")
        return self


class JinkouBaiCheck(PartialOutput):
    position: str | None = None
    element: str | None = None
    seat_branch: str | None = None
    bai_branch: str | None = None
    matched: bool | None = None
    original_pdf_page: int | None = None
    basis: str | None = None

    @model_validator(mode="after")
    def selected_phase_matches_seat(self) -> JinkouBaiCheck:
        validate_defeat_row(self.model_dump(exclude_unset=True))
        return self


class JinkouBai(PartialOutput):
    checks: list[JinkouBaiCheck] | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def complete_selected_defeat_catalog(self) -> JinkouBai:
        validate_queue(self.model_dump(exclude_unset=True), "si_bai")
        return self


class JinkouCalendarCheck(PartialOutput):
    rule_id: str | None = None
    name: str | None = None
    position: str | None = None
    branch: str | None = None
    reference_branch: str | None = None
    matched: bool | None = None
    original_pdf_page: int | None = None
    basis: str | None = None

    @model_validator(mode="after")
    def year_day_rule_matches_facts(self) -> JinkouCalendarCheck:
        validate_calendar_row(self.model_dump(exclude_unset=True))
        return self


class JinkouCalendarRelations(PartialOutput):
    year_branch: str | None = None
    day_branch: str | None = None
    checks: list[JinkouCalendarCheck] | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def year_day_references_are_coherent(self) -> JinkouCalendarRelations:
        validate_relations({"calendar": self.model_dump(exclude_unset=True)})
        return self


class JinkouRelationVariant(PartialOutput):
    branches: list[str] | None = None
    scan_element: str | None = None
    transcription_element: str | None = None
    original_pdf_page: int | None = None


class JinkouRelations(PartialOutput):
    ruleset_id: str | None = None
    source_url: str | None = None
    transcription_url: str | None = None
    source_section: str | None = None
    si_jue: JinkouJue | None = None
    si_bai: JinkouBai | None = None
    calendar: JinkouCalendarRelations | None = None
    transcription_variants: list[JinkouRelationVariant] | None = None
    complete_classical_conformance: bool | None = None
    scope: str | None = None

    @field_validator("complete_classical_conformance", mode="before")
    @classmethod
    def no_unearned_full_conformance(cls, value: object) -> bool | None:
        return value if value is None or type(value) is bool else False

    @model_validator(mode="after")
    def source_and_selected_facts_agree(self) -> JinkouRelations:
        validate_relations(self.model_dump(exclude_unset=True))
        return self


class JinkouStrengthWitness(PartialOutput):
    id: str | None = None
    title: str | None = None
    catalog_id: str | None = None
    catalog_url: str | None = None
    scan_url: str | None = None
    source_bytes: int | None = None
    source_pdf_pages: int | None = None
    original_pdf_pages: list[int] | None = None
    symbolic_example_count: int | None = None
    source_kind: Literal["manuscript_scan"] | None = None
    independent_transmission_adjudicated: StrictBool | None = None
    full_volume_collation: StrictBool | None = None


class JinkouStrengthDifference(PartialOutput):
    id: str | None = None
    changed_position: Literal["地分"] | None = None
    original_elements: list[Literal["木", "火", "土", "金", "水"]] | None = None
    primary_elements: list[Literal["木", "火", "土", "金", "水"]] | None = None
    stated_anchor: Literal["土"] | None = None
    stated_god_power: Literal["旺"] | None = None
    original_pdf_page: int | None = None
    primary_pdf_page: int | None = None
    authorial_resolution: None = None


class JinkouStrengthSource(PartialOutput):
    selected_witness: Literal["online_transcription"] | None = None
    derivation: Literal["sufficient_condition_inferred_from_examples"] | None = None
    source_url: str | None = None
    source_section: str | None = None
    scan_source_url: str | None = None
    scan_pdf_pages: list[int] | None = None
    scan_collation_status: Literal["unresolved_diagram_prose_difference"] | None = None
    daily_five_states_adjudicated: Literal[False] | None = None
    complete_classical_acceptance: Literal[False] | None = None
    note: str | None = None
    primary_witness: JinkouStrengthWitness | None = None
    witness_difference: JinkouStrengthDifference | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def source_binding(self) -> JinkouStrengthSource:
        return self


class JinkouUseSource(PartialOutput):
    scan_source_url: str | None = None
    no_control_pdf_page: int | None = None
    no_control_footer_page: int | None = None
    polarity_pdf_pages: list[int] | None = None
    combined_priority_status: Literal["not_adjudicated"] | None = None


def ganzhi_pair_facts(left: str, right: str) -> dict[str, object]:
    pair_match = _STEM_COMBINE_MAP.get(frozenset((left[0], right[0])))
    canonical_pair, el = pair_match if pair_match is not None else (None, None)
    lx, rx = xun_head_for_ganzhi(left), xun_head_for_ganzhi(right)
    return {
        "left_ganzhi": left,
        "right_ganzhi": right,
        "stem_harmony_matched": el is not None,
        "canonical_stem_pair": canonical_pair,
        "candidate_element": el,
        "branch_harmony_matched": SIX_HARMONY_BRANCHES[left[1]] == right[1],
        "both_harmonies_matched": el is not None
        and SIX_HARMONY_BRANCHES[left[1]] == right[1],
        "left_ganzhi_xun_head": lx,
        "right_ganzhi_xun_head": rx,
        "same_ganzhi_xun": lx == rx,
    }


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
    def compound_matches_its_parts(self) -> JinkouDunStemNode:
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
    def summaries_agree(self) -> JinkouGanzhiPairFacts:
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
    id: StemRuleId
    relation: Literal["神干生将干", "将干生神干", "神干克将干", "将干克神干"]
    source_position: Literal["贵神", "将神"] | None = None
    target_position: Literal["贵神", "将神"] | None = None
    phase_relation: Literal["生", "克"] | None = None
    matched: StrictBool
    original_pdf_pages: list[int] | None = None

    @model_validator(mode="after")
    def clause_metadata_matches_identifier(self) -> JinkouStemRule:
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
    relation: StemRelation | None = None
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
    def role_and_summary_consistency(self) -> JinkouStemRelations:
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


def _identity(value: BaseModel, keys: tuple[str, ...]) -> dict[str, object] | None:
    pattern_id = getattr(value, "id", None)
    if not isinstance(pattern_id, str):
        return None
    expected = pattern_identity(pattern_id)
    for key in keys:
        if key in value.model_fields_set and getattr(value, key) != expected[key]:
            raise ValueError("课钤ID所指课名、页码或条件与所选定义不一致")
    return dict(expected)


class JinkouPatternFact(PartialOutput):
    id: str | None = None
    operation: (
        Literal[
            "control",
            "generate",
            "same",
            "equal_branch",
            "clash",
            "combine",
            "stem_combine",
            "trine",
            "trine_controls",
            "three_wonders",
            "same_branches",
            "house",
            "robbery_absent",
            "step",
            "branch_set",
            "branch",
            "phase",
            "xun_kong",
            "si_da_kong",
        ]
        | None
    ) = None
    description: str | None = None
    operands: (
        dict[str, StrictStr | StrictBool | StrictInt | list[StrictStr | None] | None]
        | None
    ) = None
    reference: list[StrictStr] | None = None
    matched: StrictBool | None = None

    @model_validator(mode="after")
    def validate_present_atomic_calculation(self) -> JinkouPatternFact:
        return self


class JinkouPatternRequirement(PartialOutput):
    fact_id: str | None = None
    expected: StrictBool | None = None


class JinkouPatternEvaluation(PartialOutput):
    id: str | None = Field(default=None, pattern=r"^P(?:0[1-9]|[1-5][0-9]|6[0-4])$")
    name: str | None = None
    original_pdf_page: int | None = None
    status: (
        Literal["matched", "not_matched", "unresolved_definition", "input_unavailable"]
        | None
    ) = None
    matched: bool | None = None
    condition: str | None = None
    reason: str | None = None
    condition_groups: list[list[JinkouPatternRequirement]] | None = None

    @model_validator(mode="after")
    def preserve_three_states(self) -> JinkouPatternEvaluation:
        expected = _identity(self, ("name", "original_pdf_page", "condition"))
        if expected is not None:
            if expected["unresolved"]:
                _identity(self, ("reason",))
                if self.matched is not None or self.condition_groups is not None:
                    raise ValueError("未裁定课钤不能取得布尔结论或已裁定表达式")
                if self.status not in (None, "unresolved_definition"):
                    raise ValueError("此课钤ID的原典定义仍未裁定")
            elif self.status == "unresolved_definition":
                raise ValueError("已实现条件的缺项不能改称原典定义未裁定")
        if self.condition_groups is not None:
            if not self.condition_groups or any(not g for g in self.condition_groups):
                raise ValueError("已实现课钤不能用空表达式伪造成立")
            if any(
                not t.fact_id or t.expected is None
                for group in self.condition_groups
                for t in group
            ):
                raise ValueError("课钤条件须保留事实ID与明确要求值")
            if self.status == "unresolved_definition":
                raise ValueError("未裁定义不可以已评估表达式代替")
        if {"status", "matched"} <= self.model_fields_set:
            expected_states: dict[str, bool | None] = {
                "matched": True,
                "not_matched": False,
                "unresolved_definition": None,
                "input_unavailable": None,
            }
            if (
                self.status in expected_states
                and self.matched is not expected_states[self.status]
            ):
                raise ValueError("格局判定状态与matched三态值不一致")
        return self


class JinkouPatternCounts(PartialOutput):
    matched: int | None = Field(default=None, ge=0, le=64)
    not_matched: int | None = Field(default=None, ge=0, le=64)
    unresolved: int | None = Field(default=None, ge=0, le=64)


class JinkouPatternMatch(PartialOutput):
    id: str | None = Field(default=None, pattern=r"^P(?:0[1-9]|[1-5][0-9]|6[0-4])$")
    name: str | None = None
    alias: str | None = None
    original_pdf_page: int | None = None
    reading: str | None = None
    basis: str | None = None
    condition: str | None = None

    @model_validator(mode="after")
    def preserve_selected_identity(self) -> JinkouPatternMatch:
        _identity(self, ("name", "alias", "original_pdf_page", "condition"))
        return self


class JinkouUnresolvedPattern(PartialOutput):
    id: str | None = Field(default=None, pattern=r"^P(?:0[1-9]|[1-5][0-9]|6[0-4])$")
    name: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def preserve_selected_identity(self) -> JinkouUnresolvedPattern:
        expected = _identity(self, ("name",))
        if expected is not None and expected["unresolved"]:
            _identity(self, ("reason",))
        return self


def _distinct_ids(
    items: Sequence[JinkouPatternMatch | JinkouPatternEvaluation], label: str
) -> set[str]:
    ids = [item.id for item in items]
    if any(not isinstance(value, str) for value in ids) or len(set(ids)) != len(ids):
        raise ValueError(f"六十四课钤{label}缺少ID或ID重复")
    return {value for value in ids if isinstance(value, str)}


class JinkouPatterns(PartialOutput):
    ruleset_id: str | None = None
    source_url: str | None = None
    source_section: str | None = None
    catalog_count: int | None = Field(default=None, ge=64, le=64)
    evaluated_rule_count: int | None = Field(default=None, ge=0, le=64)
    condition_logic: Literal["any_of_all_v1"] | None = None
    condition_facts: list[JinkouPatternFact] | None = None
    evaluations: list[JinkouPatternEvaluation] | None = Field(
        default=None, min_length=64, max_length=64
    )
    evaluation_counts: JinkouPatternCounts | None = None
    matched: list[JinkouPatternMatch] | None = None
    unresolved: list[JinkouUnresolvedPattern] | None = None
    day_robbery_branch: str | None = None
    complete_classical_conformance: StrictBool | None = None
    scope: str | None = None

    @field_validator("complete_classical_conformance", mode="before")
    @classmethod
    def partial_excerpt_cannot_certify_full_conformance(
        cls, value: object
    ) -> bool | None:
        return value if value is None or type(value) is bool else False

    @model_validator(mode="after")
    def preserve_ledger_integrity(self) -> JinkouPatterns:
        for key, expected in pattern_metadata().items():
            if key in self.model_fields_set and getattr(self, key) != expected:
                raise ValueError("课钤来源、所选规则及适用范围不一致")
        matched_ids = (
            _distinct_ids(self.matched, "命中列表")
            if self.matched is not None
            else None
        )
        counts = self.evaluation_counts
        if (
            counts is not None
            and matched_ids is not None
            and counts.matched is not None
        ):
            if len(matched_ids) != counts.matched:
                raise ValueError("六十四课钤命中列表与命中计数不一致")
        if self.evaluations is not None:
            ids = _distinct_ids(self.evaluations, "逐条判定")
            if ids != {f"P{i:02}" for i in range(1, 65)}:
                raise ValueError("六十四课钤逐条判定必须保留完整64个ID")
            positive = {row.id for row in self.evaluations if row.matched is True}
            if matched_ids is not None and matched_ids != positive:
                raise ValueError("六十四课钤命中列表与逐条判定不一致")
        return self


def expected_patterns(board: Mapping[str, object]) -> dict[str, object] | None:
    rows = board.get("rows")
    policy = board.get("calendar_policy")
    day = policy.get("effective_day_ganzhi") if isinstance(policy, dict) else None
    if not isinstance(day, str) or not day:
        return None
    if not isinstance(rows, list) or len(rows) != 4:
        return None
    if any(not isinstance(row, dict) or row.get("content") is None for row in rows):
        return None
    raw_overview = board.get("overview")
    overview: dict[str, object] = raw_overview if isinstance(raw_overview, dict) else {}
    raw_de = board.get("definition_evidence")
    de: dict[str, object] = raw_de if isinstance(raw_de, dict) else {}
    diurnal_ev = overview.get("diurnal_evidence")
    raw_hour = de.get("hour_branch") or (
        diurnal_ev.get("hour_branch") if isinstance(diurnal_ev, dict) else None
    )
    hour_branch = raw_hour if isinstance(raw_hour, str) else None
    raw_diurnal = overview.get("is_diurnal")
    is_diurnal = raw_diurnal if isinstance(raw_diurnal, bool) else None
    return patterns_from_symbols(
        rows, day_ganzhi=day, hour_branch=hour_branch, is_diurnal=is_diurnal
    )


def compare_present_patterns(actual: object, expected: object) -> None:
    """Sparse views may omit fields; present statements must still be true."""
    if isinstance(actual, dict) and isinstance(expected, dict):
        for key in actual.keys() & expected.keys():
            compare_present_patterns(actual[key], expected[key])
    elif isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError("课钤判定队列与本课四位不一致")
        if actual and all(
            isinstance(row, dict) and isinstance(row.get("id"), str)
            for row in actual + expected
        ):
            observed = {row["id"]: row for row in actual}
            canonical = {row["id"]: row for row in expected}
            if len(observed) != len(actual) or observed.keys() != canonical.keys():
                raise ValueError("课钤判定ID与本课实际结构不一致")
            for pid, row in observed.items():
                compare_present_patterns(row, canonical[pid])
            return
        for a, e in zip(actual, expected, strict=True):
            compare_present_patterns(a, e)
    elif type(actual) is not type(expected) or actual != expected:
        raise ValueError("课钤判定、条件或原典来源与本课四位及占日不一致")


def validate_pattern_anchors(board: Mapping[str, object]) -> None:
    expected = expected_patterns(board)
    if expected is None:
        return
    if "patterns" in board:
        compare_present_patterns(board["patterns"], expected)


def _require_complete_pattern(actual: object, expected: object) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or expected.keys() - actual.keys():
            raise ValueError("完整金口诀须保留六十四课钤全部可空事实与依据")
        for key, value in expected.items():
            _require_complete_pattern(actual[key], value)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError("完整金口诀须保留六十四课钤完整队列")
        if actual and all(
            isinstance(row, dict) and isinstance(row.get("id"), str)
            for row in actual + expected
        ):
            observed = {row["id"]: row for row in actual}
            canonical = {row["id"]: row for row in expected}
            if len(observed) != len(actual) or observed.keys() != canonical.keys():
                raise ValueError("完整课钤ID队列与本课四位不一致")
            for pid, row in observed.items():
                _require_complete_pattern(row, canonical[pid])
            return
        for a, e in zip(actual, expected, strict=True):
            _require_complete_pattern(a, e)
    else:
        compare_present_patterns(actual, expected)


def require_complete_pattern_anchors(board: Mapping[str, object]) -> None:
    expected = expected_patterns(board)
    if expected is None:
        raise ValueError("完整金口诀须保留课钤的四位原始符号与占日")
    _require_complete_pattern(board.get("patterns"), expected)


def expected_strength_facts(board: Mapping[str, object]) -> dict[str, object]:
    """Use present raw phases as anchors; never insert an omitted view field."""
    rows = board.get("rows")
    if not isinstance(rows, list) or len(rows) != 4:
        return {}
    if not all(isinstance(r, dict) for r in rows):
        return {}
    if [r.get("label") for r in rows] != list(POSITIONS):
        return {}
    canonical: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        phase = row.get("element")
        content = row.get("content")
        if content is not None:
            if not isinstance(content, str):
                raise ValueError("旺衰输入须为人元干及其余三位的地支")
            try:
                anchored = (stem_element_text if index == 0 else branch_element_text)(
                    content
                )
            except (KeyError, TypeError) as exc:
                raise ValueError("旺衰输入须为人元干及其余三位的地支") from exc
            if "element" in row and phase != anchored:
                raise ValueError("旺衰须使用四位实际干支的五行")
            phase = anchored
        if phase is None:
            return {}
        canonical.append(dict(row, element=phase))
    strength = internal_strength(canonical)
    result: dict[str, object] = {"internal_strength": strength}
    for row in canonical:
        label = row["label"]
        if isinstance(label, str):
            row["internal_power"] = strength["powers"][label]
    needed = ("content", "seasonal_power", "xun_kong", "si_da_kong", "month_break")
    if all(all(k in r and r[k] is not None for k in needed) for r in canonical):
        for i, row in enumerate(canonical):
            sequence = HEAVENLY_STEMS if i == 0 else EARTHLY_BRANCHES
            content = row["content"]
            if isinstance(content, str):
                row["polarity"] = "阳" if sequence.index(content) % 2 == 0 else "阴"
        position, _, _ = _jinkou_pick_use_position(canonical)
        result["use_evidence"] = use_evidence(
            canonical, strength, polarity_position=position
        )
    qi = board.get("qi_evidence")
    if (
        isinstance(qi, dict)
        and qi.get("month_building_branch") is not None
        and qi.get("day_branch") is not None
        and all(r.get("content") is not None for r in canonical)
    ):
        result["qi_evidence"] = build_jinkou_qi(
            canonical,
            month_branch=qi["month_building_branch"],
            day_branch=qi["day_branch"],
        )
    return result


def validate_seasonal_evidence(board: Mapping[str, object]) -> None:
    """Bind available facts without manufacturing a projected-out month."""
    months: list[str] = []
    for name, key in (
        ("qi_evidence", "month_building_branch"),
        ("combinations", "month_branch"),
    ):
        obj = board.get(name)
        if isinstance(obj, dict):
            val = obj.get(key)
            if isinstance(val, str):
                months.append(val)
    if not months:
        return
    month = months[0]
    basis = seasonal_power_basis(month)
    if any(other != month for other in months):
        raise ValueError("同课四季旺衰的月建依据不一致")
    overview = board.get("overview")
    if isinstance(overview, dict) and overview.get("power_basis") is not None:
        compare_present(overview["power_basis"], basis)
    rows = board.get("rows")
    if not isinstance(rows, list):
        return
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        phase = row.get("element")
        content = row.get("content")
        position = row.get("label") or (POSITIONS[index] if len(rows) == 4 else None)
        if isinstance(content, str) and position in POSITIONS:
            try:
                anchored = (
                    stem_element_text if position == "人元" else branch_element_text
                )(content)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("四季旺衰须使用四位实际干支") from exc
            if phase is not None:
                compare_present(phase, anchored)
            phase = anchored
        if not isinstance(phase, str):
            continue
        power = seasonal_power(month, phase)
        if row.get("seasonal_power") is not None:
            compare_present(row["seasonal_power"], power)


def validate_strength_evidence(
    board: Mapping[str, object], *, expected: Mapping[str, object] | None = None
) -> None:
    validate_course_qi(board)
    validate_seasonal_evidence(board)
    if expected is None:
        expected = expected_strength_facts(board)
    strength = expected.get("internal_strength")
    rows = board.get("rows")
    if isinstance(strength, dict) and isinstance(rows, list):
        powers = strength.get("powers")
        if isinstance(powers, dict):
            for row in rows:
                if isinstance(row, dict) and "internal_power" in row:
                    compare_present(row["internal_power"], powers[row["label"]])
    for key, value in expected.items():
        if key in board:
            compare_present(board[key], value, key)


def _require_present_strength(actual: object, expected: object) -> None:
    """Full output retains nullable facts; views are not passed through this gate."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(expected) - set(actual):
            raise ValueError("完整金口诀缺少旺衰或用位依据字段")
        for key, value in expected.items():
            _require_present_strength(actual[key], value)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError("完整金口诀缺少旺衰或用位依据条目")
        for a, b in zip(actual, expected):
            _require_present_strength(a, b)
    elif expected is not None and actual is None:
        raise ValueError("完整金口诀不可将已知旺衰或取用依据置空")
    elif isinstance(expected, str) and (
        not isinstance(actual, str) or not actual.strip()
    ):
        raise ValueError("完整金口诀不可将旺衰或取用说明置空")


def require_complete_strength_evidence(board: Mapping[str, object]) -> None:
    rows = board.get("rows")
    if not isinstance(rows, list) or len(rows) != 4:
        raise ValueError("完整金口诀须保留四位旺衰的输入依据")
    for position, row in zip(POSITIONS, rows):
        if (
            not isinstance(row, dict)
            or row.get("label") != position
            or any(k not in row for k in ROW_FIELDS)
            or any(row[k] is None for k in ROW_FIELDS if k != "internal_power")
        ):
            raise ValueError("完整金口诀须保留四位旺衰的输入依据")
    expected = expected_strength_facts(board)
    if set(expected) != EXPECTED_EVIDENCE_KEYS:
        raise ValueError("完整金口诀须保留月建日辰与阴阳用位依据")
    qi_expected = expected["qi_evidence"]
    if not isinstance(qi_expected, dict):
        raise ValueError("完整金口诀须保留月建日辰与阴阳用位依据")
    basis = seasonal_power_basis(qi_expected["month_building_branch"])
    overview = board.get("overview")
    if not isinstance(overview, dict) or overview.get("power_basis") != basis:
        raise ValueError("完整金口诀须保留与实际月建一致的四季旺衰说明")
    for key, value in expected.items():
        _require_present_strength(board.get(key), value)
    validate_strength_evidence(board, expected=expected)


class JinkouGuishen(BranchName):
    start_branch: str | None = None
    earth_branch: str | None = None
    intrinsic_ganzhi: str | None = None
    direction: str | None = None


class JinkouOverview(PartialOutput):
    board_style: str | None = None
    board_style_detail: str | None = None
    di_fen: str | None = None
    gender: str | None = None
    guishen: JinkouGuishen | None = None
    kongwang: str | None = None
    month_general: BranchName | None = Field(
        default=None,
        description="依民用瞬间中气确定的月将本位，未移到地分；yuejiang另记落地分后的将神。",
    )
    si_da_kong: str | None = None
    transmission_method: str | None = None
    use_position: str | None = None
    use_position_basis: str | None = None
    yuejiang: BranchName | None = Field(
        default=None,
        description="月将加时后落在地分的将神，对应将神行；与month_general月将本位分开。",
    )
    di_fen_source: str | None = None
    xun_head: str | None = None
    power_basis: str | None = None
    diurnal_basis: str | None = None
    is_diurnal: bool | None = None
    diurnal_evidence: RenDiurnalEvidence | None = None


class JinkouRow(PartialOutput):
    content: str | None = None
    element: str | None = None
    label: str | None = None
    seasonal_power: str | None = Field(
        default=None, description="按月建约定的四季旺衰，与位内旺衰分开。"
    )
    internal_power: str | None = Field(
        default=None,
        description="按四位课内旺神所得旺衰；多个旺神候选未裁定时为 null。",
    )
    shenjiang: str | None = None
    polarity: str | None = None
    dun_stem: str | None = None
    intrinsic_ganzhi: str | None = None
    xun_kong: bool | None = None
    si_da_kong: bool | None = None
    month_break: bool | None = None
    is_use: bool | None = None


class JinkouMotion(PartialOutput):
    name: str | None = None
    source_position: str | None = None
    target_position: str | None = None
    relation: str | None = None
    source_section: str | None = None
    basis: str | None = None
    empty_positions: list[str] | None = None


class JinkouInternalStrength(PartialOutput):
    method: str | None = None
    status: str | None = None
    anchor_element: str | None = None
    candidate_elements: list[str] | None = None
    candidate_positions: list[str] | None = None
    has_control: bool | None = None
    relations: list[JinkouInternalRelation] | None = None
    powers: dict[str, str | None] | None = None
    basis: str | None = None
    source_evidence: JinkouStrengthSource | None = None
    scope: str | None = None


class JinkouUseEvidence(PartialOutput):
    polarity_position: str | None = None
    subject_position: str | None = None
    controlled_by: list[str] | None = None
    xun_kong: bool | None = None
    si_da_kong: bool | None = None
    month_break: bool | None = None
    seasonal_power: str | None = None
    internal_power: str | None = None
    no_control_principle_applies: bool | None = None
    internal_strength_candidates: list[str] | None = None
    comprehensive_position: None = None
    source_evidence: JinkouUseSource | None = None
    status: str | None = None
    basis: str | None = None
    scope: str | None = None


class LabelValue(PartialOutput):
    label: str | None = None
    value: str | None = None


class JinkouTrineMember(PartialOutput):
    position: str | None = None
    branch: str | None = None
    day_clash: bool | None = None
    month_break: bool | None = None
    xun_kong: bool | None = None
    si_da_kong: bool | None = None


class JinkouTrineStem(PartialOutput):
    position: str | None = None
    stem: str | None = None
    element: str | None = None
    trine_element: str | None = None
    explicit_fire_clause: bool | None = None


class JinkouTrine(PartialOutput):
    name: str | None = None
    partial_name: str | None = None
    element: str | None = None
    branches: list[str] | None = None
    present_branches: list[str] | None = None
    missing_branches: list[str] | None = None
    structural_status: str | None = None
    human_stem_relation: str | None = None
    member_conditions: list[JinkouTrineMember] | None = None
    controlling_dun_stems: list[JinkouTrineStem] | None = None
    source_listed_disruptors: list[str] | None = None
    disruptor_application: str | None = None
    du_he: None = None
    transformation_confirmed: None = None
    waiting_branch: str | None = None
    calendar_candidates: None = None
    original_pdf_pages: list[int] | None = None
    basis: str | None = None


class JinkouTrineVariant(PartialOutput):
    original_pdf_page: int | None = None
    scan_reading: str | None = None
    transcription_reading: str | None = None


class JinkouCombinations(PartialOutput):
    ruleset_id: str | None = None
    source_url: str | None = None
    source_section: str | None = None
    day_branch: str | None = None
    month_branch: str | None = None
    trines: list[JinkouTrine] | None = None
    textual_variants: list[JinkouTrineVariant] | None = None
    scope: str | None = None


class JinkouCourse(PartialOutput):
    engine: str | None = None
    overview: JinkouOverview | None = None
    rows: list[JinkouRow] | None = None
    shensha: list[LabelValue] | None = None
    motions: list[JinkouMotion] | None = None
    internal_strength: JinkouInternalStrength | None = None
    qi_evidence: JinkouQiEvidence | None = None
    position_interactions: JinkouPositionInteractions | None = None
    stem_relations: JinkouStemRelations | None = None
    definition_evidence: JinkouDefinitionEvidence | None = None
    combinations: JinkouCombinations | None = None
    patterns: JinkouPatterns | None = None
    use_evidence: JinkouUseEvidence | None = None
    relations: JinkouRelations | None = None
    branch_stars: JinkouBranchStars | None = None
    branch_breaks: JinkouBranchBreaks | None = None
    calendar_policy: RenCalendarPolicy | None = None
    ruleset: RenRuleset | None = None

    @model_validator(mode="after")
    def breaks_follow_this_course(self) -> JinkouCourse:
        align_branch_breaks(self)
        return self

    @model_validator(mode="after")
    def relations_follow_this_course(self) -> JinkouCourse:
        validate_relation_anchors(self.model_dump(exclude_unset=True))
        return self

    @model_validator(mode="after")
    def patterns_follow_this_course(self) -> JinkouCourse:
        validate_pattern_anchors(self.model_dump(exclude_unset=True))
        return self

    @model_validator(mode="after")
    def stars_follow_this_board(self) -> JinkouCourse:
        align_branch_stars(self.model_dump(exclude_unset=True))
        return self

    @model_validator(mode="after")
    def strength_and_use_follow_this_board(self, info: ValidationInfo) -> JinkouCourse:
        if not (info.context and info.context.get("full_result")):
            validate_strength_evidence(self.model_dump(exclude_unset=True))
        return self

    @model_validator(mode="after")
    def natal_relation_uses_this_general(self) -> JinkouCourse:
        primary = (
            self.relations.si_jue.natal
            if self.relations is not None and self.relations.si_jue is not None
            else None
        )
        nodes = [primary] if primary is not None else []
        row = next((r for r in self.rows or [] if r.label == "将神"), None)
        if row is not None and row.content is not None:
            for natal in nodes:
                if (
                    "left_branch" in natal.model_fields_set
                    and natal.left_branch != row.content
                ):
                    raise ValueError("将命大绝须使用同次四位的将神支")
        return self

    @model_validator(mode="after")
    def definition_facts_agree_with_positions(self) -> JinkouCourse:
        if (
            self.definition_evidence is None
            or self.rows is None
            or self.overview is None
        ):
            return self
        if self.stem_relations is None or self.stem_relations.day_stem is None:
            return self
        if self.overview.is_diurnal is None:
            return self
        actual = self.definition_evidence
        if actual.hour_branch is None:
            return self
        rows = [r.model_dump(exclude_unset=True) for r in self.rows]
        needed = ("label", "content", "element")
        if len(rows) != 4 or any(any(k not in r for k in needed) for r in rows):
            return self
        if not rows[1].get("intrinsic_ganzhi"):
            return self

        expected = definition_evidence(
            day_stem=self.stem_relations.day_stem,
            hour_branch=actual.hour_branch,
            is_diurnal=self.overview.is_diurnal,
            rows=rows,
        )
        compare_present_definition_facts(
            actual.model_dump(exclude_unset=True), expected
        )
        return self

    @model_validator(mode="after")
    def stems_agree_with_four_positions(self) -> JinkouCourse:
        if self.stem_relations is None or self.rows is None:
            return self
        by_label = {row.label: row for row in self.rows if row.label is not None}
        for label, node in (
            ("贵神", self.stem_relations.god),
            ("将神", self.stem_relations.general),
        ):
            row = by_label.get(label)
            if row is None or node is None:
                continue
            for node_field, row_field in (
                ("branch", "content"),
                ("name", "shenjiang"),
                ("dun_stem", "dun_stem"),
                ("branch_element", "element"),
                ("branch_xun_kong", "xun_kong"),
                ("branch_si_da_kong", "si_da_kong"),
            ):
                a, b = getattr(node, node_field), getattr(row, row_field)
                if a is not None and b is not None and a != b:
                    raise ValueError("遁干证据与原四位的同次事实不一致")
        god = by_label.get("贵神")
        intrinsic = self.stem_relations.guishen_intrinsic_ganzhi
        if (
            god is not None
            and god.intrinsic_ganzhi is not None
            and intrinsic is not None
            and god.intrinsic_ganzhi != intrinsic
        ):
            raise ValueError("贵神固有干支与遁干证据不一致")
        return self


def shared_compare(a: object, b: object) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a.keys() & b.keys():
            shared_compare(a[k], b[k])
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            raise ValueError("本命另课须保留同次分析队列")
        for x, y in zip(a, b):
            shared_compare(x, y)
    elif type(a) is not type(b) or a != b:
        raise ValueError("本命另课与本次占时、本命来源或课盘依据不一致")


def expected_natal_metadata(value: Mapping[str, object]) -> dict[str, object] | None:
    if not {"birth_year_ganzhi", "natal_branch", "natal_branch_source"} <= value.keys():
        return None
    source = value["natal_branch_source"]
    if not isinstance(source, str) or source not in {
        "explicit_natal_branch",
        "explicit_birth_year_ganzhi",
        "missing",
    }:
        raise ValueError("本命另课来源无效")
    birth_year_ganzhi = value["birth_year_ganzhi"]
    natal_branch = value["natal_branch"]
    return natal_course_metadata(
        birth_year_ganzhi if isinstance(birth_year_ganzhi, str) else None,
        (
            natal_branch
            if source == "explicit_natal_branch" and isinstance(natal_branch, str)
            else None
        ),
    )


def validate_natal_course(parent: Mapping[str, object]) -> None:
    value = parent.get("natal_course")
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError("本命另课须为资料对象")
    expected = expected_natal_metadata(value)
    if expected is not None:
        compare_selection({k: v for k, v in value.items() if k != "course"}, expected)
    child = value.get("course")
    if child is not None and not isinstance(child, dict):
        raise ValueError("本命另课课盘须为对象或未知")
    if (
        "status" in value
        and "course" in value
        and (child is not None) != (value["status"] == "calculated")
    ):
        raise ValueError("本命未知不能生成另课，明确已算不能丢失另课")
    annual = parent.get("year_fate")
    if isinstance(annual, dict):
        shared_compare(
            value,
            {
                k: annual[k]
                for k in ["birth_year_ganzhi", "natal_branch", "natal_branch_source"]
                if k in annual
            },
        )
    boards: list[Mapping[str, object]] = [parent]
    if isinstance(child, dict):
        boards.append(child)
    for board in boards:
        raw_rel = board.get("relations")
        si_jue = raw_rel.get("si_jue") if isinstance(raw_rel, dict) else None
        natal = si_jue.get("natal") if isinstance(si_jue, dict) else None
        if isinstance(natal, dict):
            if "right_branch" in natal and "natal_branch" in value:
                shared_compare(value["natal_branch"], natal["right_branch"])
            if "input_source" in natal and "natal_branch_source" in value:
                shared_compare(
                    (
                        "not_provided"
                        if value["natal_branch_source"] == "missing"
                        else value["natal_branch_source"]
                    ),
                    natal["input_source"],
                )
    if isinstance(child, dict):
        if any(k in child for k in ["year_fate", "natal_course"]):
            raise ValueError("本命另课不得递归另起年命课")
        overview = child.get("overview")
        if isinstance(overview, dict):
            if "di_fen" in overview and "natal_branch" in value:
                shared_compare(overview["di_fen"], value["natal_branch"])
            if "di_fen_source" in overview:
                compare_selection(
                    overview["di_fen_source"], "natal_branch_derived_course"
                )
            main = parent.get("overview")
            if isinstance(main, dict):
                shared_compare(
                    overview,
                    {
                        k: main[k]
                        for k in [
                            "month_general",
                            "is_diurnal",
                            "diurnal_basis",
                            "diurnal_evidence",
                        ]
                        if k in main
                    },
                )
        if "calendar_policy" in parent and "calendar_policy" in child:
            shared_compare(parent["calendar_policy"], child["calendar_policy"])


def require_complete_natal_course(parent: Mapping[str, object]) -> None:
    value = parent.get("natal_course")
    if not isinstance(value, dict):
        raise ValueError("完整金口诀须保留可空的本命另课资料")
    expected = expected_natal_metadata(value)
    if expected is None or set(expected) | {"course"} != set(value):
        raise ValueError("完整本命另课缺少输入、来源或范围说明")
    validate_natal_course(parent)
    course = value["course"]
    if isinstance(course, dict):
        overview = course.get("overview")
        overview_dict = overview if isinstance(overview, dict) else {}
        if not {"di_fen", "di_fen_source"} <= overview_dict.keys():
            raise ValueError("完整本命另课须保留派生地分")


class JinkouYearFate(PartialOutput):
    method_id: Literal["jingben_birth_xun_year_fate_v1"] | None = None
    status: Literal["missing_inputs", "calculated"] | None = None
    birth_year_ganzhi: str | None = None
    birth_xun: str | None = None
    gender: str | None = None
    age_ordinal: int | None = Field(default=None, strict=True, ge=1, le=150)
    age_basis: Literal["explicit_one_based_ordinal"] | None = None
    course_basis: Literal["annual_branch_as_ground_reading"] | None = None
    course_ground_is_observed: Literal[False] | None = None
    start_ganzhi: str | None = None
    direction: Literal["顺", "逆"] | None = None
    ganzhi: str | None = None
    branch: str | None = None
    missing_inputs: list[str] | None = None
    natal_branch: str | None = None
    natal_branch_source: (
        Literal["explicit_natal_branch", "explicit_birth_year_ganzhi", "missing"] | None
    ) = None
    age_boundary_classically_verified: Literal[False] | None = None
    birth_year_calendar_boundary_verified: Literal[False] | None = None
    comprehensive_year_fate_adjudicated: Literal[False] | None = None
    source_url: str | None = None
    source_section: str | None = None
    original_pdf_pages: list[int] | None = None
    relation_adjudication: Literal["unresolved_course_stem_reference"] | None = None
    relation_note: str | None = None
    scope: str | None = None
    course: JinkouCourse | None = None

    @field_validator(
        "age_boundary_classically_verified",
        "birth_year_calendar_boundary_verified",
        "comprehensive_year_fate_adjudicated",
        "course_ground_is_observed",
        mode="before",
    )
    @classmethod
    def no_unverified_year_fate_certification(cls, value: object) -> bool | None:
        return value if value is None or type(value) is bool else False

    @model_validator(mode="after")
    def ordinal_and_course_agree(self) -> JinkouYearFate:
        if {"birth_year_ganzhi", "age_ordinal", "gender"} <= self.model_fields_set:
            expected = ordinal_year_fate(
                birth_year_ganzhi=self.birth_year_ganzhi,
                age=self.age_ordinal,
                gender=self.gender,
            )
            actual = self.model_dump(exclude_unset=True)
            if any(actual[k] != expected[k] for k in actual.keys() & expected.keys()):
                raise ValueError("京本行年事实与所给出生年干支、岁序及性别不一致")
        if (
            self.birth_year_ganzhi is not None
            and "natal_branch" in self.model_fields_set
        ):
            if (
                confirmed_natal_branch(
                    self.birth_year_ganzhi, self.natal_branch, self.age_ordinal
                )
                != self.natal_branch
            ):
                raise ValueError("行年层的本命支须来自明确出生年支")
        if "course" in self.model_fields_set and self.status is not None:
            if (self.course is not None) != (self.status == "calculated"):
                raise ValueError("资料缺失不能返回已算行年课，已算行年不能丢失课盘")
        if self.course is not None:
            if (
                self.course.overview is not None
                and self.course.overview.di_fen is not None
                and self.branch is not None
            ):
                if self.course.overview.di_fen != self.branch:
                    raise ValueError("行年课的地分必须是本次行年支")
            if (
                self.course.overview is not None
                and self.course.overview.di_fen_source is not None
                and self.course.overview.di_fen_source != "annual_branch_derived_course"
            ):
                raise ValueError("行年另课地分来自行年支，不是已观测或直接指定方位")
            if (self.course.model_extra or {}).get("year_fate") is not None:
                raise ValueError("行年另课不递归产生另一层行年")
        return self


class JinkouNatalCourse(PartialOutput):
    method_id: Literal["jingben_natal_branch_course_v1"] | None = None
    status: Literal["missing_inputs", "calculated"] | None = None
    birth_year_ganzhi: str | None = None
    natal_branch: str | None = None
    natal_branch_source: (
        Literal["explicit_natal_branch", "explicit_birth_year_ganzhi", "missing"] | None
    ) = None
    missing_inputs: list[str] | None = None
    course_basis: Literal["natal_branch_as_ground_reading"] | None = None
    course_ground_is_observed: Literal[False] | None = None
    birth_year_calendar_boundary_verified: Literal[False] | None = None
    comprehensive_judgement: None = None
    source_url: str | None = None
    source_section: str | None = None
    original_pdf_pages: list[int] | None = None
    basis: str | None = None
    scope: str | None = None
    course: JinkouCourse | None = None

    @field_validator(
        "course_ground_is_observed",
        "birth_year_calendar_boundary_verified",
        mode="before",
    )
    @classmethod
    def no_unverified_natal_certification(cls, value: object) -> bool | None:
        return value if value is None or type(value) is bool else False

    @model_validator(mode="after")
    def natal_course_follows_confirmed_input(self) -> JinkouNatalCourse:
        validate_natal_course({"natal_course": self.model_dump(exclude_unset=True)})
        return self


class Jinkou(JinkouCourse):
    year_fate: JinkouYearFate | None = None
    natal_course: JinkouNatalCourse | None = None
    birth_year_derivation: dict[str, object] | None = None

    @model_validator(mode="after")
    def natal_course_keeps_analysis_facts(self) -> Jinkou:
        validate_natal_course(self.model_dump(exclude_unset=True))
        return self

    @model_validator(mode="after")
    def annual_course_keeps_analysis_facts(self) -> Jinkou:
        if self.year_fate is not None:
            boards = [self, self.year_fate.course]
            for board in boards:
                natal = (
                    board.relations.si_jue.natal
                    if board is not None
                    and board.relations is not None
                    and board.relations.si_jue is not None
                    else None
                )
                if natal is None:
                    continue
                if (
                    "natal_branch" in self.year_fate.model_fields_set
                    and "right_branch" in natal.model_fields_set
                    and self.year_fate.natal_branch != natal.right_branch
                ):
                    raise ValueError("行年与本课大绝须使用同一明确本命支")
                if (
                    "natal_branch_source" in self.year_fate.model_fields_set
                    and "input_source" in natal.model_fields_set
                ):
                    expected_source = (
                        "not_provided"
                        if self.year_fate.natal_branch_source == "missing"
                        else self.year_fate.natal_branch_source
                    )
                    if natal.input_source != expected_source:
                        raise ValueError("本命支来源须与明确输入事实一致")
        if self.year_fate is None or self.year_fate.course is None:
            return self
        child = self.year_fate.course

        def agree(a: object, b: object) -> bool:
            if isinstance(a, dict) and isinstance(b, dict):
                return all(agree(a[k], b[k]) for k in a.keys() & b.keys())
            return bool(a == b)

        if self.calendar_policy is not None and child.calendar_policy is not None:
            if not agree(
                self.calendar_policy.model_dump(exclude_unset=True),
                child.calendar_policy.model_dump(exclude_unset=True),
            ):
                raise ValueError("行年另课须保留同次分析历法口径")
        if self.overview is not None and child.overview is not None:
            a = self.overview.model_dump(exclude_unset=True)
            b = child.overview.model_dump(exclude_unset=True)
            for key in (
                "month_general",
                "is_diurnal",
                "diurnal_basis",
                "diurnal_evidence",
            ):
                if key in a and key in b and not agree(a[key], b[key]):
                    raise ValueError("行年另课须保留本次月将与显式昼夜选择")
        return self
