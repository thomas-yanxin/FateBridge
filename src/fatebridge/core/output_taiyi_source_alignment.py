"""Projection-safe explicit distinction between source facts and recounts."""

from typing import List, Optional, Union

from .output_base import PartialOutput


class TaiyiSourceAlignmentRuleset(PartialOutput):
    id: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    classical_author: Optional[str] = None
    source_title: Optional[str] = None
    facsimile_source: Optional[str] = None
    source: Optional[str] = None
    count_rule_source: Optional[str] = None
    source_manifest_sha256: Optional[str] = None
    transcription_collation_manifest_sha256: Optional[str] = None
    facsimile_collation_manifest_sha256: Optional[str] = None
    facsimile_correction_manifest_sha256: Optional[str] = None
    catalog_sha256: Optional[str] = None


class TaiyiSourcePosition(PartialOutput):
    field: Optional[str] = None
    actual_path: Optional[str] = None
    actual_value: Optional[Union[int, str]] = None
    source_value: Optional[Union[int, str]] = None
    source_literal: Optional[str] = None
    transcription_literal: Optional[str] = None
    initial_manual_literal: Optional[str] = None
    source_layer: Optional[str] = None
    matches: Optional[bool] = None


class TaiyiSourceCountStep(PartialOutput):
    palace: Optional[str] = None
    value: Optional[int] = None
    kind: Optional[str] = None


class TaiyiSourceCountTrace(PartialOutput):
    count: Optional[int] = None
    path: Optional[List[TaiyiSourceCountStep]] = None
    terminal_palace: Optional[str] = None
    terminal_excluded: Optional[bool] = None
    counting_rule: Optional[str] = None
    source: Optional[str] = None


class TaiyiSourceCount(PartialOutput):
    camp: Optional[str] = None
    field: Optional[str] = None
    marker_field: Optional[str] = None
    actual_count_path: Optional[str] = None
    actual_marker_path: Optional[str] = None
    actual_marker: Optional[str] = None
    source_marker: Optional[str] = None
    actual_count: Optional[int] = None
    source_table_count: Optional[int] = None
    source_layer: Optional[str] = None
    count_matches: Optional[bool] = None
    same_inputs: Optional[bool] = None
    source_recount_matches_table: Optional[bool] = None
    source_position_recount: Optional[TaiyiSourceCountTrace] = None
    diagnosis: Optional[str] = None


class TaiyiSourceFacsimileCheck(PartialOutput):
    id: Optional[str] = None
    field: Optional[str] = None
    text_reading: Optional[str] = None
    initial_manual_reading: Optional[str] = None
    facsimile_reading: Optional[str] = None
    page: Optional[int] = None
    status: Optional[str] = None
    selected_reading: Optional[str] = None


class TaiyiSourceAlignmentSummary(PartialOutput):
    status: Optional[str] = None
    position_disagreements: Optional[List[str]] = None
    count_disagreements: Optional[List[str]] = None
    source_internal_count_disagreements: Optional[List[str]] = None
    scope: Optional[str] = None


class TaiyiEditionImage(PartialOutput):
    book_number: Optional[int] = None
    image_number: Optional[int] = None
    url: Optional[str] = None
    sha256: Optional[str] = None


class TaiyiEditionObservation(PartialOutput):
    field: Optional[str] = None
    actual_value: Optional[Union[int, str]] = None
    selected_source_value: Optional[Union[int, str]] = None
    selected_source_literal: Optional[str] = None
    edition_value: Optional[Union[int, str]] = None
    edition_literal: Optional[str] = None
    matches_current: Optional[bool] = None
    matches_selected_source: Optional[bool] = None


class TaiyiEditionComparison(PartialOutput):
    source_id: Optional[str] = None
    source_title: Optional[str] = None
    classical_author: Optional[str] = None
    provider: Optional[str] = None
    catalog_identity: Optional[str] = None
    catalog_url: Optional[str] = None
    catalog_sha256: Optional[str] = None
    edition: Optional[str] = None
    bibliographic_note: Optional[str] = None
    chapter_image_url: Optional[str] = None
    chapter_image_sha256: Optional[str] = None
    images: Optional[List[TaiyiEditionImage]] = None
    location: Optional[str] = None
    yin_dun: Optional[bool] = None
    ju: Optional[int] = None
    observations: Optional[List[TaiyiEditionObservation]] = None
    required_observations: Optional[int] = None
    matching_current_observations: Optional[int] = None
    matching_selected_source_observations: Optional[int] = None
    review_status: Optional[str] = None
    textual_lineage_independence_established: Optional[bool] = None
    whole_work_acceptance_passed: Optional[bool] = None
    scope: Optional[str] = None


class TaiyiSourceAlignment(PartialOutput):
    ruleset: Optional[TaiyiSourceAlignmentRuleset] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    case_id: Optional[str] = None
    yin_dun: Optional[bool] = None
    ju: Optional[int] = None
    facsimile_page: Optional[int] = None
    facsimile_columns_from_right: Optional[List[int]] = None
    positions: Optional[List[TaiyiSourcePosition]] = None
    counts: Optional[List[TaiyiSourceCount]] = None
    facsimile_readings: Optional[List[TaiyiSourceFacsimileCheck]] = None
    edition_comparisons: Optional[List[TaiyiEditionComparison]] = None
    summary: Optional[TaiyiSourceAlignmentSummary] = None
    scope: Optional[str] = None
