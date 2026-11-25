"""Projection-safe daily origin and Key ten-essence facts."""

from fatebridge.core.contracts.output_base import PartialOutput


class TaiyiDayOrigin(PartialOutput):
    source: str | None = None
    winter_clock: str | None = None
    winter_day_ganzhi: str | None = None
    winter_anchor_utc: str | None = None
    winter_anchor_provider: str | None = None
    origin_effective_date: str | None = None
    target_effective_date: str | None = None
    target_day_ganzhi: str | None = None
    accumulation: int | None = None
    day_boundary: str | None = None
    same_day_jiazi_included: bool | None = None
    same_day_selection_adjudicated: bool | None = None
    alternative_strict_previous_count: int | None = None
    scope: str | None = None


class TaiyiSourceComparison(PartialOutput):
    field: str | None = None
    source_value: str | int | None = None
    rule_derived_value: str | int | None = None
    scope: str | None = None
    source: str | None = None


class TaiyiTenCandidate(PartialOutput):
    id: str | None = None
    yang_position: str | None = None
    adopted: bool | None = None


class TaiyiTenRuleEvidence(PartialOutput):
    status: str | None = None
    basis: str | None = None
    sources: dict[str, str] | None = None
    unresolved: str | None = None


class TaiyiTenRecord(PartialOutput):
    label: str | None = None
    status: str | None = None
    palace: str | None = None
    palace_number: int | None = None
    yang_position: str | None = None
    period: int | None = None
    cycle_position: int | None = None
    sequence: list[str] | None = None
    rule: str | None = None
    yin_opposition: str | None = None
    reason: str | None = None
    source: str | None = None
    ordinal: int | None = None
    candidates: list[TaiyiTenCandidate] | None = None
    source_comparisons: list[TaiyiSourceComparison] | None = None
    rule_evidence: TaiyiTenRuleEvidence | None = None


class TaiyiTenJing(PartialOutput):
    status: str | None = None
    accumulation: int | None = None
    yin: bool | None = None
    records: dict[str, TaiyiTenRecord] | None = None
    source: str | None = None
    ruleset_id: str | None = None
    version: str | None = None
    author: str | None = None
    classical_author: str | None = None
    classical_acceptance_passed: bool | None = None
    scope: str | None = None
