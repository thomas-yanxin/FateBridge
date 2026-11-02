"""Projectable route qualifications preserve unknown and blocked stages."""

from typing import Any, Dict, List, Optional

from .output_base import PartialOutput


class RoutingStage(PartialOutput):
    id: Optional[str] = None
    label: Optional[str] = None
    matched: Optional[bool] = None
    status: Optional[str] = None
    source_paths: Optional[List[str]] = None
    reason: Optional[str] = None


class SuccessiveRoute(PartialOutput):
    chain_id: Optional[str] = None
    positions: Optional[List[int]] = None
    focus_location: Optional[str] = None
    condition_match: Optional[bool] = None
    status: Optional[str] = None
    conditions: Optional[List[RoutingStage]] = None
    blocked_conditions: Optional[List[str]] = None
    pending_conditions: Optional[List[str]] = None
    binding_positions: Optional[List[int]] = None
    obstructed_positions: Optional[List[int]] = None
    source_path: Optional[str] = None
    source_url: Optional[str] = None
    legacy_source_path: Optional[str] = None


class RoutingFocus(PartialOutput):
    location: Optional[str] = None
    position: Optional[int] = None
    condition_match: Optional[bool] = None
    status: Optional[str] = None


class RoutingConditions(PartialOutput):
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    clauses: Optional[List[Dict[str, Any]]] = None
    textual_issues: Optional[List[Dict[str, Any]]] = None
    routes: Optional[List[SuccessiveRoute]] = None
    focus: Optional[RoutingFocus] = None
    status: Optional[str] = None
    adjudication: Optional[str] = None
    scope: Optional[str] = None
