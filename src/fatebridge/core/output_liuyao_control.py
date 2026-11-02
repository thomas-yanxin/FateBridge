"""Projectable chapter-14 directed-control condition facts."""

from typing import Any, Dict, List, Optional

from .output_base import PartialOutput


class ControlClause(PartialOutput):
    id: Optional[str] = None
    pdf_page: Optional[int] = None
    quote: Optional[str] = None


class ActivityCondition(PartialOutput):
    position: Optional[int] = None
    raw_activity: Optional[str] = None
    activity_condition_match: Optional[bool] = None
    status: Optional[str] = None


class DirectedControl(PartialOutput):
    metal_si_combined_effect_condition: Optional[bool] = None
    metal_si_effect_status: Optional[str] = None
    raw_condition_match: Optional[bool] = None
    raw_status: Optional[str] = None
    metal_si_growth_condition: Optional[bool] = None
    source_control_admission: Optional[bool] = None
    metal_si_growth_source_path: Optional[str] = None
    metal_si_ruleset_id: Optional[str] = None
    metal_si_ruleset_version: Optional[str] = None
    source_void_fill_control_condition: Optional[bool] = None
    source_void_fill_used: Optional[bool] = None
    void_fill_qualification_path: Optional[str] = None
    source_back_generation_condition: Optional[bool] = None
    back_generation_source_path: Optional[str] = None
    source_rescue_used: Optional[bool] = None
    source_calendar_oppositions: Optional[List[Dict[str, Any]]] = None
    source_position: Optional[int] = None
    target_position: Optional[int] = None
    source_branch: Optional[str] = None
    target_branch: Optional[str] = None
    source_active: Optional[bool] = None
    target_active: Optional[bool] = None
    source_activity_match: Optional[bool] = None
    target_activity_match: Optional[bool] = None
    relation: Optional[str] = None
    condition_match: Optional[bool] = None
    status: Optional[str] = None
    source_calendar_supported: Optional[bool] = None
    target_calendar_supported: Optional[bool] = None
    source_confirmed_active_controllers: Optional[List[int]] = None
    source_pending_active_controllers: Optional[List[int]] = None
    source_competing_active_controls: Optional[List[int]] = None
    source_obstructions: Optional[List[str]] = None
    emit_edge: Optional[bool] = None
    rule_id: Optional[str] = None
    source_url: Optional[str] = None
    fact_path: Optional[str] = None


class VoidFillQualification(PartialOutput):
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_sha256: Optional[str] = None
    source_urls: Optional[List[str]] = None
    clauses: Optional[List[Dict[str, Any]]] = None
    precedence: Optional[str] = None
    scope: Optional[str] = None


class ControlConditions(PartialOutput):
    void_fill_qualification: Optional[VoidFillQualification] = None
    back_generation_source_path: Optional[str] = None
    support_ruleset_id: Optional[str] = None
    support_ruleset_version: Optional[str] = None
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    clauses: Optional[List[ControlClause]] = None
    textual_issues: Optional[List[Dict[str, Any]]] = None
    controls: Optional[List[DirectedControl]] = None
    activity_conditions: Optional[List[ActivityCondition]] = None
    activity_resolution_passes: Optional[int] = None
    unresolved_day_clash_positions: Optional[List[int]] = None
    adjudication: Optional[str] = None
    scope: Optional[str] = None
