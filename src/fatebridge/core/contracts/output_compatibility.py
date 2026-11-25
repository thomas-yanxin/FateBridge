"""Projectable contacts and natal references for the two-person BaZi tool."""

from typing import Literal

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_bazi_evidence import RelationEvidence
from fatebridge.core.contracts.output_chinese_calendar import (
    CalendarContext,
    FourPillars,
)
from fatebridge.core.contracts.output_classical_force import (
    ClassicalForceAdjudication,
    EngineeringStrengthIndex,
)

Role = Literal["person1", "person2"]


class PairDayMaster(PartialOutput):
    stem: str | None = None
    element: str | None = None
    polarity: str | None = None
    engineering_index: EngineeringStrengthIndex | None = None
    classical_adjudication: ClassicalForceAdjudication | None = None


class PairPreference(PartialOutput):
    resolution_policy: str | None = None
    assessment_status: str | None = None
    useful_elements: list[str] | None = None
    avoid_elements: list[str] | None = None
    conditional_elements: list[str] | None = None
    neutral_elements: list[str] | None = None


class PairNatalContext(PartialOutput):
    four_pillars: FourPillars | None = None
    calendar_context: CalendarContext | None = None
    element_distribution: dict[str, float] | None = None
    day_master: PairDayMaster | None = None
    preference_assessment: PairPreference | None = None


class CrossChartGroup(PartialOutput):
    kind: Literal["三合", "三会", "三刑", "半合", "拱候选"] | None = None
    positions: list[str] | None = None
    branches: list[str] | None = None
    bureau: str | None = None
    effect_status: Literal["relation_only"] | None = None
    source_scope: Literal["cross_person", "person1", "person2"] | None = None
    natal_matches: list[Role] | None = None


class CrossChartPunishment(PartialOutput):
    source: str | None = None
    target: str | None = None
    branches: list[str] | None = None


class CrossChartRelations(PartialOutput):
    rulesets: list[dict[str, str]] | None = None
    pairs: list[RelationEvidence] | None = None
    groups: list[CrossChartGroup] | None = None
    directional_punishments: list[CrossChartPunishment] | None = None


class CrossChartStar(PartialOutput):
    pillar: str | None = None
    stem: str | None = None
    location: Literal["天干", "地支藏干"] | None = None
    ten_god: str | None = None


class DirectionalTenGods(PartialOutput):
    source: Role | None = None
    target: Role | None = None
    target_day_stem: str | None = None
    stars: list[CrossChartStar] | None = None


COMPATIBILITY_FIELDS = {
    "relationship_type": Literal[
        "general", "marriage", "friendship", "business", "family"
    ],
    "natal_contexts": dict[Role, PairNatalContext],
    "cross_chart_relations": CrossChartRelations,
    "directional_ten_gods": dict[
        Literal["person1_to_person2", "person2_to_person1"], DirectionalTenGods
    ],
}
