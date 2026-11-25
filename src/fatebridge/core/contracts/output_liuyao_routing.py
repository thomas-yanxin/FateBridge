"""Projectable route qualifications preserve unknown and blocked stages."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput


class RoutingStage(PartialOutput):
    id: str | None = None
    label: str | None = None
    matched: bool | None = None
    status: str | None = None
    source_paths: list[str] | None = None
    reason: str | None = None


class SuccessiveRoute(PartialOutput):
    chain_id: str | None = None
    positions: list[int] | None = None
    focus_location: str | None = None
    condition_match: bool | None = None
    status: str | None = None
    conditions: list[RoutingStage] | None = None
    blocked_conditions: list[str] | None = None
    pending_conditions: list[str] | None = None
    binding_positions: list[int] | None = None
    obstructed_positions: list[int] | None = None
    source_path: str | None = None
    source_url: str | None = None
    legacy_source_path: str | None = None


class RoutingFocus(PartialOutput):
    location: str | None = None
    position: int | None = None
    condition_match: bool | None = None
    status: str | None = None


class RoutingConditions(PartialOutput):
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    clauses: list[dict[str, OpenJsonValue]] | None = None
    textual_issues: list[dict[str, OpenJsonValue]] | None = None
    routes: list[SuccessiveRoute] | None = None
    focus: RoutingFocus | None = None
    status: str | None = None
    adjudication: str | None = None
    scope: str | None = None
