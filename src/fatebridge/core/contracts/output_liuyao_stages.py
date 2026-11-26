"""Optional fields for partial phase knowledge and query applicability."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput


class StageQuery(PartialOutput):
    element: str | None = None
    branch: str | None = None
    location: str | None = None
    expected_stages: list[str] | None = None
    known_stage: str | None = None
    condition_match: bool | None = None
    query_complete: bool | None = None
    table_complete: bool | None = None
    missing_stages: list[str] | None = None
    missing_expected_stages: list[str] | None = None
    source_path: str | None = None
    status: str | None = None


class StageGroup(PartialOutput):
    element: str | None = None
    condition_match: bool | None = None
    all_queries_resolved: bool | None = None
    predicate_determined: bool | None = None
    queries: list[StageQuery] | None = None
    source_path: str | None = None
    status: str | None = None


class HiddenStageConditions(PartialOutput):
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    source_path: str | None = None
    hidden_tomb_cessation: StageGroup | None = None
    flying_tomb_cessation: StageGroup | None = None
    flying_controls_hidden: bool | None = None
    has_relevant_unknown: bool | None = None
    ignored_unknown_groups: list[str] | None = None
    adjudication: str | None = None
    scope: str | None = None


class FireStageCycle(PartialOutput):
    source_url: str | None = None
    source_section: str | None = None
    stage_order_url: str | None = None
    start_branch: str | None = None
    branch_direction: str | None = None
    offsets_from_growth: dict[str, int] | None = None
    derived_positions: dict[str, str] | None = None


class StageKnowledge(PartialOutput):
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    literal_ruleset_version: str | None = None
    literal_source_stages: dict[str, dict[str, str]] | None = None
    fire_cycle_derivation: FireStageCycle | None = None
    known_stages: dict[str, dict[str, str]] | None = None
    missing_stages: dict[str, list[str]] | None = None
    clauses: list[dict[str, OpenJsonValue]] | None = None
    interpretation: dict[str, str] | None = None
    raw_table_unchanged: bool | None = None
    table_complete: bool | None = None
    adjudication: str | None = None
    scope: str | None = None
