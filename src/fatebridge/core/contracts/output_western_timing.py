"""Western progressions and time-lord outputs."""

from pydantic import Field

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_western_geometry import (
    AspectHit,
    Location,
    PrimaryDirections,
    ReturnSolver,
    WesternCalculationBasis,
    WesternPoint,
)


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
    sublevel: list["DecennialPeriod"] | None = None


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


class SystemOutput(PartialOutput):
    system: str | None = None
    system_label: str | None = None
