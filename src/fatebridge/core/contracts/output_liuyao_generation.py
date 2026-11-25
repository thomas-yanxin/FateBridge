"""Partial output contracts for directed generation and target admission."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput


class GenerationSource(PartialOutput):
    back_generation_source_path: str | None = None
    position: int | None = None
    branch: str | None = None
    condition_match: bool | None = None
    status: str | None = None
    activity_condition_match: bool | None = None
    back_generation_condition: bool | None = None
    strength_supported_unopposed: bool | None = None
    retained_calendar_oppositions: list[dict[str, OpenJsonValue]] | None = None
    source_path: str | None = None


class GenerationPair(PartialOutput):
    qualification_explanation: str | None = None
    target_yin_generation_allowed: bool | None = None
    penalty_source_path: str | None = None
    source_position: int | None = None
    target_position: int | None = None
    source_branch: str | None = None
    target_branch: str | None = None
    relation: str | None = None
    condition_match: bool | None = None
    status: str | None = None
    target_reception_condition: bool | None = None
    target_status: str | None = None
    benefit_now: bool | None = None
    source_condition_path: str | None = None
    source_path: str | None = None
    source_url: str | None = None


class GenerationFocus(PartialOutput):
    position: int | None = None
    branch: str | None = None
    source_condition_match: bool | None = None
    source_status: str | None = None
    source_condition_path: str | None = None
    source_explanation: str | None = None
    target_reception_condition: bool | None = None
    target_status: str | None = None
    target_explanation: str | None = None
    scope: str | None = None


class GenerationConditions(PartialOutput):
    focus: GenerationFocus | None = None
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    clauses: list[dict[str, OpenJsonValue]] | None = None
    textual_issues: list[dict[str, OpenJsonValue]] | None = None
    sources: list[GenerationSource] | None = None
    generations: list[GenerationPair] | None = None
    support_resolution_passes: int | None = None
    adjudication: str | None = None
    scope: str | None = None
