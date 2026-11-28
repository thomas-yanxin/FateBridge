"""Output contracts and validators for Da Liu Ren."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    Field,
    JsonValue,
    StrictBool,
    StrictInt,
    ValidationInfo,
    field_validator,
    model_validator,
)

from fatebridge.core.contracts.base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.common import BranchName, Object
from fatebridge.core.metaphysics.common import liuqin_against_day
from fatebridge.core.metaphysics.hko_term_dates import published_date_reference
from fatebridge.core.metaphysics.liureng.board import derive_selection
from fatebridge.core.metaphysics.liureng.stars import (
    GOD_ELEMENTS,
    MONTH_PARTITION,
    POWERS,
    STEM_HOUSES,
    apply_year_fate_emptiness,
    branch_pair_facts,
    branch_relations,
    cross_harmony,
    cross_harmony_metadata,
    day_placement_patterns,
    emptiness_evidence,
    empty_condition,
    god_yin_spirits,
    life_stage_cycle,
    nominal_seasonal_evidence,
    nominal_seasonal_metadata,
    placement_metadata,
    seasonal_evidence,
    seasonal_metadata,
)
from fatebridge.core.metaphysics.liureng.transmissions import (
    RULE_NAMES,
    course_conditions,
    ordered_transmission_patterns,
    phase_relation,
    transmission_progression,
    transmission_relations,
)
from fatebridge.utils.civil_time import ZonedCalendar
from fatebridge.utils.data import (
    EARTHLY_BRANCHES,
    SEXAGENARY_INDEX,
    branch_element_text,
    kongwang_for_ganzhi,
    stem_element_text,
    xun_head_for_ganzhi,
)

BRANCHES = EARTHLY_BRANCHES

Branch = Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
AuthorityRole = Literal["太岁", "月建", "月将"]
Element = Literal["木", "火", "土", "金", "水"]
Power = Literal["旺", "相", "休", "囚", "死"]
Phase = Literal["木", "火", "土", "金", "水"]
God = Literal[
    "贵人",
    "螣蛇",
    "朱雀",
    "六合",
    "勾陈",
    "青龙",
    "天空",
    "白虎",
    "太常",
    "玄武",
    "太阴",
    "天后",
]
LiurenLifeStage = Literal[
    "长生",
    "沐浴",
    "冠带",
    "临官",
    "帝旺",
    "衰",
    "病",
    "死",
    "墓",
    "绝",
    "胎",
    "养",
]
PhaseRelation = Literal[
    "branch_generates_stem",
    "stem_generates_branch",
    "branch_controls_stem",
    "stem_controls_branch",
    "same_element",
]
MatchedRuleId = Literal[
    "D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "D09", "D10"
]

_ELEMENTS: dict[str, Element] = {
    "木": "木",
    "火": "火",
    "土": "土",
    "金": "金",
    "水": "水",
}
_GOD_YIN_INPUTS = (
    "day_ganzhi",
    "month_branch",
    "is_diurnal",
    "guiren_profile",
    "sky_by_earth",
    "god_by_sky",
    "lesson_uppers",
    "transmission_branches",
    "year_fate_uppers",
)
_TRINE_COMPONENTS = {
    "旺": "得势",
    "相": "将来",
    "休": "既往",
    "囚": "失时",
    "死": "失时",
}


def _get(obj: object, key: str) -> object:
    if obj is None:
        return None
    return obj.get(key) if isinstance(obj, Mapping) else getattr(obj, key, None)


def _get_dict(obj: object, key: str) -> Mapping[str, object]:
    val = _get(obj, key)
    return val if isinstance(val, Mapping) else {}


def _get_str(obj: object, key: str) -> str | None:
    val = _get(obj, key)
    return val if isinstance(val, str) else None


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def compare_present_branches(actual: object, expected: object) -> None:
    if isinstance(actual, Mapping) and isinstance(expected, Mapping):
        for k, v in actual.items():
            if k in expected:
                compare_present_branches(v, expected[k])
    elif isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError("六壬支位关系队列缺项或重复")
        for a, b in zip(actual, expected):
            compare_present_branches(a, b)
    elif actual != expected:
        raise ValueError("六壬支位关系与同次支位或并存关系不一致")


def compare_present_empty(actual: object, expected: object) -> None:
    if isinstance(actual, Mapping) and isinstance(expected, Mapping):
        for key, value in actual.items():
            if key in expected:
                compare_present_empty(value, expected[key])
    elif isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError("六壬空亡依据队列与本课不一致")
        for left, right in zip(actual, expected):
            compare_present_empty(left, right)
    elif actual != expected:
        raise ValueError("六壬空亡依据与本课四柱、月将或天地盘不一致")


def compare_present_relations(actual: object, expected: object) -> None:
    if isinstance(actual, Mapping) and isinstance(expected, Mapping):
        for k, v in actual.items():
            if k in expected:
                compare_present_relations(v, expected[k])
    elif isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError("三传关系的队列与本课不一致")
        for a, b in zip(actual, expected):
            compare_present_relations(a, b)
    elif actual != expected:
        raise ValueError("三传关系与本课日干支、支神、天将或四课不一致")


def compare_selection(actual: object, expected: object) -> None:
    """Check present facts without manufacturing projected-out keys."""
    if isinstance(actual, Mapping) and isinstance(expected, Mapping):
        if actual.keys() - expected.keys():
            raise ValueError("九宗门证据含本次推导中不存在的字段")
        for key in actual.keys() & expected.keys():
            compare_selection(actual[key], expected[key])
    elif isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError("九宗门证据队列与同次计算不一致")
        for a, e in zip(actual, expected):
            compare_selection(a, e)
    elif type(actual) is not type(expected) or actual != expected:
        raise ValueError("九宗门选课、三传、细名或推导轨迹与日干支天地盘不一致")


def layout_compatibility_basis() -> dict[str, str]:
    return {"ruleset_id": "tanyuan_supported_noble_layout_necessity_v1"}


class RenCivilClockResolution(PartialOutput):
    method: str | None = None
    timezone: str | None = None
    input_utc_offset: str | None = None
    resolved_utc_offset: str | None = None
    wall_datetime: str | None = None
    was_ambiguous: bool | None = None
    fold: int | None = Field(default=None, ge=0, le=1)
    instant_utc: str | None = None
    timezone_rules: dict[str, str] | None = None
    timezone_source: (
        Literal["birth_timezone", "birth_place", "default_timezone"] | None
    ) = None
    timezone_resolved_place: str | None = None
    timezone_assumed: bool | None = None
    timezone_resolution_advisory: str | None = None


class RenRunyearAgeCalendar(PartialOutput):
    policy: Literal["one_timezone_lunar_year_age_v1"] | None = None
    timezone: str | None = None
    analysis_civil_datetime: str | None = None
    birth_lunar_year: int | None = None
    analysis_lunar_year: int | None = None
    year_boundary: Literal["正月初一00:00"] | None = None
    scope: str | None = None


class RenPublishedDateReference(PartialOutput):
    reference_id: Literal["hko_published_term_dates_v1"] | None = None
    term_name: str | None = None
    hko_year: StrictInt | None = None
    comparison_clock: Literal["fixed_UTC+08:00"] | None = None
    computed_hko_moment: str | None = None
    computed_hko_date: str | None = None
    published_date: str | None = None
    dates_equal: StrictBool | None = None
    status: Literal["date_match", "date_mismatch", "outside_published_range"] | None = (
        None
    )
    source_url: str | None = None
    comparison_scope: Literal["published_day_only_not_crossing_instant"] | None = None
    instant_accuracy_certified: Literal[False] | None = None

    @model_validator(mode="before")
    @classmethod
    def strict_false(cls, value: JsonValue | BaseModel) -> JsonValue | BaseModel:
        if (
            isinstance(value, dict)
            and value.get("instant_accuracy_certified") is not None
            and value["instant_accuracy_certified"] is not False
        ):
            raise ValueError("官方逐日表不认证交气瞬间精度")
        return value

    @model_validator(mode="after")
    def matches_own_context(self) -> "RenPublishedDateReference":
        if self.term_name is not None and self.computed_hko_moment is not None:
            compare_present_branches(
                self.model_dump(exclude_unset=True),
                published_date_reference(
                    self.term_name,
                    ZonedCalendar.from_isoformat(self.computed_hko_moment),
                ),
            )
        return self


def align_published_date(dependency: object) -> None:
    ref = _get(dependency, "published_date_reference")
    name = _get(dependency, "name")
    moment = _get(dependency, "civil_moment")
    if ref is not None and isinstance(name, str) and isinstance(moment, str):
        value = (
            ref.model_dump(exclude_unset=True)
            if isinstance(ref, RenPublishedDateReference)
            else ref
        )
        compare_present_branches(
            value, published_date_reference(name, ZonedCalendar.from_isoformat(moment))
        )


def require_complete_published_dates(policy: object) -> None:
    if not isinstance(policy, Mapping) or policy.get("mode") != "civil_instant_checked":
        raise ValueError("完整壬课输出缺少交气日期依据")
    rows = policy.get("solar_term_dependencies")
    if rows is None:
        return
    if (
        not isinstance(rows, list)
        or not all(isinstance(r, Mapping) for r in rows)
        or [r.get("role") for r in rows]
        != [
            "current_term",
            "next_term",
            "month_start",
            "next_month_start",
            "year_boundary",
        ]
    ):
        raise ValueError("完整壬课输出缺少五项实际交气依赖")
    for row in rows:
        name = row.get("name")
        moment = row.get("civil_moment")
        if not isinstance(name, str) or not isinstance(moment, str):
            raise ValueError("完整交气日期对照缺少同次节气与瞬间")
        expected = published_date_reference(name, ZonedCalendar.from_isoformat(moment))
        ref = row.get("published_date_reference")
        if isinstance(ref, dict):
            RenPublishedDateReference.model_validate(ref)
        if ref != expected:
            raise ValueError("完整交气官方日期对照缺项或与本次计算不符")


class LiurenAuxiliaryStar(PartialOutput):
    id: str | None = None
    name: str | None = None
    category: str | None = None
    source_token: str | None = None
    branch: Branch | None = None
    original_pdf_pages: list[int] | None = None
    earth_branch: Branch | None = None
    god: str | None = None
    dun_stem: (
        Literal["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"] | None
    ) = None
    ganzhi: str | None = None
    xun_kong: StrictBool | None = None
    seated_kong: StrictBool | None = None
    day_stem_life_stage: str | None = None
    lesson_indices: list[Annotated[int, Field(strict=True, ge=1, le=4)]] | None = None
    transmission_positions: list[Literal["initial", "middle", "final"]] | None = None
    on_day_stem: StrictBool | None = None
    on_day_branch: StrictBool | None = None


class LiurenAuxiliaryStars(PartialOutput):
    ruleset_id: (
        Literal["tanyuan_auxiliary_stars_v1", "tanyuan_auxiliary_stars_v2"] | None
    ) = None
    source_title: str | None = None
    source_url: str | None = None
    original_pdf_pages: list[int] | None = None
    day_ganzhi: str | None = None
    month_building_branch: Branch | None = None
    nominal_month: Annotated[int, Field(strict=True, ge=1, le=12)] | None = None
    month_basis: str | None = None
    stars: list[LiurenAuxiliaryStar] | None = Field(
        default=None, min_length=7, max_length=20
    )
    complete_classical_conformance: StrictBool | None = None
    scope: str | None = None

    @field_validator("stars")
    @classmethod
    def unique_complete_ids(
        cls, value: list[LiurenAuxiliaryStar] | None
    ) -> list[LiurenAuxiliaryStar] | None:
        if value is not None and not {
            "heaven_de",
            "month_de",
            "day_de",
            "branch_de",
            "day_lu",
            "day_horse",
            "heaven_horse",
        }.issubset({star.id for star in value}):
            raise ValueError("德禄马需保留七项不同的规则标识")
        return value

    @field_validator("complete_classical_conformance", mode="before")
    @classmethod
    def no_full_book_claim(cls, value: object) -> bool | None:
        if value is not None and type(value) is not bool:
            raise ValueError("德禄马符合标识须为布尔值")
        return value


class LiurenBranchFacts(PartialOutput):
    same_branch: StrictBool | None = None
    liuhe: StrictBool | None = None
    liupo: StrictBool | None = None
    liuhai: StrictBool | None = None
    liuchong: StrictBool | None = None
    left_xing_right: StrictBool | None = None
    right_xing_left: StrictBool | None = None
    harmony_annotation: Literal["破合", "刑合"] | None = None


class LiurenBranchPair(PartialOutput):
    id: str | None = None
    left_role: str | None = None
    right_role: str | None = None
    left_branch: Branch | None = None
    right_branch: Branch | None = None
    facts: LiurenBranchFacts | None = None

    @model_validator(mode="after")
    def actual_pair_facts(self) -> "LiurenBranchPair":
        if (
            self.left_branch is not None
            and self.right_branch is not None
            and self.facts is not None
        ):
            compare_present_branches(
                self.facts.model_dump(exclude_unset=True),
                branch_pair_facts(self.left_branch, self.right_branch),
            )
        return self


class LiurenLessonBranches(PartialOutput):
    index: int | None = None
    lower_branch: Branch | None = None
    upper_branch: Branch | None = None


class LiurenBranchRelations(PartialOutput):
    ruleset_id: Literal["tanyuan_branch_relations_v1"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    original_pdf_pages: list[int] | None = None
    day_ganzhi: str | None = None
    calendar_branches: dict[Literal["year", "month", "day", "hour"], Branch] | None = (
        None
    )
    month_general_branch: Branch | None = None
    sky_by_earth: dict[Branch, Branch] | None = None
    lesson_branches: list[LiurenLessonBranches] | None = None
    transmission_branches: (
        dict[Literal["initial", "middle", "final"], Branch] | None
    ) = None
    rows: list[LiurenBranchPair] | None = None
    comprehensive_judgement: None = None
    complete_classical_conformance: StrictBool | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def ledger_matches_context(self) -> "LiurenBranchRelations":
        if self.rows is not None and len(self.rows) != 47:
            raise ValueError("六壬支位关系须保留47个比较对象")
        if self.calendar_branches is not None and self.day_ganzhi is not None:
            if (
                self.calendar_branches.get("day", self.day_ganzhi[-1:])
                != self.day_ganzhi[-1:]
            ):
                raise ValueError("六壬支位关系日支与日干支不一致")
        value = self.model_dump(exclude_unset=True)
        if _branch_context_available(value):
            compare_present_branches(value, _rebuild_branch_relations(value))
        return self


def _branch_context_available(value: Mapping[str, object]) -> bool:
    cal = value.get("calendar_branches")
    sky = value.get("sky_by_earth")
    lessons = value.get("lesson_branches")
    trans = value.get("transmission_branches")
    return (
        isinstance(value.get("day_ganzhi"), str)
        and isinstance(cal, Mapping)
        and set(cal) == {"year", "month", "day", "hour"}
        and isinstance(value.get("month_general_branch"), str)
        and isinstance(sky, Mapping)
        and len(sky) == 12
        and isinstance(lessons, list)
        and len(lessons) == 4
        and all(
            isinstance(row, Mapping)
            and all(
                row.get(k) is not None
                for k in ("index", "lower_branch", "upper_branch")
            )
            for row in lessons
        )
        and isinstance(trans, Mapping)
        and set(trans) == {"initial", "middle", "final"}
    )


def _rebuild_branch_relations(value: Mapping[str, object]) -> dict[str, object]:
    cal = _get_dict(value, "calendar_branches")
    sky = _get_dict(value, "sky_by_earth")
    trans = _get_dict(value, "transmission_branches")
    lessons = value.get("lesson_branches")
    assert isinstance(lessons, list)
    return branch_relations(
        day_ganzhi=str(value["day_ganzhi"]),
        year_branch=str(cal["year"]),
        month_branch=str(cal["month"]),
        hour_branch=str(cal["hour"]),
        month_general_branch=str(value["month_general_branch"]),
        sky_by_earth={str(k): str(v) for k, v in sky.items()},
        lessons=[dict(row) for row in lessons if isinstance(row, Mapping)],
        transmissions=[str(trans[p]) for p in ("initial", "middle", "final")],
    )


def align_branch_relations(board: object, pillars: object = None) -> None:
    evidence = _get(board, "branch_relations")
    if evidence is None:
        return
    day = _get(evidence, "day_ganzhi")
    cal = _get_dict(evidence, "calendar_branches")
    if pillars is not None:
        for role in ("year", "month", "day", "hour"):
            actual = _get(_get(pillars, role), "branch")
            if actual is not None and role in cal and cal[role] != actual:
                raise ValueError("六壬支位关系年月日时支与四柱不一致")
        stem = _get(_get(pillars, "day"), "stem")
        branch = _get(_get(pillars, "day"), "branch")
        if (
            day is not None
            and isinstance(stem, str)
            and isinstance(branch, str)
            and day != stem + branch
        ):
            raise ValueError("六壬支位关系占日与四柱不一致")
    general = _get(_get(board, "month_general"), "branch")
    own_general = _get(evidence, "month_general_branch")
    if general is not None and own_general is not None and own_general != general:
        raise ValueError("六壬支位关系月将与本课不一致")
    sky = _get_dict(evidence, "sky_by_earth")
    twelve = _get(board, "twelve_board")
    if isinstance(twelve, list):
        for row in twelve:
            earth, upper = _get(row, "earth_branch"), _get(row, "sky_branch")
            if (
                isinstance(earth, str)
                and earth in sky
                and upper is not None
                and sky[earth] != upper
            ):
                raise ValueError("六壬支位关系与同时返回的天地盘不一致")
    lessons = _get(evidence, "lesson_branches")
    if isinstance(lessons, list):
        actual_lessons = _get(board, "four_lessons")
        if isinstance(actual_lessons, list):
            if len(lessons) != len(actual_lessons):
                raise ValueError("六壬支位关系四课队列不一致")
            for own, actual in zip(lessons, actual_lessons):
                for k in ("index", "lower_branch", "upper_branch"):
                    a, b = _get(own, k), _get(actual, k)
                    if a is not None and b is not None and a != b:
                        raise ValueError("六壬支位关系与同时返回的四课不一致")
    transmissions = _get_dict(evidence, "transmission_branches")
    actual_transmissions = _get(board, "three_transmissions")
    for position, branch in transmissions.items():
        actual = _get(_get(actual_transmissions, position), "branch")
        if actual is not None and branch != actual:
            raise ValueError("六壬支位关系与同时返回的三传不一致")


def require_complete_branch_relations(board: Mapping[str, object]) -> None:
    evidence = board.get("branch_relations")
    if not isinstance(evidence, Mapping) or not _branch_context_available(evidence):
        raise ValueError("完整六壬输出缺少支位关系依据")
    if dict(evidence) != _rebuild_branch_relations(evidence):
        raise ValueError("完整六壬支位关系依据缺项或不一致")
    align_branch_relations(board)


class CourseCheck(PartialOutput):
    id: str | None = None
    matched: StrictBool | None = None


class CoursePattern(PartialOutput):
    id: str | None = None
    name: str | None = None
    required_stage: str | None = None
    required_god: str | None = None
    condition: str | None = None
    stage_matches: StrictBool | None = None
    god_matches: StrictBool | None = None
    checks: list[CourseCheck] | None = None
    matched: StrictBool | None = None
    required_stage_branch: Branch | None = None
    possible_god_branches: list[Branch] | None = None
    compatible_in_any_supported_noble_layout: StrictBool | None = None


class CourseLayoutWitness(PartialOutput):
    id: str | None = None
    source_title: str | None = None
    edition: str | None = None
    source_url: str | None = None
    original_pdf_pages: list[StrictInt] | None = None


class CourseLayoutBasis(PartialOutput):
    ruleset_id: Literal["tanyuan_supported_noble_layout_necessity_v1"] | None = None
    stage_subject: Literal["day_stem"] | None = None
    noble_profiles: list[Literal["liuren_common_v1", "tanyuan_xieji_v1"]] | None = None
    diurnal_alternatives: list[StrictBool] | None = None
    direction_alternatives: list[Literal["顺", "逆"]] | None = None
    conditions_are_alternatives: StrictBool | None = None
    is_initial_transmission_guarantee: StrictBool | None = None
    unresolved_authorial_intent_ids: list[Literal["S05"]] | None = None
    authorial_intent_adjudicated: None = None
    original_conditions_rewritten: StrictBool | None = None
    witnesses: list[CourseLayoutWitness] | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def source_basis_is_fixed(self) -> "CourseLayoutBasis":
        compare_present_branches(
            self.model_dump(exclude_unset=True), layout_compatibility_basis()
        )
        return self


class CourseNameReading(PartialOutput):
    id: str | None = None
    scan_reading: str | None = None
    online_transcription: str | None = None
    adjudication: Literal["selected_scan_literal"] | None = None


class LiurenCourseConditions(PartialOutput):
    ruleset_id: Literal["tanyuan_course_conditions_v1"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    original_pdf_pages: list[StrictInt] | None = None
    stage_basis_pdf_pages: list[StrictInt] | None = None
    day_ganzhi: str | None = None
    branches: list[Branch] | None = Field(default=None, min_length=3, max_length=3)
    transmission_branches: list[Branch] | None = Field(
        default=None, min_length=3, max_length=3
    )
    initial_god: str | None = None
    initial_earth_branch: Branch | None = None
    initial_branch: Branch | None = None
    initial_stage: str | None = None
    initial_day_stem_stage: str | None = None
    day_stem_house: Branch | None = None
    xun_head_branch: Branch | None = None
    xun_tail_branch: Branch | None = None
    day_xun_head: Branch | None = None
    day_xun_tail: Branch | None = None
    stage_god_patterns: list[CoursePattern] | None = Field(
        default=None, min_length=12, max_length=12
    )
    layout_compatibility_basis: CourseLayoutBasis | None = None
    god_patterns: list[CoursePattern] | None = Field(
        default=None, min_length=12, max_length=12
    )
    structural_patterns: list[CoursePattern] | None = Field(
        default=None, min_length=3, max_length=3
    )
    matched_ids: list[str] | None = None
    name_reading_notes: list[CourseNameReading] | None = Field(
        default=None, min_length=3, max_length=3
    )
    comprehensive_judgement: None = None
    complete_classical_conformance: StrictBool | None = None
    scope: str | None = None

    @model_validator(mode="before")
    @classmethod
    def conformance_is_false(
        cls, value: JsonValue | BaseModel
    ) -> JsonValue | BaseModel:
        return value

    @model_validator(mode="after")
    def present_facts_agree(self) -> LiurenCourseConditions:
        if self.day_ganzhi is not None and self.day_ganzhi not in SEXAGENARY_INDEX:
            raise ValueError("课体条件需要有效日干支")
        used_branches = self.branches or self.transmission_branches
        inputs = (
            self.day_ganzhi,
            used_branches,
            self.initial_god,
            self.initial_earth_branch,
        )
        complete = all(v is not None for v in inputs)
        expected = course_conditions(
            self.day_ganzhi or "甲子",
            {
                p: dict(
                    branch=(used_branches or ["子"] * 3)[i],
                    god=self.initial_god or "贵人",
                    earth_branch=self.initial_earth_branch or "子",
                )
                for i, p in enumerate(("initial", "middle", "final"))
            },
        )
        if not complete:
            for k in (
                "day_ganzhi",
                "branches",
                "transmission_branches",
                "initial_branch",
                "initial_god",
                "initial_earth_branch",
                "initial_stage",
                "initial_day_stem_stage",
                "day_stem_house",
                "xun_head_branch",
                "xun_tail_branch",
                "day_xun_head",
                "day_xun_tail",
                "matched_ids",
            ):
                expected.pop(k, None)
            for group in (
                "stage_god_patterns",
                "god_patterns",
                "structural_patterns",
                "stage_god_pairs",
                "god_pairs",
                "structural_clauses",
            ):
                rows = expected.get(group, ())
                if isinstance(rows, list):
                    for row in rows:
                        if isinstance(row, dict):
                            for k in (
                                "matched",
                                "stage_matches",
                                "god_matches",
                                "checks",
                            ):
                                row.pop(k, None)
        if self.day_ganzhi is None:
            for group in ("stage_god_patterns", "stage_god_pairs"):
                rows = expected.get(group, ())
                if isinstance(rows, list):
                    for row in rows:
                        if isinstance(row, dict):
                            for k in (
                                "required_stage_branch",
                                "possible_god_branches",
                                "compatible_in_any_supported_noble_layout",
                            ):
                                row.pop(k, None)
        compare_present_branches(self.model_dump(exclude_unset=True), expected)
        if self.day_ganzhi is not None:
            if self.branches is not None and self.initial_stage is not None:
                if (
                    self.initial_stage
                    != life_stage_cycle(self.day_ganzhi[0])[self.branches[0]]
                ):
                    raise ValueError("初传十二运与本课日干不一致")
        return self


def require_complete_course_conditions(board: Mapping[str, object]) -> None:
    day = _get_str(_get(board, "calendar_policy"), "effective_day_ganzhi")
    trans = _get_dict(board, "three_transmissions")
    if day is None:
        raise ValueError("完整课体条件缺少有效日干支")
    expected = course_conditions(day, dict(trans))
    relations = _get_dict(board, "transmission_relations")
    actual = relations.get("course_conditions")
    if _canonical_json(actual) != _canonical_json(expected):
        raise ValueError("完整课体条件缺项或与本课日干支、三传天将承座不一致")
    if relations.get("day_ganzhi") != day:
        raise ValueError("课体条件与同次三传关系日干支不一致")
    rows = relations.get("rows")
    if not isinstance(rows, list) or len(rows) != 3:
        raise ValueError("课体条件需要同次完整三传关系")
    for i, row in enumerate(rows):
        p = ("initial", "middle", "final")[i]
        recorded = _get_dict(trans, p)
        if not isinstance(row, Mapping):
            raise ValueError("课体条件需要同次完整三传关系")
        for field in ("branch", "god", "earth_branch"):
            if row.get(field) != recorded.get(field):
                raise ValueError("课体条件不能借用另一课三传事实")


class CrossHarmonyPair(PartialOutput):
    id: Literal["stem_upper_to_day_branch", "branch_upper_to_stem_house"] | None = None
    left_role: str | None = None
    right_role: str | None = None
    left_branch: Branch | None = None
    right_branch: Branch | None = None
    liuhe: StrictBool | None = None

    @model_validator(mode="after")
    def pair_agrees(self) -> CrossHarmonyPair:
        if (
            self.left_branch is not None
            and self.right_branch is not None
            and self.liuhe is not None
        ):
            if self.liuhe is not branch_pair_facts(
                self.left_branch, self.right_branch
            ).get("liuhe", False):
                raise ValueError("交车六合配对事实不一致")
        return self


class LiurenCrossHarmony(PartialOutput):
    ruleset_id: Literal["daquan_siku_bifa21_cross_harmony_v1"] | None = None
    name: Literal["交车合"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_revision: StrictInt | None = None
    source_kind: str | None = None
    witness_source_title: str | None = None
    witness_source_url: str | None = None
    witness_pdf_pages: list[StrictInt] | None = None
    definition: str | None = None
    excluded_days: list[str] | None = None
    day_ganzhi: str | None = None
    day_stem_house: Branch | None = None
    day_branch: Branch | None = None
    stem_upper: Branch | None = None
    branch_upper: Branch | None = None
    sky_by_earth: dict[Branch, Branch] | None = None
    cross_pairs: list[CrossHarmonyPair] | None = Field(
        default=None, min_length=2, max_length=2
    )
    distinct_anchors: StrictBool | None = None
    both_cross_pairs: StrictBool | None = None
    matched: StrictBool | None = None
    exclusion_reason: Literal["干支同宫（八专五日）"] | None = None
    comprehensive_judgement: None = None
    complete_classical_conformance: StrictBool | None = None
    scope: str | None = None

    @model_validator(mode="before")
    @classmethod
    def no_false_certificate(
        cls, value: JsonValue | BaseModel
    ) -> JsonValue | BaseModel:
        return value

    @model_validator(mode="after")
    def present_facts_agree(self) -> LiurenCrossHarmony:
        expected = cross_harmony_metadata()
        pairs: list[dict[str, object]] = [
            {
                "id": "stem_upper_to_day_branch",
                "left_role": "干上神",
                "right_role": "日支",
            },
            {
                "id": "branch_upper_to_stem_house",
                "left_role": "支上神",
                "right_role": "日干寄宫支",
            },
        ]
        expected["cross_pairs"] = pairs
        if self.day_ganzhi is not None:
            if self.day_ganzhi not in SEXAGENARY_INDEX:
                raise ValueError("交车合条件需要有效日干支")
            house = STEM_HOUSES[self.day_ganzhi[0]]
            distinct = house != self.day_ganzhi[1]
            expected.update(
                day_ganzhi=self.day_ganzhi,
                day_stem_house=house,
                day_branch=self.day_ganzhi[1],
                distinct_anchors=distinct,
                exclusion_reason=None if distinct else "干支同宫（八专五日）",
            )
            if not distinct:
                expected["matched"] = False
            pairs[0]["right_branch"] = self.day_ganzhi[1]
            pairs[1]["right_branch"] = house
            if self.sky_by_earth is not None and len(self.sky_by_earth) == 12:
                sky: dict[str, str] = {k: v for k, v in self.sky_by_earth.items()}
                expected = cross_harmony(self.day_ganzhi, sky)
        expected_pairs = expected.get("cross_pairs")
        if isinstance(expected_pairs, list):
            for key, index in (("stem_upper", 0), ("branch_upper", 1)):
                val = getattr(self, key)
                if val is not None and isinstance(expected_pairs[index], dict):
                    expected_pairs[index]["left_branch"] = val
        both = self.both_cross_pairs
        if self.cross_pairs is not None:
            values = [p.liuhe for p in self.cross_pairs]
            if False in values:
                both = False
            elif all(v is True for v in values):
                both = True
            if both is not None:
                expected["both_cross_pairs"] = both
        distinct_value = expected.get("distinct_anchors", self.distinct_anchors)
        if both is False or distinct_value is False:
            expected["matched"] = False
        elif both is True and distinct_value is True:
            expected["matched"] = True
        compare_present_branches(self.model_dump(exclude_unset=True), expected)
        return self


def align_cross_harmony(board: object, day_ganzhi: str | None = None) -> None:
    own = _get(board, "cross_harmony")
    if own is None:
        return
    day = _get(own, "day_ganzhi")
    actual = _get_str(_get(board, "calendar_policy"), "effective_day_ganzhi")
    if day is not None and any(
        d is not None and d != day for d in (actual, day_ganzhi)
    ):
        raise ValueError("交车合条件与本课日干支不一致")
    sky = _get_dict(own, "sky_by_earth")
    rows = _get(board, "twelve_board")
    if isinstance(rows, list):
        for row in rows:
            earth, upper = _get(row, "earth_branch"), _get(row, "sky_branch")
            if (
                isinstance(earth, str)
                and earth in sky
                and upper is not None
                and sky[earth] != upper
            ):
                raise ValueError("交车合条件与本课天地盘不一致")
    effective = actual or day_ganzhi
    if (
        effective is not None
        and isinstance(rows, list)
        and len(rows) == 12
        and all(
            isinstance(_get(r, "earth_branch"), str)
            and isinstance(_get(r, "sky_branch"), str)
            for r in rows
        )
    ):
        expected = cross_harmony(
            effective,
            {str(_get(r, "earth_branch")): str(_get(r, "sky_branch")) for r in rows},
        )
        value = (
            own
            if isinstance(own, Mapping)
            else (
                own.model_dump(exclude_unset=True)
                if isinstance(own, BaseModel)
                else own
            )
        )
        compare_present_branches(value, expected)
    lessons = _get(board, "four_lessons")
    if isinstance(lessons, list) and len(lessons) >= 3:
        for key, index in (("stem_upper", 0), ("branch_upper", 2)):
            own_upper, actual_upper = _get(own, key), _get(
                lessons[index], "upper_branch"
            )
            if (
                own_upper is not None
                and actual_upper is not None
                and own_upper != actual_upper
            ):
                raise ValueError("交车合条件与同时返回的干支上神不一致")


def require_complete_cross_harmony(board: Mapping[str, object]) -> None:
    rows = board.get("twelve_board")
    if not isinstance(rows, list) or len(rows) != 12:
        raise ValueError("完整交车合条件需要十二位天地盘")
    day = _get_str(board.get("calendar_policy"), "effective_day_ganzhi")
    if day is None:
        raise ValueError("完整交车合条件缺少有效日干支")
    sky = {str(_get(r, "earth_branch")): str(_get(r, "sky_branch")) for r in rows}
    expected = cross_harmony(day, sky)
    if _canonical_json(board.get("cross_harmony")) != _canonical_json(expected):
        raise ValueError("完整交车合条件缺项或与本课不一致")


class DayPlacementRule(PartialOutput):
    id: str | None = None
    name: str | None = None
    condition: str | None = None
    placement: Literal["stem_over_branch", "branch_over_stem"] | None = None
    relation: PhaseRelation | Literal["harmony_unadjudicated"] | None = None
    definition_adjudicated: StrictBool | None = None
    placement_matches: StrictBool | None = None
    relation_matches: StrictBool | None = None
    matched: StrictBool | None = None

    @model_validator(mode="after")
    def unresolved_harmony_requires_placement(self) -> DayPlacementRule:
        if self.definition_adjudicated is False and "matched" in self.model_fields_set:
            if self.matched is not (False if self.placement_matches is False else None):
                raise ValueError("合式未裁时，仅在缺少加临前提时排除")
        return self


class LiurenDayPlacements(PartialOutput):
    ruleset_id: Literal["tanyuan_day_placements_v2"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    original_pdf_pages: list[StrictInt] | None = None
    day_ganzhi: str | None = None
    day_stem_house: Branch | None = None
    day_stem_element: Literal["木", "火", "土", "金", "水"] | None = None
    day_branch_element: Literal["木", "火", "土", "金", "水"] | None = None
    sky_by_earth: dict[Branch, Branch] | None = None
    placements: (
        dict[Literal["stem_over_branch", "branch_over_stem"], StrictBool] | None
    ) = None
    element_relations: dict[PhaseRelation, StrictBool] | None = None
    evaluations: list[DayPlacementRule] | None = Field(
        default=None, min_length=12, max_length=12
    )
    evaluated_count: StrictInt | None = None
    unresolved_count: StrictInt | None = None
    matched_ids: list[MatchedRuleId] | None = None
    unresolved_ids: list[Literal["D11", "D12"]] | None = None
    comprehensive_judgement: None = None
    complete_classical_conformance: StrictBool | None = None
    scope: str | None = None

    @model_validator(mode="before")
    @classmethod
    def no_false_conformance(
        cls, value: JsonValue | BaseModel
    ) -> JsonValue | BaseModel:
        return value

    @model_validator(mode="after")
    def present_facts_agree(self) -> LiurenDayPlacements:
        expected = placement_metadata()
        if self.day_ganzhi is not None:
            if self.day_ganzhi not in SEXAGENARY_INDEX:
                raise ValueError("干支加临需要有效日干支")
            expected.update(
                day_ganzhi=self.day_ganzhi,
                day_stem_house=STEM_HOUSES[self.day_ganzhi[0]],
                day_stem_element=stem_element_text(self.day_ganzhi[0]),
                day_branch_element=branch_element_text(self.day_ganzhi[1]),
            )
            if self.sky_by_earth is not None and len(self.sky_by_earth) == 12:
                sky: dict[str, str] = {k: v for k, v in self.sky_by_earth.items()}
                expected = day_placement_patterns(self.day_ganzhi, sky)
        compare_present_branches(self.model_dump(exclude_unset=True), expected)
        return self


def align_day_placements(board: object, day_ganzhi: str | None = None) -> None:
    evidence = _get(board, "day_placement_patterns")
    if evidence is None:
        return
    day = _get(evidence, "day_ganzhi")
    actual_day = _get(_get(board, "calendar_policy"), "effective_day_ganzhi")
    if day is not None and actual_day is not None and day != actual_day:
        raise ValueError("干支加临与本课日干支不一致")
    if day is not None and day_ganzhi is not None and day != day_ganzhi:
        raise ValueError("干支加临与同时返回的四柱不一致")
    sky = _get_dict(evidence, "sky_by_earth")
    twelve = _get(board, "twelve_board")
    if isinstance(twelve, list):
        for row in twelve:
            earth, upper = _get(row, "earth_branch"), _get(row, "sky_branch")
            if (
                isinstance(earth, str)
                and earth in sky
                and upper is not None
                and sky[earth] != upper
            ):
                raise ValueError("干支加临与同时返回的天地盘不一致")


def require_complete_day_placements(board: Mapping[str, object]) -> None:
    rows = board.get("twelve_board")
    if not isinstance(rows, list) or len(rows) != 12:
        raise ValueError("完整干支加临条件需要十二位天地盘")
    day = _get_str(board.get("calendar_policy"), "effective_day_ganzhi")
    if day is None:
        raise ValueError("完整干支加临条件缺少有效日干支")
    sky = {str(_get(r, "earth_branch")): str(_get(r, "sky_branch")) for r in rows}
    expected = day_placement_patterns(day, sky)
    if _canonical_json(board.get("day_placement_patterns")) != _canonical_json(
        expected
    ):
        raise ValueError("完整干支加临条件缺项或与本课不一致")


class LiurenEmptyRow(PartialOutput):
    earth_branch: Branch
    sky_branch: Branch
    sky_xun_kong: StrictBool
    earth_xun_kong: StrictBool
    earth_is_day_stem_house: StrictBool
    earth_stem_house_exception: StrictBool
    sky_authority_roles: list[AuthorityRole]
    sky_authority_xunkong_exception: StrictBool
    earth_year_fate_roles: list[Literal["natal", "annual"]] | None = None
    earth_year_fate_xunkong_exception: StrictBool | None = None
    earth_xunkong_after_seat_and_year_fate: StrictBool | None = None
    effective_empty: None = None

    @model_validator(mode="after")
    def seat_exception_is_local(self) -> "LiurenEmptyRow":
        if self.earth_stem_house_exception != (
            self.earth_xun_kong and self.earth_is_day_stem_house
        ):
            raise ValueError("地盘日干寄宫空亡例外的条件不一致")
        return self


class LiurenEmptyRole(PartialOutput):
    role: AuthorityRole
    branch: Branch
    branch_xun_kong: StrictBool
    xunkong_exception_applies: StrictBool


class LiurenYearFateEarthBranches(PartialOutput):
    natal: Branch | None = None
    annual: Branch | None = None


class LiurenEmptinessEvidence(PartialOutput):
    ruleset_id: Literal["liuren_tanyuan_empty_scope_v3"] | None = None
    source_url: str | None = None
    source_title: str | None = None
    original_pdf_pages: list[int] | None = None
    year_fate_placement_pdf_pages: list[int] | None = None
    day_ganzhi: str | None = None
    xun_head: str | None = None
    empty_branches: list[Branch] | None = None
    day_stem_house: Branch | None = None
    year_branch: Branch | None = None
    month_building_branch: Branch | None = None
    month_general_branch: Branch | None = None
    hour_branch: Branch | None = None
    hour_branch_xun_kong: StrictBool | None = None
    role_conditions: list[LiurenEmptyRole] | None = None
    rows: list[LiurenEmptyRow] | None = None
    year_fate_earth_branches: LiurenYearFateEarthBranches | None = None
    nianming_status: Literal["calculated", "partial", "inputs_not_available"] | None = (
        None
    )
    filling_clashing_status: Literal["role_exceptions_only"] | None = None
    comprehensive_judgement: None = None
    complete_classical_conformance: StrictBool | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def empty_facts_match_context(self) -> "LiurenEmptinessEvidence":
        if self.rows is not None and [r.earth_branch for r in self.rows] != list(
            EARTHLY_BRANCHES
        ):
            raise ValueError("六壬空亡依据必须保留十二地盘位，不得删减或调序")
        if self.rows is not None and {r.sky_branch for r in self.rows} != set(
            EARTHLY_BRANCHES
        ):
            raise ValueError("六壬空亡依据的天盘须含十二个不同支位")
        if self.role_conditions is not None and [
            r.role for r in self.role_conditions
        ] != ["太岁", "月建", "月将"]:
            raise ValueError("六壬空亡角色条件不得删减、合并或调序")
        if self.day_ganzhi is not None:
            if self.day_ganzhi not in SEXAGENARY_INDEX:
                raise ValueError("六壬空亡依据需要有效日干支")
            empty = kongwang_for_ganzhi(self.day_ganzhi)[:2]
            if self.xun_head is not None and self.xun_head != xun_head_for_ganzhi(
                self.day_ganzhi
            ):
                raise ValueError("六壬空亡旬首与占日不一致")
            if self.empty_branches is not None and self.empty_branches != list(empty):
                raise ValueError("六壬空亡两支与占日不一致")
            house = STEM_HOUSES[self.day_ganzhi[0]]
            if self.day_stem_house is not None and self.day_stem_house != house:
                raise ValueError("六壬空亡依据的日干寄宫不一致")
            for row in self.rows or []:
                if (
                    row.sky_xun_kong != (row.sky_branch in empty)
                    or row.earth_xun_kong != (row.earth_branch in empty)
                    or row.earth_is_day_stem_house != (row.earth_branch == house)
                ):
                    raise ValueError("天盘本空、地盘本空或日干地盘位与占日不一致")
            for role in self.role_conditions or []:
                if role.branch_xun_kong != (role.branch in empty):
                    raise ValueError("六壬空亡角色的本空事实与占日不一致")
            if (
                self.hour_branch is not None
                and self.hour_branch_xun_kong is not None
                and self.hour_branch_xun_kong != (self.hour_branch in empty)
            ):
                raise ValueError("六壬占时本空与占日旬空不一致")
        role_branches = {
            "太岁": self.year_branch,
            "月建": self.month_building_branch,
            "月将": self.month_general_branch,
        }
        for role in self.role_conditions or []:
            branch = role_branches[role.role]
            if branch is not None and role.branch != branch:
                raise ValueError("六壬空亡角色支位与本次依据不一致")
        if (
            self.day_ganzhi is not None
            and self.year_branch is not None
            and self.month_building_branch is not None
            and self.month_general_branch is not None
            and self.hour_branch is not None
            and self.rows is not None
        ):
            expected = emptiness_evidence(
                day_ganzhi=self.day_ganzhi,
                year_branch=self.year_branch,
                month_branch=self.month_building_branch,
                month_general_branch=self.month_general_branch,
                hour_branch=self.hour_branch,
                sky_by_earth={r.earth_branch: r.sky_branch for r in self.rows},
            )
            placements = self.year_fate_earth_branches
            if (
                placements is not None
                and {"natal", "annual"} <= placements.model_fields_set
            ):
                apply_year_fate_emptiness(
                    expected, natal=placements.natal, annual=placements.annual
                )
            else:
                for key in ("year_fate_earth_branches", "nianming_status"):
                    expected.pop(key, None)
                expected_rows = expected.get("rows")
                if isinstance(expected_rows, list):
                    for row in expected_rows:
                        if isinstance(row, dict):
                            for key in (
                                "earth_year_fate_roles",
                                "earth_year_fate_xunkong_exception",
                                "earth_xunkong_after_seat_and_year_fate",
                            ):
                                row.pop(key, None)
            compare_present_empty(self.model_dump(exclude_unset=True), expected)
        return self


def require_complete_emptiness(
    board: Mapping[str, object], *, natal: str | None = None, annual: str | None = None
) -> None:
    evidence = board.get("emptiness_evidence")
    required = (
        "day_ganzhi",
        "year_branch",
        "month_building_branch",
        "month_general_branch",
        "hour_branch",
        "rows",
    )
    if not isinstance(evidence, Mapping) or any(
        evidence.get(k) is None for k in required
    ):
        raise ValueError("完整六壬输出缺少空亡计算依据")
    day_ganzhi = _get_str(evidence, "day_ganzhi")
    year_branch = _get_str(evidence, "year_branch")
    month_branch = _get_str(evidence, "month_building_branch")
    month_general_branch = _get_str(evidence, "month_general_branch")
    hour_branch = _get_str(evidence, "hour_branch")
    rows = evidence.get("rows")
    if (
        day_ganzhi is None
        or year_branch is None
        or month_branch is None
        or month_general_branch is None
        or hour_branch is None
        or not isinstance(rows, list)
    ):
        raise ValueError("完整六壬输出缺少空亡计算依据")
    expected = emptiness_evidence(
        day_ganzhi=day_ganzhi,
        year_branch=year_branch,
        month_branch=month_branch,
        month_general_branch=month_general_branch,
        hour_branch=hour_branch,
        sky_by_earth={
            str(_get(r, "earth_branch")): str(_get(r, "sky_branch")) for r in rows
        },
    )
    if natal is not None or annual is not None:
        apply_year_fate_emptiness(expected, natal=natal, annual=annual)
    if dict(evidence) != expected:
        raise ValueError("完整六壬输出的空亡依据缺项或与计算条件不一致")


class LiurenSeasonalRow(PartialOutput):
    earth_branch: Branch
    sky_branch: Branch
    sky_element: Element
    sky_seasonal_power: Power
    god: God
    god_element: Element
    god_seasonal_power: Power
    earth_element: Element
    earth_seasonal_power: Power
    sky_xun_kong: StrictBool
    sky_empty_seasonal_condition: Literal["真空条件", "半空条件"] | None
    effective_empty_class: None

    @model_validator(mode="after")
    def inherent_and_raw_facts(self) -> "LiurenSeasonalRow":
        if (
            self.sky_element != branch_element_text(self.sky_branch)
            or self.earth_element != branch_element_text(self.earth_branch)
            or self.god_element != GOD_ELEMENTS[self.god]
        ):
            raise ValueError("季节条件的支神、天将或地盘固有五行不符")
        if self.sky_empty_seasonal_condition != empty_condition(
            self.sky_seasonal_power, self.sky_xun_kong
        ):
            raise ValueError("真半条件必须按本支五态及本空，不能套天将或日干")
        return self


class LiurenSeasonalEvidence(PartialOutput):
    ruleset_id: Literal["tanyuan_seasonal_month_conditions_v1"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    original_pdf_pages: list[StrictInt] | None = None
    month_partition_profile: Literal["declared_seasonal_month_branches_v1"] | None = (
        None
    )
    month_partition_basis: str | None = None
    day_ganzhi: str | None = None
    month_branch: Branch | None = None
    season_partition: Literal["春", "夏", "秋", "冬", "季月"] | None = None
    phase_powers: dict[Element, Power] | None = None
    day_stem_element: Element | None = None
    day_stem_seasonal_power: Power | None = None
    empty_branches: list[Branch] | None = None
    rows: list[LiurenSeasonalRow] | None = None
    raw_true_condition_branches: list[Branch] | None = None
    raw_half_condition_branches: list[Branch] | None = None
    effective_empty_classification: None = None
    effective_true_half_adjudicated: StrictBool | None = None
    complete_classical_conformance: StrictBool | None = None
    scope: str | None = None

    @model_validator(mode="before")
    @classmethod
    def strict_unresolved_flags(
        cls, value: JsonValue | BaseModel
    ) -> JsonValue | BaseModel:
        return value

    @model_validator(mode="after")
    def same_seasonal_facts(self) -> "LiurenSeasonalEvidence":
        present = self.model_dump(exclude_unset=True)
        for key, expected in seasonal_metadata().items():
            if key in present:
                compare_present_branches(present[key], expected)
        partition = (
            MONTH_PARTITION[self.month_branch]
            if self.month_branch is not None
            else self.season_partition
        )
        if (
            self.month_branch is not None
            and self.season_partition is not None
            and partition != self.season_partition
        ):
            raise ValueError("季节分组与本次月建支不符")
        known_powers = POWERS[partition] if partition is not None else self.phase_powers
        if self.phase_powers is not None and known_powers is not None:
            compare_present_branches(self.phase_powers, known_powers)
        day_element = self.day_stem_element
        if self.day_ganzhi is not None:
            if self.day_ganzhi not in SEXAGENARY_INDEX:
                raise ValueError("季节条件日干支无效")
            element = stem_element_text(self.day_ganzhi[0])
            day_element = _ELEMENTS.get(element)
            if self.day_stem_element is not None and self.day_stem_element != element:
                raise ValueError("季节条件日干五行不符")
            if self.empty_branches is not None and self.empty_branches != list(
                kongwang_for_ganzhi(self.day_ganzhi)[:2]
            ):
                raise ValueError("季节条件旬空两支不符")
        if (
            day_element is not None
            and known_powers is not None
            and day_element in known_powers
            and self.day_stem_seasonal_power is not None
            and self.day_stem_seasonal_power != known_powers[day_element]
        ):
            raise ValueError("日干季节五态与同时返回的五态表不符")
        if self.empty_branches is not None and len(self.empty_branches) != 2:
            raise ValueError("季节条件须保留两支本空")
        if self.rows is not None:
            if (
                [r.earth_branch for r in self.rows] != list(EARTHLY_BRANCHES)
                or len({r.sky_branch for r in self.rows}) != 12
                or len({r.god for r in self.rows}) != 12
            ):
                raise ValueError("季节条件须保留十二地盘顺序与完整支神天将")
            for row in self.rows:
                if known_powers is not None:
                    for elem, power in [
                        (row.sky_element, row.sky_seasonal_power),
                        (row.god_element, row.god_seasonal_power),
                        (row.earth_element, row.earth_seasonal_power),
                    ]:
                        if elem in known_powers and power != known_powers[elem]:
                            raise ValueError("季节五态与同时返回的对象五行不符")
                if self.day_ganzhi is not None and row.sky_xun_kong != (
                    row.sky_branch in kongwang_for_ganzhi(self.day_ganzhi)[:2]
                ):
                    raise ValueError("季节条件支神本空与日干支不符")
            for field_name, condition in [
                ("raw_true_condition_branches", "真空条件"),
                ("raw_half_condition_branches", "半空条件"),
            ]:
                present_branches = getattr(self, field_name)
                if present_branches is not None and present_branches != [
                    b
                    for b in EARTHLY_BRANCHES
                    if any(
                        r.sky_branch == b
                        and r.sky_empty_seasonal_condition == condition
                        for r in self.rows
                    )
                ]:
                    raise ValueError("原始真半条件支清单与同时返回的十二位不符")
            if self.day_ganzhi is not None and self.month_branch is not None:
                expected = seasonal_evidence(
                    day_ganzhi=self.day_ganzhi,
                    month_branch=self.month_branch,
                    sky_by_earth={r.earth_branch: r.sky_branch for r in self.rows},
                    god_by_sky={r.sky_branch: r.god for r in self.rows},
                )
                compare_present_branches(self.model_dump(exclude_unset=True), expected)
        return self


def align_seasonal(board: object, pillars: object = None) -> None:
    value = _get(board, "seasonal_evidence")
    if value is None:
        return
    day = _get(value, "day_ganzhi")
    month = _get(value, "month_branch")
    if pillars is not None:
        a, b = _get(_get(pillars, "day"), "stem"), _get(_get(pillars, "day"), "branch")
        if (
            day is not None
            and isinstance(a, str)
            and isinstance(b, str)
            and day != a + b
        ):
            raise ValueError("季节条件与同次日干支不符")
        own = _get(_get(pillars, "month"), "branch")
        if own is not None and month is not None and own != month:
            raise ValueError("季节条件必须用同次月建支")
    for name in ("emptiness_evidence", "branch_relations"):
        item = _get(board, name)
        if (
            day is not None
            and _get(item, "day_ganzhi") is not None
            and day != _get(item, "day_ganzhi")
        ):
            raise ValueError("季节条件日干支与本课不符")
        mb = (
            _get(item, "month_building_branch")
            if name == "emptiness_evidence"
            else _get(_get(item, "calendar_branches"), "month")
        )
        if month is not None and mb is not None and month != mb:
            raise ValueError("季节条件月建与本课不符")
    rows = _get(value, "rows")
    if isinstance(rows, list):
        by_earth = {_get(r, "earth_branch"): r for r in rows}
        by_sky = {_get(r, "sky_branch"): r for r in rows}
        twelve = _get(board, "twelve_board")
        if isinstance(twelve, list):
            for r in twelve:
                own_row = by_earth[_get(r, "earth_branch")]
                if any(
                    _get(r, k) is not None and _get(r, k) != _get(own_row, k)
                    for k in ("sky_branch", "god")
                ):
                    raise ValueError("季节条件必须沿用同次十二盘支神天将")
        trans = _get(board, "three_transmissions")
        for label in ("initial", "middle", "final"):
            r = _get(trans, label)
            branch = _get(r, "branch")
            if branch is not None:
                own_row = by_sky[branch]
                if _get(r, "god") is not None and _get(r, "god") != _get(
                    own_row, "god"
                ):
                    raise ValueError("季节条件与三传乘将不符")
                if _get(r, "xun_kong") is not None and _get(r, "xun_kong") != _get(
                    own_row, "sky_xun_kong"
                ):
                    raise ValueError("季节条件与三传本空不符")


def require_complete_seasonal(board: Mapping[str, object]) -> None:
    if not isinstance(board, Mapping):
        raise ValueError("完整六壬输出缺少本课")
    value = board.get("seasonal_evidence")
    if not isinstance(value, Mapping):
        raise ValueError("完整六壬输出缺少季节条件")
    LiurenSeasonalEvidence.model_validate(value)
    day_ganzhi = _get_str(value, "day_ganzhi")
    month_branch = _get_str(value, "month_branch")
    rows = value.get("rows")
    if day_ganzhi is None or month_branch is None or not isinstance(rows, list):
        raise ValueError("完整六壬季节条件缺少同次输入")
    expected = seasonal_evidence(
        day_ganzhi=day_ganzhi,
        month_branch=month_branch,
        sky_by_earth={
            str(_get(r, "earth_branch")): str(_get(r, "sky_branch")) for r in rows
        },
        god_by_sky={str(_get(r, "sky_branch")): str(_get(r, "god")) for r in rows},
    )
    if dict(value) != expected:
        raise ValueError("完整六壬季节条件缺项或不符")
    align_seasonal(board)


class LiurenGodYinRow(PartialOutput):
    god: God | None = None
    riding_branch: Branch | None = None
    riding_earth_branch: Branch | None = None
    yin_branch: Branch | None = None
    yin_earth_branch: Branch | None = None
    derivation: Literal["opposite_noble_start", "upper_of_riding_branch"] | None = None
    lesson_indices: list[int] | None = None
    transmission_positions: list[Literal["initial", "middle", "final"]] | None = None
    in_natal_upper: StrictBool | None = None
    in_annual_upper: StrictBool | None = None
    appears_in_roles: StrictBool | None = None
    yin_branch_xun_kong: StrictBool | None = None
    nominal_seasonal_power: Power | None = None
    nominal_wang_xiang: StrictBool | None = None
    effective_emptiness: None = None
    ri_chen_de_he_sheng_adjudicated: None = None
    comprehensive_eligibility: None = None


class LiurenGodYin(PartialOutput):
    ruleset_id: Literal["tanyuan_category_spirit_yin_v1"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    original_pdf_pages: list[int] | None = None
    day_ganzhi: str | None = None
    month_branch: Branch | None = None
    is_diurnal: StrictBool | None = None
    guiren_profile: Literal["liuren_common_v1", "tanyuan_xieji_v1"] | None = None
    sky_by_earth: dict[Branch, Branch] | None = None
    god_by_sky: dict[Branch, God] | None = None
    lesson_uppers: list[Branch] | None = None
    transmission_branches: list[Branch] | None = None
    year_fate_uppers: dict[Literal["natal", "annual"], Branch | None] | None = None
    seasonal_profile: Literal["declared_seasonal_month_branches_v1"] | None = None
    rows: list[LiurenGodYinRow] | None = None
    complete_classical_conformance: StrictBool | None = None
    scope: str | None = None

    @model_validator(mode="before")
    @classmethod
    def no_false_conformance(
        cls, value: JsonValue | BaseModel
    ) -> JsonValue | BaseModel:
        return value

    @model_validator(mode="after")
    def values_follow_this_context(self) -> "LiurenGodYin":
        value = self.model_dump(exclude_unset=True)
        if self.rows is not None and len(self.rows) != 12:
            raise ValueError("类神阴神须保留十二天将队列")
        if self.lesson_uppers is not None and len(self.lesson_uppers) != 4:
            raise ValueError("类神阴神四课依据需要四个位置")
        if (
            self.transmission_branches is not None
            and len(self.transmission_branches) != 3
        ):
            raise ValueError("类神阴神三传依据需要三个位置")
        if _god_yin_context_available(value):
            compare_present_branches(value, _rebuild_god_yin(value))
        return self


def _god_yin_context_available(value: Mapping[str, object]) -> bool:
    sky = value.get("sky_by_earth")
    gods = value.get("god_by_sky")
    yf = value.get("year_fate_uppers")
    return (
        all(key in value and value[key] is not None for key in _GOD_YIN_INPUTS)
        and isinstance(sky, Mapping)
        and set(sky) == set(EARTHLY_BRANCHES)
        and isinstance(gods, Mapping)
        and set(gods) == set(EARTHLY_BRANCHES)
        and isinstance(yf, Mapping)
        and set(yf) == {"natal", "annual"}
    )


def _rebuild_god_yin(value: Mapping[str, object]) -> dict[str, object]:
    sky = _get_dict(value, "sky_by_earth")
    gods = _get_dict(value, "god_by_sky")
    yf = _get_dict(value, "year_fate_uppers")
    lessons = value["lesson_uppers"]
    trans = value["transmission_branches"]
    assert isinstance(lessons, list) and isinstance(trans, list)
    raw_profile = value["guiren_profile"]
    guiren_profile: Literal["liuren_common_v1", "tanyuan_xieji_v1"]
    if raw_profile == "liuren_common_v1":
        guiren_profile = "liuren_common_v1"
    elif raw_profile == "tanyuan_xieji_v1":
        guiren_profile = "tanyuan_xieji_v1"
    else:
        raise ValueError("六壬贵人表配置未知")
    return god_yin_spirits(
        day_ganzhi=str(value["day_ganzhi"]),
        month_branch=str(value["month_branch"]),
        is_diurnal=bool(value["is_diurnal"]),
        guiren_profile=guiren_profile,
        sky_by_earth={str(k): str(v) for k, v in sky.items()},
        god_by_sky={str(k): str(v) for k, v in gods.items()},
        lesson_uppers=[str(x) for x in lessons],
        transmission_branches=[str(x) for x in trans],
        year_fate_uppers={
            str(k): (str(v) if v is not None else None) for k, v in yf.items()
        },
    )


def align_god_yin(
    board: object, pillars: object = None, runyear: object = None
) -> None:
    value = _get(board, "god_yin")
    if value is None:
        return
    if pillars is not None:
        stem, branch = _get(_get(pillars, "day"), "stem"), _get(
            _get(pillars, "day"), "branch"
        )
        if (
            isinstance(stem, str)
            and isinstance(branch, str)
            and _get(value, "day_ganzhi") not in (None, stem + branch)
        ):
            raise ValueError("类神阴神与同次日干支不一致")
        month = _get(_get(pillars, "month"), "branch")
        if month and _get(value, "month_branch") not in (None, month):
            raise ValueError("类神阴神季节条件与同次月建不一致")
    meta = _get(board, "meta")
    for own, other in (
        ("guiren_profile", "guiren_profile"),
        ("is_diurnal", "is_diurnal"),
    ):
        actual, expected = _get(value, own), _get(meta, other)
        if actual is not None and expected is not None and actual != expected:
            raise ValueError("类神阴神与所选贵人配置或昼夜不一致")
    sky, gods = _get_dict(value, "sky_by_earth"), _get_dict(value, "god_by_sky")
    twelve = _get(board, "twelve_board")
    if isinstance(twelve, list):
        for row in twelve:
            earth, upper, god = (
                _get(row, "earth_branch"),
                _get(row, "sky_branch"),
                _get(row, "god"),
            )
            if (
                sky
                and isinstance(earth, str)
                and earth in sky
                and upper is not None
                and sky[earth] != upper
            ):
                raise ValueError("类神阴神与本课天地盘不一致")
            if (
                gods
                and isinstance(upper, str)
                and upper in gods
                and god is not None
                and gods[upper] != god
            ):
                raise ValueError("类神阴神与本课天将盘不一致")
    lessons = _get(value, "lesson_uppers")
    four = _get(board, "four_lessons")
    if isinstance(lessons, list) and isinstance(four, list):
        for row in four:
            index, upper = _get(row, "index"), _get(row, "upper_branch")
            if (
                isinstance(index, int)
                and upper is not None
                and lessons[index - 1] != upper
            ):
                raise ValueError("类神阴神与本课四课不一致")
    transmissions = _get(value, "transmission_branches")
    if isinstance(transmissions, list):
        for i, p in enumerate(("initial", "middle", "final")):
            upper = _get(_get(_get(board, "three_transmissions"), p), "branch")
            if upper is not None and upper != transmissions[i]:
                raise ValueError("类神阴神与本课三传不一致")
    if runyear is not None and _get(value, "year_fate_uppers") is not None:
        roles = _get_dict(value, "year_fate_uppers")
        for role in ("natal", "annual"):
            if role not in roles:
                continue
            item = _get(_get(runyear, "year_fate"), role)
            if item is None:
                continue
            expected = _get(item, "sky_branch")
            present = (
                "sky_branch" in item
                if isinstance(item, Mapping)
                else "sky_branch" in getattr(item, "model_fields_set", set())
            )
            if not present:
                continue
            if roles.get(role) != expected:
                raise ValueError("类神阴神与同次年命上神不一致")


def require_complete_god_yin(board: Mapping[str, object]) -> None:
    value = board.get("god_yin")
    if not isinstance(value, Mapping) or not _god_yin_context_available(value):
        raise ValueError("完整六壬须保留类神阴神原始依据")
    expected = _rebuild_god_yin(value)
    if dict(value) != expected:
        raise ValueError("完整六壬类神阴神须保留全部可空条件及十二天将")
    align_god_yin(board)


class LiurenLifePlacement(PartialOutput):
    name: Literal["墓乘长生", "长生乘墓"] | None = None
    sky_branch: str | None = None
    earth_branch: str | None = None
    required_earth_branch: str | None = None
    sky_stage: LiurenLifeStage | None = None
    earth_stage: LiurenLifeStage | None = None
    matched: bool | None = None


class LiurenLifeStages(PartialOutput):
    ruleset_id: Literal["tanyuan_ten_stem_life_stages_v1"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    original_pdf_pages: list[int] | None = None
    day_stem: str | None = None
    direction: Literal["顺", "逆"] | None = None
    changsheng_branch: str | None = None
    linguan_branch: str | None = None
    tomb_branch: str | None = None
    stage_by_branch: dict[str, LiurenLifeStage] | None = None
    placements: list[LiurenLifePlacement] | None = None
    scope: str | None = None


class OrderedPatternEvaluation(PartialOutput):
    id: Literal["zhuolun", "zhuyin", "xuangai"] | None = None
    name: Literal["斫轮", "铸印", "轩盖"] | None = None
    required_branches: list[Branch] | None = Field(
        default=None, min_length=3, max_length=3
    )
    matched: StrictBool | None = None


class LiurenOrderedPatterns(PartialOutput):
    ruleset_id: Literal["tanyuan_ordered_transmission_patterns_v1"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    original_pdf_pages: list[StrictInt] | None = None
    branches: list[Branch] | None = Field(default=None, min_length=3, max_length=3)
    evaluations: list[OrderedPatternEvaluation] | None = Field(
        default=None, min_length=3, max_length=3
    )
    matched_ids: list[Literal["zhuolun", "zhuyin", "xuangai"]] | None = None
    complete_classical_conformance: StrictBool | None = None
    scope: str | None = None

    @model_validator(mode="before")
    @classmethod
    def conformance_is_boolean_false(
        cls, value: JsonValue | BaseModel
    ) -> JsonValue | BaseModel:
        return value

    @model_validator(mode="after")
    def literal_ledger_and_order_agree(self) -> "LiurenOrderedPatterns":
        actual = self.model_dump(exclude_unset=True)
        expected = ordered_transmission_patterns(list(self.branches or ["子"] * 3))
        if self.branches is None:
            expected.pop("branches", None)
            expected.pop("matched_ids", None)
            evals = expected.get("evaluations")
            if isinstance(evals, list):
                for row in evals:
                    if isinstance(row, dict):
                        row.pop("matched", None)
        compare_present_branches(actual, expected)
        return self


def require_complete_ordered_patterns(board: Mapping[str, object]) -> None:
    transmissions = _get_dict(board, "three_transmissions")
    branches: list[str] = []
    for p in ("initial", "middle", "final"):
        b = _get_str(transmissions.get(p), "branch")
        if b is None:
            raise ValueError("完整传序课体依据缺项或与本课初中末传不一致")
        branches.append(b)
    expected = ordered_transmission_patterns(branches)
    value = _get_dict(board, "transmission_relations").get("named_structures")
    if value != expected:
        raise ValueError("完整传序课体依据缺项或与本课初中末传不一致")


class LiurenProgression(PartialOutput):
    ruleset_id: Literal["tanyuan_transmission_progression_v1"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    original_pdf_pages: list[StrictInt] | None = None
    day_ganzhi: str | None = None
    branches: list[Branch] | None = None
    steps: list[StrictInt] | None = None
    kind: Literal["连茹", "间断"] | None = None
    structure_matched: StrictBool | None = None
    sequence_direction: Literal["进", "退"] | None = None
    empty_branches: list[Branch] | None = None
    branch_xun_kong: list[StrictBool] | None = None
    raw_branch_empty_conditional_reading: (
        Literal[
            "初空进退受阻",
            "末空以退论",
            "末空以进言",
            "按支序进读",
            "按支序退读",
            "见空不拘原进退说",
            "前进多阻",
            "后退有妨",
        ]
        | None
    ) = None
    raw_branch_empty_conditional_direction: Literal["进", "退"] | None = None
    empty_assumption: str | None = None
    effective_direction: None = None
    comprehensive_judgement: None = None
    complete_classical_conformance: StrictBool | None = None
    scope: str | None = None

    @model_validator(mode="before")
    @classmethod
    def boolean_false_conformance(
        cls, value: JsonValue | BaseModel
    ) -> JsonValue | BaseModel:
        return value

    @model_validator(mode="after")
    def consistent_progression(self) -> "LiurenProgression":
        for name, size in (
            ("branches", 3),
            ("steps", 2),
            ("empty_branches", 2),
            ("branch_xun_kong", 3),
        ):
            value = getattr(self, name)
            if value is not None and len(value) != size:
                raise ValueError("三传进退依据队列长度不符")
        if self.day_ganzhi is not None and self.branches is not None:
            compare_present_branches(
                self.model_dump(exclude_unset=True),
                transmission_progression(self.day_ganzhi, list(self.branches)),
            )
        return self


def align_progression(board: object, pillars: object = None) -> None:
    evidence = _get(board, "transmission_progression")
    if evidence is None:
        return
    day = _get(evidence, "day_ganzhi")
    if pillars is not None:
        a, b = _get(_get(pillars, "day"), "stem"), _get(_get(pillars, "day"), "branch")
        if (
            isinstance(a, str)
            and isinstance(b, str)
            and day is not None
            and day != a + b
        ):
            raise ValueError("三传进退与同次四柱日干支不符")
    for name in (
        "calendar_policy",
        "emptiness_evidence",
        "branch_relations",
        "transmission_relations",
    ):
        own = _get(
            _get(board, name),
            "effective_day_ganzhi" if name == "calendar_policy" else "day_ganzhi",
        )
        if day is not None and own is not None and day != own:
            raise ValueError("三传进退日干支与本课其他依据不符")
    branches = _get(evidence, "branches")
    flags = _get(evidence, "branch_xun_kong")
    trans = _get(board, "three_transmissions")
    for i, name in enumerate(("initial", "middle", "final")):
        item = _get(trans, name)
        branch, empty = _get(item, "branch"), _get(item, "xun_kong")
        if isinstance(branches, list) and branch is not None and branches[i] != branch:
            raise ValueError("三传进退支序与本课三传不符")
        if isinstance(flags, list) and empty is not None and flags[i] != empty:
            raise ValueError("三传进退本空与本课三传不符")


def require_complete_progression(board: Mapping[str, object]) -> None:
    value = board.get("transmission_progression")
    if not isinstance(value, Mapping):
        raise ValueError("完整六壬输出缺少三传进退依据")
    day_ganzhi = _get_str(value, "day_ganzhi")
    branches = value.get("branches")
    if day_ganzhi is None or not isinstance(branches, list):
        raise ValueError("完整六壬输出缺少三传进退依据")
    expected = transmission_progression(day_ganzhi, [str(b) for b in branches])
    if dict(value) != expected:
        raise ValueError("完整三传进退依据缺项或与同次计算不符")
    align_progression(board)


def expected_selection(
    board: Mapping[str, object], day: str | None = None
) -> dict[str, object] | None:
    days = [day] if day is not None else []
    for name, key in (
        ("calendar_policy", "effective_day_ganzhi"),
        ("auxiliary_stars", "day_ganzhi"),
        ("transmission_relations", "day_ganzhi"),
        ("emptiness_evidence", "day_ganzhi"),
    ):
        value = board.get(name)
        if isinstance(value, Mapping):
            item = value.get(key)
            if isinstance(item, str):
                days.append(item)
            elif item is not None:
                raise ValueError("九宗门计算日干支依据不一致")
    if not days:
        return None
    if any(d not in SEXAGENARY_INDEX for d in days) or len(set(days)) != 1:
        raise ValueError("九宗门计算日干支依据不一致")
    rows = board.get("twelve_board")
    if not isinstance(rows, list) or len(rows) != 12:
        return None
    if any(not isinstance(r, Mapping) for r in rows):
        raise ValueError("九宗门天地盘行必须是对象")
    if any(r.get("earth_branch") is None or r.get("sky_branch") is None for r in rows):
        return None
    if any(
        not isinstance(r[k], str) for r in rows for k in ("earth_branch", "sky_branch")
    ):
        raise ValueError("九宗门天地盘须使用十二地支")
    sky = {str(r["earth_branch"]): str(r["sky_branch"]) for r in rows}
    if set(sky) != set(BRANCHES) or set(sky.values()) != set(BRANCHES):
        raise ValueError("九宗门需要完整且无重复的天地盘")
    offsets = {(BRANCHES.index(v) - BRANCHES.index(k)) % 12 for k, v in sky.items()}
    if len(offsets) != 1:
        raise ValueError("九宗门天地盘须为同一次顺布旋转盘")

    raw_meta = board.get("meta")
    meta = raw_meta if isinstance(raw_meta, Mapping) else {}
    shehai = meta.get("shehai_method", "depth_first")
    shehai_method: Literal["depth_first", "meng_zhong_first"] = (
        "meng_zhong_first" if shehai == "meng_zhong_first" else "depth_first"
    )
    return derive_selection(
        days[0],
        sky,
        shehai_method=shehai_method,
        harm_include_terminal=bool(meta.get("harm_include_terminal", False)),
    )


def require_shape(actual: object, expected: object) -> None:
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping) or set(expected) - set(actual):
            raise ValueError("完整九宗门输出缺少选课计算依据")
        for key, value in expected.items():
            require_shape(actual[key], value)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError("完整九宗门输出缺少完整队列")
        for a, e in zip(actual, expected):
            require_shape(a, e)


def validate_selection(
    board: Mapping[str, object], day: str | None = None, *, complete: bool = False
) -> None:
    selection = expected_selection(board, day)
    if selection is None:
        if complete:
            raise ValueError("完整九宗门输出缺少日干支或天地盘依据")
        return
    for key in ("four_lessons", "board_style", "board_style_detail", "classification"):
        if complete:
            if key not in board:
                raise ValueError("完整九宗门输出缺少取传字段")
            require_shape(board[key], selection[key])
        if key in board:
            compare_selection(board[key], selection[key])
    meta = board.get("meta")
    keys = ("selected_lesson_index", "selected_lesson_relation")
    wanted_meta = {key: selection[key] for key in keys}
    if complete:
        require_shape(meta, wanted_meta)
    if isinstance(meta, Mapping):
        compare_selection({key: meta[key] for key in keys if key in meta}, wanted_meta)
    transmissions = board.get("three_transmissions")
    labels = ("initial", "middle", "final")
    branches = selection["branches"]
    assert isinstance(branches, list)
    wanted_transmissions = {
        "method": selection["transmission_method"],
        **{label: {"branch": branch} for label, branch in zip(labels, branches)},
    }
    if complete:
        require_shape(transmissions, wanted_transmissions)
    if isinstance(transmissions, Mapping):
        present: dict[str, object] = {
            k: transmissions[k] for k in ("method",) if k in transmissions
        }
        for label in labels:
            if label in transmissions:
                row = transmissions[label]
                present[label] = (
                    {"branch": row["branch"]}
                    if isinstance(row, Mapping) and "branch" in row
                    else ({} if isinstance(row, Mapping) else row)
                )
        compare_selection(present, wanted_transmissions)


class LiurenNominalTrineSeasonal(PartialOutput):
    method_id: str | None = None
    source_url: str | None = None
    original_pdf_pages: list[int] | None = None
    corroborating_source_url: str | None = None
    corroborating_pdf_pages: list[int] | None = None
    month_partition_profile: str | None = None
    month_branch: Branch | None = None
    season_partition: Literal["春", "夏", "秋", "冬", "季月"] | None = None
    nominal_element: Literal["木", "火", "金", "水"] | None = None
    nominal_power: Power | None = None
    course_component: Literal["得势", "失时", "将来", "既往"] | None = None
    full_named_course_adjudicated: bool | None = None
    transformation_confirmed: None = None
    scope: str | None = None

    @model_validator(mode="before")
    @classmethod
    def no_certificate_coercion(
        cls, value: JsonValue | BaseModel
    ) -> JsonValue | BaseModel:
        return value

    @model_validator(mode="after")
    def keep_selected_nominal_facts(self) -> "LiurenNominalTrineSeasonal":
        present = self.model_dump(exclude_unset=True)
        for key, expected in nominal_seasonal_metadata().items():
            if key in present and present[key] != expected:
                raise ValueError("名义局体季态的来源或适用范围不符")
        season = (
            MONTH_PARTITION[self.month_branch]
            if self.month_branch
            else self.season_partition
        )
        if self.season_partition is not None and season != self.season_partition:
            raise ValueError("名义局体季态与所选月建季节不符")
        if season is not None and self.nominal_element is not None:
            expected_power = POWERS[season][self.nominal_element]
            if self.nominal_power is not None and self.nominal_power != expected_power:
                raise ValueError("名义局体五态与该局体五行和季节不符")
            if (
                self.course_component is not None
                and self.course_component != _TRINE_COMPONENTS[expected_power]
            ):
                raise ValueError("名义局体课体组件与所选五态不符")
        if (
            self.nominal_power is not None
            and self.course_component is not None
            and self.course_component != _TRINE_COMPONENTS[self.nominal_power]
        ):
            raise ValueError("名义局体课体组件与同时返回五态不符")
        return self


def require_complete_nominal_seasonal(board: object) -> None:
    if not isinstance(board, Mapping):
        raise ValueError("完整名义局体季态需要本课对象")
    seasonal = _get_dict(board, "seasonal_evidence")
    month = seasonal.get("month_branch")
    transmissions = _get_dict(board, "three_transmissions")
    branches = [
        _get(transmissions.get(p), "branch") for p in ("initial", "middle", "final")
    ]
    trines = _get_dict(board, "transmission_relations").get("trines")
    if (
        not isinstance(month, str)
        or not all(isinstance(b, str) for b in branches)
        or not isinstance(trines, list)
        or len(trines) != 4
    ):
        raise ValueError("完整名义局体季态需要同次月建和三传及四局清单")
    branch_set = {str(b) for b in branches}
    for trine in trines:
        if not isinstance(trine, Mapping):
            raise ValueError("完整三合局体须保留同次月建及三传的名义季态与可空事实")
        t_branches = trine.get("branches")
        t_elem = trine.get("nominal_element")
        expected = (
            nominal_seasonal_evidence(month, str(t_elem))
            if isinstance(t_branches, list) and set(t_branches) == branch_set
            else None
        )
        if (
            "nominal_seasonal_evidence" not in trine
            or trine["nominal_seasonal_evidence"] != expected
        ):
            raise ValueError("完整三合局体须保留同次月建及三传的名义季态与可空事实")


class TransmissionRelationRow(PartialOutput):
    position: Literal["initial", "middle", "final"] | None = None
    branch: str | None = None
    element: Phase | None = None
    god: str | None = None
    god_element: Phase | None = None
    god_to_spirit: Literal["比和", "生", "受生", "克", "受克"] | None = None
    war: Literal["内战", "外战"] | None = None
    earth_branch: str | None = None
    earth_element: Phase | None = None
    spirit_to_seat: Literal["比和", "生", "受生", "克", "受克"] | None = None
    day_relation: Literal["兄弟", "父母", "子孙", "妻财", "官鬼"] | None = None
    day_stem_life_stage: str | None = None
    xun_kong: StrictBool | None = None

    @model_validator(mode="after")
    def phase_facts_agree(self) -> "TransmissionRelationRow":
        for branch, element in (
            (self.branch, self.element),
            (self.earth_branch, self.earth_element),
        ):
            if (
                branch is not None
                and element is not None
                and branch_element_text(branch) != element
            ):
                raise ValueError("三传支神或承座五行与本支不一致")
        if (
            self.god is not None
            and self.god_element is not None
            and GOD_ELEMENTS.get(self.god) != self.god_element
        ):
            raise ValueError("三传天将固有五行不一致")
        if self.god_element is not None and self.element is not None:
            expected = phase_relation(self.god_element, self.element)
            if self.god_to_spirit is not None and self.god_to_spirit != expected:
                raise ValueError("三传神将生克方向不一致")
            war = {"克": "外战", "受克": "内战"}.get(expected)
            if "war" in self.model_fields_set and self.war != war:
                raise ValueError("三传内外战与神将五行方向不一致")
        return self


class TransmissionRelationRule(PartialOutput):
    id: str | None = None
    name: str | None = None
    matched: StrictBool | None = None


class TransmissionTrine(PartialOutput):
    branches: list[str] | None = None
    present_branches: list[str] | None = None
    missing_branches: list[str] | None = None
    nominal_element: Phase | None = None
    branches_complete: StrictBool | None = None
    nominal_day_relation: str | None = None
    transformation_confirmed: None = None
    nominal_seasonal_evidence: LiurenNominalTrineSeasonal | None = None

    @model_validator(mode="after")
    def nominal_seasonal_subject(self) -> "TransmissionTrine":
        evidence = self.nominal_seasonal_evidence
        if evidence is not None:
            if self.branches_complete is False:
                raise ValueError("三合支未齐不能给出已成名义局体的季态")
            if (
                self.nominal_element is not None
                and evidence.nominal_element is not None
                and self.nominal_element != evidence.nominal_element
            ):
                raise ValueError("三合名义季态不能替换本局体五行")
        return self


class LiurenTransmissionRelations(PartialOutput):
    ruleset_id: Literal["liuren_tanyuan_transmission_relations_v1"] | None = None
    source_url: str | None = None
    original_pdf_pages: list[int] | None = None
    day_ganzhi: str | None = None
    day_element: Phase | None = None
    rows: list[TransmissionRelationRow] | None = Field(
        default=None, min_length=3, max_length=3
    )
    rules: list[TransmissionRelationRule] | None = Field(
        default=None, min_length=9, max_length=9
    )
    matched_rule_ids: list[str] | None = None
    origin_destinations_coincide: StrictBool | None = None
    trines: list[TransmissionTrine] | None = Field(
        default=None, min_length=4, max_length=4
    )
    named_structures: LiurenOrderedPatterns | None = None
    course_conditions: LiurenCourseConditions | None = None
    all_transmissions_in_lesson_uppers: StrictBool | None = None
    all_transmissions_in_day_branch_uppers: StrictBool | None = None
    two_branch_empty: StrictBool | None = None
    solid_transmission_has_sky_god: StrictBool | None = None
    any_transmission_has_sky_god: StrictBool | None = None
    equivalent_three_empty_adjudicated: None = None
    comprehensive_judgement: None = None
    complete_classical_conformance: StrictBool | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def fixed_ledger_agrees(self) -> "LiurenTransmissionRelations":
        if self.day_ganzhi is not None:
            if self.day_ganzhi not in SEXAGENARY_INDEX:
                raise ValueError("三传关系需要有效日干支")
            day = stem_element_text(self.day_ganzhi[0])
            if self.day_element is not None and self.day_element != day:
                raise ValueError("三传关系日干五行不一致")
            stages = life_stage_cycle(self.day_ganzhi[0])
            for row in self.rows or []:
                if row.branch is None:
                    continue
                if (
                    row.day_stem_life_stage is not None
                    and row.day_stem_life_stage != stages.get(row.branch)
                ):
                    raise ValueError("三传生墓与本次日干十二运不一致")
                if row.xun_kong is not None and row.xun_kong != (
                    row.branch in kongwang_for_ganzhi(self.day_ganzhi)[:2]
                ):
                    raise ValueError("三传本空与占日旬空不一致")
                if (
                    row.element is not None
                    and row.day_relation is not None
                    and row.day_relation != liuqin_against_day(day, row.element)
                ):
                    raise ValueError("三传六亲没有采用支神本五行")
        if self.rows is not None and [r.position for r in self.rows] != [
            "initial",
            "middle",
            "final",
        ]:
            raise ValueError("三传关系必须保留初中末三位")
        if self.rows is not None and self.named_structures is not None:
            if all(r.branch is not None for r in self.rows):
                compare_present_relations(
                    self.named_structures.model_dump(exclude_unset=True),
                    ordered_transmission_patterns(
                        [r.branch for r in self.rows if r.branch is not None]
                    ),
                )
        if (
            self.course_conditions is not None
            and self.day_ganzhi is not None
            and self.rows is not None
        ):
            if all(
                r.branch is not None
                and r.god is not None
                and r.earth_branch is not None
                for r in self.rows
            ):
                compare_present_relations(
                    self.course_conditions.model_dump(exclude_unset=True),
                    course_conditions(
                        self.day_ganzhi,
                        {
                            str(r.position): dict(
                                branch=r.branch, god=r.god, earth_branch=r.earth_branch
                            )
                            for r in self.rows
                        },
                    ),
                )
        if self.rules is not None:
            if [r.id for r in self.rules] != [i for i, _ in RULE_NAMES]:
                raise ValueError("三传九条结构账本不能遗漏、重复或调序")
            if self.matched_rule_ids is not None and all(
                r.matched is not None for r in self.rules
            ):
                if self.matched_rule_ids != [r.id for r in self.rules if r.matched]:
                    raise ValueError("三传结构命中摘要与逐条账本不一致")
        return self


class LiurenYearFatePlacement(PartialOutput):
    status: Literal["calculated", "not_calculated"] | None = None
    subject_ganzhi: str | None = None
    earth_branch: str | None = None
    sky_branch: str | None = None
    god: str | None = None
    upper_dun_stem: str | None = None
    upper_ganzhi: str | None = None
    upper_relation: str | None = None
    upper_xun_kong: bool | None = None
    earth_xun_kong: bool | None = None
    reason: str | None = None


class LiurenYearFate(PartialOutput):
    ruleset_id: Literal["tanyuan_year_fate_v1"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    original_pdf_pages: list[int] | None = None
    birth_year_basis: str | None = None
    placement_basis: str | None = None
    day_ganzhi: str | None = None
    guiren_profile: str | None = None
    natal: LiurenYearFatePlacement | None = None
    annual: LiurenYearFatePlacement | None = None
    scope: str | None = None


class LiurenLesson(PartialOutput):
    anchor_branch: str | None = None
    index: int | None = None
    lower_branch: str | None = None
    upper_branch: str | None = None
    upper_day_stem_life_stage: LiurenLifeStage | None = None
    relation: str | None = None
    relations: dict[str, str] | None = Field(
        default=None,
        description="兼容优先标签仅列同支、合、冲、害；平不表示无刑破。并存支位条件见liuren.branch_relations。",
    )
    style_basis: str | None = None
    style_hint: str | None = None
    text: str | None = None
    upper_lower_relation: str | None = None
    use_candidate: bool | None = None


class LiurenTransmission(PartialOutput):
    branch: str | None = None
    ganzhi: str | None = None
    god: str | None = None
    relation: str | None = None
    dun_stem: str | None = None
    xun_kong: bool | None = None
    earth_branch: str | None = None
    seated_kong: bool | None = None
    day_stem_life_stage: LiurenLifeStage | None = None
    seated_day_stem_life_stage: LiurenLifeStage | None = None


class LiurenTransmissions(PartialOutput):
    initial: LiurenTransmission | None = None
    middle: LiurenTransmission | None = None
    final: LiurenTransmission | None = None
    method: str | None = None


class LiurenBoardRow(PartialOutput):
    earth_branch: str | None = None
    sky_branch: str | None = None
    god: str | None = None


class LiurenPattern(PartialOutput):
    basis: str | None = None
    name: str | None = None


class RenDiurnalEvidence(PartialOutput):
    method_id: str | None = None
    hour_branch: str | None = None
    explicit_choice: bool | None = None
    is_diurnal: bool | None = None
    selection_source: str | None = None
    fixed_day_branches: list[str] | None = None
    stellar_visibility_observed: None = None
    astronomical_boundary_computed: bool | None = None
    solar_altitude_threshold_degrees: float | None = None
    basis: str | None = None
    scope: str | None = None


class LiurenMeta(PartialOutput):
    guiren_profile: str | None = None
    current_term: str | None = None
    month_general_basis: str | None = None
    guiren_earth_branch: str | None = None
    is_diurnal: bool | None = None
    lunar_display: str | None = None
    questioner_gender: str | None = None
    selected_lesson_index: int | None = None
    selected_lesson_relation: str | None = None
    diurnal_basis: str | None = None
    diurnal_evidence: RenDiurnalEvidence | None = None


class RenRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    source_title: str | None = None
    source_urls: list[str] | None = None
    source_kind: str | None = None
    classical_conformance: str | None = None
    classical_acceptance_passed: bool | None = None
    unresolved: list[str] | None = None


class LiurenSourceNote(PartialOutput):
    annotation: str | None = None
    original_pdf_page: int | None = None
    source_url: str | None = None
    kind: str | None = None
    explanation: str | None = None
    scope: str | None = None


class LiurenClassification(PartialOutput):
    ruleset_id: str | None = None
    source_url: str | None = None
    source_section: str | None = None
    labels: list[str] | None = None
    detail: str | None = None
    transmission_method: str | None = None
    lower_thief_lessons: list[int] | None = None
    upper_killer_lessons: list[int] | None = None
    initial_self_punishment: bool | None = None
    closing_punishment: bool | None = None
    selected_lesson: int | None = None
    basis: str | None = None
    scope: str | None = None
    source_note: LiurenSourceNote | None = None


class RenTermDependency(PartialOutput):
    published_date_reference: RenPublishedDateReference | None = None
    role: str | None = None
    name: str | None = None
    civil_moment: str | None = None
    local_clock_status: Literal["undefined"] | None = None
    provider: str | None = None
    ephemeris_model: str | None = None
    ephemeris_retflags: list[int] | None = None
    ephemeris_library_version: str | None = None
    solar_model_details: dict[str, OpenJsonValue] | None = None
    solver_time_scale: str | None = None
    civil_time_method: str | None = None
    future_leap_seconds_assumed_unchanged: bool | None = None
    leap_table_expires_at: str | None = None

    @model_validator(mode="after")
    def published_date_matches_dependency(self) -> "RenTermDependency":
        align_published_date(self)
        return self


class RenSolarLongitudeDefinition(PartialOutput):
    origin: Literal["geocentric"] | None = None
    position: Literal["apparent"] | None = None
    plane: Literal["ecliptic_of_date"] | None = None
    equinox: Literal["true_of_date"] | None = None
    astronomical_model: (
        Literal[
            "Swiss_Ephemeris_default_IERS2010_Astronomical_Almanac",
            "fatebridge_analytic_solar_v1",
            "per_dependency_named_models",
        ]
        | None
    ) = None
    horizons_frame_equivalence_certified: Literal[False] | None = None
    source_url: str | None = None
    source_section: str | None = None
    scope: str | None = None


class RenCalendarPolicy(PartialOutput):
    mode: str | None = None
    civil_datetime: str | None = None
    civil_instant_utc: str | None = None
    civil_clock_resolution: RenCivilClockResolution | None = None
    day_hour_clock: str | None = None
    corrected_clock: str | None = None
    day_boundary: str | None = None
    effective_day_date: str | None = None
    effective_day_ganzhi: str | None = None
    year_month_clock: str | None = None
    month_general_clock: str | None = None
    month_general_override: str | None = None
    month_boundary: str | None = None
    month_general_boundary: str | None = None
    solar_term_dependencies: list[RenTermDependency] | None = None
    solar_longitude_definition: RenSolarLongitudeDefinition | None = None
    precision_status: str | None = None
    scope: str | None = None


class Liuren(PartialOutput):
    god_yin: LiurenGodYin | None = None
    seasonal_evidence: LiurenSeasonalEvidence | None = None
    transmission_progression: LiurenProgression | None = None
    branch_relations: LiurenBranchRelations | None = None
    day_placement_patterns: LiurenDayPlacements | None = None
    cross_harmony: LiurenCrossHarmony | None = None
    emptiness_evidence: LiurenEmptinessEvidence | None = None
    transmission_relations: LiurenTransmissionRelations | None = None
    engine: str | None = None
    board_order: str | None = None
    board_style: str | None = None
    board_style_detail: str | None = None
    guiren_system: str | None = None
    kongwang: str | None = None
    meta: LiurenMeta | None = None
    month_general: BranchName | None = None
    overview: list[str] | None = None
    patterns: list[LiurenPattern] | None = None
    four_lessons: list[LiurenLesson] | None = None
    three_transmissions: LiurenTransmissions | None = None
    twelve_board: list[LiurenBoardRow] | None = None
    month_building_element: str | None = None
    life_stages: LiurenLifeStages | None = None
    auxiliary_stars: LiurenAuxiliaryStars | None = None
    xun_head: str | None = None
    guiren_order: str | None = None
    ruleset: RenRuleset | None = None
    classification: LiurenClassification | None = None
    calendar_policy: RenCalendarPolicy | None = None
    birth_year_derivation: dict[str, OpenJsonValue] | None = None

    @model_validator(mode="after")
    def yin_matches_its_board(self) -> "Liuren":
        align_god_yin(self)
        return self

    @model_validator(mode="after")
    def selection_follows_present_board(self, info: ValidationInfo) -> "Liuren":
        if not (info.context and info.context.get("full_result")):
            validate_selection(self.model_dump(exclude_unset=True))
        return self

    @model_validator(mode="after")
    def branch_relations_match_present_board(self) -> "Liuren":
        align_seasonal(self)
        align_branch_relations(self)
        align_day_placements(self)
        align_cross_harmony(self)
        align_progression(self)
        return self

    @model_validator(mode="after")
    def empty_evidence_matches_present_board(self) -> "Liuren":
        evidence = self.emptiness_evidence
        if evidence is None or evidence.rows is None:
            return self
        by_earth = {r.earth_branch: r for r in evidence.rows}
        by_sky = {r.sky_branch: r for r in evidence.rows}
        for row in self.twelve_board or []:
            if row.earth_branch is not None and row.sky_branch is not None:
                if (
                    row.earth_branch not in by_earth
                    or by_earth[row.earth_branch].sky_branch != row.sky_branch
                ):
                    raise ValueError("六壬空亡依据与同时返回的天地盘不一致")
        if self.three_transmissions is not None:
            for position in ("initial", "middle", "final"):
                item = getattr(self.three_transmissions, position)
                if item is None or item.branch is None:
                    continue
                if item.branch not in by_sky:
                    raise ValueError("六壬空亡依据中的三传支位无效")
                empty_row = by_sky[item.branch]
                for name, expected in (
                    ("earth_branch", empty_row.earth_branch),
                    ("xun_kong", empty_row.sky_xun_kong),
                    ("seated_kong", empty_row.earth_xun_kong),
                ):
                    actual = getattr(item, name)
                    if actual is not None and actual != expected:
                        raise ValueError("六壬空亡依据与同时返回的三传不一致")
        return self

    @model_validator(mode="after")
    def transmission_relationships_match_same_board(self) -> "Liuren":
        if self.transmission_relations and self.seasonal_evidence:
            month = self.seasonal_evidence.month_branch
            for trine in self.transmission_relations.trines or []:
                if month and trine.nominal_element and trine.nominal_seasonal_evidence:
                    compare_present_relations(
                        trine.nominal_seasonal_evidence.model_dump(exclude_unset=True),
                        nominal_seasonal_evidence(month, trine.nominal_element),
                    )
        if (
            self.transmission_relations is None
            or self.four_lessons is None
            or self.three_transmissions is None
        ):
            return self
        day = self.transmission_relations.day_ganzhi
        if day is None or any(
            lesson.index is None or lesson.upper_branch is None
            for lesson in self.four_lessons
        ):
            return self
        transmissions = self.three_transmissions.model_dump(exclude_unset=True)
        if any(
            not isinstance(transmissions.get(p), dict)
            or any(k not in transmissions[p] for k in ("branch", "god", "earth_branch"))
            for p in ("initial", "middle", "final")
        ):
            return self

        expected = transmission_relations(
            day_ganzhi=day,
            lessons=[
                lesson.model_dump(exclude_unset=True) for lesson in self.four_lessons
            ],
            transmissions=transmissions,
            month_branch=(
                self.seasonal_evidence.month_branch if self.seasonal_evidence else None
            ),
        )
        compare_present_relations(
            self.transmission_relations.model_dump(exclude_unset=True), expected
        )
        return self


class Runyear(PartialOutput):
    age: int | None = None
    engine: str | None = None
    ganzhi: str | None = None
    gender: str | None = None
    age_basis: str | None = None
    rule_id: str | None = None
    source_url: str | None = None
    source_section: str | None = None
    birth_lunar_year: int | None = None
    birth_civil_clock: RenCivilClockResolution | None = None
    year_fate: LiurenYearFate | None = None
    age_calendar: RenRunyearAgeCalendar | None = None
    status: str | None = None
    reason: str | None = None
