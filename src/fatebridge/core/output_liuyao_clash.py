"""Projectable facts that distinguish clash, day break, filling and scatter."""

from typing import Any, Dict, List, Optional

from .output_base import PartialOutput


class ClashClause(PartialOutput):
    id: Optional[str] = None
    pdf_pages: Optional[List[int]] = None
    quote: Optional[str] = None


class ClashActor(PartialOutput):
    location: Optional[str] = None
    position: Optional[int] = None
    branch: Optional[str] = None
    activity_condition_match: Optional[bool] = None
    status: Optional[str] = None


class LineClash(PartialOutput):
    qualified_back_control_condition: Optional[bool] = None
    own_si_growth_source_path: Optional[str] = None
    position: Optional[int] = None
    branch: Optional[str] = None
    is_day_clash: Optional[bool] = None
    day_void_fill_condition: Optional[bool] = None
    day_break_condition: Optional[bool] = None
    day_break_status: Optional[str] = None
    day_clash_harm_condition: Optional[bool] = None
    moving_scatter_condition: Optional[bool] = None
    scatter_status: Optional[str] = None
    has_confirmed_qi: Optional[bool] = None
    activity_condition_match: Optional[bool] = None
    clash_actors: Optional[List[ClashActor]] = None
    back_clash: Optional[bool] = None
    back_control: Optional[bool] = None
    source_path: Optional[str] = None


class ClashConditions(PartialOutput):
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    clauses: Optional[List[ClashClause]] = None
    textual_issues: Optional[List[Dict[str, Any]]] = None
    lines: Optional[List[LineClash]] = None
    focus: Optional[LineClash] = None
    adjudication: Optional[str] = None
    scope: Optional[str] = None
