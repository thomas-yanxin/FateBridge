"""Projectable Human Design calculation and evidence contracts."""

from typing import Dict, List, Optional

from pydantic import JsonValue

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.response_models import ProjectedOutput, RunMetadata


class Activation(PartialOutput):
    body: Optional[str] = None
    longitude: Optional[float] = None
    longitude_speed: Optional[float] = None
    ephemeris_model: Optional[str] = None
    return_flags: Optional[int] = None
    native_return_flag_model: Optional[str] = None
    derived_from: Optional[str] = None
    derivation_source_longitude: Optional[float] = None
    gate: Optional[int] = None
    center: Optional[str] = None
    line: Optional[int] = None
    color: Optional[int] = None
    tone: Optional[int] = None
    base: Optional[int] = None
    tone_orientation: Optional[str] = None
    gate_start_longitude: Optional[float] = None
    line_boundary_distance_degrees: Optional[float] = None
    base_boundary_distance_arcseconds: Optional[float] = None


class Activations(PartialOutput):
    personality: Optional[List[Activation]] = None
    design: Optional[List[Activation]] = None


class HDChannel(PartialOutput):
    id: Optional[str] = None
    gates: Optional[List[int]] = None
    centers: Optional[List[str]] = None
    circuit: Optional[str] = None
    personality_complete: Optional[bool] = None
    design_complete: Optional[bool] = None
    mixed_only: Optional[bool] = None


class HDCenter(PartialOutput):
    status: Optional[str] = None
    activated_gates: Optional[List[int]] = None


class HDDefinition(PartialOutput):
    kind: Optional[str] = None
    components: Optional[List[List[str]]] = None
    single_gate_bridges: Optional[List[int]] = None
    bridge_scope: Optional[str] = None


class HDBridgeWitness(PartialOutput):
    added_gates: Optional[List[int]] = None
    newly_completed_channel_ids: Optional[List[str]] = None
    result_components: Optional[List[List[str]]] = None
    merged_original_component_indices: Optional[List[List[int]]] = None
    connects_all_original_components: Optional[bool] = None


class HDBridgeSearch(PartialOutput):
    expanded_states: Optional[int] = None
    distinct_generated_states: Optional[int] = None
    cost: Optional[str] = None


class HDBridgeRuleset(PartialOutput):
    id: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    source_url: Optional[str] = None
    graph_source_url: Optional[str] = None


class HDDefinitionBridging(PartialOutput):
    method_id: Optional[str] = None
    status: Optional[str] = None
    original_components: Optional[List[List[str]]] = None
    original_component_count: Optional[int] = None
    single_gate_merges: Optional[List[HDBridgeWitness]] = None
    minimum_added_gate_count: Optional[int] = None
    minimum_solution_count: Optional[int] = None
    minimum_solutions: Optional[List[HDBridgeWitness]] = None
    minimum_solutions_preview: Optional[List[HDBridgeWitness]] = None
    preview_is_truncated: Optional[bool] = None
    all_minimum_solutions_enumerated: Optional[bool] = None
    search: Optional[HDBridgeSearch] = None
    source_url: Optional[str] = None
    source_scope: Optional[str] = None
    ruleset: Optional[HDBridgeRuleset] = None
    scope: Optional[str] = None


class HDCircuitEntry(PartialOutput):
    id: Optional[str] = None
    group: Optional[str] = None
    channel_ids: Optional[List[str]] = None
    channel_count: Optional[int] = None
    meaning: Optional[str] = None


class HDIntegration(PartialOutput):
    activated_gates: Optional[List[int]] = None
    completed_channel_ids: Optional[List[str]] = None
    all_four_channels_complete: Optional[bool] = None
    adjacent_individual_channel_ids: Optional[List[str]] = None


class HDCircuitGroupMembership(PartialOutput):
    method_id: Optional[str] = None
    source_url: Optional[str] = None
    source_catalog_sha256: Optional[str] = None
    integration_group: Optional[str] = None
    integration_is_separately_reported_subset: Optional[bool] = None
    scope: Optional[str] = None


class HDCircuitry(PartialOutput):
    topology_completion: Optional[Dict[str, JsonValue]] = None
    defined_channel_count: Optional[int] = None
    circuits: Optional[List[HDCircuitEntry]] = None
    group_channel_counts: Optional[Dict[str, int]] = None
    group_membership: Optional[HDCircuitGroupMembership] = None
    integration: Optional[HDIntegration] = None
    source_url: Optional[str] = None
    integration_source_url: Optional[str] = None
    scope: Optional[str] = None


class HDConnectionPath(PartialOutput):
    centers: Optional[List[str]] = None
    channel_ids: Optional[List[str]] = None


class HDAuthorityPriorityCheck(PartialOutput):
    center: Optional[str] = None
    defined: Optional[bool] = None


class HDClassificationEvidence(PartialOutput):
    defined_centers: Optional[List[str]] = None
    motor_to_throat_paths: Optional[List[HDConnectionPath]] = None
    authority_priority_checks: Optional[List[HDAuthorityPriorityCheck]] = None
    selected_authority: Optional[str] = None
    authority_paths: Optional[List[HDConnectionPath]] = None
    no_inner_authority: Optional[bool] = None
    scope: Optional[str] = None


class BodyGraph(PartialOutput):
    type: Optional[str] = None
    subtype: Optional[str] = None
    authority: Optional[str] = None
    strategy: Optional[str] = None
    motor_to_throat: Optional[bool] = None
    classification_evidence: Optional[HDClassificationEvidence] = None
    definition: Optional[HDDefinition] = None
    centers: Optional[Dict[str, HDCenter]] = None
    channels: Optional[List[HDChannel]] = None
    circuitry: Optional[HDCircuitry] = None
    activated_gates: Optional[List[int]] = None
    hanging_gates: Optional[List[int]] = None
    gate_sources: Optional[Dict[str, List[str]]] = None


class DesignSolver(PartialOutput):
    target_solar_arc_degrees: Optional[float] = None
    residual_degrees: Optional[float] = None
    bracket_width_seconds: Optional[float] = None
    days_before_birth: Optional[float] = None
    iterations: Optional[int] = None
    method: Optional[str] = None
    civil_elapsed_days: Optional[float] = None
    birth_jd_tt: Optional[float] = None
    design_jd_tt: Optional[float] = None
    utc_is_leap_second: Optional[bool] = None
    utc_label_status: Optional[str] = None
    precision_scope: Optional[str] = None


class HDTimeScale(PartialOutput):
    jd_tt: Optional[float] = None
    jd_ut1: Optional[float] = None
    method: Optional[str] = None
    future_leap_seconds_assumed_unchanged: Optional[bool] = None
    utc_is_leap_second: Optional[bool] = None
    utc_label_status: Optional[str] = None


class HDTimeScales(PartialOutput):
    personality: Optional[HDTimeScale] = None
    design: Optional[HDTimeScale] = None


class IncarnationCross(PartialOutput):
    gates: Optional[List[int]] = None
    order: Optional[List[str]] = None
    angle: Optional[str] = None
    name_status: Optional[str] = None
    name: Optional[str] = None
    source_pdf_page_one_based: Optional[int] = None
    source_url: Optional[str] = None
    interpretation_scope: Optional[str] = None


class HDFixingTrigger(PartialOutput):
    side: Optional[str] = None
    body: Optional[str] = None
    gate: Optional[int] = None
    line: Optional[int] = None
    relation: Optional[str] = None
    calculation_path: Optional[str] = None


class HDFixingPlanets(PartialOutput):
    exaltation: Optional[List[HDFixingTrigger]] = None
    detriment: Optional[List[HDFixingTrigger]] = None


class HDLineFixing(PartialOutput):
    side: Optional[str] = None
    body: Optional[str] = None
    gate: Optional[int] = None
    line: Optional[int] = None
    calculation_path: Optional[str] = None
    gate_name: Optional[str] = None
    source_pdf_page_one_based: Optional[int] = None
    exaltation_planet: Optional[str] = None
    detriment_planet: Optional[str] = None
    polarity_kind: Optional[str] = None
    status: Optional[str] = None
    fixing_state: Optional[str] = None
    recipient_kind: Optional[str] = None
    reading: Optional[str] = None
    fixing_planets: Optional[HDFixingPlanets] = None
    fixing_rule_id: Optional[str] = None
    scope: Optional[str] = None


class HDChannelIdentifier(PartialOutput):
    gates: Optional[List[int]] = None
    name: Optional[str] = None
    source_pdf_page_one_based: Optional[int] = None


class HDDepthEvidence(PartialOutput):
    line_fixings: Optional[List[HDLineFixing]] = None
    fixing_summary: Optional[Dict[str, JsonValue]] = None
    fixing_policy: Optional[Dict[str, JsonValue]] = None
    channel_identifiers: Optional[List[HDChannelIdentifier]] = None
    source_url: Optional[str] = None
    source_pdf_sha256: Optional[str] = None
    fixing_rule_source: Optional[str] = None
    node_fixing_exclusion_source: Optional[str] = None
    scope: Optional[str] = None


class HDReadingBasis(PartialOutput):
    path: Optional[str] = None
    value: Optional[JsonValue] = None


class HDProfileLine(PartialOutput):
    side: Optional[str] = None
    line: Optional[int] = None
    traditional_polarity: Optional[str] = None
    archetype: Optional[str] = None
    theme: Optional[str] = None
    trigram: Optional[str] = None
    basis: Optional[List[HDReadingBasis]] = None


class HDProfileGeometry(PartialOutput):
    angle: Optional[str] = None
    label: Optional[str] = None
    source_term: Optional[str] = None
    source_url: Optional[str] = None


class HDSixthLineProcess(PartialOutput):
    applicable: Optional[bool] = None
    affected_sides: Optional[List[str]] = None
    phase_assignment_status: Optional[str] = None
    current_phase: Optional[str] = None
    computed_return_dates: Optional[Dict[str, JsonValue]] = None
    traditional_phase_order: Optional[List[str]] = None
    source_cycle_markers: Optional[Dict[str, JsonValue]] = None
    source_url: Optional[str] = None
    scope: Optional[str] = None


class HDProfileRuleset(PartialOutput):
    id: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    source_author: Optional[str] = None
    source_catalog_id: Optional[str] = None


class HDProfileEvidence(PartialOutput):
    status: Optional[str] = None
    profile: Optional[str] = None
    lines: Optional[List[HDProfileLine]] = None
    geometry: Optional[HDProfileGeometry] = None
    sixth_line_process: Optional[HDSixthLineProcess] = None
    source_catalog_sha256: Optional[str] = None
    source_urls: Optional[List[str]] = None
    scope: Optional[str] = None
    ruleset: Optional[HDProfileRuleset] = None


class HDVariableArrow(PartialOutput):
    component: Optional[str] = None
    side: Optional[str] = None
    body_pair: Optional[List[str]] = None
    position: Optional[str] = None
    status: Optional[str] = None
    tone: Optional[int] = None
    orientation: Optional[str] = None
    letter: Optional[str] = None
    pair_tones_consistent: Optional[bool] = None
    basis: Optional[List[HDReadingBasis]] = None
    ephemeris_models: Optional[List[str]] = None


class HDVariables(PartialOutput):
    status: Optional[str] = None
    code: Optional[str] = None
    arrows: Optional[List[HDVariableArrow]] = None
    personality_colors: Optional[Dict[str, JsonValue]] = None
    notation_order: Optional[List[str]] = None
    source_urls: Optional[List[str]] = None
    subdivision_accuracy_certified: Optional[bool] = None
    scope: Optional[str] = None


class HDReadingStatement(PartialOutput):
    id: Optional[str] = None
    text: Optional[str] = None
    basis: Optional[List[HDReadingBasis]] = None
    source_urls: Optional[List[str]] = None


class HDInterpretation(PartialOutput):
    coordinate_frame_meaning: Optional[str] = None
    historical_polarity_context: Optional[Dict[str, JsonValue]] = None
    profile_partition_context: Optional[Dict[str, JsonValue]] = None
    apparent_position_context: Optional[Dict[str, JsonValue]] = None
    gate_activation_context: Optional[Dict[str, JsonValue]] = None
    personality_color_meaning: Optional[str] = None
    birth_interval_meaning: Optional[str] = None
    node_comparison_meaning: Optional[str] = None
    birth_clock_meaning: Optional[str] = None
    expanded_cross_name_meaning: Optional[str] = None
    circuit_topology_meaning: Optional[str] = None
    time_scope: Optional[str] = None
    ephemeris_scope: Optional[str] = None
    variables_meaning: Optional[str] = None
    design_time_precision_meaning: Optional[str] = None
    line_fixing_meaning: Optional[str] = None
    type_meaning: Optional[str] = None
    authority_meaning: Optional[str] = None
    authority_structure: Optional[str] = None
    definition_meaning: Optional[str] = None
    definition_structure: Optional[str] = None
    circuitry_meaning: Optional[str] = None
    profile_meaning: Optional[str] = None
    basis: Optional[List[str]] = None
    reality_check: Optional[str] = None
    statements: Optional[List[HDReadingStatement]] = None
    reading_policy: Optional[str] = None


class HDRuleset(PartialOutput):
    id: Optional[str] = None
    author: Optional[str] = None
    version: Optional[str] = None
    source_kind: Optional[str] = None
    sources: Optional[Dict[str, str]] = None
    scope: Optional[str] = None


class HDRuleTrace(PartialOutput):
    rule_id: Optional[str] = None
    ruleset_id: Optional[str] = None
    inputs: Optional[Dict[str, JsonValue]] = None
    result: Optional[Dict[str, JsonValue]] = None
    source_url: Optional[str] = None


class HDValidation(PartialOutput):
    calendar: Optional[str] = None
    classical: Optional[str] = None
    classical_acceptance_passed: Optional[bool] = None
    interpretation: Optional[str] = None
    prediction: Optional[str] = None
    real_world_sample_size: Optional[int] = None
    authority_certified: Optional[bool] = None
    all_four_axes_full_marks: Optional[bool] = None
    all_three_axes_full_marks: Optional[bool] = None
    limitations: Optional[List[str]] = None


class HDCycleReferenceContactOrdering(PartialOutput):
    method_id: Optional[str] = None
    reference_axis: Optional[str] = None
    contact_axis: Optional[str] = None
    reference_path: Optional[str] = None
    interval_policy: Optional[str] = None
    physical_accuracy_certified: Optional[bool] = None
    scope: Optional[str] = None


class HDCycleSummary(PartialOutput):
    status: Optional[str] = None
    reference_utc: Optional[str] = None
    reference_contact_ordering: Optional[HDCycleReferenceContactOrdering] = None


class HDIntervalCoordinateAssessment(PartialOutput):
    method_id: Optional[str] = None
    parameter_axis: Optional[str] = None
    maximum_additional_evaluations: Optional[int] = None
    additional_evaluations: Optional[int] = None
    probe_count: Optional[int] = None
    budget_exhausted: Optional[bool] = None
    probes: Optional[List[Dict[str, JsonValue]]] = None
    scope: Optional[str] = None


class HDIntervalSummary(PartialOutput):
    status: Optional[str] = None
    plus_minus_minutes: Optional[int] = None
    evaluated_full_charts: Optional[int] = None
    changed_activation_count: Optional[int] = None
    changed_joint_fields: Optional[List[str]] = None
    station_candidates: Optional[int] = None
    coordinate_extremum_probes: Optional[int] = None
    coordinate_probe_budget_exhausted: Optional[bool] = None
    coordinate_probe_unresolved_directions: Optional[int] = None
    unresolved_multiple_dependency_brackets: Optional[int] = None
    physical_models: Optional[List[str]] = None
    future_leap_seconds_assumed_unchanged: Optional[bool] = None
    continuous_interval_certified: Optional[bool] = None
    native_execution_authenticated: Optional[bool] = None
    scope: Optional[str] = None


class HDTimeSensitivity(PartialOutput):
    status: Optional[str] = None
    method_id: Optional[str] = None
    plus_minus_minutes: Optional[int] = None
    node_mode: Optional[str] = None
    evaluation_witnesses: Optional[Dict[str, JsonValue]] = None
    interval: Optional[Dict[str, JsonValue]] = None
    sampling: Optional[Dict[str, JsonValue]] = None
    comparisons: Optional[List[Dict[str, JsonValue]]] = None
    observed_changed_structure_fields: Optional[List[str]] = None
    classification_variants: Optional[List[Dict[str, JsonValue]]] = None
    joint_evidence_summary: Optional[Dict[str, JsonValue]] = None
    joint_transition_refinement: Optional[Dict[str, JsonValue]] = None
    joint_transition_refinement_summary: Optional[Dict[str, JsonValue]] = None
    joint_evidence_cache: Optional[Dict[str, JsonValue]] = None
    activation_variants: Optional[List[Dict[str, JsonValue]]] = None
    activations_checked_per_sample: Optional[int] = None
    combination_policy: Optional[str] = None
    station_candidates: Optional[List[Dict[str, JsonValue]]] = None
    station_coordinate_extremum_assessment: Optional[HDIntervalCoordinateAssessment] = (
        None
    )
    sampled_nonstandard_civil_labels: Optional[List[Dict[str, JsonValue]]] = None
    ephemeris_models_observed: Optional[List[str]] = None
    ephemeris_model_scope: Optional[str] = None
    nonphysical_factor_models_observed: Optional[Dict[str, JsonValue]] = None
    sampled_future_leap_seconds_assumed_unchanged: Optional[bool] = None
    limitation: Optional[str] = None
    summary: Optional[HDIntervalSummary] = None


class HumanDesignOutput(ProjectedOutput):
    apparent_model_comparison: Optional[Dict[str, JsonValue]] = None
    apparent_position_context: Optional[Dict[str, JsonValue]] = None
    native_execution_context: Optional[Dict[str, JsonValue]] = None
    run_metadata: Optional[RunMetadata] = None
    engine: Optional[str] = None
    method_id: Optional[str] = None
    name: Optional[str] = None
    birth_utc: Optional[str] = None
    birth_clock_evidence: Optional[Dict[str, JsonValue]] = None
    clock_evidence: Optional[Dict[str, JsonValue]] = None
    design_utc: Optional[str] = None
    design_solver: Optional[DesignSolver] = None
    time_scales: Optional[HDTimeScales] = None
    calculation_policy: Optional[Dict[str, JsonValue]] = None
    activations: Optional[Activations] = None
    variables: Optional[HDVariables] = None
    bodygraph: Optional[BodyGraph] = None
    definition_bridging: Optional[HDDefinitionBridging] = None
    profile: Optional[str] = None
    profile_evidence: Optional[HDProfileEvidence] = None
    cycle_context: Optional[Dict[str, JsonValue]] = None
    cycle_summary: Optional[HDCycleSummary] = None
    cycle_origin_comparison: Optional[Dict[str, JsonValue]] = None
    incarnation_cross: Optional[IncarnationCross] = None
    node_convention_comparison: Optional[Dict[str, JsonValue]] = None
    node_backend_comparison: Optional[Dict[str, JsonValue]] = None
    ephemeris_backend_comparison: Optional[Dict[str, JsonValue]] = None
    ephemeris_source_evidence: Optional[Dict[str, JsonValue]] = None
    ephemeris_source_summary: Optional[Dict[str, JsonValue]] = None
    time_sensitivity: Optional[HDTimeSensitivity] = None
    rulesets: Optional[List[HDRuleset]] = None
    source_consistency: Optional[Dict[str, JsonValue]] = None
    source_summary: Optional[Dict[str, JsonValue]] = None
    gate_evidence: Optional[List[Dict[str, JsonValue]]] = None
    historical_polarity_context: Optional[Dict[str, JsonValue]] = None
    gate_activation_context: Optional[Dict[str, JsonValue]] = None
    profile_partition_context: Optional[Dict[str, JsonValue]] = None
    depth_evidence: Optional[HDDepthEvidence] = None
    rule_trace: Optional[List[HDRuleTrace]] = None
    interpretation: Optional[HDInterpretation] = None
    validation: Optional[HDValidation] = None
