"""Projectable facts that distinguish clash, day break, filling and scatter."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput


class ClashClause(PartialOutput):
    id: str | None = None
    pdf_pages: list[int] | None = None
    quote: str | None = None


class ClashActor(PartialOutput):
    location: str | None = None
    position: int | None = None
    branch: str | None = None
    activity_condition_match: bool | None = None
    status: str | None = None


class LineClash(PartialOutput):
    qualified_back_control_condition: bool | None = None
    own_si_growth_source_path: str | None = None
    position: int | None = None
    branch: str | None = None
    is_day_clash: bool | None = None
    day_void_fill_condition: bool | None = None
    day_break_condition: bool | None = None
    day_break_status: str | None = None
    day_clash_harm_condition: bool | None = None
    moving_scatter_condition: bool | None = None
    scatter_status: str | None = None
    has_confirmed_qi: bool | None = None
    activity_condition_match: bool | None = None
    clash_actors: list[ClashActor] | None = None
    back_clash: bool | None = None
    back_control: bool | None = None
    source_path: str | None = None


class ClashConditions(PartialOutput):
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_url: str | None = None
    clauses: list[ClashClause] | None = None
    textual_issues: list[dict[str, OpenJsonValue]] | None = None
    lines: list[LineClash] | None = None
    focus: LineClash | None = None
    adjudication: str | None = None
    scope: str | None = None
