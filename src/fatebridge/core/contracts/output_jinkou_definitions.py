"""Unresolved source clauses must not become adjudicated matches."""

from typing import Literal

from pydantic import Field, StrictBool, field_validator, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_jinkou_interactions import (
    JinkouInteractionCondition,
)
from fatebridge.core.metaphysics.jinkou_definitions import chapter_provenance

PatternId = Literal["P52", "P53", "P56", "P57", "P58", "P59"]


class ChapterHeading(PartialOutput):
    occurrence_id: str | None = None
    pdf_page: int | None = Field(default=None, ge=1)
    side: Literal["R", "L"] | None = None
    raw_heading: str | None = None
    selected_definition: str | None = None
    selected_alias: str | None = None
    reading_note: str | None = None


class ChapterObservation(PartialOutput):
    id: str | None = None
    occurrences: list[str] | None = None
    observation: str | None = None


class JinkouChapterInventory(PartialOutput):
    inventory_id: Literal["waseda_jinkou_chapter_v1"] | None = None
    raw_inventory_sha256: str | None = None
    source_pdf_pages: int | None = Field(default=None, ge=1)
    reviewed_pdf_pages: list[int] | None = None
    chapter_heading: str | None = None
    chapter_start_pdf_page: int | None = Field(default=None, ge=1)
    chapter_end_pdf_page: int | None = Field(default=None, ge=1)
    observed_heading_occurrences: int | None = Field(default=None, ge=0)
    unique_raw_headings: int | None = Field(default=None, ge=0)
    duplicate_raw_headings: list[str] | None = None
    headings: list[ChapterHeading] | None = None
    direct_observations: list[ChapterObservation] | None = None
    chapter_heading_inventory_complete: Literal[True] | None = None
    whole_volume_transcription_complete: Literal[False] | None = None
    all_definitions_transcribed: Literal[False] | None = None
    all_diagrams_transcribed: Literal[False] | None = None
    independent_transmission_established: Literal[False] | None = None
    chronological_priority_established: Literal[False] | None = None
    classical_predicates_adjudicated: Literal[0] | None = None
    full_classical_conformance: Literal[False] | None = None
    scope: str | None = None


class DefinitionWitness(PartialOutput):
    id: Literal["cnts_v2", "waseda_book6"] | None = None
    title: str | None = None
    catalog_id: str | None = None
    catalog_url: str | None = None
    scan_url: str | None = None
    source_sha256: str | None = None
    chronology: str | None = None
    full_scan_url: str | None = None
    full_scan_sha256: str | None = None
    chapter_inventory: JinkouChapterInventory | None = None


class DefinitionReading(PartialOutput):
    witness_id: Literal["cnts_v2", "waseda_book6"] | None = None
    locator: str | None = None
    raw_heading: str | None = None
    raw_alias: str | None = None
    raw_definition: str | None = None
    literal_day_ganzhi: str | None = None
    literal_hour_branch: str | None = None
    literal_four_positions: list[str] | None = Field(
        default=None, min_length=4, max_length=4
    )


class UnresolvedDefinition(PartialOutput):
    pattern_id: PatternId | None = None
    name: str | None = None
    witness_readings: list[DefinitionReading] | None = Field(
        default=None, min_length=2, max_length=2
    )
    status: Literal["unresolved"] | None = None
    adjudicated_match: None = None
    unresolved_reason: str | None = None


class GenerationHypothesis(PartialOutput):
    pattern_id: Literal["P52", "P53"] | None = None
    hypothesis_id: Literal["outer_inner", "adjacent_pairs", "conjunction"] | None = None
    condition_checks: list[JinkouInteractionCondition] | None = None
    all_conditions_met: StrictBool | None = None
    adjudicated_predicate: None = None

    @model_validator(mode="after")
    def conjunction_matches_checks(self) -> "GenerationHypothesis":
        if self.condition_checks is not None and self.all_conditions_met is not None:
            flags = [c.matched for c in self.condition_checks]
            if all(f is not None for f in flags) and self.all_conditions_met != all(
                flags
            ):
                raise ValueError("隔生候选的合取值与所列条件不一致")
        return self


class DayNightCandidate(PartialOutput):
    mode: Literal["day", "night"] | None = None
    assumed_is_diurnal: StrictBool | None = None
    selected_under_current_policy: StrictBool | None = None
    start_branch: str | None = None
    ground_branch: str | None = None
    god_name: str | None = None
    intrinsic_ganzhi: str | None = None
    ground_clockwise_steps: int | None = Field(default=None, ge=0, le=11)
    ground_counterclockwise_steps: int | None = Field(default=None, ge=0, le=11)


class DingRoute(PartialOutput):
    route_id: (
        Literal["intrinsic_god", "daily_god", "daily_general", "human_redun_at_ground"]
        | None
    ) = None
    anchor_stem: str | None = None
    target_branch: str | None = None
    stem: str | None = None
    element: str | None = None
    is_ding: StrictBool | None = None
    controls_human: StrictBool | None = None
    controls_ground: StrictBool | None = None
    identified_by_original_clause: None = None


class JinkouDefinitionEvidence(PartialOutput):
    ruleset_id: Literal["jinkou_unresolved_definition_evidence_v1"] | None = None
    day_stem: str | None = None
    hour_branch: str | None = None
    selected_is_diurnal: StrictBool | None = None
    witnesses: list[DefinitionWitness] | None = Field(
        default=None, min_length=2, max_length=2
    )
    entries: list[UnresolvedDefinition] | None = Field(
        default=None, min_length=6, max_length=6
    )
    cross_generation_hypotheses: list[GenerationHypothesis] | None = Field(
        default=None, min_length=6, max_length=6
    )
    day_night_candidates: list[DayNightCandidate] | None = Field(
        default=None, min_length=2, max_length=2
    )
    ground_equals_day_start: StrictBool | None = None
    ground_equals_night_start: StrictBool | None = None
    ground_equals_other_start: StrictBool | None = None
    ding_routes: list[DingRoute] | None = Field(
        default=None, min_length=4, max_length=4
    )
    observed_twilight_transition: None = None
    front_back_predicate: None = None
    complete_classical_conformance: Literal[False] | None = None
    scope: str | None = None

    @field_validator("entries")
    @classmethod
    def fixed_unresolved_inventory(
        cls, value: list[UnresolvedDefinition] | None
    ) -> list[UnresolvedDefinition] | None:
        if value is not None and [e.pattern_id for e in value] != [
            "P52",
            "P53",
            "P56",
            "P57",
            "P58",
            "P59",
        ]:
            raise ValueError("六条疑义课式不得遗漏、重排或重复")
        return value


def compare_present_definition_facts(actual: object, expected: object) -> None:
    """Allow arbitrary projections; reject contradictory facts that are present."""
    if isinstance(actual, dict) and isinstance(expected, dict):
        for key, value in actual.items():
            if key in expected:
                compare_present_definition_facts(value, expected[key])
    elif isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError("课钤疑义依据的队列与本课不一致")
        for a, b in zip(actual, expected):
            compare_present_definition_facts(a, b)
    elif actual != expected:
        raise ValueError("课钤疑义依据与本课四位、日干或昼夜条件不一致")


def require_complete_chapter_witness(board: dict) -> None:

    definitions = board.get("definition_evidence") or {}
    witnesses = definitions.get("witnesses") or []
    selected = [w for w in witnesses if w.get("id") == "waseda_book6"]
    if len(selected) != 1:
        raise ValueError("完整金口诀须保留唯一的早稻田原典见证")
    expected = chapter_provenance()
    if any(selected[0].get(key) != value for key, value in expected.items()):
        raise ValueError("完整金口诀须保留连续课钤书影清单及全部未裁定说明")
