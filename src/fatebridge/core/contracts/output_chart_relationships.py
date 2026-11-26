"""Chart variants and relationship outputs."""

from typing import Literal

from pydantic import Field

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_chart_classical import MoiraPattern
from fatebridge.core.contracts.output_chart_geometry import (
    ChartAngle,
    ChartAspect,
    ChartHouse,
    ChartPlanet,
    RelationshipDerivation,
)
from fatebridge.core.contracts.output_chart_profile import ChartProfile
from fatebridge.core.contracts.output_chinese_calendar import PersonInfo
from fatebridge.core.contracts.output_guolao import GuolaoMansion, GuolaoResearch
from fatebridge.core.contracts.output_jyotish import JyotishIndia


class Guolao(GuolaoResearch):
    god_sign_index: dict[str, int] | None = None
    lunar_mansion_system: str | None = None
    moira_patterns: list[MoiraPattern] | None = None
    moon_mansion: str | None = None
    planetary_mansions: list[GuolaoMansion] | None = None
    si_yu_sign_index: dict[str, int] | None = None
    weekday_ruler: str | None = None


class India(JyotishIndia):
    """Legacy name retained for the expanded Indian contract."""


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
