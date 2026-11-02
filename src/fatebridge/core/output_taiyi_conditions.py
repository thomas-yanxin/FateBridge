"""Strict and projection-safe output for classical conjunction conditions."""

from typing import List, Optional

from .output_base import PartialOutput
from .output_taiyi_gates import TaiyiGateAssessment


class TaiyiConditionSource(PartialOutput):
    id: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    classical_author: Optional[str] = None
    source: Optional[str] = None
    conformance: Optional[str] = None
    relation_profile: Optional[str] = None
    relation_sources: Optional[List[str]] = None
    relation_scope: Optional[str] = None
    coverage_policy: Optional[str] = None


class TaiyiConditionBlocker(PartialOutput):
    source_path: Optional[str] = None
    name: Optional[str] = None
    subject: Optional[str] = None
    variant: Optional[str] = None


class TaiyiConditionFact(PartialOutput):
    field: Optional[str] = None
    value: Optional[int] = None


class TaiyiConditionUnassessed(PartialOutput):
    id: Optional[str] = None
    subjects: Optional[List[str]] = None
    basis: Optional[List[TaiyiConditionFact]] = None
    reason: Optional[str] = None


class TaiyiConditionClause(PartialOutput):
    id: Optional[str] = None
    label: Optional[str] = None
    satisfied: Optional[bool] = None
    assessed_satisfied: Optional[bool] = None
    blockers: Optional[List[TaiyiConditionBlocker]] = None
    unassessed: Optional[List[TaiyiConditionUnassessed]] = None


class TaiyiFiveGenerals(PartialOutput):
    conditions_satisfied: Optional[bool] = None
    assessed_conditions_satisfied: Optional[bool] = None
    same_core_coverage_checked: Optional[bool] = None
    clauses: Optional[List[TaiyiConditionClause]] = None


class TaiyiThreeGates(TaiyiGateAssessment):
    pass


class TaiyiConditionAssessment(PartialOutput):
    ruleset: Optional[TaiyiConditionSource] = None
    five_generals: Optional[TaiyiFiveGenerals] = None
    three_gates: Optional[TaiyiThreeGates] = None
    menju_jiangfa: Optional[bool] = None
    summary: Optional[str] = None
    scope: Optional[str] = None
