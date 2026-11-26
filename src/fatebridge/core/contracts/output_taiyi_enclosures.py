"""Projection-safe, three-state coverage of the enclosure rule family."""

from fatebridge.core.contracts.output_base import PartialOutput


class TaiyiEnclosureRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    classical_author: str | None = None
    sources: list[str] | None = None


class TaiyiPrincipalEnclosure(PartialOutput):
    status: str | None = None
    present: bool | None = None
    pattern_paths: list[str] | None = None
    meaning: str | None = None


class TaiyiUnassessedEnclosure(PartialOutput):
    name: str | None = None
    status: str | None = None
    reason: str | None = None


class TaiyiPairFact(PartialOutput):
    field: str | None = None
    value: str | int | None = None


class TaiyiPairPattern(PartialOutput):
    name: str | None = None
    subject: str | None = None
    variant: str | None = None
    basis: list[TaiyiPairFact] | None = None
    traditional_meaning: str | None = None
    source: str | None = None
    relation_profile: str | None = None
    scope: str | None = None


class TaiyiPairEnclosure(TaiyiPrincipalEnclosure):
    patterns: list[TaiyiPairPattern] | None = None


class TaiyiEnclosureAssessment(PartialOutput):
    ruleset: TaiyiEnclosureRuleset | None = None
    principal_enclosure: TaiyiPrincipalEnclosure | None = None
    two_general_ruleset: TaiyiEnclosureRuleset | None = None
    two_general_enclosure: TaiyiPairEnclosure | None = None
    unassessed: list[TaiyiUnassessedEnclosure] | None = None
    scope: str | None = None
