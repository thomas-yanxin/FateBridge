"""Output contracts for Taiyi Shenshu."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, JsonValue, StrictBool, StrictInt

from fatebridge.core.contracts.base import FULL_FACT, PartialOutput, ProjectedOutput
from fatebridge.core.contracts.common import (
    AnalysisContext,
    CalendarContext,
    FourPillars,
    SolarTerm,
)
from fatebridge.core.receipt_models import Object, RunMetadata


class TaiyiCivilClockResolution(PartialOutput):
    method: str | None = None
    timezone: str | None = None
    wall_datetime: str | None = None
    input_utc_offset: str | None = None
    resolved_utc_offset: str | None = None
    fold: int | None = Field(default=None, ge=0, le=1)
    instant_utc: str | None = None
    timezone_rules: dict[str, str] | None = None
    scope: str | None = None


class TaiyiCivilLunarCalendar(PartialOutput):
    civil_date: str | None = None
    year: int | None = None
    month: int | None = None
    day: int | None = None
    is_leap_month: bool | None = None
    display: str | None = None
    clock_basis: str | None = None
    provider: str | None = None
    conversion_source: dict[str, JsonValue] | None = None
    conversion_source_status: str | None = None
    scope: str | None = None


class TaiyiHistoricalLeapHypothesis(PartialOutput):
    method: str | None = None
    leap_month: int | None = None


class TaiyiHistoricalCalendarDisagreement(PartialOutput):
    id: str | None = None
    year: int | None = None
    printed_leap_month: int | None = None
    alternative_hypotheses: list[TaiyiHistoricalLeapHypothesis] | None = None
    adjudicated: Literal[False] | None = None
    affects_selected_year: bool | None = None
    scope: str | None = None


class TaiyiHistoricalYearCalendar(PartialOutput):
    profile_id: str | None = None
    year_label_basis: str | None = None
    source_disagreements: list[TaiyiHistoricalCalendarDisagreement] | None = None
    calendar_algorithm_identity_adjudicated: Literal[False] | None = None
    provider: str | None = None
    calendar_title: str | None = None
    calendar_authors: str | None = None
    calendar_edition: str | None = None
    source_url: str | None = None
    calendar_tradition: str | None = None
    supported_start: str | None = None
    supported_end_exclusive: str | None = None
    civil_date: str | None = None
    year: int | None = None
    month: int | None = None
    day: int | None = None
    is_leap_month: bool | None = None
    year_ganzhi: str | None = None
    day_ganzhi: str | None = None
    weekday_sunday_zero: int | None = None
    printed_week_counter: int | None = None
    printed_cycle_counter: int | None = None
    source_month_start_julian: str | None = None
    month_start_gregorian: str | None = None
    next_month_start_gregorian: str | None = None
    source_year_start_julian: str | None = None
    year_start_gregorian: str | None = None
    source_next_year_start_julian: str | None = None
    next_year_start_gregorian: str | None = None
    source_pdf_page: int | None = None
    source_printed_page: int | None = None
    display: str | None = None
    counter_policy: str | None = None
    date_basis: str | None = None
    scope: str | None = None


class TaiyiHistoricalReference(PartialOutput):
    case_id: str | None = None
    source_date: str | None = None
    western_source_date: str | None = None
    western_source_calendar: str | None = None
    normalized_gregorian_date: str | None = None
    calendar_table_title: str | None = None
    calendar_table_authors: str | None = None
    calendar_table_edition: str | None = None
    calendar_table_source: str | None = None
    calendar_table_printed_page: int | None = None
    source_day_ganzhi: str | None = None
    actual_day_ganzhi: str | None = None
    day_ganzhi_matches: bool | None = None
    source_accumulation: int | None = None
    actual_accumulation: int | None = None
    counter_matches: bool | None = None
    source_hour_branch: str | None = None
    actual_hour_branch: str | None = None
    hour_branch_matches: bool | None = None
    scope: str | None = None


class TaiyiMonthCalendarReference(PartialOutput):
    source_label: str | None = None
    source_calendar_basis: str | None = None
    comparison_hypothesis: str | None = None
    lunar_month_start_julian: str | None = None
    lunar_month_start_gregorian: str | None = None
    next_lunar_month_start_gregorian: str | None = None
    calendar_title: str | None = None
    calendar_authors: str | None = None
    calendar_edition: str | None = None
    calendar_printed_page: int | None = None
    calendar_source: str | None = None
    source_month: int | None = None
    actual_nominal_month: int | None = None
    month_label_matches: bool | None = None
    source_shortcut_count: int | None = None
    actual_shortcut_count: int | None = None
    counter_matches: bool | None = None
    scope: str | None = None


class TaiyiMonthOrigin(PartialOutput):
    profile: str | None = None
    source: str | None = None
    cycle_year: int | None = None
    counted_year: int | None = None
    counted_year_basis: str | None = None
    counter_unit: str | None = None
    mean_lunation_counter: bool | None = None
    source_year_label_adjudicated: bool | None = None
    month_offset: int | None = None
    month_number_from_daxue: int | None = None
    nominal_year: int | None = None
    nominal_month: int | None = None
    year_label_policy: str | None = None
    source_epoch_year: int | None = None
    source_epoch_accumulation: int | None = None
    source_epoch_annual_accumulation: int | None = None
    annual_accumulation: int | None = None
    completed_annual_accumulation: int | None = None
    months_per_year: int | None = None
    tianzheng_preceding_months: int | None = None
    tianzheng_month_offset: int | None = None
    accumulation: int | None = None
    shortcut_epoch_year: int | None = None
    shortcut_inclusive_years: int | None = None
    shortcut_completed_years: int | None = None
    shortcut_completed_months: int | None = None
    shortcut_count: int | None = None
    full_minus_shortcut: int | None = None
    shared_cycle_lcm: int | None = None
    all_shared_cycles_aligned: bool | None = None
    cycle360: int | None = None
    palace_month_number: int | None = None
    source_chart_ju_unadjudicated: int | None = None
    calendar_reference: TaiyiMonthCalendarReference | None = None
    scope: str | None = None


class TaiyiDayOrigin(PartialOutput):
    source: str | None = None
    winter_clock: str | None = None
    winter_day_ganzhi: str | None = None
    winter_anchor_utc: str | None = None
    winter_anchor_provider: str | None = None
    origin_effective_date: str | None = None
    target_effective_date: str | None = None
    target_day_ganzhi: str | None = None
    accumulation: int | None = None
    day_boundary: str | None = None
    same_day_jiazi_included: bool | None = None
    same_day_selection_adjudicated: bool | None = None
    alternative_strict_previous_count: int | None = None
    scope: str | None = None


class TaiyiSourceComparison(PartialOutput):
    field: str | None = None
    source_value: str | int | None = None
    rule_derived_value: str | int | None = None
    scope: str | None = None
    source: str | None = None


class TaiyiTenCandidate(PartialOutput):
    id: str | None = None
    yang_position: str | None = None
    adopted: bool | None = None


class TaiyiTenRuleEvidence(PartialOutput):
    status: str | None = None
    basis: str | None = None
    sources: dict[str, str] | None = None
    unresolved: str | None = None


class TaiyiTenRecord(PartialOutput):
    label: str | None = None
    status: str | None = None
    palace: str | None = None
    palace_number: int | None = None
    yang_position: str | None = None
    period: int | None = None
    cycle_position: int | None = None
    sequence: list[str] | None = None
    rule: str | None = None
    yin_opposition: str | None = None
    reason: str | None = None
    source: str | None = None
    ordinal: int | None = None
    candidates: list[TaiyiTenCandidate] | None = None
    source_comparisons: list[TaiyiSourceComparison] | None = None
    rule_evidence: TaiyiTenRuleEvidence | None = None


class TaiyiTenJing(PartialOutput):
    status: str | None = None
    accumulation: int | None = None
    yin: bool | None = None
    records: dict[str, TaiyiTenRecord] | None = None
    source: str | None = None
    ruleset_id: str | None = None
    version: str | None = None
    author: str | None = None
    classical_author: str | None = None
    classical_acceptance_passed: bool | None = None
    scope: str | None = None


class TaiyiHourOrigin(PartialOutput):
    source: str | None = None
    winter_clock: str | None = None
    winter_anchor_utc: str | None = None
    winter_anchor_provider: str | None = None
    winter_effective_date: str | None = None
    winter_day_ganzhi: str | None = None
    origin_effective_date: str | None = None
    origin_day_ganzhi: str | None = None
    origin_clock: str | None = None
    origin_day_selection: str | None = None
    target_effective_date: str | None = None
    target_day_ganzhi: str | None = None
    day_number: int | None = None
    hour_number: int | None = None
    accumulation: int | None = None
    gate_cycle_counter: int | None = None
    day_boundary: str | None = None
    scope: str | None = None


class TaiyiGateCounter(PartialOutput):
    remaining_units_after_current: int | None = None
    source_modulus: int | None = None
    accumulation: int | None = None
    cycle_length: int | None = None
    cycle_unit: str | None = None
    cycle_position: int | None = None
    units_per_gate: int | None = None
    gate_index: int | None = None
    unit_in_gate: int | None = None
    duty_gate: str | None = None
    epoch_basis: str | None = None


class TaiyiGateRow(PartialOutput):
    number: int | None = None
    palace: str | None = None
    door: str | None = None
    spirit_positions: list[str] | None = None


class TaiyiGateCheck(PartialOutput):
    label: str | None = None
    source_path: str | None = None
    position: str | None = None
    sector_number: int | None = None
    door: str | None = None
    gate_source_path: str | None = None
    obstructs: bool | None = None
    incomplete_kind: str | None = None


class TaiyiGateAssessment(PartialOutput):
    status: str | None = None
    reason: str | None = None
    conditions_satisfied: bool | None = None
    checks: list[TaiyiGateCheck] | None = None
    frame_source_path: str | None = None
    source: str | None = None


class TaiyiGateFrame(PartialOutput):
    source_path: str | None = None
    status: str | None = None
    reason: str | None = None
    anchor_number: int | None = None
    anchor_palace: str | None = None
    anchor_source_path: str | None = None
    anchor_source_value: str | int | None = None
    duty_gate: str | None = None
    rows: list[TaiyiGateRow] | None = None
    three_gates: TaiyiGateAssessment | None = None


class TaiyiGateRuleset(PartialOutput):
    sector_rule_id: str | None = None
    sector_sources: list[str] | None = None
    id: str | None = None
    version: str | None = None
    author: str | None = None
    classical_author: str | None = None
    sources: list[str] | None = None
    classical_conformance: str | None = None
    classical_acceptance_passed: bool | None = None
    open_issues: list[str] | None = None


class TaiyiGates(PartialOutput):
    source_comparisons: list[TaiyiSourceComparison] | None = None
    source_counter_alternatives: list[TaiyiGateCounter] | None = None
    source_comparison_source: str | None = None
    source_comparison_scope: str | None = None
    status: str | None = None
    reason: str | None = None
    ruleset: TaiyiGateRuleset | None = None
    calculation_mode: str | None = None
    selected_profile: str | None = None
    scope: str | None = None
    counter: TaiyiGateCounter | None = None
    moving_frame: TaiyiGateFrame | None = None
    old_open_frames: dict[str, TaiyiGateFrame] | None = None
    old_open_summary: dict[str, TaiyiGateFrame] | None = None
    dingmu_comparison_frame: TaiyiGateFrame | None = None
    dingmu_comparison_source: str | None = None


class TaiyiDeterminateRotation(PartialOutput):
    ruler_branch: str | None = None
    hegod: str | None = None
    wenchang: str | None = None
    forward_steps: int | None = None


class TaiyiDeterminateSourceDifference(PartialOutput):
    field: str | None = None
    source_value: int | None = None
    rule_derived_value: int | None = None


class TaiyiDeterminate(PartialOutput):
    source_disagreements: list[TaiyiDeterminateSourceDifference] | None = None
    source_comparison_source: str | None = None
    source_comparison_scope: str | None = None
    status: str | None = None
    reason: str | None = None
    marker: str | None = None
    count: int | None = None
    general: int | None = None
    vice_general: int | None = None
    rotation: TaiyiDeterminateRotation | None = None
    source: str | None = None
    scope: str | None = None


class TaiyiConditionSource(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    classical_author: str | None = None
    source: str | None = None
    conformance: str | None = None
    relation_profile: str | None = None
    relation_sources: list[str] | None = None
    relation_scope: str | None = None
    coverage_policy: str | None = None


class TaiyiConditionBlocker(PartialOutput):
    source_path: str | None = None
    name: str | None = None
    subject: str | None = None
    variant: str | None = None


class TaiyiConditionFact(PartialOutput):
    field: str | None = None
    value: int | None = None


class TaiyiConditionUnassessed(PartialOutput):
    id: str | None = None
    subjects: list[str] | None = None
    basis: list[TaiyiConditionFact] | None = None
    reason: str | None = None


class TaiyiConditionClause(PartialOutput):
    id: str | None = None
    label: str | None = None
    satisfied: bool | None = None
    assessed_satisfied: bool | None = None
    blockers: list[TaiyiConditionBlocker] | None = None
    unassessed: list[TaiyiConditionUnassessed] | None = None


class TaiyiFiveGenerals(PartialOutput):
    conditions_satisfied: bool | None = None
    assessed_conditions_satisfied: bool | None = None
    same_core_coverage_checked: bool | None = None
    clauses: list[TaiyiConditionClause] | None = None


class TaiyiThreeGates(TaiyiGateAssessment):
    pass


class TaiyiConditionAssessment(PartialOutput):
    ruleset: TaiyiConditionSource | None = None
    five_generals: TaiyiFiveGenerals | None = None
    three_gates: TaiyiThreeGates | None = None
    menju_jiangfa: bool | None = None
    adjudication: str | None = None
    summary: str | None = None
    scope: str | None = None


class TaiyiCountComponents(PartialOutput):
    ten: int | None = None
    five: int | None = None
    one: int | None = None


class TaiyiCountContext(PartialOutput):
    reference: str | None = None
    field: str | None = None
    value: str | int | None = None
    polarity: str | None = None
    count_parity: str | None = None
    is_harmonious: bool | None = None
    reading: str | None = None


class TaiyiCountMembership(PartialOutput):
    profile_id: str | None = None
    harmony_tiers: list[str] | None = None
    three_talents_listed: bool | None = None


class TaiyiCountReading(PartialOutput):
    value: int | None = None
    missing_labels: list[str] | None = None
    components: TaiyiCountComponents | None = None
    three_talents_inferred: bool | None = None
    duse: bool | None = None
    length_label: str | None = None
    is_long: bool | None = None
    number_families: list[str] | None = None
    source_memberships: list[TaiyiCountMembership] | None = None
    literal_rank_status: str | None = None
    literal_rank_consensus: str | None = None
    subject: str | None = None
    field: str | None = None
    contexts: list[TaiyiCountContext] | None = None


class TaiyiCountReadingRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    primary_sources: list[str] | None = None


class TaiyiCountReadingSource(PartialOutput):
    id: str | None = None
    title: str | None = None
    source: str | None = None
    evidence_level: str | None = None


class TaiyiCountUnadjudicatedReading(PartialOutput):
    profile_id: str | None = None
    kind: str | None = None
    reading: str | None = None
    scope: str | None = None
    values: list[int] | None = None
    status: str | None = None


class TaiyiCountAssessment(PartialOutput):
    ruleset: TaiyiCountReadingRuleset | None = None
    sources: list[TaiyiCountReadingSource] | None = None
    unadjudicated_source_readings: list[TaiyiCountUnadjudicatedReading] | None = None
    entries: list[TaiyiCountReading] | None = None
    overall_harmony_assessed: bool | None = None
    scope: str | None = None


class TaiyiElementalRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    source_title: str | None = None
    classical_author: str | None = None
    source_urls: list[str] | None = None


class TaiyiElementalEye(PartialOutput):
    camp: str | None = None
    role: str | None = None
    actual_path: str | None = None
    position: str | None = None
    source_name: str | None = None
    element: str | None = None


class TaiyiElementalSpatial(PartialOutput):
    status: str | None = None
    present: StrictBool | None = None
    pattern_paths: list[str] | None = None
    scope: str | None = None


class TaiyiElementalReading(PartialOutput):
    kind: str | None = None
    reading: str | None = None
    source: str | None = None
    applicability: str | None = None
    scope: str | None = None
    overall_outcome_assessed: StrictBool | None = None


class TaiyiElementalAssessment(PartialOutput):
    ruleset: TaiyiElementalRuleset | None = None
    calculation_mode: str | None = None
    source_day_usage: str | None = None
    full_daily_na_yin_method_verified: StrictBool | None = None
    role_scope: str | None = None
    method_scope: str | None = None
    scope: str | None = None
    implemented_spatial_guan: TaiyiElementalSpatial | None = None
    status: str | None = None
    reason: str | None = None
    eyes: list[TaiyiElementalEye] | None = None
    relation: str | None = None
    relation_label: str | None = None
    elemental_control: StrictBool | None = None
    controlling_camp: str | None = None
    source_interpretation: TaiyiElementalReading | None = None


class TaiyiEnclosureRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    classical_author: str | None = None
    sources: list[str] | None = None


class TaiyiPrincipalEnclosure(PartialOutput):
    status: str | None = None
    present: bool | None = None
    pattern_paths: list[str] | None = None
    meaning: str | None = None


class TaiyiUnassessedEnclosure(PartialOutput):
    name: str | None = None
    status: str | None = None
    reason: str | None = None


class TaiyiPairFact(PartialOutput):
    field: str | None = None
    value: str | int | None = None


class TaiyiPairPattern(PartialOutput):
    name: str | None = None
    subject: str | None = None
    variant: str | None = None
    basis: list[TaiyiPairFact] | None = None
    traditional_meaning: str | None = None
    source: str | None = None
    relation_profile: str | None = None
    scope: str | None = None


class TaiyiPairEnclosure(TaiyiPrincipalEnclosure):
    patterns: list[TaiyiPairPattern] | None = None


class TaiyiEnclosureAssessment(PartialOutput):
    ruleset: TaiyiEnclosureRuleset | None = None
    principal_enclosure: TaiyiPrincipalEnclosure | None = None
    two_general_ruleset: TaiyiEnclosureRuleset | None = None
    two_general_enclosure: TaiyiPairEnclosure | None = None
    unassessed: list[TaiyiUnassessedEnclosure] | None = None
    scope: str | None = None


class TaiyiLongEpoch(PartialOutput):
    year: int | None = None
    accumulation: int | None = None
    equivalent_short_epoch_accumulation: int | None = None
    equivalence_modulus: int | None = None


class TaiyiLongMarker(PartialOutput):
    position: str | None = None
    palace: str | None = None
    palace_number: int | None = None
    space: str | None = None
    accumulation: int | None = None
    cycle_length: int | None = None
    cycle_year: int | None = None
    years_per_position: int | None = None
    position_index: int | None = None
    year_in_palace: int | None = None
    label: str | None = None
    source_section: str | None = None
    source_method: str | None = None
    source_reference: str | None = None
    source_edition: str | None = None
    epoch_id: str | None = None
    classical_palace_name: str | None = None
    administration_phase: str | None = None
    table_position: str | None = None
    table_disagreement: bool | None = None
    table_row: str | None = None
    table_yuan: str | None = None


class TaiyiLongRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    classical_author: str | None = None
    source: str | None = None
    classical_conformance: str | None = None
    classical_acceptance_passed: bool | None = None


class TaiyiLongCycles(PartialOutput):
    year: int | None = None
    status: str | None = None
    selected_mode: str | None = None
    time_granularity: str | None = None
    ruleset: TaiyiLongRuleset | None = None
    epochs: dict[str, TaiyiLongEpoch] | None = None
    counting_convention: str | None = None
    records: dict[str, TaiyiLongMarker] | None = None
    interpretation_scope: str | None = None
    unresolved: list[str] | None = None


class TaiyiLongSummary(PartialOutput):
    status: str | None = None
    time_granularity: str | None = None
    year: int | None = None
    ruleset_id: str | None = None
    source: str | None = None
    positions: dict[str, str] | None = None
    table_disagreements: list[str] | None = None
    scope: str | None = None


class TaiyiMatrixLocator(PartialOutput):
    scan_page: StrictInt | None = None
    column_from_right: StrictInt | None = None
    slot_from_top: StrictInt | None = None


class TaiyiMatrixColumn(PartialOutput):
    text: str | None = None
    locator: TaiyiMatrixLocator | None = None


class TaiyiMatrixCell(PartialOutput):
    id: str | None = None
    source_spirit: str | None = None
    wenchang_position: str | None = None
    taiyi_number: StrictInt | None = None
    condition_column: TaiyiMatrixColumn | None = None
    result_column: TaiyiMatrixColumn | None = None
    reading_status: str | None = None


class TaiyiMatrixGeometry(PartialOutput):
    field: str | None = None
    label: str | None = None
    actual_path: str | None = None
    position: str | None = None
    distance: StrictInt | None = None
    status: str | None = None
    same_palace: StrictBool | None = None
    opposite: StrictBool | None = None
    inner_adjacent: StrictBool | None = None
    outer_adjacent: StrictBool | None = None
    adjacent: StrictBool | None = None


class TaiyiMatrixCandidate(PartialOutput):
    field: str | None = None
    actual_path: str | None = None
    position: str | None = None
    matches_geometry: StrictBool | None = None


class TaiyiMatrixClause(PartialOutput):
    column: str | None = None
    text: str | None = None
    kind: str | None = None
    candidates: list[TaiyiMatrixCandidate] | None = None
    actor: str | None = None
    predicate: str | None = None
    role_resolution: str | None = None
    source_name_scope: str | None = None


class TaiyiMatrixComparison(PartialOutput):
    resolved_eye_claims: StrictInt | None = None
    matching_eye_geometry: StrictInt | None = None
    different_eye_geometry: StrictInt | None = None
    unknown_eye_geometry: StrictInt | None = None
    unqualified_general_claims: StrictInt | None = None
    unadjudicated_clauses: StrictInt | None = None
    blank_columns: StrictInt | None = None
    source_lacuna: StrictBool | None = None
    whole_cell_conformance_assessed: StrictBool | None = None


class TaiyiVictoryMatrixAssessment(PartialOutput):
    ruleset: TaiyiElementalRuleset | None = None
    calculation_mode: str | None = None
    role_scope: str | None = None
    method_scope: str | None = None
    scope: str | None = None
    table_applicability_verified: StrictBool | None = None
    source_outcome_applied: StrictBool | None = None
    classical_acceptance_passed: StrictBool | None = None
    status: str | None = None
    reason: str | None = None
    source_cell: TaiyiMatrixCell | None = None
    actual_geometry: list[TaiyiMatrixGeometry] | None = None
    clauses: list[TaiyiMatrixClause] | None = None
    comparison_summary: TaiyiMatrixComparison | None = None


class TaiyiOppositionFact(PartialOutput):
    field: str | None = None
    value: str | int | None = None


class TaiyiAdditionalOppositionReading(PartialOutput):
    source_name: str | None = None
    matches_selected_taiyi_reference: bool | None = None
    scope: str | None = None


class TaiyiOppositionSourceComparison(PartialOutput):
    ju: int | None = None
    source_name: str | None = None
    source_reading: str | None = None
    source: str | None = None
    expected_taiyi_number: int | None = None
    expected_general_number: int | None = None
    numeric_values_match: bool | None = None
    opposition_matches: bool | None = None
    additional_readings: list[TaiyiAdditionalOppositionReading] | None = None
    scope: str | None = None


class TaiyiOppositionEntry(PartialOutput):
    subject: str | None = None
    field: str | None = None
    palace: str | None = None
    taiyi_palace: str | None = None
    relative_steps: int | None = None
    is_opposite: bool | None = None
    status: str | None = None
    classical_names: list[str] | None = None
    name_status: str | None = None
    basis: list[TaiyiOppositionFact] | None = None
    source_comparison: TaiyiOppositionSourceComparison | None = None


class TaiyiOppositionRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    classical_sources: list[str] | None = None


class TaiyiOppositionAssessment(PartialOutput):
    ruleset: TaiyiOppositionRuleset | None = None
    entries: list[TaiyiOppositionEntry] | None = None
    main_names_unified: bool | None = None
    scope: str | None = None


class TaiyiShijiRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    classical_author: str | None = None
    source: str | None = None
    corroboration: str | None = None


class TaiyiShijiPair(PartialOutput):
    step: int | None = None
    heaven_spirit: str | None = None
    earth_spirit: str | None = None


class TaiyiYinShijiVariant(PartialOutput):
    ju: int | None = None
    profile: str | None = None
    shiji: str | None = None
    shiji_literal: str | None = None
    guest_count: int | None = None
    source: str | None = None


class TaiyiShijiDerivation(PartialOutput):
    ruleset: TaiyiShijiRuleset | None = None
    shiji_profile: str | None = None
    requested_shiji_profile: str | None = None
    selected_source: str | None = None
    guest_count_basis: str | None = None
    status: str | None = None
    reason: str | None = None
    scope: str | None = None
    wenchang: str | None = None
    jishen: str | None = None
    earth_anchor: str | None = None
    direction: str | None = None
    step_count: int | None = None
    pairs: list[TaiyiShijiPair] | None = None
    derived_shiji: str | None = None
    wenchang_path: str | None = None
    jishen_path: str | None = None
    actual_path: str | None = None
    actual_shiji: str | None = None
    matches_actual: bool | None = None
    yin_37_43_44_variants: list[TaiyiYinShijiVariant] | None = None


class TaiyiSourceAlignmentRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    classical_author: str | None = None
    source_title: str | None = None
    facsimile_source: str | None = None
    source: str | None = None
    count_rule_source: str | None = None


class TaiyiSourcePosition(PartialOutput):
    field: str | None = None
    actual_path: str | None = None
    actual_value: str | int | None = None
    source_value: str | int | None = None
    source_literal: str | None = None
    transcription_literal: str | None = None
    initial_manual_literal: str | None = None
    source_layer: str | None = None
    matches: bool | None = None


class TaiyiSourceCountStep(PartialOutput):
    palace: str | None = None
    value: int | None = None
    kind: str | None = None


class TaiyiSourceCountTrace(PartialOutput):
    count: int | None = None
    path: list[TaiyiSourceCountStep] | None = None
    terminal_palace: str | None = None
    terminal_excluded: bool | None = None
    counting_rule: str | None = None
    source: str | None = None


class TaiyiSourceCount(PartialOutput):
    camp: str | None = None
    field: str | None = None
    marker_field: str | None = None
    actual_count_path: str | None = None
    actual_marker_path: str | None = None
    actual_marker: str | None = None
    source_marker: str | None = None
    actual_count: int | None = None
    source_table_count: int | None = None
    source_layer: str | None = None
    count_matches: bool | None = None
    same_inputs: bool | None = None
    source_recount_matches_table: bool | None = None
    source_position_recount: TaiyiSourceCountTrace | None = None
    diagnosis: str | None = None


class TaiyiSourceFacsimileCheck(PartialOutput):
    id: str | None = None
    field: str | None = None
    text_reading: str | None = None
    initial_manual_reading: str | None = None
    facsimile_reading: str | None = None
    page: int | None = None
    status: str | None = None
    selected_reading: str | None = None


class TaiyiSourceAlignmentSummary(PartialOutput):
    status: str | None = None
    position_disagreements: list[str] | None = None
    count_disagreements: list[str] | None = None
    source_internal_count_disagreements: list[str] | None = None
    scope: str | None = None


class TaiyiEditionImage(PartialOutput):
    book_number: int | None = None
    image_number: int | None = None
    url: str | None = None


class TaiyiEditionObservation(PartialOutput):
    field: str | None = None
    actual_value: str | int | None = None
    selected_source_value: str | int | None = None
    selected_source_literal: str | None = None
    edition_value: str | int | None = None
    edition_literal: str | None = None
    matches_current: bool | None = None
    matches_selected_source: bool | None = None


class TaiyiEditionComparison(PartialOutput):
    source_id: str | None = None
    source_title: str | None = None
    classical_author: str | None = None
    provider: str | None = None
    catalog_identity: str | None = None
    catalog_url: str | None = None
    edition: str | None = None
    bibliographic_note: str | None = None
    chapter_image_url: str | None = None
    images: list[TaiyiEditionImage] | None = None
    location: str | None = None
    yin_dun: bool | None = None
    ju: int | None = None
    observations: list[TaiyiEditionObservation] | None = None
    required_observations: int | None = None
    matching_current_observations: int | None = None
    matching_selected_source_observations: int | None = None
    review_status: str | None = None
    textual_lineage_independence_established: bool | None = None
    whole_work_acceptance_passed: bool | None = None
    scope: str | None = None


class TaiyiSourceAlignment(PartialOutput):
    ruleset: TaiyiSourceAlignmentRuleset | None = None
    status: str | None = None
    reason: str | None = None
    case_id: str | None = None
    yin_dun: bool | None = None
    ju: int | None = None
    facsimile_page: int | None = None
    facsimile_columns_from_right: list[int] | None = None
    positions: list[TaiyiSourcePosition] | None = None
    counts: list[TaiyiSourceCount] | None = None
    facsimile_readings: list[TaiyiSourceFacsimileCheck] | None = None
    edition_comparisons: list[TaiyiEditionComparison] | None = None
    summary: TaiyiSourceAlignmentSummary | None = None
    scope: str | None = None


class TaiyiCounterGroup(PartialOutput):
    number: int | None = None
    position: int | None = None
    size: int | None = None


class TaiyiCounterCycles(PartialOutput):
    ruleset_id: str | None = None
    version: str | None = None
    source: str | None = None
    paths_relative_to: str | None = None
    counter_path: str | None = None
    actual_ju_path: str | None = None
    counter: int | None = None
    calculation_mode: str | None = None
    counter_unit: str | None = None
    completed_cycles_before_current360: int | None = None
    position360: int | None = None
    ji60: TaiyiCounterGroup | None = None
    yuan72: TaiyiCounterGroup | None = None
    actual_kook_number: int | None = None
    calendar_ganzhi_alignment: str | None = None
    scope: str | None = None


class TaiyiCore(PartialOutput):
    yin_dun: bool | None = None
    ruler_branch: str | None = None
    ruler_label: str | None = None
    accumulation: int | None = None
    taiyi_number: int | None = None
    chenji: str | None = None
    dingmu: str | None = None
    diyi: str | None = None
    guest_count: Annotated[int | None, FULL_FACT] = None
    guest_count_des: list[str] | None = None
    guest_general: int | None = None
    guest_vice_general: int | None = None
    heshen: str | None = None
    jishen: str | None = None
    junji: str | None = None
    kook_number: int | None = None
    kook_year: str | None = None
    main_calculation: str | None = None
    table_policy: str | None = None
    main_count: Annotated[int | None, FULL_FACT] = None
    main_count_des: list[str] | None = None
    main_general: int | None = None
    main_vice_general: int | None = None
    minji: str | None = None
    set_count: int | None = None
    set_general: int | None = None
    set_vice_general: int | None = None
    shiji: str | None = None
    shiji_profile: str | None = None
    requested_shiji_profile: str | None = None
    sishen: str | None = None
    suijun: str | None = None
    taiyi_position: str | None = None
    tianyi: str | None = None
    wenchang_position: str | None = None
    wufu: int | None = None
    zhifu: str | None = None


class TaiyiPalace(PartialOutput):
    markers: list[str] | None = None
    palace: str | None = None


class TaiyiRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    classical_author: str | None = None
    source_title: str | None = None
    source_kind: str | None = None
    sources: dict[str, str] | None = None
    time_granularity: str | None = None
    classical_conformance: str | None = None
    classical_acceptance_passed: bool | None = None
    unresolved: list[str] | None = None


class TaiyiCalendarRules(PartialOutput):
    anchor_ephemeris_model: str | None = None
    winter_anchor_ephemeris_model: str | None = None
    civil_clock_resolution: TaiyiCivilClockResolution | None = None
    year_profile: str | None = None
    shiji_profile: str | None = None
    historical_calendar: TaiyiHistoricalYearCalendar | None = None
    civil_lunar_calendar: TaiyiCivilLunarCalendar | None = None
    month_profile: str | None = None
    month_origin: TaiyiMonthOrigin | None = None
    input_calendar: str | None = None
    historical_date_reference: TaiyiHistoricalReference | None = None
    day_profile: str | None = None
    day_origin: TaiyiDayOrigin | None = None
    palace_day_number: int | None = None
    hour_profile: str | None = None
    hour_origin: TaiyiHourOrigin | None = None
    convention: str | None = None
    calculation_mode: str | None = None
    anchor_name: str | None = None
    anchor_utc: str | None = None
    anchor_provider: str | None = None
    counter: int | None = None
    boundary_instant_basis: str | None = None
    ruler_branch_basis: str | None = None
    heshen_branch_basis: str | None = None
    clock_basis: str | None = None
    cycle_year: int | None = None
    month_offset: int | None = None
    leap_month_policy: str | None = None
    anchor_clock: str | None = None
    target_clock: str | None = None
    double_hour_start: str | None = None
    initial_interval: str | None = None
    dst_policy: str | None = None
    counter_rule_source: str | None = None
    counter_formula: str | None = None
    anchor_precision: str | None = None
    seconds_from_anchor: float | None = None
    target_slot: int | None = None
    anchor_slot: int | None = None
    year: int | None = None
    year_boundary: str | None = None
    year_boundary_status: str | None = None
    year_ganzhi: str | None = None
    civil_datetime: str | None = None
    timezone: str | None = None
    solar_correction_affects_year: bool | None = None
    pillars_role: str | None = None


class TaiyiEvidenceFact(PartialOutput):
    field: str | None = None
    value: str | int | None = None


class TaiyiPattern(PartialOutput):
    name: str | None = None
    subject: str | None = None
    variant: str | None = None
    basis: list[TaiyiEvidenceFact] | None = None
    traditional_meaning: str | None = None
    source: str | None = None
    supplementary_sources: list[str] | None = None
    relation_profile: str | None = None
    scope: str | None = None


class TaiyiWinterOriginSelection(PartialOutput):
    policy_id: str | None = None
    selection_switch_basis: str | None = None
    selected_winter_utc: str | None = None
    count_origin_date: str | None = None
    count_origin_clock: str | None = None
    clock_basis: str | None = None
    classical_source_scope: str | None = None
    classical_activation_adjudicated: bool | None = None
    scope: str | None = None


class Taiyi(PartialOutput):
    winter_origin_selection: TaiyiWinterOriginSelection | None = None
    solar_anchors: dict[str, SolarTerm] | None = None
    solar_anchor_scope: str | None = None
    counter_cycles: TaiyiCounterCycles | None = None
    shiji_derivation: TaiyiShijiDerivation | None = None
    elemental_guan_assessment: TaiyiElementalAssessment | None = None
    victory_matrix_assessment: TaiyiVictoryMatrixAssessment | None = None
    count_source_assessment: TaiyiSourceAlignment | None = None
    count_assessment: TaiyiCountAssessment | None = None
    opposition_assessment: TaiyiOppositionAssessment | None = None
    enclosure_assessment: TaiyiEnclosureAssessment | None = None
    ten_jing: TaiyiTenJing | None = None
    fate_palaces: Object | None = None
    day_source_comparisons: list[TaiyiSourceComparison] | None = None
    gates: TaiyiGates | None = None
    determinate_calculation: TaiyiDeterminate | None = None
    condition_assessment: TaiyiConditionAssessment | None = None
    long_cycles: TaiyiLongCycles | None = None
    long_cycle_summary: TaiyiLongSummary | None = None
    extra_palace_marks: list[TaiyiPalace] | None = None
    engine: Annotated[str | None, FULL_FACT] = None
    accumulation_label: str | None = None
    core_board: Annotated[TaiyiCore | None, FULL_FACT] = None
    life_method: Annotated[str | None, FULL_FACT] = None
    palace_marks: Annotated[list[TaiyiPalace] | None, FULL_FACT] = Field(
        default=None, min_length=8
    )
    center_marks: TaiyiPalace | None = None
    ruleset: Annotated[TaiyiRuleset | None, FULL_FACT] = None
    calendar_rules: TaiyiCalendarRules | None = None
    calendar_summary: TaiyiCalendarRules | None = None
    pattern_summary: Object | None = None
    patterns: list[TaiyiPattern] | None = None
    interpretation_scope: Object | None = None
    rotation: str | None = None
    style_label: str | None = None
    taiyi_palace: str | None = None
    wenchang_palace: str | None = None
    big_pattern: str | None = None
    small_pattern: str | None = None


class TaiyiOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    calendar_context: CalendarContext | None = None
    four_pillars: FourPillars | None = None
    taiyi: Taiyi | None = None
