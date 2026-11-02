"""Partial textual-witness views retain unreadability and unadjudicated claims."""

from __future__ import annotations

from typing import Literal

from pydantic import StrictBool, StrictInt, model_validator

from .output_base import PartialOutput


class BreakPairWitness(PartialOutput):
    id: str | None = None
    title: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    source_bytes: StrictInt | None = None
    source_pdf_pages: StrictInt | None = None
    reviewed_pdf_pages: list[StrictInt] | None = None
    phrase_pdf_page: StrictInt | None = None
    literal_break_sequence: str | None = None
    extra_phrase_present: StrictBool | None = None
    reading_status: (
        Literal["literal_phrase_readable", "unresolved_dense_handwriting"] | None
    ) = None
    enumerated_pair_count: None = None
    note: str | None = None

    @model_validator(mode="after")
    def readable_phrase_is_not_an_effect_claim(self) -> BreakPairWitness:
        if (
            self.literal_break_sequence is not None
            and self.extra_phrase_present is not None
        ):
            if self.extra_phrase_present is not (
                "寅破巳" in self.literal_break_sequence
            ):
                raise ValueError("字句旁证须符合实际转写，不增写第二个寅")
        if (
            "literal_break_sequence" in self.model_fields_set
            and self.literal_break_sequence is None
        ):
            if self.extra_phrase_present is not None:
                raise ValueError("未读清的见证不能改成支持或否定")
        return self


class BreakPairWitnessEvidence(PartialOutput):
    method_id: Literal["jinkou_break_pair_textual_witnesses_v1"] | None = None
    reader_count: StrictInt | None = None
    blinded: StrictBool | None = None
    independent_expert_review: StrictBool | None = None
    independent_transmission_established: StrictBool | None = None
    witnesses: list[BreakPairWitness] | None = None
    extra_phrase_corroborated: StrictBool | None = None
    readable_corroboration_count: StrictInt | None = None
    unresolved_witness_count: StrictInt | None = None
    author_intent: None = None
    effective_break: None = None
    effect_direction: None = None
    whole_book_conformance: StrictBool | None = None
    new_independent_real_events: StrictInt | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def no_false_source_certification(self) -> BreakPairWitnessEvidence:
        for key in (
            "blinded",
            "independent_expert_review",
            "independent_transmission_established",
            "whole_book_conformance",
        ):
            if key in self.model_fields_set and getattr(self, key) is not False:
                raise ValueError("本次目读未建立盲验、独立专家、传承独立或全书符合")
        if self.witnesses is not None and all(
            "extra_phrase_present" in w.model_fields_set for w in self.witnesses
        ):
            positive = sum(w.extra_phrase_present is True for w in self.witnesses)
            unknown = sum(w.extra_phrase_present is None for w in self.witnesses)
            if (
                self.readable_corroboration_count is not None
                and self.readable_corroboration_count != positive
            ):
                raise ValueError("可读旁证计数不一致")
            if (
                self.unresolved_witness_count is not None
                and self.unresolved_witness_count != unknown
            ):
                raise ValueError("未读清见证不能从分母删除")
        return self
