"""Western timing chart geometry and primary directions."""

from pydantic import Field

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_chart_geometry import (
    EphemerisReferencePoints,
    HouseAxisConvention,
    HousePositionProjection,
)
from fatebridge.core.contracts.output_chart_motion import LongitudeMotionPolicy
from fatebridge.core.contracts.output_clock_labels import (
    UTCDefinitionEvidence,
    WesternUTCRepresentation,
)
from fatebridge.core.contracts.output_ephemeris import ApparentPositionPolicy
from fatebridge.core.contracts.output_midpoint_geometry import PhysicalEphemerisSource
from fatebridge.core.contracts.output_rotation import EarthRotationPolicy


class WesternPoint(PartialOutput):
    point: str | None = None
    point_label: str | None = None
    absolute_degree: float | None = Field(default=None, ge=0, lt=360)
    degree: float | None = Field(default=None, ge=0, lt=30)
    longitude: float | None = Field(default=None, ge=0, lt=360)
    sign: str | None = None
    sign_label: str | None = None
    house: int | None = None
    house_label: str | None = None
    retrograde: bool | None = None
    natal_absolute_degree: float | None = None
    lot: str | None = None
    lot_label: str | None = None
    angularity: str | None = None
    angularity_label: str | None = None
    planet: str | None = None
    planet_label: str | None = None


class Sect(PartialOutput):
    key: str | None = None
    label: str | None = None


class WesternCalculationBasis(PartialOutput):
    utc_definition: UTCDefinitionEvidence | None = None
    angle_definition: dict[str, OpenJsonValue] | None = None
    utc_representation: WesternUTCRepresentation | None = None
    apparent_position_policy: ApparentPositionPolicy | None = None
    ephemeris_reference_points: EphemerisReferencePoints | None = None
    longitude_motion: LongitudeMotionPolicy | None = None
    physical_ephemeris_source: PhysicalEphemerisSource | None = None
    house_axis_convention: HouseAxisConvention | None = None
    earth_rotation: EarthRotationPolicy | None = None
    house_position_projection: HousePositionProjection | None = None
    engine_backend: str | None = None
    engine_precision: str | None = None
    ephemeris_model: str | None = None
    calendar: str | None = None
    time_scale: str | None = None
    julian_day_tt: float | None = None
    julian_day_ut1: float | None = None
    future_leap_seconds_assumed_unchanged: bool | None = None
    horizon_method: str | None = None
    ayanamsha_model: str | None = None
    ayanamsha_degrees: float | None = None


class ReturnSolver(PartialOutput):
    method_id: str | None = None
    julian_day_tt: float | None = None
    target_longitude: float | None = None
    solved_longitude: float | None = None
    residual_arcseconds: float | None = None
    event_not_after_analysis: bool | None = None


class NatalReference(PartialOutput):
    calculation_basis: WesternCalculationBasis | None = None
    ascendant: WesternPoint | None = None
    medium_coeli: WesternPoint | None = None
    sun: WesternPoint | None = None
    moon: WesternPoint | None = None
    mercury: WesternPoint | None = None
    venus: WesternPoint | None = None
    mars: WesternPoint | None = None
    jupiter: WesternPoint | None = None
    saturn: WesternPoint | None = None
    uranus: WesternPoint | None = None
    neptune: WesternPoint | None = None
    pluto: WesternPoint | None = None
    sect: Sect | None = None
    lots: dict[str, WesternPoint] | None = None


class Location(PartialOutput):
    longitude: float | None = None
    latitude: float | None = None
    timezone: str | None = None


class AspectHit(PartialOutput):
    source: str | None = None
    source_label: str | None = None
    target: str | None = None
    target_label: str | None = None
    aspect: str | None = None
    aspect_label: str | None = None
    orb: float | None = None


class CoordinateEntry(PartialOutput):
    key: str | None = None
    label: str | None = None
    coordinate_degrees: float | None = None
    coordinate_system: str | None = None
    coordinate_label: str | None = None
    arc_applied_degrees: float | None = None


class CoordinateContext(PartialOutput):
    promissor_natal: CoordinateEntry | None = None
    promissor_current: CoordinateEntry | None = None
    significator_natal: CoordinateEntry | None = None
    aspect_target: CoordinateEntry | None = None
    current_orb_degrees: float | None = None


class PrimaryDirectionHit(PartialOutput):
    promissor: str | None = None
    promissor_label: str | None = None
    significator: str | None = None
    significator_label: str | None = None
    aspect: str | None = None
    aspect_label: str | None = None
    aspect_degree: float | None = None
    aspect_variant_degrees: float | None = None
    arc_degrees: float | None = None
    arc_applied_degrees: float | None = None
    event_age_years: float | None = None
    event_datetime: str | None = None
    direction_mode: str | None = None
    direction_mode_label: str | None = None
    coordinate_system: str | None = None
    coordinate_label: str | None = None
    relative_years_from_current: float | None = None
    relative_arc_from_current: float | None = None
    distance_from_current_years: float | None = None
    timing_phase: str | None = None
    timing_phase_label: str | None = None
    coordinate_context: CoordinateContext | None = None


class BoundsEntry(WesternPoint):
    key: str | None = None
    label: str | None = None
    bound_lord: str | None = None
    bound_lord_label: str | None = None
    segment_start_degree: float | None = None
    segment_end_degree: float | None = None


class BoundsOverlay(PartialOutput):
    system: str | None = None
    system_label: str | None = None
    enabled: bool | None = None
    points: dict[str, BoundsEntry] | None = None
    lots: dict[str, BoundsEntry] | None = None


class SignChange(PartialOutput):
    point: str | None = None
    point_label: str | None = None
    from_sign: str | None = None
    from_sign_label: str | None = None
    to_sign: str | None = None
    to_sign_label: str | None = None


class CoordinateDiagnostic(PartialOutput):
    projection: str | None = None
    projection_label: str | None = None
    right_ascension: float | None = None
    declination: float | None = None
    hour_angle_degrees: float | None = None
    semiarc_degrees: float | None = None
    nocturnal_semiarc_degrees: float | None = None
    quadrant: str | None = None
    quadrant_label: str | None = None
    mundane_position_degrees: float | None = None


class PrimaryDirections(PartialOutput):
    method: str | None = None
    method_label: str | None = None
    time_key: str | None = None
    time_key_label: str | None = None
    pd_type: int | None = None
    direction_mode: str | None = None
    direction_mode_label: str | None = None
    coordinate_system: str | None = None
    coordinate_label: str | None = None
    coordinate_backend: str | None = None
    coordinate_precision: str | None = None
    coordinate_diagnostics: dict[str, CoordinateDiagnostic] | None = None
    coordinate_points: dict[str, CoordinateEntry] | None = None
    coordinate_lots: dict[str, CoordinateEntry] | None = None
    current_coordinate_points: dict[str, CoordinateEntry] | None = None
    current_coordinate_lots: dict[str, CoordinateEntry] | None = None
    natal_coordinate_points: dict[str, CoordinateEntry] | None = None
    natal_coordinate_lots: dict[str, CoordinateEntry] | None = None
    directed_coordinate_points: dict[str, CoordinateEntry] | None = None
    directed_coordinate_lots: dict[str, CoordinateEntry] | None = None
    current_age_years: float | None = None
    current_arc_degrees: float | None = None
    current_arc_absolute_degrees: float | None = None
    aspects: list[int] | None = None
    promissors: list[str] | None = None
    timeline: list[PrimaryDirectionHit] | None = None
    current_window: list[PrimaryDirectionHit] | None = None
    exact_window: list[PrimaryDirectionHit] | None = None
    past_window: list[PrimaryDirectionHit] | None = None
    future_window: list[PrimaryDirectionHit] | None = None
    hits: list[PrimaryDirectionHit] | None = None
    exact_hits: list[PrimaryDirectionHit] | None = None
    coordinate_hits: list[PrimaryDirectionHit] | None = None
    approximation: str | None = None
    approximation_label: str | None = None
    analysis_datetime: str | None = None
    show_pd_bounds: bool | None = None
    bounds_overlay: BoundsOverlay | None = None
    directed_points: dict[str, WesternPoint] | None = None
    directed_lots: dict[str, WesternPoint] | None = None
    directed_ascendant: WesternPoint | None = None
    directed_medium_coeli: WesternPoint | None = None
    sign_changes: list[SignChange] | None = None
