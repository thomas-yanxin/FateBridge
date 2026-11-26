"""Shared projected contract for the actually selected Earth-rotation policy."""

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_ut1 import C04UT1Evidence


class LongtermPhaseAlignment(PartialOutput):
    method: str | None = None
    boundary_tt_jd: float | None = None
    native_longterm_variation_retained: bool | None = None
    absolute_accuracy_certified: bool | None = None
    derivative_continuity_certified: bool | None = None
    source_url: str | None = None
    source_section: str | None = None
    attribution: str | None = None


class TerrestrialOrientation(PartialOutput):
    polar_motion_applied: bool | None = None
    celestial_pole_offsets_applied: bool | None = None
    polar_motion_x_radians: float | None = None
    polar_motion_y_radians: float | None = None
    tio_locator_radians: float | None = None
    celestial_pole_offsets_arcseconds: list[float] | None = None
    cio_locator_policy: str | None = None
    origin_policy: str | None = None
    local_frame_policy: str | None = None
    tidal_model_id: str | None = None
    cpo_application_policy: str | None = None
    station_velocity_scope: str | None = None
    vertical_scope: str | None = None


class EarthRotationPolicy(PartialOutput):
    tt_argument_policy: str | None = None
    ut1_reference: C04UT1Evidence | None = None
    terrestrial_orientation: TerrestrialOrientation | None = None
    policy_id: str | None = None
    sidereal_time_model: str | None = None
    implementation: str | None = None
    model_epoch_jd_tt: float | None = None
    model_epoch_jd_ut1: float | None = None
    modern_adoption_window_tt: dict[str, float] | None = None
    native_iers_interval_ut1: dict[str, float] | None = None
    native_interval_role: str | None = None
    celestial_frame_model: str | None = None
    celestial_frame_scope: str | None = None
    source_equatorial_frame_model: str | None = None
    origin_method: str | None = None
    erfa_version: str | None = None
    selection_basis: str | None = None
    longterm_phase_alignment: LongtermPhaseAlignment | None = None
    nutation_model: str | None = None
    other_astronomical_models: str | None = None
    geographic_longitude_policy: str | None = None
    native_event_api_scope: str | None = None
    scope: str | None = None
    measured_eop_applied: bool | None = None
    precision_scope: str | None = None
    source_url: str | None = None
    origin_source_url: str | None = None
    frame_source_url: str | None = None
    native_frame_source_url: str | None = None
