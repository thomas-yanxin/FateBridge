"""Midpoint source tables and mixed-pair geometry."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_midpoint_geometry import (
    GeometrySource,
    ReferenceAngleGeometry,
)


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
    arc_invariant_contacts: list[MixedPairContact] | None = None


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
