"""Optional cessation-position and bounded earth-exception evidence."""

from typing import Any, Dict, List, Optional

from fatebridge.core.output_base import PartialOutput


class CessationQuery(PartialOutput):
    location: Optional[str] = None
    branch: Optional[str] = None
    position_match: Optional[bool] = None
    condition_match: Optional[bool] = None
    status: Optional[str] = None
    actual_cessation_adjudicated: Optional[bool] = None
    source_path: Optional[str] = None
    source_url: Optional[str] = None


class CessationLine(PartialOutput):
    position: Optional[int] = None
    branch: Optional[str] = None
    element: Optional[str] = None
    day: Optional[CessationQuery] = None
    changed: Optional[CessationQuery] = None
    independent_supports: Optional[List[Dict[str, Any]]] = None
    excluded_self_or_unqualified_supports: Optional[List[Dict[str, Any]]] = None
    pending_supports: Optional[List[Dict[str, Any]]] = None
    oppositions: Optional[List[Dict[str, Any]]] = None
    independent_support_present: Optional[bool] = None
    total_rootlessness_established: Optional[bool] = None
    strength_source_path: Optional[str] = None
    source_path: Optional[str] = None


class CessationConditions(PartialOutput):
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    clauses: Optional[List[Dict[str, Any]]] = None
    lines: Optional[List[CessationLine]] = None
    focus: Optional[CessationLine] = None
    scope: Optional[str] = None
