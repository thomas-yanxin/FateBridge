"""Strict, projection-safe facts for the separately sourced annual cycles."""

from typing import Dict, List, Optional

from .output_base import PartialOutput


class TaiyiLongEpoch(PartialOutput):
    year: Optional[int] = None
    accumulation: Optional[int] = None
    equivalent_short_epoch_accumulation: Optional[int] = None
    equivalence_modulus: Optional[int] = None


class TaiyiLongMarker(PartialOutput):
    position: Optional[str] = None
    palace: Optional[str] = None
    palace_number: Optional[int] = None
    space: Optional[str] = None
    accumulation: Optional[int] = None
    cycle_length: Optional[int] = None
    cycle_year: Optional[int] = None
    years_per_position: Optional[int] = None
    position_index: Optional[int] = None
    year_in_palace: Optional[int] = None
    label: Optional[str] = None
    source_section: Optional[str] = None
    source_method: Optional[str] = None
    source_reference: Optional[str] = None
    source_edition: Optional[str] = None
    epoch_id: Optional[str] = None
    classical_palace_name: Optional[str] = None
    administration_phase: Optional[str] = None
    table_position: Optional[str] = None
    table_disagreement: Optional[bool] = None
    table_row: Optional[str] = None
    table_yuan: Optional[str] = None


class TaiyiLongRuleset(PartialOutput):
    id: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    classical_author: Optional[str] = None
    source: Optional[str] = None
    classical_conformance: Optional[str] = None
    classical_acceptance_passed: Optional[bool] = None


class TaiyiLongCycles(PartialOutput):
    year: Optional[int] = None
    status: Optional[str] = None
    selected_mode: Optional[str] = None
    time_granularity: Optional[str] = None
    ruleset: Optional[TaiyiLongRuleset] = None
    epochs: Optional[Dict[str, TaiyiLongEpoch]] = None
    counting_convention: Optional[str] = None
    records: Optional[Dict[str, TaiyiLongMarker]] = None
    interpretation_scope: Optional[str] = None
    unresolved: Optional[List[str]] = None


class TaiyiLongSummary(PartialOutput):
    status: Optional[str] = None
    time_granularity: Optional[str] = None
    year: Optional[int] = None
    ruleset_id: Optional[str] = None
    source: Optional[str] = None
    positions: Optional[Dict[str, str]] = None
    table_disagreements: Optional[List[str]] = None
    scope: Optional[str] = None
