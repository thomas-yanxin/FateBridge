"""Western lifespan techniques and period outputs."""

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_civil_time import CivilPointEvidence
from fatebridge.core.contracts.output_clock_labels import (
    WesternUTCRepresentation as WesternUTCRepresentation,
)
from fatebridge.core.contracts.output_midpoint_geometry import PhysicalEphemerisSource
from fatebridge.core.contracts.output_western_geometry import (
    AspectHit,
    WesternCalculationBasis,
    WesternPoint,
)
from fatebridge.core.contracts.output_western_timing import (
    ProgressionCalculationOptions,
    ProgressionClockOptions,
    SystemOutput,
)


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


class PlanetaryArc(SystemOutput):
    progressed_datetime: str | None = None
    progression_options: ProgressionCalculationOptions | None = None
    arc_degrees: float | None = None
    arc_source: str | None = None
    arc_source_label: str | None = None
    orb: float | None = None
    positions: dict[str, WesternPoint] | None = None
    hits: list[AspectHit] | None = None


class PersianHit(PartialOutput):
    age: float | None = None
    aspect: int | None = None
    date: str | None = None
    promittor: str | None = None
    promittor_label: str | None = None
    significator: str | None = None


class PersianDirected(SystemOutput):
    hit_count: int | None = None
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
    contacts: list[AgePointContact] | None = None


class VedicProgression(SystemOutput):
    progressed_datetime: str | None = None
    calculation_options: ProgressionCalculationOptions | None = None
    orb: float | None = None
    zodiac: str | None = None
    positions: dict[str, WesternPoint] | None = None
    hits: list[AspectHit] | None = None


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
