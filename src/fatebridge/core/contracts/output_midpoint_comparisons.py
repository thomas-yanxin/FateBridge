"""Midpoint solar arcs and comparative geometry."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_midpoint_directions import (
    DirectedFactor,
    DirectionDial,
    SolarArcProfile,
)
from fatebridge.core.contracts.output_midpoint_geometry import (
    FactorSpan,
    GeometrySource,
    MeridianFactorPosition,
    SourceInterpretation,
)
from fatebridge.core.contracts.output_midpoint_meridian import DayMeridianAnalysis
from fatebridge.core.contracts.output_midpoint_sensitivity import (
    RecordedPhysicalGrid,
    SpecialtyTimeSensitivity,
)
from fatebridge.core.contracts.output_midpoint_source_tables import (
    MixedPairGeometry,
    Witte1925SourceTable,
)


class SolarArcAnalysis(PartialOutput):
    status: str | None = None
    reason: str | None = None
    ruleset_id: str | None = None
    version: str | None = None
    author: str | None = None
    profile: SolarArcProfile | None = None
    directed_factors: list[DirectedFactor] | None = None
    dials: dict[str, DirectionDial] | None = None
    mixed_pair_geometry: MixedPairGeometry | None = None
    contact_counts: dict[str, dict[str, int]] | None = None
    interpretations: list[SourceInterpretation] | None = None
    birth_time_sensitivity: SpecialtyTimeSensitivity | None = None
    daily_meridian: DayMeridianAnalysis | None = None
    original_table_1925: Witte1925SourceTable | None = None
    sources: list[GeometrySource] | None = None
    limitations: list[str] | None = None
    original_text_conformance: str | None = None


class MeridianHouseCusp(PartialOutput):
    house: int | None = None
    longitude: float | None = None
    tropical_longitude: float | None = None
    right_ascension: float | None = None


class MeridianHouseProfile(PartialOutput):
    house_code: str | None = None
    swisseph_version: str | None = None
    house_flags: int | None = None
    obliquity_return_flags: int | None = None
    obliquity_model: str | None = None
    geographic_latitude: float | None = None
    geographic_longitude: float | None = None
    construction: str | None = None
    zodiac: str | None = None
    right_ascension_frame: str | None = None
    julian_day_ut1: float | None = None
    shared_julian_day_tt: float | None = None
    native_angle_julian_day_tt: float | None = None
    native_angle_minus_shared_tt_seconds: float | None = None
    angle_time_policy: str | None = None
    armc: float | None = None
    true_obliquity: float | None = None
    source_ecliptic_longitude_origin: float | None = None
    ayanamsha_apparent: float | None = None
    first_cusp_definition: str | None = None
    tenth_cusp_definition: str | None = None
    physical_ascendant: float | None = None
    retained_ascendant_definition_reference: str | None = None
    physical_midheaven: float | None = None
    first_cusp_replaces_physical_ascendant: bool | None = None
    base_chart_houses_replaced: bool | None = None
    geographic_pole_meridian_convention: bool | None = None


class MeridianCuspSpan(FactorSpan):
    house: int | None = None


class MeridianFactorStability(PartialOutput):
    id: str | None = None
    nominal_house: int | None = None
    sampled_houses: list[int] | None = None
    unresolved_sample_count: int | None = None
    sampled_status: str | None = None


class MeridianHouseSensitivity(PartialOutput):
    recorded_physical_grid: RecordedPhysicalGrid | None = None
    status: str | None = None
    uncertainty_minutes: float | None = None
    continuous_interval_proven: bool | None = None
    sample_reference: str | None = None
    sample_count: int | None = None
    maximum_recorded_sample_gap_seconds: float | None = None
    cusp_spans: list[MeridianCuspSpan] | None = None
    factor_placement_summary: list[MeridianFactorStability] | None = None


class MeridianFactorPlacement(PartialOutput):
    status: str | None = None
    ruleset_id: str | None = None
    author: str | None = None
    version: str | None = None
    factor_count: int | None = None
    physical_factor_count: int | None = None
    hypothetical_factor_count: int | None = None
    node_factor_count: int | None = None
    factors: list[MeridianFactorPosition] | None = None
    factor_ayanamsha_apparent: float | None = None
    factor_julian_day_tt: float | None = None
    projection_obliquity_julian_day_tt: float | None = None
    coordinate_policy: str | None = None
    sector_policy: str | None = None
    pole_horizontal_norm_threshold: float | None = None
    reference_points_included: bool | None = None
    source_example_reconciliation: str | None = None
    scope: str | None = None
    sources: list[GeometrySource] | None = None
    full_original_method_accepted: bool | None = None


class MeridianHouseAnalysis(PartialOutput):
    status: str | None = None
    reason: str | None = None
    ruleset_id: str | None = None
    author: str | None = None
    version: str | None = None
    profile: MeridianHouseProfile | None = None
    cusps: list[MeridianHouseCusp] | None = None
    factor_placement: MeridianFactorPlacement | None = None
    birth_time_sensitivity: MeridianHouseSensitivity | None = None
    sources: list[GeometrySource] | None = None
    limitations: list[str] | None = None
    original_text_conformance: str | None = None


class ComparativePointSystem(PartialOutput):
    longitudes: dict[str, float | None] | None = None
    backend_longitudes: dict[str, float] | None = None
    input_reference_geometry_resolved: bool | None = None
    reference_angle_basis: dict[str, str] | None = None
    defined_anchor_identity: bool | None = None
    unique_point_count: int | None = None
    backend_unique_point_count: int | None = None


class ComparativeFrameSummary(PartialOutput):
    anchor_factor: str | None = None
    target_tropical_longitude: float | None = None
    target_display_longitude: float | None = None
    rotation_degrees: float | None = None
    backend_rotation_degrees: float | None = None
    anchor_input_reference_resolved: bool | None = None
    anchor_reference_angle_basis: dict[str, str] | None = None
    resolved_factor_system_count: int | None = None
    unresolved_factor_system_count: int | None = None


class ComparativeFrame(ComparativeFrameSummary):
    factor_systems: dict[str, ComparativePointSystem] | None = None


class ComparativeProfile(PartialOutput):
    native_factor_count: int | None = None
    constructed_frame_count: int | None = None
    native_aries_point_longitude: float | None = None
    display_zodiac: str | None = None
    cardinal_policy: str | None = None
    rotated_aries_factor_policy: str | None = None
    rotation_formula: str | None = None
    four_point_formula: str | None = None
    source_natal_table_factor_count: int | None = None
    native_factor_reference: str | None = None
    exact_coordinate_policy: str | None = None
    node_anchor_policy: str | None = None
    meridian_anchor_policy: str | None = None
    coordinates_are_new_observations: bool | None = None


class ComparativeSample(PartialOutput):
    sample_index: int | None = None
    offset_seconds: float | None = None
    recorded_utc: str | None = None
    effective_utc: str | None = None
    julian_day_tt: float | None = None
    factor_longitudes: dict[str, float] | None = None
    angle_definition: dict[str, OpenJsonValue] | None = None
    frame_summary: dict[str, ComparativeFrameSummary] | None = None
    point_systems: dict[str, dict[str, ComparativePointSystem]] | None = None
    native_sample_reference: str | None = None


class ComparativeOffsetSpan(PartialOutput):
    minimum: float | None = None
    maximum: float | None = None


class ComparativePointSpan(PartialOutput):
    nominal_input_reference_geometry_resolved: bool | None = None
    resolved_sample_count: int | None = None
    unresolved_sample_count: int | None = None
    unresolved_sample_indices: list[int] | None = None
    known_sampled_signed_offsets_from_nominal: (
        dict[str, ComparativeOffsetSpan] | None
    ) = None
    backend_sampled_signed_offsets_from_nominal: (
        dict[str, ComparativeOffsetSpan] | None
    ) = None


class ComparativeSensitivitySummary(PartialOutput):
    samples_with_unresolved_reference: int | None = None
    point_systems_per_sample: int | None = None
    all_confirmed_samples_retained: bool | None = None


class ComparativeSensitivity(PartialOutput):
    status: str | None = None
    uncertainty_minutes: float | None = None
    sample_count: int | None = None
    nominal_sample_index: int | None = None
    continuous_interval_proven: bool | None = None
    summary: ComparativeSensitivitySummary | None = None
    point_spans: dict[str, dict[str, ComparativePointSpan]] | None = None
    samples: list[ComparativeSample] | None = None
    interval: dict[str, OpenJsonValue] | None = None
    scope: str | None = None


class ComparativeGeometry(PartialOutput):
    status: str | None = None
    reason: str | None = None
    ruleset_id: str | None = None
    author: str | None = None
    version: str | None = None
    profile: ComparativeProfile | None = None
    radix_systems: dict[str, ComparativePointSystem] | None = None
    frames: dict[str, ComparativeFrame] | None = None
    frame_summary: dict[str, ComparativeFrameSummary] | None = None
    birth_time_sensitivity: ComparativeSensitivity | None = None
    sources: list[GeometrySource] | None = None
    original_text_conformance: str | None = None
    limitations: list[str] | None = None
