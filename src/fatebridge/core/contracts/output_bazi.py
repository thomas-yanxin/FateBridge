"""Stable nested facts for BaZi single-dimension analyses."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_bazi_evidence import DominantStructure
from fatebridge.core.contracts.output_chinese_calendar import (
    CalendarContext,
    FourPillars,
    SolarTerm,
)


class TimingOverrides(PartialOutput):
    dayun_pillar: bool | None = None
    liunian_pillar: bool | None = None


class DimensionTimingContext(PartialOutput):
    analysis_date: str | None = None
    analysis_datetime: str | None = None
    timezone: str | None = None
    input_granularity: Literal["date"] | None = None
    anchor_policy: Literal["local_midnight"] | None = None
    year_boundary_policy: Literal["lichun_exact_moment"] | None = None
    boundary_status: Literal["year_boundary_day", "not_year_boundary_day"] | None = None
    boundaries_on_date: list[SolarTerm] | None = None
    dayun_pillar: str | None = None
    liunian_pillar: str | None = None
    source: str | None = None
    dayun_status: str | None = None
    message: str | None = None
    dayun_age: float | None = None
    dayun_selection_basis: str | None = None
    dayun_start_at: str | None = None
    dayun_end_at: str | None = None
    child_limit: dict[str, OpenJsonValue] | None = None
    xiaoyun_pillar: str | None = None
    xiaoyun: dict[str, OpenJsonValue] | None = None
    overridden: TimingOverrides | None = None


class TopicMarker(PartialOutput):
    name: str | None = None
    anchor: str | None = None
    target_branch: str | None = None
    direction: str | None = None
    natal_positions: list[str] | None = None
    timing_layers: list[str] | None = None


class TopicFacts(PartialOutput):
    topic: str | None = None
    four_pillars: FourPillars | None = None
    day_master: dict[str, OpenJsonValue] | None = None
    favorable_elements: list[str] | None = None
    avoid_elements: list[str] | None = None
    dominant_structure: str | None = None
    structure_detail: DominantStructure | None = None
    seasonal_climate: dict[str, OpenJsonValue] | None = None
    element_distribution: dict[str, float] | None = None
    element_seasonal_phase: dict[str, str] | None = None
    natal_stars: list[dict[str, OpenJsonValue]] | None = None
    markers: list[TopicMarker] | None = None
    palace_relations: dict[str, list[dict[str, OpenJsonValue]]] | None = None
    natal_groups: list[dict[str, OpenJsonValue]] | None = None
    timing_layers: list[dict[str, OpenJsonValue]] | None = None


class DimensionOutput(PartialOutput):
    model_config = ConfigDict(extra="forbid")

    calendar_context: CalendarContext | None = None
    timing_context: DimensionTimingContext | None = None
    topic_facts: TopicFacts | None = None
