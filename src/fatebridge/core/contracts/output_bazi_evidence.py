"""Published, projection-compatible contracts for BaZi structure and relation facts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput


class RelationEvidence(PartialOutput):
    kind: str | None = None
    level: Literal["stem", "branch", "pillar"] | None = None
    positions: list[str] | None = None
    characters: list[str] | None = None
    distance: int | None = Field(default=None, ge=1, le=3)
    effect_status: Literal["relation_only"] | None = None
    candidate_element: str | None = None
    detail: str | None = None
    group: str | None = None
    complete: bool | None = None


class GroupEvidence(PartialOutput):
    kind: Literal["三合", "半合", "拱合", "三会", "拱会", "三刑"] | None = None
    positions: list[str] | None = None
    branches: list[str] | None = None
    bureau: str | None = None
    arched: str | None = None
    effect_status: Literal["relation_only"] | None = None


class DominantStructure(PartialOutput):
    key: str | None = None
    label: str | None = None
    category: str | None = None
    selection_rule: str | None = None
    month_stem: str | None = None
    month_ten_god: str | None = None
    formation_status: str | None = None
    obstructions: list[str] | None = None
    rescues: list[str] | None = None
    useful_elements: list[str] | None = None
    avoid_elements: list[str] | None = None
    reason: str | None = None


class ClassicalForceSummary(PartialOutput):
    status: str | None = None
    body_strength: Literal["强", "中和", "弱"] | None = None
    ordinary_fuyi_applicable: bool | None = None
    dominant_pattern: str | None = None
    formation_status: str | None = None


class SeasonalClimateInfo(PartialOutput):
    available: bool | None = None
    primary: str | None = None
    secondary: list[str] | None = None
    elements: list[str] | None = None
    primary_present: bool | None = None
    observations: list[dict[str, OpenJsonValue]] | None = None


class EvidenceStructureProfile(PartialOutput):
    assessment_status: (
        Literal["adjudicated", "conditional", "partial", "not_adjudicated"] | None
    ) = None
    dominant_structure: DominantStructure | None = None
    recognized_structures: list[dict[str, OpenJsonValue]] | None = None
    useful_elements: list[str] | None = None
    avoid_elements: list[str] | None = None
    neutral_elements: list[str] | None = None
    useful_ten_gods: list[str] | None = None
    seasonal_climate: SeasonalClimateInfo | None = None
    classical_adjudication: ClassicalForceSummary | None = None
    harmony_patterns: dict[str, OpenJsonValue] | None = None
    clash_patterns: dict[str, OpenJsonValue] | None = None
