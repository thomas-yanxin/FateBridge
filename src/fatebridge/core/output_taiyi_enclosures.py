"""Projection-safe, three-state coverage of the enclosure rule family."""

from typing import List, Optional, Union

from .output_base import PartialOutput


class TaiyiEnclosureRuleset(PartialOutput):
    id: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    classical_author: Optional[str] = None
    sources: Optional[List[str]] = None


class TaiyiPrincipalEnclosure(PartialOutput):
    status: Optional[str] = None
    present: Optional[bool] = None
    pattern_paths: Optional[List[str]] = None
    meaning: Optional[str] = None


class TaiyiUnassessedEnclosure(PartialOutput):
    name: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None


class TaiyiPairFact(PartialOutput):
    field: Optional[str] = None
    value: Optional[Union[str, int]] = None


class TaiyiPairPattern(PartialOutput):
    name: Optional[str] = None
    subject: Optional[str] = None
    variant: Optional[str] = None
    basis: Optional[List[TaiyiPairFact]] = None
    traditional_meaning: Optional[str] = None
    source: Optional[str] = None
    relation_profile: Optional[str] = None
    scope: Optional[str] = None


class TaiyiPairEnclosure(TaiyiPrincipalEnclosure):
    patterns: Optional[List[TaiyiPairPattern]] = None


class TaiyiEnclosureAssessment(PartialOutput):
    ruleset: Optional[TaiyiEnclosureRuleset] = None
    principal_enclosure: Optional[TaiyiPrincipalEnclosure] = None
    two_general_ruleset: Optional[TaiyiEnclosureRuleset] = None
    two_general_enclosure: Optional[TaiyiPairEnclosure] = None
    unassessed: Optional[List[TaiyiUnassessedEnclosure]] = None
    scope: Optional[str] = None
