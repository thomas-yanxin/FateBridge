"""Projection-compatible contracts for source-scoped Mei Hua evidence."""

from pydantic import JsonValue

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_meihua_calendar import (
    MeihuaCalendarPrecision,
    MeihuaSolarDateReference,
)


class MeihuaSource(PartialOutput):
    id: str | None = None
    title: str | None = None
    revision: int | None = None
    url: str | None = None


class MeihuaRule(PartialOutput):
    id: str | None = None
    source_id: str | None = None
    section: str | None = None
    kind: str | None = None
    quote: str | None = None
    statement: str | None = None


class MeihuaRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    title: str | None = None
    edition: str | None = None
    sources: list[MeihuaSource] | None = None
    rules: list[MeihuaRule] | None = None
    scope: str | None = None


class MeihuaCalendarPolicy(PartialOutput):
    civil_clock_resolution: dict[str, JsonValue] | None = None
    label_precision: MeihuaCalendarPrecision | None = None
    solar_term_date_reference: MeihuaSolarDateReference | None = None
    context_status: str | None = None
    lunar_year: int | None = None
    year_boundary: str | None = None
    day_boundary: str | None = None
    is_leap_month: bool | None = None
    leap_month_rule: str | None = None
    timezone: str | None = None
    date_basis: str | None = None
    hour_basis: str | None = None
    true_solar_time_applied: bool | None = None
    minute_role: str | None = None
    rule_kind: str | None = None


class MeihuaTraceStep(PartialOutput):
    rule_id: str | None = None
    operation: str | None = None
    inputs: dict[str, JsonValue] | None = None
    result: JsonValue | None = None


class MeihuaStageRelation(PartialOutput):
    role: str | None = None
    stage: str | None = None
    body: str | None = None
    body_element: str | None = None
    trigram: str | None = None
    element: str | None = None
    relation: str | None = None
    traditional_tendency: str | None = None
    meaning: str | None = None
    fact_path: str | None = None
    rule_id: str | None = None


class MeihuaSeasonalTrigram(PartialOutput):
    role: str | None = None
    trigram: str | None = None
    element: str | None = None
    strength: str | None = None
    fact_path: str | None = None


class MeihuaSeasonalStrength(PartialOutput):
    month_branch: str | None = None
    season: str | None = None
    basis: str | None = None
    rule_id: str | None = None
    convention_rule_id: str | None = None
    trigrams: list[MeihuaSeasonalTrigram] | None = None


class MeihuaEvidenceScope(PartialOutput):
    calculation_status: str | None = None
    text_count_basis: dict[str, JsonValue] | None = None
    text_tone_basis: dict[str, JsonValue] | None = None
    missing_context: list[str] | None = None
    classical_coverage: str | None = None
    implemented: list[str] | None = None
    not_implemented: list[str] | None = None
    interpretation_basis: str | None = None
    authority_certified: bool | None = None


class MeihuaCountingVariant(PartialOutput):
    line_sum_basis: str | None = None
    selected: bool | None = None
    moving_line: int | None = None
    changed_code: str | None = None
    body: str | None = None
    use: str | None = None
    moving_palace: str | None = None
    body_use_relation: str | None = None
