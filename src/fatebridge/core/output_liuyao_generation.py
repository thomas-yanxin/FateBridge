"""Partial output contracts for directed generation and target admission."""

from typing import Any, Dict, List, Optional

from fatebridge.core.output_base import PartialOutput


class GenerationSource(PartialOutput):
    back_generation_source_path: Optional[str] = None
    position: Optional[int] = None
    branch: Optional[str] = None
    condition_match: Optional[bool] = None
    status: Optional[str] = None
    activity_condition_match: Optional[bool] = None
    back_generation_condition: Optional[bool] = None
    strength_supported_unopposed: Optional[bool] = None
    retained_calendar_oppositions: Optional[List[Dict[str, Any]]] = None
    source_path: Optional[str] = None


class GenerationPair(PartialOutput):
    qualification_explanation: Optional[str] = None
    target_yin_generation_allowed: Optional[bool] = None
    penalty_source_path: Optional[str] = None
    source_position: Optional[int] = None
    target_position: Optional[int] = None
    source_branch: Optional[str] = None
    target_branch: Optional[str] = None
    relation: Optional[str] = None
    condition_match: Optional[bool] = None
    status: Optional[str] = None
    target_reception_condition: Optional[bool] = None
    target_status: Optional[str] = None
    benefit_now: Optional[bool] = None
    source_condition_path: Optional[str] = None
    source_path: Optional[str] = None
    source_url: Optional[str] = None


class GenerationFocus(PartialOutput):
    position: Optional[int] = None
    branch: Optional[str] = None
    source_condition_match: Optional[bool] = None
    source_status: Optional[str] = None
    source_condition_path: Optional[str] = None
    source_explanation: Optional[str] = None
    target_reception_condition: Optional[bool] = None
    target_status: Optional[str] = None
    target_explanation: Optional[str] = None
    scope: Optional[str] = None


class GenerationConditions(PartialOutput):
    focus: Optional[GenerationFocus] = None
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    clauses: Optional[List[Dict[str, Any]]] = None
    textual_issues: Optional[List[Dict[str, Any]]] = None
    sources: Optional[List[GenerationSource]] = None
    generations: Optional[List[GenerationPair]] = None
    support_resolution_passes: Optional[int] = None
    adjudication: Optional[str] = None
    scope: Optional[str] = None
