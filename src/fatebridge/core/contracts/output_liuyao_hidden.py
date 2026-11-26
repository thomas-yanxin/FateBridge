"""Projection-safe fields for the bounded hidden reception gate."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_liuyao_growth import MetalMovingSupport
from fatebridge.core.contracts.output_liuyao_penalty import PenaltyLine


class FlyingGeneration(PartialOutput):
    raw_condition_match: bool | None = None
    penalty_source_path: str | None = None
    condition_match: bool | None = None
    status: str | None = None
    raw_relation_match: bool | None = None
    source_path: str | None = None
    generation_source_path: str | None = None
    source_generation_condition_match: bool | None = None
    source_generation_status: str | None = None


class HiddenReception(PartialOutput):
    moving_support: MetalMovingSupport | None = None
    penalty: PenaltyLine | None = None
    calendar_growth_rule_applied: bool | None = None
    calendar_growth_source_url: str | None = None
    calendar_growth_ruleset_id: str | None = None
    flying_growth_source_path: str | None = None
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    condition_match: bool | None = None
    status: str | None = None
    source_path: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    clauses: list[dict[str, OpenJsonValue]] | None = None
    textual_issues: list[dict[str, OpenJsonValue]] | None = None
    flying_generation: FlyingGeneration | None = None
    support_reasons: list[str] | None = None
    calendar_support_reasons: list[str] | None = None
    pending_calendar_support_reasons: list[str] | None = None
    pending_reasons: list[str] | None = None
    blocking_reasons: list[str] | None = None
    supporting_positions: list[int] | None = None
    pending_generation_positions: list[int] | None = None
    possible_control_positions: list[int] | None = None
    is_current_void: bool | None = None
    is_month_break: bool | None = None
    stage_condition_source_path: str | None = None
    stage_ruleset_id: str | None = None
    stage_unknown_is_relevant: bool | None = None
    adjudication: str | None = None
    scope: str | None = None
