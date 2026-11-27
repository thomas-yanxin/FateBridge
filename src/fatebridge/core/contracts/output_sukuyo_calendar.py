"""Sukuyo dates, calendar references and witnesses."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput


class SukuyoMonthTableVariant(PartialOutput):
    ruleset_id: str | None = None
    lunar_month: int | None = None
    lunar_day: int | None = None
    literal_mansion: str | None = None
    table_mansion_28: str | None = None
    reference_month_day_mansion_27: str | None = None
    reference_is_primary_result: bool | None = None
    differs_from_selected_27: bool | None = None
    applied_to_sanjiu: bool | None = None
    locator: str | None = None
    source_url: str | None = None


class SukuyoDayClassification(PartialOutput):
    witness: str | None = None
    assessment: str | None = None
    locator: str | None = None


class SukuyoTimeRestriction(PartialOutput):
    witness: str | None = None
    phase: str | None = None
    assessment_before_release: str | None = None
    release_after: str | None = None
    locator: str | None = None
    source_excerpt: str | None = None
    literal_lunar_day: int | None = None
    interpreted_lunar_day: int | None = None
    interpretation_status: str | None = None
    annotation_locator: str | None = None
    release_locator: str | None = None
    release_excerpt: str | None = None


class SukuyoVerseResolution(PartialOutput):
    id: str | None = None
    locator: str | None = None
    source_url: str | None = None
    source_excerpt: str | None = None
    xml_kind: str | None = None
    literal_expression: str | None = None
    literal_lunar_day: int | None = None
    interpreted_lunar_day: int | None = None
    resolution_status: str | None = None
    applies_to_current_lunar_day: bool | None = None
    scope: str | None = None


class SukuyoComparativeTimeReference(PartialOutput):
    id: str | None = None
    witnesses: list[dict[str, OpenJsonValue]] | None = None
    applied_to_runtime_clock: bool | None = None
    t1299_day_eight_night_eight_replaced: bool | None = None
    modern_clock_conversion_established: bool | None = None
    solar_altitude_degrees: float | None = None
    hinoo_half_mapping_established: bool | None = None
    scope: str | None = None


class SukuyoClockDoctrine(PartialOutput):
    source_specific_time_calibration: dict[str, OpenJsonValue] | None = None
    kenyu_printed_reference: dict[str, OpenJsonValue] | None = None
    textual_position_reference: dict[str, OpenJsonValue] | None = None
    historical_clock_arithmetic: dict[str, OpenJsonValue] | None = None
    id: str | None = None
    source_url: str | None = None
    locator: str | None = None
    source_excerpt: str | None = None
    day_parts: int | None = None
    night_parts: int | None = None
    starting_boundary_literal: str | None = None
    next_boundary_literal: str | None = None
    intradaily_luminary_order: list[str] | None = None
    comparative_time_systems: SukuyoComparativeTimeReference | None = None
    physical_clock_mapping_status: str | None = None
    western_24_hora_applied: bool | None = None
    scope: str | None = None


class SukuyoCalendarDay(PartialOutput):
    lunar_day: int | None = None
    lunar_half: str | None = None
    half_day: int | None = None
    upper_name: str | None = None
    lower_name: str | None = None
    upper_name_locator: str | None = None
    lower_name_locator: str | None = None
    classifications: list[SukuyoDayClassification] | None = None
    time_restrictions: list[SukuyoTimeRestriction] | None = None
    name_variant: bool | None = None
    classification_variant: bool | None = None
    prose_verse_time_variant: bool | None = None
    prose_verse_time_semantic_conflict: bool | None = None
    verse_abbreviation_resolution: SukuyoVerseResolution | None = None
    clock_evaluation_status: str | None = None
    clock_scope: str | None = None
    clock_doctrine: SukuyoClockDoctrine | None = None
    japanese_selected_reference: dict[str, OpenJsonValue] | None = None


class SukuyoDateInterval(PartialOutput):
    calendar_date: str | None = None
    start_utc_inclusive: str | None = None
    end_utc_exclusive: str | None = None
    start_utc_epoch_seconds: int | None = None
    end_utc_epoch_seconds: int | None = None
    start_utc_epoch_microseconds: str | None = None
    end_utc_epoch_microseconds: str | None = None


class SukuyoDateSupport(PartialOutput):
    calendar_reference_timezone: str | None = None
    utc_endpoints_use_astronomical_year_numbering: bool | None = None
    method_id: str | None = None
    local_date: str | None = None
    input_timezone: str | None = None
    possible_calendar_dates: list[str] | None = None
    utc_support_intervals: list[SukuyoDateInterval] | None = None
    civil_support_seconds: int | None = None
    enumeration_resolution_seconds: int | None = None
    interval_resolution_microseconds: int | None = None
    fixed_offset_microseconds: int | None = None
    timezone_rules: dict[str, str] | None = None
    complete_under_loaded_timezone_rules: bool | None = None
    birth_time_imputed: bool | None = None
    scope: str | None = None


class SukuyoFullmoonCalculation(PartialOutput):
    ruleset_id: str | None = None
    lunar_month: int | None = None
    lunar_day: int | None = None
    fullmoon_day: int | None = None
    fullmoon_mansion: str | None = None
    signed_day_offset: int | None = None
    direct_mansion: str | None = None
    shortcut_inclusive_count: int | None = None
    shortcut_one_based_remainder: int | None = None
    shortcut_mansion: str | None = None
    methods_agree: bool | None = None
    source_url: str | None = None
    direct_locator: str | None = None
    shortcut_locator: str | None = None
    scope: str | None = None


class SukuyoCalendarProfile(PartialOutput):
    calendar_profile: str | None = None
    mansion_method_id: str | None = None
    host_calculation: SukuyoFullmoonCalculation | None = None
    requested_leap_month_policy: str | None = None
    effective_leap_month_policy: str | None = None
    calendar_day_part: str | None = None
    resolved: bool | None = None
    resolution_reason: str | None = None
    natal_su27: str | None = None
    candidate_su27: str | None = None
    candidate_su27s: list[str] | None = None
    candidate_set_complete_under_declared_reconstructions: bool | None = None
    short_month_assignment: dict[str, OpenJsonValue] | None = None
    hinoo_source: dict[str, OpenJsonValue] | None = None
    historical_calendar_reconstruction: bool | None = None
    classical_full_profile_acceptance: bool | None = None


class SukuyoDayCycleAnchor(PartialOutput):
    civil_ordinal: int | None = None
    day_ganzhi: str | None = None
    source_lunar_year_query: int | None = None


class SukuyoHistoricalDayReference(PartialOutput):
    name: str | None = None
    method_id: str | None = None
    source_anchor: SukuyoDayCycleAnchor | None = None
    elapsed_civil_days: int | None = None
    reference_boundary: str | None = None
    historical_day_boundary_accepted: bool | None = None
    bazi_day_pillar_evaluated: bool | None = None


class SukuyoCalendarReference(PartialOutput):
    manuscript_month_header: dict[str, OpenJsonValue] | None = None
    manuscript_daily_annotations: dict[str, OpenJsonValue] | None = None
    id: str | None = None
    provider_calendar_id: str | None = None
    source_url: str | None = None
    calendar_metadata_url: str | None = None
    source_month_start_ordinal: int | None = None
    source_month_length_days: int | None = None
    day_cycle_anchor: SukuyoDayCycleAnchor | None = None
    day_ganzhi_reference: SukuyoHistoricalDayReference | None = None
    month_truncated_by_calendar_reform: bool | None = None
    cross_source_comparison: dict[str, OpenJsonValue] | None = None
    cross_source_disagreement_dates: int | None = None
    retained_disagreement_interval_count: int | None = None
    complete_provider_advertised_historical_range: bool | None = None
    public_datetime_year_zero_and_bce_inputs_supported: bool | None = None
    supported_range_inclusive: list[str] | None = None
    methodology_advertised_range_inclusive: list[str] | None = None
    reference_day_count: int | None = None
    source_provenance: list[dict[str, OpenJsonValue]] | None = None
    monthly_endpoint_reconciliation: list[dict[str, OpenJsonValue]] | None = None
    source_discrepancies_retained: list[str] | None = None
    date_source_uri: str | None = None
    date_provenance: str | None = None
    calendar_reference_timezone: str | None = None
    historical_local_time_reconstruction: bool | None = None
    printed_lunar_year: int | None = None
    lunar_year_is_gregorian_era_year: bool | None = None
    historical_calendar_acceptance: bool | None = None
    independent_whole_range_verification: bool | None = None
    scope: str | None = None


class SukuyoCalendar(PartialOutput):
    input_timezone_rules: dict[str, str] | None = None
    calendar_basis: str | None = None
    calendar_reference: SukuyoCalendarReference | None = None
    status: str | None = None
    calendar_date: str | None = None
    calendar_timezone: str | None = None
    lunar_year: int | None = None
    lunar_month: int | None = None
    lunar_day: int | None = None
    is_leap_month: bool | None = None
    birth_time_known: bool | None = None
    natal_su27: str | None = None
    candidate_su27: str | None = None
    candidate_su27s: list[str] | None = None
    calendar_profile: str | None = None
    mansion_method_id: str | None = None
    calendar_day_part: str | None = None
    resolution_reason: str | None = None
    profile_calculation: SukuyoCalendarProfile | None = None
    leap_month_policy: str | None = None
    source_table_variant: SukuyoMonthTableVariant | None = None
    printed_edition_reference: dict[str, OpenJsonValue] | None = None
    rule_trace: list[dict[str, OpenJsonValue]] | None = None
    date_support: SukuyoDateSupport | None = None
    calendar_candidates: list[dict[str, OpenJsonValue]] | None = None
    out_of_range_calendar_dates: list[str] | None = None
