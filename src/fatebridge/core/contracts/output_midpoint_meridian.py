"""Day-meridian geometry and sensitivity contracts."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_midpoint_directions import SunEphemerisBatch
from fatebridge.core.contracts.output_midpoint_geometry import (
    FactorSpan,
    GeometryRuleTrace,
    GeometrySource,
    ReferenceAngleGeometry,
)
from fatebridge.core.contracts.output_midpoint_sensitivity import RecordedPhysicalGrid


class DayMeridianBackendCoordinates(PartialOutput):
    natal_upper_meridian_longitude: float | None = None
    natal_lower_meridian_longitude: float | None = None
    solar_arc_midheaven_longitude: float | None = None
    upper_meridian_longitude: float | None = None
    lower_meridian_longitude: float | None = None


class DayMeridianCoordinates(ReferenceAngleGeometry):
    backend_convention: DayMeridianBackendCoordinates | None = None
    natal_upper_meridian_longitude: float | None = None
    natal_lower_meridian_longitude: float | None = None
    natal_tropical_sun: float | None = None
    target_tropical_sun: float | None = None
    solar_arc_degrees: float | None = None
    solar_arc_midheaven_longitude: float | None = None
    transit_sun_displacement_degrees: float | None = None
    upper_meridian_longitude: float | None = None
    lower_meridian_longitude: float | None = None


class DayMeridianProfile(DayMeridianCoordinates):
    angle_definition: dict[str, OpenJsonValue] | None = None
    analysis_utc: str | None = None
    target_julian_day_tt: float | None = None
    target_time_scale_method: str | None = None
    future_leap_seconds_assumed_unchanged: bool | None = None
    target_sun_ephemeris_model: str | None = None
    target_sun_observation_index: int | None = None
    sun_ephemeris_source: SunEphemerisBatch | None = None
    source_formula: str | None = None
    year_key_policy: str | None = None
    display_frame: str | None = None
    meridians_are_observations: bool | None = None


class DayMeridianSample(DayMeridianCoordinates):
    angle_definition: dict[str, OpenJsonValue] | None = None
    julian_day_tt: float | None = None
    progressed_julian_day_tt: float | None = None
    sun_observation_indices: list[int] | None = None
    status: str | None = None
    reason_code: str | None = None
    key_years: float | None = None
    supported_key_years: list[float] | None = None
    offset_seconds: float | None = None
    recorded_utc: str | None = None
    effective_utc: str | None = None


class DayMeridianSensitivity(PartialOutput):
    recorded_physical_grid: RecordedPhysicalGrid | None = None
    resolved_reference_sample_count: int | None = None
    unresolved_reference_sample_count: int | None = None
    unresolved_reference_sample_indices: list[int] | None = None
    computed_sample_count: int | None = None
    unavailable_sample_count: int | None = None
    sample_scope_policy: str | None = None
    factor_spans_scope: str | None = None
    status: str | None = None
    uncertainty_minutes: float | None = None
    continuous_interval_proven: bool | None = None
    scope: str | None = None
    recorded_interval_start_utc: str | None = None
    recorded_interval_end_utc: str | None = None
    maximum_recorded_sample_gap_seconds: float | None = None
    represented_radius_seconds: float | None = None
    clock_policy: str | None = None
    input_clock_basis: str | None = None
    recorded_interval_start_clock: str | None = None
    recorded_interval_end_clock: str | None = None
    requested_clock_radius_seconds: float | None = None
    sample_count: int | None = None
    factor_spans: dict[str, FactorSpan] | None = None
    samples: list[DayMeridianSample] | None = None


class DayMeridianSourceComparison(PartialOutput):
    status: str | None = None
    selected_construction: str | None = None
    compared_construction: str | None = None
    compared_source_id: str | None = None
    computed_for_current_chart: bool | None = None
    scope: str | None = None
    explanation: str | None = None
    historical_example_difference_arcminutes: int | None = None
    separate_printed_sensitive_point_residual_arcminutes: int | None = None
    difference_is_universal_correction: bool | None = None
    original_variants_fully_reconciled: bool | None = None
    original_progression_time_key_accepted: bool | None = None


class DayMeridianInputCoherence(PartialOutput):
    status: str | None = None
    birth_julian_day_tt: float | None = None
    target_julian_day_tt: float | None = None
    sample_count: int | None = None
    nominal_sample_index: int | None = None
    scope: str | None = None


class DayMeridianAnalysis(PartialOutput):
    input_coherence: DayMeridianInputCoherence | None = None
    status: str | None = None
    reason: str | None = None
    ruleset_id: str | None = None
    author: str | None = None
    version: str | None = None
    profile: DayMeridianProfile | None = None
    birth_time_sensitivity: DayMeridianSensitivity | None = None
    sources: list[GeometrySource] | None = None
    source_comparison: DayMeridianSourceComparison | None = None
    rule_trace: list[GeometryRuleTrace] | None = None
    limitations: list[str] | None = None
    original_text_conformance: str | None = None
    real_world_efficacy: str | None = None
