"""Projectable chapter-14 directed-control condition facts."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput


class ControlClause(PartialOutput):
    id: str | None = None
    pdf_page: int | None = None
    quote: str | None = None


class ActivityCondition(PartialOutput):
    position: int | None = None
    raw_activity: str | None = None
    activity_condition_match: bool | None = None
    status: str | None = None


class DirectedControl(PartialOutput):
    metal_si_combined_effect_condition: bool | None = None
    metal_si_effect_status: str | None = None
    raw_condition_match: bool | None = None
    raw_status: str | None = None
    metal_si_growth_condition: bool | None = None
    source_control_admission: bool | None = None
    metal_si_growth_source_path: str | None = None
    metal_si_ruleset_id: str | None = None
    metal_si_ruleset_version: str | None = None
    source_void_fill_control_condition: bool | None = None
    source_void_fill_used: bool | None = None
    void_fill_qualification_path: str | None = None
    source_back_generation_condition: bool | None = None
    back_generation_source_path: str | None = None
    source_rescue_used: bool | None = None
    source_calendar_oppositions: list[dict[str, OpenJsonValue]] | None = None
    source_position: int | None = None
    target_position: int | None = None
    source_branch: str | None = None
    target_branch: str | None = None
    source_active: bool | None = None
    target_active: bool | None = None
    source_activity_match: bool | None = None
    target_activity_match: bool | None = None
    relation: str | None = None
    condition_match: bool | None = None
    status: str | None = None
    source_calendar_supported: bool | None = None
    target_calendar_supported: bool | None = None
    source_confirmed_active_controllers: list[int] | None = None
    source_pending_active_controllers: list[int] | None = None
    source_competing_active_controls: list[int] | None = None
    source_obstructions: list[str] | None = None
    emit_edge: bool | None = None
    rule_id: str | None = None
    source_url: str | None = None
    fact_path: str | None = None


class VoidFillQualification(PartialOutput):
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_urls: list[str] | None = None
    clauses: list[dict[str, OpenJsonValue]] | None = None
    precedence: str | None = None
    scope: str | None = None


class ControlConditions(PartialOutput):
    void_fill_qualification: VoidFillQualification | None = None
    back_generation_source_path: str | None = None
    support_ruleset_id: str | None = None
    support_ruleset_version: str | None = None
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_url: str | None = None
    clauses: list[ControlClause] | None = None
    textual_issues: list[dict[str, OpenJsonValue]] | None = None
    controls: list[DirectedControl] | None = None
    activity_conditions: list[ActivityCondition] | None = None
    activity_resolution_passes: int | None = None
    unresolved_day_clash_positions: list[int] | None = None
    adjudication: str | None = None
    scope: str | None = None
