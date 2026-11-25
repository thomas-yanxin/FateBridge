"""Projected source facts and explicit limits of current Jin Kou rules."""

from typing import Any, Literal

from pydantic import StrictBool, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.metaphysics.jinkou_sources import strength_sources


class JinkouStrengthWitness(PartialOutput):
    id: str | None = None
    title: str | None = None
    catalog_id: str | None = None
    catalog_url: str | None = None
    scan_url: str | None = None
    source_sha256: str | None = None
    source_bytes: int | None = None
    source_pdf_pages: int | None = None
    original_pdf_pages: list[int] | None = None
    symbolic_example_count: int | None = None
    source_kind: Literal["manuscript_scan"] | None = None
    independent_transmission_adjudicated: StrictBool | None = None
    full_volume_collation: StrictBool | None = None


class JinkouStrengthDifference(PartialOutput):
    id: str | None = None
    changed_position: Literal["地分"] | None = None
    original_elements: list[Literal["木", "火", "土", "金", "水"]] | None = None
    primary_elements: list[Literal["木", "火", "土", "金", "水"]] | None = None
    stated_anchor: Literal["土"] | None = None
    stated_god_power: Literal["旺"] | None = None
    original_pdf_page: int | None = None
    primary_pdf_page: int | None = None
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
    selected_witness: Literal["online_transcription"] | None = None
    derivation: Literal["sufficient_condition_inferred_from_examples"] | None = None
    source_url: str | None = None
    source_section: str | None = None
    scan_source_url: str | None = None
    scan_source_sha256: str | None = None
    scan_pdf_pages: list[int] | None = None
    scan_collation_status: Literal["unresolved_diagram_prose_difference"] | None = None
    daily_five_states_adjudicated: Literal[False] | None = None
    complete_classical_acceptance: Literal[False] | None = None
    note: str | None = None
    primary_witness: JinkouStrengthWitness | None = None
    witness_difference: JinkouStrengthDifference | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def source_binding(self) -> "JinkouStrengthSource":

        _source_fields_match(self.model_dump(exclude_unset=True), strength_sources())
        return self


class JinkouUseSource(PartialOutput):
    scan_source_url: str | None = None
    scan_source_sha256: str | None = None
    no_control_pdf_page: int | None = None
    no_control_footer_page: int | None = None
    polarity_pdf_pages: list[int] | None = None
    combined_priority_status: Literal["not_adjudicated"] | None = None
