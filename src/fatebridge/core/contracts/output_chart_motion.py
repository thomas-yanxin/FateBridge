"""Western chart longitude and source-motion evidence."""

from typing import Annotated, Literal

from pydantic import Field

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_midpoint_geometry import PhysicalFactorSource


class TropicalRotationMotion(PartialOutput):
    method_id: str | None = None
    epoch_jd_tt: float | None = None
    native_version: str | None = None
    binding_version: str | None = None
    source_function: str | None = None
    source_url: str | None = None
    step_days: float | None = None
    scope: str | None = None
    status: str | None = None
    reason: str | None = None
    nutation_obliquity_rate_degrees_per_day: float | None = None


class LunarSpatialAberrationMotion(PartialOutput):
    method_id: str | None = None
    status: str | None = None
    source_function: str | None = None
    native_backward_step_days: float | None = None
    longitude_speed_correction: float | None = None
    observer_beta_held_fixed: bool | None = None
    positions_unchanged: bool | None = None
    native_binary_arithmetic_identity_certified: bool | None = None
    scope: str | None = None


class LunarObserverVelocitySample(PartialOutput):
    epoch_jd_tt: float | None = None
    velocity_au_per_native_argument_day: list[float] | None = None
    is_center: bool | None = None


class LunarFixedFrameSourceMotion(PartialOutput):
    method_id: str | None = None
    epoch_jd_tt: float | None = None
    ephemeris_model: str | None = None
    fixed_frame_id: str | None = None
    fixed_frame_epoch_jd_tt: float | None = None
    input_frame_held_fixed: bool | None = None
    input_velocity_time_variable: str | None = None
    full_fixed_frame_apparent_position_au: list[float] | None = None
    full_fixed_frame_velocity_au_per_native_argument_day: list[float] | None = None
    status: str | None = None
    reason: str | None = None
    source_function: str | None = None
    preaberration_source: str | None = None
    scope: str | None = None
    acceleration_steps_days: list[float] | None = None
    selected_step_days: float | None = None
    acceleration_agreement_line_au_per_day2: float | None = None
    observer_agreement_line_arcsec_per_day: float | None = None
    position_reproduction_line_arcsec: float | None = None
    positions_unchanged: bool | None = None
    complete_moving_frame_derivative_certified: bool | None = None
    native_binary_arithmetic_identity_certified: bool | None = None
    source_window: dict[str, OpenJsonValue] | None = None
    selected_stencil: str | None = None
    stencil_offsets: list[int] | None = None
    stencil_integer_weights: list[int] | None = None
    stencil_divisor: int | None = None
    sample_count: int | None = None
    acceleration_estimates_au_per_day2: list[list[float]] | None = None
    acceleration_samples: list[LunarObserverVelocitySample] | None = None
    acceleration_difference_au_per_day2: float | None = None
    observer_derivative_disagreement_arcsec_per_day: float | None = None
    center_native_states_reproduced_exactly: bool | None = None
    center_file_context_reproduced_exactly: bool | None = None
    full_fixed_frame_longitude_speed_degrees_per_day: float | None = None
    native_fixed_frame_longitude_speed_degrees_per_day: float | None = None
    observer_beta_jvp_longitude_speed_degrees_per_day: float | None = None
    source_position_reproduction_arcsec: float | None = None
    source_radius_reproduction_error_au: float | None = None
    longitude_speed_correction: float | None = None


class LunarLightTimeMotion(PartialOutput):
    method_id: str | None = None
    native_version: str | None = None
    binding_version: str | None = None
    ephemeris_model: str | None = None
    epoch_jd_tt: float | None = None
    source_url: str | None = None
    source_function: str | None = None
    scope: str | None = None
    status: str | None = None
    reason: str | None = None
    frame_method: str | None = None
    longitude_origin_invariance: str | None = None
    light_time_days: float | None = None
    light_time_derivative: float | None = None
    longitude_speed_correction: float | None = None
    spatial_aberration: LunarSpatialAberrationMotion | None = None
    fixed_frame_source_derivative: LunarFixedFrameSourceMotion | None = None
    latitude_reproduction_error_degrees: float | None = None
    radius_reproduction_error_au: float | None = None
    source_factors: list[str] | None = None
    source_contexts: dict[str, PhysicalFactorSource] | None = None


class DirectionalMotionEstimate(PartialOutput):
    sample_count: int | None = None
    forward_rate: float | None = None
    backward_rate: float | None = None


class DirectionalMotionCheck(PartialOutput):
    method_id: str | None = None
    step_days: float | None = None
    central_step_days: float | None = None
    estimates: list[DirectionalMotionEstimate] | None = None
    central_rates: list[float] | None = None
    forward_rate: float | None = None
    backward_rate: float | None = None
    disagreement_arcsec_per_day: float | None = None
    passed: bool | None = None


class PositionMotionAttempt(PartialOutput):
    selected_stencil: str | None = None
    steps_days: list[float] | None = None
    rates: list[float] | None = None
    pair_differences_arcsec_per_day: list[float] | None = None
    directional_checks: list[DirectionalMotionCheck] | None = None
    consecutive_converged_pairs: int | None = None
    status: str | None = None


class PositionMotionRefinementBudget(PartialOutput):
    method_id: str | None = None
    epoch_ulp_days: float | None = None
    coordinate_quantization_degrees: float | None = None
    minimum_epoch_ulps: int | None = None
    directional_l1_norm: float | None = None
    estimated_roundoff_floor_days: float | None = None
    minimum_step_days: float | None = None
    scope: str | None = None


class RetardedEpochSampling(PartialOutput):
    symmetric_stabilized_attempt: PositionMotionAttempt | None = None
    acceptance_scope: str | None = None
    refinement_budget: PositionMotionRefinementBudget | None = None
    directional_guard_method_id: str | None = None
    method_id: str | None = None
    unstabilized_attempt: PositionMotionAttempt | None = None
    candidate_steps_days: list[float] | None = None
    required_consecutive_converged_pairs: int | None = None
    consecutive_converged_pairs: int | None = None
    one_sided_checks: list[DirectionalMotionCheck] | None = None
    sample_count: int | None = None
    maximum_epoch_remainder_days: float | None = None
    maximum_sampling_shift_arcseconds: float | None = None
    displayed_native_position_changed: bool | None = None
    scope: str | None = None


CenterFileCell = Annotated[
    str,
    Field(
        pattern=r"^center_files_(solar_direction|solar_cell_([0-9]|[1-9][0-9]|100))$"
    ),
]


class MotionSourceFileWindow(PartialOutput):
    slot: int | None = None
    filename: str | None = None
    start_jd_tt: float | None = None
    end_jd_tt: float | None = None


class CenterFileReplay(PartialOutput):
    method_id: str | None = None
    center_native_state_reproduced_exactly: bool | None = None
    source_context: PhysicalFactorSource | None = None
    center_windows: list[MotionSourceFileWindow] | None = None
    replay_anchor_jd_tt: list[float] | None = None
    sample_count: int | None = None
    ineligible_sample_count: int | None = None
    displayed_native_position_changed: bool | None = None
    scope: str | None = None


class SolarBranchGeometry(PartialOutput):
    method_id: str | None = None
    source_url: str | None = None
    status: str | None = None
    cell: int | CenterFileCell | None = Field(
        default=None,
        description="Solar mass cell index, or an explicitly named replayed-center-file cell; a file-cell label is not a solar radius fraction.",
    )
    impact_solar_radius_fraction: float | None = None
    cross_product_impact_fraction: float | None = None
    arithmetic_margin_fraction: float | None = None
    scope: str | None = None


class SolarBranchSide(PartialOutput):
    direction: int | None = None
    node_cells: list[int | CenterFileCell | None] | None = None
    eligible: bool | None = None


class SolarBranchEstimate(PartialOutput):
    direction: int | None = None
    sample_count: int | None = None
    rate: float | None = None


class SolarBranchLevel(PartialOutput):
    step_days: float | None = None
    sides: list[SolarBranchSide] | None = None
    estimates: list[SolarBranchEstimate] | None = None
    eligible_directions: list[int] | None = None
    passed: bool | None = None
    rate: float | None = None
    disagreement_arcsec_per_day: float | None = None


class DecimalApparentReduction(PartialOutput):
    method_id: Literal["native_geometric_decimal_apparent_reduction_v2"] | None = None
    ephemeris_model: Literal["swieph", "jpl"] | None = None
    center_interpolation_branch: SolarBranchGeometry | None = None
    precision_decimal_digits: Literal[50] | None = None
    solar_mass_profile_sha256: str | None = None
    frame_basis_bodies: list[str] | None = None
    sample_count: int | None = None
    maximum_frame_orthogonality_error: float | None = None
    maximum_epoch_remainder_days: float | None = None
    center_sampling_shift_arcseconds: float | None = None
    displayed_native_position_changed: Literal[False] | None = None
    independent_astronomical_accuracy_certified: Literal[False] | None = None
    scope: str | None = None


class SolarBranchMotion(PartialOutput):
    decimal_reduction: DecimalApparentReduction | None = None
    center_file_replay: CenterFileReplay | None = None
    refinement_budget: PositionMotionRefinementBudget | None = None
    method_id: str | None = None
    source_function: str | None = None
    center: SolarBranchGeometry | None = None
    status: str | None = None
    levels: list[SolarBranchLevel] | None = None
    required_consecutive_levels: int | None = None
    convergence_line_arcsec_per_day: float | None = None
    scope: str | None = None
    selected_step_days: float | None = None
    eligible_directions: list[int] | None = None
    selected_rate: float | None = None
    steps_days: list[float] | None = None
    candidate_steps_days: list[float] | None = None
    rates: list[float] | None = None
    pair_differences_arcsec_per_day: list[float] | None = None
    consecutive_converged_pairs: int | None = None
    probe_count: int | None = None


class CompletePositionMotion(PartialOutput):
    decimal_reduction_previous_attempt: SolarBranchMotion | None = None
    source_branch_motion: SolarBranchMotion | None = None
    center_file_replay_attempts: list[SolarBranchMotion] | None = None
    refinement_budget: PositionMotionRefinementBudget | None = None
    sun_extension_previous_attempt: PositionMotionAttempt | None = None
    directional_guard_method_id: str | None = None
    directional_checks: list[DirectionalMotionCheck] | None = None
    method_id: str | None = None
    native_version: str | None = None
    binding_version: str | None = None
    ephemeris_model: str | None = None
    epoch_jd_tt: float | None = None
    reference_frame: str | None = None
    steps_days: list[float] | None = None
    candidate_steps_days: list[float] | None = None
    selection_policy: str | None = None
    selected_stencil: str | None = None
    primary_attempt: PositionMotionAttempt | None = None
    sampling_stabilization: RetardedEpochSampling | None = None
    pair_differences_arcsec_per_day: list[float] | None = None
    chosen_step_days: float | None = None
    convergence_line_arcsec_per_day: float | None = None
    source_url: str | None = None
    numerical_source_url: str | None = None
    scope: str | None = None
    status: str | None = None
    reason: str | None = None
    step_rates_degrees_per_day: list[float] | None = None
    step_difference_arcsec_per_day: float | None = None
    source_contexts: dict[str, PhysicalFactorSource] | None = None


class LunarSourceFileWindow(PartialOutput):
    slot: int | None = None
    filename: str | None = None
    start_jd_tt: float | None = None
    end_jd_tt: float | None = None
    de_number: int | None = None


class LunarSourceWindow(PartialOutput):
    method_id: str | None = None
    epoch_jd_tt: float | None = None
    ephemeris_model: str | None = None
    native_version: str | None = None
    binding_version: str | None = None
    source_url: str | None = None
    source_function: str | None = None
    scope: str | None = None
    status: str | None = None
    reason: str | None = None
    light_time_days: float | None = None
    retarded_jd_tt: float | None = None
    selected_windows: list[LunarSourceFileWindow] | None = None
    selected_windows_after_recomputation: list[LunarSourceFileWindow] | None = None
    initial_spherical_coordinates: list[float] | None = None
    coherent_spherical_coordinates: list[float] | None = None
    initial_native_state: list[float] | None = None
    coherent_native_state: list[float] | None = None
    requested_coordinate_flags: int | None = None
    coordinate_kind: str | None = None
    source_contexts: dict[str, PhysicalFactorSource] | None = None


class SiderealOriginMotion(PartialOutput):
    method_id: str | None = None
    epoch_jd_tt: float | None = None
    native_version: str | None = None
    binding_version: str | None = None
    source_url: str | None = None
    source_function: str | None = None
    sidereal_mode: str | None = None
    native_divisor_days: float | None = None
    positions_unchanged: bool | None = None
    complete_origin_derivative_certified: bool | None = None
    physical_TT_clock_mapping_certified: bool | None = None
    scope: str | None = None
    status: str | None = None
    reason: str | None = None
    previous_epoch_jd_tt: float | None = None
    actual_binary64_interval_days: float | None = None
    previous_origin_degrees: float | None = None
    current_origin_degrees: float | None = None
    previous_returned_flags: int | None = None
    current_returned_flags: int | None = None
    requested_origin_flags: int | None = None
    raw_difference_degrees: float | None = None
    principal_difference_degrees: float | None = None
    whole_turns_removed: int | None = None
    longitude_speed_correction: float | None = None
    center_origin_reproduced_exactly: bool | None = None


class LongitudeMotionPolicy(PartialOutput):
    method_id: str | None = None
    tropical_rotation: TropicalRotationMotion | None = None
    lunar_light_time: LunarLightTimeMotion | None = None
    traditional_sidereal_origin_wrap: SiderealOriginMotion | None = None
    lunar_source_windows: dict[str, LunarSourceWindow] | None = None
    complete_position_derivatives: dict[str, CompletePositionMotion] | None = None
    display_frame: str | None = None
    display_rotation_correction_applied: bool | None = None
    display_longitude_offset_speed_degrees_per_day: float | None = None
    scope: str | None = None
