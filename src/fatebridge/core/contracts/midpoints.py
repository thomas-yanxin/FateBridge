"""Output contracts for ephemeris provenance, Earth rotation, and midpoint geometry."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, JsonValue

from fatebridge.core.contracts.base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.common import C04UT1Evidence


class GeometrySource(PartialOutput):
    id: str | None = None
    author: str | None = None
    title: str | None = None
    url: str | None = None
    scope: str | None = None
    sections: list[str] | None = None


class ReferenceAngleGeometry(PartialOutput):
    reference_angle_basis: dict[str, str] | None = None
    physical_reference_geometry_resolved: bool | None = None


class MidpointFactor(PartialOutput):
    coordinate_basis: str | None = None
    angle_definition: dict[str, OpenJsonValue] | None = None
    native_return_flags: int | None = None
    id: str | None = None
    longitude: float | None = None
    kind: str | None = None
    model: str | None = None
    element_name: str | None = None


class MeridianFactorPosition(PartialOutput):
    id: str | None = None
    kind: str | None = None
    model: str | None = None
    status: str | None = None
    right_ascension: float | None = None
    right_ascension_raw_degrees: float | None = None
    declination: float | None = None
    equatorial_horizontal_norm: float | None = None
    input_tropical_longitude: float | None = None
    input_ecliptic_latitude: float | None = None
    longitude_only_control_house: int | None = None
    longitude_only_control_house_position: float | None = None
    house: int | None = None
    house_position: float | None = None
    offset_from_first_cusp_degrees: float | None = None
    distance_to_nearest_cusp_degrees: float | None = None
    latitude_changes_house: bool | None = None


class MidpointAxis(ReferenceAngleGeometry):
    id_a: str | None = None
    id_b: str | None = None
    axis_longitude: float | None = None
    opposite_longitude: float | None = None
    antipodal_inputs: bool | None = None
    dial_90: float | None = None
    dial_45: float | None = None
    self_midpoint: bool | None = None
    rule_id: str | None = None
    contains_hypothetical: bool | None = None


class SensitivePoint(ReferenceAngleGeometry):
    plus: list[str] | None = None
    minus: str | None = None
    occupant: str | None = None
    equation: str | None = None
    longitude: float | None = None
    occupant_longitude: float | None = None
    period_degrees: int | None = None
    signed_orb: float | None = None
    orb: float | None = None
    maximum_orb_degrees: float | None = None
    direct_signed_orb: float | None = None
    direct_orb: float | None = None
    occupancy: str | None = None
    rule_id: str | None = None


class SourceInterpretation(ReferenceAngleGeometry):
    source_application_status: str | None = None
    backend_reading_zh: str | None = None
    claim_id: str | None = None
    factor_longitudes: dict[str, float] | None = None
    contains_hypothetical: bool | None = None
    source_id: str | None = None
    source_section: str | None = None
    source_expression: str | None = None
    basis_expression: str | None = None
    sensitive_point_longitude: float | None = None
    occupant_longitude: float | None = None
    direct_orb_degrees: float | None = None
    maximum_orb_degrees: float | None = None
    symbolic_theme_zh: str | None = None
    reading_zh: str | None = None
    practical_prompt_zh: str | None = None
    claim_type: str | None = None
    rule_id: str | None = None
    birth_time_sampled_status: str | None = None
    factor_layers: dict[str, str] | None = None
    analysis_utc: str | None = None
    solar_arc_degrees: float | None = None


class SymmetryContact(ReferenceAngleGeometry):
    point: str | None = None
    id_a: str | None = None
    id_b: str | None = None
    id_c: str | None = None
    id_d: str | None = None
    equation: str | None = None
    orb: float | None = None
    signed_orb: float | None = None
    axis_offset_degrees: int | float | None = None
    rule_id: str | None = None
    contains_hypothetical: bool | None = None
    sensitive_point: SensitivePoint | None = None
    source_interpretation: SourceInterpretation | None = None


class TwoFactorContact(ReferenceAngleGeometry):
    id_a: str | None = None
    id_b: str | None = None
    equation: str | None = None
    orb: float | None = None
    signed_orb: float | None = None
    factor_offset_degrees: int | None = None
    aspect_degrees: int | None = None
    separation_degrees: float | None = None
    rule_id: str | None = None
    contains_hypothetical: bool | None = None


class MidpointDial(PartialOutput):
    period_degrees: int | float | None = None
    two_factor_contacts: list[TwoFactorContact] | None = None
    three_factor_contacts: list[SymmetryContact] | None = None
    three_factor_returned_count: int | None = None
    three_factor_total_count: int | None = None
    four_factor_contacts: list[SymmetryContact] | None = None
    four_factor_returned_count: int | None = None
    four_factor_total_count: int | None = None


class PhysicalEphemerisFile(PartialOutput):
    id: str | None = None
    slot: int | None = None
    filename: str | None = None
    bytes: int | None = None
    range_time_scale: Literal["TT", "TDB"] | None = None
    start_julian_day_tt: float | None = Field(
        default=None,
        description="Swiss se1 native range start in its TT argument convention; absent for JPL raw headers.",
    )
    end_julian_day_tt: float | None = Field(
        default=None,
        description="Swiss se1 native range end in its TT argument convention; absent for JPL raw headers.",
    )
    start_julian_day_tdb: float | None = Field(
        default=None, description="JPL raw TDB header start; no TDB-to-TT conversion."
    )
    end_julian_day_tdb: float | None = Field(
        default=None, description="JPL raw TDB header end; no TDB-to-TT conversion."
    )
    de_number: int | None = None
    matches_packaged_manifest: bool | None = None


class PhysicalFactorSource(PartialOutput):
    model: str | None = None
    status: str | None = None
    file_ids: list[str] | None = None


class EphemerisTimeScalePolicy(PartialOutput):
    policy_id: str | None = None
    status: str | None = None
    native_version: str | None = None
    binding_version: str | None = None
    native_api_time_scale: str | None = None
    raw_header_time_scale: str | None = None
    tt_tdb_conversion_applied: bool | None = None
    source_documented_maximum_difference_seconds: float | None = None
    source_function: str | None = None
    source_url: str | None = None
    native_source_url: str | None = None
    scope: str | None = None


class PhysicalEphemerisSource(PartialOutput):
    ruleset_id: str | None = None
    by_factor: dict[str, PhysicalFactorSource] | None = None
    files: list[PhysicalEphemerisFile] | None = None
    has_unidentified_sources: bool | None = None
    scope: str | None = None
    atomic_file_read_proven: bool | None = None
    accuracy_certified: bool | None = None
    time_scale_policy: EphemerisTimeScalePolicy | None = None


class ReferenceAngleModel(PartialOutput):
    house_code: str | None = None
    house_flags: int | None = None
    cusp_output_used: bool | None = None
    role: str | None = None
    used_reference_outputs: list[str] | None = None


class MidpointProfile(PartialOutput):
    reference_angle_model: ReferenceAngleModel | None = None
    angle_definition: dict[str, OpenJsonValue] | None = None
    ephemeris_model_scope: str | None = None
    zodiac: str | None = None
    calendar: str | None = None
    time_scale: str | None = None
    orb_degrees: float | None = None
    orb_policy: str | None = None
    coordinate_rounding_before_comparison: bool | None = None
    factor_count: int | None = None
    contact_policy: str | None = None
    hypothetical_model: str | None = None
    aries_point: str | None = None
    node_mode: str | None = None
    seven_planet_view: str | None = None
    sensitive_point_policy: str | None = None
    ephemeris_models: list[str] | None = None
    julian_day_tt: float | None = None
    julian_day_ut1: float | None = None
    julian_day_utc: float | None = None
    time_scale_method: str | None = None
    future_leap_seconds_assumed_unchanged: bool | None = None
    swisseph_version: str | None = None
    physical_ephemeris_source: PhysicalEphemerisSource | None = None


class DialCounts(PartialOutput):
    two_factor: int | None = None
    three_factor: int | None = None
    four_factor: int | None = None


class FactorSpan(PartialOutput):
    status: str | None = None
    backend_convention_span: dict[str, float] | None = None
    unresolved_sample_count: int | None = None
    minimum_offset_from_nominal_degrees: float | None = None
    maximum_offset_from_nominal_degrees: float | None = None
    maximum_adjacent_sample_jump_degrees: float | None = None


class SolarEphemerisReference(PartialOutput):
    author: str | None = None
    source_version: str | None = None
    source_url: str | None = None
    calculation_library: str | None = None
    time_argument: str | None = None
    coefficient_representation: str | None = None
    coefficient_profile: str | None = None


class CompressedFileWindow(PartialOutput):
    slot: int | None = None
    filename: str | None = None
    start_jd_tt: float | None = None
    end_jd_tt: float | None = None
    de_number: int | None = None


class CompressedEndpointRecord(PartialOutput):
    operation: str | None = None
    input_julian_day: float | None = None
    physical_jd_tt: float | None = None
    body_id: int | None = None
    returned_flags: int | None = None
    original_native_state: list[float] | None = None
    selected_native_state: list[float] | None = None
    native_state_changed: bool | None = None
    initial_windows: list[CompressedFileWindow] | None = None
    selected_windows: list[CompressedFileWindow] | None = None
    selection_anchor_jd_tt: list[float] | None = None
    physical_instant_shifted: bool | None = None


class CompressedEndpointPolicy(PartialOutput):
    policy_id: str | None = None
    trigger: str | None = None
    input_instant_shifted: bool | None = None
    native_coordinates_may_be_corrected: bool | None = None
    context_strategy: str | None = None
    native_cache_resets_so_far: int | None = None
    reference_preflight: str | None = None
    calls_corrected_so_far: int | None = None
    native_states_changed_so_far: int | None = None
    records: list[CompressedEndpointRecord] | None = None
    unrecorded_calls_at_record_limit: int | None = None
    source_url: str | None = None
    scope: str | None = None


class NativeCoordinateContext(CompressedEndpointRecord):
    policy_id: str | None = None
    original_target_state_status: str | None = None
    private_native_cache_reset: bool | None = None
    preflight_reference: str | None = None
    scope: str | None = None


class NativeExecutionContext(PartialOutput):
    mechanism: str | None = None
    lifetime: str | None = None
    auxiliary_candidates_checked: int | None = None
    auxiliary_files_present: list[dict[str, JsonValue]] | None = None
    scope: str | None = None
    compressed_file_endpoint_policy: CompressedEndpointPolicy | None = None


class SolarPositionBody(PartialOutput):
    status: str | None = None
    unbent_ray_domain: str | None = None
    reason: str | None = None
    coordinate_backends: dict[str, str] | None = None
    impact_solar_radius_fraction: float | None = None
    target_distance_au: float | None = None
    solar_distance_au: float | None = None
    solar_projection_distance_au: float | None = None
    arithmetic_margin_fraction: float | None = None
    position_interpretation: str | None = None
    observational_accuracy_certified: bool | None = None
    maximum_physical_error_arcseconds: float | None = None


class SolarModelRegularity(PartialOutput):
    profile: str | None = None
    axis_continuity_certified: bool | None = None
    unique_rate_at_mass_knots_certified: bool | None = None
    scope: str | None = None


class ApparentPositionPolicy(PartialOutput):
    method_id: str | None = None
    epoch_jd_tt: float | None = None
    native_version: str | None = None
    binding_version: str | None = None
    solar_deflection_model: str | None = None
    source_url: str | None = None
    source_section: str | None = None
    native_source_url: str | None = None
    native_model_solar_radius_au: float | None = None
    source_model_regularity: SolarModelRegularity | None = None
    coordinate_origin: str | None = None
    geometry_frame: str | None = None
    bodies: dict[str, SolarPositionBody] | None = None
    excluded_factors: dict[str, str] | None = None
    source_contexts: dict[str, PhysicalFactorSource] | None = None
    displayed_native_positions_changed: bool | None = None
    observational_accuracy_certified: bool | None = None
    scope: str | None = None


class LongtermPhaseAlignment(PartialOutput):
    method: str | None = None
    boundary_tt_jd: float | None = None
    native_longterm_variation_retained: bool | None = None
    absolute_accuracy_certified: bool | None = None
    derivative_continuity_certified: bool | None = None
    source_url: str | None = None
    source_section: str | None = None
    attribution: str | None = None


class TerrestrialOrientation(PartialOutput):
    polar_motion_applied: bool | None = None
    celestial_pole_offsets_applied: bool | None = None
    polar_motion_x_radians: float | None = None
    polar_motion_y_radians: float | None = None
    tio_locator_radians: float | None = None
    celestial_pole_offsets_arcseconds: list[float] | None = None
    cio_locator_policy: str | None = None
    origin_policy: str | None = None
    local_frame_policy: str | None = None
    tidal_model_id: str | None = None
    cpo_application_policy: str | None = None
    station_velocity_scope: str | None = None
    vertical_scope: str | None = None


class EarthRotationPolicy(PartialOutput):
    tt_argument_policy: str | None = None
    ut1_reference: C04UT1Evidence | None = None
    terrestrial_orientation: TerrestrialOrientation | None = None
    policy_id: str | None = None
    sidereal_time_model: str | None = None
    implementation: str | None = None
    model_epoch_jd_tt: float | None = None
    model_epoch_jd_ut1: float | None = None
    modern_adoption_window_tt: dict[str, float] | None = None
    native_iers_interval_ut1: dict[str, float] | None = None
    native_interval_role: str | None = None
    celestial_frame_model: str | None = None
    celestial_frame_scope: str | None = None
    source_equatorial_frame_model: str | None = None
    origin_method: str | None = None
    erfa_version: str | None = None
    selection_basis: str | None = None
    longterm_phase_alignment: LongtermPhaseAlignment | None = None
    nutation_model: str | None = None
    other_astronomical_models: str | None = None
    geographic_longitude_policy: str | None = None
    native_event_api_scope: str | None = None
    scope: str | None = None
    measured_eop_applied: bool | None = None
    precision_scope: str | None = None
    source_url: str | None = None
    origin_source_url: str | None = None
    frame_source_url: str | None = None
    native_frame_source_url: str | None = None


class DirectedFactor(PartialOutput):
    coordinate_basis: str | None = None
    angle_definition: dict[str, OpenJsonValue] | None = None
    id: str | None = None
    longitude: float | None = None
    natal_longitude: float | None = None
    kind: str | None = None
    natal_model: str | None = None
    model: str | None = None


class DirectionContact(PartialOutput):
    rule_id: str | None = None
    equation: str | None = None
    orb: float | None = None
    signed_orb: float | None = None
    contains_hypothetical: bool | None = None
    zero_arc_identity: bool | None = None
    point: str | None = None
    point_layer: str | None = None
    axis_layer: str | None = None
    id_a: str | None = None
    id_b: str | None = None
    id_c: str | None = None
    id_d: str | None = None
    layer_a: str | None = None
    layer_b: str | None = None
    layer_c: str | None = None
    layer_d: str | None = None


class DirectionDial(PartialOutput):
    period_degrees: int | None = None
    two_factor_contacts: list[DirectionContact] | None = None
    three_factor_contacts: list[DirectionContact] | None = None
    three_factor_returned_count: int | None = None
    three_factor_total_count: int | None = None
    four_factor_contacts: list[DirectionContact] | None = None
    four_factor_returned_count: int | None = None
    four_factor_total_count: int | None = None


class SunObservation(PartialOutput):
    index: int | None = None
    julian_day_tt: float | None = None
    longitude: float | None = None
    model: str | None = None
    status: str | None = None
    file_ids: list[str] | None = None


class SunEphemerisBatch(PartialOutput):
    ruleset_id: str | None = None
    observations: list[SunObservation] | None = None
    files: list[PhysicalEphemerisFile] | None = None
    query_count: int | None = None
    configuration_locked: bool | None = None
    equal_tt_epochs_reused: bool | None = None
    has_unidentified_sources: bool | None = None
    scope: str | None = None
    atomic_file_read_proven: bool | None = None
    accuracy_certified: bool | None = None


class PrintedTimeOperation(PartialOutput):
    id: str | None = None
    section: str | None = None
    computed_time_seconds: int | None = None
    printed_time_seconds: int | None = None
    printed_minus_computed_time_seconds: int | None = None
    arithmetic_matches_print: bool | None = None


class ProgressionKeySourceComparison(PartialOutput):
    status: str | None = None
    ruleset_id: str | None = None
    author: str | None = None
    version: str | None = None
    selected_key_id: str | None = None
    selected_key_from_compared_source: bool | None = None
    computed_for_current_chart: bool | None = None
    comparison_unit: str | None = None
    source: GeometrySource | None = None
    operations: list[PrintedTimeOperation] | None = None
    printed_arithmetic_consistent: bool | None = None
    inconsistent_operation_ids: list[str] | None = None
    clock_label_status: str | None = None
    residuals_applied_as_corrections: bool | None = None
    original_progression_time_key_accepted: bool | None = None
    full_original_rulebook_accepted: bool | None = None
    scope: str | None = None


class SolarArcProfile(PartialOutput):
    reference_angle_model: ReferenceAngleModel | None = None
    angle_definition: dict[str, OpenJsonValue] | None = None
    analysis_utc: str | None = None
    birth_effective_utc: str | None = None
    elapsed_calendar_days: float | None = None
    year_days: float | None = None
    key_years: float | None = None
    birth_julian_day_tt: float | None = None
    progressed_julian_day_tt: float | None = None
    julian_day_resolution_seconds: float | None = None
    natal_tropical_sun: float | None = None
    progressed_tropical_sun: float | None = None
    solar_arc_degrees: float | None = None
    one_degree_per_year_degrees: float | None = None
    difference_from_one_degree_per_year: float | None = None
    sun_ephemeris_models: list[str] | None = None
    sun_observation_indices: list[int] | None = None
    sun_ephemeris_source: SunEphemerisBatch | None = None
    key_policy: str | None = None
    key_source_comparison: ProgressionKeySourceComparison | None = None
    orb_degrees: float | None = None
    orb_policy: str | None = None
    display_frame: str | None = None
    directed_factors_are_observations: bool | None = None


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
    factor_spans: dict[str, FactorSpan] | None = None
    samples: list[TimeSample] | None = None
    limitations: list[str] | None = None
    source_pattern: PatternSensitivity | None = None
    sector_assignments: list[SectorSensitivity] | None = None


class SourceTableCorner(PartialOutput):
    row: int | None = None
    age_years: int | None = None
    raw_cell: str | None = None
    arcminutes: int | None = None
    weight_fraction: list[int] | None = None


class SourceTableProbe(PartialOutput):
    status: str | None = None
    ruleset_id: str | None = None
    day_offset_fraction: list[int] | None = None
    age_years_fraction: list[int] | None = None
    corners: list[SourceTableCorner] | None = None
    arcminutes: float | None = None
    arcminutes_fraction: list[int] | None = None
    full_original_method_accepted: bool | None = None
    scope: str | None = None


class SourceTableRow(PartialOutput):
    row: int | None = None
    printed_date: str | None = None
    common_year_day_offset: int | None = None
    raw_age_cells: list[str] | None = None
    raw_until_january_zero_arcminutes: int | None = None
    normalized_arcminutes: list[int | None] | None = None
    unresolved_age_columns: list[int] | None = None


class SourceTableCoverage(PartialOutput):
    date_rows: int | None = None
    raw_age_cells: int | None = None
    resolved_age_cells: int | None = None
    unresolved_age_cells: int | None = None
    last_column_cells: int | None = None
    all_printed_raw_cells_retained: bool | None = None
    all_degrees_resolved: bool | None = None


class SourceTableWorkedExample(PartialOutput):
    birth_date_label: str | None = None
    target_date_label: str | None = None
    clock_or_timezone_given: bool | None = None
    printed_components_arcminutes: list[int] | None = None
    literal_components_sum_arcminutes: int | None = None
    printed_total_arcminutes: int | None = None
    literal_arithmetic_matches_print: bool | None = None
    exact_bilinear_base: SourceTableProbe | None = None
    exact_fifty_year_arcminutes: float | None = None
    exact_sixty_year_arcminutes: float | None = None
    exact_last_column_arcminutes: float | None = None
    hypothetical_unrounded_partial_year_arcminutes: float | None = None
    hypothetical_unrounded_total_arcminutes: float | None = None
    hypothetical_total_fraction: list[int] | None = None
    printed_minus_hypothetical_total_arcminutes: float | None = None
    hypothetical_unrounded_policy_adopted_as_original: bool | None = None
    source_rounding_policy_fully_specified: bool | None = None


class Witte1925SourceTable(PartialOutput):
    status: str | None = None
    ruleset_id: str | None = None
    author: str | None = None
    version: str | None = None
    computed_for_current_chart: bool | None = None
    source: GeometrySource | None = None
    coverage: SourceTableCoverage | None = None
    age_columns_years: list[int] | None = None
    rows: list[SourceTableRow] | None = None
    worked_example: SourceTableWorkedExample | None = None
    limitations: list[str] | None = None
    full_original_method_accepted: bool | None = None


class MixedPairContact(ReferenceAngleGeometry):
    rule_id: str | None = None
    id_a: str | None = None
    id_b: str | None = None
    id_c: str | None = None
    id_d: str | None = None
    equation: str | None = None
    signed_orb: float | None = None
    orb: float | None = None
    midpoint_arc_coefficient: float | None = None
    arc_invariant: bool | None = None
    factor_layer_assignments: list[dict[str, str]] | None = None
    represented_layer_assignment_count: int | None = None
    contains_hypothetical: bool | None = None
    zero_arc_groups_coincide: bool | None = None


class MixedPairDial(PartialOutput):
    period_degrees: int | None = None
    arc_dependent_contacts: list[MixedPairContact] | None = None
    arc_dependent_returned_count: int | None = None
    arc_dependent_total_count: int | None = None
    arc_invariant_contacts: list[MixedPairContact] | None = None
    arc_invariant_returned_count: int | None = None
    arc_invariant_total_count: int | None = None


class MixedPairProfile(PartialOutput):
    solar_arc_degrees: float | None = None
    orb_degrees: float | None = None
    factor_count: int | None = None
    four_distinct_factor_names_required: bool | None = None
    pair_partitions_tested_per_dial: int | None = None
    residual_groups_tested_per_dial: int | None = None
    layer_assignments_represented_per_dial: int | None = None
    coefficient_formula: str | None = None
    arc_invariant_means: str | None = None
    grouping_policy: str | None = None
    birth_time_contact_sensitivity: str | None = None


class MixedSensitivitySample(PartialOutput):
    sample_index: int | None = None
    offset_seconds: float | None = None
    recorded_utc: str | None = None
    effective_utc: str | None = None
    julian_day_tt: float | None = None
    factor_longitudes: dict[str, float] | None = None
    solar_arc_status: str | None = None
    solar_arc_degrees: float | None = None
    reason_code: str | None = None
    unresolved_reference_names: list[str] | None = None
    native_sample_reference: str | None = None
    solar_sample_reference: str | None = None


class MixedSensitivityContact(PartialOutput):
    id_a: str | None = None
    id_b: str | None = None
    id_c: str | None = None
    id_d: str | None = None
    midpoint_arc_coefficient: float | None = None
    arc_invariant: bool | None = None
    arc_required_for_relative_condition: bool | None = None
    factor_layer_assignments: list[dict[str, str]] | None = None
    nominal_backend_condition: bool | None = None
    nominal_condition: bool | None = None
    sampled_status: str | None = None
    assessment_complete: bool | None = None
    present_sample_indices: list[int] | None = None
    known_absent_sample_count: int | None = None
    unknown_sample_indices: list[int] | None = None
    backend_hit_sample_indices: list[int] | None = None
    backend_evaluable_sample_count: int | None = None
    minimum_known_sampled_orb_degrees: float | None = None
    maximum_known_sampled_orb_degrees: float | None = None


class MixedSensitivitySummary(PartialOutput):
    evaluated_relation_groups: int | None = None
    listed_observed_or_nominal_contact_groups: int | None = None
    all_group_status_counts: dict[str, int] | None = None
    unlisted_no_observed_hit_counts: dict[str, int] | None = None


class MixedSensitivityDial(PartialOutput):
    period_degrees: int | None = None
    contacts: list[MixedSensitivityContact] | None = None
    all_group_status_counts: dict[str, int] | None = None
    unlisted_no_observed_hit_counts: dict[str, int] | None = None


class MixedPairSensitivity(PartialOutput):
    ruleset_id: str | None = None
    status: str | None = None
    uncertainty_minutes: float | None = None
    continuous_interval_proven: bool | None = None
    summary: dict[str, MixedSensitivitySummary] | None = None
    sample_count: int | None = None
    computed_arc_sample_count: int | None = None
    unavailable_arc_sample_count: int | None = None
    scope: str | None = None
    nominal_sample_index: int | None = None
    nominal_unresolved_reference_names: list[str] | None = None
    exact_lattice_denominator_power: int | None = None
    samples: list[MixedSensitivitySample] | None = None
    dials: dict[str, MixedSensitivityDial] | None = None
    ledger_policy: str | None = None
    arc_policy: str | None = None
    interval: dict[str, OpenJsonValue] | None = None


class MixedPairGeometry(PartialOutput):
    status: str | None = None
    reason: str | None = None
    ruleset_id: str | None = None
    author: str | None = None
    version: str | None = None
    profile: MixedPairProfile | None = None
    dials: dict[str, MixedPairDial] | None = None
    contact_counts: dict[str, dict[str, int]] | None = None
    unique_relation_groups_across_dials: int | None = None
    birth_time_sensitivity: MixedPairSensitivity | None = None
    sources: list[GeometrySource] | None = None
    limitations: list[str] | None = None
    full_original_method_accepted: bool | None = None


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
    limitations: list[str] | None = None
    original_text_conformance: str | None = None


class SolarArcAnalysis(PartialOutput):
    status: str | None = None
    reason: str | None = None
    ruleset_id: str | None = None
    version: str | None = None
    author: str | None = None
    profile: SolarArcProfile | None = None
    directed_factors: list[DirectedFactor] | None = None
    dials: dict[str, DirectionDial] | None = None
    mixed_pair_geometry: MixedPairGeometry | None = None
    contact_counts: dict[str, dict[str, int]] | None = None
    interpretations: list[SourceInterpretation] | None = None
    birth_time_sensitivity: SpecialtyTimeSensitivity | None = None
    daily_meridian: DayMeridianAnalysis | None = None
    original_table_1925: Witte1925SourceTable | None = None
    sources: list[GeometrySource] | None = None
    limitations: list[str] | None = None
    original_text_conformance: str | None = None


class MeridianHouseCusp(PartialOutput):
    house: int | None = None
    longitude: float | None = None
    tropical_longitude: float | None = None
    right_ascension: float | None = None


class MeridianHouseProfile(PartialOutput):
    house_code: str | None = None
    swisseph_version: str | None = None
    house_flags: int | None = None
    obliquity_return_flags: int | None = None
    obliquity_model: str | None = None
    geographic_latitude: float | None = None
    geographic_longitude: float | None = None
    construction: str | None = None
    zodiac: str | None = None
    right_ascension_frame: str | None = None
    julian_day_ut1: float | None = None
    shared_julian_day_tt: float | None = None
    native_angle_julian_day_tt: float | None = None
    native_angle_minus_shared_tt_seconds: float | None = None
    angle_time_policy: str | None = None
    armc: float | None = None
    true_obliquity: float | None = None
    source_ecliptic_longitude_origin: float | None = None
    ayanamsha_apparent: float | None = None
    first_cusp_definition: str | None = None
    tenth_cusp_definition: str | None = None
    physical_ascendant: float | None = None
    retained_ascendant_definition_reference: str | None = None
    physical_midheaven: float | None = None
    first_cusp_replaces_physical_ascendant: bool | None = None
    base_chart_houses_replaced: bool | None = None
    geographic_pole_meridian_convention: bool | None = None


class MeridianCuspSpan(FactorSpan):
    house: int | None = None


class MeridianFactorStability(PartialOutput):
    id: str | None = None
    nominal_house: int | None = None
    sampled_houses: list[int] | None = None
    unresolved_sample_count: int | None = None
    sampled_status: str | None = None


class MeridianHouseSensitivity(PartialOutput):
    recorded_physical_grid: RecordedPhysicalGrid | None = None
    status: str | None = None
    uncertainty_minutes: float | None = None
    continuous_interval_proven: bool | None = None
    sample_reference: str | None = None
    sample_count: int | None = None
    maximum_recorded_sample_gap_seconds: float | None = None
    cusp_spans: list[MeridianCuspSpan] | None = None
    factor_placement_summary: list[MeridianFactorStability] | None = None


class MeridianFactorPlacement(PartialOutput):
    status: str | None = None
    ruleset_id: str | None = None
    author: str | None = None
    version: str | None = None
    factor_count: int | None = None
    physical_factor_count: int | None = None
    hypothetical_factor_count: int | None = None
    node_factor_count: int | None = None
    factors: list[MeridianFactorPosition] | None = None
    factor_ayanamsha_apparent: float | None = None
    factor_julian_day_tt: float | None = None
    projection_obliquity_julian_day_tt: float | None = None
    coordinate_policy: str | None = None
    sector_policy: str | None = None
    pole_horizontal_norm_threshold: float | None = None
    reference_points_included: bool | None = None
    source_example_reconciliation: str | None = None
    scope: str | None = None
    sources: list[GeometrySource] | None = None
    full_original_method_accepted: bool | None = None


class MeridianHouseAnalysis(PartialOutput):
    status: str | None = None
    reason: str | None = None
    ruleset_id: str | None = None
    author: str | None = None
    version: str | None = None
    profile: MeridianHouseProfile | None = None
    cusps: list[MeridianHouseCusp] | None = None
    factor_placement: MeridianFactorPlacement | None = None
    birth_time_sensitivity: MeridianHouseSensitivity | None = None
    sources: list[GeometrySource] | None = None
    limitations: list[str] | None = None
    original_text_conformance: str | None = None


class ComparativePointSystem(PartialOutput):
    longitudes: dict[str, float | None] | None = None
    backend_longitudes: dict[str, float] | None = None
    input_reference_geometry_resolved: bool | None = None
    reference_angle_basis: dict[str, str] | None = None
    defined_anchor_identity: bool | None = None
    unique_point_count: int | None = None
    backend_unique_point_count: int | None = None


class ComparativeFrameSummary(PartialOutput):
    anchor_factor: str | None = None
    target_tropical_longitude: float | None = None
    target_display_longitude: float | None = None
    rotation_degrees: float | None = None
    backend_rotation_degrees: float | None = None
    anchor_input_reference_resolved: bool | None = None
    anchor_reference_angle_basis: dict[str, str] | None = None
    resolved_factor_system_count: int | None = None
    unresolved_factor_system_count: int | None = None


class ComparativeFrame(ComparativeFrameSummary):
    factor_systems: dict[str, ComparativePointSystem] | None = None


class ComparativeProfile(PartialOutput):
    native_factor_count: int | None = None
    constructed_frame_count: int | None = None
    native_aries_point_longitude: float | None = None
    display_zodiac: str | None = None
    cardinal_policy: str | None = None
    rotated_aries_factor_policy: str | None = None
    rotation_formula: str | None = None
    four_point_formula: str | None = None
    source_natal_table_factor_count: int | None = None
    native_factor_reference: str | None = None
    exact_coordinate_policy: str | None = None
    node_anchor_policy: str | None = None
    meridian_anchor_policy: str | None = None
    coordinates_are_new_observations: bool | None = None


class ComparativeSample(PartialOutput):
    sample_index: int | None = None
    offset_seconds: float | None = None
    recorded_utc: str | None = None
    effective_utc: str | None = None
    julian_day_tt: float | None = None
    factor_longitudes: dict[str, float] | None = None
    angle_definition: dict[str, OpenJsonValue] | None = None
    frame_summary: dict[str, ComparativeFrameSummary] | None = None
    point_systems: dict[str, dict[str, ComparativePointSystem]] | None = None
    native_sample_reference: str | None = None


class ComparativeOffsetSpan(PartialOutput):
    minimum: float | None = None
    maximum: float | None = None


class ComparativePointSpan(PartialOutput):
    nominal_input_reference_geometry_resolved: bool | None = None
    resolved_sample_count: int | None = None
    unresolved_sample_count: int | None = None
    unresolved_sample_indices: list[int] | None = None
    known_sampled_signed_offsets_from_nominal: (
        dict[str, ComparativeOffsetSpan] | None
    ) = None
    backend_sampled_signed_offsets_from_nominal: (
        dict[str, ComparativeOffsetSpan] | None
    ) = None


class ComparativeSensitivitySummary(PartialOutput):
    samples_with_unresolved_reference: int | None = None
    point_systems_per_sample: int | None = None
    all_confirmed_samples_retained: bool | None = None


class ComparativeSensitivity(PartialOutput):
    status: str | None = None
    uncertainty_minutes: float | None = None
    sample_count: int | None = None
    nominal_sample_index: int | None = None
    continuous_interval_proven: bool | None = None
    summary: ComparativeSensitivitySummary | None = None
    point_spans: dict[str, dict[str, ComparativePointSpan]] | None = None
    samples: list[ComparativeSample] | None = None
    interval: dict[str, OpenJsonValue] | None = None
    scope: str | None = None


class ComparativeGeometry(PartialOutput):
    status: str | None = None
    reason: str | None = None
    ruleset_id: str | None = None
    author: str | None = None
    version: str | None = None
    profile: ComparativeProfile | None = None
    radix_systems: dict[str, ComparativePointSystem] | None = None
    frames: dict[str, ComparativeFrame] | None = None
    frame_summary: dict[str, ComparativeFrameSummary] | None = None
    birth_time_sensitivity: ComparativeSensitivity | None = None
    sources: list[GeometrySource] | None = None
    original_text_conformance: str | None = None
    limitations: list[str] | None = None


class MidpointAnalysis(PartialOutput):
    status: str | None = None
    reason: str | None = None
    ruleset_id: str | None = None
    version: str | None = None
    profile: MidpointProfile | None = None
    factors: list[MidpointFactor] | None = None
    midpoint_axes: list[MidpointAxis] | None = None
    dials: dict[str, MidpointDial] | None = None
    contact_counts: dict[str, DialCounts] | None = None
    unique_two_factor_pair_count: int | None = None
    interpretations: list[SourceInterpretation] | None = None
    birth_time_sensitivity: SpecialtyTimeSensitivity | None = None
    solar_arc_analysis: SolarArcAnalysis | None = None
    meridian_houses: MeridianHouseAnalysis | None = None
    comparative_geometry: ComparativeGeometry | None = None
    reading_guide: dict[str, str] | None = None
    sources: list[GeometrySource] | None = None
    limitations: list[str] | None = None
    original_text_conformance: str | None = None


class SectorProfile(PartialOutput):
    status: str | None = None
    backend_convention_anchor_longitude: float | None = None
    backend_convention_sectors: list[dict[str, OpenJsonValue]] | None = None
    angle_definition: dict[str, OpenJsonValue] | None = None
    ruleset_id: str | None = None
    author: str | None = None
    version: str | None = None
    anchor: str | None = None
    anchor_longitude: float | None = None
    sector_count: int | None = None
    width_degrees: float | None = None
    interval_convention: str | None = None
    boundary_display: str | None = None
    coordinate_system: str | None = None
    astronomical_constellations: bool | None = None
    original_text_conformance: str | None = None
    sources: list[GeometrySource] | None = None


class SectorEvidence(PartialOutput):
    assignment_status: str | None = None
    backend_convention_sector: int | None = None
    angle_definition: dict[str, OpenJsonValue] | None = None
    longitude_unrounded: float | None = None
    ascendant_unrounded: float | None = None
    interval_convention: str | None = None
    rule_id: str | None = None
    birth_time_uncertainty: str | None = None
