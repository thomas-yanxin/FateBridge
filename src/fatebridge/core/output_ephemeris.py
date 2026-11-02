"""Projected contracts for native file-context provenance."""

from typing import Dict, List, Optional

from pydantic import JsonValue

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_midpoints import PhysicalFactorSource


class CompressedFileWindow(PartialOutput):
    slot: Optional[int] = None
    filename: Optional[str] = None
    start_jd_tt: Optional[float] = None
    end_jd_tt: Optional[float] = None
    de_number: Optional[int] = None


class CompressedEndpointRecord(PartialOutput):
    operation: Optional[str] = None
    input_julian_day: Optional[float] = None
    physical_jd_tt: Optional[float] = None
    body_id: Optional[int] = None
    returned_flags: Optional[int] = None
    original_native_state: Optional[List[float]] = None
    selected_native_state: Optional[List[float]] = None
    native_state_changed: Optional[bool] = None
    initial_windows: Optional[List[CompressedFileWindow]] = None
    selected_windows: Optional[List[CompressedFileWindow]] = None
    selection_anchor_jd_tt: Optional[List[float]] = None
    physical_instant_shifted: Optional[bool] = None


class CompressedEndpointPolicy(PartialOutput):
    policy_id: Optional[str] = None
    trigger: Optional[str] = None
    input_instant_shifted: Optional[bool] = None
    native_coordinates_may_be_corrected: Optional[bool] = None
    context_strategy: Optional[str] = None
    native_cache_resets_so_far: Optional[int] = None
    reference_preflight: Optional[str] = None
    calls_corrected_so_far: Optional[int] = None
    native_states_changed_so_far: Optional[int] = None
    records: Optional[List[CompressedEndpointRecord]] = None
    unrecorded_calls_at_record_limit: Optional[int] = None
    source_url: Optional[str] = None
    scope: Optional[str] = None


class NativeCoordinateContext(CompressedEndpointRecord):
    policy_id: Optional[str] = None
    original_target_state_status: Optional[str] = None
    private_native_cache_reset: Optional[bool] = None
    preflight_reference: Optional[str] = None
    scope: Optional[str] = None


class NativeExecutionContext(PartialOutput):
    mechanism: Optional[str] = None
    lifetime: Optional[str] = None
    auxiliary_candidates_checked: Optional[int] = None
    auxiliary_files_present: Optional[List[Dict[str, JsonValue]]] = None
    scope: Optional[str] = None
    compressed_file_endpoint_policy: Optional[CompressedEndpointPolicy] = None


class SolarPositionBody(PartialOutput):
    status: Optional[str] = None
    unbent_ray_domain: Optional[str] = None
    reason: Optional[str] = None
    coordinate_backends: Optional[Dict[str, str]] = None
    impact_solar_radius_fraction: Optional[float] = None
    target_distance_au: Optional[float] = None
    solar_distance_au: Optional[float] = None
    solar_projection_distance_au: Optional[float] = None
    arithmetic_margin_fraction: Optional[float] = None
    position_interpretation: Optional[str] = None
    observational_accuracy_certified: Optional[bool] = None
    maximum_physical_error_arcseconds: Optional[float] = None


class SolarModelRegularity(PartialOutput):
    profile: Optional[str] = None
    source_profile_sha256: Optional[str] = None
    axis_continuity_certified: Optional[bool] = None
    unique_rate_at_mass_knots_certified: Optional[bool] = None
    scope: Optional[str] = None


class ApparentPositionPolicy(PartialOutput):
    method_id: Optional[str] = None
    epoch_jd_tt: Optional[float] = None
    native_version: Optional[str] = None
    binding_version: Optional[str] = None
    solar_deflection_model: Optional[str] = None
    source_url: Optional[str] = None
    source_section: Optional[str] = None
    native_source_url: Optional[str] = None
    native_model_solar_radius_au: Optional[float] = None
    source_model_regularity: Optional[SolarModelRegularity] = None
    coordinate_origin: Optional[str] = None
    geometry_frame: Optional[str] = None
    bodies: Optional[Dict[str, SolarPositionBody]] = None
    excluded_factors: Optional[Dict[str, str]] = None
    source_contexts: Optional[Dict[str, PhysicalFactorSource]] = None
    displayed_native_positions_changed: Optional[bool] = None
    observational_accuracy_certified: Optional[bool] = None
    scope: Optional[str] = None
