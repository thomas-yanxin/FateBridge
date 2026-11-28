"""Qimen Dunjia structured output contracts."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, JsonValue

from fatebridge.core.contracts.base import FULL_FACT, PartialOutput, ProjectedOutput
from fatebridge.core.contracts.common import (
    AnalysisContext,
    CalendarContext,
    FourPillars,
)
from fatebridge.core.receipt_models import Object, RunMetadata


class QimenRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    title: str | None = None
    author: str | None = None
    classical_author: str | None = None
    classical_conformance: str | None = None
    ju_method: str | None = None


class QimenCalendarPolicy(PartialOutput):
    timezone: str | None = None
    timezone_rules: Object | None = None
    civil_clock_resolution: Object | None = None
    civil_datetime: str | None = None
    corrected_datetime: str | None = None
    hour_clock: str | None = None
    day_boundary: str | None = None
    ju_term: str | None = None
    ju_method: str | None = None
    solar_term_provider: str | None = None


class QimenPattern(PartialOutput):
    rule_id: str | None = None
    name: str | None = None
    palace: str | None = None
    facts: Object | None = None
    coexisting_conflicts: list[str] | None = None


class QimenStructure(PartialOutput):
    hour_branch_tomb: bool | None = None
    stars_fuyin: bool | None = None
    stars_fanyin: bool | None = None
    doors_fuyin: bool | None = None
    doors_fanyin: bool | None = None
    stems_fuyin: bool | None = None
    stems_fanyin: bool | None = None
    five_not_meet: bool | None = None
    tian_xian_time: bool | None = None


class QimenAssessment(PartialOutput):
    calculation_scope: str | None = None
    classical_conformance: str | None = None


class QimenHexagram(PartialOutput):
    binary_code: str | None = None
    name: str | None = None


class QimenPalace(PartialOutput):
    god_sequence_index: int | None = None
    index: Annotated[int | None, FULL_FACT] = None
    direction: str | None = None
    element: str | None = None
    heaven_origin_trigram: str | None = None
    heaven_stems: list[str] | None = None
    earth_stems: list[str] | None = None
    hidden_stem: str | None = None
    hosted_stars: list[str] | None = None
    name: str | None = None
    content_palace: str | None = None
    content_trigram: str | None = None
    trigram: str | None = None
    door: str | None = None
    door_hexagram: QimenHexagram | None = None
    door_palace_relation: str | None = None
    door_pressure: bool | None = None
    star_season_state: str | None = None
    wonder_tombs: list[str] | None = None
    punishments: list[str] | None = None
    branches: list[str] | None = None
    hour_void_branches: list[str] | None = None
    day_void_branches: list[str] | None = None
    hour_void_scope: str | None = None
    day_void_scope: str | None = None
    is_horse_palace: bool | None = None
    earth_stem: str | None = None
    heaven_stem: str | None = None
    god: str | None = None
    star: str | None = None


class QimenLeader(PartialOutput):
    code: str | None = None
    content_palace: str | None = None
    content_trigram: str | None = None
    palace: str | None = None
    trigram: str | None = None
    star: str | None = None
    door: str | None = None


class QimenOptions(PartialOutput):
    ju_method: str | None = None
    lodging_policy: str | None = None
    god_profile: str | None = None
    season_profile: str | None = None
    layout: str | None = None
    palaceShift: int | None = None
    reverse: bool | None = None


class Qimen(PartialOutput):
    god_profile: str | None = None
    season_profile: str | None = None
    lodging_policy: str | None = None
    rule_profiles: Object | None = None
    ju_method: str | None = None
    ju_decision: Object | None = None
    ju_term: str | None = None
    day_ganzhi: str | None = None
    time_ganzhi: str | None = None
    day_xun_head: str | None = None
    day_kongwang: str | None = None
    horse_star: dict[str, str] | None = None
    void_palaces: dict[str, list[str]] | None = None
    hidden_stems_palace_map: dict[str, str] | None = None
    calendar_policy: Annotated[QimenCalendarPolicy | None, FULL_FACT] = None
    structure: QimenStructure | None = None
    patterns: list[QimenPattern] | None = None
    stem_context: Object | None = None
    assessment: QimenAssessment | None = None
    source_disagreements: list[dict[str, JsonValue]] | None = None
    engine: str | None = None
    dun_type: Annotated[str | None, FULL_FACT] = None
    fu_tou: str | None = None
    fushi_hexagram: QimenHexagram | None = None
    ju_number: Annotated[int | None, FULL_FACT] = None
    ju_text: str | None = None
    kongwang: str | None = None
    layout: str | None = None
    options_applied: QimenOptions | None = None
    palaces: Annotated[list[QimenPalace] | None, FULL_FACT] = Field(
        default=None,
        min_length=9,
        max_length=9,
        json_schema_extra={"x-fatebridge-full-result-unique-by": "index"},
    )
    reference: str | None = None
    xun_head: str | None = None
    yuan: str | None = None
    yuan_order: str | None = None
    zhifu: QimenLeader | None = None
    zhishi: QimenLeader | None = None


class QimenOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    calendar_context: CalendarContext | None = None
    four_pillars: FourPillars | None = None
    qimen: Qimen | None = None
