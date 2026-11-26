"""Optional evidence fields preserve projection and unresolved time horizon."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput


class VoidRule(PartialOutput):
    rule_id: str | None = None
    condition: str | None = None
    matched: bool | None = None
    qualified_matched: bool | None = None
    qualification_source_path: str | None = None
    status: str | None = None
    source_url: str | None = None


class VoidLine(PartialOutput):
    location: str | None = None
    position: int | None = None
    branch: str | None = None
    is_xunkong: bool | None = None
    changed_is_xunkong: bool | None = None
    day_void_fill_condition: bool | None = None
    flying_branch: str | None = None
    not_empty_conditions: list[VoidRule] | None = None
    empty_conditions: list[VoidRule] | None = None
    classification: str | None = None
    is_true_void: bool | None = None
    is_permanently_void: bool | None = None
    permanent_void_status: str | None = None
    requires_horizon_review: bool | None = None
    source_url: str | None = None


class VoidConditions(PartialOutput):
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_url: str | None = None
    lines: list[VoidLine] | None = None
    hidden: list[VoidLine] | None = None
    focus: VoidLine | None = None
    textual_issues: list[dict[str, OpenJsonValue]] | None = None
    horizon_status: str | None = None
    scope: str | None = None
