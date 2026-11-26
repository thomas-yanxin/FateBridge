"""Midpoint geometry, factors and ephemeris provenance."""

from typing import Literal

from pydantic import Field

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput


class GeometrySource(PartialOutput):
    id: str | None = None
    author: str | None = None
    title: str | None = None
    url: str | None = None
    scope: str | None = None
    sections: list[str] | None = None
    source_sha256: str | None = None


class ReferenceAngleGeometry(PartialOutput):
    reference_angle_basis: dict[str, str] | None = None
    physical_reference_geometry_resolved: bool | None = None


class MidpointFactor(PartialOutput):
    coordinate_basis: str | None = None
    angle_definition: dict[str, OpenJsonValue] | None = None
    native_return_flags: int | None = None
    id: str | None = None
    longitude: float | None = None
    kind: str | None = None
    model: str | None = None
    element_name: str | None = None


class MeridianFactorPosition(PartialOutput):
    id: str | None = None
    kind: str | None = None
    model: str | None = None
    status: str | None = None
    right_ascension: float | None = None
    right_ascension_raw_degrees: float | None = None
    declination: float | None = None
    equatorial_horizontal_norm: float | None = None
    input_tropical_longitude: float | None = None
    input_ecliptic_latitude: float | None = None
    longitude_only_control_house: int | None = None
    longitude_only_control_house_position: float | None = None
    house: int | None = None
    house_position: float | None = None
    offset_from_first_cusp_degrees: float | None = None
    distance_to_nearest_cusp_degrees: float | None = None
    latitude_changes_house: bool | None = None


class MidpointAxis(ReferenceAngleGeometry):
    id_a: str | None = None
    id_b: str | None = None
    axis_longitude: float | None = None
    opposite_longitude: float | None = None
    antipodal_inputs: bool | None = None
    dial_90: float | None = None
    dial_45: float | None = None
    self_midpoint: bool | None = None
    rule_id: str | None = None
    contains_hypothetical: bool | None = None


class SensitivePoint(ReferenceAngleGeometry):
    plus: list[str] | None = None
    minus: str | None = None
    occupant: str | None = None
    equation: str | None = None
    longitude: float | None = None
    occupant_longitude: float | None = None
    period_degrees: int | None = None
    signed_orb: float | None = None
    orb: float | None = None
    maximum_orb_degrees: float | None = None
    direct_signed_orb: float | None = None
    direct_orb: float | None = None
    occupancy: str | None = None
    rule_id: str | None = None


class SourceInterpretation(ReferenceAngleGeometry):
    source_application_status: str | None = None
    backend_reading_zh: str | None = None
    claim_id: str | None = None
    factor_longitudes: dict[str, float] | None = None
    contains_hypothetical: bool | None = None
    source_id: str | None = None
    source_section: str | None = None
    source_expression: str | None = None
    basis_expression: str | None = None
    sensitive_point_longitude: float | None = None
    occupant_longitude: float | None = None
    direct_orb_degrees: float | None = None
    maximum_orb_degrees: float | None = None
    symbolic_theme_zh: str | None = None
    reading_zh: str | None = None
    practical_prompt_zh: str | None = None
    claim_type: str | None = None
    rule_id: str | None = None
    birth_time_sampled_status: str | None = None
    factor_layers: dict[str, str] | None = None
    analysis_utc: str | None = None
    solar_arc_degrees: float | None = None


class SymmetryContact(ReferenceAngleGeometry):
    point: str | None = None
    id_a: str | None = None
    id_b: str | None = None
    id_c: str | None = None
    id_d: str | None = None
    equation: str | None = None
    orb: float | None = None
    signed_orb: float | None = None
    axis_offset_degrees: int | None = None
    rule_id: str | None = None
    contains_hypothetical: bool | None = None
    sensitive_point: SensitivePoint | None = None
    source_interpretation: SourceInterpretation | None = None


class TwoFactorContact(ReferenceAngleGeometry):
    id_a: str | None = None
    id_b: str | None = None
    equation: str | None = None
    orb: float | None = None
    signed_orb: float | None = None
    factor_offset_degrees: int | None = None
    aspect_degrees: int | None = None
    separation_degrees: float | None = None
    rule_id: str | None = None
    contains_hypothetical: bool | None = None


class MidpointDial(PartialOutput):
    period_degrees: int | None = None
    two_factor_contacts: list[TwoFactorContact] | None = None
    three_factor_contacts: list[SymmetryContact] | None = None
    four_factor_contacts: list[SymmetryContact] | None = None


class FictitiousElementSource(PartialOutput):
    filename: str | None = None
    status: str | None = None
    search_path_index: int | None = None
    sha256: str | None = None
    scope: str | None = None


class PhysicalEphemerisFile(PartialOutput):
    id: str | None = None
    slot: int | None = None
    filename: str | None = None
    sha256: str | None = None
    bytes: int | None = None
    range_time_scale: Literal["TT", "TDB"] | None = None
    start_julian_day_tt: float | None = Field(
        default=None,
        description="Swiss se1 native range start in its TT argument convention; absent for JPL raw headers.",
    )
    end_julian_day_tt: float | None = Field(
        default=None,
        description="Swiss se1 native range end in its TT argument convention; absent for JPL raw headers.",
    )
    start_julian_day_tdb: float | None = Field(
        default=None, description="JPL raw TDB header start; no TDB-to-TT conversion."
    )
    end_julian_day_tdb: float | None = Field(
        default=None, description="JPL raw TDB header end; no TDB-to-TT conversion."
    )
    de_number: int | None = None
    matches_packaged_manifest: bool | None = None


class PhysicalFactorSource(PartialOutput):
    model: str | None = None
    status: str | None = None
    file_ids: list[str] | None = None


class EphemerisTimeScalePolicy(PartialOutput):
    policy_id: str | None = None
    status: str | None = None
    native_version: str | None = None
    binding_version: str | None = None
    native_api_time_scale: str | None = None
    raw_header_time_scale: str | None = None
    tt_tdb_conversion_applied: bool | None = None
    source_documented_maximum_difference_seconds: float | None = None
    source_function: str | None = None
    source_url: str | None = None
    native_source_url: str | None = None
    scope: str | None = None


class PhysicalEphemerisSource(PartialOutput):
    ruleset_id: str | None = None
    by_factor: dict[str, PhysicalFactorSource] | None = None
    files: list[PhysicalEphemerisFile] | None = None
    has_unidentified_sources: bool | None = None
    scope: str | None = None
    atomic_file_read_proven: bool | None = None
    accuracy_certified: bool | None = None
    time_scale_policy: EphemerisTimeScalePolicy | None = None


class ReferenceAngleModel(PartialOutput):
    house_code: str | None = None
    house_flags: int | None = None
    cusp_output_used: bool | None = None
    role: str | None = None
    used_reference_outputs: list[str] | None = None


class MidpointProfile(PartialOutput):
    reference_angle_model: ReferenceAngleModel | None = None
    angle_definition: dict[str, OpenJsonValue] | None = None
    ephemeris_model_scope: str | None = None
    zodiac: str | None = None
    calendar: str | None = None
    time_scale: str | None = None
    orb_degrees: float | None = None
    orb_policy: str | None = None
    coordinate_rounding_before_comparison: bool | None = None
    factor_count: int | None = None
    contact_policy: str | None = None
    hypothetical_model: str | None = None
    aries_point: str | None = None
    node_mode: str | None = None
    seven_planet_view: str | None = None
    sensitive_point_policy: str | None = None
    ephemeris_models: list[str] | None = None
    julian_day_tt: float | None = None
    julian_day_ut1: float | None = None
    julian_day_utc: float | None = None
    time_scale_method: str | None = None
    future_leap_seconds_assumed_unchanged: bool | None = None
    swisseph_version: str | None = None
    hypothetical_element_source: FictitiousElementSource | None = None
    physical_ephemeris_source: PhysicalEphemerisSource | None = None


class GeometryRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    source_ids: list[str] | None = None


class GeometryRuleTrace(PartialOutput):
    rule_id: str | None = None
    source_id: str | None = None
    source_sections: list[str] | None = None
    formula: str | None = None
    scope: str | None = None


class DialCounts(PartialOutput):
    two_factor: int | None = None
    three_factor: int | None = None
    four_factor: int | None = None


class FactorSpan(PartialOutput):
    status: str | None = None
    backend_convention_span: dict[str, float] | None = None
    unresolved_sample_count: int | None = None
    minimum_offset_from_nominal_degrees: float | None = None
    maximum_offset_from_nominal_degrees: float | None = None
    maximum_adjacent_sample_jump_degrees: float | None = None
