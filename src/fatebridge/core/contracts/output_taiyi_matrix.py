"""Partial projection schema for the classical 128-cell column reference."""

from pydantic import StrictBool, StrictInt

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_taiyi_elemental import TaiyiElementalRuleset


class TaiyiMatrixLocator(PartialOutput):
    scan_page: StrictInt | None = None
    column_from_right: StrictInt | None = None
    slot_from_top: StrictInt | None = None


class TaiyiMatrixColumn(PartialOutput):
    text: str | None = None
    locator: TaiyiMatrixLocator | None = None


class TaiyiMatrixCell(PartialOutput):
    id: str | None = None
    source_spirit: str | None = None
    wenchang_position: str | None = None
    taiyi_number: StrictInt | None = None
    condition_column: TaiyiMatrixColumn | None = None
    result_column: TaiyiMatrixColumn | None = None
    reading_status: str | None = None


class TaiyiMatrixGeometry(PartialOutput):
    field: str | None = None
    label: str | None = None
    actual_path: str | None = None
    position: str | None = None
    distance: StrictInt | None = None
    status: str | None = None
    same_palace: StrictBool | None = None
    opposite: StrictBool | None = None
    inner_adjacent: StrictBool | None = None
    outer_adjacent: StrictBool | None = None
    adjacent: StrictBool | None = None


class TaiyiMatrixCandidate(PartialOutput):
    field: str | None = None
    actual_path: str | None = None
    position: str | None = None
    matches_geometry: StrictBool | None = None


class TaiyiMatrixClause(PartialOutput):
    column: str | None = None
    text: str | None = None
    kind: str | None = None
    candidates: list[TaiyiMatrixCandidate] | None = None
    actor: str | None = None
    predicate: str | None = None
    role_resolution: str | None = None
    source_name_scope: str | None = None


class TaiyiMatrixComparison(PartialOutput):
    resolved_eye_claims: StrictInt | None = None
    matching_eye_geometry: StrictInt | None = None
    different_eye_geometry: StrictInt | None = None
    unknown_eye_geometry: StrictInt | None = None
    unqualified_general_claims: StrictInt | None = None
    unadjudicated_clauses: StrictInt | None = None
    blank_columns: StrictInt | None = None
    source_lacuna: StrictBool | None = None
    whole_cell_conformance_assessed: StrictBool | None = None


class TaiyiVictoryMatrixAssessment(PartialOutput):
    ruleset: TaiyiElementalRuleset | None = None
    calculation_mode: str | None = None
    role_scope: str | None = None
    method_scope: str | None = None
    scope: str | None = None
    table_applicability_verified: StrictBool | None = None
    source_outcome_applied: StrictBool | None = None
    classical_acceptance_passed: StrictBool | None = None
    real_world_efficacy: str | None = None
    status: str | None = None
    reason: str | None = None
    source_cell: TaiyiMatrixCell | None = None
    actual_geometry: list[TaiyiMatrixGeometry] | None = None
    clauses: list[TaiyiMatrixClause] | None = None
    comparison_summary: TaiyiMatrixComparison | None = None
