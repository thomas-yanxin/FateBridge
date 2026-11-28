"""Projectable astrodice evidence contracts shared by every transport."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, JsonValue

from fatebridge.core.contracts import output_charts
from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_chart_geometry import HousePositionProjection
from fatebridge.core.contracts.output_chart_profile import ChartProfile
from fatebridge.core.contracts.output_chinese_bundles import (
    LocalAngles,
    LocalHouse,
    LocalObject,
)


class ConditionEvidence(PartialOutput):
    condition: Literal["domicile", "exaltation", "detriment", "fall"] | None = None
    matched: bool | None = None
    basis_signs: list[str] | None = None
    ruleset_id: str | None = None
    source_url: str | None = None
    derivation: str | None = None
    status: str | None = None


class SignCondition(PartialOutput):
    status: str | None = None
    conditions: list[str] | None = None
    condition_evidence: list[ConditionEvidence] | None = None
    domicile_ruler: str | None = None
    dispositor_status: str | None = None
    unassessed: list[str] | None = None
    note: str | None = None


class SymbolicHouse(PartialOutput):
    house_number: int | None = None
    sign: str | None = None
    domicile_ruler: str | None = None


class HouseCondition(PartialOutput):
    status: str | None = None
    joy_house_number: int | None = None
    in_joy: bool | None = None
    ruleset_id: str | None = None
    scope: str | None = None


class TriplicityRulers(PartialOutput):
    primary: str | None = None
    co_ruler: str | None = None


class TriplicityCondition(PartialOutput):
    status: str | None = None
    ruleset_id: str | None = None
    sect: str | None = None
    assigned_rulers: list[str] | None = Field(
        default=None,
        description="Robbins I.18 overall triangle assignment; distinct from governance under a named day/night condition.",
    )
    in_assigned_group: bool | None = Field(
        default=None,
        description="Membership in the overall assignment. Null means the rolled body is outside the seven-planet reference scope.",
    )
    roles_by_sect: (
        dict[
            str,
            Literal[
                "primary",
                "co_ruler",
                "assigned_not_selected",
                "not_assigned",
                "outside_seven_planet_scope",
            ],
        ]
        | None
    ) = Field(
        default=None,
        description="Separate day/night conditional roles; assigned_not_selected preserves overall membership without selecting the named primary/co-ruler role.",
    )
    rulers_by_sect: dict[str, TriplicityRulers] | None = None
    matches_by_sect: dict[str, bool | None] | None = Field(
        default=None,
        description="Match to the returned primary or explicit co-ruler under each named condition. False does not negate overall triangle assignment or all dignity; null means outside seven-planet scope.",
    )
    match_definition: str | None = None
    scope: str | None = None


class PlanetSectAssignments(PartialOutput):
    morning_star: Literal["day", "night"] | None = None
    evening_star: Literal["day", "night"] | None = None


class PlanetSectCondition(PartialOutput):
    status: (
        Literal[
            "natural_assignment_without_chart_sect",
            "conditional_on_solar_phase_not_in_roll",
            "outside_seven_planet_scope",
        ]
        | None
    ) = None
    ruleset_id: str | None = None
    natural_sect: Literal["day", "night"] | None = Field(
        default=None,
        description="Robbins I.7 natural assignment. Mercury is unresolved without its solar phase; outer planets and nodes are outside this seven-planet rule.",
    )
    assignments_by_solar_phase: PlanetSectAssignments | None = None
    solar_phase: None = Field(
        default=None, description="Not encoded by the rolled faces."
    )
    applied_chart_sect: None = Field(
        default=None,
        description="No actual day/night chart sect is inferred from dice or transferred from optional sky.",
    )
    matches_chart_sect: None = Field(
        default=None,
        description="Unassessed because a natural planet assignment alone cannot establish agreement with chart sect.",
    )
    scope: str | None = None


class DiceDetails(PartialOutput):
    house_number: int | None = None
    planet_kind: str | None = None
    element: str | None = None
    modality: str | None = None
    house_group: str | None = None
    sign_condition: SignCondition | None = None
    house_condition: HouseCondition | None = None
    triplicity_condition: TriplicityCondition | None = None
    planet_sect_condition: PlanetSectCondition | None = None
    symbolic_house_ring: list[SymbolicHouse] | None = None
    houses_ruled_by_rolled_planet: list[int] | None = None


class DiceValidation(PartialOutput):
    calendar: str | None = None
    classical: str | None = None


class FortuneDefinition(PartialOutput):
    method: Literal["sect_reversing", "ptolemy_iii10"] | None = None
    formula: str | None = None
    sect_applied: Literal["day", "night"] | None = None
    author: str | None = None
    edition: str | None = None
    source_url: str | None = None
    source_path: str | None = None
    source_kind: Literal["primary_text_translation", "runtime_convention"] | None = None
    scope: str | None = None


class DiceSkyParams(PartialOutput):
    chart_profile: ChartProfile | None = None
    birthLatitude: float | None = None
    birthLongitude: float | None = None
    coordinatePolicy: str | None = None
    housePositionMethod: str | None = None
    housePositionProjection: HousePositionProjection | None = None
    lunarNodeModel: str | None = None
    fortuneDefinition: FortuneDefinition | None = None
    ephemerisReferencePoints: output_charts.EphemerisReferencePoints | None = None
    motionPolicy: DiceMotionPolicy | None = None


class DiceMotionPolicy(PartialOutput):
    policy_id: str | None = None
    status: Literal["computed", "partial"] | None = None
    uncomputed_points: list[str] | None = None
    reference_frame: str | None = None
    unit: Literal["degree_per_day"] | None = None
    sign_policy: str | None = None
    source_url: str | None = None
    source_sections: str | None = None
    scope: str | None = None


class DiceLongitudeMotion(PartialOutput):
    longitude_speed: float | None = None
    native_longitude_speed: float | None = None
    model_longitude_speed: float | None = None
    sidereal_origin_correction: float | None = None
    source_url: str | None = None
    light_time_correction: float | None = None
    spatial_aberration_correction: float | None = None
    lunar_source_remainder_correction: float | None = None
    sidereal_origin_wrap_correction: float | None = None
    rotation_correction: float | None = None
    position_derivative_correction: float | None = None
    method_id: str | None = None
    correction_status: (
        Literal["applied", "partial", "native_only", "approximate_model"] | None
    ) = None
    unit: Literal["degree_per_day"] | None = None
    direction: (
        Literal["direct", "retrograde", "zero_instantaneous_rate", "not_computed"]
        | None
    ) = None
    reference_frame: str | None = None
    basis: str | None = None
    source_model: str | None = None


class DiceSkyObject(LocalObject):
    motion: DiceLongitudeMotion | None = None


class DiceSkyGeometry(PartialOutput):
    angles: LocalAngles | None = None
    houses: list[LocalHouse] | None = None
    objects: list[DiceSkyObject] | None = None
    ok: bool | None = None


class DiceSkyChart(PartialOutput):
    chart: DiceSkyGeometry | None = None
    params: DiceSkyParams | None = None


ASTRODICE_FIELDS = {
    "chart": DiceSkyChart,
    "method_id": str,
    "symbolic_details": DiceDetails,
    "validation": DiceValidation,
}
