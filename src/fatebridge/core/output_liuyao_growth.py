"""Optional fields for original-book day-growth qualifications."""

from typing import Any, Dict, List, Optional

from pydantic import Field

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_liuyao_stages import StageQuery


class MovingRootStep(PartialOutput):
    position: Optional[int] = None
    location: Optional[str] = None
    branch: Optional[str] = None
    source_position: Optional[int] = None
    kind: Optional[str] = None
    source_path: Optional[str] = None


class MovingEarthCandidate(PartialOutput):
    source_position: Optional[int] = None
    source_branch: Optional[str] = None
    source_condition_match: Optional[bool] = None
    activity_condition_match: Optional[bool] = None
    source_generation_path: Optional[str] = None
    independent_root_proven: Optional[bool] = None
    root_proof: Optional[List[MovingRootStep]] = None
    condition_match: Optional[bool] = None
    status: Optional[str] = None


class MetalMovingSupport(PartialOutput):
    application_source_url: Optional[str] = None
    application_source_sha256: Optional[str] = None
    application_interpretation: Optional[str] = None
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    source_path: Optional[str] = None
    condition_match: Optional[bool] = Field(
        default=None,
        description="是否已核完本项独立动土扶持证明；False不表示全局无扶，来源资格的真假与未决另列。",
    )
    excluded_target_position: Optional[int] = None
    candidates: Optional[List[MovingEarthCandidate]] = None
    successful_positions: Optional[List[int]] = None
    scope: Optional[str] = None


class OwnSiCalendarRoot(PartialOutput):
    location: Optional[str] = None
    branch: Optional[str] = None
    relation: Optional[str] = None
    source_path: Optional[str] = None


class OwnSiGrowth(PartialOutput):
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    position: Optional[int] = None
    branch: Optional[str] = None
    changed_branch: Optional[str] = None
    is_actual_moving: Optional[bool] = None
    raw_back_relation: Optional[str] = None
    raw_back_control: Optional[bool] = None
    raw_outgoing_obstructions: Optional[List[str]] = None
    support_condition_match: Optional[bool] = None
    calendar_supports: Optional[List[OwnSiCalendarRoot]] = None
    moving_support: Optional[MetalMovingSupport] = None
    changed_void: Optional[bool] = None
    changed_day_void_fill: Optional[bool] = None
    changed_month_break: Optional[bool] = None
    changed_current_month_obstruction: Optional[bool] = None
    changed_admission_condition: Optional[bool] = None
    condition_match: Optional[bool] = None
    qualified_back_control_condition: Optional[bool] = None
    status: Optional[str] = None
    source_path: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    admission_source_url: Optional[str] = None
    admission_interpretation: Optional[str] = None
    actual_total_effect_adjudicated: Optional[bool] = None
    scope: Optional[str] = None


class MovingSiSource(PartialOutput):
    combined_effect_condition: Optional[bool] = None
    source_position: Optional[int] = None
    source_branch: Optional[str] = None
    raw_relation: Optional[str] = None
    raw_control_condition: Optional[bool] = None
    source_control_admission: Optional[bool] = None
    growth_condition_match: Optional[bool] = None
    qualified_control_condition: Optional[bool] = Field(
        default=None, description="沿用原动静克制条件许可，不表示生克合并后的最终效力"
    )
    control_source_path: Optional[str] = None
    source_path: Optional[str] = None
    status: Optional[str] = None


class MovingSiGrowth(PartialOutput):
    combined_effect_adjudicated: Optional[bool] = None
    cross_passage_source_urls: Optional[List[str]] = None
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    position: Optional[int] = None
    branch: Optional[str] = None
    actual_si_positions: Optional[List[int]] = None
    textual_encounter_condition: Optional[bool] = None
    support_condition_match: Optional[bool] = None
    condition_match: Optional[bool] = None
    calendar_supports: Optional[List[OwnSiCalendarRoot]] = None
    moving_support: Optional[MetalMovingSupport] = None
    sources: Optional[List[MovingSiSource]] = None
    source_path: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    actual_total_effect_adjudicated: Optional[bool] = None
    scope: Optional[str] = None


class GrowthLine(PartialOutput):
    condition_match_scope: Optional[str] = None
    moving_si: Optional[MovingSiGrowth] = None
    own_changed_si: Optional[OwnSiGrowth] = None
    moving_support: Optional[MetalMovingSupport] = None
    position: Optional[int] = None
    branch: Optional[str] = None
    element: Optional[str] = None
    day_branch: Optional[str] = None
    position_query: Optional[StageQuery] = None
    position_match: Optional[bool] = None
    condition_match: Optional[bool] = None
    penalty_growth_source_path: Optional[str] = None
    penalty_growth_source_url: Optional[str] = None
    day_yin_growth_excluded: Optional[bool] = None
    metal_si_exception_applicable: Optional[bool] = None
    independent_month_support: Optional[bool] = None
    month_support_fact_paths: Optional[List[str]] = None
    raw_day_element_relation: Optional[str] = None
    day_control_in_calendar_oppositions: Optional[bool] = None
    other_oppositions: Optional[List[Dict[str, Any]]] = None
    pending_supports: Optional[List[Dict[str, Any]]] = None
    status: Optional[str] = None
    source_path: Optional[str] = None
    source_url: Optional[str] = None
    actual_total_effect_adjudicated: Optional[bool] = None


class GrowthConditions(PartialOutput):
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    clauses: Optional[List[Dict[str, Any]]] = None
    lines: Optional[List[GrowthLine]] = None
    focus: Optional[GrowthLine] = None
    scope: Optional[str] = None
