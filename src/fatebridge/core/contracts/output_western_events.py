"""Planetary event history and horary event paths."""

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_chart_geometry import EphemerisReferencePoints
from fatebridge.core.contracts.output_chart_motion import LongitudeMotionPolicy
from fatebridge.core.contracts.output_charts import ApparentPositionPolicy
from fatebridge.core.contracts.output_midpoint_geometry import PhysicalEphemerisSource
from fatebridge.core.contracts.output_western_horary_facts import (
    LillyCondition,
    LillyReception,
)


class PlanetaryEventState(PartialOutput):
    longitude: float | None = None
    latitude: float | None = None
    speed: float | None = None
    speed_native: float | None = None
    speed_light_time_correction: float | None = None
    speed_spatial_aberration_correction: float | None = None
    speed_lunar_source_remainder_correction: float | None = None
    speed_sidereal_origin_wrap_correction: float | None = None
    speed_rotation_correction: float | None = None
    speed_analytic_frame_correction: float | None = None
    speed_position_derivative_correction: float | None = None
    speed_display_offset_correction: float | None = None


class PlanetaryEventFailedSample(PartialOutput):
    planet: str | None = None
    julian_day_tt: float | None = None


class PlanetaryEvent(PartialOutput):
    kind: str | None = None
    bodies: list[str] | None = None
    julian_day_tt: float | None = None
    root_bracket_tt: list[float] | None = None
    epoch_relation: str | None = None
    states: dict[str, PlanetaryEventState] | None = None
    state_brackets: dict[str, list[PlanetaryEventState]] | None = None
    ray_degrees: int | None = None
    direction: int | None = None
    topology: str | None = None
    aspect: str | None = None
    datetime_utc: str | None = None


class PlanetaryUnresolvedInterval(PartialOutput):
    kind: str | None = None
    bodies: list[str] | None = None
    interval_tt: list[float] | None = None


class PlanetaryEventHistory(PartialOutput):
    apparent_position_policy: ApparentPositionPolicy | None = None
    ephemeris_reference_points: EphemerisReferencePoints | None = None
    longitude_motion: LongitudeMotionPolicy | None = None
    status: str | None = None
    method_id: str | None = None
    constant_velocity_projection: bool | None = None
    time_scale: str | None = None
    question_julian_day_tt: float | None = None
    window_tt: list[float] | None = None
    scan_step_days: float | None = None
    bodies: list[str] | None = None
    question_states: dict[str, PlanetaryEventState] | None = None
    events: list[PlanetaryEvent] | None = None
    unresolved_intervals: list[PlanetaryUnresolvedInterval] | None = None
    completeness_scope: str | None = None
    full_original_text_acceptance: bool | None = None
    physical_ephemeris_source: PhysicalEphemerisSource | None = None
    longitude_frame: str | None = None
    unavailable_reason: str | None = None
    unavailable_code: str | None = None
    failed_sample: PlanetaryEventFailedSample | None = None


class EventReception(PartialOutput):
    julian_day_tt: float | None = None
    root_bracket_tt: list[float] | None = None
    chart_sect: str | None = None
    reception: LillyReception | None = None
    endpoint_receptions: list[LillyReception] | None = None
    boundary_uncertainty: bool | None = None


class LillyEventPath(PartialOutput):
    mode: str | None = None
    actors: list[str] | None = None
    conditions: list[LillyCondition] | None = None
    sequence_conditions_satisfied: bool | None = None
    status: str | None = None
    event_receptions: list[EventReception] | None = None
    full_path_accepted: bool | None = None
    prior_principal_contact: PlanetaryEvent | None = None
    prior_carrier_contact: PlanetaryEvent | None = None
    future_contact: PlanetaryEvent | None = None
    transitions: list[PlanetaryEvent] | None = None
    intervening_contacts: list[PlanetaryEvent] | None = None
    collection_contacts: list[PlanetaryEvent] | None = None


class RefranationPattern(PartialOutput):
    applicant: str | None = None
    recipient: str | None = None
    station: PlanetaryEvent | None = None
    source_pages: list[int] | None = None
    scope: str | None = None


class ProhibitionPattern(PartialOutput):
    interposer: str | None = None
    applicant: str | None = None
    recipient: str | None = None
    first_contact: PlanetaryEvent | None = None
    second_contact: PlanetaryEvent | None = None
    source_pages: list[int] | None = None
    scope: str | None = None


class LillyEventPaths(PartialOutput):
    status: str | None = None
    paths: list[LillyEventPath] | None = None
    refranation_patterns: list[RefranationPattern] | None = None
    prohibition_patterns: list[ProhibitionPattern] | None = None
    reception_epoch_policy: str | None = None
    source_pages: list[int] | None = None
    scope: str | None = None
    full_original_text_acceptance: bool | None = None
    unavailable_reason: str | None = None
