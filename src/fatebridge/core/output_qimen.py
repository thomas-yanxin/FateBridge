"""Projection-compatible, source-scoped Qimen evidence contracts."""

from typing import Dict, List, Optional

from pydantic import JsonValue

from fatebridge.core.output_base import PartialOutput

Object = Dict[str, JsonValue]


class QimenPalaceEvidence(PartialOutput):
    status: Optional[str] = None
    note: Optional[str] = None
    hour_void_branches: Optional[List[str]] = None
    hour_void_scope: Optional[str] = None
    door_element: Optional[str] = None
    door_pressure: Optional[bool] = None
    palace_restricts_door: Optional[bool] = None
    star_element: Optional[str] = None
    star_season_state: Optional[str] = None
    star_season_profile: Optional[str] = None
    star_season_source_section: Optional[str] = None
    star_season_relation: Optional[str] = None
    god_interpretation: Optional[Object] = None
    wonder_tomb: Optional[Object] = None
    six_instrument_punishment: Optional[Object] = None
    door_palace_relation: Optional[Object] = None
    three_deceptions: Optional[Object] = None
    five_jia: Optional[Object] = None
    season_month_branch: Optional[str] = None
    season_month_element: Optional[str] = None


class QimenRuleset(PartialOutput):
    id: Optional[str] = None
    version: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    classical_author: Optional[str] = None
    source: Optional[str] = None
    source_kind: Optional[str] = None
    scan_collation: Optional[Object] = None
    sections: Optional[List[str]] = None
    classical_conformance: Optional[str] = None
    ju_method: Optional[str] = None
    conventions: Optional[List[str]] = None
    unresolved: Optional[List[str]] = None
    real_world_efficacy: Optional[str] = None


class QimenCalendarPolicy(PartialOutput):
    solar_time_adjustment: Optional[Object] = None
    timezone: Optional[str] = None
    timezone_rules: Optional[Object] = None
    civil_clock_resolution: Optional[Object] = None
    civil_datetime: Optional[str] = None
    corrected_datetime: Optional[str] = None
    hour_clock: Optional[str] = None
    day_boundary: Optional[str] = None
    xun_scope: Optional[str] = None
    astronomical_term: Optional[Object] = None
    ju_term: Optional[str] = None
    ju_method: Optional[str] = None
    solar_term_providers: Optional[List[str]] = None
    term_grid_years_observed: Optional[List[int]] = None
    precision_status: Optional[str] = None
    rule_change_granularity: Optional[str] = None


class QimenRuleTrace(PartialOutput):
    rule_id: Optional[str] = None
    source: Optional[str] = None
    section: Optional[str] = None
    inputs: Optional[Object] = None
    outputs: Optional[Object] = None
    evidence_paths: Optional[List[str]] = None


class QimenPattern(PartialOutput):
    rule_id: Optional[str] = None
    name: Optional[str] = None
    palace: Optional[str] = None
    evidence_paths: Optional[List[str]] = None
    facts: Optional[Object] = None
    traditional_meaning: Optional[str] = None
    source: Optional[str] = None
    section: Optional[str] = None
    layer: Optional[str] = None
    qualification: Optional[Object] = None
    source_scan_pages: Optional[List[int]] = None


class QimenStructure(PartialOutput):
    hour_branch_tomb: Optional[bool] = None
    stars_fuyin: Optional[bool] = None
    stars_fanyin: Optional[bool] = None
    doors_fuyin: Optional[bool] = None
    doors_fanyin: Optional[bool] = None
    five_not_meet: Optional[bool] = None


class QimenAssessment(PartialOutput):
    calculation_scope: Optional[str] = None
    classical_conformance: Optional[str] = None
    interpretation_status: Optional[str] = None
    real_world_efficacy: Optional[str] = None
    authority_certified: Optional[bool] = None
    score: None = None
