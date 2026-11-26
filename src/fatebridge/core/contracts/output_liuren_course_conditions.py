"""Projection-compatible contracts and same-board guards for literal clauses."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, JsonValue, StrictBool, StrictInt, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_liuren_branches import compare_present_branches
from fatebridge.core.contracts.output_liuren_emptiness import Branch
from fatebridge.core.metaphysics.common import SEXAGENARY_INDEX
from fatebridge.core.metaphysics.liureng_course_conditions import (
    course_conditions,
    course_conditions_trace,
)
from fatebridge.core.metaphysics.liureng_course_layout import layout_compatibility_basis
from fatebridge.core.metaphysics.liureng_life_stages import life_stage_cycle


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
    initial_god: str | None = None
    initial_earth_branch: Branch | None = None
    initial_stage: str | None = None
    day_stem_house: Branch | None = None
    xun_head_branch: Branch | None = None
    xun_tail_branch: Branch | None = None
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
    complete_classical_conformance: Literal[False] | None = None
    scope: str | None = None

    @model_validator(mode="before")
    @classmethod
    def conformance_is_false(
        cls, value: JsonValue | BaseModel
    ) -> JsonValue | BaseModel:
        if (
            isinstance(value, dict)
            and value.get("complete_classical_conformance") is not None
        ):
            if value["complete_classical_conformance"] is not False:
                raise ValueError("课体条件不认证完整原典，须为布尔false")
        return value

    @model_validator(mode="after")
    def present_facts_agree(self) -> LiurenCourseConditions:

        if self.day_ganzhi is not None and self.day_ganzhi not in SEXAGENARY_INDEX:
            raise ValueError("课体条件需要有效日干支")
        inputs = (
            self.day_ganzhi,
            self.branches,
            self.initial_god,
            self.initial_earth_branch,
        )
        complete = all(v is not None for v in inputs)
        expected = course_conditions(
            self.day_ganzhi or "甲子",
            {
                p: dict(
                    branch=(self.branches or ["子"] * 3)[i],
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
                "initial_god",
                "initial_earth_branch",
                "initial_stage",
                "day_stem_house",
                "xun_head_branch",
                "xun_tail_branch",
                "matched_ids",
            ):
                expected.pop(k)
            for group in ("stage_god_patterns", "god_patterns", "structural_patterns"):
                for row in expected[group]:
                    for k in ("matched", "stage_matches", "god_matches", "checks"):
                        row.pop(k, None)
        if self.day_ganzhi is None:
            for row in expected["stage_god_patterns"]:
                for k in (
                    "required_stage_branch",
                    "possible_god_branches",
                    "compatible_in_any_supported_noble_layout",
                ):
                    row.pop(k)
        compare_present_branches(self.model_dump(exclude_unset=True), expected)
        # Some projections include enough inputs for a smaller independent check.
        if self.day_ganzhi is not None:

            if self.branches is not None and self.initial_stage is not None:
                if (
                    self.initial_stage
                    != life_stage_cycle(self.day_ganzhi[0])[self.branches[0]]
                ):
                    raise ValueError("初传十二运与本课日干不一致")
        return self


def require_complete_course_conditions(board: dict[str, Any]) -> None:

    day = board.get("calendar_policy", {}).get("effective_day_ganzhi")
    expected = course_conditions(day, board.get("three_transmissions", {}))
    actual = board.get("transmission_relations", {}).get("course_conditions")
    canonical = lambda v: json.dumps(
        v, ensure_ascii=False, sort_keys=True, allow_nan=False
    )
    if canonical(actual) != canonical(expected):
        raise ValueError("完整课体条件缺项或与本课日干支、三传天将承座不一致")
    relations = board.get("transmission_relations", {})
    if relations.get("day_ganzhi") != day:
        raise ValueError("课体条件与同次三传关系日干支不一致")
    rows = relations.get("rows")
    if not isinstance(rows, list) or len(rows) != 3:
        raise ValueError("课体条件需要同次完整三传关系")
    for i, row in enumerate(rows):
        p = ("initial", "middle", "final")[i]
        recorded = board["three_transmissions"][p]
        for field in ("branch", "god", "earth_branch"):
            if row.get(field) != recorded[field]:
                raise ValueError("课体条件不能借用另一课三传事实")
    traces = [
        t
        for t in board.get("rule_trace", [])
        if t.get("rule_id") == "liuren.course_conditions"
    ]
    if canonical(traces) != canonical([course_conditions_trace(expected)]):
        raise ValueError("课体条件轨迹缺项、重复或与本课不一致")
