"""Partial output contracts for shared original own-back-generation gates."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput


class BackGenerationSource(PartialOutput):
    position: int | None = None
    branch: str | None = None
    is_actual_moving: bool | None = None
    changed_branch: str | None = None
    changed_relation: str | None = None
    is_back_generation: bool | None = None
    condition_match: bool | None = None
    raw_condition_match: bool | None = None
    month_break_qualified_gate: bool | None = None
    raw_status: str | None = None
    penalty_source_path: str | None = None
    status: str | None = None
    changed_void: bool | None = None
    changed_day_void_fill: bool | None = None
    changed_month_break: bool | None = None
    changed_calendar_relations: dict[str, str] | None = None
    source_path: str | None = None


class BackGenerationConditions(PartialOutput):
    qualification_ruleset_id: str | None = None
    qualification_ruleset_version: str | None = None
    qualification_source_url: str | None = None
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_url: str | None = None
    clauses: list[dict[str, OpenJsonValue]] | None = None
    textual_issues: list[dict[str, OpenJsonValue]] | None = None
    sources: list[BackGenerationSource] | None = None
    focus: BackGenerationSource | None = None
    adjudication: str | None = None
    scope: str | None = None
