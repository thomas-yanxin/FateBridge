"""Three-state records of the selected Jin Kou structural definitions.

These validate calculation results, not the completeness of an original text.
An unresolved source definition must never acquire a false/true verdict.
"""

from typing import Any, Literal

from pydantic import (
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.metaphysics.jinkou.patterns import (
    pattern_identity,
    pattern_metadata,
)


def _identity(value: Any, keys: tuple[str, ...]) -> dict[str, Any] | None:
    if value.id is None:
        return None

    expected = pattern_identity(value.id)
    for key in keys:
        if key in value.model_fields_set and getattr(value, key) != expected[key]:
            raise ValueError("课钤ID所指课名、页码或条件与所选定义不一致")
    return expected


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
    def validate_present_atomic_calculation(self) -> "JinkouPatternFact":
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
    def preserve_three_states(self) -> "JinkouPatternEvaluation":
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
        # A field projection may contain only one fact. Validate their
        # relationship only when both were actually supplied.
        if {"status", "matched"} <= self.model_fields_set:
            expected = {
                "matched": True,
                "not_matched": False,
                "unresolved_definition": None,
                "input_unavailable": None,
            }
            if self.status in expected and self.matched is not expected[self.status]:
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
    def preserve_selected_identity(self) -> "JinkouPatternMatch":
        _identity(self, ("name", "alias", "original_pdf_page", "condition"))
        return self


class JinkouUnresolvedPattern(PartialOutput):
    id: str | None = Field(default=None, pattern=r"^P(?:0[1-9]|[1-5][0-9]|6[0-4])$")
    name: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def preserve_selected_identity(self) -> "JinkouUnresolvedPattern":
        expected = _identity(self, ("name",))
        if expected is not None and expected["unresolved"]:
            _identity(self, ("reason",))
        return self


def _distinct_ids(items: list[Any], label: str) -> set[str]:
    ids = [item.id for item in items]
    if any(not isinstance(value, str) for value in ids) or len(set(ids)) != len(ids):
        raise ValueError(f"六十四课钤{label}缺少ID或ID重复")
    return set(ids)


class JinkouPatterns(PartialOutput):
    ruleset_id: str | None = None
    source_url: str | None = None
    source_section: str | None = None
    catalog_count: int | None = Field(default=None, ge=64, le=64)
    evaluated_rule_count: int | None = Field(default=None, ge=0, le=64)
    condition_logic: Literal["any_of_all_v1"] | None = None
    condition_facts: list[JinkouPatternFact] | None = None
    # Object projections may omit this array, but never shorten its items or
    # remove entries. The source catalog, including unresolved entries, is 64.
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
    def preserve_ledger_integrity(self) -> "JinkouPatterns":
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
