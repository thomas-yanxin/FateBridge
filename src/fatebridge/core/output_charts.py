"""Nested contracts for classical, specialized and relationship charts.

Shared value contracts describe the canonical response fields. Dynamic
planet and midpoint keys remain open; interpretation prose remains extensible.
"""

from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import Field

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_chinese import PersonInfo
from fatebridge.core.output_clock_labels import WesternUTCRepresentation
from fatebridge.core.output_ephemeris import (
    ApparentPositionPolicy as ApparentPositionPolicy,
)
from fatebridge.core.output_ephemeris import SolarPositionBody as SolarPositionBody
from fatebridge.core.output_guolao import (
    GuolaoMansion,
    GuolaoPatternEvidence,
    GuolaoResearch,
)
from fatebridge.core.output_jyotish import JyotishIndia
from fatebridge.core.output_midpoints import (
    MidpointAnalysis,
    PhysicalEphemerisSource,
    PhysicalFactorSource,
    SectorEvidence,
    SectorProfile,
    SpecialtyTimeSensitivity,
)
from fatebridge.core.output_rotation import EarthRotationPolicy as EarthRotationPolicy
from fatebridge.core.output_rotation import (
    LongtermPhaseAlignment as LongtermPhaseAlignment,
)


class EphemerisReferencePoints(PartialOutput):
    policy_id: Optional[str] = None
    body_centers: Optional[List[str]] = None
    system_barycenters: Optional[List[str]] = None
    theoretical_points: Optional[List[str]] = None
    approximate_points: Optional[List[str]] = None
    unresolved_points: Optional[List[str]] = None
    derived_points: Optional[List[str]] = None
    center_body_correction_applied: Optional[Literal[False]] = None
    source_url: Optional[str] = None
    source_section: Optional[str] = None
    note_zh: Optional[str] = None
    scope: Optional[str] = None


class Dignity(PartialOutput):
    dignity: Optional[str] = None
    status_zh: Optional[str] = None
    scope: Optional[str] = None


class ChartPlanet(PartialOutput):
    id: Optional[str] = None
    longitude: Optional[float] = Field(default=None, ge=0, lt=360)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    degree_in_sign: Optional[float] = Field(default=None, ge=0, lt=30)
    sign: Optional[str] = None
    sign_zh: Optional[str] = None
    house: Optional[int] = None
    ecliptic_house_position: Optional[float] = Field(default=None, ge=1, lt=13)
    element: Optional[str] = None
    modality: Optional[str] = None
    dignity: Optional[Dignity] = None
    su28: Optional[str] = None
    nakshatra: Optional[str] = None
    sector13: Optional[int] = None
    sector13_evidence: Optional[SectorEvidence] = None


class ChartAngle(PartialOutput):
    longitude: Optional[float] = Field(default=None, ge=0, lt=360)
    sign: Optional[str] = None
    sign_zh: Optional[str] = None


class ChartHouse(PartialOutput):
    cusp_longitude: Optional[float] = Field(default=None, ge=0, lt=360)
    house: Optional[int] = None
    sign: Optional[str] = None
    sign_zh: Optional[str] = None


class ChartAspect(PartialOutput):
    planet_a: Optional[str] = None
    planet_b: Optional[str] = None
    aspect: Optional[str] = None
    orb: Optional[float] = Field(default=None, ge=0, le=180)
    exact_angle: Optional[float] = Field(default=None, ge=0, le=180)
    orb_limit: Optional[float] = Field(default=None, ge=0, le=180)
    separation: Optional[float] = Field(default=None, ge=0, le=180)
    rule_id: Optional[str] = None


class FixedStarNature(PartialOutput):
    planet: Optional[str] = None
    qualifier: Optional[str] = None


class FixedStar(PartialOutput):
    nature_components: Optional[List[FixedStarNature]] = None
    nature_source_region: Optional[str] = None
    star_latitude: Optional[float] = None
    nature_source_url: Optional[str] = None
    astrometry_source_url: Optional[str] = None
    catalogue_identifier: Optional[str] = None
    cn: Optional[str] = None
    nature: Optional[List[str]] = None
    orb: Optional[float] = None
    point: Optional[str] = None
    star: Optional[str] = None
    star_longitude: Optional[float] = None


class FixedStarProfile(PartialOutput):
    nature_ruleset_id: Optional[str] = None
    nature_rules_sha256: Optional[str] = None
    swisseph_version: Optional[str] = None
    orb_limit: Optional[float] = Field(default=None, ge=0, le=180)
    model_id: Optional[str] = None
    status: Optional[str] = None
    catalogue_id: Optional[str] = None
    catalogue_sha256: Optional[str] = None
    catalogue_size: Optional[int] = None
    catalogue_epoch: Optional[str] = None
    julian_day_tt: Optional[float] = None
    longitude_frame: Optional[str] = None
    conjunction_basis: Optional[str] = None
    latitude_used_for_conjunction: Optional[bool] = None
    space_motion: Optional[str] = None
    astrometry_source: Optional[str] = None
    nature_source_url: Optional[str] = None
    absolute_sky_accuracy_certified: Optional[bool] = None
    native_flags: Optional[List[int]] = None
    earth_flags: Optional[int] = None
    earth_ephemeris_model: Optional[str] = None
    unavailable_reason: Optional[str] = None
    note_zh: Optional[str] = None


class PlanetaryHours(PartialOutput):
    weekday_clock_basis: Optional[str] = None
    weekday_opening_sunrise_label: Optional[str] = None
    weekday_policy: Optional[str] = None
    day_ruler: Optional[str] = None
    hour_number: Optional[int] = Field(default=None, ge=1, le=12)
    hour_ruler: Optional[str] = None
    is_day: Optional[bool] = None
    planetary_day_start_utc: Optional[str] = None
    arc_start_utc: Optional[str] = None
    arc_end_utc: Optional[str] = None
    hour_start_utc: Optional[str] = None
    hour_end_utc: Optional[str] = None
    arc_start_jd_ut1: Optional[float] = None
    arc_end_jd_ut1: Optional[float] = None
    rule_id: Optional[str] = None
    sunrise_convention: Optional[str] = None
    time_scale: Optional[str] = None
    sequence_source: Optional[str] = None
    sequence_source_url: Optional[str] = None
    source_scope: Optional[str] = None


class ChartAspectPolicy(PartialOutput):
    rule_id: Optional[str] = None
    planet_orbs: Optional[Dict[str, float]] = None
    fallback_orb: Optional[float] = Field(default=None, ge=0, le=180)
    combination: Optional[str] = None
    exact_angles: Optional[Dict[str, float]] = None
    sextile_square_scale: Optional[float] = Field(default=None, gt=0, le=1)


class TopocentricProjectionBranch(PartialOutput):
    above_horizon: Optional[bool] = None
    reflected_western: Optional[bool] = None
    candidate_scope: Optional[str] = None
    root_selection: Optional[str] = None
    selected_root_degrees: Optional[float] = Field(default=None, ge=0, le=90)
    candidate_root_degrees: Optional[List[float]] = None
    candidate_positions: Optional[List[float]] = None
    computed_root_bracket_width_degrees: Optional[str] = None
    geographic_latitude_used: Optional[float] = Field(default=None, ge=-90, le=90)
    latitude_clamped: Optional[bool] = None


class HouseProjectionPrecisionCheck(PartialOutput):
    tropical_longitude: Optional[float] = None
    native_tropical_longitude: Optional[float] = None
    native_position: Optional[float] = None
    delivered_position: Optional[float] = None
    house: Optional[int] = Field(default=None, ge=1, le=12)
    phase_degrees: Optional[float] = Field(default=None, ge=0, lt=360)
    phase_degrees_decimal: Optional[str] = None
    working_decimal_digits: Optional[List[int]] = None
    action: Optional[str] = None
    topocentric_branch: Optional[TopocentricProjectionBranch] = None


class HouseProjectionPrecision(PartialOutput):
    method_id: Optional[str] = None
    phase_forward_offset_arcseconds: Optional[float] = None
    boundary_policy: Optional[str] = None
    input_precision_scope: Optional[str] = None
    maximum_physical_error_arcseconds: Optional[float] = None
    checks: Optional[List[HouseProjectionPrecisionCheck]] = None
    status: Optional[str] = None
    branch_policy: Optional[str] = None
    native_inverse_latitude_limit_degrees: Optional[float] = None
    latitude_clamped: Optional[bool] = None


class HousePositionProjection(PartialOutput):
    method: Optional[str] = None
    library_version: Optional[str] = None
    reason: Optional[str] = None
    armc: Optional[float] = None
    geographic_latitude: Optional[float] = None
    true_obliquity: Optional[float] = None
    house_code: Optional[str] = None
    input_frame: Optional[str] = None
    input_ecliptic_latitude: Optional[float] = None
    source_url: Optional[str] = None
    source_section: Optional[str] = None
    scope: Optional[str] = None
    precision: Optional[HouseProjectionPrecision] = None
    note_zh: Optional[str] = None


class RelationshipDerivation(PartialOutput):
    method_id: Optional[str] = None
    variant: Optional[str] = None
    source_url: Optional[str] = None
    source_kind: Optional[str] = None
    positions_from_single_instant: Optional[bool] = None
    time_policy: Optional[str] = None
    time_source_scope: Optional[str] = None
    geographic_policy: Optional[str] = None
    longitude_unwrapping: Optional[str] = None
    midpoint_jd_ut1: Optional[float] = None
    input_julian_days_ut1: Optional[List[float]] = None
    midpoint_longitude: Optional[float] = Field(default=None, ge=-180, lt=180)
    midpoint_latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    mc_target_tropical: Optional[float] = Field(default=None, ge=0, lt=360)
    mc_actual_tropical: Optional[float] = Field(default=None, ge=0, lt=360)
    mc_residual_degrees: Optional[float] = Field(default=None, ge=0, le=1e-5)
    time_correction_seconds_ut1: Optional[float] = None
    mc_target_policy: Optional[str] = None
    longitude_policy: Optional[str] = None
    latitude_policy: Optional[str] = None
    house_policy: Optional[str] = None
    mercury_venus_policy: Optional[str] = None
    recipe: Optional[str] = None
    base_davison_variant: Optional[str] = None


class GeographicPoleAngleDefinition(PartialOutput):
    status: Optional[str] = None
    ascendant_definition: Optional[str] = None
    fixed_direction_diurnal_rising_defined: Optional[bool] = Field(
        default=None,
        description="False at an exact geographic pole: a fixed celestial direction has no rise/set caused by Earth's daily rotation. Computed angles retain a meridian convention.",
    )
    reference_meridian: Optional[str] = None
    dependent_quantities: Optional[List[str]] = None
    note_zh: Optional[str] = None
    source_urls: Optional[List[str]] = None


class OrbitalFallback(PartialOutput):
    approximate_planets: Optional[List[str]] = None
    time_argument: Optional[str] = None
    source_path: Optional[str] = None
    method_reference_url: Optional[str] = None
    note_zh: Optional[str] = None
    candidate_file_year: Optional[int] = None
    candidate_files: Optional[List[str]] = Field(
        default=None,
        description="Candidate planet/Moon data segments for the requested CE year, including adjacent-year boundaries. This list is not a file-integrity or loaded-model check.",
    )


class EasternDirectionPrecision(PartialOutput):
    method_id: Optional[str] = None
    working_decimal_digits: Optional[List[int]] = None
    convergence_degrees: Optional[str] = None
    geographic_latitude: Optional[float] = None
    armc: Optional[float] = None
    true_obliquity: Optional[float] = None
    house_auxiliary_tt: Optional[float] = None
    eastern_selector: Optional[str] = None
    intersection_normal_norm: Optional[float] = None
    tropical_model_ascendant: Optional[float] = None
    input_precision_scope: Optional[str] = None
    maximum_physical_error_arcseconds: Optional[float] = None
    source_url: Optional[str] = None
    source_scope: Optional[str] = None
    native_common_ascendant: Optional[float] = None
    delivered_ascendant: Optional[float] = None
    ascendant_action: Optional[str] = None
    corrected_cusps: Optional[List[int]] = None
    house_cusp_scope: Optional[str] = None
    coordinate_frame: Optional[str] = None
    native_cusps: Optional[List[float]] = None
    delivered_cusps: Optional[List[float]] = None


class HouseAxisConvention(PartialOutput):
    policy_id: Optional[str] = None
    house_code: Optional[str] = None
    longitude_frame: Optional[str] = None
    public_midheaven_definition: Optional[str] = None
    public_ascendant_definition: Optional[str] = None
    public_midheaven: Optional[float] = Field(default=None, ge=0, lt=360)
    native_house_midheaven: Optional[float] = Field(default=None, ge=0, lt=360)
    public_ascendant: Optional[float] = Field(default=None, ge=0, lt=360)
    native_house_ascendant: Optional[float] = Field(default=None, ge=0, lt=360)
    meridian_branch_separation_degrees: Optional[float] = Field(
        default=None, ge=0, le=180
    )
    ascendant_branch_separation_degrees: Optional[float] = Field(
        default=None, ge=0, le=180
    )
    native_cusps_and_projection_retained: Optional[bool] = None
    eastern_direction_precision: Optional[EasternDirectionPrecision] = None
    source_url: Optional[str] = None
    source_section: Optional[str] = None
    note_zh: Optional[str] = None


class TropicalRotationMotion(PartialOutput):
    method_id: Optional[str] = None
    epoch_jd_tt: Optional[float] = None
    native_version: Optional[str] = None
    binding_version: Optional[str] = None
    source_function: Optional[str] = None
    source_url: Optional[str] = None
    step_days: Optional[float] = None
    scope: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    nutation_obliquity_rate_degrees_per_day: Optional[float] = None


class LunarSpatialAberrationMotion(PartialOutput):
    method_id: Optional[str] = None
    status: Optional[str] = None
    source_function: Optional[str] = None
    native_backward_step_days: Optional[float] = None
    longitude_speed_correction: Optional[float] = None
    observer_beta_held_fixed: Optional[bool] = None
    positions_unchanged: Optional[bool] = None
    native_binary_arithmetic_identity_certified: Optional[bool] = None
    scope: Optional[str] = None


class LunarObserverVelocitySample(PartialOutput):
    epoch_jd_tt: Optional[float] = None
    velocity_au_per_native_argument_day: Optional[List[float]] = None
    is_center: Optional[bool] = None


class LunarFixedFrameSourceMotion(PartialOutput):
    method_id: Optional[str] = None
    epoch_jd_tt: Optional[float] = None
    ephemeris_model: Optional[str] = None
    fixed_frame_id: Optional[str] = None
    fixed_frame_epoch_jd_tt: Optional[float] = None
    input_frame_held_fixed: Optional[bool] = None
    input_velocity_time_variable: Optional[str] = None
    full_fixed_frame_apparent_position_au: Optional[List[float]] = None
    full_fixed_frame_velocity_au_per_native_argument_day: Optional[List[float]] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    source_function: Optional[str] = None
    preaberration_source: Optional[str] = None
    scope: Optional[str] = None
    acceleration_steps_days: Optional[List[float]] = None
    selected_step_days: Optional[float] = None
    acceleration_agreement_line_au_per_day2: Optional[float] = None
    observer_agreement_line_arcsec_per_day: Optional[float] = None
    position_reproduction_line_arcsec: Optional[float] = None
    positions_unchanged: Optional[bool] = None
    complete_moving_frame_derivative_certified: Optional[bool] = None
    native_binary_arithmetic_identity_certified: Optional[bool] = None
    source_window: Optional[Dict[str, Any]] = None
    selected_stencil: Optional[str] = None
    stencil_offsets: Optional[List[int]] = None
    stencil_integer_weights: Optional[List[int]] = None
    stencil_divisor: Optional[int] = None
    sample_count: Optional[int] = None
    acceleration_estimates_au_per_day2: Optional[List[List[float]]] = None
    acceleration_samples: Optional[List[LunarObserverVelocitySample]] = None
    acceleration_difference_au_per_day2: Optional[float] = None
    observer_derivative_disagreement_arcsec_per_day: Optional[float] = None
    center_native_states_reproduced_exactly: Optional[bool] = None
    center_file_context_reproduced_exactly: Optional[bool] = None
    full_fixed_frame_longitude_speed_degrees_per_day: Optional[float] = None
    native_fixed_frame_longitude_speed_degrees_per_day: Optional[float] = None
    observer_beta_jvp_longitude_speed_degrees_per_day: Optional[float] = None
    source_position_reproduction_arcsec: Optional[float] = None
    source_radius_reproduction_error_au: Optional[float] = None
    longitude_speed_correction: Optional[float] = None


class LunarLightTimeMotion(PartialOutput):
    method_id: Optional[str] = None
    native_version: Optional[str] = None
    binding_version: Optional[str] = None
    ephemeris_model: Optional[str] = None
    epoch_jd_tt: Optional[float] = None
    source_url: Optional[str] = None
    source_function: Optional[str] = None
    scope: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    frame_method: Optional[str] = None
    longitude_origin_invariance: Optional[str] = None
    light_time_days: Optional[float] = None
    light_time_derivative: Optional[float] = None
    longitude_speed_correction: Optional[float] = None
    spatial_aberration: Optional[LunarSpatialAberrationMotion] = None
    fixed_frame_source_derivative: Optional[LunarFixedFrameSourceMotion] = None
    latitude_reproduction_error_degrees: Optional[float] = None
    radius_reproduction_error_au: Optional[float] = None
    source_factors: Optional[List[str]] = None
    source_contexts: Optional[Dict[str, PhysicalFactorSource]] = None


class DirectionalMotionEstimate(PartialOutput):
    sample_count: Optional[int] = None
    forward_rate: Optional[float] = None
    backward_rate: Optional[float] = None


class DirectionalMotionCheck(PartialOutput):
    method_id: Optional[str] = None
    step_days: Optional[float] = None
    central_step_days: Optional[float] = None
    estimates: Optional[List[DirectionalMotionEstimate]] = None
    central_rates: Optional[List[float]] = None
    forward_rate: Optional[float] = None
    backward_rate: Optional[float] = None
    disagreement_arcsec_per_day: Optional[float] = None
    passed: Optional[bool] = None
    legacy_six_point_forward_rate: Optional[float] = None
    legacy_six_point_backward_rate: Optional[float] = None
    legacy_disagreement_arcsec_per_day: Optional[float] = None
    legacy_passed: Optional[bool] = None


class PositionMotionAttempt(PartialOutput):
    selected_stencil: Optional[str] = None
    steps_days: Optional[List[float]] = None
    rates: Optional[List[float]] = None
    pair_differences_arcsec_per_day: Optional[List[float]] = None
    directional_checks: Optional[List[DirectionalMotionCheck]] = None
    consecutive_converged_pairs: Optional[int] = None
    status: Optional[str] = None


class PositionMotionRefinementBudget(PartialOutput):
    method_id: Optional[str] = None
    epoch_ulp_days: Optional[float] = None
    coordinate_quantization_degrees: Optional[float] = None
    minimum_epoch_ulps: Optional[int] = None
    directional_l1_norm: Optional[float] = None
    estimated_roundoff_floor_days: Optional[float] = None
    minimum_step_days: Optional[float] = None
    scope: Optional[str] = None


class RetardedEpochSampling(PartialOutput):
    symmetric_stabilized_attempt: Optional[PositionMotionAttempt] = None
    acceptance_scope: Optional[str] = None
    refinement_budget: Optional[PositionMotionRefinementBudget] = None
    directional_guard_method_id: Optional[str] = None
    method_id: Optional[str] = None
    unstabilized_attempt: Optional[PositionMotionAttempt] = None
    candidate_steps_days: Optional[List[float]] = None
    required_consecutive_converged_pairs: Optional[int] = None
    consecutive_converged_pairs: Optional[int] = None
    one_sided_checks: Optional[List[DirectionalMotionCheck]] = None
    sample_count: Optional[int] = None
    maximum_epoch_remainder_days: Optional[float] = None
    maximum_sampling_shift_arcseconds: Optional[float] = None
    displayed_native_position_changed: Optional[bool] = None
    scope: Optional[str] = None


CenterFileCell = Annotated[
    str,
    Field(
        pattern=r"^center_files_(solar_direction|solar_cell_([0-9]|[1-9][0-9]|100))$"
    ),
]


class MotionSourceFileWindow(PartialOutput):
    slot: Optional[int] = None
    filename: Optional[str] = None
    start_jd_tt: Optional[float] = None
    end_jd_tt: Optional[float] = None


class CenterFileReplay(PartialOutput):
    method_id: Optional[str] = None
    center_native_state_reproduced_exactly: Optional[bool] = None
    source_context: Optional[PhysicalFactorSource] = None
    center_windows: Optional[List[MotionSourceFileWindow]] = None
    replay_anchor_jd_tt: Optional[List[float]] = None
    sample_count: Optional[int] = None
    ineligible_sample_count: Optional[int] = None
    displayed_native_position_changed: Optional[bool] = None
    scope: Optional[str] = None


class SolarBranchGeometry(PartialOutput):
    method_id: Optional[str] = None
    source_url: Optional[str] = None
    status: Optional[str] = None
    cell: Optional[Union[int, CenterFileCell]] = Field(
        default=None,
        description="Solar mass cell index, or an explicitly named replayed-center-file cell; a file-cell label is not a solar radius fraction.",
    )
    impact_solar_radius_fraction: Optional[float] = None
    cross_product_impact_fraction: Optional[float] = None
    arithmetic_margin_fraction: Optional[float] = None
    scope: Optional[str] = None


class SolarBranchSide(PartialOutput):
    direction: Optional[int] = None
    node_cells: Optional[List[Optional[Union[int, CenterFileCell]]]] = None
    eligible: Optional[bool] = None


class SolarBranchEstimate(PartialOutput):
    direction: Optional[int] = None
    sample_count: Optional[int] = None
    rate: Optional[float] = None


class SolarBranchLevel(PartialOutput):
    step_days: Optional[float] = None
    sides: Optional[List[SolarBranchSide]] = None
    estimates: Optional[List[SolarBranchEstimate]] = None
    eligible_directions: Optional[List[int]] = None
    passed: Optional[bool] = None
    rate: Optional[float] = None
    disagreement_arcsec_per_day: Optional[float] = None


class DecimalApparentReduction(PartialOutput):
    method_id: Optional[
        Literal[
            "native_geometric_decimal_apparent_reduction_v1",
            "native_geometric_decimal_apparent_reduction_v2",
        ]
    ] = None
    ephemeris_model: Optional[Literal["swieph", "jpl"]] = None
    center_interpolation_branch: Optional[SolarBranchGeometry] = None
    precision_decimal_digits: Optional[Literal[50]] = None
    solar_mass_profile_sha256: Optional[str] = None
    frame_basis_bodies: Optional[List[str]] = None
    sample_count: Optional[int] = None
    maximum_frame_orthogonality_error: Optional[float] = None
    maximum_epoch_remainder_days: Optional[float] = None
    center_sampling_shift_arcseconds: Optional[float] = None
    displayed_native_position_changed: Optional[Literal[False]] = None
    independent_astronomical_accuracy_certified: Optional[Literal[False]] = None
    scope: Optional[str] = None


class SolarBranchMotion(PartialOutput):
    decimal_reduction: Optional[DecimalApparentReduction] = None
    center_file_replay: Optional[CenterFileReplay] = None
    refinement_budget: Optional[PositionMotionRefinementBudget] = None
    method_id: Optional[str] = None
    source_function: Optional[str] = None
    center: Optional[SolarBranchGeometry] = None
    status: Optional[str] = None
    levels: Optional[List[SolarBranchLevel]] = None
    required_consecutive_levels: Optional[int] = None
    convergence_line_arcsec_per_day: Optional[float] = None
    scope: Optional[str] = None
    selected_step_days: Optional[float] = None
    eligible_directions: Optional[List[int]] = None
    selected_rate: Optional[float] = None
    steps_days: Optional[List[float]] = None
    candidate_steps_days: Optional[List[float]] = None
    rates: Optional[List[float]] = None
    pair_differences_arcsec_per_day: Optional[List[float]] = None
    consecutive_converged_pairs: Optional[int] = None
    probe_count: Optional[int] = None


class CompletePositionMotion(PartialOutput):
    decimal_reduction_previous_attempt: Optional[SolarBranchMotion] = None
    source_branch_motion: Optional[SolarBranchMotion] = None
    center_file_replay_attempts: Optional[List[SolarBranchMotion]] = None
    refinement_budget: Optional[PositionMotionRefinementBudget] = None
    sun_extension_previous_attempt: Optional[PositionMotionAttempt] = None
    directional_guard_method_id: Optional[str] = None
    directional_checks: Optional[List[DirectionalMotionCheck]] = None
    method_id: Optional[str] = None
    native_version: Optional[str] = None
    binding_version: Optional[str] = None
    ephemeris_model: Optional[str] = None
    epoch_jd_tt: Optional[float] = None
    reference_frame: Optional[str] = None
    steps_days: Optional[List[float]] = None
    candidate_steps_days: Optional[List[float]] = None
    selection_policy: Optional[str] = None
    selected_stencil: Optional[str] = None
    primary_attempt: Optional[PositionMotionAttempt] = None
    sampling_stabilization: Optional[RetardedEpochSampling] = None
    pair_differences_arcsec_per_day: Optional[List[float]] = None
    chosen_step_days: Optional[float] = None
    convergence_line_arcsec_per_day: Optional[float] = None
    source_url: Optional[str] = None
    numerical_source_url: Optional[str] = None
    scope: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    step_rates_degrees_per_day: Optional[List[float]] = None
    step_difference_arcsec_per_day: Optional[float] = None
    source_contexts: Optional[Dict[str, PhysicalFactorSource]] = None


class LunarSourceFileWindow(PartialOutput):
    slot: Optional[int] = None
    filename: Optional[str] = None
    start_jd_tt: Optional[float] = None
    end_jd_tt: Optional[float] = None
    de_number: Optional[int] = None


class LunarSourceWindow(PartialOutput):
    method_id: Optional[str] = None
    epoch_jd_tt: Optional[float] = None
    ephemeris_model: Optional[str] = None
    native_version: Optional[str] = None
    binding_version: Optional[str] = None
    source_url: Optional[str] = None
    source_function: Optional[str] = None
    scope: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    light_time_days: Optional[float] = None
    retarded_jd_tt: Optional[float] = None
    selected_windows: Optional[List[LunarSourceFileWindow]] = None
    selected_windows_after_recomputation: Optional[List[LunarSourceFileWindow]] = None
    initial_spherical_coordinates: Optional[List[float]] = None
    coherent_spherical_coordinates: Optional[List[float]] = None
    initial_native_state: Optional[List[float]] = None
    coherent_native_state: Optional[List[float]] = None
    requested_coordinate_flags: Optional[int] = None
    coordinate_kind: Optional[str] = None
    source_contexts: Optional[Dict[str, PhysicalFactorSource]] = None


class SiderealOriginMotion(PartialOutput):
    method_id: Optional[str] = None
    epoch_jd_tt: Optional[float] = None
    native_version: Optional[str] = None
    binding_version: Optional[str] = None
    source_url: Optional[str] = None
    source_function: Optional[str] = None
    sidereal_mode: Optional[str] = None
    native_divisor_days: Optional[float] = None
    positions_unchanged: Optional[bool] = None
    complete_origin_derivative_certified: Optional[bool] = None
    physical_TT_clock_mapping_certified: Optional[bool] = None
    scope: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    previous_epoch_jd_tt: Optional[float] = None
    actual_binary64_interval_days: Optional[float] = None
    previous_origin_degrees: Optional[float] = None
    current_origin_degrees: Optional[float] = None
    previous_returned_flags: Optional[int] = None
    current_returned_flags: Optional[int] = None
    requested_origin_flags: Optional[int] = None
    raw_difference_degrees: Optional[float] = None
    principal_difference_degrees: Optional[float] = None
    whole_turns_removed: Optional[int] = None
    longitude_speed_correction: Optional[float] = None
    center_origin_reproduced_exactly: Optional[bool] = None


class LongitudeMotionPolicy(PartialOutput):
    method_id: Optional[str] = None
    tropical_rotation: Optional[TropicalRotationMotion] = None
    lunar_light_time: Optional[LunarLightTimeMotion] = None
    traditional_sidereal_origin_wrap: Optional[SiderealOriginMotion] = None
    lunar_source_windows: Optional[Dict[str, LunarSourceWindow]] = None
    complete_position_derivatives: Optional[Dict[str, CompletePositionMotion]] = None
    display_frame: Optional[str] = None
    display_rotation_correction_applied: Optional[bool] = None
    display_longitude_offset_speed_degrees_per_day: Optional[float] = None
    scope: Optional[str] = None


class ChartProfile(PartialOutput):
    ephemeris_reference_points: Optional[EphemerisReferencePoints] = None
    apparent_position_policy: Optional[ApparentPositionPolicy] = None
    longitude_motion: Optional[LongitudeMotionPolicy] = None
    ephemeris_model_scope: Optional[str] = None
    nonphysical_factor_models: Optional[Dict[str, str]] = None
    physical_ephemeris_source: Optional[PhysicalEphemerisSource] = None
    fixed_stars: Optional[FixedStarProfile] = None
    house_axis_convention: Optional[HouseAxisConvention] = None
    earth_rotation: Optional[EarthRotationPolicy] = None
    planetary_models: Optional[Dict[str, str]] = None
    orbital_fallback: Optional[OrbitalFallback] = None
    sidereal_planetary_methods: Optional[Dict[str, str]] = None
    angle_definition: Optional[GeographicPoleAngleDefinition] = None
    house_overlay_policy: Optional[str] = None
    derivation_policy: Optional[RelationshipDerivation] = None
    aspect_policy: Optional[ChartAspectPolicy] = None
    house_position_projection: Optional[HousePositionProjection] = None
    coordinate_precision: Optional[str] = None
    midpoint_coordinate_source: Optional[str] = None
    midpoint_antipodal_policy: Optional[str] = None
    calendar: Optional[str] = None
    time_scale: Optional[str] = None
    julian_day_tt: Optional[float] = None
    julian_day_ut1: Optional[float] = None
    future_leap_seconds_assumed_unchanged: Optional[bool] = None
    horizon_method: Optional[str] = None
    angle_method: Optional[str] = None
    sect_convention: Optional[str] = None
    ayanamsha: Optional[float] = None
    ayanamsha_mean: Optional[float] = None
    ayanamsha_includes_nutation: Optional[bool] = None
    sidereal_position_method: Optional[str] = None
    sidereal_house_method: Optional[str] = None
    chart_type: Optional[str] = None
    engine_backend: Optional[str] = None
    engine_precision: Optional[str] = None
    ephemeris_model: Optional[str] = None
    house_system: Optional[str] = None
    house_system_code: Optional[int] = None
    house_system_label_zh: Optional[str] = None
    house_system_source: Optional[str] = None
    tradition: Optional[bool] = None
    zodiac: Optional[str] = None
    zodiac_label_zh: Optional[str] = None
    zodiacal: Optional[int] = None
    analysis_focus: Optional[str] = None


class ClassicalLot(PartialOutput):
    almuten: Optional[str] = None
    cn: Optional[str] = None
    degree_in_sign: Optional[float] = None
    dispositor: Optional[str] = None
    longitude: Optional[float] = None
    sign: Optional[str] = None


class EssentialDignities(PartialOutput):
    bound_lord: Optional[str] = None
    debilities: Optional[List[str]] = None
    dignities: Optional[List[str]] = None
    face_lord: Optional[str] = None
    labels_zh: Optional[List[str]] = None
    peregrine: Optional[bool] = None
    score: Optional[int] = None
    known_score: Optional[int] = None
    unknown_dignities: Optional[List[str]] = None
    triplicity_ruler: Optional[str] = None


class Melothesia(PartialOutput):
    body_parts: Optional[List[str]] = None
    position: Optional[str] = None


class OrientalityPolicy(PartialOutput):
    model: Optional[Literal["ecliptic_longitude_phase"]] = None
    arithmetic: Optional[Literal["exact_supplied_finite_angles"]] = None
    conjunction: Optional[Literal["unknown_at_exact_coincidence"]] = None
    opposition: Optional[Literal["oriental_legacy_half_open_tie"]] = None
    nonzero_deadband: Optional[Literal["none"]] = None
    physical_rise_set_verified: Optional[Literal[False]] = None
    heliacal_visibility_verified: Optional[Literal[False]] = None
    author_transition_endpoints_certified: Optional[Literal[False]] = None


class ClassicalPlanet(PartialOutput):
    above_horizon: Optional[bool] = None
    angularity: Optional[str] = None
    combustion: Optional[str] = None
    dodekatemorion: Optional[str] = None
    essential: Optional[EssentialDignities] = None
    in_halb: Optional[bool] = None
    joy: Optional[bool] = None
    melothesia: Optional[Melothesia] = None
    ninth_part: Optional[str] = None
    orientality: Optional[str] = None
    out_of_bounds: Optional[bool] = None
    retrograde: Optional[bool] = None
    sect_placement: Optional[str] = None


class PtolemyTerm(PartialOutput):
    lord: Optional[str] = None
    start_degree: Optional[int] = Field(default=None, ge=0, lt=30)
    end_degree: Optional[int] = Field(default=None, gt=0, le=30)
    chapter_ref: Optional[str] = None


class PtolemyPlanet(PartialOutput):
    longitude: Optional[float] = Field(default=None, ge=0, lt=360)
    sign: Optional[str] = None
    degree_in_sign: Optional[float] = Field(default=None, ge=0, lt=30)
    domicile_lord: Optional[str] = None
    in_domicile: Optional[bool] = None
    in_exaltation: Optional[bool] = None
    in_depression: Optional[bool] = None
    triplicity_primary: Optional[str] = None
    triplicity_co_ruler: Optional[str] = None
    natural_sect: Optional[str] = None
    terms: Optional[Dict[str, PtolemyTerm]] = None


class PtolemyFortune(PartialOutput):
    formula: Optional[str] = None
    longitude: Optional[float] = Field(default=None, ge=0, lt=360)
    sign: Optional[str] = None
    degree_in_sign: Optional[float] = Field(default=None, ge=0, lt=30)
    source_url: Optional[str] = None


class PtolemySignRelationship(PartialOutput):
    planet_a: Optional[str] = None
    planet_b: Optional[str] = None
    sign_a: Optional[str] = None
    sign_b: Optional[str] = None
    separation_signs: Optional[int] = None
    same_sign: Optional[bool] = None
    sign_aspect: Optional[str] = None
    aspect_quality: Optional[str] = None
    commanding_sign: Optional[str] = None
    obeying_sign: Optional[str] = None
    beholding_equal_power: Optional[bool] = None
    disjunct: Optional[bool] = None
    chapter_refs: Optional[List[str]] = None


class PtolemyLayer(PartialOutput):
    orientality_policy: Optional[OrientalityPolicy] = None
    term_policy: Optional[str] = None
    term_source_url: Optional[str] = None
    term_transcription_note: Optional[str] = None
    sign_relationships: Optional[List[PtolemySignRelationship]] = None
    sign_relationship_policy: Optional[str] = None
    lot_of_fortune: Optional[PtolemyFortune] = None
    ruleset_id: Optional[str] = None
    author: Optional[str] = None
    edition: Optional[str] = None
    source_url: Optional[str] = None
    chapters: Optional[Dict[str, str]] = None
    status: Optional[str] = None
    scope: Optional[str] = None
    planets: Optional[Dict[str, PtolemyPlanet]] = None


class AlmutenPoint(PartialOutput):
    degree_in_sign: Optional[float] = None
    sign: Optional[str] = None
    totals: Optional[Dict[str, int]] = None
    winner: Optional[str] = None


class AlmutenFiguris(PartialOutput):
    points: Optional[Dict[str, AlmutenPoint]] = None
    totals: Optional[Dict[str, int]] = None
    winner: Optional[str] = None


class DispositorChain(PartialOutput):
    chain: Optional[List[str]] = None
    terminal: Optional[str] = None
    terminal_type: Optional[str] = None


class Dispositors(PartialOutput):
    chains: Optional[Dict[str, DispositorChain]] = None
    final_dispositors: Optional[List[str]] = None
    mutual_receptions: Optional[List[List[str]]] = None


class SyzygySolver(PartialOutput):
    method: Optional[str] = None
    target_elongation: Optional[float] = None
    residual_degrees: Optional[float] = Field(default=None, ge=0, lt=1e-6)
    strictly_before_birth: Optional[bool] = None


class SyzygySampleSource(PartialOutput):
    body: Optional[str] = None
    stage: Optional[str] = None
    model: Optional[str] = None
    status: Optional[str] = None
    file_ids: Optional[List[str]] = None
    sample_count: Optional[int] = Field(default=None, ge=1)
    minimum_jd_tt: Optional[float] = None
    maximum_jd_tt: Optional[float] = None


class SyzygyEphemerisSource(PartialOutput):
    method_id: Optional[str] = None
    models_by_body: Optional[Dict[str, List[str]]] = None
    models_stable: Optional[bool] = None
    sample_contexts: Optional[List[SyzygySampleSource]] = None
    physical_ephemeris_source: Optional[PhysicalEphemerisSource] = None
    absolute_accuracy_certified: Optional[bool] = None
    scope: Optional[str] = None
    note_zh: Optional[str] = None


class Syzygy(PartialOutput):
    degree_in_sign: Optional[float] = Field(default=None, ge=0, lt=30)
    julian_day: Optional[float] = None
    julian_day_ut1: Optional[float] = None
    julian_day_tt: Optional[float] = None
    event_datetime_utc: Optional[str] = None
    utc_representation: Optional[WesternUTCRepresentation] = None
    longitude: Optional[float] = Field(default=None, ge=0, lt=360)
    tropical_longitude: Optional[float] = Field(default=None, ge=0, lt=360)
    sign: Optional[str] = None
    type: Optional[str] = None
    zodiac: Optional[str] = None
    solver: Optional[SyzygySolver] = None
    ephemeris_source: Optional[SyzygyEphemerisSource] = None


class Temperament(PartialOutput):
    cn: Optional[str] = None
    humor: Optional[str] = None
    hygral: Optional[str] = None
    tally: Optional[Dict[str, int]] = None
    thermal: Optional[str] = None


class TopicAlmuten(PartialOutput):
    sign: Optional[str] = None
    winner: Optional[str] = None


class SolarConditionPolicy(PartialOutput):
    rule_id: Optional[str] = None
    source_edition: Optional[str] = None
    source_url: Optional[str] = None
    printed_page: Optional[int] = None
    cazimi_limit_exact_degrees: Optional[str] = None
    combust_limit_degrees: Optional[float] = None
    under_beams_limit_degrees: Optional[float] = None
    combust_requires_same_sign: Optional[bool] = None
    interval_policy: Optional[str] = None
    zodiac_policy: Optional[str] = None
    printed_example_discrepancy: Optional[str] = None
    full_page_acceptance: Optional[bool] = None


class Classical(PartialOutput):
    orientality_policy: Optional[OrientalityPolicy] = None
    solar_condition_policy: Optional[SolarConditionPolicy] = None
    obliquity: Optional[float] = None
    source_profile: Optional[str] = None
    ptolemy: Optional[PtolemyLayer] = None
    almuten_figuris: Optional[AlmutenFiguris] = None
    dispositors: Optional[Dispositors] = None
    lots: Optional[Dict[str, ClassicalLot]] = None
    planets: Optional[Dict[str, ClassicalPlanet]] = None
    sect: Optional[str] = None
    syzygy: Optional[Syzygy] = None
    temperament: Optional[Temperament] = None
    topic_almutens: Optional[Dict[str, TopicAlmuten]] = None


class Bonification(PartialOutput):
    bonified_by: Optional[List[str]] = None
    maltreated_by: Optional[List[str]] = None


class Overcoming(PartialOutput):
    overcome: Optional[str] = None
    overcomer: Optional[str] = None


class Translation(PartialOutput):
    from_: Optional[str] = Field(default=None, alias="from")
    translator: Optional[str] = None
    to: Optional[str] = None


class Collection(PartialOutput):
    from_: Optional[List[str]] = Field(default=None, alias="from")
    collector: Optional[str] = None


class NodalBending(PartialOutput):
    planet: Optional[str] = None
    bending: Optional[str] = None
    orb: Optional[float] = None


class PtolemyLatitudeCondition(PartialOutput):
    status: Optional[str] = None
    latitude_a: Optional[float] = None
    latitude_b: Optional[float] = None
    source_url: Optional[str] = None
    policy: Optional[str] = None


class AspectMotion(PartialOutput):
    ptolemy_latitude_condition: Optional[PtolemyLatitudeCondition] = None
    planet_a: Optional[str] = None
    planet_b: Optional[str] = None
    aspect: Optional[str] = None
    exact_angle: Optional[float] = None
    separation: Optional[float] = None
    orb: Optional[float] = None
    relative_longitude_speed: Optional[float] = None
    phase: Optional[
        Literal["applying", "separating", "exact", "stationary", "unavailable"]
    ] = None


class AspectApplicationPolicy(PartialOutput):
    rule_id: Optional[str] = None
    method: Optional[str] = None
    speed_unit: Optional[str] = None
    scope: Optional[str] = None
    source_url: Optional[str] = None


class LightConfigurationPolicy(PartialOutput):
    rule_id: Optional[str] = None
    source_edition: Optional[str] = None
    source_url: Optional[str] = None
    translation_definition_page: Optional[int] = None
    collection_judgement_page: Optional[int] = None
    weight_order: Optional[List[str]] = None
    status: Optional[str] = None
    full_original_text_acceptance: Optional[bool] = None
    unverified_conditions: Optional[List[str]] = None


class ClassicalPatterns(PartialOutput):
    light_configuration_policy: Optional[LightConfigurationPolicy] = None
    aspect_motion: Optional[List[AspectMotion]] = None
    application_policy: Optional[AspectApplicationPolicy] = None
    aversions: Optional[List[List[str]]] = None
    besiegement: Optional[Dict[str, str]] = None
    bonification: Optional[Dict[str, Bonification]] = None
    collection_of_light: Optional[List[Collection]] = None
    nodal_bending: Optional[List[NodalBending]] = None
    overcoming: Optional[List[Overcoming]] = None
    sect_benefic: Optional[str] = None
    sect_malefic: Optional[str] = None
    translation_of_light: Optional[List[Translation]] = None


class Hellenistic(PartialOutput):
    angular_planets: Optional[List[str]] = None
    ascendant_ruler: Optional[str] = None
    lot_of_fortune: Optional[ChartPlanet] = None
    sect: Optional[str] = None


class PlanetMansion(PartialOutput):
    id: Optional[str] = None
    su28: Optional[str] = None


class MoiraPattern(PartialOutput):
    basis: Optional[str] = None
    classical_acceptance: Optional[bool] = None
    detail: Optional[str] = None
    dsl: Optional[str] = None
    level: Optional[str] = None
    name: Optional[str] = None
    score: Optional[str] = None
    source: Optional[str] = None
    rule_id: Optional[str] = None
    evidence: Optional[GuolaoPatternEvidence] = None


class Guolao(GuolaoResearch):
    god_sign_index: Optional[Dict[str, int]] = None
    lunar_mansion_system: Optional[str] = None
    moira_patterns: Optional[List[MoiraPattern]] = None
    moon_mansion: Optional[str] = None
    planetary_mansions: Optional[List[GuolaoMansion]] = None
    si_yu_sign_index: Optional[Dict[str, int]] = None
    weekday_ruler: Optional[str] = None


class India(JyotishIndia):
    """Legacy name retained for the expanded Indian contract."""


class ThirteenSector(PartialOutput):
    cusp_longitude: Optional[float] = None
    end_longitude: Optional[float] = None
    width_degrees: Optional[float] = None
    sector: Optional[int] = None
    sign: Optional[str] = None


class Midpoint(PartialOutput):
    opposite_longitude: Optional[float] = None
    antipodal_inputs: Optional[bool] = None
    computed_from_unrounded: Optional[bool] = None
    degree_in_sign: Optional[float] = None
    id_a: Optional[str] = None
    id_b: Optional[str] = None
    idA: Optional[str] = None
    idB: Optional[str] = None
    longitude: Optional[float] = None
    sign: Optional[str] = None
    sign_zh: Optional[str] = None


class MidpointAspect(PartialOutput):
    aspect: Optional[str] = None
    midpoint: Optional[str] = None
    orb: Optional[float] = None
    planet: Optional[str] = None


class RelativeMidpointHit(PartialOutput):
    aspect: Optional[str] = None
    delta: Optional[float] = None
    midpoint: Optional[Midpoint] = None


class RelativeContact(PartialOutput):
    aspect: Optional[str] = None
    delta: Optional[float] = None
    id: Optional[str] = None


class DirectionalContacts(PartialOutput):
    id: Optional[str] = None
    objects: Optional[List[RelativeContact]] = None


class RelativeAntiscia(PartialOutput):
    idA: Optional[str] = None
    idB: Optional[str] = None
    delta: Optional[float] = None


class SynastryAspect(PartialOutput):
    aspect: Optional[str] = None
    inner: Optional[str] = None
    orb: Optional[float] = None
    outer: Optional[str] = None


class CompatibilityScores(PartialOutput):
    element_harmony_score: Optional[int] = None
    modality_balance_score: Optional[int] = None
    overall_score: Optional[int] = None
    synastry_aspect_score: Optional[int] = None


class CompatibilityOverlap(PartialOutput):
    inner_counts: Optional[Dict[str, int]] = None
    outer_counts: Optional[Dict[str, int]] = None
    overlap_count: Optional[int] = None
    denominator: Optional[int] = None
    unrounded_score: Optional[float] = None
    score: Optional[int] = None


class ScoredSynastryContact(SynastryAspect):
    synastry_aspect_index: Optional[int] = None
    delta: Optional[int] = None


class CompatibilityAspectSelection(PartialOutput):
    candidate_count: Optional[int] = None
    nominal_limit: Optional[int] = None
    cutoff_orb: Optional[float] = None
    boundary_tie_count: Optional[int] = None
    selected_count: Optional[int] = None
    excluded_count: Optional[int] = None
    selected_contacts: Optional[List[ScoredSynastryContact]] = None
    baseline: Optional[int] = None
    positive_count: Optional[int] = None
    negative_count: Optional[int] = None
    unclamped_score: Optional[int] = None
    clamped: Optional[bool] = None
    score: Optional[int] = None


class CompatibilityOverall(PartialOutput):
    numerator: Optional[int] = None
    denominator: Optional[int] = None
    unrounded_score: Optional[float] = None
    score: Optional[int] = None


class CompatibilityEvidence(PartialOutput):
    rule_id: Optional[str] = None
    source_paths: Optional[List[str]] = None
    element_overlap: Optional[CompatibilityOverlap] = None
    modality_overlap: Optional[CompatibilityOverlap] = None
    aspect_selection: Optional[CompatibilityAspectSelection] = None
    overall: Optional[CompatibilityOverall] = None


class BirthClockConversion(PartialOutput):
    ruleset_id: Optional[str] = None
    author: Optional[str] = None
    input_clock_basis: Optional[str] = None
    input_wall_datetime: Optional[str] = None
    longitude_east_degrees: Optional[float] = None
    longitude_offset_seconds: Optional[float] = None
    equation_of_time_seconds: Optional[float] = None
    sun_apparent_right_ascension_degrees: Optional[float] = None
    greenwich_apparent_sidereal_degrees: Optional[float] = None
    solar_ephemeris_model: Optional[str] = None
    solar_ephemeris_policy: Optional[str] = None
    input_calendar: Optional[str] = None
    solar_ephemeris_models_observed: Optional[List[str]] = None
    solar_model_call_count: Optional[int] = None
    solar_reference: Optional[str] = None
    sidereal_time_model: Optional[str] = None
    earth_rotation_policy_id: Optional[str] = None
    target_julian_day_ut1: Optional[float] = None
    julian_day_ut1: Optional[float] = None
    converted_utc: Optional[str] = None
    time_scale_method: Optional[str] = None
    future_leap_seconds_assumed_unchanged: Optional[bool] = None
    ut1_roundtrip_error_seconds: Optional[float] = None
    input_clock_roundtrip_error_seconds: Optional[float] = None
    numerical_resolution_seconds: Optional[float] = None
    measured_eop_applied: Optional[bool] = None
    clock_accuracy_certified: Optional[bool] = None
    swisseph_version: Optional[str] = None
    source_url: Optional[str] = None
    source_code_url: Optional[str] = None
    source_sections: Optional[str] = None


class WesternSolarTimeReference(PartialOutput):
    method_id: Optional[
        Literal[
            "western_solar_rebase_ut1_v1", "western_solar_rebase_coherent_tt_ut1_v2"
        ]
    ] = None
    recorded_utc: Optional[str] = None
    recorded_julian_day_tt: Optional[float] = Field(default=None, allow_inf_nan=False)
    equation_of_time_julian_day_ut1: Optional[float] = Field(
        default=None, allow_inf_nan=False
    )
    equation_of_time_seconds: Optional[float] = Field(default=None, allow_inf_nan=False)
    sun_apparent_right_ascension_degrees: Optional[float] = Field(
        default=None, allow_inf_nan=False
    )
    greenwich_apparent_sidereal_degrees: Optional[float] = Field(
        default=None, allow_inf_nan=False
    )
    solar_ephemeris_model: Optional[str] = None
    solar_ephemeris_source: Optional[dict[str, Any]] = None
    sidereal_time_model: Optional[str] = None
    earth_rotation_policy_id: Optional[str] = None
    rebase_arithmetic: Optional[Literal["frozen_recorded_utc_offset_v1"]] = None
    recorded_local_datetime: Optional[str] = None
    recorded_utc_offset_seconds: Optional[float] = Field(
        default=None, allow_inf_nan=False
    )
    rebased_solar_clock_datetime: Optional[str] = None
    rebased_utc: Optional[str] = None
    rebase_utc_shift_seconds: Optional[float] = Field(default=None, allow_inf_nan=False)
    time_scale_method: Optional[str] = None
    future_leap_seconds_assumed_unchanged: Optional[bool] = None
    scope: Optional[str] = None


class ChartTrueSolar(PartialOutput):
    applied: Optional[bool] = None
    correction_minutes: Optional[float] = Field(default=None, allow_inf_nan=False)
    time_reference: Optional[WesternSolarTimeReference] = None


class ChartPerson(PersonInfo):
    timezone_source: Optional[
        Literal["birth_timezone", "birth_place", "solar_clock_conversion"]
    ] = None
    birth_latitude: Optional[float] = None
    birth_longitude: Optional[float] = None
    birth_place: Optional[str] = None
    birth_timezone: Optional[str] = None
    name: Optional[str] = None
    birth_datetime: Optional[str] = None
    utc_datetime: Optional[str] = None
    clock_conversion: Optional[BirthClockConversion] = None
    true_solar: Optional[ChartTrueSolar] = None


class InterpretationEvidence(PartialOutput):
    source_paths: Optional[List[str]] = None
    kind: Optional[str] = None
    policy_id: Optional[str] = None


class Chart(PartialOutput):
    aspect_evidence: Optional[List[ChartAspect]] = None
    angles: Optional[Dict[str, ChartAngle]] = None
    aspects: Optional[List[ChartAspect]] = None
    balance_basis: Optional[str] = None
    chart_profile: Optional[ChartProfile] = None
    element_balance: Optional[Dict[str, float]] = None
    houses: Optional[List[ChartHouse]] = None
    modality_balance: Optional[Dict[str, float]] = None
    person_info: Optional[ChartPerson] = None
    planets: Optional[List[ChartPlanet]] = None
    summary: Optional[List[str]] = None


class InnerOuter(PartialOutput):
    chart: Optional[Chart] = None
    chart_profile: Optional[ChartProfile] = None
    summary: Optional[List[str]] = None


class RelationshipFocus(PartialOutput):
    emphasis_bodies: Optional[List[str]] = None
    emphasis_houses: Optional[List[int]] = None
    focus: Optional[str] = None
    focus_label_zh: Optional[str] = None
    focused_aspect_count: Optional[int] = None
    focused_synastry_aspects: Optional[List[SynastryAspect]] = None
    note: Optional[str] = None


class RelationshipScoringPolicy(PartialOutput):
    rule_id: Optional[str] = None
    population: Optional[str] = None
    overlap_formula: Optional[str] = None
    aspect_selection: Optional[str] = None
    aspect_baseline: Optional[int] = None
    harmonious_aspects: Optional[List[str]] = None
    per_aspect_delta: Optional[int] = None
    overall_formula: Optional[str] = None
    rounding: Optional[str] = None
    is_probability: Optional[bool] = None
    original_text_rule: Optional[bool] = None
    empirically_calibrated: Optional[bool] = None


class RelationshipProfile(PartialOutput):
    compatibility_policy: Optional[RelationshipScoringPolicy] = None
    relative_midpoint_policy: Optional[str] = None
    derivation_policy: Optional[RelationshipDerivation] = None
    davison_variant: Optional[str] = None
    primary_chart_role: Optional[str] = None
    chart_type: Optional[str] = None
    engine_backend: Optional[str] = None
    engine_precision: Optional[str] = None
    focus: Optional[RelationshipFocus] = None
    house_system: Optional[str] = None
    house_system_label_zh: Optional[str] = None
    hsys: Optional[int] = None
    mode_status: Optional[str] = None
    primary_layer: Optional[str] = None
    relative_mode_input: Optional[Union[str, int]] = None
    relative_mode_label_zh: Optional[str] = None
    relative_mode_normalized: Optional[str] = None
    relative_mode_resolution: Optional[str] = None
    zodiac_label_zh: Optional[str] = None
    zodiac_mode: Optional[str] = None
    zodiacal: Optional[int] = None


CHART_FIELDS: Dict[str, Any] = {
    "aspect_evidence": List[ChartAspect],
    "interpretation_evidence": Dict[str, InterpretationEvidence],
    "angles": Dict[str, ChartAngle],
    "aspects": List[ChartAspect],
    "houses": List[ChartHouse],
    "planets": List[ChartPlanet],
    "fixed_stars": List[FixedStar],
    "planetary_hours": PlanetaryHours,
    "chart_profile": ChartProfile,
    "classical": Classical,
    "classical_patterns": ClassicalPatterns,
    "hellenistic": Hellenistic,
    "guolao": Guolao,
    "india": India,
    "thirteen_sectors": List[ThirteenSector],
    "sector_profile": SectorProfile,
    "midpoint_analysis": MidpointAnalysis,
    "time_sensitivity": SpecialtyTimeSensitivity,
    "midpoints": List[Midpoint],
    "midpoint_aspects": List[MidpointAspect],
    "element_balance": Dict[str, float],
    "modality_balance": Dict[str, float],
    "base_chart": Chart,
    "inner_chart": Chart,
    "outer_chart": Chart,
    "inner": InnerOuter,
    "outer": InnerOuter,
    "compatibility": CompatibilityScores,
    "compatibility_evidence": CompatibilityEvidence,
    "relationship_profile": RelationshipProfile,
    "marks_charts": Dict[str, Chart],
    "synastry_aspects": List[SynastryAspect],
    **{
        name: List[DirectionalContacts]
        for name in (
            "in_to_out_aspects",
            "out_to_in_aspects",
        )
    },
    **{
        name: List[RelativeAntiscia]
        for name in (
            "in_to_out_antiscia",
            "out_to_in_antiscia",
            "in_to_out_contra_antiscia",
            "out_to_in_contra_antiscia",
        )
    },
    **{
        name: Dict[str, List[RelativeMidpointHit]]
        for name in (
            "in_to_out_midpoint",
            "out_to_in_midpoint",
        )
    },
}

CHART_TOOL_FIELDS: Dict[str, Dict[str, Any]] = {
    "astro_chart": {"person_info": ChartPerson},
    "astro_chart13": {"person_info": ChartPerson},
    "astro_relative": {"chart": Chart},
    "astro_relative_chart": {"chart": Chart},
}
