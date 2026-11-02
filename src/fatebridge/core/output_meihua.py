"""Projection-compatible contracts for source-scoped Mei Hua evidence."""

from typing import Dict, List, Optional

from pydantic import JsonValue

from .output_base import PartialOutput
from .output_meihua_calendar import (
    MeihuaCalendarPrecision,
    MeihuaSolarDateReference,
)


class MeihuaSource(PartialOutput):
    id: Optional[str] = None
    title: Optional[str] = None
    revision: Optional[int] = None
    url: Optional[str] = None


class MeihuaRule(PartialOutput):
    id: Optional[str] = None
    source_id: Optional[str] = None
    section: Optional[str] = None
    kind: Optional[str] = None
    quote: Optional[str] = None
    statement: Optional[str] = None


class MeihuaRuleset(PartialOutput):
    id: Optional[str] = None
    version: Optional[str] = None
    title: Optional[str] = None
    edition: Optional[str] = None
    sources: Optional[List[MeihuaSource]] = None
    rules: Optional[List[MeihuaRule]] = None
    scope: Optional[str] = None


class MeihuaCalendarPolicy(PartialOutput):
    civil_clock_resolution: Optional[Dict[str, JsonValue]] = None
    label_precision: Optional[MeihuaCalendarPrecision] = None
    solar_term_date_reference: Optional[MeihuaSolarDateReference] = None
    context_status: Optional[str] = None
    lunar_year: Optional[int] = None
    year_boundary: Optional[str] = None
    day_boundary: Optional[str] = None
    is_leap_month: Optional[bool] = None
    leap_month_rule: Optional[str] = None
    timezone: Optional[str] = None
    date_basis: Optional[str] = None
    hour_basis: Optional[str] = None
    true_solar_time_applied: Optional[bool] = None
    minute_role: Optional[str] = None
    rule_kind: Optional[str] = None


class MeihuaTraceStep(PartialOutput):
    rule_id: Optional[str] = None
    operation: Optional[str] = None
    inputs: Optional[Dict[str, JsonValue]] = None
    result: Optional[JsonValue] = None


class MeihuaStageRelation(PartialOutput):
    role: Optional[str] = None
    stage: Optional[str] = None
    body: Optional[str] = None
    body_element: Optional[str] = None
    trigram: Optional[str] = None
    element: Optional[str] = None
    relation: Optional[str] = None
    traditional_tendency: Optional[str] = None
    meaning: Optional[str] = None
    fact_path: Optional[str] = None
    rule_id: Optional[str] = None


class MeihuaSeasonalTrigram(PartialOutput):
    role: Optional[str] = None
    trigram: Optional[str] = None
    element: Optional[str] = None
    strength: Optional[str] = None
    fact_path: Optional[str] = None


class MeihuaSeasonalStrength(PartialOutput):
    month_branch: Optional[str] = None
    season: Optional[str] = None
    basis: Optional[str] = None
    rule_id: Optional[str] = None
    convention_rule_id: Optional[str] = None
    trigrams: Optional[List[MeihuaSeasonalTrigram]] = None


class MeihuaEvidenceScope(PartialOutput):
    calculation_status: Optional[str] = None
    text_count_basis: Optional[Dict[str, JsonValue]] = None
    text_tone_basis: Optional[Dict[str, JsonValue]] = None
    missing_context: Optional[List[str]] = None
    classical_coverage: Optional[str] = None
    implemented: Optional[List[str]] = None
    not_implemented: Optional[List[str]] = None
    interpretation_basis: Optional[str] = None
    real_world_efficacy: Optional[str] = None
    authority_certified: Optional[bool] = None


class MeihuaCountingVariant(PartialOutput):
    line_sum_basis: Optional[str] = None
    selected: Optional[bool] = None
    moving_line: Optional[int] = None
    changed_code: Optional[str] = None
    body: Optional[str] = None
    use: Optional[str] = None
    moving_palace: Optional[str] = None
    body_use_relation: Optional[str] = None
