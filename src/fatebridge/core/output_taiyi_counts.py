"""Strict partial projections for source-specific count classifications."""

from typing import List, Optional, Union

from .output_base import PartialOutput


class TaiyiCountComponents(PartialOutput):
    ten: Optional[int] = None
    five: Optional[int] = None
    one: Optional[int] = None


class TaiyiCountContext(PartialOutput):
    reference: Optional[str] = None
    field: Optional[str] = None
    value: Optional[Union[int, str]] = None
    polarity: Optional[str] = None
    count_parity: Optional[str] = None
    is_harmonious: Optional[bool] = None
    reading: Optional[str] = None


class TaiyiCountMembership(PartialOutput):
    profile_id: Optional[str] = None
    harmony_tiers: Optional[List[str]] = None
    three_talents_listed: Optional[bool] = None


class TaiyiCountReading(PartialOutput):
    value: Optional[int] = None
    missing_labels: Optional[List[str]] = None
    components: Optional[TaiyiCountComponents] = None
    three_talents_inferred: Optional[bool] = None
    duse: Optional[bool] = None
    length_label: Optional[str] = None
    is_long: Optional[bool] = None
    number_families: Optional[List[str]] = None
    source_memberships: Optional[List[TaiyiCountMembership]] = None
    literal_rank_status: Optional[str] = None
    literal_rank_consensus: Optional[str] = None
    subject: Optional[str] = None
    field: Optional[str] = None
    contexts: Optional[List[TaiyiCountContext]] = None


class TaiyiCountReadingRuleset(PartialOutput):
    id: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    primary_sources: Optional[List[str]] = None
    catalog_sha256: Optional[str] = None


class TaiyiCountReadingSource(PartialOutput):
    id: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None
    evidence_level: Optional[str] = None


class TaiyiCountUnadjudicatedReading(PartialOutput):
    profile_id: Optional[str] = None
    kind: Optional[str] = None
    reading: Optional[str] = None
    scope: Optional[str] = None
    values: Optional[List[int]] = None
    status: Optional[str] = None


class TaiyiCountAssessment(PartialOutput):
    ruleset: Optional[TaiyiCountReadingRuleset] = None
    sources: Optional[List[TaiyiCountReadingSource]] = None
    unadjudicated_source_readings: Optional[List[TaiyiCountUnadjudicatedReading]] = None
    entries: Optional[List[TaiyiCountReading]] = None
    overall_harmony_assessed: Optional[bool] = None
    scope: Optional[str] = None
