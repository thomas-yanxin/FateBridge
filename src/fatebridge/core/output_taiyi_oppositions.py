"""Typed partial projections of physical oppositions and literal source notes."""

from typing import List, Optional, Union

from .output_base import PartialOutput


class TaiyiOppositionFact(PartialOutput):
    field: Optional[str] = None
    value: Optional[Union[int, str]] = None


class TaiyiAdditionalOppositionReading(PartialOutput):
    source_name: Optional[str] = None
    matches_selected_taiyi_reference: Optional[bool] = None
    scope: Optional[str] = None


class TaiyiOppositionSourceComparison(PartialOutput):
    ju: Optional[int] = None
    source_name: Optional[str] = None
    source_reading: Optional[str] = None
    source: Optional[str] = None
    expected_taiyi_number: Optional[int] = None
    expected_general_number: Optional[int] = None
    numeric_values_match: Optional[bool] = None
    opposition_matches: Optional[bool] = None
    additional_readings: Optional[List[TaiyiAdditionalOppositionReading]] = None
    scope: Optional[str] = None


class TaiyiOppositionEntry(PartialOutput):
    subject: Optional[str] = None
    field: Optional[str] = None
    palace: Optional[str] = None
    taiyi_palace: Optional[str] = None
    relative_steps: Optional[int] = None
    is_opposite: Optional[bool] = None
    status: Optional[str] = None
    classical_names: Optional[List[str]] = None
    name_status: Optional[str] = None
    basis: Optional[List[TaiyiOppositionFact]] = None
    source_comparison: Optional[TaiyiOppositionSourceComparison] = None


class TaiyiOppositionRuleset(PartialOutput):
    id: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    classical_sources: Optional[List[str]] = None
    annotation_data_sha256: Optional[str] = None


class TaiyiOppositionAssessment(PartialOutput):
    ruleset: Optional[TaiyiOppositionRuleset] = None
    entries: Optional[List[TaiyiOppositionEntry]] = None
    main_names_unified: Optional[bool] = None
    scope: Optional[str] = None
