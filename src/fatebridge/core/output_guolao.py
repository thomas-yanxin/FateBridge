"""Projection-compatible public evidence contracts for the Guolao research model."""

from typing import Any, Optional

from fatebridge.core.output_base import PartialOutput


class GuolaoMansion(PartialOutput):
    id: Optional[str] = None
    su28: Optional[str] = None
    degree_lord: Optional[str] = None
    right_ascension: Optional[float] = None
    degree_in_mansion: Optional[float] = None
    mansion_width: Optional[float] = None
    boundary_distance: Optional[float] = None
    determinative_star: Optional[str] = None
    coordinate_unit: Optional[str] = None
    placement_basis: Optional[str] = None


class GuolaoBody(PartialOutput):
    id: Optional[str] = None
    name_zh: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    longitude_speed: Optional[float] = None
    longitude_speed_native: Optional[float] = None
    longitude_speed_light_time_correction: Optional[float] = None
    longitude_speed_spatial_aberration_correction: Optional[float] = None
    longitude_speed_lunar_source_remainder_correction: Optional[float] = None
    longitude_speed_sidereal_origin_wrap_correction: Optional[float] = None
    longitude_speed_rotation_correction: Optional[float] = None
    longitude_speed_position_derivative_correction: Optional[float] = None
    longitude_speed_reference_frame: Optional[str] = None
    right_ascension: Optional[float] = None
    declination: Optional[float] = None
    zodiac_longitude: Optional[float] = None
    model: Optional[str] = None
    palace_branch: Optional[str] = None
    palace_lord: Optional[str] = None
    mansion: Optional[GuolaoMansion] = None
    in_own_palace: Optional[bool] = None
    in_own_mansion: Optional[bool] = None
    natal_functional_palace: Optional[str] = None


class GuolaoLifePalace(PartialOutput):
    longitude: Optional[float] = None
    branch: Optional[str] = None
    palace_lord: Optional[str] = None
    mansion: Optional[GuolaoMansion] = None
    method: Optional[str] = None
    sun_palace_branch: Optional[str] = None
    sun_palace_basis: Optional[str] = None
    birth_hour_branch: Optional[str] = None
    birth_clock: Optional[str] = None
    clock_basis: Optional[str] = None
    counting_anchor_branch: Optional[str] = None
    seasonal_anchor_policy: Optional[str] = None
    seasonal_anchor_evidence: Optional[dict[str, Any]] = None
    degree_status: Optional[str] = None


class GuolaoPalace(PartialOutput):
    palace: Optional[str] = None
    branch: Optional[str] = None
    lord: Optional[str] = None
    lord_sign_index: Optional[int] = None
    lord_relations: Optional[dict[str, str]] = None


class GuolaoConditions(PartialOutput):
    is_day: Optional[bool] = None
    solar_altitude: Optional[float] = None
    day_night_basis: Optional[str] = None
    season: Optional[str] = None
    season_basis: Optional[str] = None


class GuolaoReferenceGeometry(PartialOutput):
    status: Optional[str] = None
    angles_status: Optional[str] = None
    houses_status: Optional[str] = None
    requested_house_system: Optional[str] = None
    requested_house_code: Optional[str] = None
    coordinate_frame: Optional[str] = None
    angle_method: Optional[str] = None
    house_method: Optional[str] = None
    reason: Optional[str] = None
    substituted_house_system: Optional[bool] = None


class GuolaoApparentSolarClock(PartialOutput):
    method_id: Optional[str] = None
    source_url: Optional[str] = None
    display: Optional[str] = None
    display_status: Optional[str] = None
    display_basis: Optional[str] = None
    display_precision: Optional[str] = None
    birth_hour_branch: Optional[str] = None
    apparent_day_fraction_exact: Optional[str] = None
    hour_boundary_distance_seconds_exact: Optional[str] = None
    solar_day_offset_from_civil: Optional[int] = None
    equation_of_time_seconds: Optional[float] = None
    total_correction_seconds: Optional[float] = None
    julian_day_ut1: Optional[float] = None
    sun_apparent_right_ascension: Optional[float] = None
    greenwich_apparent_sidereal_degrees: Optional[float] = None
    longitude: Optional[float] = None
    solar_reference: Optional[str] = None
    earth_rotation_basis: Optional[str] = None
    physical_time_accuracy_certified: Optional[bool] = None
    changes_physical_instant: Optional[bool] = None
    classical_clock_mapping_accepted: Optional[bool] = None


class GuolaoCoordinateProvenance(PartialOutput):
    ecliptic_model: Optional[str] = None
    equatorial_model: Optional[str] = None
    ecliptic_return_flags: Optional[int] = None
    equatorial_return_flags: Optional[int] = None


class GuolaoEphemerisProvenance(PartialOutput):
    physical_backend_policy: Optional[str] = None
    physical_model_scope: Optional[str] = None
    by_body: Optional[dict[str, GuolaoCoordinateProvenance]] = None
    nonphysical_factor_models: Optional[dict[str, str]] = None
    nonphysical_return_flags: Optional[dict[str, dict[str, int]]] = None
    fixed_star_observer_ephemeris_model: Optional[str] = None
    fixed_star_observer_return_flags: Optional[int] = None
    fixed_star_native_return_flags: Optional[list[int]] = None
    fixed_star_flag_scope: Optional[str] = None
    absolute_astronomical_accuracy_certified: Optional[bool] = None


class GuolaoLongitudeMotionPolicy(PartialOutput):
    method_id: Optional[str] = None
    reference_frame: Optional[str] = None
    unit: Optional[str] = None
    scope: Optional[str] = None
    tropical_rotation: Optional[dict[str, Any]] = None
    lunar_light_time: Optional[dict[str, Any]] = None
    complete_position_derivatives: Optional[dict[str, dict[str, Any]]] = None
    physical_ephemeris_source: Optional[dict[str, Any]] = None


class GuolaoProfile(PartialOutput):
    native_time_axis: Optional[dict[str, Any]] = None
    input_clock: Optional[dict[str, Any]] = None
    ruleset_id: Optional[str] = None
    pattern_model_id: Optional[str] = None
    calendar: Optional[str] = None
    utc_datetime: Optional[str] = None
    julian_day_tt: Optional[float] = None
    julian_day_ut1: Optional[float] = None
    time_conversion: Optional[str] = None
    future_leap_seconds_assumed_unchanged: Optional[bool] = None
    solar_clock_display: Optional[str] = None
    apparent_solar_clock: Optional[GuolaoApparentSolarClock] = None
    solar_clock_changes_instant: Optional[bool] = None
    catalogue_sha256: Optional[str] = None
    ephemeris_models: Optional[list[str]] = None
    ephemeris_provenance: Optional[GuolaoEphemerisProvenance] = None
    longitude_motion: Optional[GuolaoLongitudeMotionPolicy] = None
    mansion_unit: Optional[str] = None
    anchor_order: Optional[str] = None
    astronomical_house_role: Optional[str] = None
    astronomical_house_frame: Optional[str] = None
    astronomical_house_method: Optional[str] = None
    reference_geometry: Optional[GuolaoReferenceGeometry] = None
    functional_palace_basis: Optional[str] = None


class GuolaoPatternEvidence(PartialOutput):
    model_id: Optional[str] = None
    granularity: Optional[str] = None
    inputs: Optional[dict[str, Any]] = None
    condition_satisfied: Optional[bool] = None
    classical_acceptance: Optional[bool] = None
    event_probability_estimated: Optional[bool] = None


class GuolaoBoundary(PartialOutput):
    su28: Optional[str] = None
    star: Optional[str] = None
    right_ascension: Optional[float] = None


class GuolaoRuleset(PartialOutput):
    id: Optional[str] = None
    edition_id: Optional[str] = None
    title: Optional[str] = None
    source_url: Optional[str] = None
    verified_subset: Optional[str] = None


class GuolaoRuleTrace(PartialOutput):
    rule_id: Optional[str] = None
    source_id: Optional[str] = None
    locator: Optional[str] = None
    subject: Optional[str] = None
    inputs: Optional[dict[str, Any]] = None
    outputs: Optional[dict[str, Any]] = None
    placement_classical_acceptance: Optional[bool] = None


class GuolaoValidation(PartialOutput):
    classical_acceptance_passed: Optional[bool] = None
    real_world_prediction_status: Optional[str] = None
    full_marks_established: Optional[bool] = None
    limitations: Optional[list[str]] = None


class GuolaoGodPositions(PartialOutput):
    native_year_comparison: Optional[dict[str, Any]] = None
    year_stem: Optional[str] = None
    year_branch: Optional[str] = None
    year_boundary_basis: Optional[str] = None
    branches: Optional[dict[str, str]] = None
    aliases: Optional[dict[str, str]] = None
    selected_noble: Optional[str] = None
    selected_noble_branch: Optional[str] = None
    source_id: Optional[str] = None
    locator: Optional[str] = None


class GuolaoPurpleModelAudit(PartialOutput):
    model_in_use: Optional[str] = None
    fitted_period_days: Optional[float] = None
    source_id: Optional[str] = None
    source_epoch_description: Optional[str] = None
    source_validation_status: Optional[str] = None
    source_period_days: Optional[str] = None
    source_offset_days: Optional[str] = None
    source_days_per_historical_du: Optional[str] = None
    source_circle_historical_du: Optional[str] = None
    source_circle_basis: Optional[str] = None
    source_printed_circle_historical_du: Optional[str] = None
    source_printed_xu_width_du: Optional[str] = None
    source_facsimile_locator: Optional[str] = None
    source_corrected_period_days: Optional[str] = None
    source_rounding_discrepancy_days: Optional[str] = None
    modern_epoch_calibration_status: Optional[str] = None
    historical_period_used_as_modern_longitude: Optional[bool] = None
    corrected_offset_recalibrated: Optional[bool] = None


class GuolaoSmallLimit(PartialOutput):
    branch: Optional[str] = None
    natal_functional_palace: Optional[str] = None
    palace_lord: Optional[str] = None
    life_branch: Optional[str] = None
    birth_year_stem: Optional[str] = None
    birth_year_branch: Optional[str] = None
    target_year_stem: Optional[str] = None
    target_year_branch: Optional[str] = None
    year_boundary_basis: Optional[str] = None
    source_id: Optional[str] = None
    locator: Optional[str] = None
    method: Optional[str] = None
    placement_classical_acceptance: Optional[bool] = None


class GuolaoTargetProfile(PartialOutput):
    julian_day_tt: Optional[float] = None
    julian_day_ut1: Optional[float] = None
    time_conversion: Optional[str] = None
    future_leap_seconds_assumed_unchanged: Optional[bool] = None
    ephemeris_models: Optional[list[str]] = None
    ephemeris_provenance: Optional[GuolaoEphemerisProvenance] = None
    longitude_motion: Optional[GuolaoLongitudeMotionPolicy] = None
    catalogue_sha256: Optional[str] = None
    ayanamsha: Optional[float] = None
    zodiac: Optional[str] = None
    position_basis: Optional[str] = None
    observer_geometry: Optional[str] = None
    mansion_basis: Optional[str] = None
    purple_model: Optional[str] = None


class GuolaoMonthContext(PartialOutput):
    calendar_date: Optional[str] = None
    calendar_date_evidence: Optional[dict[str, Any]] = None
    term_search_year: Optional[int] = None
    term_search_year_basis: Optional[str] = None
    primary_julian_day_tt: Optional[float] = None
    primary_julian_day_ut1: Optional[float] = None
    utc_representation: Optional[dict[str, Any]] = None
    calendar_lookup_basis: Optional[str] = None
    comparison_basis: Optional[str] = None
    unavailable_reason: Optional[str] = None
    status: Optional[str] = None
    instant_utc: Optional[str] = None
    month_number: Optional[int] = None
    month_branch: Optional[str] = None
    start_boundary: Optional[dict[str, Any]] = None
    next_boundary: Optional[dict[str, Any]] = None
    timezone: Optional[str] = None
    boundary_basis: Optional[str] = None
    is_leap_month: Optional[bool] = None
    lunar_year: Optional[int] = None
    lunar_day: Optional[int] = None
    calendar_datetime: Optional[str] = None
    conversion_source: Optional[dict[str, Any]] = None


class GuolaoMonthLimit(PartialOutput):
    status: Optional[str] = None
    model_id: Optional[str] = None
    source_id: Optional[str] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    source_data_sha256: Optional[str] = None
    source_image_sha256: Optional[str] = None
    locator: Optional[str] = None
    month_basis: Optional[str] = None
    method: Optional[str] = None
    annual_branch: Optional[str] = None
    birth_month: Optional[GuolaoMonthContext] = None
    target_month: Optional[GuolaoMonthContext] = None
    branch: Optional[str] = None
    natal_functional_palace: Optional[str] = None
    palace_lord: Optional[str] = None
    ordinal_rule_collated: Optional[bool] = None
    calendar_mapping_classical_acceptance: Optional[bool] = None
    event_probability_estimated: Optional[bool] = None
    clock_basis: Optional[str] = None
    intercalary_policy: Optional[str] = None
    limitations: Optional[list[str]] = None


class GuolaoTiming(PartialOutput):
    native_year_comparison: Optional[dict[str, Any]] = None
    target_order_evidence: Optional[dict[str, Any]] = None
    calendar_timezone_role: Optional[str] = None
    status: Optional[str] = None
    analysis_datetime: Optional[str] = None
    calendar_datetime: Optional[str] = None
    calendar_timezone: Optional[str] = None
    calendar: Optional[str] = None
    small_limit: Optional[GuolaoSmallLimit] = None
    month_limit: Optional[GuolaoMonthLimit] = None
    transit_bodies: Optional[list[GuolaoBody]] = None
    mansion_boundaries: Optional[list[GuolaoBoundary]] = None
    profile: Optional[GuolaoTargetProfile] = None
    limitations: Optional[list[str]] = None


class GuolaoResearch(PartialOutput):
    bodies: Optional[list[GuolaoBody]] = None
    life_palace: Optional[GuolaoLifePalace] = None
    palaces: Optional[list[GuolaoPalace]] = None
    conditions: Optional[GuolaoConditions] = None
    profile: Optional[GuolaoProfile] = None
    mansion_boundaries: Optional[list[GuolaoBoundary]] = None
    rulesets: Optional[list[GuolaoRuleset]] = None
    rule_trace: Optional[list[GuolaoRuleTrace]] = None
    validation: Optional[GuolaoValidation] = None
    god_positions: Optional[GuolaoGodPositions] = None
    purple_model_audit: Optional[GuolaoPurpleModelAudit] = None
    timing: Optional[GuolaoTiming] = None
