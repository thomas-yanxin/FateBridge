"""Projection-safe fields for the bounded hidden reception gate."""

from typing import Any, Dict, List, Optional

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_liuyao_growth import MetalMovingSupport
from fatebridge.core.output_liuyao_penalty import PenaltyLine


class FlyingGeneration(PartialOutput):
    raw_condition_match: Optional[bool] = None
    penalty_source_path: Optional[str] = None
    condition_match: Optional[bool] = None
    status: Optional[str] = None
    raw_relation_match: Optional[bool] = None
    source_path: Optional[str] = None
    generation_source_path: Optional[str] = None
    source_generation_condition_match: Optional[bool] = None
    source_generation_status: Optional[str] = None


class HiddenReception(PartialOutput):
    moving_support: Optional[MetalMovingSupport] = None
    penalty: Optional[PenaltyLine] = None
    calendar_growth_rule_applied: Optional[bool] = None
    calendar_growth_source_url: Optional[str] = None
    calendar_growth_ruleset_id: Optional[str] = None
    flying_growth_source_path: Optional[str] = None
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    condition_match: Optional[bool] = None
    status: Optional[str] = None
    source_path: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    clauses: Optional[List[Dict[str, Any]]] = None
    textual_issues: Optional[List[Dict[str, Any]]] = None
    flying_generation: Optional[FlyingGeneration] = None
    support_reasons: Optional[List[str]] = None
    calendar_support_reasons: Optional[List[str]] = None
    pending_calendar_support_reasons: Optional[List[str]] = None
    pending_reasons: Optional[List[str]] = None
    blocking_reasons: Optional[List[str]] = None
    supporting_positions: Optional[List[int]] = None
    pending_generation_positions: Optional[List[int]] = None
    possible_control_positions: Optional[List[int]] = None
    is_current_void: Optional[bool] = None
    is_month_break: Optional[bool] = None
    stage_condition_source_path: Optional[str] = None
    stage_ruleset_id: Optional[str] = None
    stage_unknown_is_relevant: Optional[bool] = None
    adjudication: Optional[str] = None
    scope: Optional[str] = None
