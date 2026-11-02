"""Partial output contracts for shared original own-back-generation gates."""

from typing import Any, Dict, List, Optional

from .output_base import PartialOutput


class BackGenerationSource(PartialOutput):
    position: Optional[int] = None
    branch: Optional[str] = None
    is_actual_moving: Optional[bool] = None
    changed_branch: Optional[str] = None
    changed_relation: Optional[str] = None
    is_back_generation: Optional[bool] = None
    condition_match: Optional[bool] = None
    raw_condition_match: Optional[bool] = None
    month_break_qualified_gate: Optional[bool] = None
    raw_status: Optional[str] = None
    penalty_source_path: Optional[str] = None
    status: Optional[str] = None
    changed_void: Optional[bool] = None
    changed_day_void_fill: Optional[bool] = None
    changed_month_break: Optional[bool] = None
    changed_calendar_relations: Optional[Dict[str, str]] = None
    source_path: Optional[str] = None


class BackGenerationConditions(PartialOutput):
    qualification_ruleset_id: Optional[str] = None
    qualification_ruleset_version: Optional[str] = None
    qualification_source_url: Optional[str] = None
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_sha256: Optional[str] = None
    source_url: Optional[str] = None
    clauses: Optional[List[Dict[str, Any]]] = None
    textual_issues: Optional[List[Dict[str, Any]]] = None
    sources: Optional[List[BackGenerationSource]] = None
    focus: Optional[BackGenerationSource] = None
    adjudication: Optional[str] = None
    scope: Optional[str] = None
