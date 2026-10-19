"""Stable nested facts for western professional techniques.

These contracts follow the builders in core/predictive, astrology_lifespan and
astrology_horary. Dictionary keys (planet, lot and diagnostic identifiers) stay
open; their values have contracts. Labels and method names remain extensible.
"""

from typing import Any, Dict, List, Optional

from fatebridge.core.output_base import PartialOutput


class WesternPoint(PartialOutput):
    point: Optional[str] = None
    point_label: Optional[str] = None
    absolute_degree: Optional[float] = None
    degree: Optional[float] = None
    longitude: Optional[float] = None
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


class NatalReference(PartialOutput):
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
    ingress_term: Optional[str] = None
    ingress_datetime_local: Optional[str] = None
    ingress_datetime_utc: Optional[str] = None
    ascendant: Optional[WesternPoint] = None
    medium_coeli: Optional[WesternPoint] = None
    points: Optional[Dict[str, WesternPoint]] = None


class HoraryPlanet(WesternPoint):
    speed: Optional[float] = None
    dignities: Optional[List[str]] = None


class HoraryAspect(PartialOutput):
    angle: Optional[float] = None
    aspect: Optional[str] = None
    aspect_label: Optional[str] = None
    orb: Optional[float] = None
    other: Optional[str] = None
    other_label: Optional[str] = None
    applying: Optional[bool] = None
    phase: Optional[str] = None


class HoraryMoon(PartialOutput):
    degrees_left_in_sign: Optional[float] = None
    next_aspect: Optional[HoraryAspect] = None
    sign: Optional[str] = None
    sign_label: Optional[str] = None
    speed: Optional[float] = None
    void_of_course: Optional[bool] = None


class HorarySignificators(PartialOutput):
    querent: Optional[HoraryPlanet] = None
    quesited: Optional[HoraryPlanet] = None
    moon_co_significator: Optional[HoraryPlanet] = None


class HoraryPerfection(PartialOutput):
    mode: Optional[str] = None
    mode_label: Optional[str] = None
    perfects: Optional[bool] = None
    receptions: Optional[List[str]] = None
    aspect: Optional[HoraryAspect] = None


class HoraryStricture(PartialOutput):
    code: Optional[str] = None
    detail: Optional[str] = None


class HoraryRadicality(PartialOutput):
    safe_to_judge: Optional[bool] = None
    strictures: Optional[List[HoraryStricture]] = None


class Horary(SystemOutput):
    category: Optional[str] = None
    category_label: Optional[str] = None
    ascendant: Optional[WesternPoint] = None
    moon: Optional[HoraryMoon] = None
    significators: Optional[HorarySignificators] = None
    perfection: Optional[HoraryPerfection] = None
    quesited_house: Optional[int] = None
    radicality: Optional[HoraryRadicality] = None
    reasoning: Optional[str] = None
    verdict: Optional[str] = None


WESTERN_FIELDS: Dict[str, Any] = {
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
