"""Optional fields for partial phase knowledge and query applicability."""

from typing import Any, Dict, List, Optional

from fatebridge.core.output_base import PartialOutput


class StageQuery(PartialOutput):
    element: Optional[str] = None
    branch: Optional[str] = None
    location: Optional[str] = None
    expected_stages: Optional[List[str]] = None
    known_stage: Optional[str] = None
    condition_match: Optional[bool] = None
    query_complete: Optional[bool] = None
    table_complete: Optional[bool] = None
    missing_stages: Optional[List[str]] = None
    missing_expected_stages: Optional[List[str]] = None
    source_path: Optional[str] = None
    status: Optional[str] = None


class StageGroup(PartialOutput):
    element: Optional[str] = None
    condition_match: Optional[bool] = None
    all_queries_resolved: Optional[bool] = None
    predicate_determined: Optional[bool] = None
    queries: Optional[List[StageQuery]] = None
    source_path: Optional[str] = None
    status: Optional[str] = None


class HiddenStageConditions(PartialOutput):
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    source_path: Optional[str] = None
    hidden_tomb_cessation: Optional[StageGroup] = None
    flying_tomb_cessation: Optional[StageGroup] = None
    flying_controls_hidden: Optional[bool] = None
    has_relevant_unknown: Optional[bool] = None
    ignored_unknown_groups: Optional[List[str]] = None
    adjudication: Optional[str] = None
    scope: Optional[str] = None


class StageKnowledge(PartialOutput):
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    known_stages: Optional[Dict[str, Dict[str, str]]] = None
    missing_stages: Optional[Dict[str, List[str]]] = None
    clauses: Optional[List[Dict[str, Any]]] = None
    interpretation: Optional[Dict[str, str]] = None
    raw_table_unchanged: Optional[bool] = None
    table_complete: Optional[bool] = None
    adjudication: Optional[str] = None
    scope: Optional[str] = None
