"""Output contracts for Western timing, lifespan, horary, and electional astrology."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, JsonValue

from fatebridge.core.contracts.astro import (
    BirthClockConversion,
    EphemerisReferencePoints,
    FixedStarProfile,
    HouseAxisConvention,
    HousePositionProjection,
    LongitudeMotionPolicy,
    PlanetaryHours,
    SolarConditionPolicy,
)
from fatebridge.core.contracts.base import OpenJsonValue, PartialOutput, ProjectedOutput
from fatebridge.core.contracts.common import (
    AnalysisContext,
    C04UT1Evidence,
    CivilPointEvidence,
    Object,
    UTCDefinitionEvidence,
    WesternUTCRepresentation,
)
from fatebridge.core.contracts.midpoints import (
    ApparentPositionPolicy,
    EarthRotationPolicy,
    PhysicalEphemerisSource,
)
from fatebridge.core.receipt_models import RunMetadata


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
    total_timeline_count: int | None = None
    timeline_truncated: bool | None = None
    current_window: list[PrimaryDirectionHit] | None = None
    current_window_total_count: int | None = None
    exact_window: list[PrimaryDirectionHit] | None = None
    exact_window_total_count: int | None = None
    past_window: list[PrimaryDirectionHit] | None = None
    past_window_total_count: int | None = None
    future_window: list[PrimaryDirectionHit] | None = None
    future_window_total_count: int | None = None
    hits: list[PrimaryDirectionHit] | None = None
    hits_total_count: int | None = None
    exact_hits: list[PrimaryDirectionHit] | None = None
    exact_hits_total_count: int | None = None
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


class LillyDignity(PartialOutput):
    rule_id: str | None = None
    status: str | None = None
    planet: str | None = None
    longitude: float | None = None
    sign: str | None = None
    degree_in_sign: float | None = None
    chart_sect: str | None = None
    dignities: list[str] | None = None
    unknown_dignities: list[str] | None = None
    debilities: list[str] | None = None
    peregrine: bool | None = None
    lords: dict[str, str | None] | None = None
    bound_start_degree: int | None = None
    bound_end_degree: int | None = None
    exaltation_degree_in_sign: int | None = None
    source_pages: list[int] | None = None
    boundary_policy: str | None = None


class LillyReception(PartialOutput):
    rule_id: str | None = None
    receiver: str | None = None
    guest: str | None = None
    guest_longitude: float | None = None
    guest_sign: str | None = None
    chart_sect: str | None = None
    allowed_dignities: list[str] | None = None
    dignities: list[str] | None = None
    unknown_dignities: list[str] | None = None
    receives: bool | None = None
    source_pages: list[int] | None = None


class LillyPairReception(PartialOutput):
    rule_id: str | None = None
    status: str | None = None
    directions: list[LillyReception] | None = None
    mutual: bool | None = None
    mutual_same_kind: list[str] | None = None


class LillyCondition(PartialOutput):
    code: str | None = None
    passed: bool | None = None
    status: str | None = None
    source_pages: list[int] | None = None
    detail: str | None = None


class LillyHouseCondition(PartialOutput):
    occupied_house: int | None = None
    house_class: str | None = None
    p48_strength_rank: int | None = None
    p48_rank_condition: str | None = None
    p115_house_points: int | None = None
    points_scope: str | None = None
    assignment_policy: str | None = None
    house_system: str | None = None
    zodiac_type: str | None = None
    source_method_scope: str | None = None
    source_url: str | None = None
    source_pages: list[int] | None = None
    full_original_text_acceptance: bool | None = None


class LillyHouseAssignment(PartialOutput):
    rule_id: str | None = None
    source_url: str | None = None
    source_pages: list[int] | None = None
    status: str | None = None
    unavailable_reason: str | None = None
    geometric_house: int | None = None
    assigned_house: int | None = None
    changed_from_geometric_house: bool | None = None
    five_degree_limit: int | None = None
    boundary_policy: str | None = None
    assignment_policy: str | None = None
    house_system: str | None = None
    zodiac_type: str | None = None
    source_method_scope: str | None = None
    source_exception: str | None = None
    full_original_text_acceptance: bool | None = None
    longitude: float | None = None
    lower_cusp: float | None = None
    next_cusp: float | None = None
    previous_cusp_gap_degrees: float | None = None
    next_cusp_gap_degrees: float | None = None
    previous_cusp_gap_exact_degrees: str | None = None
    next_cusp_gap_exact_degrees: str | None = None
    assigned_p115_house_points: int | None = None
    assigned_p145_house_points: int | None = None
    conditional_reading_zh: str | None = None


class HoraryPlanet(WesternPoint):
    house_assignment: LillyHouseAssignment | None = None
    occupied_house: int | None = None
    house_condition: LillyHouseCondition | None = None
    speed: float | None = None
    dignities: list[str] | None = None
    essential_condition: LillyDignity | None = None


class HoraryAspect(PartialOutput):
    orb_profile: str | None = None
    orb_limit: float | None = None
    separation: float | None = None
    ray_degrees: int | None = None
    after_days: float | None = None
    julian_day_tt: float | None = None
    root_bracket_tt: list[float] | None = None
    moon_longitude: float | None = None
    other_longitude: float | None = None
    moon_latitude: float | None = None
    other_latitude: float | None = None
    datetime_utc: str | None = None
    inside_current_orb: bool | None = None
    angle: float | None = None
    aspect: str | None = None
    aspect_label: str | None = None
    orb: float | None = None
    other: str | None = None
    other_label: str | None = None
    applying: bool | None = None
    phase: str | None = None


class HoraryMotionBasis(PartialOutput):
    future_speed_policy: dict[str, OpenJsonValue] | None = None
    ephemeris_reference_points: EphemerisReferencePoints | None = None
    longitude_motion: LongitudeMotionPolicy | None = None
    status: str | None = None
    method_id: str | None = None
    constant_velocity_projection: bool | None = None
    degrees_left_in_sign: float | None = None
    sign_exit_after_days: float | None = None
    sign_exit_julian_day_tt: float | None = None
    sign_exit_root_bracket_tt: list[float] | None = None
    start_julian_day_tt: float | None = None
    contacts: list[HoraryAspect] | None = None
    ambiguous_boundary_contacts: list[HoraryAspect] | None = None
    void_of_course: bool | None = None
    unavailable_reason: str | None = None
    source_url: str | None = None
    source_scope: str | None = None
    time_scale: str | None = None
    scan_step_days: float | None = None
    scan_guard_days: int | None = None
    monotonicity_evidence: str | None = None
    physical_ephemeris_source: PhysicalEphemerisSource | None = None
    longitude_frame: str | None = None
    datetime_utc: str | None = None


class HoraryMoon(PartialOutput):
    motion_basis: HoraryMotionBasis | None = None
    degrees_left_in_sign: float | None = None
    next_aspect: HoraryAspect | None = None
    sign: str | None = None
    sign_label: str | None = None
    speed: float | None = None
    void_of_course: bool | None = None


class LillyDirectedSignRelationship(PartialOutput):
    method_id: str | None = None
    caster: str | None = None
    receiver: str | None = None
    caster_sign: str | None = None
    receiver_sign: str | None = None
    forward_sign_steps: int | None = None
    distinct_bodies: bool | None = None
    relation_status: (
        Literal["ray", "co_present", "listed_inconjunct", "not_in_either_table"] | None
    ) = None
    sign_ray: Literal["sextile", "square", "trine", "opposition"] | None = None
    ray_direction: Literal["dexter", "sinister"] | None = None
    listed_inconjunct: bool | None = None
    selected_degree_aspect: str | None = None
    selected_degree_aspect_agrees: bool | None = None
    coordinate_scope: str | None = None
    source_pages: list[int] | None = None
    source_url: str | None = None
    boundary_policy: str | None = None
    direction_policy: str | None = None
    quantitative_bonus_added: Literal[False] | None = None
    full_original_text_acceptance: Literal[False] | None = None


class HorarySignificators(PartialOutput):
    querent: HoraryPlanet | None = None
    quesited: HoraryPlanet | None = None
    moon_co_significator: HoraryPlanet | None = None
    directed_sign_relationship: LillyDirectedSignRelationship | None = None


class LillyRoute(PartialOutput):
    mode: str | None = None
    actors: list[str] | None = None
    condition_epoch: str | None = None
    status: str | None = None
    conditions: list[LillyCondition] | None = None
    receptions: list[LillyReception] | None = None
    full_path_accepted: bool | None = None
    source_planet: str | None = None
    target_planet: str | None = None
    carrier: str | None = None
    collector: str | None = None
    aspect: HoraryAspect | None = None
    next_lunar_contact: HoraryAspect | None = None


class LillyConditionalReading(PartialOutput):
    premise_satisfied: bool | None = None
    source_pages: list[int] | None = None
    conditional_reading_zh: str | None = None
    full_judgement_accepted: bool | None = None


class PlanetaryEventState(PartialOutput):
    longitude: float | None = None
    latitude: float | None = None
    speed: float | None = None
    speed_native: float | None = None
    speed_light_time_correction: float | None = None
    speed_spatial_aberration_correction: float | None = None
    speed_lunar_source_remainder_correction: float | None = None
    speed_sidereal_origin_wrap_correction: float | None = None
    speed_rotation_correction: float | None = None
    speed_analytic_frame_correction: float | None = None
    speed_position_derivative_correction: float | None = None
    speed_display_offset_correction: float | None = None


class PlanetaryEventFailedSample(PartialOutput):
    planet: str | None = None
    julian_day_tt: float | None = None


class PlanetaryEvent(PartialOutput):
    kind: str | None = None
    bodies: list[str] | None = None
    julian_day_tt: float | None = None
    root_bracket_tt: list[float] | None = None
    epoch_relation: str | None = None
    states: dict[str, PlanetaryEventState] | None = None
    state_brackets: dict[str, list[PlanetaryEventState]] | None = None
    ray_degrees: int | None = None
    direction: int | None = None
    topology: str | None = None
    aspect: str | None = None
    datetime_utc: str | None = None


class PlanetaryUnresolvedInterval(PartialOutput):
    kind: str | None = None
    bodies: list[str] | None = None
    interval_tt: list[float] | None = None


class PlanetaryEventHistory(PartialOutput):
    apparent_position_policy: ApparentPositionPolicy | None = None
    ephemeris_reference_points: EphemerisReferencePoints | None = None
    longitude_motion: LongitudeMotionPolicy | None = None
    status: str | None = None
    method_id: str | None = None
    constant_velocity_projection: bool | None = None
    time_scale: str | None = None
    question_julian_day_tt: float | None = None
    window_tt: list[float] | None = None
    scan_step_days: float | None = None
    bodies: list[str] | None = None
    question_states: dict[str, PlanetaryEventState] | None = None
    events: list[PlanetaryEvent] | None = None
    unresolved_intervals: list[PlanetaryUnresolvedInterval] | None = None
    completeness_scope: str | None = None
    full_original_text_acceptance: bool | None = None
    physical_ephemeris_source: PhysicalEphemerisSource | None = None
    longitude_frame: str | None = None
    unavailable_reason: str | None = None
    unavailable_code: str | None = None
    failed_sample: PlanetaryEventFailedSample | None = None


class EventReception(PartialOutput):
    julian_day_tt: float | None = None
    root_bracket_tt: list[float] | None = None
    chart_sect: str | None = None
    reception: LillyReception | None = None
    endpoint_receptions: list[LillyReception] | None = None
    boundary_uncertainty: bool | None = None


class LillyEventPath(PartialOutput):
    mode: str | None = None
    actors: list[str] | None = None
    conditions: list[LillyCondition] | None = None
    sequence_conditions_satisfied: bool | None = None
    status: str | None = None
    event_receptions: list[EventReception] | None = None
    full_path_accepted: bool | None = None
    prior_principal_contact: PlanetaryEvent | None = None
    prior_carrier_contact: PlanetaryEvent | None = None
    future_contact: PlanetaryEvent | None = None
    transitions: list[PlanetaryEvent] | None = None
    intervening_contacts: list[PlanetaryEvent] | None = None
    collection_contacts: list[PlanetaryEvent] | None = None


class RefranationPattern(PartialOutput):
    applicant: str | None = None
    recipient: str | None = None
    station: PlanetaryEvent | None = None
    source_pages: list[int] | None = None
    scope: str | None = None


class ProhibitionPattern(PartialOutput):
    interposer: str | None = None
    applicant: str | None = None
    recipient: str | None = None
    first_contact: PlanetaryEvent | None = None
    second_contact: PlanetaryEvent | None = None
    source_pages: list[int] | None = None
    scope: str | None = None


class LillyEventPaths(PartialOutput):
    status: str | None = None
    paths: list[LillyEventPath] | None = None
    refranation_patterns: list[RefranationPattern] | None = None
    prohibition_patterns: list[ProhibitionPattern] | None = None
    reception_epoch_policy: str | None = None
    source_pages: list[int] | None = None
    scope: str | None = None
    full_original_text_acceptance: bool | None = None
    unavailable_reason: str | None = None


class SystemOutput(PartialOutput):
    system: str | None = None
    system_label: str | None = None


class ProfectionCalculationOptions(PartialOutput):
    annual_basis: str | None = None
    monthly_basis: str | None = None
    anniversary_clock_policy: str | None = None
    timezone: str | None = None


class Profection(PartialOutput):
    age_years: int | None = None
    year_start: str | None = None
    year_end: str | None = None
    calculation_options: ProfectionCalculationOptions | None = None
    activated_house: int | None = None
    activated_sign: str | None = None
    activated_sign_label: str | None = None
    lord: str | None = None
    lord_label: str | None = None
    monthly_house: int | None = None
    monthly_sign: str | None = None
    monthly_sign_label: str | None = None


class MonthlyProfection(PartialOutput):
    month_index: int | None = None
    start: str | None = None
    end: str | None = None
    active: bool | None = None
    house: int | None = None
    house_label: str | None = None
    sign: str | None = None
    sign_label: str | None = None
    lord: str | None = None
    lord_label: str | None = None


class HouseEmphasis(PartialOutput):
    house: int | None = None
    house_label: str | None = None
    count: int | None = None


class ProgressionClockOptions(PartialOutput):
    method: str | None = None
    year_basis: str | None = None
    year_key_numerator: int | None = None
    year_key_denominator: int | None = Field(default=None, gt=0)
    time_basis: str | None = None
    timestamp_rounding: str | None = None


class ProgressionCalculationOptions(ProgressionClockOptions):
    house_method: str | None = None


class SolarArcCalculationOptions(PartialOutput):
    arc_method: str | None = None
    angle_method: str | None = None
    progression: ProgressionCalculationOptions | None = None


class TransitTimelineStep(PartialOutput):
    day_offset: int | None = None
    date: str | None = None
    analysis_datetime: str | None = None
    exact_hits: list[AspectHit] | None = None
    exact_hits_total_count: int | None = None
    tight_hits: list[AspectHit] | None = None
    tight_hits_total_count: int | None = None


class TimingChart(PartialOutput):
    calculation_basis: WesternCalculationBasis | None = None
    calculation_options: (
        ProgressionCalculationOptions | SolarArcCalculationOptions | None
    ) = None
    solver: ReturnSolver | None = None
    return_datetime_utc: str | None = None
    analysis_datetime: str | None = None
    return_datetime: str | None = None
    progressed_datetime: str | None = None
    arc_degrees: float | None = None
    ascendant: WesternPoint | None = None
    medium_coeli: WesternPoint | None = None
    sun: WesternPoint | None = None
    moon: WesternPoint | None = None
    hits: list[AspectHit] | None = None
    hits_total_count: int | None = None
    exact_hits: list[AspectHit] | None = None
    exact_hits_total_count: int | None = None
    location: Location | None = None
    natal_reference: dict[str, WesternPoint] | None = None
    transit_reference: dict[str, WesternPoint] | None = None
    house_emphasis: list[HouseEmphasis] | None = None
    orb_limit: float | None = None
    exact_orb_limit: float | None = None
    scan_days: int | None = None
    tight_orb_limit: float | None = None
    transit_timeline: list[TransitTimelineStep] | None = None
    annual_profection: Profection | None = None
    monthly_profections: list[MonthlyProfection] | None = None
    year_start: str | None = None
    year_end: str | None = None


class FirdariaPeriod(PartialOutput):
    planet: str | None = None
    planet_label: str | None = None
    start: str | None = None
    end: str | None = None
    start_display: str | None = None
    end_display: str | None = None


class FirdariaMajor(FirdariaPeriod):
    years: float | None = None
    subperiods: list[FirdariaPeriod] | None = None
    nominal_start_age: int | None = None
    nominal_end_age: int | None = None


class FirdariaCalculationOptions(PartialOutput):
    night_order: str | None = None
    year_basis: str | None = None
    subperiod_basis: str | None = None
    timezone: str | None = None


class Firdaria(PartialOutput):
    sect: str | None = None
    sect_label: str | None = None
    current_major: FirdariaMajor | None = None
    current_sub: FirdariaPeriod | None = None
    timeline: list[FirdariaMajor] | None = None
    calculation_options: FirdariaCalculationOptions | None = None


class DecennialExactOffset(PartialOutput):
    numerator: int | None = None
    denominator: int | None = Field(default=None, gt=0)


class DecennialCalculationOptions(PartialOutput):
    start_mode: str | None = None
    order_type: str | None = None
    day_method: str | None = None
    calendar_type: str | None = None
    time_basis: str | None = None
    timestamp_rounding: str | None = None
    offset_minutes_rounding: str | None = None
    timezone: str | None = None


class DecennialPeriod(PartialOutput):
    key: str | None = None
    level: int | None = None
    planet: str | None = None
    planet_label: str | None = None
    date: str | None = None
    nominal: str | None = None
    start: str | None = None
    end: str | None = None
    active: bool | None = None
    start_offset_minutes: int | None = None
    end_offset_minutes: int | None = None
    start_offset_exact_minutes: DecennialExactOffset | None = None
    end_offset_exact_minutes: DecennialExactOffset | None = None
    sublevel: list[DecennialPeriod] | None = None


class Decennials(PartialOutput):
    base_order: list[str] | None = None
    resolved_start_planet: str | None = None
    resolved_start_planet_label: str | None = None
    current_level_1: DecennialPeriod | None = None
    current_level_2: DecennialPeriod | None = None
    current_level_3: DecennialPeriod | None = None
    timeline: list[DecennialPeriod] | None = None
    calculation_options: DecennialCalculationOptions | None = None


class ReleasingPeriod(PartialOutput):
    sign: str | None = None
    sign_label: str | None = None
    ruler: str | None = None
    ruler_label: str | None = None
    level: int | None = None
    duration_value: float | None = Field(
        default=None,
        description="Nominal full-sign duration before parent truncation, in duration_unit: 360-day years at L1, 30-day months at L2, calendar days at L3. Actual interval is start/end.",
    )
    duration_unit: str | None = None
    duration_unit_label: str | None = None
    start: str | None = None
    end: str | None = None
    loosing_of_bond: bool | None = None
    parent_sign: str | None = None
    parent_sign_label: str | None = None
    active: bool | None = None
    phase: str | None = None
    phase_label: str | None = None
    relative_sign_index: int | None = None
    is_peak_period: bool | None = None


class SignLabel(PartialOutput):
    sign: str | None = None
    sign_label: str | None = None


class ReleasingTrack(PartialOutput):
    base_point: str | None = None
    base_point_label: str | None = None
    release_start_sign: str | None = None
    release_start_sign_label: str | None = None
    start_sign_adjusted: bool | None = None
    angular_reference_sign: str | None = None
    lot: WesternPoint | None = None
    peak_signs: list[SignLabel] | None = None
    current_level_1: ReleasingPeriod | None = None
    current_level_2: ReleasingPeriod | None = None
    current_level_3: ReleasingPeriod | None = None
    current_level_4: ReleasingPeriod | None = None
    level_1_timeline: list[ReleasingPeriod] | None = None
    level_2_timeline: list[ReleasingPeriod] | None = None
    level_3_timeline: list[ReleasingPeriod] | None = None
    level_4_timeline: list[ReleasingPeriod] | None = None


class ReleasingCalculationBasis(PartialOutput):
    method_id: str | None = None
    source_authors: list[str] | None = None
    source_title: str | None = None
    source_date: str | None = None
    source_url: str | None = None
    year_basis: str | None = None
    year_days: float | None = None
    interval_time_basis: str | None = None
    angular_reference_point: str | None = None
    angular_reference_sign: str | None = None
    spirit_same_sign_rule: str | None = None
    published_levels: list[int] | None = None
    whole_procedure_certified: bool | None = None


class ZodiacalReleasing(PartialOutput):
    calculation_basis: ReleasingCalculationBasis | None = None
    fortune: ReleasingTrack | None = None
    spirit: ReleasingTrack | None = None


class Returns(PartialOutput):
    solar_return: TimingChart | None = None
    lunar_return: TimingChart | None = None


class Directions(PartialOutput):
    given_year: TimingChart | None = None
    primary_directions: PrimaryDirections | None = None
    primary_direction_chart: PrimaryDirections | None = None
    secondary_progression: TimingChart | None = None
    solar_arc: TimingChart | None = None


class TimeLords(PartialOutput):
    annual_profection: Profection | None = None
    monthly_profections: list[MonthlyProfection] | None = None
    firdaria: Firdaria | None = None
    decennials: Decennials | None = None
    zodiacal_releasing: ZodiacalReleasing | None = None


class Transits(PartialOutput):
    current_transit: TimingChart | None = None


class LillyDwellingClause(PartialOutput):
    rule_id: str | None = None
    source_url: str | None = None
    source_pages: list[int] | None = None
    quesited_occupied_house: int | None = None
    quesited_in_first_house: bool | None = None
    dwelling_alone_sufficient: bool | None = None
    distinct_lunar_transfer_actors: bool | None = None
    moon_last_contact_is_quesited: bool | None = None
    moon_next_contact_is_querent: bool | None = None
    moon_separating_from_prior_source_ray_now: bool | None = None
    moon_applying_to_next_recipient_ray_now: bool | None = None
    lunar_sequence_subconditions_satisfied: bool | None = None
    named_necessary_conditions_satisfied: bool | None = None
    prior_lunar_contact: PlanetaryEvent | None = None
    next_lunar_contact: PlanetaryEvent | None = None
    matching_p126_event_path_indexes: list[int] | None = None
    event_history_status: str | None = None
    event_history_unavailable_reason: str | None = None
    event_history_window_tt: list[float] | None = None
    event_history_completeness_scope: str | None = None
    scope: str | None = None
    conditional_reading_zh: str | None = None
    full_judgement_accepted: bool | None = None
    full_original_text_acceptance: bool | None = None


class LillyConditions(PartialOutput):
    rule_id: str | None = None
    chart_sect: str | None = None
    coordinate_scope: str | None = None
    principal_reception: LillyPairReception | None = None
    p112_mutual_reception: LillyConditionalReading | None = None
    p126_127_dwelling: LillyDwellingClause | None = None
    routes: list[LillyRoute] | None = None
    event_paths: LillyEventPaths | None = None
    same_body_not_bilateral: bool | None = None
    full_original_text_acceptance: bool | None = None
    scope: str | None = None


class HoraryPerfection(PartialOutput):
    perfected: bool | None = None
    before_ingress: bool | None = None
    intervening_contacts_count: int | None = None
    sequence_conditions_unverified: bool | None = None
    perfection_routes: list[str] | None = None
    obstructions: list[str] | None = None
    principal_reception: LillyPairReception | None = None
    event_path_summary: list[dict[str, OpenJsonValue]] | None = None
    lilly_conditions: LillyConditions | None = None
    event_history: PlanetaryEventHistory | None = None
    status: str | None = None
    missing_conditions: list[str] | None = None


class HoraryStricture(PartialOutput):
    code: str | None = None
    detail: str | None = None
    source_pages: list[int] | None = None
    status: str | None = None
    exception_satisfied: bool | None = None
    exception_applicable: bool | None = None
    attributed_variant: bool | None = None


class LillyRadicalityReportedContext(PartialOutput):
    figure_origin: str | None = None
    very_young_querent_reported: bool | None = None
    rising_description_agreement_reported: bool | None = None
    age_degree_agreement_reported: bool | None = None
    event_time_certain_reported: bool | None = None
    principal_significators_very_strong_reported: bool | None = None
    seventh_cusp_afflicted_reported: bool | None = None
    seventh_lord_impeded_reported: bool | None = None
    seventh_lord_unfortunate_reported: bool | None = None
    equal_fortune_infortune_testimonies_reported: bool | None = None
    figure_origin_source: str | None = None
    provided_fields: list[str] | None = None
    verification_scope: str | None = None


class LillyHourAffinity(PartialOutput):
    hour_ruler: str | None = None
    ascendant_sign: str | None = None
    ascendant_lord: str | None = None
    chart_sect: str | None = None
    same_ruler: bool | None = None
    ascendant_triplicity: bool | None = None
    same_own_nature: bool | None = None
    selected_triplicity_lord: str | None = None
    listed_triplicity_lords: list[str] | None = None
    hour_ruler_in_any_listed_triplicity: bool | None = None
    hour_ruler_own_nature: list[str] | None = None
    ascendant_lord_own_nature: list[str] | None = None
    supported_under_declared_policy: bool | None = None
    triplicity_policy: str | None = None
    nature_policy: str | None = None
    source_pages: list[int] | None = None
    full_original_text_acceptance: bool | None = None


class LillyRadicalityHourInputs(PartialOutput):
    status: str | None = None
    unavailable_reason: str | None = None
    hour: PlanetaryHours | None = None
    horizon_policy: str | None = None
    actual_solar_backend_verified: bool | None = None
    source_method_acceptance: bool | None = None
    epoch_jd_ut1: float | None = None
    geometric_chart_sect: str | None = None
    hour_and_geometric_sect_differ: bool | None = None
    sect_comparison_policy: str | None = None


class LillyConsideration(PartialOutput):
    code: str | None = None
    condition: str | None = None
    source_pages: list[int] | None = None
    condition_present: bool | None = None
    applicable: bool | None = None
    exception_satisfied: bool | None = None
    exception_applicable: bool | None = None
    attributed_variant: bool | None = None
    status: str | None = None
    inputs: dict[str, OpenJsonValue] | None = None
    conditional_reading_zh: str | None = None


class HoraryDegreeGate(PartialOutput):
    early: bool | None = None
    late: bool | None = None
    early_exception_satisfied: bool | None = None
    late_exception_satisfied: bool | None = None
    certain_timed_event_exception: bool | None = None


class HoraryRadicality(PartialOutput):
    method_id: str | None = None
    source_url: str | None = None
    source_pages: list[int] | None = None
    clause_count: int | None = None
    clauses: list[LillyConsideration] | None = None
    hour_inputs: LillyRadicalityHourInputs | None = None
    hour_affinity: LillyHourAffinity | None = None
    reported_context: LillyRadicalityReportedContext | None = None
    ascendant_degree_gate: HoraryDegreeGate | None = None
    unknown_clauses: list[str] | None = None
    status: str | None = None
    house_policy: str | None = None
    house_system: str | None = None
    zodiac_type: str | None = None
    source_method_scope: str | None = None
    conditional_reading_zh: str | None = None
    full_original_text_acceptance: bool | None = None
    full_judgement_accepted: bool | None = None
    safe_to_judge_scope: str | None = None
    safe_to_judge: bool | None = None
    strictures: list[HoraryStricture] | None = None


class LillyOrbTable(PartialOutput):
    profile_id: str | None = None
    source_url: str | None = None
    source_pages: list[int] | None = None
    full_orbs_degrees: dict[str, float] | None = None
    moieties_degrees: dict[str, float] | None = None
    available_profiles: list[str] | None = None
    pair_rule: str | None = None
    boundary_convention: str | None = None
    default_selection_basis: str | None = None
    full_original_text_acceptance: bool | None = None


class LillyFortitudeSample(PartialOutput):
    offset_days: float | None = None
    longitude: float | None = None


class LillyFortitudeMotion(PartialOutput):
    nominal_coordinate_check: str | None = None
    nominal_coordinate_roundoff_allowance_degrees: float | None = None
    direction: str | None = None
    daily_motion_degrees: float | None = None
    daily_motion_exact_degrees: str | None = None
    status: str | None = None
    samples: list[LillyFortitudeSample] | None = None
    instantaneous_speed_degrees_per_day: float | None = None
    source_model: str | None = None


class LillyFortitudeInputs(PartialOutput):
    status: str | None = None
    reason: str | None = None
    epoch_jd_tt: float | None = None
    motion: dict[str, LillyFortitudeMotion] | None = None
    north_node_longitude: float | None = None
    node_model: str | None = None
    star_longitudes: dict[str, float] | None = None
    star_position_policy: str | None = None
    daily_motion_policy: str | None = None
    day_interval_tt: list[float] | None = None
    longitude_frame: str | None = None
    physical_ephemeris_source: PhysicalEphemerisSource | None = None
    stars_profile: FixedStarProfile | None = None


class LillyFortitudeRow(PartialOutput):
    code: str | None = None
    group: str | None = None
    condition: str | None = None
    label_zh: str | None = None
    points: int | None = None
    applicable: bool | None = None
    satisfied: bool | None = None
    contribution: int | None = None
    status: str | None = None
    inputs: dict[str, OpenJsonValue] | None = None
    source_pages: list[int] | None = None


class LillyFortitudeAppliedCondition(PartialOutput):
    code: str | None = None
    label_zh: str | None = None
    contribution: int | None = None
    source_pages: list[int] | None = None


class LillyFortitudeSummary(PartialOutput):
    status: str | None = None
    known_fortitudes: int | None = None
    known_debilities: int | None = None
    known_balance: int | None = None
    literal_table_balance: int | None = None
    unknown_rows: list[str] | None = None
    applied_conditions: list[LillyFortitudeAppliedCondition] | None = None
    row_count: int | None = None
    conditional_reading_zh: str | None = None


class LillyFortitudePlanet(LillyFortitudeSummary):
    rows: list[LillyFortitudeRow] | None = None
    inactive_row_codes: list[str] | None = None


class LillyFortitudes(PartialOutput):
    method_id: str | None = None
    source_url: str | None = None
    source_edition: str | None = None
    source_pages: list[int] | None = None
    row_count_per_planet: int | None = None
    include_inactive_rows: bool | None = None
    row_catalog: dict[str, dict[str, OpenJsonValue]] | None = None
    planets: dict[str, LillyFortitudePlanet] | None = None
    summary: dict[str, LillyFortitudeSummary] | None = None
    physical_inputs: LillyFortitudeInputs | None = None
    solar_policy: dict[str, OpenJsonValue] | None = None
    zodiac_type: str | None = None
    house_system: str | None = None
    source_method_scope: str | None = None
    aggregation_policy: str | None = None
    source_conflicts: list[str] | None = None
    full_original_text_acceptance: bool | None = None
    full_judgement_accepted: bool | None = None


class LillyFortuneFormula(PartialOutput):
    expression: str | None = None
    reverses_at_night: bool | None = None
    ascendant: float | None = None
    sun: float | None = None
    moon: float | None = None
    uses_physical_ascendant_not_first_cusp: bool | None = None
    source_pages: list[int] | None = None
    scope: str | None = None


class LillyFortune(LillyFortitudeSummary):
    method_id: str | None = None
    source_url: str | None = None
    source_pages: list[int] | None = None
    longitude: float | None = None
    exact_longitude: str | None = None
    sign: str | None = None
    degree_in_sign: float | None = None
    formula: LillyFortuneFormula | None = None
    house_assignment: LillyHouseAssignment | None = None
    bound_lord: str | None = None
    solar_state: str | None = None
    rows: list[LillyFortitudeRow] | None = None
    source_method_scope: str | None = None
    interpretation_policies: list[str] | None = None
    full_original_text_acceptance: bool | None = None
    full_judgement_accepted: bool | None = None


class HoraryRuleProfile(PartialOutput):
    sign_relationship_policy: str | None = None
    radicality_policy: str | None = None
    cusp_virtue_policy: str | None = None
    fortune_policy: str | None = None
    fortitudes_policy: str | None = None
    orb_table: LillyOrbTable | None = None
    house_axis_policy: str | None = None
    essential_dignity_policy: str | None = None
    rule_id: str | None = None
    source_edition: str | None = None
    source_url: str | None = None
    chapter_pages: list[int] | None = None
    full_original_text_acceptance: bool | None = None
    instantaneous_phase: str | None = None
    orb_policy: str | None = None
    moon_policy: str | None = None
    judgement_status: str | None = None


class Horary(SystemOutput):
    reference_geometry: dict[str, OpenJsonValue] | None = None
    backend_convention: dict[str, OpenJsonValue] | None = None
    fortune: LillyFortune | None = None
    fortitudes: LillyFortitudes | None = None
    calculation_basis: WesternCalculationBasis | None = None
    rule_profile: HoraryRuleProfile | None = None
    category: str | None = None
    category_label: str | None = None
    ascendant: WesternPoint | None = None
    moon: HoraryMoon | None = None
    significators: HorarySignificators | None = None
    planets: dict[str, HoraryPlanet] | None = None
    perfection: HoraryPerfection | None = None
    quesited_house: int | None = None
    radicality: HoraryRadicality | None = None


class CivilDateParts(PartialOutput):
    year: int | None = None
    month: int | None = None
    day: int | None = None


class CivilClockParts(PartialOutput):
    hour: int | None = None
    minute: int | None = None
    second: int | None = None


class WesternCivilCalendarConversion(PartialOutput):
    method_id: str | None = None
    input_calendar: str | None = None
    input_date: CivilDateParts | None = None
    input_clock: CivilClockParts | None = None
    normalized_calendar: str | None = None
    normalized_local_datetime: str | None = None
    normalized_date_representable: bool | None = None
    normalized_local_datetime_scope: str | None = None
    date_label_jdn: int | None = None
    date_label_jdn_scope: str | None = None
    same_label_gregorian_date_valid: bool | None = None
    same_label_gregorian_offset_days: int | None = None
    calendar_conversion_performed: bool | None = None
    clock_preserved: bool | None = None
    automatic_regional_reform_applied: bool | None = None
    year_numbering: str | None = None
    calendar_selection_source: str | None = None
    timezone_order: str | None = None
    historical_clock_reconstruction_performed: bool | None = None
    scope: str | None = None


class WesternHourOriginConversion(PartialOutput):
    method_id: str | None = None
    input_hour_origin: str | None = None
    input_calendar: str | None = None
    input_date: CivilDateParts | None = None
    input_clock: CivilClockParts | None = None
    source_date_label_jdn: int | None = None
    source_date_gregorian_representable: bool | None = None
    calendar_normalized_label: str | None = None
    normalized_wall_calendar: str | None = None
    normalized_wall_datetime: str | None = None
    normalized_date_label_jdn: int | None = None
    day_carry: int | None = None
    nominal_label_shift_minutes: int | None = None
    normalization_performed: bool | None = None
    physical_duration_applied: bool | None = None
    timezone_applied: bool | None = None
    source_clock_identification_performed: bool | None = None
    selection_source: str | None = None
    rule_source: str | None = None
    rule_source_url: str | None = None
    source_pages: list[int] | None = None
    scope: str | None = None


class EventSolarObservation(PartialOutput):
    phase: str | None = None
    julian_day_ut1: float | None = None
    julian_day_tt: float | None = None
    source_index: int | None = None


class EventSolarSources(PartialOutput):
    status: str | None = None
    physical_ephemeris_sources: list[PhysicalEphemerisSource] | None = None
    has_unidentified_sources: bool | None = None
    observations: list[EventSolarObservation] | None = None
    scope: str | None = None


class EventSolarConversion(BirthClockConversion):
    solar_source_comparison: EventSolarSources | None = None


class EventClockChartComparison(PartialOutput):
    status: str | None = None
    chart_sun_source: PhysicalEphemerisSource | None = None
    has_unidentified_sources: bool | None = None
    scope: str | None = None


class WesternEventClockConversion(PartialOutput):
    ut1_reference: C04UT1Evidence | None = None
    method_id: str | None = None
    input_hour_origin: str | None = None
    hour_origin_conversion: WesternHourOriginConversion | None = None
    input_clock_basis: str | None = None
    input_wall_datetime: str | None = None
    input_granularity: str | None = None
    input_timezone: str | None = None
    effective_civil_timezone: str | None = None
    timezone_selection_source: str | None = None
    chart_timezone: str | None = None
    converted_utc: str | None = None
    utc_representation: WesternUTCRepresentation | None = None
    julian_day_tt: float | None = None
    julian_day_ut1: float | None = None
    time_scale_method: str | None = None
    modeled_solar_conversion_performed: bool | None = None
    source_clock_identification_performed: bool | None = None
    input_clock_accuracy_certified: bool | None = None
    solar_conversion: EventSolarConversion | None = None
    clock_chart_source_comparison: EventClockChartComparison | None = None
    scope: str | None = None


class HarmonicConjunction(PartialOutput):
    points: list[str] | None = None
    points_label: list[str] | None = None
    separation_degree: float | None = None
    orb: float | None = None


class HarmonicChart(PartialOutput):
    harmonic: int | None = None
    orb: float | None = None
    method: str | None = None
    method_label: str | None = None
    positions: dict[str, WesternPoint] | None = None
    resonant_conjunctions: list[HarmonicConjunction] | None = None


class AgeBand(PartialOutput):
    planet: str | None = None
    planet_label: str | None = None
    start_age: float | None = None
    end_age: float | None = None
    duration_years: float | None = None
    active: bool | None = None
    natal_condition: WesternPoint | None = None


class PlanetaryAges(SystemOutput):
    active_planet: str | None = None
    active_planet_label: str | None = None
    current_age_years: float | None = None
    bands: list[AgeBand] | None = None


class PhaseIngress(PartialOutput):
    phase: str | None = None
    phase_label: str | None = None
    elongation_degree: float | None = None
    ingress_age_years: float | None = None
    progressed_julian_day_tt: float | None = None
    progressed_utc_point: CivilPointEvidence | None = None
    progressed_datetime_utc: str | None = None
    source_root_bracket_tt: list[float] | None = None
    residual_degrees: float | None = None


class LunationPhaseSolver(PartialOutput):
    method: str | None = None
    step_days: float | None = None
    max_bisection_iterations: int | None = None
    window_tt_jd: list[float] | None = None
    window_membership: str | None = None


class LunationPhase(SystemOutput):
    method_id: str | None = None
    progression_options: ProgressionClockOptions | None = None
    age_basis: str | None = None
    physical_ephemeris_source: PhysicalEphemerisSource | None = None
    solver: LunationPhaseSolver | None = None
    max_age_years: float | None = None
    natal_elongation_degree: float | None = None
    natal_phase: str | None = None
    natal_phase_label: str | None = None
    phase_ingresses: list[PhaseIngress] | None = None
    phase_ingress_count: int | None = None


class DistributionParticipant(PartialOutput):
    planet: str | None = None
    planet_label: str | None = None
    contact_age_years: float | None = None


class DistributionPeriod(PartialOutput):
    distributor: str | None = None
    distributor_label: str | None = None
    sign: str | None = None
    sign_label: str | None = None
    bound_start_degree: float | None = None
    bound_end_degree: float | None = None
    start_age_years: float | None = None
    end_age_years: float | None = None
    participants: list[DistributionParticipant] | None = None


class Distributions(SystemOutput):
    ascendant_absolute_degree: float | None = None
    direction_model: str | None = None
    direction_model_label: str | None = None
    max_age_years: float | None = None
    rate_deg_per_year: float | None = None
    time_key: str | None = None
    periods: list[DistributionPeriod] | None = None


class AgePeriod(PartialOutput):
    planet: str | None = None
    planet_label: str | None = None
    start_age_years: float | None = None
    duration_years: float | None = None
    small_year: float | None = None


class BalbillusPeriod(AgePeriod):
    subperiods: list[AgePeriod] | None = None


class Balbillus(SystemOutput):
    max_age_years: float | None = None
    mode: str | None = None
    mode_label: str | None = None
    start_planet: str | None = None
    start_planet_label: str | None = None
    zodiacal_order: list[str] | None = None
    periods: list[BalbillusPeriod] | None = None


class YearSystem129(SystemOutput):
    max_age_years: float | None = None
    sequence_model: str | None = None
    sequence_model_label: str | None = None
    start_planet: str | None = None
    start_planet_label: str | None = None
    zodiacal_order: list[str] | None = None
    total_cycle_years: int | None = None
    periods: list[AgePeriod] | None = None


class KeypointPosition(PartialOutput):
    planet: str | None = None
    planet_label: str | None = None
    position_number: int | None = None
    period_number: int | None = None


class KeypointActivation(PartialOutput):
    age: int | None = None
    house: int | None = None
    factors: list[list[int]] | None = None
    position_active: list[KeypointPosition] | None = None
    period_active: list[KeypointPosition] | None = None


class Keypoints(SystemOutput):
    release_mode: str | None = None
    release_mode_label: str | None = None
    release_sign_index: int | None = None
    positions: list[KeypointPosition] | None = None
    activations: list[KeypointActivation] | None = None
    activation_count: int | None = None


class PlanetaryArc(SystemOutput):
    progressed_datetime: str | None = None
    progression_options: ProgressionCalculationOptions | None = None
    arc_degrees: float | None = None
    arc_source: str | None = None
    arc_source_label: str | None = None
    orb: float | None = None
    positions: dict[str, WesternPoint] | None = None
    hits: list[AspectHit] | None = None
    hits_total_count: int | None = None


class PersianHit(PartialOutput):
    age: float | None = None
    aspect: int | None = None
    date: str | None = None
    promittor: str | None = None
    promittor_label: str | None = None
    significator: str | None = None


class PersianDirected(SystemOutput):
    hit_count: int | None = None
    hits_total_count: int | None = None
    max_age_years: float | None = None
    rate_deg_per_year: float | None = None
    hits: list[PersianHit] | None = None


class AgePointPosition(PartialOutput):
    age: float | None = None
    longitude: float | None = None
    sign: str | None = None
    sign_label: str | None = None
    signlon: float | None = None
    house: int | None = None
    aspect_to: str | None = None
    aspect_to_label: str | None = None


class AgePointContact(PartialOutput):
    age: float | None = None
    body: str | None = None
    body_label: str | None = None
    longitude: float | None = None


class AgePoint(SystemOutput):
    cycle_years: float | None = None
    max_age_years: float | None = None
    years_per_house: float | None = None
    points: list[AgePointPosition] | None = None
    point_count: int | None = None
    contacts: list[AgePointContact] | None = None


class VedicProgression(SystemOutput):
    progressed_datetime: str | None = None
    calculation_options: ProgressionCalculationOptions | None = None
    orb: float | None = None
    zodiac: str | None = None
    positions: dict[str, WesternPoint] | None = None
    hits: list[AspectHit] | None = None
    hits_total_count: int | None = None


class DeclinationParallel(PartialOutput):
    kind: str | None = None
    kind_label: str | None = None
    natal: str | None = None
    natal_label: str | None = None
    natal_declination: float | None = None
    progressed: str | None = None
    progressed_label: str | None = None
    progressed_declination: float | None = None
    orb: float | None = None


class JaynesDeclination(SystemOutput):
    progressed_datetime: str | None = None
    calculation_options: ProgressionClockOptions | None = None
    orb: float | None = None
    parallels: list[DeclinationParallel] | None = None


class ReturnMoment(PartialOutput):
    datetime_utc: str | None = None
    datetime_local: str | None = None
    julian_day_tt: float | None = None
    utc_representation: WesternUTCRepresentation | None = None


class PlanetReturn(PartialOutput):
    body: str | None = None
    body_label: str | None = None
    natal_longitude: WesternPoint | None = None
    most_recent_return: ReturnMoment | None = None
    next_return: ReturnMoment | None = None


class ExtraReturns(SystemOutput):
    reference_datetime: str | None = None
    returns: list[PlanetReturn] | None = None


class Mundane(SystemOutput):
    calculation_basis: WesternCalculationBasis | None = None
    ingress_term: str | None = None
    ingress_datetime_local: str | None = None
    ingress_datetime_utc: str | None = None
    ascendant: WesternPoint | None = None
    medium_coeli: WesternPoint | None = None
    points: dict[str, WesternPoint] | None = None


class ElectionFactor(PartialOutput):
    code: str | None = None
    body: str | None = None
    resolved_hit_axes: list[str] | None = None


class ElectionPlanet(PartialOutput):
    planet: str | None = None
    sign: str | None = None
    longitude: float | None = None
    speed: float | None = None
    retrograde: bool | None = None
    house: str | None = None
    dignity: str | None = None
    dignity_scope: str | None = None


class ElectionAxes(PartialOutput):
    ascendant_longitude: float | None = None
    midheaven_longitude: float | None = None
    first_house_cusp: float | None = None
    tenth_house_cusp: float | None = None
    policy: str | None = None


class ElectionMoon(PartialOutput):
    sign: str | None = None
    sign_label: str | None = None
    longitude: float | None = None
    void_of_course: bool | None = None
    phase: str | None = None
    elongation_degrees: float | None = None
    solar_condition: str | None = None
    motion_basis: HoraryMotionBasis | None = None


class ElectionAscendant(PartialOutput):
    sign: str | None = None
    sign_label: str | None = None
    longitude: float | None = None
    ruler: str | None = None
    ruler_label: str | None = None
    ruler_dignity: str | None = None


class ElectionUnresolvedFactor(PartialOutput):
    code: str | None = None
    reason: str | None = None


class ElectionHouseSignificator(PartialOutput):
    house: int | None = None
    reference_point: str | None = None
    role_in_source: str | None = None
    longitude: float | None = None
    sign: str | None = None
    ruler: str | None = None
    ruler_state: ElectionPlanet | None = None


class ElectionMarriageParty(PartialOutput):
    role_in_source: str | None = None
    natural_significator: str | None = None
    lunar_contact_role: str | None = None
    lunar_significator: str | None = None
    contact_order_established: bool | None = None
    contact: PlanetaryEvent | None = None


class ElectionMarriageSignificators(PartialOutput):
    method_id: str | None = None
    status: str | None = None
    author: str | None = None
    edition: str | None = None
    source_url: str | None = None
    source_pages: list[int] | None = None
    facsimile_url: str | None = None
    facsimile_pdf_pages: list[int] | None = None
    source_basis: str | None = None
    house_system: str | None = None
    zodiac_type: str | None = None
    houses: list[ElectionHouseSignificator] | None = None
    parties: list[ElectionMarriageParty] | None = None
    event_history: PlanetaryEventHistory | None = None
    scope: str | None = None
    full_original_text_acceptance: bool | None = None


class ElectionCandidateWindow(PartialOutput):
    datetime: str | None = None
    offset_hours: int | None = None
    score: int | None = None
    moon_void_of_course: bool | None = None
    planetary_hour_match: bool | None = None
    factor_codes: list[str] | None = None


class Election(PartialOutput):
    reference_geometry: dict[str, OpenJsonValue] | None = None
    backend_convention: dict[str, OpenJsonValue] | None = None
    system: str | None = None
    system_label: str | None = None
    significator: str | None = None
    significator_label: str | None = None
    planets: dict[str, ElectionPlanet] | None = None
    axes: ElectionAxes | None = None
    calculation_basis: WesternCalculationBasis | None = None
    solar_condition_policy: SolarConditionPolicy | None = None
    moon: ElectionMoon | None = None
    ascendant: ElectionAscendant | None = None
    condition_policy: Object | None = None
    unresolved_factors: list[ElectionUnresolvedFactor] | None = None
    dignity_scope: str | None = None
    marriage_significators: ElectionMarriageSignificators | None = None
    topic_id: str | None = None
    topic_label: str | None = None
    topic_house: int | None = None
    factors: list[ElectionFactor] | None = None
    candidate_windows: list[ElectionCandidateWindow] | None = None
    candidate_windows_total_count: int | None = None


class TriplicityStage(PartialOutput):
    stage: int | None = None
    stage_label: str | None = None
    role: str | None = None
    role_label: str | None = None
    ruler: str | None = None
    ruler_label: str | None = None
    start_age: float | None = None
    end_age: float | None = None
    planetary_period_years: float | None = None
    natal_condition: WesternPoint | None = None


class TriplicityRulers(SystemOutput):
    division: str | None = None
    element: str | None = None
    element_label: str | None = None
    lifespan_years: float | None = None
    sect: str | None = None
    sect_label: str | None = None
    sect_light: str | None = None
    sect_light_label: str | None = None
    sect_light_sign: str | None = None
    sect_light_sign_label: str | None = None
    stages: list[TriplicityStage] | None = None


class WesternTimingOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    directions: Directions | None = None
    natal_reference: NatalReference | None = None
    returns: Returns | None = None
    summary: Object | list[JsonValue] | str | None = None
    time_lords: TimeLords | None = None
    transits: Transits | None = None


class SolarReturnOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    solar_return: TimingChart | None = None
    summary: Object | list[JsonValue] | str | None = None


class LunarReturnOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    lunar_return: TimingChart | None = None
    natal_reference: NatalReference | None = None
    summary: Object | list[JsonValue] | str | None = None


class TransitChartOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    summary: Object | list[JsonValue] | str | None = None
    transit_chart: TimingChart | None = None


class SolarArcOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    solar_arc: TimingChart | None = None
    summary: Object | list[JsonValue] | str | None = None


class ChartForYearOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    chart_for_year: TimingChart | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    summary: Object | list[JsonValue] | str | None = None


class ProfectionOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    profection: Profection | None = None
    summary: Object | list[JsonValue] | str | None = None


class PrimaryDirectionsOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    primary_directions: PrimaryDirections | None = None
    summary: Object | list[JsonValue] | str | None = None


class PrimaryDirectionsChartOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    primary_directions_chart: PrimaryDirections | None = None
    summary: Object | list[JsonValue] | str | None = None


class ZodiacalReleasingOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    summary: Object | list[JsonValue] | str | None = None
    zodiacal_releasing: ZodiacalReleasing | None = None


class FirdariaOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    firdaria: Firdaria | None = None
    natal_reference: NatalReference | None = None
    summary: Object | list[JsonValue] | str | None = None


class DecennialsOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    decennials: Decennials | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    summary: Object | list[JsonValue] | str | None = None


class HarmonicChartOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    harmonic_chart: HarmonicChart | None = None
    natal_reference: NatalReference | None = None
    summary: Object | list[JsonValue] | str | None = None


class PlanetaryAgesOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    planetary_ages: PlanetaryAges | None = None
    summary: Object | list[JsonValue] | str | None = None


class TriplicityRulerPeriodsOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    summary: Object | list[JsonValue] | str | None = None
    triplicity_ruler_periods: TriplicityRulers | None = None


class LunarPhaseProgressionsOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    lunar_phase_progressions: LunationPhase | None = None
    natal_reference: NatalReference | None = None
    summary: Object | list[JsonValue] | str | None = None


class BoundsDirectionsOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    bounds_directions: Distributions | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    summary: Object | list[JsonValue] | str | None = None


class BalbillusPeriodsOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    balbillus: Balbillus | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    summary: Object | list[JsonValue] | str | None = None


class NumericAspectPeriodsOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    numeric_aspect_periods: Keypoints | None = None
    summary: Object | list[JsonValue] | str | None = None


class PlanetaryPeriods129YearsOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    planetary_periods_129_years: YearSystem129 | None = None
    summary: Object | list[JsonValue] | str | None = None


class PlanetaryArcDirectionsOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    planetary_arc: PlanetaryArc | None = None
    summary: Object | list[JsonValue] | str | None = None


class PersianDirectionsOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    persian_directions: PersianDirected | None = None
    summary: Object | list[JsonValue] | str | None = None


class AgePointOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    age_point: AgePoint | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    summary: Object | list[JsonValue] | str | None = None


class SiderealProgressionsOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    sidereal_progressions: VedicProgression | None = None
    summary: Object | list[JsonValue] | str | None = None


class DeclinationProgressionsOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    declination_progressions: JaynesDeclination | None = None
    engine: str | None = None
    natal_reference: NatalReference | None = None
    summary: Object | list[JsonValue] | str | None = None


class MundaneIngressChartOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    mundane_ingress_chart: Mundane | None = None
    summary: Object | list[JsonValue] | str | None = None


class PlanetaryReturnsOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    engine: str | None = None
    planetary_returns: ExtraReturns | None = None
    summary: Object | list[JsonValue] | str | None = None


class HoraryChartOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    calendar_conversion: WesternCivilCalendarConversion | None = None
    clock_conversion: WesternEventClockConversion | None = None
    engine: str | None = None
    horary_chart: Horary | None = None
    summary: Object | list[JsonValue] | str | None = None


class EvaluateElectionTimeOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    calendar_conversion: WesternCivilCalendarConversion | None = None
    clock_conversion: WesternEventClockConversion | None = None
    election: Election | None = None
    engine: str | None = None
    summary: Object | list[JsonValue] | str | None = None
