"""Unresolved source clauses must not become adjudicated matches."""

from typing import List, Literal, Optional

from pydantic import Field, StrictBool, field_validator, model_validator

from .output_base import PartialOutput
from .output_jinkou_interactions import JinkouInteractionCondition

PatternId = Literal["P52", "P53", "P56", "P57", "P58", "P59"]


class ChapterHeading(PartialOutput):
    occurrence_id: Optional[str] = None
    pdf_page: Optional[int] = Field(default=None, ge=1)
    side: Optional[Literal["R", "L"]] = None
    raw_heading: Optional[str] = None
    selected_definition: Optional[str] = None
    selected_alias: Optional[str] = None
    reading_note: Optional[str] = None


class ChapterObservation(PartialOutput):
    id: Optional[str] = None
    occurrences: Optional[List[str]] = None
    observation: Optional[str] = None


class JinkouChapterInventory(PartialOutput):
    inventory_id: Optional[Literal["waseda_jinkou_chapter_v1"]] = None
    raw_inventory_sha256: Optional[str] = None
    source_pdf_pages: Optional[int] = Field(default=None, ge=1)
    reviewed_pdf_pages: Optional[List[int]] = None
    chapter_heading: Optional[str] = None
    chapter_start_pdf_page: Optional[int] = Field(default=None, ge=1)
    chapter_end_pdf_page: Optional[int] = Field(default=None, ge=1)
    observed_heading_occurrences: Optional[int] = Field(default=None, ge=0)
    unique_raw_headings: Optional[int] = Field(default=None, ge=0)
    duplicate_raw_headings: Optional[List[str]] = None
    headings: Optional[List[ChapterHeading]] = None
    direct_observations: Optional[List[ChapterObservation]] = None
    chapter_heading_inventory_complete: Optional[Literal[True]] = None
    whole_volume_transcription_complete: Optional[Literal[False]] = None
    all_definitions_transcribed: Optional[Literal[False]] = None
    all_diagrams_transcribed: Optional[Literal[False]] = None
    independent_transmission_established: Optional[Literal[False]] = None
    chronological_priority_established: Optional[Literal[False]] = None
    classical_predicates_adjudicated: Optional[Literal[0]] = None
    full_classical_conformance: Optional[Literal[False]] = None
    scope: Optional[str] = None


class DefinitionWitness(PartialOutput):
    id: Optional[Literal["cnts_v2", "waseda_book6"]] = None
    title: Optional[str] = None
    catalog_id: Optional[str] = None
    catalog_url: Optional[str] = None
    scan_url: Optional[str] = None
    source_sha256: Optional[str] = None
    chronology: Optional[str] = None
    full_scan_url: Optional[str] = None
    full_scan_sha256: Optional[str] = None
    chapter_inventory: Optional[JinkouChapterInventory] = None


class DefinitionReading(PartialOutput):
    witness_id: Optional[Literal["cnts_v2", "waseda_book6"]] = None
    locator: Optional[str] = None
    raw_heading: Optional[str] = None
    raw_alias: Optional[str] = None
    raw_definition: Optional[str] = None
    literal_day_ganzhi: Optional[str] = None
    literal_hour_branch: Optional[str] = None
    literal_four_positions: Optional[List[str]] = Field(
        default=None, min_length=4, max_length=4
    )


class UnresolvedDefinition(PartialOutput):
    pattern_id: Optional[PatternId] = None
    name: Optional[str] = None
    witness_readings: Optional[List[DefinitionReading]] = Field(
        default=None, min_length=2, max_length=2
    )
    status: Optional[Literal["unresolved"]] = None
    adjudicated_match: None = None
    unresolved_reason: Optional[str] = None


class GenerationHypothesis(PartialOutput):
    pattern_id: Optional[Literal["P52", "P53"]] = None
    hypothesis_id: Optional[Literal["outer_inner", "adjacent_pairs", "conjunction"]] = (
        None
    )
    condition_checks: Optional[List[JinkouInteractionCondition]] = None
    all_conditions_met: Optional[StrictBool] = None
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
    mode: Optional[Literal["day", "night"]] = None
    assumed_is_diurnal: Optional[StrictBool] = None
    selected_under_current_policy: Optional[StrictBool] = None
    start_branch: Optional[str] = None
    ground_branch: Optional[str] = None
    god_name: Optional[str] = None
    intrinsic_ganzhi: Optional[str] = None
    ground_clockwise_steps: Optional[int] = Field(default=None, ge=0, le=11)
    ground_counterclockwise_steps: Optional[int] = Field(default=None, ge=0, le=11)


class DingRoute(PartialOutput):
    route_id: Optional[
        Literal["intrinsic_god", "daily_god", "daily_general", "human_redun_at_ground"]
    ] = None
    anchor_stem: Optional[str] = None
    target_branch: Optional[str] = None
    stem: Optional[str] = None
    element: Optional[str] = None
    is_ding: Optional[StrictBool] = None
    controls_human: Optional[StrictBool] = None
    controls_ground: Optional[StrictBool] = None
    identified_by_original_clause: None = None


class JinkouDefinitionEvidence(PartialOutput):
    ruleset_id: Optional[Literal["jinkou_unresolved_definition_evidence_v1"]] = None
    day_stem: Optional[str] = None
    hour_branch: Optional[str] = None
    selected_is_diurnal: Optional[StrictBool] = None
    witnesses: Optional[List[DefinitionWitness]] = Field(
        default=None, min_length=2, max_length=2
    )
    entries: Optional[List[UnresolvedDefinition]] = Field(
        default=None, min_length=6, max_length=6
    )
    cross_generation_hypotheses: Optional[List[GenerationHypothesis]] = Field(
        default=None, min_length=6, max_length=6
    )
    day_night_candidates: Optional[List[DayNightCandidate]] = Field(
        default=None, min_length=2, max_length=2
    )
    ground_equals_day_start: Optional[StrictBool] = None
    ground_equals_night_start: Optional[StrictBool] = None
    ground_equals_other_start: Optional[StrictBool] = None
    ding_routes: Optional[List[DingRoute]] = Field(
        default=None, min_length=4, max_length=4
    )
    observed_twilight_transition: None = None
    front_back_predicate: None = None
    complete_classical_conformance: Optional[Literal[False]] = None
    scope: Optional[str] = None

    @field_validator("entries")
    @classmethod
    def fixed_unresolved_inventory(
        cls, value: Optional[List[UnresolvedDefinition]]
    ) -> Optional[List[UnresolvedDefinition]]:
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
    from .metaphysics.jinkou_definitions import chapter_provenance

    definitions = board.get("definition_evidence") or {}
    witnesses = definitions.get("witnesses") or []
    selected = [w for w in witnesses if w.get("id") == "waseda_book6"]
    if len(selected) != 1:
        raise ValueError("完整金口诀须保留唯一的早稻田原典见证")
    expected = chapter_provenance()
    if any(selected[0].get(key) != value for key, value in expected.items()):
        raise ValueError("完整金口诀须保留连续课钤书影清单及全部未裁定说明")
