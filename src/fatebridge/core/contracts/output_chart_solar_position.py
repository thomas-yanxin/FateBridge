"""Solar observation and position evidence."""

from typing import Literal

from pydantic import Field

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_chart_geometry import EphemerisReferencePoints
from fatebridge.core.contracts.output_midpoint_geometry import PhysicalEphemerisSource


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
