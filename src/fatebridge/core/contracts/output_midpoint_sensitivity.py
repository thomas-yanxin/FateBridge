"""Midpoint pattern and sector sensitivity evidence."""

from pydantic import Field

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_midpoint_geometry import (
    FactorSpan,
    FictitiousElementSource,
    MeridianFactorPosition,
    PhysicalEphemerisSource,
    ReferenceAngleModel,
)


class PatternBackendSample(PartialOutput):
    directed_midheaven_longitude: float | None = None
    source_direct_orb_degrees: float | None = None
    source_condition_met: bool | None = None


class RecordedPhysicalGrid(PartialOutput):
    nominal_sample_index: int | None = None
    radius_si_seconds: float | None = None
    maximum_gap_si_seconds: float | None = None


class SampleSolarRebase(PartialOutput):
    nominal_utc_origin: str | None = None
    shift_seconds: float | None = None
    sun_apparent_ra_degrees: float | None = None
    greenwich_apparent_sidereal_degrees: float | None = None
    solar_ephemeris_model: str | None = None
    utc_rule_state: str | None = None


class PhysicalSampleTiming(PartialOutput):
    recorded_tt_jd_exact: str | None = Field(
        default=None,
        description="Exact rational TT Julian day, encoded as an integer or fraction.",
    )
    recorded_ut1_jd_exact: str | None = None
    effective_tt_jd_exact: str | None = None
    effective_ut1_jd_exact: str | None = None
    recorded_label_status: str | None = None
    effective_label_status: str | None = None
    solar_rebase: SampleSolarRebase | None = None


class TimeSample(PartialOutput):
    physical_timing: PhysicalSampleTiming | None = None
    source_reference_geometry_resolved: bool | None = None
    source_reference_angle_basis: dict[str, str] | None = None
    backend_convention: PatternBackendSample | None = None
    reference_angle_model: ReferenceAngleModel | None = None
    angle_definition: dict[str, OpenJsonValue] | None = None
    status: str | None = None
    reason_code: str | None = None
    key_years: float | None = None
    supported_key_years: list[float] | None = None
    meridian_house_cusps: list[float] | None = None
    meridian_armc: float | None = None
    meridian_obliquity: float | None = None
    meridian_source_ecliptic_longitude_origin: float | None = Field(
        default=None,
        description="Add this signed offset in degrees to the cusp longitude in the local intersection frame, then subtract the sample's apparent ayanamsha for the displayed longitude.",
    )
    meridian_angle_julian_day_tt: float | None = None
    meridian_ayanamsha: float | None = None
    meridian_factor_positions: list[MeridianFactorPosition] | None = None
    sun_observation_indices: list[int] | None = None
    sun_ephemeris_models: list[str] | None = None
    physical_source_index: int | None = None
    offset_seconds: float | None = None
    recorded_utc: str | None = None
    effective_utc: str | None = None
    julian_day_tt: float | None = None
    julian_day_ut1: float | None = None
    time_scale_method: str | None = None
    future_leap_seconds_assumed_unchanged: bool | None = None
    factor_longitudes: dict[str, float] | None = None
    progressed_julian_day_tt: float | None = None
    solar_arc_degrees: float | None = None
    directed_midheaven_longitude: float | None = None
    source_direct_orb_degrees: float | None = None
    source_condition_met: bool | None = None


class PatternBackendSummary(PartialOutput):
    evaluable_sample_count: int | None = None
    present_sample_count: int | None = None
    absent_sample_count: int | None = None
    condition_by_sample: list[bool | None] | None = None
    minimum_sampled_direct_orb_degrees: float | None = None
    maximum_sampled_direct_orb_degrees: float | None = None
    scope: str | None = None


class PatternSensitivity(PartialOutput):
    resolved_condition_sample_count: int | None = None
    unresolved_reference_sample_count: int | None = None
    unresolved_reference_sample_indices: list[int] | None = None
    condition_by_sample: list[bool | None] | None = None
    backend_convention: PatternBackendSummary | None = None
    computed_sample_count: int | None = None
    unavailable_sample_count: int | None = None
    orb_range_scope: str | None = None
    source_id: str | None = None
    basis_expression: str | None = None
    maximum_direct_orb_degrees: float | None = None
    sampled_status: str | None = None
    present_sample_count: int | None = None
    absent_sample_count: int | None = None
    minimum_sampled_direct_orb_degrees: float | None = None
    maximum_sampled_direct_orb_degrees: float | None = None


class SectorSensitivity(PartialOutput):
    computed_sample_count: int | None = None
    unresolved_sample_count: int | None = None
    id: str | None = None
    nominal_sector: int | None = None
    observed_sectors: list[int] | None = None
    sampled_status: str | None = None
    sector_by_sample: list[int | None] | None = None


class SpecialtyTimeSensitivity(PartialOutput):
    recorded_physical_grid: RecordedPhysicalGrid | None = None
    unresolved_reference_sample_count: int | None = None
    computed_sample_count: int | None = None
    unavailable_sample_count: int | None = None
    sample_scope_policy: str | None = None
    ephemeris_model_scope: str | None = None
    ruleset_id: str | None = None
    author: str | None = None
    status: str | None = None
    reason: str | None = None
    uncertainty_minutes: float | None = None
    scope: str | None = None
    continuous_interval_proven: bool | None = None
    sample_count: int | None = None
    maximum_recorded_sample_gap_seconds: float | None = None
    represented_radius_seconds: float | None = None
    datetime_resolution: str | None = None
    recorded_interval_start_utc: str | None = None
    recorded_interval_end_utc: str | None = None
    clock_policy: str | None = None
    input_clock_basis: str | None = None
    recorded_interval_start_clock: str | None = None
    recorded_interval_end_clock: str | None = None
    requested_clock_radius_seconds: float | None = None
    zodiac: str | None = None
    ephemeris_models: list[str] | None = None
    physical_ephemeris_sources: list[PhysicalEphemerisSource] | None = None
    physical_ephemeris_models_consistent: bool | None = None
    factor_scope: str | None = None
    factor_count: int | None = None
    hypothetical_element_source: FictitiousElementSource | None = None
    factor_spans: dict[str, FactorSpan] | None = None
    samples: list[TimeSample] | None = None
    limitations: list[str] | None = None
    source_pattern: PatternSensitivity | None = None
    sector_assignments: list[SectorSensitivity] | None = None
