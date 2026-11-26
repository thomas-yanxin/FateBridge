"""Horary placements, dignities and lunar testimony."""

from typing import Literal

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_chart_geometry import EphemerisReferencePoints
from fatebridge.core.contracts.output_chart_motion import LongitudeMotionPolicy
from fatebridge.core.contracts.output_midpoint_geometry import PhysicalEphemerisSource
from fatebridge.core.contracts.output_western_geometry import WesternPoint


class LillyDignity(PartialOutput):
    rule_id: str | None = None
    status: str | None = None
    planet: str | None = None
    longitude: float | None = None
    sign: str | None = None
    degree_in_sign: float | None = None
    chart_sect: str | None = None
    dignities: list[str] | None = None
    unknown_dignities: list[str] | None = None
    debilities: list[str] | None = None
    peregrine: bool | None = None
    lords: dict[str, str | None] | None = None
    bound_start_degree: int | None = None
    bound_end_degree: int | None = None
    exaltation_degree_in_sign: int | None = None
    source_pages: list[int] | None = None
    boundary_policy: str | None = None


class LillyReception(PartialOutput):
    rule_id: str | None = None
    receiver: str | None = None
    guest: str | None = None
    guest_longitude: float | None = None
    guest_sign: str | None = None
    chart_sect: str | None = None
    allowed_dignities: list[str] | None = None
    dignities: list[str] | None = None
    unknown_dignities: list[str] | None = None
    receives: bool | None = None
    source_pages: list[int] | None = None


class LillyPairReception(PartialOutput):
    rule_id: str | None = None
    status: str | None = None
    directions: list[LillyReception] | None = None
    mutual: bool | None = None
    mutual_same_kind: list[str] | None = None


class LillyCondition(PartialOutput):
    code: str | None = None
    passed: bool | None = None
    status: str | None = None
    source_pages: list[int] | None = None
    detail: str | None = None


class LillyHouseCondition(PartialOutput):
    occupied_house: int | None = None
    house_class: str | None = None
    p48_strength_rank: int | None = None
    p48_rank_condition: str | None = None
    p115_house_points: int | None = None
    points_scope: str | None = None
    assignment_policy: str | None = None
    house_system: str | None = None
    zodiac_type: str | None = None
    source_method_scope: str | None = None
    source_url: str | None = None
    source_pages: list[int] | None = None
    full_original_text_acceptance: bool | None = None


class LillyHouseAssignment(PartialOutput):
    rule_id: str | None = None
    source_url: str | None = None
    source_pages: list[int] | None = None
    status: str | None = None
    unavailable_reason: str | None = None
    geometric_house: int | None = None
    assigned_house: int | None = None
    changed_from_geometric_house: bool | None = None
    five_degree_limit: int | None = None
    boundary_policy: str | None = None
    assignment_policy: str | None = None
    house_system: str | None = None
    zodiac_type: str | None = None
    source_method_scope: str | None = None
    source_exception: str | None = None
    full_original_text_acceptance: bool | None = None
    longitude: float | None = None
    lower_cusp: float | None = None
    next_cusp: float | None = None
    previous_cusp_gap_degrees: float | None = None
    next_cusp_gap_degrees: float | None = None
    previous_cusp_gap_exact_degrees: str | None = None
    next_cusp_gap_exact_degrees: str | None = None
    assigned_p115_house_points: int | None = None
    assigned_p145_house_points: int | None = None
    conditional_reading_zh: str | None = None


class HoraryPlanet(WesternPoint):
    house_assignment: LillyHouseAssignment | None = None
    occupied_house: int | None = None
    house_condition: LillyHouseCondition | None = None
    speed: float | None = None
    dignities: list[str] | None = None
    essential_condition: LillyDignity | None = None


class HoraryAspect(PartialOutput):
    orb_profile: str | None = None
    orb_limit: float | None = None
    separation: float | None = None
    ray_degrees: int | None = None
    after_days: float | None = None
    julian_day_tt: float | None = None
    root_bracket_tt: list[float] | None = None
    moon_longitude: float | None = None
    other_longitude: float | None = None
    moon_latitude: float | None = None
    other_latitude: float | None = None
    datetime_utc: str | None = None
    inside_current_orb: bool | None = None
    angle: float | None = None
    aspect: str | None = None
    aspect_label: str | None = None
    orb: float | None = None
    other: str | None = None
    other_label: str | None = None
    applying: bool | None = None
    phase: str | None = None


class HoraryMotionBasis(PartialOutput):
    future_speed_policy: dict[str, OpenJsonValue] | None = None
    ephemeris_reference_points: EphemerisReferencePoints | None = None
    longitude_motion: LongitudeMotionPolicy | None = None
    status: str | None = None
    method_id: str | None = None
    constant_velocity_projection: bool | None = None
    degrees_left_in_sign: float | None = None
    sign_exit_after_days: float | None = None
    sign_exit_julian_day_tt: float | None = None
    sign_exit_root_bracket_tt: list[float] | None = None
    start_julian_day_tt: float | None = None
    contacts: list[HoraryAspect] | None = None
    ambiguous_boundary_contacts: list[HoraryAspect] | None = None
    void_of_course: bool | None = None
    unavailable_reason: str | None = None
    source_url: str | None = None
    source_scope: str | None = None
    time_scale: str | None = None
    scan_step_days: float | None = None
    scan_guard_days: int | None = None
    monotonicity_evidence: str | None = None
    physical_ephemeris_source: PhysicalEphemerisSource | None = None
    longitude_frame: str | None = None
    datetime_utc: str | None = None


class HoraryMoon(PartialOutput):
    motion_basis: HoraryMotionBasis | None = None
    degrees_left_in_sign: float | None = None
    next_aspect: HoraryAspect | None = None
    sign: str | None = None
    sign_label: str | None = None
    speed: float | None = None
    void_of_course: bool | None = None


class LillyDirectedSignRelationship(PartialOutput):
    method_id: str | None = None
    caster: str | None = None
    receiver: str | None = None
    caster_sign: str | None = None
    receiver_sign: str | None = None
    forward_sign_steps: int | None = None
    distinct_bodies: bool | None = None
    relation_status: (
        Literal["ray", "co_present", "listed_inconjunct", "not_in_either_table"] | None
    ) = None
    sign_ray: Literal["sextile", "square", "trine", "opposition"] | None = None
    ray_direction: Literal["dexter", "sinister"] | None = None
    listed_inconjunct: bool | None = None
    selected_degree_aspect: str | None = None
    selected_degree_aspect_agrees: bool | None = None
    coordinate_scope: str | None = None
    source_pages: list[int] | None = None
    source_url: str | None = None
    boundary_policy: str | None = None
    direction_policy: str | None = None
    quantitative_bonus_added: Literal[False] | None = None
    full_original_text_acceptance: Literal[False] | None = None


class HorarySignificators(PartialOutput):
    querent: HoraryPlanet | None = None
    quesited: HoraryPlanet | None = None
    moon_co_significator: HoraryPlanet | None = None
    directed_sign_relationship: LillyDirectedSignRelationship | None = None


class LillyRoute(PartialOutput):
    mode: str | None = None
    actors: list[str] | None = None
    condition_epoch: str | None = None
    status: str | None = None
    conditions: list[LillyCondition] | None = None
    receptions: list[LillyReception] | None = None
    full_path_accepted: bool | None = None
    source_planet: str | None = None
    target_planet: str | None = None
    carrier: str | None = None
    collector: str | None = None
    aspect: HoraryAspect | None = None
    next_lunar_contact: HoraryAspect | None = None


class LillyConditionalReading(PartialOutput):
    premise_satisfied: bool | None = None
    source_pages: list[int] | None = None
    conditional_reading_zh: str | None = None
    full_judgement_accepted: bool | None = None
