"""Three-state records of the selected Jin Kou structural definitions.

These validate calculation results, not the completeness of an original text.
An unresolved source definition must never acquire a false/true verdict.
"""

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import (
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from .output_base import PartialOutput


def _identity(value: Any, keys: tuple[str, ...]) -> dict[str, Any] | None:
    if value.id is None:
        return None
    from .metaphysics.jinkou_patterns import pattern_identity

    expected = pattern_identity(value.id)
    for key in keys:
        if key in value.model_fields_set and getattr(value, key) != expected[key]:
            raise ValueError("课钤ID所指课名、页码或条件与所选定义不一致")
    return expected


class JinkouPatternFact(PartialOutput):
    id: Optional[str] = None
    operation: Optional[
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
    ] = None
    description: Optional[str] = None
    operands: Optional[
        Dict[
            str,
            Optional[
                Union[StrictStr, StrictBool, StrictInt, List[Optional[StrictStr]]]
            ],
        ]
    ] = None
    reference: Optional[List[StrictStr]] = None
    matched: Optional[StrictBool] = None

    @model_validator(mode="after")
    def validate_present_atomic_calculation(self) -> "JinkouPatternFact":
        if self.operation is None or self.operands is None:
            return self
        from .metaphysics.jinkou_pattern_proofs import evaluate_fact

        try:
            result, reference = evaluate_fact(self.operation, self.operands)
        except (KeyError, IndexError, TypeError, StopIteration) as error:
            raise ValueError("课钤条件输入不完整或不合法") from error
        if "matched" in self.model_fields_set and self.matched is not result:
            raise ValueError("课钤原子条件与自身计算输入不符")
        if "reference" in self.model_fields_set and self.reference != reference:
            raise ValueError("课钤原子条件的查表依据不符")
        return self


class JinkouPatternRequirement(PartialOutput):
    fact_id: Optional[str] = None
    expected: Optional[StrictBool] = None


class JinkouPatternEvaluation(PartialOutput):
    id: Optional[str] = Field(default=None, pattern=r"^P(?:0[1-9]|[1-5][0-9]|6[0-4])$")
    name: Optional[str] = None
    original_pdf_page: Optional[int] = None
    status: Optional[
        Literal["matched", "not_matched", "unresolved_definition", "input_unavailable"]
    ] = None
    matched: Optional[bool] = None
    condition: Optional[str] = None
    reason: Optional[str] = None
    condition_groups: Optional[List[List[JinkouPatternRequirement]]] = None

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
    matched: Optional[int] = Field(default=None, ge=0, le=64)
    not_matched: Optional[int] = Field(default=None, ge=0, le=64)
    unresolved: Optional[int] = Field(default=None, ge=0, le=64)


class JinkouPatternMatch(PartialOutput):
    id: Optional[str] = Field(default=None, pattern=r"^P(?:0[1-9]|[1-5][0-9]|6[0-4])$")
    name: Optional[str] = None
    alias: Optional[str] = None
    original_pdf_page: Optional[int] = None
    reading: Optional[str] = None
    basis: Optional[str] = None
    condition: Optional[str] = None

    @model_validator(mode="after")
    def preserve_selected_identity(self) -> "JinkouPatternMatch":
        expected = _identity(self, ("name", "alias", "original_pdf_page", "condition"))
        if expected is not None and expected["unresolved"]:
            raise ValueError("未裁定课钤不能进入命中列表")
        return self


class JinkouUnresolvedPattern(PartialOutput):
    id: Optional[str] = Field(default=None, pattern=r"^P(?:0[1-9]|[1-5][0-9]|6[0-4])$")
    name: Optional[str] = None
    reason: Optional[str] = None

    @model_validator(mode="after")
    def preserve_selected_identity(self) -> "JinkouUnresolvedPattern":
        expected = _identity(self, ("name",))
        if expected is not None and expected["unresolved"]:
            _identity(self, ("reason",))
        return self


def _distinct_ids(items: List[Any], label: str) -> set[str]:
    ids = [item.id for item in items]
    if any(not isinstance(value, str) for value in ids) or len(set(ids)) != len(ids):
        raise ValueError(f"六十四课钤{label}缺少ID或ID重复")
    return set(ids)


class JinkouPatterns(PartialOutput):
    ruleset_id: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    source_section: Optional[str] = None
    catalog_count: Optional[int] = Field(default=None, ge=64, le=64)
    evaluated_rule_count: Optional[int] = Field(default=None, ge=0, le=64)
    condition_logic: Optional[Literal["any_of_all_v1"]] = None
    condition_facts: Optional[List[JinkouPatternFact]] = None
    # Object projections may omit this array, but never shorten its items or
    # remove entries. The source catalog, including unresolved entries, is 64.
    evaluations: Optional[List[JinkouPatternEvaluation]] = Field(
        default=None, min_length=64, max_length=64
    )
    evaluation_counts: Optional[JinkouPatternCounts] = None
    matched: Optional[List[JinkouPatternMatch]] = None
    unresolved: Optional[List[JinkouUnresolvedPattern]] = None
    day_robbery_branch: Optional[str] = None
    complete_classical_conformance: Optional[Literal[False]] = None
    scope: Optional[str] = None

    @field_validator("complete_classical_conformance", mode="before")
    @classmethod
    def partial_excerpt_cannot_certify_full_conformance(cls, value: Any) -> Any:
        if value is not None and value is not False:
            raise ValueError("当前六十四课钤节录未取得完整原典符合认证")
        return value

    @model_validator(mode="after")
    def preserve_ledger_integrity(self) -> "JinkouPatterns":
        from .metaphysics.jinkou_patterns import pattern_metadata

        for key, expected in pattern_metadata().items():
            if key in self.model_fields_set and getattr(self, key) != expected:
                raise ValueError("课钤来源、所选规则及适用范围不一致")
        if self.condition_facts is not None:
            from .metaphysics.jinkou_pattern_proofs import EXPRESSIONS

            actual = _distinct_ids(self.condition_facts, "条件事实")
            canonical_fact_ids = {
                term.lstrip("!")
                for alternatives in EXPRESSIONS.values()
                for clause in alternatives
                for term in clause.split()
            }
            if actual != canonical_fact_ids:
                raise ValueError("课钤条件事实须保留全部已实现规则的完整队列")
            required = {
                "id",
                "operation",
                "description",
                "operands",
                "reference",
                "matched",
            }
            if any(
                not required <= f.model_fields_set
                or any(getattr(f, key) is None for key in required - {"matched"})
                for f in self.condition_facts
            ):
                raise ValueError("课钤条件队列的条目须保留完整事实")
        matched_ids = (
            _distinct_ids(self.matched, "命中列表")
            if self.matched is not None
            else None
        )
        unresolved_ids = (
            _distinct_ids(self.unresolved, "未决列表")
            if self.unresolved is not None
            else None
        )
        counts = self.evaluation_counts
        if counts is not None:
            parts = (counts.matched, counts.not_matched, counts.unresolved)
            if self.catalog_count is not None and all(p is not None for p in parts):
                if sum(p for p in parts if p is not None) != self.catalog_count:
                    raise ValueError("六十四课钤三态计数与完整目录数量不一致")
            if matched_ids is not None and counts.matched is not None:
                if len(matched_ids) != counts.matched:
                    raise ValueError("六十四课钤命中列表与命中计数不一致")
            if unresolved_ids is not None and counts.unresolved is not None:
                if len(unresolved_ids) != counts.unresolved:
                    raise ValueError("六十四课钤未决列表与未决计数不一致")
        if self.evaluations is None:
            return self
        ids = _distinct_ids(self.evaluations, "逐条判定")
        if ids != {f"P{i:02}" for i in range(1, 65)}:
            raise ValueError("六十四课钤逐条判定必须保留完整64个ID")
        if any(
            not {"status", "matched"} <= row.model_fields_set or row.status is None
            for row in self.evaluations
        ):
            raise ValueError("六十四课钤逐条判定缺少三态事实")
        positive = {row.id for row in self.evaluations if row.matched is True}
        negative = {row.id for row in self.evaluations if row.matched is False}
        unknown = {row.id for row in self.evaluations if row.matched is None}
        if self.evaluated_rule_count is not None:
            if self.evaluated_rule_count != len(positive) + len(negative):
                raise ValueError("六十四课钤已评估数量与逐条三态不一致")
        if counts is not None:
            for key, expected in (
                ("matched", len(positive)),
                ("not_matched", len(negative)),
                ("unresolved", len(unknown)),
            ):
                value = getattr(counts, key)
                if value is not None and value != expected:
                    raise ValueError("六十四课钤三态计数与逐条判定不一致")
        for observed, expected_ids, label in (
            (matched_ids, positive, "命中"),
            (unresolved_ids, unknown, "未决"),
        ):
            if observed is not None and observed != expected_ids:
                raise ValueError(f"六十四课钤{label}列表与逐条判定不一致")
        ledger = {row.id: row for row in self.evaluations}
        if self.condition_facts is not None:
            facts = {fact.id: fact for fact in self.condition_facts}
            from .metaphysics.jinkou_pattern_proofs import evaluate_groups

            referenced: set[str] = set()
            for row in self.evaluations:
                groups = row.condition_groups
                if groups is None:
                    continue
                if any(term.fact_id not in facts for group in groups for term in group):
                    raise ValueError("课钤表达式引用不存在的计算事实")
                referenced.update(
                    term.fact_id
                    for group in groups
                    for term in group
                    if term.fact_id is not None
                )
                result = evaluate_groups(
                    [[t.model_dump(exclude_unset=True) for t in g] for g in groups],
                    {
                        identity: f.matched
                        for identity, f in facts.items()
                        if identity is not None
                    },
                )
                if row.matched is not result:
                    raise ValueError("课钤结论与条件组计算不一致")
            if referenced != set(facts):
                raise ValueError("课钤条件事实含未被表达式引用的项目")
        for items, keys in (
            (self.matched, ("name", "original_pdf_page", "condition")),
            (self.unresolved, ("name", "reason")),
        ):
            for item in items or []:
                row = ledger[item.id]
                for key in keys:
                    if key in item.model_fields_set and key in row.model_fields_set:
                        if getattr(item, key) != getattr(row, key):
                            raise ValueError(
                                "六十四课钤同一ID的依据文字与逐条判定不一致"
                            )
        return self
