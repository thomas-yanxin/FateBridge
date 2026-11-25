"""Strict, projection-safe facts for the separately sourced annual cycles."""

from fatebridge.core.contracts.output_base import PartialOutput


class TaiyiLongEpoch(PartialOutput):
    year: int | None = None
    accumulation: int | None = None
    equivalent_short_epoch_accumulation: int | None = None
    equivalence_modulus: int | None = None


class TaiyiLongMarker(PartialOutput):
    position: str | None = None
    palace: str | None = None
    palace_number: int | None = None
    space: str | None = None
    accumulation: int | None = None
    cycle_length: int | None = None
    cycle_year: int | None = None
    years_per_position: int | None = None
    position_index: int | None = None
    year_in_palace: int | None = None
    label: str | None = None
    source_section: str | None = None
    source_method: str | None = None
    source_reference: str | None = None
    source_edition: str | None = None
    epoch_id: str | None = None
    classical_palace_name: str | None = None
    administration_phase: str | None = None
    table_position: str | None = None
    table_disagreement: bool | None = None
    table_row: str | None = None
    table_yuan: str | None = None


class TaiyiLongRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    classical_author: str | None = None
    source: str | None = None
    classical_conformance: str | None = None
    classical_acceptance_passed: bool | None = None


class TaiyiLongCycles(PartialOutput):
    year: int | None = None
    status: str | None = None
    selected_mode: str | None = None
    time_granularity: str | None = None
    ruleset: TaiyiLongRuleset | None = None
    epochs: dict[str, TaiyiLongEpoch] | None = None
    counting_convention: str | None = None
    records: dict[str, TaiyiLongMarker] | None = None
    interpretation_scope: str | None = None
    unresolved: list[str] | None = None


class TaiyiLongSummary(PartialOutput):
    status: str | None = None
    time_granularity: str | None = None
    year: int | None = None
    ruleset_id: str | None = None
    source: str | None = None
    positions: dict[str, str] | None = None
    table_disagreements: list[str] | None = None
    scope: str | None = None
