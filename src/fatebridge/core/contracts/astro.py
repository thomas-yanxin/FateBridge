"""Output contracts for Western/classical/hellenistic/Guolao/Astrodice/Chart tools."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, JsonValue

from fatebridge.core.contracts.base import (
    FULL_FACT,
    OpenJsonValue,
    PartialOutput,
    ProjectedOutput,
)
from fatebridge.core.contracts.common import (
    AnalysisContext,
    Object,
    PersonInfo,
    UTCDefinitionEvidence,
    WesternUTCRepresentation,
)
from fatebridge.core.contracts.jyotish import India, Vimshottari
from fatebridge.core.contracts.midpoints import (
    ApparentPositionPolicy,
    EarthRotationPolicy,
    MidpointAnalysis,
    PhysicalEphemerisSource,
    PhysicalFactorSource,
    SectorEvidence,
    SectorProfile,
    SolarEphemerisReference,
    SpecialtyTimeSensitivity,
)
from fatebridge.core.receipt_models import RunMetadata


class EphemerisReferencePoints(PartialOutput):
    policy_id: str | None = None
    body_centers: list[str] | None = None
    system_barycenters: list[str] | None = None
    theoretical_points: list[str] | None = None
    approximate_points: list[str] | None = None
    unresolved_points: list[str] | None = None
    derived_points: list[str] | None = None
    center_body_correction_applied: Literal[False] | None = None
    source_url: str | None = None
    source_section: str | None = None
    additional_source_urls: list[str] | None = None
    note_zh: str | None = None
    scope: str | None = None


class Dignity(PartialOutput):
    dignity: str | None = None
    status_zh: str | None = None
    scope: str | None = None


class ChartPoint(PartialOutput):
    longitude: Annotated[float | None, FULL_FACT] = Field(default=None, ge=0, lt=360)
    degree_in_sign: float | None = Field(default=None, ge=0, lt=30)
    sign: str | None = None
    sign_zh: str | None = None


class ChartPlanet(ChartPoint):
    id: Annotated[str | None, FULL_FACT] = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    house: int | None = None
    ecliptic_house_position: float | None = Field(default=None, ge=1, lt=13)
    element: str | None = None
    modality: str | None = None
    dignity: Dignity | None = None
    su28: str | None = None
    nakshatra: str | None = None
    sector13: int | None = None
    sector13_evidence: SectorEvidence | None = None


PlanetsField = Annotated[
    list[ChartPlanet] | None,
    Field(
        min_length=7,
        json_schema_extra={
            "x-fatebridge-full-result-unique-by": "id",
            "x-fatebridge-full-result-identities": [
                "Sun",
                "Moon",
                "Mercury",
                "Venus",
                "Mars",
                "Jupiter",
                "Saturn",
            ],
        },
    ),
]


class ChartAngle(PartialOutput):
    longitude: float | None = Field(default=None, ge=0, lt=360)
    sign: str | None = None
    sign_zh: str | None = None


class ChartHouse(PartialOutput):
    cusp_longitude: float | None = Field(default=None, ge=0, lt=360)
    house: int | None = None
    sign: str | None = None
    sign_zh: str | None = None


class ChartAspect(PartialOutput):
    planet_a: str | None = None
    planet_b: str | None = None
    aspect: str | None = None
    orb: float | None = Field(default=None, ge=0, le=180)
    exact_angle: float | None = Field(default=None, ge=0, le=180)
    orb_limit: float | None = Field(default=None, ge=0, le=180)
    separation: float | None = Field(default=None, ge=0, le=180)
    rule_id: str | None = None


class FixedStarNature(PartialOutput):
    planet: str | None = None
    qualifier: str | None = None


class FixedStar(PartialOutput):
    nature_components: list[FixedStarNature] | None = None
    nature_source_region: str | None = None
    star_latitude: float | None = None
    nature_source_url: str | None = None
    astrometry_source_url: str | None = None
    catalogue_identifier: str | None = None
    cn: str | None = None
    nature: list[str] | None = None
    orb: float | None = None
    point: str | None = None
    star: str | None = None
    star_longitude: float | None = None


class FixedStarProfile(PartialOutput):
    nature_ruleset_id: str | None = None
    swisseph_version: str | None = None
    orb_limit: float | None = Field(default=None, ge=0, le=180)
    model_id: str | None = None
    status: str | None = None
    catalogue_id: str | None = None
    catalogue_size: int | None = None
    catalogue_epoch: str | None = None
    julian_day_tt: float | None = None
    longitude_frame: str | None = None
    conjunction_basis: str | None = None
    latitude_used_for_conjunction: bool | None = None
    space_motion: str | None = None
    astrometry_source: str | None = None
    nature_source_url: str | None = None
    absolute_sky_accuracy_certified: bool | None = None
    native_flags: list[int] | None = None
    earth_flags: int | None = None
    earth_ephemeris_model: str | None = None
    unavailable_reason: str | None = None
    note_zh: str | None = None


class PlanetaryHours(PartialOutput):
    weekday_clock_basis: str | None = None
    weekday_opening_sunrise_label: str | None = None
    weekday_policy: str | None = None
    day_ruler: str | None = None
    hour_number: int | None = Field(default=None, ge=1, le=12)
    hour_ruler: str | None = None
    is_day: bool | None = None
    planetary_day_start_utc: str | None = None
    arc_start_utc: str | None = None
    arc_end_utc: str | None = None
    hour_start_utc: str | None = None
    hour_end_utc: str | None = None
    arc_start_jd_ut1: float | None = None
    arc_end_jd_ut1: float | None = None
    rule_id: str | None = None
    sunrise_convention: str | None = None
    event_model: str | None = None
    ephemeris_models: list[str] | None = None
    ephemeris_sources: dict[str, SolarEphemerisReference] | None = None
    ephemeris_source_policy: str | None = None
    equatorial_frame: str | None = None
    time_scale: str | None = None
    sequence_source: str | None = None
    sequence_source_url: str | None = None
    source_scope: str | None = None


class ChartAspectPolicy(PartialOutput):
    rule_id: str | None = None
    planet_orbs: dict[str, float] | None = None
    fallback_orb: float | None = Field(default=None, ge=0, le=180)
    combination: str | None = None
    exact_angles: dict[str, float] | None = None
    sextile_square_scale: float | None = Field(default=None, gt=0, le=1)


class TopocentricProjectionBranch(PartialOutput):
    above_horizon: bool | None = None
    reflected_western: bool | None = None
    candidate_scope: str | None = None
    root_selection: str | None = None
    selected_root_degrees: float | None = Field(default=None, ge=0, le=90)
    candidate_root_degrees: list[float] | None = None
    candidate_positions: list[float] | None = None
    computed_root_bracket_width_degrees: str | None = None
    geographic_latitude_used: float | None = Field(default=None, ge=-90, le=90)
    geographic_latitude_input: float | None = Field(default=None, ge=-90, le=90)
    rotation_axis_latitude_used: float | None = Field(default=None, ge=-90, le=90)
    latitude_clamped: bool | None = None


class HouseProjectionPrecisionCheck(PartialOutput):
    tropical_longitude: float | None = None
    native_tropical_longitude: float | None = None
    native_position: float | None = None
    delivered_position: float | None = None
    house: int | None = Field(default=None, ge=1, le=12)
    phase_degrees: float | None = Field(default=None, ge=0, lt=360)
    phase_degrees_decimal: str | None = None
    working_decimal_digits: list[int] | None = None
    action: str | None = None
    topocentric_branch: TopocentricProjectionBranch | None = None


class HouseProjectionPrecision(PartialOutput):
    method_id: str | None = None
    phase_forward_offset_arcseconds: float | None = None
    boundary_policy: str | None = None
    input_precision_scope: str | None = None
    maximum_physical_error_arcseconds: float | None = None
    checks: list[HouseProjectionPrecisionCheck] | None = None
    status: str | None = None
    branch_policy: str | None = None
    native_inverse_latitude_limit_degrees: float | None = None
    latitude_clamped: bool | None = None


class HousePositionProjection(PartialOutput):
    method: str | None = None
    library_version: str | None = None
    factor_source_versions: dict[str, str] | None = None
    factor_source_urls: dict[str, str] | None = None
    reason: str | None = None
    armc: float | None = None
    geographic_latitude: float | None = None
    rotation_axis_latitude: float | None = None
    true_obliquity: float | None = None
    house_code: str | None = None
    input_frame: str | None = None
    backend_longitude_origin: float | None = None
    backend_frame: str | None = None
    input_ecliptic_latitude: float | None = None
    source_url: str | None = None
    source_section: str | None = None
    scope: str | None = None
    precision: HouseProjectionPrecision | None = None
    note_zh: str | None = None


class RelationshipDerivation(PartialOutput):
    method_id: str | None = None
    variant: str | None = None
    source_url: str | None = None
    source_kind: str | None = None
    positions_from_single_instant: bool | None = None
    time_policy: str | None = None
    time_source_scope: str | None = None
    geographic_policy: str | None = None
    longitude_unwrapping: str | None = None
    midpoint_jd_ut1: float | None = None
    input_julian_days_ut1: list[float] | None = None
    midpoint_longitude: float | None = Field(default=None, ge=-180, lt=180)
    midpoint_latitude: float | None = Field(default=None, ge=-90, le=90)
    mc_target_tropical: float | None = Field(default=None, ge=0, lt=360)
    mc_actual_tropical: float | None = Field(default=None, ge=0, lt=360)
    mc_residual_degrees: float | None = Field(default=None, ge=0, le=1e-5)
    time_correction_seconds_ut1: float | None = None
    mc_target_policy: str | None = None
    longitude_policy: str | None = None
    latitude_policy: str | None = None
    house_policy: str | None = None
    mercury_venus_policy: str | None = None
    recipe: str | None = None
    base_davison_variant: str | None = None


class AngleGeometryInputs(PartialOutput):
    geographic_latitude: float | None = None
    rotation_axis_latitude: float | None = None
    armc: float | None = None
    obliquity: float | None = None
    frame: str | None = None


class GeographicPoleAngleDefinition(PartialOutput):
    status: str | None = None
    ascendant_definition: str | None = None
    fixed_direction_diurnal_rising_defined: bool | None = Field(
        default=None,
        description="False for the frozen model's rotation-pole convention. A geographic pole need not coincide with the selected CIP after polar motion; in that case this geographic-coordinate record makes no daily rise/set assertion.",
    )
    reference_meridian: str | None = None
    geometry_inputs: AngleGeometryInputs | None = None
    dependent_quantities: list[str] | None = None
    note_zh: str | None = None
    source_urls: list[str] | None = None


class OrbitalFallback(PartialOutput):
    approximate_planets: list[str] | None = None
    time_argument: str | None = None
    source_path: str | None = None
    method_reference_url: str | None = None
    factor_time_arguments: dict[str, str] | None = None
    julian_day_tt: float | None = None
    tt_source: str | None = None
    library: str | None = None
    library_version: str | None = None
    additional_source_urls: list[str] | None = None
    position_convention: str | None = None
    longitude_motion_method: str | None = None
    factor_longitude_motion_methods: dict[str, str] | None = None
    uncomputed_motion_reasons: dict[str, str] | None = None
    longitude_motion_origin_rate_degrees_per_day: float | None = None
    accuracy_certified: bool | None = None
    note_zh: str | None = None
    candidate_file_year: int | None = None
    candidate_file_utc_calendar_year: int | None = None
    candidate_file_plan_basis: str | None = None
    candidate_files: list[str] | None = Field(
        default=None,
        description="Candidate planet/Moon data segments for the requested CE year, including adjacent-year boundaries. This list is not a file-integrity or loaded-model check.",
    )


class EasternDirectionPrecision(PartialOutput):
    method_id: str | None = None
    working_decimal_digits: list[int] | None = None
    convergence_degrees: str | None = None
    geographic_latitude: float | None = None
    rotation_axis_latitude: float | None = None
    armc: float | None = None
    true_obliquity: float | None = None
    house_auxiliary_tt: float | None = None
    eastern_selector: str | None = None
    intersection_normal_norm: float | None = None
    tropical_model_ascendant: float | None = None
    model_longitude_origin: float | None = None
    input_precision_scope: str | None = None
    maximum_physical_error_arcseconds: float | None = None
    source_url: str | None = None
    source_scope: str | None = None
    native_common_ascendant: float | None = None
    delivered_ascendant: float | None = None
    ascendant_action: str | None = None
    corrected_cusps: list[int] | None = None
    house_cusp_scope: str | None = None
    coordinate_frame: str | None = None
    native_cusps: list[float] | None = None
    delivered_cusps: list[float] | None = None


class HouseAxisConvention(PartialOutput):
    policy_id: str | None = None
    house_code: str | None = None
    longitude_frame: str | None = None
    public_midheaven_definition: str | None = None
    public_ascendant_definition: str | None = None
    public_midheaven: float | None = Field(default=None, ge=0, lt=360)
    native_house_midheaven: float | None = Field(default=None, ge=0, lt=360)
    public_ascendant: float | None = Field(default=None, ge=0, lt=360)
    native_house_ascendant: float | None = Field(default=None, ge=0, lt=360)
    meridian_branch_separation_degrees: float | None = Field(default=None, ge=0, le=180)
    ascendant_branch_separation_degrees: float | None = Field(
        default=None, ge=0, le=180
    )
    native_cusps_and_projection_retained: bool | None = None
    eastern_direction_precision: EasternDirectionPrecision | None = None
    source_url: str | None = None
    source_section: str | None = None
    note_zh: str | None = None


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


class OpaqueSolarConvention(PartialOutput):
    observer: Literal["Earth_geocenter"] | None = None
    solar_radius_m: Literal[695700000] | None = None
    deflection: (
        Literal["finite_source_solar_monopole_except_intercepted_opaque_rays"] | None
    ) = None
    tangent_boundary: Literal["exterior"] | None = None
    opaque_intersection_arithmetic: Literal["exact_supplied_binary64_states"] | None = (
        None
    )
    deflection_limiter: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    aberration: Literal["ERFA_ab"] | None = None
    light_speed_au_day: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    inside_solar_disk: Literal["nonobservable_mathematical_extension"] | None = None


class OpaqueSolarLightTimeSolution(PartialOutput):
    method_id: Literal["exact_source_light_cone_adjacent_tt_v1"] | None = None
    selected_endpoint: Literal["first_nonnegative_F"] | None = None
    lower_jd_tt: float | None = Field(default=None, allow_inf_nan=False)
    upper_jd_tt: float | None = Field(default=None, allow_inf_nan=False)
    lower_residual_seconds: float | None = Field(
        default=None, le=0, allow_inf_nan=False
    )
    upper_residual_seconds: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    bracket_width_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    exact_root: bool | None = None
    lower_target_barycentric_icrs_au_au_day: list[float] | None = Field(
        default=None, min_length=6, max_length=6
    )


class OpaqueSolarPosition(PartialOutput):
    body: Literal[
        "Sun",
        "Moon",
        "Mercury",
        "Venus",
        "Mars",
        "Jupiter",
        "Saturn",
        "Uranus",
        "Neptune",
        "Pluto",
    ]
    longitude: float = Field(ge=0, lt=360, allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    distance_au: float = Field(gt=0, allow_inf_nan=False)
    apparent_icrs_unit_direction: list[float] = Field(min_length=3, max_length=3)
    solar_disc_intercepted: bool
    solar_deflection_applied: bool
    emission_jd_tt: float = Field(allow_inf_nan=False)
    solar_passage_jd_tt: float = Field(allow_inf_nan=False)
    light_time_iterations: int = Field(ge=1, le=20)
    light_time_solution: OpaqueSolarLightTimeSolution
    target_barycentric_icrs_au_au_day: list[float] = Field(min_length=6, max_length=6)
    solar_barycentric_icrs_au_au_day: list[float] = Field(min_length=6, max_length=6)
    input_state_return_flags: list[int] = Field(min_length=2, max_length=2)


class OpaqueSolarPositions(PartialOutput):
    status: Literal["computed"] | None = None
    method_id: Literal["finite_source_opaque_solar_apparent_positions_v1"] | None = None
    apparent_model: Literal["opaque_solar"] | None = None
    scope: Literal["standalone_positions_only"] | None = None
    frame: Literal["IAU2006/2000A_true_ecliptic_of_date"] | None = None
    jd_tt: float | None = Field(default=None, allow_inf_nan=False)
    positions: list[OpaqueSolarPosition] | None = Field(
        default=None, min_length=10, max_length=10
    )
    earth_barycentric_icrs_au_au_day: list[float] | None = Field(
        default=None, min_length=6, max_length=6
    )
    sun_at_observation_barycentric_icrs_au_au_day: list[float] | None = Field(
        default=None, min_length=6, max_length=6
    )
    input_state_return_flags: list[int] | None = Field(
        default=None, min_length=2, max_length=2
    )
    physical_ephemeris_source: PhysicalEphemerisSource | None = None
    ephemeris_reference_points: EphemerisReferencePoints | None = None
    convention: OpaqueSolarConvention | None = None
    natal_chart_recomputed: Literal[False] | None = None
    speeds_and_derived_chart_assessed: Literal[False] | None = None
    physical_accuracy_certified: Literal[False] | None = None


class ChartProfile(PartialOutput):
    utc_definition: UTCDefinitionEvidence | None = None
    ephemeris_reference_points: EphemerisReferencePoints | None = None
    apparent_position_policy: ApparentPositionPolicy | None = None
    longitude_motion: LongitudeMotionPolicy | None = None
    ephemeris_model_scope: str | None = None
    nonphysical_factor_models: dict[str, str] | None = None
    physical_ephemeris_source: PhysicalEphemerisSource | None = None
    fixed_stars: FixedStarProfile | None = None
    house_axis_convention: HouseAxisConvention | None = None
    earth_rotation: EarthRotationPolicy | None = None
    planetary_models: dict[str, str] | None = None
    orbital_fallback: OrbitalFallback | None = None
    sidereal_planetary_methods: dict[str, str] | None = None
    angle_definition: GeographicPoleAngleDefinition | None = None
    house_overlay_policy: str | None = None
    derivation_policy: RelationshipDerivation | None = None
    aspect_policy: ChartAspectPolicy | None = None
    aspects_total_count: int | None = None
    aspects_returned_count: int | None = None
    house_position_projection: HousePositionProjection | None = None
    coordinate_precision: str | None = None
    midpoint_coordinate_source: str | None = None
    midpoint_antipodal_policy: str | None = None
    calendar: str | None = None
    time_scale: str | None = None
    julian_day_tt: float | None = None
    julian_day_ut1: float | None = None
    future_leap_seconds_assumed_unchanged: bool | None = None
    horizon_method: str | None = None
    angle_method: str | None = None
    sect_convention: str | None = None
    ayanamsha: float | None = None
    ayanamsha_mean: float | None = None
    ayanamsha_includes_nutation: bool | None = None
    sidereal_position_method: str | None = None
    sidereal_house_method: str | None = None
    chart_type: Annotated[str | None, FULL_FACT] = None
    engine_backend: Annotated[str | None, FULL_FACT] = None
    engine_precision: str | None = None
    ephemeris_model: str | None = None
    house_system: str | None = None
    house_system_code: int | None = None
    house_system_label_zh: str | None = None
    house_system_source: str | None = None
    tradition: bool | None = None
    zodiac: str | None = None
    zodiac_label_zh: str | None = None
    zodiacal: int | None = None
    analysis_focus: str | None = None


class ClassicalLot(PartialOutput):
    almuten: str | None = None
    cn: str | None = None
    degree_in_sign: float | None = None
    dispositor: str | None = None
    longitude: float | None = None
    sign: str | None = None


class EssentialDignities(PartialOutput):
    bound_lord: str | None = None
    debilities: list[str] | None = None
    dignities: list[str] | None = None
    face_lord: str | None = None
    labels_zh: list[str] | None = None
    peregrine: bool | None = None
    score: int | None = None
    known_score: int | None = None
    unknown_dignities: list[str] | None = None
    triplicity_ruler: str | None = None


class Melothesia(PartialOutput):
    body_parts: list[str] | None = None
    position: str | None = None


class OrientalityPolicy(PartialOutput):
    model: Literal["ecliptic_longitude_phase"] | None = None
    arithmetic: Literal["exact_supplied_finite_angles"] | None = None
    conjunction: Literal["unknown_at_exact_coincidence"] | None = None
    opposition: Literal["oriental_legacy_half_open_tie"] | None = None
    nonzero_deadband: Literal["none"] | None = None
    physical_rise_set_verified: Literal[False] | None = None
    heliacal_visibility_verified: Literal[False] | None = None
    author_transition_endpoints_certified: Literal[False] | None = None


class ClassicalPlanet(PartialOutput):
    above_horizon: bool | None = None
    angularity: str | None = None
    combustion: str | None = None
    dodekatemorion: str | None = None
    essential: EssentialDignities | None = None
    in_halb: bool | None = None
    joy: bool | None = None
    melothesia: Melothesia | None = None
    ninth_part: str | None = None
    orientality: str | None = None
    out_of_bounds: bool | None = None
    retrograde: bool | None = None
    sect_placement: str | None = None


class PtolemyTerm(PartialOutput):
    lord: str | None = None
    start_degree: int | None = Field(default=None, ge=0, lt=30)
    end_degree: int | None = Field(default=None, gt=0, le=30)
    chapter_ref: str | None = None


class PtolemyPlanet(PartialOutput):
    longitude: float | None = Field(default=None, ge=0, lt=360)
    sign: str | None = None
    degree_in_sign: float | None = Field(default=None, ge=0, lt=30)
    domicile_lord: str | None = None
    in_domicile: bool | None = None
    in_exaltation: bool | None = None
    in_depression: bool | None = None
    triplicity_primary: str | None = None
    triplicity_co_ruler: str | None = None
    natural_sect: str | None = None
    terms: dict[str, PtolemyTerm] | None = None


class PtolemyFortune(PartialOutput):
    formula: str | None = None
    longitude: float | None = Field(default=None, ge=0, lt=360)
    sign: str | None = None
    degree_in_sign: float | None = Field(default=None, ge=0, lt=30)
    source_url: str | None = None


class PtolemySignRelationship(PartialOutput):
    planet_a: str | None = None
    planet_b: str | None = None
    sign_a: str | None = None
    sign_b: str | None = None
    separation_signs: int | None = None
    same_sign: bool | None = None
    sign_aspect: str | None = None
    aspect_quality: str | None = None
    commanding_sign: str | None = None
    obeying_sign: str | None = None
    beholding_equal_power: bool | None = None
    disjunct: bool | None = None
    chapter_refs: list[str] | None = None


class PtolemyLayer(PartialOutput):
    orientality_policy: OrientalityPolicy | None = None
    term_policy: str | None = None
    term_source_url: str | None = None
    term_transcription_note: str | None = None
    sign_relationships: list[PtolemySignRelationship] | None = None
    sign_relationship_policy: str | None = None
    lot_of_fortune: PtolemyFortune | None = None
    ruleset_id: str | None = None
    author: str | None = None
    edition: str | None = None
    source_url: str | None = None
    chapters: dict[str, str] | None = None
    status: str | None = None
    scope: str | None = None
    planets: dict[str, PtolemyPlanet] | None = None


class AlmutenPoint(PartialOutput):
    degree_in_sign: float | None = None
    sign: str | None = None
    totals: dict[str, int] | None = None
    winner: str | None = None


AlmutenPointId = Literal["Sun", "Moon", "Ascendant", "fortune", "syzygy"]


class AlmutenMethodSource(PartialOutput):
    title: str | None = None
    author: str | None = None
    edition: str | None = None
    url: str | None = None
    section: str | None = None
    scope: str | None = None


class AlmutenFigurisMethod(PartialOutput):
    method_id: str | None = None
    source_profile: str | None = None
    scope: str | None = None
    dignity_weights: (
        dict[Literal["domicile", "exaltation", "triplicity", "term", "face"], int]
        | None
    ) = None
    triplicity_policy: str | None = None
    is_day: bool | None = None
    bounds_policy: str | None = None
    face_policy: str | None = None
    tie_break_policy: str | None = None
    tie_break_order: list[str] | None = None
    expected_points: list[AlmutenPointId] | None = None
    included_points: list[AlmutenPointId] | None = None
    missing_points: list[AlmutenPointId] | None = None
    historical_method_status: Literal["selected_mixed_subset"] | None = None
    source_refs: list[AlmutenMethodSource] | None = None


class AlmutenFiguris(PartialOutput):
    status: Literal["partial"] | None = None
    unknown_points: list[AlmutenPointId] | None = None
    known_totals: dict[str, int] | None = None
    method: AlmutenFigurisMethod | None = None
    points: dict[str, AlmutenPoint] | None = None
    totals: dict[str, int] | None = None
    winner: str | None = None


class DispositorChain(PartialOutput):
    chain: list[str] | None = None
    terminal: str | None = None
    terminal_type: str | None = None


class Dispositors(PartialOutput):
    chains: dict[str, DispositorChain] | None = None
    final_dispositors: list[str] | None = None
    mutual_receptions: list[list[str]] | None = None


class SyzygySolver(PartialOutput):
    method: str | None = None
    target_elongation: float | None = None
    residual_degrees: float | None = Field(default=None, ge=0, lt=1e-6)
    strictly_before_birth: bool | None = None


class SyzygySampleSource(PartialOutput):
    body: str | None = None
    stage: str | None = None
    model: str | None = None
    status: str | None = None
    file_ids: list[str] | None = None
    sample_count: int | None = Field(default=None, ge=1)
    minimum_jd_tt: float | None = None
    maximum_jd_tt: float | None = None


class SyzygyEphemerisSource(PartialOutput):
    method_id: str | None = None
    models_by_body: dict[str, list[str]] | None = None
    models_stable: bool | None = None
    sample_contexts: list[SyzygySampleSource] | None = None
    physical_ephemeris_source: PhysicalEphemerisSource | None = None
    absolute_accuracy_certified: bool | None = None
    scope: str | None = None
    note_zh: str | None = None


class Syzygy(PartialOutput):
    degree_in_sign: float | None = Field(default=None, ge=0, lt=30)
    julian_day: float | None = None
    julian_day_ut1: float | None = None
    julian_day_tt: float | None = None
    event_datetime_utc: str | None = None
    utc_representation: WesternUTCRepresentation | None = None
    longitude: float | None = Field(default=None, ge=0, lt=360)
    tropical_longitude: float | None = Field(default=None, ge=0, lt=360)
    sign: str | None = None
    type: str | None = None
    zodiac: str | None = None
    solver: SyzygySolver | None = None
    ephemeris_source: SyzygyEphemerisSource | None = None


class Temperament(PartialOutput):
    status: Literal["partial"] | None = None
    unknown_components: list[Literal["ascendant_sign", "ascendant_ruler"]] | None = None
    known_tally: dict[str, int] | None = None
    cn: str | None = None
    humor: str | None = None
    hygral: str | None = None
    tally: dict[str, int] | None = None
    thermal: str | None = None


class TopicAlmuten(PartialOutput):
    sign: str | None = None
    winner: str | None = None


class SolarConditionPolicy(PartialOutput):
    rule_id: str | None = None
    source_edition: str | None = None
    source_url: str | None = None
    printed_page: int | None = None
    cazimi_limit_exact_degrees: str | None = None
    combust_limit_degrees: float | None = None
    under_beams_limit_degrees: float | None = None
    combust_requires_same_sign: bool | None = None
    interval_policy: str | None = None
    zodiac_policy: str | None = None
    printed_example_discrepancy: str | None = None
    full_page_acceptance: bool | None = None


class Classical(PartialOutput):
    orientality_policy: OrientalityPolicy | None = None
    solar_condition_policy: SolarConditionPolicy | None = None
    obliquity: float | None = None
    source_profile: str | None = None
    ptolemy: PtolemyLayer | None = None
    almuten_figuris: AlmutenFiguris | None = None
    dispositors: Dispositors | None = None
    lots: dict[str, ClassicalLot] | None = None
    planets: dict[str, ClassicalPlanet] | None = None
    sect: str | None = None
    syzygy: Syzygy | None = None
    temperament: Temperament | None = None
    topic_almutens: dict[str, TopicAlmuten] | None = None


class Bonification(PartialOutput):
    bonified_by: list[str] | None = None
    maltreated_by: list[str] | None = None


class Overcoming(PartialOutput):
    overcome: str | None = None
    overcomer: str | None = None


class Translation(PartialOutput):
    from_: str | None = Field(default=None, alias="from")
    translator: str | None = None
    to: str | None = None


class Collection(PartialOutput):
    from_: list[str] | None = Field(default=None, alias="from")
    collector: str | None = None


class NodalBending(PartialOutput):
    planet: str | None = None
    bending: str | None = None
    orb: float | None = None


class PtolemyLatitudeCondition(PartialOutput):
    status: str | None = None
    latitude_a: float | None = None
    latitude_b: float | None = None
    source_url: str | None = None
    policy: str | None = None


class AspectMotion(PartialOutput):
    ptolemy_latitude_condition: PtolemyLatitudeCondition | None = None
    planet_a: str | None = None
    planet_b: str | None = None
    aspect: str | None = None
    exact_angle: float | None = None
    separation: float | None = None
    orb: float | None = None
    relative_longitude_speed: float | None = None
    phase: (
        Literal["applying", "separating", "exact", "stationary", "unavailable"] | None
    ) = None


class AspectApplicationPolicy(PartialOutput):
    rule_id: str | None = None
    method: str | None = None
    speed_unit: str | None = None
    scope: str | None = None
    source_url: str | None = None


class LightConfigurationPolicy(PartialOutput):
    rule_id: str | None = None
    source_edition: str | None = None
    source_url: str | None = None
    translation_definition_page: int | None = None
    collection_judgement_page: int | None = None
    weight_order: list[str] | None = None
    status: str | None = None
    full_original_text_acceptance: bool | None = None
    unverified_conditions: list[str] | None = None


class ClassicalPatterns(PartialOutput):
    light_configuration_policy: LightConfigurationPolicy | None = None
    aspect_motion: list[AspectMotion] | None = None
    application_policy: AspectApplicationPolicy | None = None
    aversions: list[list[str]] | None = None
    besiegement: dict[str, str] | None = None
    bonification: dict[str, Bonification] | None = None
    collection_of_light: list[Collection] | None = None
    nodal_bending: list[NodalBending] | None = None
    overcoming: list[Overcoming] | None = None
    sect_benefic: str | None = None
    sect_malefic: str | None = None
    translation_of_light: list[Translation] | None = None


class Hellenistic(PartialOutput):
    angular_planets: list[str] | None = None
    ascendant_ruler: str | None = None
    lot_of_fortune: ChartPoint | None = None
    sect: str | None = None


class GuolaoMansion(PartialOutput):
    id: str | None = None
    su28: str | None = None
    degree_lord: str | None = None
    right_ascension: float | None = None
    longitude: float | None = None
    coordinate: float | None = None
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
    retrograde: bool | None = None
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
    hua_yao: str | None = None
    role_vs_life_lord: str | None = None
    role_vs_degree_lord: str | None = None


class GuolaoLifePalace(PartialOutput):
    longitude: float | None = None
    degree_in_palace: float | None = None
    branch: str | None = None
    palace_lord: str | None = None
    mansion: GuolaoMansion | None = None
    degree_lord: str | None = None
    method: str | None = None
    life_degree_method: str | None = None
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


class GuolaoBodyPalace(PartialOutput):
    branch: str | None = None
    palace_lord: str | None = None
    longitude: float | None = None
    degree_in_palace: float | None = None
    mansion: GuolaoMansion | None = None
    degree_lord: str | None = None
    basis: str | None = None


class GuolaoPalace(PartialOutput):
    palace: str | None = None
    branch: str | None = None
    lord: str | None = None
    lord_sign_index: int | None = None
    lord_relations: dict[str, str] | None = None
    gods_in_palace: list[str] | None = None


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


class MoiraPattern(PartialOutput):
    basis: str | None = None
    classical_acceptance: bool | None = None
    detail: str | None = None
    dsl: str | None = None
    level: str | None = None
    name: str | None = None
    source: str | None = None
    rule_id: str | None = None
    evidence: GuolaoPatternEvidence | None = None


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


class GuolaoValidation(PartialOutput):
    classical_acceptance_passed: bool | None = None
    full_marks_established: bool | None = None
    limitations: list[str] | None = None


class GuolaoGodPositions(PartialOutput):
    native_year_comparison: dict[str, OpenJsonValue] | None = None
    year_stem: str | None = None
    year_branch: str | None = None
    month_branch: str | None = None
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
    dongwei_daxian: dict[str, OpenJsonValue] | None = None
    month_limit: GuolaoMonthLimit | None = None
    transit_bodies: list[GuolaoBody] | None = None
    mansion_boundaries: list[GuolaoBoundary] | None = None
    profile: GuolaoTargetProfile | None = None
    limitations: list[str] | None = None


class GuolaoResearch(PartialOutput):
    moira_rule_evaluation: GuolaoMoiraEvaluation | None = None
    moira_source_provider: GuolaoMoiraSourceProvider | None = None
    lunar_mansion_system: str | None = None
    mansion_frame: str | None = None
    weekday_ruler: str | None = None
    planetary_mansions: list[GuolaoMansion] | None = None
    moon_mansion: str | None = None
    si_yu_sign_index: dict[str, int] | None = None
    god_sign_index: dict[str, int] | None = None
    moira_patterns: list[MoiraPattern] | None = None
    bodies: list[GuolaoBody] | None = None
    life_palace: GuolaoLifePalace | None = None
    body_palace: GuolaoBodyPalace | None = None
    hua_yao: dict[str, OpenJsonValue] | None = None
    en_yong_nan_chou: dict[str, OpenJsonValue] | None = None
    dongwei_daxian: dict[str, OpenJsonValue] | None = None
    palaces: list[GuolaoPalace] | None = None
    conditions: GuolaoConditions | None = None
    profile: GuolaoProfile | None = None
    mansion_boundaries: list[GuolaoBoundary] | None = None
    validation: GuolaoValidation | None = None
    god_positions: GuolaoGodPositions | None = None
    purple_model_audit: GuolaoPurpleModelAudit | None = None
    timing: GuolaoTiming | None = None


class Guolao(GuolaoResearch):
    god_sign_index: dict[str, int] | None = None
    lunar_mansion_system: str | None = None
    moon_mansion: str | None = None
    planetary_mansions: list[GuolaoMansion] | None = None
    si_yu_sign_index: dict[str, int] | None = None
    weekday_ruler: str | None = None


class ThirteenSector(PartialOutput):
    cusp_longitude: float | None = None
    end_longitude: float | None = None
    width_degrees: float | None = None
    sector: int | None = None
    sign: str | None = None


class Midpoint(PartialOutput):
    opposite_longitude: float | None = None
    antipodal_inputs: bool | None = None
    computed_from_unrounded: bool | None = None
    degree_in_sign: float | None = None
    id_a: str | None = None
    id_b: str | None = None
    idA: str | None = None
    idB: str | None = None
    longitude: float | None = None
    sign: str | None = None
    sign_zh: str | None = None


class MidpointAspect(PartialOutput):
    aspect: str | None = None
    midpoint: str | None = None
    orb: float | None = None
    planet: str | None = None


class RelativeMidpointHit(PartialOutput):
    aspect: str | None = None
    delta: float | None = None
    midpoint: Midpoint | None = None


class RelativeContact(PartialOutput):
    aspect: str | None = None
    delta: float | None = None
    id: str | None = None


class DirectionalContacts(PartialOutput):
    id: str | None = None
    objects: list[RelativeContact] | None = None


class RelativeAntiscia(PartialOutput):
    idA: str | None = None
    idB: str | None = None
    delta: float | None = None


class SynastryAspect(PartialOutput):
    aspect: str | None = None
    inner: str | None = None
    orb: float | None = None
    outer: str | None = None


class BirthClockConversion(PartialOutput):
    ruleset_id: str | None = None
    author: str | None = None
    input_clock_basis: str | None = None
    input_wall_datetime: str | None = None
    longitude_east_degrees: float | None = None
    longitude_offset_seconds: float | None = None
    equation_of_time_seconds: float | None = None
    sun_apparent_right_ascension_degrees: float | None = None
    greenwich_apparent_sidereal_degrees: float | None = None
    solar_ephemeris_model: str | None = None
    solar_ephemeris_policy: str | None = None
    input_calendar: str | None = None
    solar_ephemeris_models_observed: list[str] | None = None
    solar_model_call_count: int | None = None
    solar_reference: str | None = None
    equatorial_frame: str | None = None
    sidereal_time_model: str | None = None
    earth_rotation_policy_id: str | None = None
    target_julian_day_ut1: float | None = None
    julian_day_ut1: float | None = None
    converted_utc: str | None = None
    time_scale_method: str | None = None
    future_leap_seconds_assumed_unchanged: bool | None = None
    ut1_roundtrip_error_seconds: float | None = None
    input_clock_roundtrip_error_seconds: float | None = None
    numerical_resolution_seconds: float | None = None
    measured_eop_applied: bool | None = None
    clock_accuracy_certified: bool | None = None
    swisseph_version: str | None = None
    source_url: str | None = None
    source_code_url: str | None = None
    source_sections: str | None = None


class WesternSolarTimeReference(PartialOutput):
    method_id: (
        Literal[
            "western_solar_rebase_ut1_v1", "western_solar_rebase_coherent_tt_ut1_v2"
        ]
        | None
    ) = None
    recorded_utc: str | None = None
    recorded_julian_day_tt: float | None = Field(default=None, allow_inf_nan=False)
    equation_of_time_julian_day_ut1: float | None = Field(
        default=None, allow_inf_nan=False
    )
    equation_of_time_seconds: float | None = Field(default=None, allow_inf_nan=False)
    sun_apparent_right_ascension_degrees: float | None = Field(
        default=None, allow_inf_nan=False
    )
    greenwich_apparent_sidereal_degrees: float | None = Field(
        default=None, allow_inf_nan=False
    )
    solar_ephemeris_model: str | None = None
    equatorial_frame: str | None = None
    solar_ephemeris_source: dict[str, OpenJsonValue] | None = None
    sidereal_time_model: str | None = None
    earth_rotation_policy_id: str | None = None
    rebase_arithmetic: Literal["frozen_recorded_utc_offset_v1"] | None = None
    recorded_local_datetime: str | None = None
    recorded_utc_offset_seconds: float | None = Field(default=None, allow_inf_nan=False)
    rebased_solar_clock_datetime: str | None = None
    rebased_utc: str | None = None
    rebase_utc_shift_seconds: float | None = Field(default=None, allow_inf_nan=False)
    time_scale_method: str | None = None
    future_leap_seconds_assumed_unchanged: bool | None = None
    scope: str | None = None


class ChartTrueSolar(PartialOutput):
    applied: bool | None = None
    correction_minutes: float | None = Field(default=None, allow_inf_nan=False)
    time_reference: WesternSolarTimeReference | None = None


class ChartPerson(PersonInfo):
    timezone_source: (
        Literal["birth_timezone", "birth_place", "solar_clock_conversion"] | None
    ) = None
    birth_latitude: float | None = None
    birth_longitude: float | None = None
    birth_place: str | None = None
    birth_timezone: str | None = None
    name: str | None = None
    birth_datetime: str | None = None
    utc_datetime: str | None = None
    clock_conversion: BirthClockConversion | None = None
    true_solar: ChartTrueSolar | None = None


class Chart(PartialOutput):
    aspect_evidence: list[ChartAspect] | None = None
    angles: dict[str, ChartAngle] | None = None
    aspects: list[ChartAspect] | None = None
    balance_basis: str | None = None
    chart_profile: ChartProfile | None = None
    element_balance: dict[str, float] | None = None
    houses: list[ChartHouse] | None = None
    modality_balance: dict[str, float] | None = None
    person_info: ChartPerson | None = None
    planets: list[ChartPlanet] | None = None
    summary: list[str] | None = None


class InnerOuter(PartialOutput):
    chart: Chart | None = None
    chart_profile: ChartProfile | None = None
    summary: list[str] | None = None


class RelationshipFocus(PartialOutput):
    emphasis_bodies: list[str] | None = None
    emphasis_houses: list[int] | None = None
    focus: str | None = None
    focus_label_zh: str | None = None
    focused_aspect_count: int | None = None
    focused_synastry_aspects: list[SynastryAspect] | None = None
    note: str | None = None


class RelationshipProfile(PartialOutput):
    relative_midpoint_policy: str | None = None
    derivation_policy: RelationshipDerivation | None = None
    davison_variant: str | None = None
    primary_chart_role: str | None = None
    chart_type: str | None = None
    engine_backend: str | None = None
    engine_precision: str | None = None
    focus: RelationshipFocus | None = None
    house_system: str | None = None
    house_system_label_zh: str | None = None
    hsys: int | None = None
    mode_status: str | None = None
    primary_layer: str | None = None
    relative_mode_input: str | int | None = None
    relative_mode_label_zh: str | None = None
    relative_mode_normalized: str | None = None
    relative_mode_resolution: str | None = None
    zodiac_label_zh: str | None = None
    zodiac_mode: str | None = None
    zodiacal: int | None = None


class LocalAngles(PartialOutput):
    ascendant: float | None = None
    midheaven: float | None = None


class LocalHouse(PartialOutput):
    id: str | None = None
    lon: float | None = None
    sign: str | None = None
    sign_zh: str | None = None


class LocalObject(PartialOutput):
    house: str | None = None
    ecliptic_house_position: float | None = None
    ecliptic_house_phase_degrees_ratio: str | None = Field(
        default=None,
        description="原生宫位模型的工作相位（有理数文本，现代度）；保留细微边界供反向分宫，不代表物理精度或唯一性获证",
    )
    id: str | None = None
    lon: float | None = None
    sign: str | None = None
    signlon: float | None = None


class LocalChart(PartialOutput):
    angles: LocalAngles | None = None
    houses: list[LocalHouse] | None = None
    objects: list[LocalObject] | None = None
    ok: bool | None = None


class LocalChartBundle(PartialOutput):
    chart: LocalChart | None = None
    params: Object | None = None


class ConditionEvidence(PartialOutput):
    condition: Literal["domicile", "exaltation", "detriment", "fall"] | None = None
    matched: bool | None = None
    basis_signs: list[str] | None = None
    ruleset_id: str | None = None
    source_url: str | None = None
    derivation: str | None = None
    status: str | None = None


class SignCondition(PartialOutput):
    status: str | None = None
    conditions: list[str] | None = None
    condition_evidence: list[ConditionEvidence] | None = None
    domicile_ruler: str | None = None
    dispositor_status: str | None = None
    unassessed: list[str] | None = None
    note: str | None = None


class SymbolicHouse(PartialOutput):
    house_number: int | None = None
    sign: str | None = None
    domicile_ruler: str | None = None


class HouseCondition(PartialOutput):
    status: str | None = None
    joy_house_number: int | None = None
    in_joy: bool | None = None
    ruleset_id: str | None = None
    scope: str | None = None


class TriplicityRulers(PartialOutput):
    primary: str | None = None
    co_ruler: str | None = None


class TriplicityCondition(PartialOutput):
    status: str | None = None
    ruleset_id: str | None = None
    sect: str | None = None
    assigned_rulers: list[str] | None = Field(
        default=None,
        description="Robbins I.18 overall triangle assignment; distinct from governance under a named day/night condition.",
    )
    in_assigned_group: bool | None = Field(
        default=None,
        description="Membership in the overall assignment. Null means the rolled body is outside the seven-planet reference scope.",
    )
    roles_by_sect: (
        dict[
            str,
            Literal[
                "primary",
                "co_ruler",
                "assigned_not_selected",
                "not_assigned",
                "outside_seven_planet_scope",
            ],
        ]
        | None
    ) = Field(
        default=None,
        description="Separate day/night conditional roles; assigned_not_selected preserves overall membership without selecting the named primary/co-ruler role.",
    )
    rulers_by_sect: dict[str, TriplicityRulers] | None = None
    matches_by_sect: dict[str, bool | None] | None = Field(
        default=None,
        description="Match to the returned primary or explicit co-ruler under each named condition. False does not negate overall triangle assignment or all dignity; null means outside seven-planet scope.",
    )
    match_definition: str | None = None
    scope: str | None = None


class PlanetSectAssignments(PartialOutput):
    morning_star: Literal["day", "night"] | None = None
    evening_star: Literal["day", "night"] | None = None


class PlanetSectCondition(PartialOutput):
    status: (
        Literal[
            "natural_assignment_without_chart_sect",
            "conditional_on_solar_phase_not_in_roll",
            "outside_seven_planet_scope",
        ]
        | None
    ) = None
    ruleset_id: str | None = None
    natural_sect: Literal["day", "night"] | None = Field(
        default=None,
        description="Robbins I.7 natural assignment. Mercury is unresolved without its solar phase; outer planets and nodes are outside this seven-planet rule.",
    )
    assignments_by_solar_phase: PlanetSectAssignments | None = None
    solar_phase: None = Field(
        default=None, description="Not encoded by the rolled faces."
    )
    applied_chart_sect: None = Field(
        default=None,
        description="No actual day/night chart sect is inferred from dice or transferred from optional sky.",
    )
    matches_chart_sect: None = Field(
        default=None,
        description="Unassessed because a natural planet assignment alone cannot establish agreement with chart sect.",
    )
    scope: str | None = None


class DiceDetails(PartialOutput):
    house_number: int | None = None
    planet_kind: str | None = None
    element: str | None = None
    modality: str | None = None
    house_group: str | None = None
    sign_condition: SignCondition | None = None
    house_condition: HouseCondition | None = None
    triplicity_condition: TriplicityCondition | None = None
    planet_sect_condition: PlanetSectCondition | None = None
    symbolic_house_ring: list[SymbolicHouse] | None = None
    houses_ruled_by_rolled_planet: list[int] | None = None


class DiceValidation(PartialOutput):
    calendar: str | None = None
    classical: str | None = None


class FortuneDefinition(PartialOutput):
    method: Literal["sect_reversing", "ptolemy_iii10"] | None = None
    formula: str | None = None
    sect_applied: Literal["day", "night"] | None = None
    author: str | None = None
    edition: str | None = None
    source_url: str | None = None
    source_path: str | None = None
    source_kind: Literal["primary_text_translation", "runtime_convention"] | None = None
    scope: str | None = None


class DiceMotionPolicy(PartialOutput):
    policy_id: str | None = None
    status: Literal["computed", "partial"] | None = None
    uncomputed_points: list[str] | None = None
    reference_frame: str | None = None
    unit: Literal["degree_per_day"] | None = None
    sign_policy: str | None = None
    source_url: str | None = None
    source_sections: str | None = None
    scope: str | None = None


class DiceSkyParams(PartialOutput):
    chart_profile: ChartProfile | None = None
    birthLatitude: float | None = None
    birthLongitude: float | None = None
    coordinatePolicy: str | None = None
    housePositionMethod: str | None = None
    housePositionProjection: HousePositionProjection | None = None
    lunarNodeModel: str | None = None
    fortuneDefinition: FortuneDefinition | None = None
    ephemerisReferencePoints: EphemerisReferencePoints | None = None
    motionPolicy: DiceMotionPolicy | None = None


class DiceLongitudeMotion(PartialOutput):
    longitude_speed: float | None = None
    native_longitude_speed: float | None = None
    model_longitude_speed: float | None = None
    sidereal_origin_correction: float | None = None
    source_url: str | None = None
    light_time_correction: float | None = None
    spatial_aberration_correction: float | None = None
    lunar_source_remainder_correction: float | None = None
    sidereal_origin_wrap_correction: float | None = None
    rotation_correction: float | None = None
    position_derivative_correction: float | None = None
    method_id: str | None = None
    correction_status: (
        Literal["applied", "partial", "native_only", "approximate_model"] | None
    ) = None
    unit: Literal["degree_per_day"] | None = None
    direction: (
        Literal["direct", "retrograde", "zero_instantaneous_rate", "not_computed"]
        | None
    ) = None
    reference_frame: str | None = None
    basis: str | None = None
    source_model: str | None = None


class DiceSkyObject(LocalObject):
    motion: DiceLongitudeMotion | None = None


class DiceSkyGeometry(PartialOutput):
    angles: LocalAngles | None = None
    houses: list[LocalHouse] | None = None
    objects: list[DiceSkyObject] | None = None
    ok: bool | None = None


class DiceSkyChart(PartialOutput):
    chart: DiceSkyGeometry | None = None
    params: DiceSkyParams | None = None


class AstrologyChartOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    angles: dict[str, ChartAngle] | None = None
    apparent_model_positions: OpaqueSolarPositions | None = None
    aspect_evidence: list[ChartAspect] | None = None
    aspects: list[ChartAspect] | None = None
    balance_basis: str | None = None
    chart_profile: ChartProfile | None = None
    classical: Classical | None = None
    classical_patterns: ClassicalPatterns | None = None
    element_balance: dict[str, float] | None = None
    fixed_stars: list[FixedStar] | None = None
    houses: list[ChartHouse] | None = None
    modality_balance: dict[str, float] | None = None
    person_info: ChartPerson | None = None
    planetary_hours: PlanetaryHours | None = None
    planets: PlanetsField = None
    summary: Object | list[JsonValue] | str | None = None


class ThirteenSectorChartOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    angles: dict[str, ChartAngle] | None = None
    aspect_evidence: list[ChartAspect] | None = None
    aspects: list[ChartAspect] | None = None
    balance_basis: str | None = None
    chart_profile: ChartProfile | None = None
    classical: Classical | None = None
    classical_patterns: ClassicalPatterns | None = None
    element_balance: dict[str, float] | None = None
    fixed_stars: list[FixedStar] | None = None
    houses: list[ChartHouse] | None = None
    modality_balance: dict[str, float] | None = None
    person_info: ChartPerson | None = None
    planetary_hours: PlanetaryHours | None = None
    planets: PlanetsField = None
    summary: Object | list[JsonValue] | str | None = None
    thirteen_sectors: list[ThirteenSector] | None = None
    sector_profile: SectorProfile | None = None
    birth_time_sensitivity: SpecialtyTimeSensitivity | None = None


class HellenisticChartOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    angles: dict[str, ChartAngle] | None = None
    aspect_evidence: list[ChartAspect] | None = None
    aspects: list[ChartAspect] | None = None
    balance_basis: str | None = None
    chart_profile: ChartProfile | None = None
    classical: Classical | None = None
    classical_patterns: ClassicalPatterns | None = None
    element_balance: dict[str, float] | None = None
    fixed_stars: list[FixedStar] | None = None
    hellenistic: Hellenistic | None = None
    houses: list[ChartHouse] | None = None
    modality_balance: dict[str, float] | None = None
    person_info: ChartPerson | None = None
    planetary_hours: PlanetaryHours | None = None
    planets: PlanetsField = None
    summary: Object | list[JsonValue] | str | None = None


class GuolaoChartOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    angles: dict[str, ChartAngle] | None = None
    chart_profile: ChartProfile | None = None
    guolao: Guolao | None = None
    houses: list[ChartHouse] | None = None
    person_info: ChartPerson | None = None
    planets: PlanetsField = None
    summary: Object | list[JsonValue] | str | None = None


class VedicChartOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    person_info: ChartPerson | None = None
    summary: Object | list[JsonValue] | str | None = None
    vedic_chart: India | None = None


class VimshottariDashaOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    ashtottari: Object | None = None
    chara: Object | None = None
    person_info: ChartPerson | None = None
    summary: Object | list[JsonValue] | str | None = None
    vimshottari: Vimshottari | None = None
    yogini: Object | None = None


class HamburgMidpointChartOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    base_chart: Chart | None = None
    chart_profile: ChartProfile | None = None
    planets: PlanetsField = None
    midpoint_aspects: list[MidpointAspect] | None = None
    midpoints: list[Midpoint] | None = None
    midpoint_analysis: MidpointAnalysis | None = None
    summary: Object | list[JsonValue] | str | None = None


class RelationshipChartOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    chart: Chart | None = None
    composite_to_inner_aspects: list[JsonValue] | None = None
    composite_to_outer_aspects: list[JsonValue] | None = None
    in_to_out_antiscia: list[RelativeAntiscia] | None = None
    in_to_out_aspects: list[DirectionalContacts] | None = None
    in_to_out_contra_antiscia: list[RelativeAntiscia] | None = None
    in_to_out_midpoint: dict[str, list[RelativeMidpointHit]] | None = None
    inner: InnerOuter | None = None
    inner_chart: Chart | None = None
    marks_charts: dict[str, Chart] | None = None
    out_to_in_antiscia: list[RelativeAntiscia] | None = None
    out_to_in_aspects: list[DirectionalContacts] | None = None
    out_to_in_contra_antiscia: list[RelativeAntiscia] | None = None
    out_to_in_midpoint: dict[str, list[RelativeMidpointHit]] | None = None
    outer: InnerOuter | None = None
    outer_chart: Chart | None = None
    relationship_profile: RelationshipProfile | None = None
    summary: Object | list[JsonValue] | str | None = None
    synastry_aspects: list[SynastryAspect] | None = None


class InterpretAstrologyDiceOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    chart: DiceSkyChart | None = None
    dice_chart: LocalChartBundle | None = None
    house: int | None = None
    method_id: str | None = None
    planet: str | None = None
    question: JsonValue | str | None = None
    sign: str | None = None
    summary: Object | list[JsonValue] | str | None = None
    symbolic_details: DiceDetails | None = None
    validation: DiceValidation | None = None
