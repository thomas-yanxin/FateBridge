"""Stable nested facts for western professional techniques.

These contracts follow the builders in core/predictive, astrology_lifespan and
astrology_horary. Dictionary keys (planet, lot and diagnostic identifiers) stay
open; their values have contracts. Labels and method names remain extensible.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import Field

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_charts import (
    ApparentPositionPolicy,
    BirthClockConversion,
    EarthRotationPolicy,
    EphemerisReferencePoints,
    FixedStarProfile,
    HouseAxisConvention,
    HousePositionProjection,
    LongitudeMotionPolicy,
    PlanetaryHours,
)
from fatebridge.core.output_clock_labels import (
    WesternUTCRepresentation as WesternUTCRepresentation,
)
from fatebridge.core.output_midpoints import PhysicalEphemerisSource
from fatebridge.core.output_ut1 import C04UT1Evidence


class CivilDateParts(PartialOutput):
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None


class CivilClockParts(PartialOutput):
    hour: Optional[int] = None
    minute: Optional[int] = None


class WesternCivilCalendarConversion(PartialOutput):
    method_id: Optional[str] = None
    input_calendar: Optional[str] = None
    input_date: Optional[CivilDateParts] = None
    input_clock: Optional[CivilClockParts] = None
    normalized_calendar: Optional[str] = None
    normalized_local_datetime: Optional[str] = None
    normalized_date_representable: Optional[bool] = None
    normalized_local_datetime_scope: Optional[str] = None
    date_label_jdn: Optional[int] = None
    date_label_jdn_scope: Optional[str] = None
    same_label_gregorian_date_valid: Optional[bool] = None
    same_label_gregorian_offset_days: Optional[int] = None
    calendar_conversion_performed: Optional[bool] = None
    clock_preserved: Optional[bool] = None
    automatic_regional_reform_applied: Optional[bool] = None
    year_numbering: Optional[str] = None
    calendar_selection_source: Optional[str] = None
    timezone_order: Optional[str] = None
    historical_clock_reconstruction_performed: Optional[bool] = None
    scope: Optional[str] = None


class WesternHourOriginConversion(PartialOutput):
    method_id: Optional[str] = None
    input_hour_origin: Optional[str] = None
    input_calendar: Optional[str] = None
    input_date: Optional[CivilDateParts] = None
    input_clock: Optional[CivilClockParts] = None
    source_date_label_jdn: Optional[int] = None
    source_date_gregorian_representable: Optional[bool] = None
    calendar_normalized_label: Optional[str] = None
    normalized_wall_calendar: Optional[str] = None
    normalized_wall_datetime: Optional[str] = None
    normalized_date_label_jdn: Optional[int] = None
    day_carry: Optional[int] = None
    nominal_label_shift_minutes: Optional[int] = None
    normalization_performed: Optional[bool] = None
    physical_duration_applied: Optional[bool] = None
    timezone_applied: Optional[bool] = None
    source_clock_identification_performed: Optional[bool] = None
    selection_source: Optional[str] = None
    rule_source: Optional[str] = None
    rule_source_url: Optional[str] = None
    source_pages: Optional[List[int]] = None
    scope: Optional[str] = None


class EventSolarObservation(PartialOutput):
    phase: Optional[str] = None
    julian_day_ut1: Optional[float] = None
    julian_day_tt: Optional[float] = None
    source_index: Optional[int] = None


class EventSolarSources(PartialOutput):
    status: Optional[str] = None
    physical_ephemeris_sources: Optional[List[PhysicalEphemerisSource]] = None
    has_unidentified_sources: Optional[bool] = None
    observations: Optional[List[EventSolarObservation]] = None
    scope: Optional[str] = None


class EventSolarConversion(BirthClockConversion):
    solar_source_comparison: Optional[EventSolarSources] = None


class EventClockChartComparison(PartialOutput):
    status: Optional[str] = None
    chart_sun_source: Optional[PhysicalEphemerisSource] = None
    has_unidentified_sources: Optional[bool] = None
    scope: Optional[str] = None


class WesternEventClockConversion(PartialOutput):
    ut1_reference: Optional[C04UT1Evidence] = None
    method_id: Optional[str] = None
    input_hour_origin: Optional[str] = None
    hour_origin_conversion: Optional[WesternHourOriginConversion] = None
    input_clock_basis: Optional[str] = None
    input_wall_datetime: Optional[str] = None
    input_granularity: Optional[str] = None
    input_timezone: Optional[str] = None
    effective_civil_timezone: Optional[str] = None
    timezone_selection_source: Optional[str] = None
    chart_timezone: Optional[str] = None
    converted_utc: Optional[str] = None
    utc_representation: Optional[WesternUTCRepresentation] = None
    julian_day_tt: Optional[float] = None
    julian_day_ut1: Optional[float] = None
    time_scale_method: Optional[str] = None
    modeled_solar_conversion_performed: Optional[bool] = None
    source_clock_identification_performed: Optional[bool] = None
    input_clock_accuracy_certified: Optional[bool] = None
    solar_conversion: Optional[EventSolarConversion] = None
    clock_chart_source_comparison: Optional[EventClockChartComparison] = None
    scope: Optional[str] = None


class WesternPoint(PartialOutput):
    point: Optional[str] = None
    point_label: Optional[str] = None
    absolute_degree: Optional[float] = Field(default=None, ge=0, lt=360)
    degree: Optional[float] = Field(default=None, ge=0, lt=30)
    longitude: Optional[float] = Field(default=None, ge=0, lt=360)
    sign: Optional[str] = None
    sign_label: Optional[str] = None
    house: Optional[int] = None
    house_label: Optional[str] = None
    retrograde: Optional[bool] = None
    natal_absolute_degree: Optional[float] = None
    lot: Optional[str] = None
    lot_label: Optional[str] = None
    angularity: Optional[str] = None
    angularity_label: Optional[str] = None
    planet: Optional[str] = None
    planet_label: Optional[str] = None


class Sect(PartialOutput):
    key: Optional[str] = None
    label: Optional[str] = None


class WesternCalculationBasis(PartialOutput):
    angle_definition: Optional[Dict[str, Any]] = None
    utc_representation: Optional[WesternUTCRepresentation] = None
    apparent_position_policy: Optional[ApparentPositionPolicy] = None
    ephemeris_reference_points: Optional[EphemerisReferencePoints] = None
    longitude_motion: Optional[LongitudeMotionPolicy] = None
    physical_ephemeris_source: Optional[PhysicalEphemerisSource] = None
    house_axis_convention: Optional[HouseAxisConvention] = None
    earth_rotation: Optional[EarthRotationPolicy] = None
    house_position_projection: Optional[HousePositionProjection] = None
    engine_backend: Optional[str] = None
    engine_precision: Optional[str] = None
    ephemeris_model: Optional[str] = None
    calendar: Optional[str] = None
    time_scale: Optional[str] = None
    julian_day_tt: Optional[float] = None
    julian_day_ut1: Optional[float] = None
    future_leap_seconds_assumed_unchanged: Optional[bool] = None
    horizon_method: Optional[str] = None
    ayanamsha_model: Optional[str] = None
    ayanamsha_degrees: Optional[float] = None


class ReturnSolver(PartialOutput):
    method_id: Optional[str] = None
    julian_day_tt: Optional[float] = None
    target_longitude: Optional[float] = None
    solved_longitude: Optional[float] = None
    residual_arcseconds: Optional[float] = None
    event_not_after_analysis: Optional[bool] = None


class NatalReference(PartialOutput):
    calculation_basis: Optional[WesternCalculationBasis] = None
    ascendant: Optional[WesternPoint] = None
    medium_coeli: Optional[WesternPoint] = None
    sun: Optional[WesternPoint] = None
    moon: Optional[WesternPoint] = None
    mercury: Optional[WesternPoint] = None
    venus: Optional[WesternPoint] = None
    mars: Optional[WesternPoint] = None
    jupiter: Optional[WesternPoint] = None
    saturn: Optional[WesternPoint] = None
    uranus: Optional[WesternPoint] = None
    neptune: Optional[WesternPoint] = None
    pluto: Optional[WesternPoint] = None
    sect: Optional[Sect] = None
    lots: Optional[Dict[str, WesternPoint]] = None


class Location(PartialOutput):
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    timezone: Optional[str] = None


class AspectHit(PartialOutput):
    source: Optional[str] = None
    source_label: Optional[str] = None
    target: Optional[str] = None
    target_label: Optional[str] = None
    aspect: Optional[str] = None
    aspect_label: Optional[str] = None
    orb: Optional[float] = None


class CoordinateEntry(PartialOutput):
    key: Optional[str] = None
    label: Optional[str] = None
    coordinate_degrees: Optional[float] = None
    coordinate_system: Optional[str] = None
    coordinate_label: Optional[str] = None
    arc_applied_degrees: Optional[float] = None


class CoordinateContext(PartialOutput):
    promissor_natal: Optional[CoordinateEntry] = None
    promissor_current: Optional[CoordinateEntry] = None
    significator_natal: Optional[CoordinateEntry] = None
    aspect_target: Optional[CoordinateEntry] = None
    current_orb_degrees: Optional[float] = None


class PrimaryDirectionHit(PartialOutput):
    promissor: Optional[str] = None
    promissor_label: Optional[str] = None
    significator: Optional[str] = None
    significator_label: Optional[str] = None
    aspect: Optional[str] = None
    aspect_label: Optional[str] = None
    aspect_degree: Optional[float] = None
    aspect_variant_degrees: Optional[float] = None
    arc_degrees: Optional[float] = None
    arc_applied_degrees: Optional[float] = None
    event_age_years: Optional[float] = None
    event_datetime: Optional[str] = None
    direction_mode: Optional[str] = None
    direction_mode_label: Optional[str] = None
    coordinate_system: Optional[str] = None
    coordinate_label: Optional[str] = None
    relative_years_from_current: Optional[float] = None
    relative_arc_from_current: Optional[float] = None
    distance_from_current_years: Optional[float] = None
    timing_phase: Optional[str] = None
    timing_phase_label: Optional[str] = None
    coordinate_context: Optional[CoordinateContext] = None


class BoundsEntry(WesternPoint):
    key: Optional[str] = None
    label: Optional[str] = None
    bound_lord: Optional[str] = None
    bound_lord_label: Optional[str] = None
    segment_start_degree: Optional[float] = None
    segment_end_degree: Optional[float] = None


class BoundsOverlay(PartialOutput):
    system: Optional[str] = None
    system_label: Optional[str] = None
    enabled: Optional[bool] = None
    points: Optional[Dict[str, BoundsEntry]] = None
    lots: Optional[Dict[str, BoundsEntry]] = None


class SignChange(PartialOutput):
    point: Optional[str] = None
    point_label: Optional[str] = None
    from_sign: Optional[str] = None
    from_sign_label: Optional[str] = None
    to_sign: Optional[str] = None
    to_sign_label: Optional[str] = None


class CoordinateDiagnostic(PartialOutput):
    projection: Optional[str] = None
    projection_label: Optional[str] = None
    right_ascension: Optional[float] = None
    declination: Optional[float] = None
    hour_angle_degrees: Optional[float] = None
    semiarc_degrees: Optional[float] = None
    nocturnal_semiarc_degrees: Optional[float] = None
    quadrant: Optional[str] = None
    quadrant_label: Optional[str] = None
    mundane_position_degrees: Optional[float] = None


class PrimaryDirections(PartialOutput):
    method: Optional[str] = None
    method_label: Optional[str] = None
    time_key: Optional[str] = None
    time_key_label: Optional[str] = None
    pd_type: Optional[int] = None
    direction_mode: Optional[str] = None
    direction_mode_label: Optional[str] = None
    coordinate_system: Optional[str] = None
    coordinate_label: Optional[str] = None
    coordinate_backend: Optional[str] = None
    coordinate_precision: Optional[str] = None
    coordinate_diagnostics: Optional[Dict[str, CoordinateDiagnostic]] = None
    coordinate_points: Optional[Dict[str, CoordinateEntry]] = None
    coordinate_lots: Optional[Dict[str, CoordinateEntry]] = None
    current_coordinate_points: Optional[Dict[str, CoordinateEntry]] = None
    current_coordinate_lots: Optional[Dict[str, CoordinateEntry]] = None
    natal_coordinate_points: Optional[Dict[str, CoordinateEntry]] = None
    natal_coordinate_lots: Optional[Dict[str, CoordinateEntry]] = None
    directed_coordinate_points: Optional[Dict[str, CoordinateEntry]] = None
    directed_coordinate_lots: Optional[Dict[str, CoordinateEntry]] = None
    current_age_years: Optional[float] = None
    current_arc_degrees: Optional[float] = None
    current_arc_absolute_degrees: Optional[float] = None
    aspects: Optional[List[int]] = None
    promissors: Optional[List[str]] = None
    timeline: Optional[List[PrimaryDirectionHit]] = None
    current_window: Optional[List[PrimaryDirectionHit]] = None
    exact_window: Optional[List[PrimaryDirectionHit]] = None
    past_window: Optional[List[PrimaryDirectionHit]] = None
    future_window: Optional[List[PrimaryDirectionHit]] = None
    hits: Optional[List[PrimaryDirectionHit]] = None
    exact_hits: Optional[List[PrimaryDirectionHit]] = None
    coordinate_hits: Optional[List[PrimaryDirectionHit]] = None
    approximation: Optional[str] = None
    approximation_label: Optional[str] = None
    analysis_datetime: Optional[str] = None
    show_pd_bounds: Optional[bool] = None
    bounds_overlay: Optional[BoundsOverlay] = None
    directed_points: Optional[Dict[str, WesternPoint]] = None
    directed_lots: Optional[Dict[str, WesternPoint]] = None
    directed_ascendant: Optional[WesternPoint] = None
    directed_medium_coeli: Optional[WesternPoint] = None
    sign_changes: Optional[List[SignChange]] = None


class Profection(PartialOutput):
    activated_house: Optional[int] = None
    activated_sign: Optional[str] = None
    activated_sign_label: Optional[str] = None
    lord: Optional[str] = None
    lord_label: Optional[str] = None
    monthly_house: Optional[int] = None
    monthly_sign: Optional[str] = None
    monthly_sign_label: Optional[str] = None


class MonthlyProfection(PartialOutput):
    month_index: Optional[int] = None
    start: Optional[str] = None
    end: Optional[str] = None
    active: Optional[bool] = None
    house: Optional[int] = None
    house_label: Optional[str] = None
    sign: Optional[str] = None
    sign_label: Optional[str] = None
    lord: Optional[str] = None
    lord_label: Optional[str] = None


class HouseEmphasis(PartialOutput):
    house: Optional[int] = None
    house_label: Optional[str] = None
    count: Optional[int] = None


class TimingChart(PartialOutput):
    calculation_basis: Optional[WesternCalculationBasis] = None
    solver: Optional[ReturnSolver] = None
    return_datetime_utc: Optional[str] = None
    analysis_datetime: Optional[str] = None
    return_datetime: Optional[str] = None
    progressed_datetime: Optional[str] = None
    arc_degrees: Optional[float] = None
    ascendant: Optional[WesternPoint] = None
    medium_coeli: Optional[WesternPoint] = None
    sun: Optional[WesternPoint] = None
    moon: Optional[WesternPoint] = None
    hits: Optional[List[AspectHit]] = None
    exact_hits: Optional[List[AspectHit]] = None
    location: Optional[Location] = None
    natal_reference: Optional[Dict[str, WesternPoint]] = None
    transit_reference: Optional[Dict[str, WesternPoint]] = None
    house_emphasis: Optional[List[HouseEmphasis]] = None
    orb_limit: Optional[float] = None
    annual_profection: Optional[Profection] = None
    monthly_profections: Optional[List[MonthlyProfection]] = None
    year_start: Optional[str] = None
    year_end: Optional[str] = None


class FirdariaPeriod(PartialOutput):
    planet: Optional[str] = None
    planet_label: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    start_display: Optional[str] = None
    end_display: Optional[str] = None


class FirdariaMajor(FirdariaPeriod):
    years: Optional[float] = None
    subperiods: Optional[List[FirdariaPeriod]] = None
    nominal_start_age: Optional[int] = None
    nominal_end_age: Optional[int] = None


class FirdariaCalculationOptions(PartialOutput):
    night_order: Optional[str] = None
    year_basis: Optional[str] = None
    subperiod_basis: Optional[str] = None
    timezone: Optional[str] = None


class Firdaria(PartialOutput):
    sect: Optional[str] = None
    sect_label: Optional[str] = None
    current_major: Optional[FirdariaMajor] = None
    current_sub: Optional[FirdariaPeriod] = None
    timeline: Optional[List[FirdariaMajor]] = None
    calculation_options: Optional[FirdariaCalculationOptions] = None


class DecennialPeriod(PartialOutput):
    key: Optional[str] = None
    level: Optional[int] = None
    planet: Optional[str] = None
    planet_label: Optional[str] = None
    date: Optional[str] = None
    nominal: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    active: Optional[bool] = None
    start_offset_minutes: Optional[int] = None
    end_offset_minutes: Optional[int] = None
    sublevel: Optional[List["DecennialPeriod"]] = None


class Decennials(PartialOutput):
    base_order: Optional[List[str]] = None
    resolved_start_planet: Optional[str] = None
    resolved_start_planet_label: Optional[str] = None
    current_level_1: Optional[DecennialPeriod] = None
    current_level_2: Optional[DecennialPeriod] = None
    current_level_3: Optional[DecennialPeriod] = None
    timeline: Optional[List[DecennialPeriod]] = None


class ReleasingPeriod(PartialOutput):
    sign: Optional[str] = None
    sign_label: Optional[str] = None
    ruler: Optional[str] = None
    ruler_label: Optional[str] = None
    level: Optional[int] = None
    duration_value: Optional[float] = None
    duration_unit: Optional[str] = None
    duration_unit_label: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    loosing_of_bond: Optional[bool] = None
    parent_sign: Optional[str] = None
    parent_sign_label: Optional[str] = None
    active: Optional[bool] = None
    phase: Optional[str] = None
    phase_label: Optional[str] = None
    relative_sign_index: Optional[int] = None
    is_peak_period: Optional[bool] = None


class SignLabel(PartialOutput):
    sign: Optional[str] = None
    sign_label: Optional[str] = None


class ReleasingTrack(PartialOutput):
    base_point: Optional[str] = None
    base_point_label: Optional[str] = None
    release_start_sign: Optional[str] = None
    release_start_sign_label: Optional[str] = None
    lot: Optional[WesternPoint] = None
    peak_signs: Optional[List[SignLabel]] = None
    current_level_1: Optional[ReleasingPeriod] = None
    current_level_2: Optional[ReleasingPeriod] = None
    current_level_3: Optional[ReleasingPeriod] = None
    current_level_4: Optional[ReleasingPeriod] = None
    level_1_timeline: Optional[List[ReleasingPeriod]] = None
    level_2_timeline: Optional[List[ReleasingPeriod]] = None
    level_3_timeline: Optional[List[ReleasingPeriod]] = None
    level_4_timeline: Optional[List[ReleasingPeriod]] = None


class ZodiacalReleasing(PartialOutput):
    fortune: Optional[ReleasingTrack] = None
    spirit: Optional[ReleasingTrack] = None


class Returns(PartialOutput):
    solar_return: Optional[TimingChart] = None
    lunar_return: Optional[TimingChart] = None


class Directions(PartialOutput):
    given_year: Optional[TimingChart] = None
    primary_directions: Optional[PrimaryDirections] = None
    primary_direction_chart: Optional[PrimaryDirections] = None
    secondary_progression: Optional[TimingChart] = None
    solar_arc: Optional[TimingChart] = None


class TimeLords(PartialOutput):
    annual_profection: Optional[Profection] = None
    monthly_profections: Optional[List[MonthlyProfection]] = None
    firdaria: Optional[Firdaria] = None
    decennials: Optional[Decennials] = None
    zodiacal_releasing: Optional[ZodiacalReleasing] = None


class Transits(PartialOutput):
    current_transit: Optional[TimingChart] = None


class SystemOutput(PartialOutput):
    system: Optional[str] = None
    system_label: Optional[str] = None


class HarmonicConjunction(PartialOutput):
    points: Optional[List[str]] = None
    points_label: Optional[List[str]] = None
    separation_degree: Optional[float] = None
    orb: Optional[float] = None


class HarmonicChart(PartialOutput):
    harmonic: Optional[int] = None
    orb: Optional[float] = None
    method: Optional[str] = None
    method_label: Optional[str] = None
    positions: Optional[Dict[str, WesternPoint]] = None
    resonant_conjunctions: Optional[List[HarmonicConjunction]] = None


class AgeBand(PartialOutput):
    planet: Optional[str] = None
    planet_label: Optional[str] = None
    start_age: Optional[float] = None
    end_age: Optional[float] = None
    duration_years: Optional[float] = None
    active: Optional[bool] = None
    theme: Optional[str] = None
    natal_condition: Optional[WesternPoint] = None


class PlanetaryAges(SystemOutput):
    active_planet: Optional[str] = None
    active_planet_label: Optional[str] = None
    current_age_years: Optional[float] = None
    bands: Optional[List[AgeBand]] = None


class TriplicityStage(PartialOutput):
    stage: Optional[int] = None
    stage_label: Optional[str] = None
    role: Optional[str] = None
    role_label: Optional[str] = None
    ruler: Optional[str] = None
    ruler_label: Optional[str] = None
    start_age: Optional[float] = None
    end_age: Optional[float] = None
    planetary_period_years: Optional[float] = None
    natal_condition: Optional[WesternPoint] = None


class TriplicityRulers(SystemOutput):
    division: Optional[str] = None
    element: Optional[str] = None
    element_label: Optional[str] = None
    lifespan_years: Optional[float] = None
    sect: Optional[str] = None
    sect_label: Optional[str] = None
    sect_light: Optional[str] = None
    sect_light_label: Optional[str] = None
    sect_light_sign: Optional[str] = None
    sect_light_sign_label: Optional[str] = None
    stages: Optional[List[TriplicityStage]] = None


class PhaseIngress(PartialOutput):
    phase: Optional[str] = None
    phase_label: Optional[str] = None
    elongation_degree: Optional[float] = None
    ingress_age_years: Optional[float] = None


class LunationPhase(SystemOutput):
    max_age_years: Optional[float] = None
    natal_elongation_degree: Optional[float] = None
    natal_phase: Optional[str] = None
    natal_phase_label: Optional[str] = None
    progression_rate_deg_per_year: Optional[float] = None
    synodic_cycle_years: Optional[float] = None
    phase_ingresses: Optional[List[PhaseIngress]] = None


class DistributionParticipant(PartialOutput):
    planet: Optional[str] = None
    planet_label: Optional[str] = None
    contact_age_years: Optional[float] = None


class DistributionPeriod(PartialOutput):
    distributor: Optional[str] = None
    distributor_label: Optional[str] = None
    sign: Optional[str] = None
    sign_label: Optional[str] = None
    bound_start_degree: Optional[float] = None
    bound_end_degree: Optional[float] = None
    start_age_years: Optional[float] = None
    end_age_years: Optional[float] = None
    participants: Optional[List[DistributionParticipant]] = None


class Distributions(SystemOutput):
    ascendant_absolute_degree: Optional[float] = None
    direction_model: Optional[str] = None
    direction_model_label: Optional[str] = None
    max_age_years: Optional[float] = None
    rate_deg_per_year: Optional[float] = None
    time_key: Optional[str] = None
    periods: Optional[List[DistributionPeriod]] = None


class AgePeriod(PartialOutput):
    planet: Optional[str] = None
    planet_label: Optional[str] = None
    start_age_years: Optional[float] = None
    duration_years: Optional[float] = None
    small_year: Optional[float] = None


class BalbillusPeriod(AgePeriod):
    sub_periods: Optional[List[AgePeriod]] = None


class Balbillus(SystemOutput):
    max_age_years: Optional[float] = None
    mode: Optional[str] = None
    mode_label: Optional[str] = None
    start_planet: Optional[str] = None
    start_planet_label: Optional[str] = None
    zodiacal_order: Optional[List[str]] = None
    periods: Optional[List[BalbillusPeriod]] = None


class YearSystem129(SystemOutput):
    max_age_years: Optional[float] = None
    sequence_model: Optional[str] = None
    sequence_model_label: Optional[str] = None
    start_planet: Optional[str] = None
    start_planet_label: Optional[str] = None
    zodiacal_order: Optional[List[str]] = None
    total_cycle_years: Optional[int] = None
    periods: Optional[List[AgePeriod]] = None


class KeypointPosition(PartialOutput):
    planet: Optional[str] = None
    planet_label: Optional[str] = None
    position_number: Optional[int] = None
    period_number: Optional[int] = None


class KeypointActivation(PartialOutput):
    age: Optional[int] = None
    house: Optional[int] = None
    factors: Optional[List[List[int]]] = None
    position_active: Optional[List[KeypointPosition]] = None
    period_active: Optional[List[KeypointPosition]] = None


class Keypoints(SystemOutput):
    release_mode: Optional[str] = None
    release_mode_label: Optional[str] = None
    release_sign_index: Optional[int] = None
    positions: Optional[List[KeypointPosition]] = None
    activations: Optional[List[KeypointActivation]] = None


class PlanetaryArc(SystemOutput):
    arc_degrees: Optional[float] = None
    arc_source: Optional[str] = None
    arc_source_label: Optional[str] = None
    orb: Optional[float] = None
    positions: Optional[Dict[str, WesternPoint]] = None
    hits: Optional[List[AspectHit]] = None


class PersianHit(PartialOutput):
    age: Optional[float] = None
    aspect: Optional[int] = None
    date: Optional[str] = None
    promittor: Optional[str] = None
    promittor_label: Optional[str] = None
    significator: Optional[str] = None


class PersianDirected(SystemOutput):
    hit_count: Optional[int] = None
    max_age_years: Optional[float] = None
    rate_deg_per_year: Optional[float] = None
    hits: Optional[List[PersianHit]] = None


class AgePointPosition(PartialOutput):
    age: Optional[float] = None
    longitude: Optional[float] = None
    sign: Optional[str] = None
    sign_label: Optional[str] = None
    signlon: Optional[float] = None
    house: Optional[int] = None
    aspect_to: Optional[str] = None
    aspect_to_label: Optional[str] = None


class AgePointContact(PartialOutput):
    age: Optional[float] = None
    body: Optional[str] = None
    body_label: Optional[str] = None
    longitude: Optional[float] = None


class AgePoint(SystemOutput):
    cycle_years: Optional[float] = None
    max_age_years: Optional[float] = None
    years_per_house: Optional[float] = None
    points: Optional[List[AgePointPosition]] = None
    contacts: Optional[List[AgePointContact]] = None


class VedicProgression(SystemOutput):
    orb: Optional[float] = None
    zodiac: Optional[str] = None
    positions: Optional[Dict[str, WesternPoint]] = None
    hits: Optional[List[AspectHit]] = None


class DeclinationParallel(PartialOutput):
    kind: Optional[str] = None
    kind_label: Optional[str] = None
    natal: Optional[str] = None
    natal_label: Optional[str] = None
    natal_declination: Optional[float] = None
    progressed: Optional[str] = None
    progressed_label: Optional[str] = None
    progressed_declination: Optional[float] = None
    orb: Optional[float] = None


class JaynesDeclination(SystemOutput):
    orb: Optional[float] = None
    parallels: Optional[List[DeclinationParallel]] = None


class ReturnMoment(PartialOutput):
    datetime_utc: Optional[str] = None
    datetime_local: Optional[str] = None


class PlanetReturn(PartialOutput):
    body: Optional[str] = None
    body_label: Optional[str] = None
    natal_longitude: Optional[WesternPoint] = None
    most_recent_return: Optional[ReturnMoment] = None
    next_return: Optional[ReturnMoment] = None


class ExtraReturns(SystemOutput):
    reference_datetime: Optional[str] = None
    returns: Optional[List[PlanetReturn]] = None


class Mundane(SystemOutput):
    calculation_basis: Optional[WesternCalculationBasis] = None
    ingress_term: Optional[str] = None
    ingress_datetime_local: Optional[str] = None
    ingress_datetime_utc: Optional[str] = None
    ascendant: Optional[WesternPoint] = None
    medium_coeli: Optional[WesternPoint] = None
    points: Optional[Dict[str, WesternPoint]] = None


class LillyDignity(PartialOutput):
    rule_id: Optional[str] = None
    status: Optional[str] = None
    planet: Optional[str] = None
    longitude: Optional[float] = None
    sign: Optional[str] = None
    degree_in_sign: Optional[float] = None
    chart_sect: Optional[str] = None
    dignities: Optional[List[str]] = None
    unknown_dignities: Optional[List[str]] = None
    debilities: Optional[List[str]] = None
    peregrine: Optional[bool] = None
    lords: Optional[Dict[str, Optional[str]]] = None
    bound_start_degree: Optional[int] = None
    bound_end_degree: Optional[int] = None
    exaltation_degree_in_sign: Optional[int] = None
    source_pages: Optional[List[int]] = None
    boundary_policy: Optional[str] = None


class LillyReception(PartialOutput):
    rule_id: Optional[str] = None
    receiver: Optional[str] = None
    guest: Optional[str] = None
    guest_longitude: Optional[float] = None
    guest_sign: Optional[str] = None
    chart_sect: Optional[str] = None
    allowed_dignities: Optional[List[str]] = None
    dignities: Optional[List[str]] = None
    unknown_dignities: Optional[List[str]] = None
    receives: Optional[bool] = None
    source_pages: Optional[List[int]] = None


class LillyPairReception(PartialOutput):
    rule_id: Optional[str] = None
    status: Optional[str] = None
    directions: Optional[List[LillyReception]] = None
    mutual: Optional[bool] = None
    mutual_same_kind: Optional[List[str]] = None


class LillyCondition(PartialOutput):
    code: Optional[str] = None
    passed: Optional[bool] = None
    status: Optional[str] = None
    source_pages: Optional[List[int]] = None
    detail: Optional[str] = None


class LillyHouseCondition(PartialOutput):
    occupied_house: Optional[int] = None
    house_class: Optional[str] = None
    p48_strength_rank: Optional[int] = None
    p48_rank_condition: Optional[str] = None
    p115_house_points: Optional[int] = None
    points_scope: Optional[str] = None
    assignment_policy: Optional[str] = None
    house_system: Optional[str] = None
    zodiac_type: Optional[str] = None
    source_method_scope: Optional[str] = None
    source_url: Optional[str] = None
    source_pages: Optional[List[int]] = None
    full_original_text_acceptance: Optional[bool] = None


class LillyHouseAssignment(PartialOutput):
    rule_id: Optional[str] = None
    source_url: Optional[str] = None
    source_pages: Optional[List[int]] = None
    status: Optional[str] = None
    unavailable_reason: Optional[str] = None
    geometric_house: Optional[int] = None
    assigned_house: Optional[int] = None
    changed_from_geometric_house: Optional[bool] = None
    five_degree_limit: Optional[int] = None
    boundary_policy: Optional[str] = None
    assignment_policy: Optional[str] = None
    house_system: Optional[str] = None
    zodiac_type: Optional[str] = None
    source_method_scope: Optional[str] = None
    source_exception: Optional[str] = None
    full_original_text_acceptance: Optional[bool] = None
    longitude: Optional[float] = None
    lower_cusp: Optional[float] = None
    next_cusp: Optional[float] = None
    previous_cusp_gap_degrees: Optional[float] = None
    next_cusp_gap_degrees: Optional[float] = None
    previous_cusp_gap_exact_degrees: Optional[str] = None
    next_cusp_gap_exact_degrees: Optional[str] = None
    assigned_p115_house_points: Optional[int] = None
    assigned_p145_house_points: Optional[int] = None
    conditional_reading_zh: Optional[str] = None


class HoraryPlanet(WesternPoint):
    house_assignment: Optional[LillyHouseAssignment] = None
    occupied_house: Optional[int] = None
    house_condition: Optional[LillyHouseCondition] = None
    speed: Optional[float] = None
    dignities: Optional[List[str]] = None
    essential_condition: Optional[LillyDignity] = None


class HoraryAspect(PartialOutput):
    orb_profile: Optional[str] = None
    orb_limit: Optional[float] = None
    separation: Optional[float] = None
    ray_degrees: Optional[int] = None
    after_days: Optional[float] = None
    julian_day_tt: Optional[float] = None
    root_bracket_tt: Optional[List[float]] = None
    moon_longitude: Optional[float] = None
    other_longitude: Optional[float] = None
    moon_latitude: Optional[float] = None
    other_latitude: Optional[float] = None
    datetime_utc: Optional[str] = None
    inside_current_orb: Optional[bool] = None
    angle: Optional[float] = None
    aspect: Optional[str] = None
    aspect_label: Optional[str] = None
    orb: Optional[float] = None
    other: Optional[str] = None
    other_label: Optional[str] = None
    applying: Optional[bool] = None
    phase: Optional[str] = None


class HoraryMotionBasis(PartialOutput):
    future_speed_policy: Optional[Dict[str, Any]] = None
    ephemeris_reference_points: Optional[EphemerisReferencePoints] = None
    longitude_motion: Optional[LongitudeMotionPolicy] = None
    status: Optional[str] = None
    method_id: Optional[str] = None
    constant_velocity_projection: Optional[bool] = None
    degrees_left_in_sign: Optional[float] = None
    sign_exit_after_days: Optional[float] = None
    sign_exit_julian_day_tt: Optional[float] = None
    sign_exit_root_bracket_tt: Optional[List[float]] = None
    start_julian_day_tt: Optional[float] = None
    contacts: Optional[List[HoraryAspect]] = None
    ambiguous_boundary_contacts: Optional[List[HoraryAspect]] = None
    void_of_course: Optional[bool] = None
    unavailable_reason: Optional[str] = None
    source_url: Optional[str] = None
    source_scope: Optional[str] = None
    time_scale: Optional[str] = None
    scan_step_days: Optional[float] = None
    scan_guard_days: Optional[int] = None
    monotonicity_evidence: Optional[str] = None
    physical_ephemeris_source: Optional[PhysicalEphemerisSource] = None
    longitude_frame: Optional[str] = None
    datetime_utc: Optional[str] = None


class HoraryMoon(PartialOutput):
    motion_basis: Optional[HoraryMotionBasis] = None
    degrees_left_in_sign: Optional[float] = None
    next_aspect: Optional[HoraryAspect] = None
    sign: Optional[str] = None
    sign_label: Optional[str] = None
    speed: Optional[float] = None
    void_of_course: Optional[bool] = None


class LillyDirectedSignRelationship(PartialOutput):
    method_id: Optional[str] = None
    caster: Optional[str] = None
    receiver: Optional[str] = None
    caster_sign: Optional[str] = None
    receiver_sign: Optional[str] = None
    forward_sign_steps: Optional[int] = None
    distinct_bodies: Optional[bool] = None
    relation_status: Optional[
        Literal["ray", "co_present", "listed_inconjunct", "not_in_either_table"]
    ] = None
    sign_ray: Optional[Literal["sextile", "square", "trine", "opposition"]] = None
    ray_direction: Optional[Literal["dexter", "sinister"]] = None
    listed_inconjunct: Optional[bool] = None
    selected_degree_aspect: Optional[str] = None
    selected_degree_aspect_agrees: Optional[bool] = None
    coordinate_scope: Optional[str] = None
    source_pages: Optional[List[int]] = None
    source_url: Optional[str] = None
    boundary_policy: Optional[str] = None
    direction_policy: Optional[str] = None
    quantitative_bonus_added: Optional[Literal[False]] = None
    full_original_text_acceptance: Optional[Literal[False]] = None


class HorarySignificators(PartialOutput):
    querent: Optional[HoraryPlanet] = None
    quesited: Optional[HoraryPlanet] = None
    moon_co_significator: Optional[HoraryPlanet] = None
    directed_sign_relationship: Optional[LillyDirectedSignRelationship] = None


class LillyRoute(PartialOutput):
    mode: Optional[str] = None
    actors: Optional[List[str]] = None
    condition_epoch: Optional[str] = None
    status: Optional[str] = None
    conditions: Optional[List[LillyCondition]] = None
    receptions: Optional[List[LillyReception]] = None
    full_path_accepted: Optional[bool] = None
    source_planet: Optional[str] = None
    target_planet: Optional[str] = None
    carrier: Optional[str] = None
    collector: Optional[str] = None
    aspect: Optional[HoraryAspect] = None
    next_lunar_contact: Optional[HoraryAspect] = None


class LillyConditionalReading(PartialOutput):
    premise_satisfied: Optional[bool] = None
    source_pages: Optional[List[int]] = None
    conditional_reading_zh: Optional[str] = None
    full_judgement_accepted: Optional[bool] = None


class PlanetaryEventState(PartialOutput):
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    speed: Optional[float] = None
    speed_native: Optional[float] = None
    speed_light_time_correction: Optional[float] = None
    speed_spatial_aberration_correction: Optional[float] = None
    speed_lunar_source_remainder_correction: Optional[float] = None
    speed_sidereal_origin_wrap_correction: Optional[float] = None
    speed_rotation_correction: Optional[float] = None
    speed_analytic_frame_correction: Optional[float] = None
    speed_position_derivative_correction: Optional[float] = None
    speed_display_offset_correction: Optional[float] = None


class PlanetaryEventFailedSample(PartialOutput):
    planet: Optional[str] = None
    julian_day_tt: Optional[float] = None


class PlanetaryEvent(PartialOutput):
    kind: Optional[str] = None
    bodies: Optional[List[str]] = None
    julian_day_tt: Optional[float] = None
    root_bracket_tt: Optional[List[float]] = None
    epoch_relation: Optional[str] = None
    states: Optional[Dict[str, PlanetaryEventState]] = None
    state_brackets: Optional[Dict[str, List[PlanetaryEventState]]] = None
    ray_degrees: Optional[int] = None
    direction: Optional[int] = None
    topology: Optional[str] = None
    aspect: Optional[str] = None
    datetime_utc: Optional[str] = None


class PlanetaryUnresolvedInterval(PartialOutput):
    kind: Optional[str] = None
    bodies: Optional[List[str]] = None
    interval_tt: Optional[List[float]] = None


class PlanetaryEventHistory(PartialOutput):
    apparent_position_policy: Optional[ApparentPositionPolicy] = None
    ephemeris_reference_points: Optional[EphemerisReferencePoints] = None
    longitude_motion: Optional[LongitudeMotionPolicy] = None
    status: Optional[str] = None
    method_id: Optional[str] = None
    constant_velocity_projection: Optional[bool] = None
    time_scale: Optional[str] = None
    question_julian_day_tt: Optional[float] = None
    window_tt: Optional[List[float]] = None
    scan_step_days: Optional[float] = None
    bodies: Optional[List[str]] = None
    question_states: Optional[Dict[str, PlanetaryEventState]] = None
    events: Optional[List[PlanetaryEvent]] = None
    unresolved_intervals: Optional[List[PlanetaryUnresolvedInterval]] = None
    completeness_scope: Optional[str] = None
    full_original_text_acceptance: Optional[bool] = None
    physical_ephemeris_source: Optional[PhysicalEphemerisSource] = None
    longitude_frame: Optional[str] = None
    unavailable_reason: Optional[str] = None
    unavailable_code: Optional[str] = None
    failed_sample: Optional[PlanetaryEventFailedSample] = None


class EventReception(PartialOutput):
    julian_day_tt: Optional[float] = None
    root_bracket_tt: Optional[List[float]] = None
    chart_sect: Optional[str] = None
    reception: Optional[LillyReception] = None
    endpoint_receptions: Optional[List[LillyReception]] = None
    boundary_uncertainty: Optional[bool] = None


class LillyEventPath(PartialOutput):
    mode: Optional[str] = None
    actors: Optional[List[str]] = None
    conditions: Optional[List[LillyCondition]] = None
    sequence_conditions_satisfied: Optional[bool] = None
    status: Optional[str] = None
    event_receptions: Optional[List[EventReception]] = None
    full_path_accepted: Optional[bool] = None
    prior_principal_contact: Optional[PlanetaryEvent] = None
    prior_carrier_contact: Optional[PlanetaryEvent] = None
    future_contact: Optional[PlanetaryEvent] = None
    transitions: Optional[List[PlanetaryEvent]] = None
    intervening_contacts: Optional[List[PlanetaryEvent]] = None
    collection_contacts: Optional[List[PlanetaryEvent]] = None


class RefranationPattern(PartialOutput):
    applicant: Optional[str] = None
    recipient: Optional[str] = None
    station: Optional[PlanetaryEvent] = None
    source_pages: Optional[List[int]] = None
    scope: Optional[str] = None


class ProhibitionPattern(PartialOutput):
    interposer: Optional[str] = None
    applicant: Optional[str] = None
    recipient: Optional[str] = None
    first_contact: Optional[PlanetaryEvent] = None
    second_contact: Optional[PlanetaryEvent] = None
    source_pages: Optional[List[int]] = None
    scope: Optional[str] = None


class LillyEventPaths(PartialOutput):
    status: Optional[str] = None
    paths: Optional[List[LillyEventPath]] = None
    refranation_patterns: Optional[List[RefranationPattern]] = None
    prohibition_patterns: Optional[List[ProhibitionPattern]] = None
    reception_epoch_policy: Optional[str] = None
    source_pages: Optional[List[int]] = None
    scope: Optional[str] = None
    full_original_text_acceptance: Optional[bool] = None
    unavailable_reason: Optional[str] = None


class LillyDwellingClause(PartialOutput):
    rule_id: Optional[str] = None
    source_url: Optional[str] = None
    source_pages: Optional[List[int]] = None
    quesited_occupied_house: Optional[int] = None
    quesited_in_first_house: Optional[bool] = None
    dwelling_alone_sufficient: Optional[bool] = None
    distinct_lunar_transfer_actors: Optional[bool] = None
    moon_last_contact_is_quesited: Optional[bool] = None
    moon_next_contact_is_querent: Optional[bool] = None
    moon_separating_from_prior_source_ray_now: Optional[bool] = None
    moon_applying_to_next_recipient_ray_now: Optional[bool] = None
    lunar_sequence_subconditions_satisfied: Optional[bool] = None
    named_necessary_conditions_satisfied: Optional[bool] = None
    prior_lunar_contact: Optional[PlanetaryEvent] = None
    next_lunar_contact: Optional[PlanetaryEvent] = None
    matching_p126_event_path_indexes: Optional[List[int]] = None
    event_history_status: Optional[str] = None
    event_history_unavailable_reason: Optional[str] = None
    event_history_window_tt: Optional[List[float]] = None
    event_history_completeness_scope: Optional[str] = None
    scope: Optional[str] = None
    conditional_reading_zh: Optional[str] = None
    full_judgement_accepted: Optional[bool] = None
    full_original_text_acceptance: Optional[bool] = None


class LillyConditions(PartialOutput):
    rule_id: Optional[str] = None
    chart_sect: Optional[str] = None
    coordinate_scope: Optional[str] = None
    principal_reception: Optional[LillyPairReception] = None
    p112_mutual_reception: Optional[LillyConditionalReading] = None
    p126_127_dwelling: Optional[LillyDwellingClause] = None
    routes: Optional[List[LillyRoute]] = None
    event_paths: Optional[LillyEventPaths] = None
    same_body_not_bilateral: Optional[bool] = None
    full_original_text_acceptance: Optional[bool] = None
    scope: Optional[str] = None


class HoraryPerfection(PartialOutput):
    lilly_conditions: Optional[LillyConditions] = None
    event_history: Optional[PlanetaryEventHistory] = None
    heuristic_perfection_signal: Optional[bool] = None
    candidate: Optional[bool] = None
    candidate_scope: Optional[str] = None
    status: Optional[str] = None
    missing_conditions: Optional[List[str]] = None
    carrier: Optional[str] = None
    carrier_label: Optional[str] = None
    collector: Optional[str] = None
    collector_label: Optional[str] = None
    mode: Optional[str] = None
    mode_label: Optional[str] = None
    perfects: Optional[bool] = None
    receptions: Optional[List[str]] = None
    aspect: Optional[HoraryAspect] = None


class HoraryStricture(PartialOutput):
    code: Optional[str] = None
    detail: Optional[str] = None
    source_pages: Optional[List[int]] = None
    status: Optional[str] = None
    exception_satisfied: Optional[bool] = None
    exception_applicable: Optional[bool] = None
    attributed_variant: Optional[bool] = None


class LillyRadicalityReportedContext(PartialOutput):
    figure_origin: Optional[str] = None
    very_young_querent_reported: Optional[bool] = None
    rising_description_agreement_reported: Optional[bool] = None
    age_degree_agreement_reported: Optional[bool] = None
    event_time_certain_reported: Optional[bool] = None
    principal_significators_very_strong_reported: Optional[bool] = None
    seventh_cusp_afflicted_reported: Optional[bool] = None
    seventh_lord_impeded_reported: Optional[bool] = None
    seventh_lord_unfortunate_reported: Optional[bool] = None
    equal_fortune_infortune_testimonies_reported: Optional[bool] = None
    figure_origin_source: Optional[str] = None
    provided_fields: Optional[List[str]] = None
    verification_scope: Optional[str] = None


class LillyHourAffinity(PartialOutput):
    hour_ruler: Optional[str] = None
    ascendant_sign: Optional[str] = None
    ascendant_lord: Optional[str] = None
    chart_sect: Optional[str] = None
    same_ruler: Optional[bool] = None
    ascendant_triplicity: Optional[bool] = None
    same_own_nature: Optional[bool] = None
    selected_triplicity_lord: Optional[str] = None
    listed_triplicity_lords: Optional[List[str]] = None
    hour_ruler_in_any_listed_triplicity: Optional[bool] = None
    hour_ruler_own_nature: Optional[List[str]] = None
    ascendant_lord_own_nature: Optional[List[str]] = None
    supported_under_declared_policy: Optional[bool] = None
    triplicity_policy: Optional[str] = None
    nature_policy: Optional[str] = None
    source_pages: Optional[List[int]] = None
    full_original_text_acceptance: Optional[bool] = None


class LillyRadicalityHourInputs(PartialOutput):
    status: Optional[str] = None
    unavailable_reason: Optional[str] = None
    hour: Optional[PlanetaryHours] = None
    horizon_policy: Optional[str] = None
    actual_solar_backend_verified: Optional[bool] = None
    source_method_acceptance: Optional[bool] = None
    epoch_jd_ut1: Optional[float] = None
    geometric_chart_sect: Optional[str] = None
    hour_and_geometric_sect_differ: Optional[bool] = None
    sect_comparison_policy: Optional[str] = None


class LillyConsideration(PartialOutput):
    code: Optional[str] = None
    condition: Optional[str] = None
    source_pages: Optional[List[int]] = None
    condition_present: Optional[bool] = None
    applicable: Optional[bool] = None
    exception_satisfied: Optional[bool] = None
    exception_applicable: Optional[bool] = None
    attributed_variant: Optional[bool] = None
    status: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    conditional_reading_zh: Optional[str] = None


class HoraryDegreeGate(PartialOutput):
    early: Optional[bool] = None
    late: Optional[bool] = None
    early_exception_satisfied: Optional[bool] = None
    late_exception_satisfied: Optional[bool] = None
    certain_timed_event_exception: Optional[bool] = None


class HoraryRadicality(PartialOutput):
    method_id: Optional[str] = None
    source_url: Optional[str] = None
    source_pages: Optional[List[int]] = None
    clause_count: Optional[int] = None
    clauses: Optional[List[LillyConsideration]] = None
    hour_inputs: Optional[LillyRadicalityHourInputs] = None
    hour_affinity: Optional[LillyHourAffinity] = None
    reported_context: Optional[LillyRadicalityReportedContext] = None
    ascendant_degree_gate: Optional[HoraryDegreeGate] = None
    unknown_clauses: Optional[List[str]] = None
    status: Optional[str] = None
    house_policy: Optional[str] = None
    house_system: Optional[str] = None
    zodiac_type: Optional[str] = None
    source_method_scope: Optional[str] = None
    conditional_reading_zh: Optional[str] = None
    full_original_text_acceptance: Optional[bool] = None
    full_judgement_accepted: Optional[bool] = None
    real_world_prediction_established: Optional[bool] = None
    safe_to_judge_scope: Optional[str] = None
    safe_to_judge: Optional[bool] = None
    strictures: Optional[List[HoraryStricture]] = None


class LillyOrbTable(PartialOutput):
    profile_id: Optional[str] = None
    source_url: Optional[str] = None
    source_pages: Optional[List[int]] = None
    full_orbs_degrees: Optional[Dict[str, float]] = None
    moieties_degrees: Optional[Dict[str, float]] = None
    available_profiles: Optional[List[str]] = None
    pair_rule: Optional[str] = None
    boundary_convention: Optional[str] = None
    default_selection_basis: Optional[str] = None
    full_original_text_acceptance: Optional[bool] = None


class LillyFortitudeSample(PartialOutput):
    offset_days: Optional[float] = None
    longitude: Optional[float] = None


class LillyFortitudeMotion(PartialOutput):
    nominal_coordinate_check: Optional[str] = None
    nominal_coordinate_roundoff_allowance_degrees: Optional[float] = None
    direction: Optional[str] = None
    daily_motion_degrees: Optional[float] = None
    daily_motion_exact_degrees: Optional[str] = None
    status: Optional[str] = None
    samples: Optional[List[LillyFortitudeSample]] = None
    instantaneous_speed_degrees_per_day: Optional[float] = None
    source_model: Optional[str] = None


class LillyFortitudeInputs(PartialOutput):
    status: Optional[str] = None
    reason: Optional[str] = None
    epoch_jd_tt: Optional[float] = None
    motion: Optional[Dict[str, LillyFortitudeMotion]] = None
    north_node_longitude: Optional[float] = None
    node_model: Optional[str] = None
    star_longitudes: Optional[Dict[str, float]] = None
    star_position_policy: Optional[str] = None
    daily_motion_policy: Optional[str] = None
    day_interval_tt: Optional[List[float]] = None
    longitude_frame: Optional[str] = None
    physical_ephemeris_source: Optional[PhysicalEphemerisSource] = None
    stars_profile: Optional[FixedStarProfile] = None


class LillyFortitudeRow(PartialOutput):
    code: Optional[str] = None
    group: Optional[str] = None
    condition: Optional[str] = None
    label_zh: Optional[str] = None
    points: Optional[int] = None
    applicable: Optional[bool] = None
    satisfied: Optional[bool] = None
    contribution: Optional[int] = None
    status: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    source_pages: Optional[List[int]] = None


class LillyFortitudeAppliedCondition(PartialOutput):
    code: Optional[str] = None
    label_zh: Optional[str] = None
    contribution: Optional[int] = None
    source_pages: Optional[List[int]] = None


class LillyFortitudeSummary(PartialOutput):
    status: Optional[str] = None
    known_fortitudes: Optional[int] = None
    known_debilities: Optional[int] = None
    known_balance: Optional[int] = None
    literal_table_balance: Optional[int] = None
    unknown_rows: Optional[List[str]] = None
    applied_conditions: Optional[List[LillyFortitudeAppliedCondition]] = None
    row_count: Optional[int] = None
    points_are_success_probability: Optional[bool] = None
    conditional_reading_zh: Optional[str] = None


class LillyFortitudePlanet(LillyFortitudeSummary):
    rows: Optional[List[LillyFortitudeRow]] = None


class LillyFortitudes(PartialOutput):
    method_id: Optional[str] = None
    source_url: Optional[str] = None
    source_edition: Optional[str] = None
    source_pages: Optional[List[int]] = None
    row_count_per_planet: Optional[int] = None
    planets: Optional[Dict[str, LillyFortitudePlanet]] = None
    summary: Optional[Dict[str, LillyFortitudeSummary]] = None
    physical_inputs: Optional[LillyFortitudeInputs] = None
    solar_policy: Optional[Dict[str, Any]] = None
    zodiac_type: Optional[str] = None
    house_system: Optional[str] = None
    source_method_scope: Optional[str] = None
    aggregation_policy: Optional[str] = None
    source_conflicts: Optional[List[str]] = None
    full_original_text_acceptance: Optional[bool] = None
    full_judgement_accepted: Optional[bool] = None
    real_world_prediction_established: Optional[bool] = None


class LillyFortuneFormula(PartialOutput):
    expression: Optional[str] = None
    reverses_at_night: Optional[bool] = None
    ascendant: Optional[float] = None
    sun: Optional[float] = None
    moon: Optional[float] = None
    uses_physical_ascendant_not_first_cusp: Optional[bool] = None
    source_pages: Optional[List[int]] = None
    scope: Optional[str] = None


class LillyFortune(LillyFortitudeSummary):
    method_id: Optional[str] = None
    source_url: Optional[str] = None
    source_pages: Optional[List[int]] = None
    longitude: Optional[float] = None
    exact_longitude: Optional[str] = None
    sign: Optional[str] = None
    degree_in_sign: Optional[float] = None
    formula: Optional[LillyFortuneFormula] = None
    house_assignment: Optional[LillyHouseAssignment] = None
    bound_lord: Optional[str] = None
    solar_state: Optional[str] = None
    rows: Optional[List[LillyFortitudeRow]] = None
    source_method_scope: Optional[str] = None
    interpretation_policies: Optional[List[str]] = None
    full_original_text_acceptance: Optional[bool] = None
    full_judgement_accepted: Optional[bool] = None
    real_world_prediction_established: Optional[bool] = None


class HoraryRuleProfile(PartialOutput):
    sign_relationship_policy: Optional[str] = None
    radicality_policy: Optional[str] = None
    cusp_virtue_policy: Optional[str] = None
    fortune_policy: Optional[str] = None
    fortitudes_policy: Optional[str] = None
    orb_table: Optional[LillyOrbTable] = None
    house_axis_policy: Optional[str] = None
    essential_dignity_policy: Optional[str] = None
    rule_id: Optional[str] = None
    source_edition: Optional[str] = None
    source_url: Optional[str] = None
    chapter_pages: Optional[List[int]] = None
    full_original_text_acceptance: Optional[bool] = None
    instantaneous_phase: Optional[str] = None
    orb_policy: Optional[str] = None
    moon_policy: Optional[str] = None
    judgement_status: Optional[str] = None


class Horary(SystemOutput):
    reference_geometry: Optional[Dict[str, Any]] = None
    backend_convention: Optional[Dict[str, Any]] = None
    fortune: Optional[LillyFortune] = None
    fortitudes: Optional[LillyFortitudes] = None
    calculation_basis: Optional[WesternCalculationBasis] = None
    heuristic_verdict: Optional[str] = None
    heuristic_reasoning: Optional[str] = None
    rule_profile: Optional[HoraryRuleProfile] = None
    category: Optional[str] = None
    category_label: Optional[str] = None
    ascendant: Optional[WesternPoint] = None
    moon: Optional[HoraryMoon] = None
    significators: Optional[HorarySignificators] = None
    planets: Optional[Dict[str, HoraryPlanet]] = None
    perfection: Optional[HoraryPerfection] = None
    quesited_house: Optional[int] = None
    radicality: Optional[HoraryRadicality] = None
    reasoning: Optional[str] = None
    verdict: Optional[str] = None


WESTERN_FIELDS: Dict[str, Any] = {
    "calendar_conversion": WesternCivilCalendarConversion,
    "clock_conversion": WesternEventClockConversion,
    "natal_reference": NatalReference,
    "solarreturn": TimingChart,
    "lunarreturn": TimingChart,
    "transit": TimingChart,
    "solararc": TimingChart,
    "givenyear": TimingChart,
    "profection": Profection,
    "pd": PrimaryDirections,
    "pdchart": PrimaryDirections,
    "zr": ZodiacalReleasing,
    "firdaria": Firdaria,
    "decennials": Decennials,
    "directions": Directions,
    "returns": Returns,
    "time_lords": TimeLords,
    "transits": Transits,
    "harmonic_chart": HarmonicChart,
    "planetary_ages": PlanetaryAges,
    "triplicity_rulers": TriplicityRulers,
    "lunation_phase": LunationPhase,
    "distributions": Distributions,
    "balbillus": Balbillus,
    "keypoints": Keypoints,
    "yearsystem129": YearSystem129,
    "planetary_arc": PlanetaryArc,
    "persian_directed": PersianDirected,
    "age_point": AgePoint,
    "vedic_progression": VedicProgression,
    "jaynes_declination": JaynesDeclination,
    "mundane": Mundane,
    "extrareturns": ExtraReturns,
    "horary": Horary,
}
