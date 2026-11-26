"""Projection-compatible, source-scoped transmission relationships."""

from typing import Literal

from pydantic import Field, StrictBool, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_liuren_course_conditions import (
    LiurenCourseConditions,
)
from fatebridge.core.contracts.output_liuren_ordered_patterns import (
    LiurenOrderedPatterns,
)
from fatebridge.core.contracts.output_liuren_trine_seasonal import (
    LiurenNominalTrineSeasonal,
)
from fatebridge.core.metaphysics.common import (
    SEXAGENARY_INDEX,
    branch_element_text,
    kongwang_for_ganzhi,
    liuqin_against_day,
    stem_element_text,
)
from fatebridge.core.metaphysics.liureng.stars import GOD_ELEMENTS, life_stage_cycle
from fatebridge.core.metaphysics.liureng.transmissions import (
    RULE_NAMES,
    course_conditions,
    ordered_transmission_patterns,
    phase_relation,
    transmission_relations,
)

Phase = Literal["木", "火", "土", "金", "水"]


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


def compare_present_relations(actual: object, expected: object) -> None:
    if isinstance(actual, dict) and isinstance(expected, dict):
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
