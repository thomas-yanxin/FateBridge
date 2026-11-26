"""Typed partial projections of physical oppositions and literal source notes."""

from fatebridge.core.contracts.output_base import PartialOutput


class TaiyiOppositionFact(PartialOutput):
    field: str | None = None
    value: str | int | None = None


class TaiyiAdditionalOppositionReading(PartialOutput):
    source_name: str | None = None
    matches_selected_taiyi_reference: bool | None = None
    scope: str | None = None


class TaiyiOppositionSourceComparison(PartialOutput):
    ju: int | None = None
    source_name: str | None = None
    source_reading: str | None = None
    source: str | None = None
    expected_taiyi_number: int | None = None
    expected_general_number: int | None = None
    numeric_values_match: bool | None = None
    opposition_matches: bool | None = None
    additional_readings: list[TaiyiAdditionalOppositionReading] | None = None
    scope: str | None = None


class TaiyiOppositionEntry(PartialOutput):
    subject: str | None = None
    field: str | None = None
    palace: str | None = None
    taiyi_palace: str | None = None
    relative_steps: int | None = None
    is_opposite: bool | None = None
    status: str | None = None
    classical_names: list[str] | None = None
    name_status: str | None = None
    basis: list[TaiyiOppositionFact] | None = None
    source_comparison: TaiyiOppositionSourceComparison | None = None


class TaiyiOppositionRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    classical_sources: list[str] | None = None
    annotation_data_sha256: str | None = None


class TaiyiOppositionAssessment(PartialOutput):
    ruleset: TaiyiOppositionRuleset | None = None
    entries: list[TaiyiOppositionEntry] | None = None
    main_names_unified: bool | None = None
    scope: str | None = None
