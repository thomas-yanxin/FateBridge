"""Strict and projection-safe output for classical conjunction conditions."""

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_taiyi_gates import TaiyiGateAssessment


class TaiyiConditionSource(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    classical_author: str | None = None
    source: str | None = None
    conformance: str | None = None
    relation_profile: str | None = None
    relation_sources: list[str] | None = None
    relation_scope: str | None = None
    coverage_policy: str | None = None


class TaiyiConditionBlocker(PartialOutput):
    source_path: str | None = None
    name: str | None = None
    subject: str | None = None
    variant: str | None = None


class TaiyiConditionFact(PartialOutput):
    field: str | None = None
    value: int | None = None


class TaiyiConditionUnassessed(PartialOutput):
    id: str | None = None
    subjects: list[str] | None = None
    basis: list[TaiyiConditionFact] | None = None
    reason: str | None = None


class TaiyiConditionClause(PartialOutput):
    id: str | None = None
    label: str | None = None
    satisfied: bool | None = None
    assessed_satisfied: bool | None = None
    blockers: list[TaiyiConditionBlocker] | None = None
    unassessed: list[TaiyiConditionUnassessed] | None = None


class TaiyiFiveGenerals(PartialOutput):
    conditions_satisfied: bool | None = None
    assessed_conditions_satisfied: bool | None = None
    same_core_coverage_checked: bool | None = None
    clauses: list[TaiyiConditionClause] | None = None


class TaiyiThreeGates(TaiyiGateAssessment):
    pass


class TaiyiConditionAssessment(PartialOutput):
    ruleset: TaiyiConditionSource | None = None
    five_generals: TaiyiFiveGenerals | None = None
    three_gates: TaiyiThreeGates | None = None
    menju_jiangfa: bool | None = None
    adjudication: str | None = None
    summary: str | None = None
    scope: str | None = None
