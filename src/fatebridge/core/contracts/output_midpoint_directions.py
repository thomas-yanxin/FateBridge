"""Midpoint directions and solar arc references."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_midpoint_geometry import (
    GeometrySource,
    PhysicalEphemerisFile,
    ReferenceAngleModel,
)


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
