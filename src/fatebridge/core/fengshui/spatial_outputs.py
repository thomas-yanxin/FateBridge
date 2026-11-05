"""Typed spatial facts and projection-compatible public containers."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, JsonValue

from fatebridge.core.output_base import PartialOutput

from .layout_inputs import FormObservation
from .spatial_inputs import (
    CompassDirection,
    PlanPoint,
    RelativePosition,
    ResolvedMoveDomain,
)
from .spatial_sources import ResearchCoverage


class GeometryCheck(BaseModel):
    check_id: str
    object_ids: list[str]
    passed: bool | None
    scope: Literal["engineering_geometry"] = "engineering_geometry"
    measurement: float | None = None
    unit: str | None = None


class SeatGeometry(BaseModel):
    desk_id: str
    subject_ids: list[str] | None = None
    position: PlanPoint
    plan_facing_degrees: float
    sector_anchor: str
    location_directions: list[CompassDirection]
    facing_directions: list[CompassDirection]
    chart_binding_status: Literal[
        "confirmed", "candidate_only", "not_bound", "at_sector_origin"
    ]
    form: FormObservation | None
    backing_distance_m: float | None
    barriers_between: list[str]
    entrance_relative_positions: list[RelativePosition] = []
    window_relative_positions: list[RelativePosition] = []


class DesktopPlacement(BaseModel):
    desk_id: str
    object_id: str
    zone: str | None
    zones: list[str]
    compass_directions: list[CompassDirection]
    world_center: PlanPoint


class ScreenVisibility(BaseModel):
    desk_id: str
    object_id: str
    front_facing: bool
    in_horizontal_view: bool
    model_visible_fraction: float
    unobstructed: bool | None
    blocking_object_ids: list[str]
    candidate_only: bool
    required_visible: bool
    scope: str = (
        "vertical_display_perspective_area_with_opaque_prisms_not_glare_or_readability"
    )


@dataclass
class EvaluatedGeometry:
    seats: list[SeatGeometry]
    checks: list[GeometryCheck]
    desktop_placements: list[DesktopPlacement]
    candidate_only: bool
    body_sectors: dict[str, list[CompassDirection]]
    screen_visibility: list[ScreenVisibility]

    @property
    def physically_feasible(self) -> bool:
        return all(check.passed is True for check in self.checks)


class GeometryOutput(PartialOutput):
    frame_id: str | None = None
    observation_basis: str | None = None
    coordinate_uncertainty_m: float | None = None
    candidate_only: bool | None = None
    physically_feasible: bool | None = None
    seats: list[SeatGeometry] | None = None
    checks: list[GeometryCheck] | None = None
    desktop_placements: list[DesktopPlacement] | None = None
    body_sectors: dict[str, list[CompassDirection]] | None = None
    screen_visibility: list[ScreenVisibility] | None = None


class MeasuredLayoutOutput(PartialOutput):
    status: Literal["complete", "partial"] | None = None
    geometry: GeometryOutput | None = None
    # These records retain their source rule and are preserved whole in arrays.
    scope: str | None = None
    missing_inputs: list[str] | None = None
    readings: list[dict[str, JsonValue]] | None = None
    rule_comparisons: list[dict[str, JsonValue]] | None = None
    search: "MeasuredSearchOutput | None" = None
    limitations: list[str] | None = None
    rule_trace: list[dict[str, JsonValue]] | None = None
    research_completion_status: Literal["complete", "incomplete"] | None = None
    research_coverage: list[ResearchCoverage] | None = None


class SearchReceipt(BaseModel):
    candidate_id: str
    poses: dict[str, dict[str, JsonValue]]
    physically_feasible: bool
    status: Literal["ready", "conditional_option", "candidate_only", "blocked"]
    blocking_reasons: list[str]
    pending_confirmations: list[str]
    rule_dimensions: dict[str, int | None]
    changed_object_count: int
    movement_m: float
    rotation_degrees: float
    pareto_frontier: bool = False


class MeasuredSearchOutput(PartialOutput):
    status: Literal["complete"] | None = None
    evaluated_count: int | None = None
    rejected_count: int | None = None
    feasible_count: int | None = None
    frontier_candidate_ids: list[str] | None = None
    returned_candidate_ids: list[str] | None = None
    omitted_frontier_count: int | None = None
    enumeration_complete: bool | None = None
    resolved_domains: list[ResolvedMoveDomain] | None = None
    selection_policy: str | None = None
    receipts: list[SearchReceipt] | None = None
    candidates: list[dict[str, JsonValue]] | None = None
