"""Projected source facts and explicit limits of current Jin Kou rules."""

from typing import Any, List, Literal, Optional

from pydantic import StrictBool, model_validator

from .output_base import PartialOutput


class JinkouStrengthWitness(PartialOutput):
    id: Optional[str] = None
    title: Optional[str] = None
    catalog_id: Optional[str] = None
    catalog_url: Optional[str] = None
    scan_url: Optional[str] = None
    source_sha256: Optional[str] = None
    source_bytes: Optional[int] = None
    source_pdf_pages: Optional[int] = None
    original_pdf_pages: Optional[List[int]] = None
    symbolic_example_count: Optional[int] = None
    source_kind: Optional[Literal["manuscript_scan"]] = None
    independent_transmission_adjudicated: Optional[StrictBool] = None
    full_volume_collation: Optional[StrictBool] = None


class JinkouStrengthDifference(PartialOutput):
    id: Optional[str] = None
    changed_position: Optional[Literal["地分"]] = None
    original_elements: Optional[List[Literal["木", "火", "土", "金", "水"]]] = None
    primary_elements: Optional[List[Literal["木", "火", "土", "金", "水"]]] = None
    stated_anchor: Optional[Literal["土"]] = None
    stated_god_power: Optional[Literal["旺"]] = None
    original_pdf_page: Optional[int] = None
    primary_pdf_page: Optional[int] = None
    authorial_resolution: None = None


def _source_fields_match(actual: Any, expected: Any) -> None:
    if isinstance(actual, dict) and isinstance(expected, dict):
        for key, value in actual.items():
            if key not in expected:
                raise ValueError("旺衰来源不能添加未登记的认证")
            _source_fields_match(value, expected[key])
    elif type(actual) is not type(expected) or actual != expected:
        raise ValueError("旺衰来源、原页或异文与已登记原书不一致")


class JinkouStrengthSource(PartialOutput):
    selected_witness: Optional[Literal["online_transcription"]] = None
    derivation: Optional[Literal["sufficient_condition_inferred_from_examples"]] = None
    source_url: Optional[str] = None
    source_section: Optional[str] = None
    scan_source_url: Optional[str] = None
    scan_source_sha256: Optional[str] = None
    scan_pdf_pages: Optional[List[int]] = None
    scan_collation_status: Optional[Literal["unresolved_diagram_prose_difference"]] = (
        None
    )
    daily_five_states_adjudicated: Optional[Literal[False]] = None
    complete_classical_acceptance: Optional[Literal[False]] = None
    note: Optional[str] = None
    primary_witness: Optional[JinkouStrengthWitness] = None
    witness_difference: Optional[JinkouStrengthDifference] = None
    scope: Optional[str] = None

    @model_validator(mode="after")
    def source_binding(self) -> "JinkouStrengthSource":
        from .metaphysics.jinkou_sources import strength_sources

        _source_fields_match(self.model_dump(exclude_unset=True), strength_sources())
        return self


class JinkouUseSource(PartialOutput):
    scan_source_url: Optional[str] = None
    scan_source_sha256: Optional[str] = None
    no_control_pdf_page: Optional[int] = None
    no_control_footer_page: Optional[int] = None
    polarity_pdf_pages: Optional[List[int]] = None
    combined_priority_status: Optional[Literal["not_adjudicated"]] = None
