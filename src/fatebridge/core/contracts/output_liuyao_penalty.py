"""Optional, projection-safe scoped penalty presence and effect qualifiers."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput


class PenaltyActor(PartialOutput):
    location: str | None = None
    position: int | None = None
    branch: str | None = None
    presence_condition_match: bool | None = None
    activity_source_path: str | None = None
    reason: str | None = None


class PenaltyLine(PartialOutput):
    position: int | None = None
    branch: str | None = None
    subject_kind: str | None = None
    applicable: bool | None = None
    condition_match: bool | None = None
    effect_condition_match: bool | None = None
    yin_generation_allowed: bool | None = None
    day_yin_growth_applicable: bool | None = None
    day_yin_growth_allowed: bool | None = None
    actors: list[PenaltyActor] | None = None
    ignored_actors: list[PenaltyActor] | None = None
    source_path: str | None = None
    source_url: str | None = None
    status: str | None = None


class PenaltyConditions(PartialOutput):
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    clauses: list[dict[str, OpenJsonValue]] | None = None
    quotation_errata: dict[str, OpenJsonValue] | None = None
    precedence: dict[str, OpenJsonValue] | None = None
    lines: list[PenaltyLine] | None = None
    focus: PenaltyLine | None = None
    scope: str | None = None
