"""Projection-safe daily origin and Key ten-essence facts."""

from typing import Dict, List, Optional, Union

from .output_base import PartialOutput


class TaiyiDayOrigin(PartialOutput):
    source: Optional[str] = None
    winter_clock: Optional[str] = None
    winter_day_ganzhi: Optional[str] = None
    winter_anchor_utc: Optional[str] = None
    winter_anchor_provider: Optional[str] = None
    origin_effective_date: Optional[str] = None
    target_effective_date: Optional[str] = None
    target_day_ganzhi: Optional[str] = None
    accumulation: Optional[int] = None
    day_boundary: Optional[str] = None
    same_day_jiazi_included: Optional[bool] = None
    same_day_selection_adjudicated: Optional[bool] = None
    alternative_strict_previous_count: Optional[int] = None
    scope: Optional[str] = None


class TaiyiSourceComparison(PartialOutput):
    field: Optional[str] = None
    source_value: Optional[Union[str, int]] = None
    rule_derived_value: Optional[Union[str, int]] = None
    scope: Optional[str] = None
    source: Optional[str] = None


class TaiyiTenCandidate(PartialOutput):
    id: Optional[str] = None
    yang_position: Optional[str] = None
    adopted: Optional[bool] = None


class TaiyiTenRuleEvidence(PartialOutput):
    status: Optional[str] = None
    basis: Optional[str] = None
    sources: Optional[Dict[str, str]] = None
    unresolved: Optional[str] = None


class TaiyiTenRecord(PartialOutput):
    label: Optional[str] = None
    status: Optional[str] = None
    palace: Optional[str] = None
    palace_number: Optional[int] = None
    yang_position: Optional[str] = None
    period: Optional[int] = None
    cycle_position: Optional[int] = None
    sequence: Optional[List[str]] = None
    rule: Optional[str] = None
    yin_opposition: Optional[str] = None
    reason: Optional[str] = None
    source: Optional[str] = None
    ordinal: Optional[int] = None
    candidates: Optional[List[TaiyiTenCandidate]] = None
    source_comparisons: Optional[List[TaiyiSourceComparison]] = None
    rule_evidence: Optional[TaiyiTenRuleEvidence] = None


class TaiyiTenJing(PartialOutput):
    status: Optional[str] = None
    accumulation: Optional[int] = None
    yin: Optional[bool] = None
    records: Optional[Dict[str, TaiyiTenRecord]] = None
    source: Optional[str] = None
    ruleset_id: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    classical_author: Optional[str] = None
    classical_acceptance_passed: Optional[bool] = None
    scope: Optional[str] = None
