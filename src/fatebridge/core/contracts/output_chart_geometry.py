"""Western chart points, angles and house geometry."""

from typing import Annotated, Literal

from pydantic import Field

from fatebridge.core.contracts.output_base import FULL_FACT, PartialOutput
from fatebridge.core.contracts.output_ephemeris import SolarEphemerisReference
from fatebridge.core.contracts.output_midpoints import SectorEvidence


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
