"""Strict partial projections for source-specific count classifications."""

from fatebridge.core.contracts.output_base import PartialOutput


class TaiyiCountComponents(PartialOutput):
    ten: int | None = None
    five: int | None = None
    one: int | None = None


class TaiyiCountContext(PartialOutput):
    reference: str | None = None
    field: str | None = None
    value: str | int | None = None
    polarity: str | None = None
    count_parity: str | None = None
    is_harmonious: bool | None = None
    reading: str | None = None


class TaiyiCountMembership(PartialOutput):
    profile_id: str | None = None
    harmony_tiers: list[str] | None = None
    three_talents_listed: bool | None = None


class TaiyiCountReading(PartialOutput):
    value: int | None = None
    missing_labels: list[str] | None = None
    components: TaiyiCountComponents | None = None
    three_talents_inferred: bool | None = None
    duse: bool | None = None
    length_label: str | None = None
    is_long: bool | None = None
    number_families: list[str] | None = None
    source_memberships: list[TaiyiCountMembership] | None = None
    literal_rank_status: str | None = None
    literal_rank_consensus: str | None = None
    subject: str | None = None
    field: str | None = None
    contexts: list[TaiyiCountContext] | None = None


class TaiyiCountReadingRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    primary_sources: list[str] | None = None
    catalog_sha256: str | None = None


class TaiyiCountReadingSource(PartialOutput):
    id: str | None = None
    title: str | None = None
    source: str | None = None
    evidence_level: str | None = None


class TaiyiCountUnadjudicatedReading(PartialOutput):
    profile_id: str | None = None
    kind: str | None = None
    reading: str | None = None
    scope: str | None = None
    values: list[int] | None = None
    status: str | None = None


class TaiyiCountAssessment(PartialOutput):
    ruleset: TaiyiCountReadingRuleset | None = None
    sources: list[TaiyiCountReadingSource] | None = None
    unadjudicated_source_readings: list[TaiyiCountUnadjudicatedReading] | None = None
    entries: list[TaiyiCountReading] | None = None
    overall_harmony_assessed: bool | None = None
    scope: str | None = None
