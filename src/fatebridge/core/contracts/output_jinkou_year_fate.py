"""Jinkou natal and annual-fate output contracts."""

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_jinkou_board import JinkouCourse
from fatebridge.core.contracts.output_jinkou_natal_course import validate_natal_course
from fatebridge.core.metaphysics.jinkou.year_fate import (
    confirmed_natal_branch,
    ordinal_year_fate,
)


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
    def ordinal_and_course_agree(self) -> "JinkouYearFate":

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
    def natal_course_follows_confirmed_input(self) -> "JinkouNatalCourse":

        validate_natal_course({"natal_course": self.model_dump(exclude_unset=True)})
        return self


class Jinkou(JinkouCourse):
    year_fate: JinkouYearFate | None = None
    natal_course: JinkouNatalCourse | None = None

    @model_validator(mode="after")
    def natal_course_keeps_analysis_facts(self) -> "Jinkou":

        validate_natal_course(self.model_dump(exclude_unset=True))
        return self

    @model_validator(mode="after")
    def annual_course_keeps_analysis_facts(self) -> "Jinkou":
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

        def agree(a: Any, b: Any) -> bool:
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
            for key in (
                "month_general",
                "is_diurnal",
                "diurnal_basis",
                "diurnal_evidence",
            ):
                a = self.overview.model_dump(exclude_unset=True)
                b = child.overview.model_dump(exclude_unset=True)
                if key in a and key in b and not agree(a[key], b[key]):
                    raise ValueError("行年另课须保留本次月将与显式昼夜选择")
        return self
