"""Projection-compatible public evidence contracts for the Guolao research model."""

from typing import Literal

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput


class GuolaoMansion(PartialOutput):
    id: str | None = None
    su28: str | None = None
    degree_lord: str | None = None
    right_ascension: float | None = None
    degree_in_mansion: float | None = None
    mansion_width: float | None = None
    boundary_distance: float | None = None
    determinative_star: str | None = None
    coordinate_unit: str | None = None
    placement_basis: str | None = None


class GuolaoBody(PartialOutput):
    id: str | None = None
    name_zh: str | None = None
    longitude: float | None = None
    latitude: float | None = None
    longitude_speed: float | None = None
    longitude_speed_native: float | None = None
    longitude_speed_light_time_correction: float | None = None
    longitude_speed_spatial_aberration_correction: float | None = None
    longitude_speed_lunar_source_remainder_correction: float | None = None
    longitude_speed_sidereal_origin_wrap_correction: float | None = None
    longitude_speed_rotation_correction: float | None = None
    longitude_speed_position_derivative_correction: float | None = None
    longitude_speed_reference_frame: str | None = None
    right_ascension: float | None = None
    declination: float | None = None
    zodiac_longitude: float | None = None
    model: str | None = None
    derived_from: Literal["罗"] | None = None
    derivation_source_longitude: float | None = None
    derivation_source_right_ascension: float | None = None
    palace_branch: str | None = None
    palace_lord: str | None = None
    mansion: GuolaoMansion | None = None
    in_own_palace: bool | None = None
    in_own_mansion: bool | None = None
    natal_functional_palace: str | None = None


class GuolaoLifePalace(PartialOutput):
    longitude: float | None = None
    branch: str | None = None
    palace_lord: str | None = None
    mansion: GuolaoMansion | None = None
    method: str | None = None
    sun_palace_branch: str | None = None
    sun_palace_basis: str | None = None
    birth_hour_branch: str | None = None
    birth_clock: str | None = None
    clock_basis: str | None = None
    counting_anchor_branch: str | None = None
    seasonal_anchor_policy: str | None = None
    seasonal_anchor_evidence: dict[str, OpenJsonValue] | None = None
    degree_status: str | None = None
    degree_reason: str | None = None


class GuolaoPalace(PartialOutput):
    palace: str | None = None
    branch: str | None = None
    lord: str | None = None
    lord_sign_index: int | None = None
    lord_relations: dict[str, str] | None = None


class GuolaoConditions(PartialOutput):
    is_day: bool | None = None
    solar_altitude: float | None = None
    day_night_basis: str | None = None
    season: str | None = None
    season_basis: str | None = None


class GuolaoReferenceGeometry(PartialOutput):
    status: str | None = None
    angles_status: str | None = None
    houses_status: str | None = None
    requested_house_system: str | None = None
    requested_house_code: str | None = None
    coordinate_frame: str | None = None
    angle_method: str | None = None
    house_method: str | None = None
    reason: str | None = None
    substituted_house_system: bool | None = None


class GuolaoApparentSolarClock(PartialOutput):
    method_id: str | None = None
    source_url: str | None = None
    display: str | None = None
    display_status: str | None = None
    display_basis: str | None = None
    display_precision: str | None = None
    birth_hour_branch: str | None = None
    apparent_day_fraction_exact: str | None = None
    hour_boundary_distance_seconds_exact: str | None = None
    solar_day_offset_from_civil: int | None = None
    equation_of_time_seconds: float | None = None
    total_correction_seconds: float | None = None
    julian_day_ut1: float | None = None
    sun_apparent_right_ascension: float | None = None
    equatorial_frame: str | None = None
    greenwich_apparent_sidereal_degrees: float | None = None
    longitude: float | None = None
    solar_reference: str | None = None
    earth_rotation_basis: str | None = None
    physical_time_accuracy_certified: bool | None = None
    changes_physical_instant: bool | None = None
    classical_clock_mapping_accepted: bool | None = None


class GuolaoCoordinateProvenance(PartialOutput):
    ecliptic_model: str | None = None
    equatorial_model: str | None = None
    ecliptic_return_flags: int | None = None
    equatorial_return_flags: int | None = None


class GuolaoEphemerisProvenance(PartialOutput):
    physical_backend_policy: str | None = None
    physical_model_scope: str | None = None
    by_body: dict[str, GuolaoCoordinateProvenance] | None = None
    nonphysical_factor_models: dict[str, str] | None = None
    nonphysical_return_flags: dict[str, dict[str, int]] | None = None
    fixed_star_observer_ephemeris_model: str | None = None
    fixed_star_observer_return_flags: int | None = None
    fixed_star_native_return_flags: list[int] | None = None
    fixed_star_flag_scope: str | None = None
    absolute_astronomical_accuracy_certified: bool | None = None


class GuolaoLongitudeMotionPolicy(PartialOutput):
    method_id: str | None = None
    reference_frame: str | None = None
    unit: str | None = None
    scope: str | None = None
    tropical_rotation: dict[str, OpenJsonValue] | None = None
    lunar_light_time: dict[str, OpenJsonValue] | None = None
    complete_position_derivatives: dict[str, dict[str, OpenJsonValue]] | None = None
    physical_ephemeris_source: dict[str, OpenJsonValue] | None = None


class GuolaoProfile(PartialOutput):
    native_time_axis: dict[str, OpenJsonValue] | None = None
    input_clock: dict[str, OpenJsonValue] | None = None
    ruleset_id: str | None = None
    pattern_model_id: str | None = None
    calendar: str | None = None
    utc_datetime: str | None = None
    julian_day_tt: float | None = None
    julian_day_ut1: float | None = None
    time_conversion: str | None = None
    future_leap_seconds_assumed_unchanged: bool | None = None
    solar_clock_display: str | None = None
    apparent_solar_clock: GuolaoApparentSolarClock | None = None
    solar_clock_changes_instant: bool | None = None
    catalogue_sha256: str | None = None
    ephemeris_models: list[str] | None = None
    ephemeris_provenance: GuolaoEphemerisProvenance | None = None
    longitude_motion: GuolaoLongitudeMotionPolicy | None = None
    mansion_unit: str | None = None
    anchor_order: str | None = None
    astronomical_house_role: str | None = None
    astronomical_house_frame: str | None = None
    astronomical_house_method: str | None = None
    reference_geometry: GuolaoReferenceGeometry | None = None
    functional_palace_basis: str | None = None


class GuolaoPatternEvidence(PartialOutput):
    model_id: str | None = None
    granularity: str | None = None
    inputs: dict[str, OpenJsonValue] | None = None
    condition_satisfied: bool | None = None
    classical_acceptance: bool | None = None


class GuolaoMoiraCounts(PartialOutput):
    source_declarations: int | None = None
    predicate_rules: int | None = None
    aliases: int | None = None
    evaluated: int | None = None
    uncomputed: int | None = None
    active: int | None = None
    suppressed: int | None = None
    unknown_conditions: int | None = None
    unresolved_visibility: int | None = None
    undefined_symbols: int | None = None


class GuolaoMoiraRule(PartialOutput):
    rule_id: str | None = None
    source_line: int | None = None
    polarity: Literal["good", "bad"] | None = None
    priority: list[int] | None = None
    never_output: bool | None = None
    raw_state: Literal["uncomputed", "evaluating", "computed"] | None = None
    value_status: (
        Literal["known", "unknown", "undefined", "null", "uncomputed"] | None
    ) = None
    value: str | list[str] | None = None
    condition_status: (
        Literal["true", "false", "unknown", "undefined", "uncomputed"] | None
    ) = None
    condition_value: bool | None = None
    hidden: bool | None = None
    suppressed_by: list[str] | None = None
    possibly_suppressed_by: list[str] | None = None
    visibility: (
        Literal["active", "suppressed", "unknown", "inactive", "internal", "uncomputed"]
        | None
    ) = None
    missing_facts: list[str] | None = None
    undefined_symbols: list[str] | None = None
    evaluation_errors: list[str] | None = None


class GuolaoMoiraAlias(PartialOutput):
    name: str | None = None
    rule_id: str | None = None
    source_line: int | None = None
    status: (
        Literal[
            "active", "suppressed", "unknown", "inactive", "undefined", "uncomputed"
        ]
        | None
    ) = None
    visible: bool | None = None


class GuolaoMoiraEvaluation(PartialOutput):
    profile_id: str | None = None
    source_commit: str | None = None
    source_property_sha256: str | None = None
    scope: str | None = None
    fact_provenance: dict[str, str] | None = None
    counts: GuolaoMoiraCounts | None = None
    rules: list[GuolaoMoiraRule] | None = None
    aliases: list[GuolaoMoiraAlias] | None = None


class GuolaoMoiraCalendar(PartialOutput):
    year_pillar: str | None = None
    month_pillar: str | None = None
    hour_branch: str | None = None
    lunar_day: int | None = None
    provenance: dict[str, str] | None = None


class GuolaoMoiraSourceProvider(PartialOutput):
    profile_id: str | None = None
    source_commit: str | None = None
    source_url: str | None = None
    calendar: GuolaoMoiraCalendar | None = None
    known_absent: list[str] | None = None
    provenance: dict[str, str] | None = None
    scope: str | None = None


class GuolaoBoundary(PartialOutput):
    su28: str | None = None
    star: str | None = None
    right_ascension: float | None = None


class GuolaoRuleset(PartialOutput):
    id: str | None = None
    edition_id: str | None = None
    title: str | None = None
    source_url: str | None = None
    verified_subset: str | None = None


class GuolaoRuleTrace(PartialOutput):
    rule_id: str | None = None
    source_id: str | None = None
    locator: str | None = None
    subject: str | None = None
    inputs: dict[str, OpenJsonValue] | None = None
    outputs: dict[str, OpenJsonValue] | None = None
    placement_classical_acceptance: bool | None = None


class GuolaoValidation(PartialOutput):
    classical_acceptance_passed: bool | None = None
    real_world_prediction_status: str | None = None
    full_marks_established: bool | None = None
    limitations: list[str] | None = None


class GuolaoGodPositions(PartialOutput):
    native_year_comparison: dict[str, OpenJsonValue] | None = None
    year_stem: str | None = None
    year_branch: str | None = None
    year_boundary_basis: str | None = None
    branches: dict[str, str] | None = None
    aliases: dict[str, str] | None = None
    selected_noble: str | None = None
    selected_noble_branch: str | None = None
    source_id: str | None = None
    locator: str | None = None


class GuolaoPurpleModelAudit(PartialOutput):
    model_in_use: str | None = None
    period_days: float | None = None
    epoch_jd: float | None = None
    epoch_longitude: float | None = None
    software_source_url: str | None = None
    software_source_commit: str | None = None
    software_source_function: str | None = None
    fixture_fitting_used: bool | None = None
    source_id: str | None = None
    source_epoch_description: str | None = None
    source_validation_status: str | None = None
    source_period_days: str | None = None
    source_offset_days: str | None = None
    source_days_per_historical_du: str | None = None
    source_circle_historical_du: str | None = None
    source_circle_basis: str | None = None
    source_printed_circle_historical_du: str | None = None
    source_printed_xu_width_du: str | None = None
    source_facsimile_locator: str | None = None
    source_corrected_period_days: str | None = None
    source_rounding_discrepancy_days: str | None = None
    modern_epoch_calibration_status: str | None = None
    historical_period_used_as_modern_longitude: bool | None = None
    corrected_offset_recalibrated: bool | None = None


class GuolaoSmallLimit(PartialOutput):
    branch: str | None = None
    natal_functional_palace: str | None = None
    palace_lord: str | None = None
    life_branch: str | None = None
    birth_year_stem: str | None = None
    birth_year_branch: str | None = None
    target_year_stem: str | None = None
    target_year_branch: str | None = None
    year_boundary_basis: str | None = None
    source_id: str | None = None
    locator: str | None = None
    method: str | None = None
    placement_classical_acceptance: bool | None = None


class GuolaoTargetProfile(PartialOutput):
    julian_day_tt: float | None = None
    julian_day_ut1: float | None = None
    time_conversion: str | None = None
    future_leap_seconds_assumed_unchanged: bool | None = None
    ephemeris_models: list[str] | None = None
    ephemeris_provenance: GuolaoEphemerisProvenance | None = None
    longitude_motion: GuolaoLongitudeMotionPolicy | None = None
    catalogue_sha256: str | None = None
    ayanamsha: float | None = None
    zodiac: str | None = None
    position_basis: str | None = None
    observer_geometry: str | None = None
    mansion_basis: str | None = None
    purple_model: str | None = None


class GuolaoMonthContext(PartialOutput):
    calendar_date: str | None = None
    calendar_date_evidence: dict[str, OpenJsonValue] | None = None
    term_search_year: int | None = None
    term_search_year_basis: str | None = None
    primary_julian_day_tt: float | None = None
    primary_julian_day_ut1: float | None = None
    utc_representation: dict[str, OpenJsonValue] | None = None
    calendar_lookup_basis: str | None = None
    comparison_basis: str | None = None
    unavailable_reason: str | None = None
    status: str | None = None
    instant_utc: str | None = None
    month_number: int | None = None
    month_branch: str | None = None
    start_boundary: dict[str, OpenJsonValue] | None = None
    next_boundary: dict[str, OpenJsonValue] | None = None
    timezone: str | None = None
    boundary_basis: str | None = None
    is_leap_month: bool | None = None
    lunar_year: int | None = None
    lunar_day: int | None = None
    calendar_datetime: str | None = None
    conversion_source: dict[str, OpenJsonValue] | None = None


class GuolaoMonthLimit(PartialOutput):
    status: str | None = None
    model_id: str | None = None
    source_id: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_data_sha256: str | None = None
    source_image_sha256: str | None = None
    locator: str | None = None
    month_basis: str | None = None
    method: str | None = None
    annual_branch: str | None = None
    birth_month: GuolaoMonthContext | None = None
    target_month: GuolaoMonthContext | None = None
    branch: str | None = None
    natal_functional_palace: str | None = None
    palace_lord: str | None = None
    ordinal_rule_collated: bool | None = None
    calendar_mapping_classical_acceptance: bool | None = None
    clock_basis: str | None = None
    intercalary_policy: str | None = None
    limitations: list[str] | None = None


class GuolaoTiming(PartialOutput):
    native_year_comparison: dict[str, OpenJsonValue] | None = None
    target_order_evidence: dict[str, OpenJsonValue] | None = None
    calendar_timezone_role: str | None = None
    status: str | None = None
    analysis_datetime: str | None = None
    calendar_datetime: str | None = None
    calendar_timezone: str | None = None
    calendar: str | None = None
    small_limit: GuolaoSmallLimit | None = None
    month_limit: GuolaoMonthLimit | None = None
    transit_bodies: list[GuolaoBody] | None = None
    mansion_boundaries: list[GuolaoBoundary] | None = None
    profile: GuolaoTargetProfile | None = None
    limitations: list[str] | None = None


class GuolaoResearch(PartialOutput):
    moira_rule_evaluation: GuolaoMoiraEvaluation | None = None
    moira_source_provider: GuolaoMoiraSourceProvider | None = None
    bodies: list[GuolaoBody] | None = None
    life_palace: GuolaoLifePalace | None = None
    palaces: list[GuolaoPalace] | None = None
    conditions: GuolaoConditions | None = None
    profile: GuolaoProfile | None = None
    mansion_boundaries: list[GuolaoBoundary] | None = None
    rulesets: list[GuolaoRuleset] | None = None
    rule_trace: list[GuolaoRuleTrace] | None = None
    validation: GuolaoValidation | None = None
    god_positions: GuolaoGodPositions | None = None
    purple_model_audit: GuolaoPurpleModelAudit | None = None
    timing: GuolaoTiming | None = None
