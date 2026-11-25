"""Projection-compatible, source-scoped Qimen evidence contracts."""

from pydantic import JsonValue

from fatebridge.core.contracts.output_base import PartialOutput

Object = dict[str, JsonValue]


class QimenPalaceEvidence(PartialOutput):
    status: str | None = None
    note: str | None = None
    hour_void_branches: list[str] | None = None
    hour_void_scope: str | None = None
    door_element: str | None = None
    door_pressure: bool | None = None
    palace_restricts_door: bool | None = None
    star_element: str | None = None
    star_season_state: str | None = None
    star_season_profile: str | None = None
    star_season_source_section: str | None = None
    star_season_relation: str | None = None
    god_interpretation: Object | None = None
    wonder_tomb: Object | None = None
    six_instrument_punishment: Object | None = None
    door_palace_relation: Object | None = None
    three_deceptions: Object | None = None
    five_jia: Object | None = None
    season_month_branch: str | None = None
    season_month_element: str | None = None


class QimenRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    title: str | None = None
    author: str | None = None
    classical_author: str | None = None
    source: str | None = None
    source_kind: str | None = None
    scan_collation: Object | None = None
    sections: list[str] | None = None
    classical_conformance: str | None = None
    ju_method: str | None = None
    conventions: list[str] | None = None
    unresolved: list[str] | None = None


class QimenCalendarPolicy(PartialOutput):
    solar_time_adjustment: Object | None = None
    timezone: str | None = None
    timezone_rules: Object | None = None
    civil_clock_resolution: Object | None = None
    civil_datetime: str | None = None
    corrected_datetime: str | None = None
    hour_clock: str | None = None
    day_boundary: str | None = None
    xun_scope: str | None = None
    astronomical_term: Object | None = None
    ju_term: str | None = None
    ju_method: str | None = None
    solar_term_providers: list[str] | None = None
    term_grid_years_observed: list[int] | None = None
    precision_status: str | None = None
    rule_change_granularity: str | None = None


class QimenRuleTrace(PartialOutput):
    rule_id: str | None = None
    source: str | None = None
    section: str | None = None
    inputs: Object | None = None
    outputs: Object | None = None
    evidence_paths: list[str] | None = None


class QimenPattern(PartialOutput):
    rule_id: str | None = None
    name: str | None = None
    palace: str | None = None
    evidence_paths: list[str] | None = None
    facts: Object | None = None
    traditional_meaning: str | None = None
    source: str | None = None
    section: str | None = None
    layer: str | None = None
    qualification: Object | None = None
    source_scan_pages: list[int] | None = None


class QimenStructure(PartialOutput):
    hour_branch_tomb: bool | None = None
    stars_fuyin: bool | None = None
    stars_fanyin: bool | None = None
    doors_fuyin: bool | None = None
    doors_fanyin: bool | None = None
    five_not_meet: bool | None = None


class QimenAssessment(PartialOutput):
    calculation_scope: str | None = None
    classical_conformance: str | None = None
    interpretation_status: str | None = None
