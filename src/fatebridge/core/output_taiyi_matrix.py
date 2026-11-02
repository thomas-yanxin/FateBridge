"""Partial projection schema for the classical 128-cell column reference."""

from typing import List, Optional

from pydantic import StrictBool, StrictInt

from .output_base import PartialOutput
from .output_taiyi_elemental import TaiyiElementalRuleset


class TaiyiMatrixLocator(PartialOutput):
    scan_page: Optional[StrictInt] = None
    column_from_right: Optional[StrictInt] = None
    slot_from_top: Optional[StrictInt] = None


class TaiyiMatrixColumn(PartialOutput):
    text: Optional[str] = None
    locator: Optional[TaiyiMatrixLocator] = None


class TaiyiMatrixCell(PartialOutput):
    id: Optional[str] = None
    source_spirit: Optional[str] = None
    wenchang_position: Optional[str] = None
    taiyi_number: Optional[StrictInt] = None
    condition_column: Optional[TaiyiMatrixColumn] = None
    result_column: Optional[TaiyiMatrixColumn] = None
    reading_status: Optional[str] = None


class TaiyiMatrixGeometry(PartialOutput):
    field: Optional[str] = None
    label: Optional[str] = None
    actual_path: Optional[str] = None
    position: Optional[str] = None
    distance: Optional[StrictInt] = None
    status: Optional[str] = None
    same_palace: Optional[StrictBool] = None
    opposite: Optional[StrictBool] = None
    inner_adjacent: Optional[StrictBool] = None
    outer_adjacent: Optional[StrictBool] = None
    adjacent: Optional[StrictBool] = None


class TaiyiMatrixCandidate(PartialOutput):
    field: Optional[str] = None
    actual_path: Optional[str] = None
    position: Optional[str] = None
    matches_geometry: Optional[StrictBool] = None


class TaiyiMatrixClause(PartialOutput):
    column: Optional[str] = None
    text: Optional[str] = None
    kind: Optional[str] = None
    candidates: Optional[List[TaiyiMatrixCandidate]] = None
    actor: Optional[str] = None
    predicate: Optional[str] = None
    role_resolution: Optional[str] = None
    source_name_scope: Optional[str] = None


class TaiyiMatrixComparison(PartialOutput):
    resolved_eye_claims: Optional[StrictInt] = None
    matching_eye_geometry: Optional[StrictInt] = None
    different_eye_geometry: Optional[StrictInt] = None
    unknown_eye_geometry: Optional[StrictInt] = None
    unqualified_general_claims: Optional[StrictInt] = None
    unadjudicated_clauses: Optional[StrictInt] = None
    blank_columns: Optional[StrictInt] = None
    source_lacuna: Optional[StrictBool] = None
    whole_cell_conformance_assessed: Optional[StrictBool] = None


class TaiyiVictoryMatrixAssessment(PartialOutput):
    ruleset: Optional[TaiyiElementalRuleset] = None
    calculation_mode: Optional[str] = None
    role_scope: Optional[str] = None
    method_scope: Optional[str] = None
    scope: Optional[str] = None
    table_applicability_verified: Optional[StrictBool] = None
    source_outcome_applied: Optional[StrictBool] = None
    classical_acceptance_passed: Optional[StrictBool] = None
    real_world_efficacy: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    source_cell: Optional[TaiyiMatrixCell] = None
    actual_geometry: Optional[List[TaiyiMatrixGeometry]] = None
    clauses: Optional[List[TaiyiMatrixClause]] = None
    comparison_summary: Optional[TaiyiMatrixComparison] = None
