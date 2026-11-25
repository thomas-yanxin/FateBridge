"""Optional fields for original-book day-growth qualifications."""

from pydantic import Field

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_liuyao_stages import StageQuery


class MovingRootStep(PartialOutput):
    position: int | None = None
    location: str | None = None
    branch: str | None = None
    source_position: int | None = None
    kind: str | None = None
    source_path: str | None = None


class MovingEarthCandidate(PartialOutput):
    source_position: int | None = None
    source_branch: str | None = None
    source_condition_match: bool | None = None
    activity_condition_match: bool | None = None
    source_generation_path: str | None = None
    independent_root_proven: bool | None = None
    root_proof: list[MovingRootStep] | None = None
    condition_match: bool | None = None
    status: str | None = None


class MetalMovingSupport(PartialOutput):
    application_source_url: str | None = None
    application_source_sha256: str | None = None
    application_interpretation: str | None = None
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    source_path: str | None = None
    condition_match: bool | None = Field(
        default=None,
        description="是否已核完本项独立动土扶持证明；False不表示全局无扶，来源资格的真假与未决另列。",
    )
    excluded_target_position: int | None = None
    candidates: list[MovingEarthCandidate] | None = None
    successful_positions: list[int] | None = None
    scope: str | None = None


class OwnSiCalendarRoot(PartialOutput):
    location: str | None = None
    branch: str | None = None
    relation: str | None = None
    source_path: str | None = None


class OwnSiGrowth(PartialOutput):
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    position: int | None = None
    branch: str | None = None
    changed_branch: str | None = None
    is_actual_moving: bool | None = None
    raw_back_relation: str | None = None
    raw_back_control: bool | None = None
    raw_outgoing_obstructions: list[str] | None = None
    support_condition_match: bool | None = None
    calendar_supports: list[OwnSiCalendarRoot] | None = None
    moving_support: MetalMovingSupport | None = None
    changed_void: bool | None = None
    changed_day_void_fill: bool | None = None
    changed_month_break: bool | None = None
    changed_current_month_obstruction: bool | None = None
    changed_admission_condition: bool | None = None
    condition_match: bool | None = None
    qualified_back_control_condition: bool | None = None
    status: str | None = None
    source_path: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    admission_source_url: str | None = None
    admission_interpretation: str | None = None
    actual_total_effect_adjudicated: bool | None = None
    scope: str | None = None


class MovingSiSource(PartialOutput):
    combined_effect_condition: bool | None = None
    source_position: int | None = None
    source_branch: str | None = None
    raw_relation: str | None = None
    raw_control_condition: bool | None = None
    source_control_admission: bool | None = None
    growth_condition_match: bool | None = None
    qualified_control_condition: bool | None = Field(
        default=None, description="沿用原动静克制条件许可，不表示生克合并后的最终效力"
    )
    control_source_path: str | None = None
    source_path: str | None = None
    status: str | None = None


class MovingSiGrowth(PartialOutput):
    combined_effect_adjudicated: bool | None = None
    cross_passage_source_urls: list[str] | None = None
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    position: int | None = None
    branch: str | None = None
    actual_si_positions: list[int] | None = None
    textual_encounter_condition: bool | None = None
    support_condition_match: bool | None = None
    condition_match: bool | None = None
    calendar_supports: list[OwnSiCalendarRoot] | None = None
    moving_support: MetalMovingSupport | None = None
    sources: list[MovingSiSource] | None = None
    source_path: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    actual_total_effect_adjudicated: bool | None = None
    scope: str | None = None


class GrowthLine(PartialOutput):
    condition_match_scope: str | None = None
    moving_si: MovingSiGrowth | None = None
    own_changed_si: OwnSiGrowth | None = None
    moving_support: MetalMovingSupport | None = None
    position: int | None = None
    branch: str | None = None
    element: str | None = None
    day_branch: str | None = None
    position_query: StageQuery | None = None
    position_match: bool | None = None
    condition_match: bool | None = None
    penalty_growth_source_path: str | None = None
    penalty_growth_source_url: str | None = None
    day_yin_growth_excluded: bool | None = None
    metal_si_exception_applicable: bool | None = None
    independent_month_support: bool | None = None
    month_support_fact_paths: list[str] | None = None
    raw_day_element_relation: str | None = None
    day_control_in_calendar_oppositions: bool | None = None
    other_oppositions: list[dict[str, OpenJsonValue]] | None = None
    pending_supports: list[dict[str, OpenJsonValue]] | None = None
    status: str | None = None
    source_path: str | None = None
    source_url: str | None = None
    actual_total_effect_adjudicated: bool | None = None


class GrowthConditions(PartialOutput):
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    clauses: list[dict[str, OpenJsonValue]] | None = None
    lines: list[GrowthLine] | None = None
    focus: GrowthLine | None = None
    scope: str | None = None
