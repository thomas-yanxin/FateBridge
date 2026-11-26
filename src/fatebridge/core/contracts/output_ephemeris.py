"""Projected contracts for native file-context provenance."""

from pydantic import JsonValue

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_midpoint_geometry import PhysicalFactorSource


class SolarEphemerisReference(PartialOutput):
    author: str | None = None
    source_version: str | None = None
    source_url: str | None = None
    calculation_library: str | None = None
    time_argument: str | None = None
    coefficient_representation: str | None = None
    coefficient_profile: str | None = None


class CompressedFileWindow(PartialOutput):
    slot: int | None = None
    filename: str | None = None
    start_jd_tt: float | None = None
    end_jd_tt: float | None = None
    de_number: int | None = None


class CompressedEndpointRecord(PartialOutput):
    operation: str | None = None
    input_julian_day: float | None = None
    physical_jd_tt: float | None = None
    body_id: int | None = None
    returned_flags: int | None = None
    original_native_state: list[float] | None = None
    selected_native_state: list[float] | None = None
    native_state_changed: bool | None = None
    initial_windows: list[CompressedFileWindow] | None = None
    selected_windows: list[CompressedFileWindow] | None = None
    selection_anchor_jd_tt: list[float] | None = None
    physical_instant_shifted: bool | None = None


class CompressedEndpointPolicy(PartialOutput):
    policy_id: str | None = None
    trigger: str | None = None
    input_instant_shifted: bool | None = None
    native_coordinates_may_be_corrected: bool | None = None
    context_strategy: str | None = None
    native_cache_resets_so_far: int | None = None
    reference_preflight: str | None = None
    calls_corrected_so_far: int | None = None
    native_states_changed_so_far: int | None = None
    records: list[CompressedEndpointRecord] | None = None
    unrecorded_calls_at_record_limit: int | None = None
    source_url: str | None = None
    scope: str | None = None


class NativeCoordinateContext(CompressedEndpointRecord):
    policy_id: str | None = None
    original_target_state_status: str | None = None
    private_native_cache_reset: bool | None = None
    preflight_reference: str | None = None
    scope: str | None = None


class NativeExecutionContext(PartialOutput):
    mechanism: str | None = None
    lifetime: str | None = None
    auxiliary_candidates_checked: int | None = None
    auxiliary_files_present: list[dict[str, JsonValue]] | None = None
    scope: str | None = None
    compressed_file_endpoint_policy: CompressedEndpointPolicy | None = None


class SolarPositionBody(PartialOutput):
    status: str | None = None
    unbent_ray_domain: str | None = None
    reason: str | None = None
    coordinate_backends: dict[str, str] | None = None
    impact_solar_radius_fraction: float | None = None
    target_distance_au: float | None = None
    solar_distance_au: float | None = None
    solar_projection_distance_au: float | None = None
    arithmetic_margin_fraction: float | None = None
    position_interpretation: str | None = None
    observational_accuracy_certified: bool | None = None
    maximum_physical_error_arcseconds: float | None = None


class SolarModelRegularity(PartialOutput):
    profile: str | None = None
    axis_continuity_certified: bool | None = None
    unique_rate_at_mass_knots_certified: bool | None = None
    scope: str | None = None


class ApparentPositionPolicy(PartialOutput):
    method_id: str | None = None
    epoch_jd_tt: float | None = None
    native_version: str | None = None
    binding_version: str | None = None
    solar_deflection_model: str | None = None
    source_url: str | None = None
    source_section: str | None = None
    native_source_url: str | None = None
    native_model_solar_radius_au: float | None = None
    source_model_regularity: SolarModelRegularity | None = None
    coordinate_origin: str | None = None
    geometry_frame: str | None = None
    bodies: dict[str, SolarPositionBody] | None = None
    excluded_factors: dict[str, str] | None = None
    source_contexts: dict[str, PhysicalFactorSource] | None = None
    displayed_native_positions_changed: bool | None = None
    observational_accuracy_certified: bool | None = None
    scope: str | None = None
