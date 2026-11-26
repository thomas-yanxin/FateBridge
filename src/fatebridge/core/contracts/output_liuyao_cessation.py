"""Optional cessation-position and bounded earth-exception evidence."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput


class CessationQuery(PartialOutput):
    location: str | None = None
    branch: str | None = None
    position_match: bool | None = None
    condition_match: bool | None = None
    status: str | None = None
    actual_cessation_adjudicated: bool | None = None
    source_path: str | None = None
    source_url: str | None = None


class CessationLine(PartialOutput):
    position: int | None = None
    branch: str | None = None
    element: str | None = None
    day: CessationQuery | None = None
    changed: CessationQuery | None = None
    independent_supports: list[dict[str, OpenJsonValue]] | None = None
    excluded_self_or_unqualified_supports: list[dict[str, OpenJsonValue]] | None = None
    pending_supports: list[dict[str, OpenJsonValue]] | None = None
    oppositions: list[dict[str, OpenJsonValue]] | None = None
    independent_support_present: bool | None = None
    total_rootlessness_established: bool | None = None
    strength_source_path: str | None = None
    source_path: str | None = None


class CessationConditions(PartialOutput):
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_url: str | None = None
    clauses: list[dict[str, OpenJsonValue]] | None = None
    lines: list[CessationLine] | None = None
    focus: CessationLine | None = None
    scope: str | None = None
