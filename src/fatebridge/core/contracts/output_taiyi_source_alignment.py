"""Projection-safe explicit distinction between source facts and recounts."""

from fatebridge.core.contracts.output_base import PartialOutput


class TaiyiSourceAlignmentRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    classical_author: str | None = None
    source_title: str | None = None
    facsimile_source: str | None = None
    source: str | None = None
    count_rule_source: str | None = None


class TaiyiSourcePosition(PartialOutput):
    field: str | None = None
    actual_path: str | None = None
    actual_value: str | int | None = None
    source_value: str | int | None = None
    source_literal: str | None = None
    transcription_literal: str | None = None
    initial_manual_literal: str | None = None
    source_layer: str | None = None
    matches: bool | None = None


class TaiyiSourceCountStep(PartialOutput):
    palace: str | None = None
    value: int | None = None
    kind: str | None = None


class TaiyiSourceCountTrace(PartialOutput):
    count: int | None = None
    path: list[TaiyiSourceCountStep] | None = None
    terminal_palace: str | None = None
    terminal_excluded: bool | None = None
    counting_rule: str | None = None
    source: str | None = None


class TaiyiSourceCount(PartialOutput):
    camp: str | None = None
    field: str | None = None
    marker_field: str | None = None
    actual_count_path: str | None = None
    actual_marker_path: str | None = None
    actual_marker: str | None = None
    source_marker: str | None = None
    actual_count: int | None = None
    source_table_count: int | None = None
    source_layer: str | None = None
    count_matches: bool | None = None
    same_inputs: bool | None = None
    source_recount_matches_table: bool | None = None
    source_position_recount: TaiyiSourceCountTrace | None = None
    diagnosis: str | None = None


class TaiyiSourceFacsimileCheck(PartialOutput):
    id: str | None = None
    field: str | None = None
    text_reading: str | None = None
    initial_manual_reading: str | None = None
    facsimile_reading: str | None = None
    page: int | None = None
    status: str | None = None
    selected_reading: str | None = None


class TaiyiSourceAlignmentSummary(PartialOutput):
    status: str | None = None
    position_disagreements: list[str] | None = None
    count_disagreements: list[str] | None = None
    source_internal_count_disagreements: list[str] | None = None
    scope: str | None = None


class TaiyiEditionImage(PartialOutput):
    book_number: int | None = None
    image_number: int | None = None
    url: str | None = None


class TaiyiEditionObservation(PartialOutput):
    field: str | None = None
    actual_value: str | int | None = None
    selected_source_value: str | int | None = None
    selected_source_literal: str | None = None
    edition_value: str | int | None = None
    edition_literal: str | None = None
    matches_current: bool | None = None
    matches_selected_source: bool | None = None


class TaiyiEditionComparison(PartialOutput):
    source_id: str | None = None
    source_title: str | None = None
    classical_author: str | None = None
    provider: str | None = None
    catalog_identity: str | None = None
    catalog_url: str | None = None
    edition: str | None = None
    bibliographic_note: str | None = None
    chapter_image_url: str | None = None
    images: list[TaiyiEditionImage] | None = None
    location: str | None = None
    yin_dun: bool | None = None
    ju: int | None = None
    observations: list[TaiyiEditionObservation] | None = None
    required_observations: int | None = None
    matching_current_observations: int | None = None
    matching_selected_source_observations: int | None = None
    review_status: str | None = None
    textual_lineage_independence_established: bool | None = None
    whole_work_acceptance_passed: bool | None = None
    scope: str | None = None


class TaiyiSourceAlignment(PartialOutput):
    ruleset: TaiyiSourceAlignmentRuleset | None = None
    status: str | None = None
    reason: str | None = None
    case_id: str | None = None
    yin_dun: bool | None = None
    ju: int | None = None
    facsimile_page: int | None = None
    facsimile_columns_from_right: list[int] | None = None
    positions: list[TaiyiSourcePosition] | None = None
    counts: list[TaiyiSourceCount] | None = None
    facsimile_readings: list[TaiyiSourceFacsimileCheck] | None = None
    edition_comparisons: list[TaiyiEditionComparison] | None = None
    summary: TaiyiSourceAlignmentSummary | None = None
    scope: str | None = None
