"""Optional evidence fields preserve projection and unresolved time horizon."""

from typing import Any, Dict, List, Optional

from .output_base import PartialOutput


class VoidRule(PartialOutput):
    rule_id: Optional[str] = None
    condition: Optional[str] = None
    matched: Optional[bool] = None
    qualified_matched: Optional[bool] = None
    status: Optional[str] = None
    source_url: Optional[str] = None


class VoidLine(PartialOutput):
    location: Optional[str] = None
    position: Optional[int] = None
    branch: Optional[str] = None
    is_xunkong: Optional[bool] = None
    changed_is_xunkong: Optional[bool] = None
    day_void_fill_condition: Optional[bool] = None
    flying_branch: Optional[str] = None
    not_empty_conditions: Optional[List[VoidRule]] = None
    empty_conditions: Optional[List[VoidRule]] = None
    classification: Optional[str] = None
    is_true_void: Optional[bool] = None
    is_permanently_void: Optional[bool] = None
    permanent_void_status: Optional[str] = None
    requires_horizon_review: Optional[bool] = None
    source_url: Optional[str] = None


class VoidConditions(PartialOutput):
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    lines: Optional[List[VoidLine]] = None
    hidden: Optional[List[VoidLine]] = None
    focus: Optional[VoidLine] = None
    textual_issues: Optional[List[Dict[str, Any]]] = None
    horizon_status: Optional[str] = None
    scope: Optional[str] = None
