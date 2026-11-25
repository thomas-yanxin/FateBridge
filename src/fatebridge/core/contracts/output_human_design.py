"""Projectable Human Design calculation and evidence contracts."""

from pydantic import JsonValue

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.response_models import ProjectedOutput, RunMetadata


class Activation(PartialOutput):
    body: str | None = None
    longitude: float | None = None
    longitude_speed: float | None = None
    ephemeris_model: str | None = None
    return_flags: int | None = None
    native_return_flag_model: str | None = None
    derived_from: str | None = None
    derivation_source_longitude: float | None = None
    gate: int | None = None
    center: str | None = None
    line: int | None = None
    color: int | None = None
    tone: int | None = None
    base: int | None = None
    tone_orientation: str | None = None
    gate_start_longitude: float | None = None
    line_boundary_distance_degrees: float | None = None
    base_boundary_distance_arcseconds: float | None = None


class Activations(PartialOutput):
    personality: list[Activation] | None = None
    design: list[Activation] | None = None


class HDChannel(PartialOutput):
    id: str | None = None
    gates: list[int] | None = None
    centers: list[str] | None = None
    circuit: str | None = None
    personality_complete: bool | None = None
    design_complete: bool | None = None
    mixed_only: bool | None = None


class HDCenter(PartialOutput):
    status: str | None = None
    activated_gates: list[int] | None = None


class HDDefinition(PartialOutput):
    kind: str | None = None
    components: list[list[str]] | None = None
    single_gate_bridges: list[int] | None = None
    bridge_scope: str | None = None


class HDBridgeWitness(PartialOutput):
    added_gates: list[int] | None = None
    newly_completed_channel_ids: list[str] | None = None
    result_components: list[list[str]] | None = None
    merged_original_component_indices: list[list[int]] | None = None
    connects_all_original_components: bool | None = None


class HDBridgeSearch(PartialOutput):
    expanded_states: int | None = None
    distinct_generated_states: int | None = None
    cost: str | None = None


class HDBridgeRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    source_url: str | None = None
    graph_source_url: str | None = None


class HDDefinitionBridging(PartialOutput):
    method_id: str | None = None
    status: str | None = None
    original_components: list[list[str]] | None = None
    original_component_count: int | None = None
    single_gate_merges: list[HDBridgeWitness] | None = None
    minimum_added_gate_count: int | None = None
    minimum_solution_count: int | None = None
    minimum_solutions: list[HDBridgeWitness] | None = None
    minimum_solutions_preview: list[HDBridgeWitness] | None = None
    preview_is_truncated: bool | None = None
    all_minimum_solutions_enumerated: bool | None = None
    search: HDBridgeSearch | None = None
    source_url: str | None = None
    source_scope: str | None = None
    ruleset: HDBridgeRuleset | None = None
    scope: str | None = None


class HDCircuitEntry(PartialOutput):
    id: str | None = None
    group: str | None = None
    channel_ids: list[str] | None = None
    channel_count: int | None = None
    meaning: str | None = None


class HDIntegration(PartialOutput):
    activated_gates: list[int] | None = None
    completed_channel_ids: list[str] | None = None
    all_four_channels_complete: bool | None = None
    adjacent_individual_channel_ids: list[str] | None = None


class HDCircuitGroupMembership(PartialOutput):
    method_id: str | None = None
    source_url: str | None = None
    source_catalog_sha256: str | None = None
    integration_group: str | None = None
    integration_is_separately_reported_subset: bool | None = None
    scope: str | None = None


class HDCircuitry(PartialOutput):
    topology_completion: dict[str, JsonValue] | None = None
    defined_channel_count: int | None = None
    circuits: list[HDCircuitEntry] | None = None
    group_channel_counts: dict[str, int] | None = None
    group_membership: HDCircuitGroupMembership | None = None
    integration: HDIntegration | None = None
    source_url: str | None = None
    integration_source_url: str | None = None
    scope: str | None = None


class HDConnectionPath(PartialOutput):
    centers: list[str] | None = None
    channel_ids: list[str] | None = None


class HDAuthorityPriorityCheck(PartialOutput):
    center: str | None = None
    defined: bool | None = None


class HDClassificationEvidence(PartialOutput):
    defined_centers: list[str] | None = None
    motor_to_throat_paths: list[HDConnectionPath] | None = None
    authority_priority_checks: list[HDAuthorityPriorityCheck] | None = None
    selected_authority: str | None = None
    authority_paths: list[HDConnectionPath] | None = None
    no_inner_authority: bool | None = None
    scope: str | None = None


class BodyGraph(PartialOutput):
    type: str | None = None
    subtype: str | None = None
    authority: str | None = None
    strategy: str | None = None
    motor_to_throat: bool | None = None
    classification_evidence: HDClassificationEvidence | None = None
    definition: HDDefinition | None = None
    centers: dict[str, HDCenter] | None = None
    channels: list[HDChannel] | None = None
    circuitry: HDCircuitry | None = None
    activated_gates: list[int] | None = None
    hanging_gates: list[int] | None = None
    gate_sources: dict[str, list[str]] | None = None


class DesignSolver(PartialOutput):
    target_solar_arc_degrees: float | None = None
    residual_degrees: float | None = None
    bracket_width_seconds: float | None = None
    days_before_birth: float | None = None
    iterations: int | None = None
    method: str | None = None
    civil_elapsed_days: float | None = None
    birth_jd_tt: float | None = None
    design_jd_tt: float | None = None
    utc_is_leap_second: bool | None = None
    utc_label_status: str | None = None
    precision_scope: str | None = None


class HDTimeScale(PartialOutput):
    jd_tt: float | None = None
    jd_ut1: float | None = None
    method: str | None = None
    future_leap_seconds_assumed_unchanged: bool | None = None
    utc_is_leap_second: bool | None = None
    utc_label_status: str | None = None


class HDTimeScales(PartialOutput):
    personality: HDTimeScale | None = None
    design: HDTimeScale | None = None


class IncarnationCross(PartialOutput):
    gates: list[int] | None = None
    order: list[str] | None = None
    angle: str | None = None
    name_status: str | None = None
    name: str | None = None
    source_pdf_page_one_based: int | None = None
    source_url: str | None = None
    interpretation_scope: str | None = None


class HDFixingTrigger(PartialOutput):
    side: str | None = None
    body: str | None = None
    gate: int | None = None
    line: int | None = None
    relation: str | None = None
    calculation_path: str | None = None


class HDFixingPlanets(PartialOutput):
    exaltation: list[HDFixingTrigger] | None = None
    detriment: list[HDFixingTrigger] | None = None


class HDLineFixing(PartialOutput):
    side: str | None = None
    body: str | None = None
    gate: int | None = None
    line: int | None = None
    calculation_path: str | None = None
    gate_name: str | None = None
    source_pdf_page_one_based: int | None = None
    exaltation_planet: str | None = None
    detriment_planet: str | None = None
    polarity_kind: str | None = None
    status: str | None = None
    fixing_state: str | None = None
    recipient_kind: str | None = None
    reading: str | None = None
    fixing_planets: HDFixingPlanets | None = None
    fixing_rule_id: str | None = None
    scope: str | None = None


class HDChannelIdentifier(PartialOutput):
    gates: list[int] | None = None
    name: str | None = None
    source_pdf_page_one_based: int | None = None


class HDDepthEvidence(PartialOutput):
    line_fixings: list[HDLineFixing] | None = None
    fixing_summary: dict[str, JsonValue] | None = None
    fixing_policy: dict[str, JsonValue] | None = None
    channel_identifiers: list[HDChannelIdentifier] | None = None
    source_url: str | None = None
    source_pdf_sha256: str | None = None
    fixing_rule_source: str | None = None
    node_fixing_exclusion_source: str | None = None
    scope: str | None = None


class HDReadingBasis(PartialOutput):
    path: str | None = None
    value: JsonValue | None = None


class HDProfileLine(PartialOutput):
    side: str | None = None
    line: int | None = None
    traditional_polarity: str | None = None
    archetype: str | None = None
    trigram: str | None = None
    basis: list[HDReadingBasis] | None = None


class HDProfileGeometry(PartialOutput):
    angle: str | None = None
    label: str | None = None
    source_term: str | None = None
    source_url: str | None = None


class HDSixthLineProcess(PartialOutput):
    applicable: bool | None = None
    affected_sides: list[str] | None = None
    phase_assignment_status: str | None = None
    current_phase: str | None = None
    computed_return_dates: dict[str, JsonValue] | None = None
    traditional_phase_order: list[str] | None = None
    source_cycle_markers: dict[str, JsonValue] | None = None
    source_url: str | None = None
    scope: str | None = None


class HDProfileRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    source_author: str | None = None
    source_catalog_id: str | None = None


class HDProfileEvidence(PartialOutput):
    status: str | None = None
    profile: str | None = None
    lines: list[HDProfileLine] | None = None
    geometry: HDProfileGeometry | None = None
    sixth_line_process: HDSixthLineProcess | None = None
    source_catalog_sha256: str | None = None
    source_urls: list[str] | None = None
    scope: str | None = None
    ruleset: HDProfileRuleset | None = None


class HDVariableArrow(PartialOutput):
    component: str | None = None
    side: str | None = None
    body_pair: list[str] | None = None
    position: str | None = None
    status: str | None = None
    tone: int | None = None
    orientation: str | None = None
    letter: str | None = None
    pair_tones_consistent: bool | None = None
    basis: list[HDReadingBasis] | None = None
    ephemeris_models: list[str] | None = None


class HDVariables(PartialOutput):
    status: str | None = None
    code: str | None = None
    arrows: list[HDVariableArrow] | None = None
    personality_colors: dict[str, JsonValue] | None = None
    notation_order: list[str] | None = None
    source_urls: list[str] | None = None
    subdivision_accuracy_certified: bool | None = None
    scope: str | None = None


class HDReadingStatement(PartialOutput):
    id: str | None = None
    text: str | None = None
    basis: list[HDReadingBasis] | None = None
    source_urls: list[str] | None = None


class HDInterpretation(PartialOutput):
    coordinate_frame_meaning: str | None = None
    historical_polarity_context: dict[str, JsonValue] | None = None
    profile_partition_context: dict[str, JsonValue] | None = None
    apparent_position_context: dict[str, JsonValue] | None = None
    gate_activation_context: dict[str, JsonValue] | None = None
    personality_color_meaning: str | None = None
    birth_interval_meaning: str | None = None
    node_comparison_meaning: str | None = None
    birth_clock_meaning: str | None = None
    expanded_cross_name_meaning: str | None = None
    circuit_topology_meaning: str | None = None
    time_scope: str | None = None
    ephemeris_scope: str | None = None
    variables_meaning: str | None = None
    design_time_precision_meaning: str | None = None
    line_fixing_meaning: str | None = None
    type_meaning: str | None = None
    authority_meaning: str | None = None
    authority_structure: str | None = None
    definition_meaning: str | None = None
    definition_structure: str | None = None
    circuitry_meaning: str | None = None
    profile_meaning: str | None = None
    basis: list[str] | None = None
    statements: list[HDReadingStatement] | None = None
    reading_policy: str | None = None


class HDRuleset(PartialOutput):
    id: str | None = None
    author: str | None = None
    version: str | None = None
    source_kind: str | None = None
    sources: dict[str, str] | None = None
    scope: str | None = None


class HDRuleTrace(PartialOutput):
    rule_id: str | None = None
    ruleset_id: str | None = None
    inputs: dict[str, JsonValue] | None = None
    result: dict[str, JsonValue] | None = None
    source_url: str | None = None


class HDValidation(PartialOutput):
    calendar: str | None = None
    classical: str | None = None
    classical_acceptance_passed: bool | None = None
    interpretation: str | None = None
    prediction: str | None = None
    limitations: list[str] | None = None


class HDCycleReferenceContactOrdering(PartialOutput):
    method_id: str | None = None
    reference_axis: str | None = None
    contact_axis: str | None = None
    reference_path: str | None = None
    interval_policy: str | None = None
    physical_accuracy_certified: bool | None = None
    scope: str | None = None


class HDCycleSummary(PartialOutput):
    status: str | None = None
    reference_utc: str | None = None
    reference_contact_ordering: HDCycleReferenceContactOrdering | None = None


class HDIntervalCoordinateAssessment(PartialOutput):
    method_id: str | None = None
    parameter_axis: str | None = None
    maximum_additional_evaluations: int | None = None
    additional_evaluations: int | None = None
    probe_count: int | None = None
    budget_exhausted: bool | None = None
    probes: list[dict[str, JsonValue]] | None = None
    scope: str | None = None


class HDIntervalSummary(PartialOutput):
    status: str | None = None
    plus_minus_minutes: int | None = None
    evaluated_full_charts: int | None = None
    changed_activation_count: int | None = None
    changed_joint_fields: list[str] | None = None
    station_candidates: int | None = None
    coordinate_extremum_probes: int | None = None
    coordinate_probe_budget_exhausted: bool | None = None
    coordinate_probe_unresolved_directions: int | None = None
    unresolved_multiple_dependency_brackets: int | None = None
    physical_models: list[str] | None = None
    future_leap_seconds_assumed_unchanged: bool | None = None
    continuous_interval_certified: bool | None = None
    native_execution_authenticated: bool | None = None
    scope: str | None = None


class HDTimeSensitivity(PartialOutput):
    status: str | None = None
    method_id: str | None = None
    plus_minus_minutes: int | None = None
    node_mode: str | None = None
    evaluation_witnesses: dict[str, JsonValue] | None = None
    interval: dict[str, JsonValue] | None = None
    sampling: dict[str, JsonValue] | None = None
    comparisons: list[dict[str, JsonValue]] | None = None
    observed_changed_structure_fields: list[str] | None = None
    classification_variants: list[dict[str, JsonValue]] | None = None
    joint_evidence_summary: dict[str, JsonValue] | None = None
    joint_transition_refinement: dict[str, JsonValue] | None = None
    joint_transition_refinement_summary: dict[str, JsonValue] | None = None
    joint_evidence_cache: dict[str, JsonValue] | None = None
    activation_variants: list[dict[str, JsonValue]] | None = None
    activations_checked_per_sample: int | None = None
    combination_policy: str | None = None
    station_candidates: list[dict[str, JsonValue]] | None = None
    station_coordinate_extremum_assessment: HDIntervalCoordinateAssessment | None = None
    sampled_nonstandard_civil_labels: list[dict[str, JsonValue]] | None = None
    ephemeris_models_observed: list[str] | None = None
    ephemeris_model_scope: str | None = None
    nonphysical_factor_models_observed: dict[str, JsonValue] | None = None
    sampled_future_leap_seconds_assumed_unchanged: bool | None = None
    limitation: str | None = None
    summary: HDIntervalSummary | None = None


class HumanDesignOutput(ProjectedOutput):
    apparent_model_comparison: dict[str, JsonValue] | None = None
    apparent_position_context: dict[str, JsonValue] | None = None
    native_execution_context: dict[str, JsonValue] | None = None
    run_metadata: RunMetadata | None = None
    engine: str | None = None
    method_id: str | None = None
    name: str | None = None
    birth_utc: str | None = None
    birth_clock_evidence: dict[str, JsonValue] | None = None
    clock_evidence: dict[str, JsonValue] | None = None
    design_utc: str | None = None
    design_solver: DesignSolver | None = None
    time_scales: HDTimeScales | None = None
    calculation_policy: dict[str, JsonValue] | None = None
    activations: Activations | None = None
    variables: HDVariables | None = None
    bodygraph: BodyGraph | None = None
    definition_bridging: HDDefinitionBridging | None = None
    profile: str | None = None
    profile_evidence: HDProfileEvidence | None = None
    cycle_context: dict[str, JsonValue] | None = None
    cycle_summary: HDCycleSummary | None = None
    cycle_origin_comparison: dict[str, JsonValue] | None = None
    incarnation_cross: IncarnationCross | None = None
    node_convention_comparison: dict[str, JsonValue] | None = None
    node_backend_comparison: dict[str, JsonValue] | None = None
    ephemeris_backend_comparison: dict[str, JsonValue] | None = None
    ephemeris_source_evidence: dict[str, JsonValue] | None = None
    ephemeris_source_summary: dict[str, JsonValue] | None = None
    time_sensitivity: HDTimeSensitivity | None = None
    rulesets: list[HDRuleset] | None = None
    source_consistency: dict[str, JsonValue] | None = None
    source_summary: dict[str, JsonValue] | None = None
    gate_evidence: list[dict[str, JsonValue]] | None = None
    historical_polarity_context: dict[str, JsonValue] | None = None
    gate_activation_context: dict[str, JsonValue] | None = None
    profile_partition_context: dict[str, JsonValue] | None = None
    depth_evidence: HDDepthEvidence | None = None
    rule_trace: list[HDRuleTrace] | None = None
    interpretation: HDInterpretation | None = None
    validation: HDValidation | None = None
