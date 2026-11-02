"""Projection-compatible public contracts for specialized chart geometry."""

from typing import Any, Dict, List, Optional

from pydantic import Field

from fatebridge.core.output_base import PartialOutput


class GeometrySource(PartialOutput):
    id: Optional[str] = None
    author: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    scope: Optional[str] = None
    sections: Optional[List[str]] = None
    source_sha256: Optional[str] = None


class ReferenceAngleGeometry(PartialOutput):
    reference_angle_basis: Optional[Dict[str, str]] = None
    physical_reference_geometry_resolved: Optional[bool] = None


class MidpointFactor(PartialOutput):
    coordinate_basis: Optional[str] = None
    angle_definition: Optional[Dict[str, Any]] = None
    native_return_flags: Optional[int] = None
    id: Optional[str] = None
    longitude: Optional[float] = None
    kind: Optional[str] = None
    model: Optional[str] = None
    element_name: Optional[str] = None


class MeridianFactorPosition(PartialOutput):
    id: Optional[str] = None
    kind: Optional[str] = None
    model: Optional[str] = None
    status: Optional[str] = None
    right_ascension: Optional[float] = None
    right_ascension_raw_degrees: Optional[float] = None
    declination: Optional[float] = None
    equatorial_horizontal_norm: Optional[float] = None
    input_tropical_longitude: Optional[float] = None
    input_ecliptic_latitude: Optional[float] = None
    longitude_only_control_house: Optional[int] = None
    longitude_only_control_house_position: Optional[float] = None
    house: Optional[int] = None
    house_position: Optional[float] = None
    offset_from_first_cusp_degrees: Optional[float] = None
    distance_to_nearest_cusp_degrees: Optional[float] = None
    latitude_changes_house: Optional[bool] = None


class MidpointAxis(ReferenceAngleGeometry):
    id_a: Optional[str] = None
    id_b: Optional[str] = None
    axis_longitude: Optional[float] = None
    opposite_longitude: Optional[float] = None
    antipodal_inputs: Optional[bool] = None
    dial_90: Optional[float] = None
    dial_45: Optional[float] = None
    self_midpoint: Optional[bool] = None
    rule_id: Optional[str] = None
    contains_hypothetical: Optional[bool] = None


class SensitivePoint(ReferenceAngleGeometry):
    plus: Optional[List[str]] = None
    minus: Optional[str] = None
    occupant: Optional[str] = None
    equation: Optional[str] = None
    longitude: Optional[float] = None
    occupant_longitude: Optional[float] = None
    period_degrees: Optional[int] = None
    signed_orb: Optional[float] = None
    orb: Optional[float] = None
    maximum_orb_degrees: Optional[float] = None
    direct_signed_orb: Optional[float] = None
    direct_orb: Optional[float] = None
    occupancy: Optional[str] = None
    rule_id: Optional[str] = None


class SourceInterpretation(ReferenceAngleGeometry):
    source_application_status: Optional[str] = None
    backend_reading_zh: Optional[str] = None
    claim_id: Optional[str] = None
    factor_longitudes: Optional[Dict[str, float]] = None
    contains_hypothetical: Optional[bool] = None
    source_id: Optional[str] = None
    source_section: Optional[str] = None
    source_expression: Optional[str] = None
    basis_expression: Optional[str] = None
    sensitive_point_longitude: Optional[float] = None
    occupant_longitude: Optional[float] = None
    direct_orb_degrees: Optional[float] = None
    maximum_orb_degrees: Optional[float] = None
    symbolic_theme_zh: Optional[str] = None
    reading_zh: Optional[str] = None
    practical_prompt_zh: Optional[str] = None
    claim_type: Optional[str] = None
    rule_id: Optional[str] = None
    birth_time_sampled_status: Optional[str] = None
    factor_layers: Optional[Dict[str, str]] = None
    analysis_utc: Optional[str] = None
    solar_arc_degrees: Optional[float] = None


class SymmetryContact(ReferenceAngleGeometry):
    point: Optional[str] = None
    id_a: Optional[str] = None
    id_b: Optional[str] = None
    id_c: Optional[str] = None
    id_d: Optional[str] = None
    equation: Optional[str] = None
    orb: Optional[float] = None
    signed_orb: Optional[float] = None
    axis_offset_degrees: Optional[int] = None
    rule_id: Optional[str] = None
    contains_hypothetical: Optional[bool] = None
    sensitive_point: Optional[SensitivePoint] = None
    source_interpretation: Optional[SourceInterpretation] = None


class TwoFactorContact(ReferenceAngleGeometry):
    id_a: Optional[str] = None
    id_b: Optional[str] = None
    equation: Optional[str] = None
    orb: Optional[float] = None
    signed_orb: Optional[float] = None
    factor_offset_degrees: Optional[int] = None
    aspect_degrees: Optional[int] = None
    separation_degrees: Optional[float] = None
    rule_id: Optional[str] = None
    contains_hypothetical: Optional[bool] = None


class MidpointDial(PartialOutput):
    period_degrees: Optional[int] = None
    two_factor_contacts: Optional[List[TwoFactorContact]] = None
    three_factor_contacts: Optional[List[SymmetryContact]] = None
    four_factor_contacts: Optional[List[SymmetryContact]] = None


class FictitiousElementSource(PartialOutput):
    filename: Optional[str] = None
    status: Optional[str] = None
    search_path_index: Optional[int] = None
    sha256: Optional[str] = None
    scope: Optional[str] = None


class PhysicalEphemerisFile(PartialOutput):
    id: Optional[str] = None
    slot: Optional[int] = None
    filename: Optional[str] = None
    sha256: Optional[str] = None
    bytes: Optional[int] = None
    start_julian_day_tt: Optional[float] = Field(
        default=None,
        description="Native file range. In JPL mode this historical name aliases the raw TDB header start; no TDB-to-TT conversion. See time_scale_policy.",
    )
    end_julian_day_tt: Optional[float] = Field(
        default=None,
        description="Native file range. In JPL mode this historical name aliases the raw TDB header end; no TDB-to-TT conversion. See time_scale_policy.",
    )
    de_number: Optional[int] = None
    matches_packaged_manifest: Optional[bool] = None


class PhysicalFactorSource(PartialOutput):
    model: Optional[str] = None
    status: Optional[str] = None
    file_ids: Optional[List[str]] = None


class EphemerisTimeScalePolicy(PartialOutput):
    policy_id: Optional[str] = None
    status: Optional[str] = None
    native_version: Optional[str] = None
    binding_version: Optional[str] = None
    native_api_time_scale: Optional[str] = None
    raw_header_time_scale: Optional[str] = None
    tt_tdb_conversion_applied: Optional[bool] = None
    source_documented_maximum_difference_seconds: Optional[float] = None
    legacy_tt_range_fields: Optional[str] = None
    source_function: Optional[str] = None
    source_url: Optional[str] = None
    native_source_url: Optional[str] = None
    scope: Optional[str] = None


class PhysicalEphemerisSource(PartialOutput):
    ruleset_id: Optional[str] = None
    by_factor: Optional[Dict[str, PhysicalFactorSource]] = None
    files: Optional[List[PhysicalEphemerisFile]] = None
    has_unidentified_sources: Optional[bool] = None
    scope: Optional[str] = None
    atomic_file_read_proven: Optional[bool] = None
    accuracy_certified: Optional[bool] = None
    time_scale_policy: Optional[EphemerisTimeScalePolicy] = None


class ReferenceAngleModel(PartialOutput):
    house_code: Optional[str] = None
    house_flags: Optional[int] = None
    cusp_output_used: Optional[bool] = None
    role: Optional[str] = None
    used_reference_outputs: Optional[List[str]] = None


class MidpointProfile(PartialOutput):
    reference_angle_model: Optional[ReferenceAngleModel] = None
    angle_definition: Optional[Dict[str, Any]] = None
    ephemeris_model_scope: Optional[str] = None
    zodiac: Optional[str] = None
    calendar: Optional[str] = None
    time_scale: Optional[str] = None
    orb_degrees: Optional[float] = None
    orb_policy: Optional[str] = None
    coordinate_rounding_before_comparison: Optional[bool] = None
    factor_count: Optional[int] = None
    contact_policy: Optional[str] = None
    hypothetical_model: Optional[str] = None
    aries_point: Optional[str] = None
    node_mode: Optional[str] = None
    legacy_view: Optional[str] = None
    sensitive_point_policy: Optional[str] = None
    ephemeris_models: Optional[List[str]] = None
    julian_day_tt: Optional[float] = None
    julian_day_ut1: Optional[float] = None
    julian_day_utc: Optional[float] = None
    time_scale_method: Optional[str] = None
    future_leap_seconds_assumed_unchanged: Optional[bool] = None
    swisseph_version: Optional[str] = None
    hypothetical_element_source: Optional[FictitiousElementSource] = None
    physical_ephemeris_source: Optional[PhysicalEphemerisSource] = None


class GeometryRuleset(PartialOutput):
    id: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    source_ids: Optional[List[str]] = None


class GeometryRuleTrace(PartialOutput):
    rule_id: Optional[str] = None
    source_id: Optional[str] = None
    source_sections: Optional[List[str]] = None
    formula: Optional[str] = None
    scope: Optional[str] = None


class DialCounts(PartialOutput):
    two_factor: Optional[int] = None
    three_factor: Optional[int] = None
    four_factor: Optional[int] = None


class FactorSpan(PartialOutput):
    status: Optional[str] = None
    backend_convention_span: Optional[Dict[str, float]] = None
    unresolved_sample_count: Optional[int] = None
    minimum_offset_from_nominal_degrees: Optional[float] = None
    maximum_offset_from_nominal_degrees: Optional[float] = None
    maximum_adjacent_sample_jump_degrees: Optional[float] = None


class PatternBackendSample(PartialOutput):
    directed_midheaven_longitude: Optional[float] = None
    source_direct_orb_degrees: Optional[float] = None
    source_condition_met: Optional[bool] = None


class TimeSample(PartialOutput):
    source_reference_geometry_resolved: Optional[bool] = None
    source_reference_angle_basis: Optional[Dict[str, str]] = None
    backend_convention: Optional[PatternBackendSample] = None
    reference_angle_model: Optional[ReferenceAngleModel] = None
    angle_definition: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    reason_code: Optional[str] = None
    key_years: Optional[float] = None
    supported_key_years: Optional[List[float]] = None
    meridian_house_cusps: Optional[List[float]] = None
    meridian_armc: Optional[float] = None
    meridian_obliquity: Optional[float] = None
    meridian_angle_julian_day_tt: Optional[float] = None
    meridian_ayanamsha: Optional[float] = None
    meridian_factor_positions: Optional[List[MeridianFactorPosition]] = None
    sun_observation_indices: Optional[List[int]] = None
    sun_ephemeris_models: Optional[List[str]] = None
    physical_source_index: Optional[int] = None
    offset_seconds: Optional[float] = None
    recorded_utc: Optional[str] = None
    effective_utc: Optional[str] = None
    julian_day_tt: Optional[float] = None
    julian_day_ut1: Optional[float] = None
    time_scale_method: Optional[str] = None
    future_leap_seconds_assumed_unchanged: Optional[bool] = None
    factor_longitudes: Optional[Dict[str, float]] = None
    progressed_julian_day_tt: Optional[float] = None
    solar_arc_degrees: Optional[float] = None
    directed_midheaven_longitude: Optional[float] = None
    source_direct_orb_degrees: Optional[float] = None
    source_condition_met: Optional[bool] = None


class PatternBackendSummary(PartialOutput):
    evaluable_sample_count: Optional[int] = None
    present_sample_count: Optional[int] = None
    absent_sample_count: Optional[int] = None
    condition_by_sample: Optional[List[Optional[bool]]] = None
    minimum_sampled_direct_orb_degrees: Optional[float] = None
    maximum_sampled_direct_orb_degrees: Optional[float] = None
    scope: Optional[str] = None


class PatternSensitivity(PartialOutput):
    resolved_condition_sample_count: Optional[int] = None
    unresolved_reference_sample_count: Optional[int] = None
    unresolved_reference_sample_indices: Optional[List[int]] = None
    condition_by_sample: Optional[List[Optional[bool]]] = None
    backend_convention: Optional[PatternBackendSummary] = None
    computed_sample_count: Optional[int] = None
    unavailable_sample_count: Optional[int] = None
    orb_range_scope: Optional[str] = None
    source_id: Optional[str] = None
    basis_expression: Optional[str] = None
    maximum_direct_orb_degrees: Optional[float] = None
    sampled_status: Optional[str] = None
    present_sample_count: Optional[int] = None
    absent_sample_count: Optional[int] = None
    minimum_sampled_direct_orb_degrees: Optional[float] = None
    maximum_sampled_direct_orb_degrees: Optional[float] = None


class SectorSensitivity(PartialOutput):
    computed_sample_count: Optional[int] = None
    unresolved_sample_count: Optional[int] = None
    id: Optional[str] = None
    nominal_sector: Optional[int] = None
    observed_sectors: Optional[List[int]] = None
    sampled_status: Optional[str] = None
    sector_by_sample: Optional[List[Optional[int]]] = None


class SpecialtyTimeSensitivity(PartialOutput):
    unresolved_reference_sample_count: Optional[int] = None
    computed_sample_count: Optional[int] = None
    unavailable_sample_count: Optional[int] = None
    sample_scope_policy: Optional[str] = None
    ephemeris_model_scope: Optional[str] = None
    ruleset_id: Optional[str] = None
    author: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    uncertainty_minutes: Optional[float] = None
    scope: Optional[str] = None
    continuous_interval_proven: Optional[bool] = None
    sample_frequency_is_probability: Optional[bool] = None
    sample_count: Optional[int] = None
    maximum_recorded_sample_gap_seconds: Optional[float] = None
    represented_radius_seconds: Optional[float] = None
    datetime_resolution: Optional[str] = None
    recorded_interval_start_utc: Optional[str] = None
    recorded_interval_end_utc: Optional[str] = None
    clock_policy: Optional[str] = None
    input_clock_basis: Optional[str] = None
    recorded_interval_start_clock: Optional[str] = None
    recorded_interval_end_clock: Optional[str] = None
    requested_clock_radius_seconds: Optional[float] = None
    zodiac: Optional[str] = None
    ephemeris_models: Optional[List[str]] = None
    physical_ephemeris_sources: Optional[List[PhysicalEphemerisSource]] = None
    physical_ephemeris_models_consistent: Optional[bool] = None
    factor_scope: Optional[str] = None
    factor_count: Optional[int] = None
    hypothetical_element_source: Optional[FictitiousElementSource] = None
    factor_spans: Optional[Dict[str, FactorSpan]] = None
    samples: Optional[List[TimeSample]] = None
    limitations: Optional[List[str]] = None
    source_pattern: Optional[PatternSensitivity] = None
    sector_assignments: Optional[List[SectorSensitivity]] = None


class DirectedFactor(PartialOutput):
    coordinate_basis: Optional[str] = None
    angle_definition: Optional[Dict[str, Any]] = None
    id: Optional[str] = None
    longitude: Optional[float] = None
    natal_longitude: Optional[float] = None
    kind: Optional[str] = None
    natal_model: Optional[str] = None
    model: Optional[str] = None


class DirectionContact(PartialOutput):
    rule_id: Optional[str] = None
    equation: Optional[str] = None
    orb: Optional[float] = None
    signed_orb: Optional[float] = None
    contains_hypothetical: Optional[bool] = None
    zero_arc_identity: Optional[bool] = None
    point: Optional[str] = None
    point_layer: Optional[str] = None
    axis_layer: Optional[str] = None
    id_a: Optional[str] = None
    id_b: Optional[str] = None
    id_c: Optional[str] = None
    id_d: Optional[str] = None
    layer_a: Optional[str] = None
    layer_b: Optional[str] = None
    layer_c: Optional[str] = None
    layer_d: Optional[str] = None


class DirectionDial(PartialOutput):
    period_degrees: Optional[int] = None
    two_factor_contacts: Optional[List[DirectionContact]] = None
    three_factor_contacts: Optional[List[DirectionContact]] = None
    four_factor_contacts: Optional[List[DirectionContact]] = None


class SunObservation(PartialOutput):
    index: Optional[int] = None
    julian_day_tt: Optional[float] = None
    longitude: Optional[float] = None
    model: Optional[str] = None
    status: Optional[str] = None
    file_ids: Optional[List[str]] = None


class SunEphemerisBatch(PartialOutput):
    ruleset_id: Optional[str] = None
    observations: Optional[List[SunObservation]] = None
    files: Optional[List[PhysicalEphemerisFile]] = None
    query_count: Optional[int] = None
    configuration_locked: Optional[bool] = None
    equal_tt_epochs_reused: Optional[bool] = None
    has_unidentified_sources: Optional[bool] = None
    scope: Optional[str] = None
    atomic_file_read_proven: Optional[bool] = None
    accuracy_certified: Optional[bool] = None


class PrintedTimeOperation(PartialOutput):
    id: Optional[str] = None
    section: Optional[str] = None
    computed_time_seconds: Optional[int] = None
    printed_time_seconds: Optional[int] = None
    printed_minus_computed_time_seconds: Optional[int] = None
    arithmetic_matches_print: Optional[bool] = None


class ProgressionKeySourceComparison(PartialOutput):
    status: Optional[str] = None
    ruleset_id: Optional[str] = None
    author: Optional[str] = None
    version: Optional[str] = None
    selected_key_id: Optional[str] = None
    selected_key_from_compared_source: Optional[bool] = None
    computed_for_current_chart: Optional[bool] = None
    comparison_unit: Optional[str] = None
    source_record_sha256: Optional[str] = None
    source: Optional[GeometrySource] = None
    operations: Optional[List[PrintedTimeOperation]] = None
    printed_arithmetic_consistent: Optional[bool] = None
    inconsistent_operation_ids: Optional[List[str]] = None
    clock_label_status: Optional[str] = None
    residuals_applied_as_corrections: Optional[bool] = None
    original_progression_time_key_accepted: Optional[bool] = None
    full_original_rulebook_accepted: Optional[bool] = None
    scope: Optional[str] = None


class SolarArcProfile(PartialOutput):
    reference_angle_model: Optional[ReferenceAngleModel] = None
    angle_definition: Optional[Dict[str, Any]] = None
    analysis_utc: Optional[str] = None
    birth_effective_utc: Optional[str] = None
    elapsed_calendar_days: Optional[float] = None
    year_days: Optional[float] = None
    key_years: Optional[float] = None
    birth_julian_day_tt: Optional[float] = None
    progressed_julian_day_tt: Optional[float] = None
    julian_day_resolution_seconds: Optional[float] = None
    natal_tropical_sun: Optional[float] = None
    progressed_tropical_sun: Optional[float] = None
    solar_arc_degrees: Optional[float] = None
    one_degree_per_year_degrees: Optional[float] = None
    difference_from_one_degree_per_year: Optional[float] = None
    sun_ephemeris_models: Optional[List[str]] = None
    sun_observation_indices: Optional[List[int]] = None
    sun_ephemeris_source: Optional[SunEphemerisBatch] = None
    key_policy: Optional[str] = None
    key_source_comparison: Optional[ProgressionKeySourceComparison] = None
    orb_degrees: Optional[float] = None
    orb_policy: Optional[str] = None
    display_frame: Optional[str] = None
    directed_factors_are_observations: Optional[bool] = None


class DayMeridianBackendCoordinates(PartialOutput):
    natal_upper_meridian_longitude: Optional[float] = None
    natal_lower_meridian_longitude: Optional[float] = None
    solar_arc_midheaven_longitude: Optional[float] = None
    upper_meridian_longitude: Optional[float] = None
    lower_meridian_longitude: Optional[float] = None


class DayMeridianCoordinates(ReferenceAngleGeometry):
    backend_convention: Optional[DayMeridianBackendCoordinates] = None
    natal_upper_meridian_longitude: Optional[float] = None
    natal_lower_meridian_longitude: Optional[float] = None
    natal_tropical_sun: Optional[float] = None
    target_tropical_sun: Optional[float] = None
    solar_arc_degrees: Optional[float] = None
    solar_arc_midheaven_longitude: Optional[float] = None
    transit_sun_displacement_degrees: Optional[float] = None
    upper_meridian_longitude: Optional[float] = None
    lower_meridian_longitude: Optional[float] = None


class DayMeridianProfile(DayMeridianCoordinates):
    angle_definition: Optional[Dict[str, Any]] = None
    analysis_utc: Optional[str] = None
    target_julian_day_tt: Optional[float] = None
    target_time_scale_method: Optional[str] = None
    future_leap_seconds_assumed_unchanged: Optional[bool] = None
    target_sun_ephemeris_model: Optional[str] = None
    target_sun_observation_index: Optional[int] = None
    sun_ephemeris_source: Optional[SunEphemerisBatch] = None
    source_formula: Optional[str] = None
    year_key_policy: Optional[str] = None
    display_frame: Optional[str] = None
    meridians_are_observations: Optional[bool] = None


class DayMeridianSample(DayMeridianCoordinates):
    angle_definition: Optional[Dict[str, Any]] = None
    julian_day_tt: Optional[float] = None
    progressed_julian_day_tt: Optional[float] = None
    sun_observation_indices: Optional[List[int]] = None
    status: Optional[str] = None
    reason_code: Optional[str] = None
    key_years: Optional[float] = None
    supported_key_years: Optional[List[float]] = None
    offset_seconds: Optional[float] = None
    recorded_utc: Optional[str] = None
    effective_utc: Optional[str] = None


class DayMeridianSensitivity(PartialOutput):
    resolved_reference_sample_count: Optional[int] = None
    unresolved_reference_sample_count: Optional[int] = None
    unresolved_reference_sample_indices: Optional[List[int]] = None
    computed_sample_count: Optional[int] = None
    unavailable_sample_count: Optional[int] = None
    sample_scope_policy: Optional[str] = None
    factor_spans_scope: Optional[str] = None
    status: Optional[str] = None
    uncertainty_minutes: Optional[float] = None
    continuous_interval_proven: Optional[bool] = None
    sample_frequency_is_probability: Optional[bool] = None
    scope: Optional[str] = None
    recorded_interval_start_utc: Optional[str] = None
    recorded_interval_end_utc: Optional[str] = None
    maximum_recorded_sample_gap_seconds: Optional[float] = None
    represented_radius_seconds: Optional[float] = None
    clock_policy: Optional[str] = None
    input_clock_basis: Optional[str] = None
    recorded_interval_start_clock: Optional[str] = None
    recorded_interval_end_clock: Optional[str] = None
    requested_clock_radius_seconds: Optional[float] = None
    sample_count: Optional[int] = None
    factor_spans: Optional[Dict[str, FactorSpan]] = None
    samples: Optional[List[DayMeridianSample]] = None


class DayMeridianSourceComparison(PartialOutput):
    status: Optional[str] = None
    selected_construction: Optional[str] = None
    compared_construction: Optional[str] = None
    compared_source_id: Optional[str] = None
    computed_for_current_chart: Optional[bool] = None
    scope: Optional[str] = None
    explanation: Optional[str] = None
    historical_example_difference_arcminutes: Optional[int] = None
    separate_printed_sensitive_point_residual_arcminutes: Optional[int] = None
    difference_is_universal_correction: Optional[bool] = None
    original_variants_fully_reconciled: Optional[bool] = None
    original_progression_time_key_accepted: Optional[bool] = None


class DayMeridianInputCoherence(PartialOutput):
    status: Optional[str] = None
    birth_julian_day_tt: Optional[float] = None
    target_julian_day_tt: Optional[float] = None
    sample_count: Optional[int] = None
    nominal_sample_index: Optional[int] = None
    scope: Optional[str] = None


class DayMeridianAnalysis(PartialOutput):
    input_coherence: Optional[DayMeridianInputCoherence] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    ruleset_id: Optional[str] = None
    author: Optional[str] = None
    version: Optional[str] = None
    profile: Optional[DayMeridianProfile] = None
    birth_time_sensitivity: Optional[DayMeridianSensitivity] = None
    sources: Optional[List[GeometrySource]] = None
    source_comparison: Optional[DayMeridianSourceComparison] = None
    rule_trace: Optional[List[GeometryRuleTrace]] = None
    limitations: Optional[List[str]] = None
    original_text_conformance: Optional[str] = None
    real_world_efficacy: Optional[str] = None


class SourceTableCorner(PartialOutput):
    row: Optional[int] = None
    age_years: Optional[int] = None
    raw_cell: Optional[str] = None
    arcminutes: Optional[int] = None
    weight_fraction: Optional[List[int]] = None


class SourceTableProbe(PartialOutput):
    status: Optional[str] = None
    ruleset_id: Optional[str] = None
    day_offset_fraction: Optional[List[int]] = None
    age_years_fraction: Optional[List[int]] = None
    corners: Optional[List[SourceTableCorner]] = None
    arcminutes: Optional[float] = None
    arcminutes_fraction: Optional[List[int]] = None
    full_original_method_accepted: Optional[bool] = None
    scope: Optional[str] = None


class SourceTableRow(PartialOutput):
    row: Optional[int] = None
    printed_date: Optional[str] = None
    common_year_day_offset: Optional[int] = None
    raw_age_cells: Optional[List[str]] = None
    raw_until_january_zero_arcminutes: Optional[int] = None
    normalized_arcminutes: Optional[List[Optional[int]]] = None
    unresolved_age_columns: Optional[List[int]] = None


class SourceTableCoverage(PartialOutput):
    date_rows: Optional[int] = None
    raw_age_cells: Optional[int] = None
    resolved_age_cells: Optional[int] = None
    unresolved_age_cells: Optional[int] = None
    last_column_cells: Optional[int] = None
    all_printed_raw_cells_retained: Optional[bool] = None
    all_degrees_resolved: Optional[bool] = None


class SourceTableWorkedExample(PartialOutput):
    birth_date_label: Optional[str] = None
    target_date_label: Optional[str] = None
    clock_or_timezone_given: Optional[bool] = None
    printed_components_arcminutes: Optional[List[int]] = None
    literal_components_sum_arcminutes: Optional[int] = None
    printed_total_arcminutes: Optional[int] = None
    literal_arithmetic_matches_print: Optional[bool] = None
    exact_bilinear_base: Optional[SourceTableProbe] = None
    exact_fifty_year_arcminutes: Optional[float] = None
    exact_sixty_year_arcminutes: Optional[float] = None
    exact_last_column_arcminutes: Optional[float] = None
    hypothetical_unrounded_partial_year_arcminutes: Optional[float] = None
    hypothetical_unrounded_total_arcminutes: Optional[float] = None
    hypothetical_total_fraction: Optional[List[int]] = None
    printed_minus_hypothetical_total_arcminutes: Optional[float] = None
    hypothetical_unrounded_policy_adopted_as_original: Optional[bool] = None
    source_rounding_policy_fully_specified: Optional[bool] = None


class Witte1925SourceTable(PartialOutput):
    status: Optional[str] = None
    ruleset_id: Optional[str] = None
    author: Optional[str] = None
    version: Optional[str] = None
    computed_for_current_chart: Optional[bool] = None
    source_record_sha256: Optional[str] = None
    source: Optional[GeometrySource] = None
    coverage: Optional[SourceTableCoverage] = None
    age_columns_years: Optional[List[int]] = None
    rows: Optional[List[SourceTableRow]] = None
    worked_example: Optional[SourceTableWorkedExample] = None
    limitations: Optional[List[str]] = None
    full_original_method_accepted: Optional[bool] = None
    real_world_efficacy: Optional[str] = None


class MixedPairContact(ReferenceAngleGeometry):
    rule_id: Optional[str] = None
    id_a: Optional[str] = None
    id_b: Optional[str] = None
    id_c: Optional[str] = None
    id_d: Optional[str] = None
    equation: Optional[str] = None
    signed_orb: Optional[float] = None
    orb: Optional[float] = None
    midpoint_arc_coefficient: Optional[float] = None
    arc_invariant: Optional[bool] = None
    factor_layer_assignments: Optional[List[Dict[str, str]]] = None
    represented_layer_assignment_count: Optional[int] = None
    contains_hypothetical: Optional[bool] = None
    zero_arc_groups_coincide: Optional[bool] = None


class MixedPairDial(PartialOutput):
    period_degrees: Optional[int] = None
    arc_dependent_contacts: Optional[List[MixedPairContact]] = None
    arc_invariant_contacts: Optional[List[MixedPairContact]] = None


class MixedPairProfile(PartialOutput):
    solar_arc_degrees: Optional[float] = None
    orb_degrees: Optional[float] = None
    factor_count: Optional[int] = None
    four_distinct_factor_names_required: Optional[bool] = None
    pair_partitions_tested_per_dial: Optional[int] = None
    residual_groups_tested_per_dial: Optional[int] = None
    layer_assignments_represented_per_dial: Optional[int] = None
    coefficient_formula: Optional[str] = None
    arc_invariant_means: Optional[str] = None
    grouping_policy: Optional[str] = None
    birth_time_contact_sensitivity: Optional[str] = None


class MixedSensitivitySample(PartialOutput):
    sample_index: Optional[int] = None
    offset_seconds: Optional[float] = None
    recorded_utc: Optional[str] = None
    effective_utc: Optional[str] = None
    julian_day_tt: Optional[float] = None
    factor_longitudes: Optional[Dict[str, float]] = None
    solar_arc_status: Optional[str] = None
    solar_arc_degrees: Optional[float] = None
    reason_code: Optional[str] = None
    unresolved_reference_names: Optional[List[str]] = None
    native_sample_reference: Optional[str] = None
    solar_sample_reference: Optional[str] = None


class MixedSensitivityContact(PartialOutput):
    id_a: Optional[str] = None
    id_b: Optional[str] = None
    id_c: Optional[str] = None
    id_d: Optional[str] = None
    midpoint_arc_coefficient: Optional[float] = None
    arc_invariant: Optional[bool] = None
    arc_required_for_relative_condition: Optional[bool] = None
    factor_layer_assignments: Optional[List[Dict[str, str]]] = None
    nominal_backend_condition: Optional[bool] = None
    nominal_condition: Optional[bool] = None
    sampled_status: Optional[str] = None
    assessment_complete: Optional[bool] = None
    present_sample_indices: Optional[List[int]] = None
    known_absent_sample_count: Optional[int] = None
    unknown_sample_indices: Optional[List[int]] = None
    backend_hit_sample_indices: Optional[List[int]] = None
    backend_evaluable_sample_count: Optional[int] = None
    minimum_known_sampled_orb_degrees: Optional[float] = None
    maximum_known_sampled_orb_degrees: Optional[float] = None


class MixedSensitivitySummary(PartialOutput):
    evaluated_relation_groups: Optional[int] = None
    listed_observed_or_nominal_contact_groups: Optional[int] = None
    all_group_status_counts: Optional[Dict[str, int]] = None
    unlisted_no_observed_hit_counts: Optional[Dict[str, int]] = None


class MixedSensitivityDial(PartialOutput):
    period_degrees: Optional[int] = None
    contacts: Optional[List[MixedSensitivityContact]] = None
    all_group_status_counts: Optional[Dict[str, int]] = None
    unlisted_no_observed_hit_counts: Optional[Dict[str, int]] = None


class MixedPairSensitivity(PartialOutput):
    ruleset_id: Optional[str] = None
    status: Optional[str] = None
    uncertainty_minutes: Optional[float] = None
    continuous_interval_proven: Optional[bool] = None
    sample_frequency_is_probability: Optional[bool] = None
    summary: Optional[Dict[str, MixedSensitivitySummary]] = None
    sample_count: Optional[int] = None
    computed_arc_sample_count: Optional[int] = None
    unavailable_arc_sample_count: Optional[int] = None
    scope: Optional[str] = None
    nominal_sample_index: Optional[int] = None
    nominal_unresolved_reference_names: Optional[List[str]] = None
    exact_lattice_denominator_power: Optional[int] = None
    samples: Optional[List[MixedSensitivitySample]] = None
    dials: Optional[Dict[str, MixedSensitivityDial]] = None
    ledger_policy: Optional[str] = None
    arc_policy: Optional[str] = None
    interval: Optional[Dict[str, Any]] = None


class MixedPairGeometry(PartialOutput):
    status: Optional[str] = None
    reason: Optional[str] = None
    ruleset_id: Optional[str] = None
    author: Optional[str] = None
    version: Optional[str] = None
    profile: Optional[MixedPairProfile] = None
    dials: Optional[Dict[str, MixedPairDial]] = None
    contact_counts: Optional[Dict[str, Dict[str, int]]] = None
    unique_relation_groups_across_dials: Optional[int] = None
    birth_time_sensitivity: Optional[MixedPairSensitivity] = None
    sources: Optional[List[GeometrySource]] = None
    limitations: Optional[List[str]] = None
    full_original_method_accepted: Optional[bool] = None
    real_world_efficacy: Optional[str] = None


class SolarArcAnalysis(PartialOutput):
    status: Optional[str] = None
    reason: Optional[str] = None
    ruleset_id: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    profile: Optional[SolarArcProfile] = None
    directed_factors: Optional[List[DirectedFactor]] = None
    dials: Optional[Dict[str, DirectionDial]] = None
    mixed_pair_geometry: Optional[MixedPairGeometry] = None
    contact_counts: Optional[Dict[str, Dict[str, int]]] = None
    interpretations: Optional[List[SourceInterpretation]] = None
    birth_time_sensitivity: Optional[SpecialtyTimeSensitivity] = None
    daily_meridian: Optional[DayMeridianAnalysis] = None
    original_table_1925: Optional[Witte1925SourceTable] = None
    sources: Optional[List[GeometrySource]] = None
    rule_trace: Optional[List[GeometryRuleTrace]] = None
    limitations: Optional[List[str]] = None
    original_text_conformance: Optional[str] = None
    real_world_efficacy: Optional[str] = None


class MeridianHouseCusp(PartialOutput):
    house: Optional[int] = None
    longitude: Optional[float] = None
    tropical_longitude: Optional[float] = None
    right_ascension: Optional[float] = None


class MeridianHouseProfile(PartialOutput):
    house_code: Optional[str] = None
    swisseph_version: Optional[str] = None
    house_flags: Optional[int] = None
    obliquity_return_flags: Optional[int] = None
    geographic_latitude: Optional[float] = None
    geographic_longitude: Optional[float] = None
    construction: Optional[str] = None
    zodiac: Optional[str] = None
    right_ascension_frame: Optional[str] = None
    julian_day_ut1: Optional[float] = None
    shared_julian_day_tt: Optional[float] = None
    native_angle_julian_day_tt: Optional[float] = None
    native_angle_minus_shared_tt_seconds: Optional[float] = None
    angle_time_policy: Optional[str] = None
    armc: Optional[float] = None
    true_obliquity: Optional[float] = None
    ayanamsha_apparent: Optional[float] = None
    first_cusp_definition: Optional[str] = None
    tenth_cusp_definition: Optional[str] = None
    physical_ascendant: Optional[float] = None
    retained_ascendant_definition_reference: Optional[str] = None
    physical_midheaven: Optional[float] = None
    first_cusp_replaces_physical_ascendant: Optional[bool] = None
    base_chart_houses_replaced: Optional[bool] = None
    geographic_pole_meridian_convention: Optional[bool] = None


class MeridianCuspSpan(FactorSpan):
    house: Optional[int] = None


class MeridianFactorStability(PartialOutput):
    id: Optional[str] = None
    nominal_house: Optional[int] = None
    sampled_houses: Optional[List[int]] = None
    unresolved_sample_count: Optional[int] = None
    sampled_status: Optional[str] = None


class MeridianHouseSensitivity(PartialOutput):
    status: Optional[str] = None
    uncertainty_minutes: Optional[float] = None
    continuous_interval_proven: Optional[bool] = None
    sample_frequency_is_probability: Optional[bool] = None
    sample_reference: Optional[str] = None
    sample_count: Optional[int] = None
    maximum_recorded_sample_gap_seconds: Optional[float] = None
    cusp_spans: Optional[List[MeridianCuspSpan]] = None
    factor_placement_summary: Optional[List[MeridianFactorStability]] = None


class MeridianFactorPlacement(PartialOutput):
    status: Optional[str] = None
    ruleset_id: Optional[str] = None
    author: Optional[str] = None
    version: Optional[str] = None
    factor_count: Optional[int] = None
    physical_factor_count: Optional[int] = None
    hypothetical_factor_count: Optional[int] = None
    node_factor_count: Optional[int] = None
    factors: Optional[List[MeridianFactorPosition]] = None
    factor_ayanamsha_apparent: Optional[float] = None
    factor_julian_day_tt: Optional[float] = None
    projection_obliquity_julian_day_tt: Optional[float] = None
    coordinate_policy: Optional[str] = None
    sector_policy: Optional[str] = None
    pole_horizontal_norm_threshold: Optional[float] = None
    reference_points_included: Optional[bool] = None
    source_example_reconciliation: Optional[str] = None
    scope: Optional[str] = None
    sources: Optional[List[GeometrySource]] = None
    full_original_method_accepted: Optional[bool] = None
    real_world_efficacy: Optional[str] = None


class MeridianHouseAnalysis(PartialOutput):
    status: Optional[str] = None
    reason: Optional[str] = None
    ruleset_id: Optional[str] = None
    author: Optional[str] = None
    version: Optional[str] = None
    profile: Optional[MeridianHouseProfile] = None
    cusps: Optional[List[MeridianHouseCusp]] = None
    factor_placement: Optional[MeridianFactorPlacement] = None
    birth_time_sensitivity: Optional[MeridianHouseSensitivity] = None
    sources: Optional[List[GeometrySource]] = None
    rule_trace: Optional[List[GeometryRuleTrace]] = None
    limitations: Optional[List[str]] = None
    original_text_conformance: Optional[str] = None
    real_world_efficacy: Optional[str] = None


class ComparativePointSystem(PartialOutput):
    longitudes: Optional[Dict[str, Optional[float]]] = None
    backend_longitudes: Optional[Dict[str, float]] = None
    input_reference_geometry_resolved: Optional[bool] = None
    reference_angle_basis: Optional[Dict[str, str]] = None
    defined_anchor_identity: Optional[bool] = None
    unique_point_count: Optional[int] = None
    backend_unique_point_count: Optional[int] = None


class ComparativeFrameSummary(PartialOutput):
    anchor_factor: Optional[str] = None
    target_tropical_longitude: Optional[float] = None
    target_display_longitude: Optional[float] = None
    rotation_degrees: Optional[float] = None
    backend_rotation_degrees: Optional[float] = None
    anchor_input_reference_resolved: Optional[bool] = None
    anchor_reference_angle_basis: Optional[Dict[str, str]] = None
    resolved_factor_system_count: Optional[int] = None
    unresolved_factor_system_count: Optional[int] = None


class ComparativeFrame(ComparativeFrameSummary):
    factor_systems: Optional[Dict[str, ComparativePointSystem]] = None


class ComparativeProfile(PartialOutput):
    native_factor_count: Optional[int] = None
    constructed_frame_count: Optional[int] = None
    native_aries_point_longitude: Optional[float] = None
    display_zodiac: Optional[str] = None
    cardinal_policy: Optional[str] = None
    rotated_aries_factor_policy: Optional[str] = None
    rotation_formula: Optional[str] = None
    four_point_formula: Optional[str] = None
    source_natal_table_factor_count: Optional[int] = None
    native_factor_reference: Optional[str] = None
    exact_coordinate_policy: Optional[str] = None
    node_anchor_policy: Optional[str] = None
    meridian_anchor_policy: Optional[str] = None
    coordinates_are_new_observations: Optional[bool] = None


class ComparativeSample(PartialOutput):
    sample_index: Optional[int] = None
    offset_seconds: Optional[float] = None
    recorded_utc: Optional[str] = None
    effective_utc: Optional[str] = None
    julian_day_tt: Optional[float] = None
    factor_longitudes: Optional[Dict[str, float]] = None
    angle_definition: Optional[Dict[str, Any]] = None
    frame_summary: Optional[Dict[str, ComparativeFrameSummary]] = None
    point_systems: Optional[Dict[str, Dict[str, ComparativePointSystem]]] = None
    native_sample_reference: Optional[str] = None


class ComparativeOffsetSpan(PartialOutput):
    minimum: Optional[float] = None
    maximum: Optional[float] = None


class ComparativePointSpan(PartialOutput):
    nominal_input_reference_geometry_resolved: Optional[bool] = None
    resolved_sample_count: Optional[int] = None
    unresolved_sample_count: Optional[int] = None
    unresolved_sample_indices: Optional[List[int]] = None
    known_sampled_signed_offsets_from_nominal: Optional[
        Dict[str, ComparativeOffsetSpan]
    ] = None
    backend_sampled_signed_offsets_from_nominal: Optional[
        Dict[str, ComparativeOffsetSpan]
    ] = None


class ComparativeSensitivitySummary(PartialOutput):
    samples_with_unresolved_reference: Optional[int] = None
    point_systems_per_sample: Optional[int] = None
    all_confirmed_samples_retained: Optional[bool] = None


class ComparativeSensitivity(PartialOutput):
    status: Optional[str] = None
    uncertainty_minutes: Optional[float] = None
    sample_count: Optional[int] = None
    nominal_sample_index: Optional[int] = None
    continuous_interval_proven: Optional[bool] = None
    sample_frequency_is_probability: Optional[bool] = None
    summary: Optional[ComparativeSensitivitySummary] = None
    point_spans: Optional[Dict[str, Dict[str, ComparativePointSpan]]] = None
    samples: Optional[List[ComparativeSample]] = None
    interval: Optional[Dict[str, Any]] = None
    scope: Optional[str] = None


class ComparativeGeometry(PartialOutput):
    status: Optional[str] = None
    reason: Optional[str] = None
    ruleset_id: Optional[str] = None
    author: Optional[str] = None
    version: Optional[str] = None
    profile: Optional[ComparativeProfile] = None
    radix_systems: Optional[Dict[str, ComparativePointSystem]] = None
    frames: Optional[Dict[str, ComparativeFrame]] = None
    frame_summary: Optional[Dict[str, ComparativeFrameSummary]] = None
    birth_time_sensitivity: Optional[ComparativeSensitivity] = None
    sources: Optional[List[GeometrySource]] = None
    original_text_conformance: Optional[str] = None
    real_world_efficacy: Optional[str] = None
    limitations: Optional[List[str]] = None


class MidpointAnalysis(PartialOutput):
    status: Optional[str] = None
    reason: Optional[str] = None
    ruleset_id: Optional[str] = None
    version: Optional[str] = None
    profile: Optional[MidpointProfile] = None
    factors: Optional[List[MidpointFactor]] = None
    midpoint_axes: Optional[List[MidpointAxis]] = None
    dials: Optional[Dict[str, MidpointDial]] = None
    contact_counts: Optional[Dict[str, DialCounts]] = None
    unique_two_factor_pair_count: Optional[int] = None
    interpretations: Optional[List[SourceInterpretation]] = None
    time_sensitivity: Optional[SpecialtyTimeSensitivity] = None
    solar_arc_analysis: Optional[SolarArcAnalysis] = None
    meridian_houses: Optional[MeridianHouseAnalysis] = None
    comparative_geometry: Optional[ComparativeGeometry] = None
    reading_guide: Optional[Dict[str, str]] = None
    rulesets: Optional[List[GeometryRuleset]] = None
    rule_trace: Optional[List[GeometryRuleTrace]] = None
    sources: Optional[List[GeometrySource]] = None
    limitations: Optional[List[str]] = None
    original_text_conformance: Optional[str] = None
    real_world_efficacy: Optional[str] = None


class SectorProfile(PartialOutput):
    status: Optional[str] = None
    backend_convention_anchor_longitude: Optional[float] = None
    backend_convention_sectors: Optional[List[Dict[str, Any]]] = None
    angle_definition: Optional[Dict[str, Any]] = None
    ruleset_id: Optional[str] = None
    author: Optional[str] = None
    version: Optional[str] = None
    anchor: Optional[str] = None
    anchor_longitude: Optional[float] = None
    sector_count: Optional[int] = None
    width_degrees: Optional[float] = None
    interval_convention: Optional[str] = None
    boundary_display: Optional[str] = None
    coordinate_system: Optional[str] = None
    astronomical_constellations: Optional[bool] = None
    original_text_conformance: Optional[str] = None
    real_world_efficacy: Optional[str] = None
    sources: Optional[List[GeometrySource]] = None


class SectorEvidence(PartialOutput):
    assignment_status: Optional[str] = None
    backend_convention_sector: Optional[int] = None
    angle_definition: Optional[Dict[str, Any]] = None
    longitude_unrounded: Optional[float] = None
    ascendant_unrounded: Optional[float] = None
    interval_convention: Optional[str] = None
    rule_id: Optional[str] = None
    birth_time_uncertainty: Optional[str] = None
