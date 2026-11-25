"""Canping verse readings and evidence selection."""

from typing import Literal

from pydantic import Field, JsonValue

from fatebridge.core.contracts.output_base import PartialOutput


class CanpingTextWitness(PartialOutput):
    element: str | None = None
    number: int | None = None
    kind: Literal["male", "female", "luck"] | None = None
    text: str | None = None
    pdf_pages: list[int] | None = None
    body_pdf_page: int | None = None
    source_occurrence_id: str | None = Field(default=None, min_length=1)
    header_pdf_page: int | None = Field(default=None, gt=0)
    number_occurrence_count: int | None = Field(default=None, gt=0)
    number_occurrence_ambiguous: bool | None = None
    reading_uncertainties: list[str] | None = None
    source_corpus_id: str | None = None
    text_status: str | None = None
    relation: (
        Literal[
            "same_text",
            "different_text",
            "selected_reading_uncertain",
            "witness_reading_uncertain",
            "both_readings_uncertain",
        ]
        | None
    ) = None
    replaces_selected_text: Literal[False] | None = None
    inherited_reading_matches: bool | None = None


class CanpingReadingRevision(PartialOutput):
    rereading_id: str | None = None
    previous_collation_version: str | None = None
    previous_text: str | None = None
    previous_cell_status: Literal["source_reading_uncertain"] | None = None
    source_pdf_page: int | None = Field(default=None, gt=0)
    note: str | None = None


class CanpingNumberReadingEvidence(PartialOutput):
    element: str | None = None
    provisional_number: int | None = None
    pdf_page: int | None = Field(default=None, gt=0)
    observed_header: str | None = None
    obstruction_kind: Literal["seal_overprint", "faded_digit"] | None = None
    note: str | None = None
    resolution_status: Literal["unresolved"] | None = None
    witness_id: str | None = None
    body_evidence_basis: (
        Literal["prior_literal_transcription_not_new_body_collation"] | None
    ) = None


class CanpingTextSelection(PartialOutput):
    element: str | None = None
    number: int | None = None
    kind: Literal["male", "female", "luck"] | None = None
    column: str | None = None
    corpus_key: str | None = None
    row_status: str | None = None
    cell_status: str | None = None
    corrected_number: int | None = None
    collation_id: str | None = None
    source_pdf_page: int | None = None
    reading_notes: list[str] | None = None
    reading_uncertainties: list[str] | None = None
    number_reading_uncertainties: list[str] | None = None
    number_attribution_status: Literal["provisional_inherited_key"] | None = None
    reading_revision: CanpingReadingRevision | None = None
    body_reading_status: (
        Literal[
            "source_body_visually_read",
            "source_body_printed_blank",
            "source_body_printed_partial_blank",
            "source_body_reading_uncertain",
        ]
        | None
    ) = None
    number_reading_evidence: CanpingNumberReadingEvidence | None = None
    editorial_unknown_marker: str | None = None
    witnesses: list[CanpingTextWitness] | None = None
    inherited_text: str | None = None
    inherited_number: int | None = None
    unapplied_note: dict[str, JsonValue] | None = None


class CanpingPairResolution(PartialOutput):
    same_number: bool | None = None
    distinct_numbers: int | None = None
    local_text_availability: str | None = None
    source_rule_pdf_page: int | None = None
    independent_evidence_count: int | None = None
    scope: str | None = None
