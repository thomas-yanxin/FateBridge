"""Projectable astrodice evidence contracts shared by every transport."""

from typing import Dict, List, Literal, Optional

from pydantic import Field, JsonValue

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_charts import (
    ChartProfile,
    EphemerisReferencePoints,
    HousePositionProjection,
)
from fatebridge.core.output_chinese import LocalAngles, LocalHouse, LocalObject


class ConditionEvidence(PartialOutput):
    condition: Optional[Literal["domicile", "exaltation", "detriment", "fall"]] = None
    matched: Optional[bool] = None
    basis_signs: Optional[List[str]] = None
    ruleset_id: Optional[str] = None
    source_url: Optional[str] = None
    derivation: Optional[str] = None
    status: Optional[str] = None


class SignCondition(PartialOutput):
    status: Optional[str] = None
    conditions: Optional[List[str]] = None
    condition_evidence: Optional[List[ConditionEvidence]] = None
    domicile_ruler: Optional[str] = None
    dispositor_status: Optional[str] = None
    unassessed: Optional[List[str]] = None
    note: Optional[str] = None


class SymbolicHouse(PartialOutput):
    house_number: Optional[int] = None
    sign: Optional[str] = None
    domicile_ruler: Optional[str] = None


class HouseCondition(PartialOutput):
    status: Optional[str] = None
    joy_house_number: Optional[int] = None
    in_joy: Optional[bool] = None
    ruleset_id: Optional[str] = None
    scope: Optional[str] = None


class TriplicityRulers(PartialOutput):
    primary: Optional[str] = None
    co_ruler: Optional[str] = None


class TriplicityCondition(PartialOutput):
    status: Optional[str] = None
    ruleset_id: Optional[str] = None
    sect: Optional[str] = None
    assigned_rulers: Optional[List[str]] = Field(
        default=None,
        description="Robbins I.18 overall triangle assignment; distinct from governance under a named day/night condition.",
    )
    in_assigned_group: Optional[bool] = Field(
        default=None,
        description="Membership in the overall assignment. Null means the rolled body is outside the seven-planet reference scope.",
    )
    roles_by_sect: Optional[
        Dict[
            str,
            Literal[
                "primary",
                "co_ruler",
                "assigned_not_selected",
                "not_assigned",
                "outside_seven_planet_scope",
            ],
        ]
    ] = Field(
        default=None,
        description="Separate day/night conditional roles; assigned_not_selected preserves overall membership without selecting the named primary/co-ruler role.",
    )
    rulers_by_sect: Optional[Dict[str, TriplicityRulers]] = None
    matches_by_sect: Optional[Dict[str, Optional[bool]]] = Field(
        default=None,
        description="Match to the returned primary or explicit co-ruler under each named condition. False does not negate overall triangle assignment or all dignity; null means outside seven-planet scope.",
    )
    match_definition: Optional[str] = None
    scope: Optional[str] = None


class PlanetSectAssignments(PartialOutput):
    morning_star: Optional[Literal["day", "night"]] = None
    evening_star: Optional[Literal["day", "night"]] = None


class PlanetSectCondition(PartialOutput):
    status: Optional[
        Literal[
            "natural_assignment_without_chart_sect",
            "conditional_on_solar_phase_not_in_roll",
            "outside_seven_planet_scope",
        ]
    ] = None
    ruleset_id: Optional[str] = None
    natural_sect: Optional[Literal["day", "night"]] = Field(
        default=None,
        description="Robbins I.7 natural assignment. Mercury is unresolved without its solar phase; outer planets and nodes are outside this seven-planet rule.",
    )
    assignments_by_solar_phase: Optional[PlanetSectAssignments] = None
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
    scope: Optional[str] = None


class DiceDetails(PartialOutput):
    house_number: Optional[int] = None
    planet_kind: Optional[str] = None
    element: Optional[str] = None
    modality: Optional[str] = None
    house_group: Optional[str] = None
    sign_condition: Optional[SignCondition] = None
    house_condition: Optional[HouseCondition] = None
    triplicity_condition: Optional[TriplicityCondition] = None
    planet_sect_condition: Optional[PlanetSectCondition] = None
    symbolic_house_ring: Optional[List[SymbolicHouse]] = None
    houses_ruled_by_rolled_planet: Optional[List[int]] = None


class InterpretationBasis(PartialOutput):
    text_path: Optional[str] = None
    kind: Optional[
        Literal[
            "product_vocabulary",
            "editorial_traditional_paraphrase",
            "conditional_rule_paraphrase",
            "product_convention",
            "reality_check_prompt",
            "epistemic_limit",
            "user_context",
        ]
    ] = None
    fact_paths: Optional[List[str]] = None
    rule_ids: Optional[List[str]] = None
    ruleset_ids: Optional[List[str]] = None


class DiceInterpretation(PartialOutput):
    planet_keyword: Optional[str] = None
    sign_keyword: Optional[str] = None
    house_keyword: Optional[str] = None
    summary: Optional[str] = None
    question_adjustment: Optional[str] = None
    condition_meanings: Optional[List[str]] = None
    house_condition_meaning: Optional[str] = None
    triplicity_meaning: Optional[str] = None
    planet_sect_meaning: Optional[str] = None
    dispositor_meaning: Optional[str] = None
    symbolic_links: Optional[str] = None
    reality_check: Optional[str] = None
    basis: Optional[List[str]] = None
    limits: Optional[str] = None
    evidence: Optional[Dict[str, InterpretationBasis]] = None


class DiceRuleset(PartialOutput):
    id: Optional[str] = None
    author: Optional[str] = None
    version: Optional[str] = None
    source_url: Optional[str] = None
    source_path: Optional[str] = None
    additional_urls: Optional[List[str]] = None
    source_kind: Optional[str] = None
    scope: Optional[str] = None


class DiceRuleTrace(PartialOutput):
    rule_id: Optional[str] = None
    ruleset_id: Optional[str] = None
    supporting_ruleset_ids: Optional[List[str]] = None
    inputs: Optional[Dict[str, JsonValue]] = None
    result: Optional[Dict[str, JsonValue]] = None
    scope: Optional[str] = None


class DiceValidation(PartialOutput):
    calendar: Optional[str] = None
    classical: Optional[str] = None
    interpretation: Optional[str] = None
    prediction: Optional[str] = None
    real_world_sample_size: Optional[int] = None
    authority_certified: Optional[bool] = None
    limitations: Optional[List[str]] = None


class FortuneDefinition(PartialOutput):
    method: Optional[Literal["sect_reversing", "ptolemy_iii10"]] = None
    formula: Optional[str] = None
    sect_applied: Optional[Literal["day", "night"]] = None
    author: Optional[str] = None
    edition: Optional[str] = None
    source_url: Optional[str] = None
    source_path: Optional[str] = None
    source_kind: Optional[Literal["primary_text_translation", "runtime_convention"]] = (
        None
    )
    scope: Optional[str] = None


class DiceSkyParams(PartialOutput):
    chart_profile: Optional[ChartProfile] = None
    birthLatitude: Optional[float] = None
    birthLongitude: Optional[float] = None
    coordinatePolicy: Optional[str] = None
    housePositionMethod: Optional[str] = None
    housePositionProjection: Optional[HousePositionProjection] = None
    lunarNodeModel: Optional[str] = None
    fortuneDefinition: Optional[FortuneDefinition] = None
    ephemerisReferencePoints: Optional[EphemerisReferencePoints] = None
    motionPolicy: Optional["DiceMotionPolicy"] = None


class DiceMotionPolicy(PartialOutput):
    policy_id: Optional[str] = None
    status: Optional[Literal["computed", "partial"]] = None
    uncomputed_points: Optional[List[str]] = None
    reference_frame: Optional[str] = None
    unit: Optional[Literal["degree_per_day"]] = None
    sign_policy: Optional[str] = None
    source_url: Optional[str] = None
    source_sections: Optional[str] = None
    scope: Optional[str] = None


class DiceLongitudeMotion(PartialOutput):
    longitude_speed: Optional[float] = None
    native_longitude_speed: Optional[float] = None
    light_time_correction: Optional[float] = None
    spatial_aberration_correction: Optional[float] = None
    lunar_source_remainder_correction: Optional[float] = None
    sidereal_origin_wrap_correction: Optional[float] = None
    rotation_correction: Optional[float] = None
    position_derivative_correction: Optional[float] = None
    method_id: Optional[str] = None
    correction_status: Optional[Literal["applied", "partial", "native_only"]] = None
    unit: Optional[Literal["degree_per_day"]] = None
    direction: Optional[
        Literal["direct", "retrograde", "zero_instantaneous_rate", "not_computed"]
    ] = None
    reference_frame: Optional[str] = None
    basis: Optional[str] = None
    source_model: Optional[str] = None


class DiceSkyObject(LocalObject):
    motion: Optional[DiceLongitudeMotion] = None


class DiceSkyGeometry(PartialOutput):
    angles: Optional[LocalAngles] = None
    houses: Optional[List[LocalHouse]] = None
    objects: Optional[List[DiceSkyObject]] = None
    ok: Optional[bool] = None


class DiceSkyChart(PartialOutput):
    chart: Optional[DiceSkyGeometry] = None
    params: Optional[DiceSkyParams] = None


ASTRODICE_FIELDS = {
    "chart": DiceSkyChart,
    "method_id": str,
    "symbolic_details": DiceDetails,
    "interpretation": DiceInterpretation,
    "rulesets": List[DiceRuleset],
    "rule_trace": List[DiceRuleTrace],
    "validation": DiceValidation,
}
