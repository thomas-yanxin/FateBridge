"""Classical and Hellenistic chart layers."""

from typing import Literal

from pydantic import Field

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_chart_geometry import ChartPoint
from fatebridge.core.contracts.output_clock_labels import WesternUTCRepresentation
from fatebridge.core.contracts.output_guolao import GuolaoPatternEvidence
from fatebridge.core.contracts.output_midpoint_geometry import PhysicalEphemerisSource


class ClassicalLot(PartialOutput):
    almuten: str | None = None
    cn: str | None = None
    degree_in_sign: float | None = None
    dispositor: str | None = None
    longitude: float | None = None
    sign: str | None = None


class EssentialDignities(PartialOutput):
    bound_lord: str | None = None
    debilities: list[str] | None = None
    dignities: list[str] | None = None
    face_lord: str | None = None
    labels_zh: list[str] | None = None
    peregrine: bool | None = None
    score: int | None = None
    known_score: int | None = None
    unknown_dignities: list[str] | None = None
    triplicity_ruler: str | None = None


class Melothesia(PartialOutput):
    body_parts: list[str] | None = None
    position: str | None = None


class OrientalityPolicy(PartialOutput):
    model: Literal["ecliptic_longitude_phase"] | None = None
    arithmetic: Literal["exact_supplied_finite_angles"] | None = None
    conjunction: Literal["unknown_at_exact_coincidence"] | None = None
    opposition: Literal["oriental_legacy_half_open_tie"] | None = None
    nonzero_deadband: Literal["none"] | None = None
    physical_rise_set_verified: Literal[False] | None = None
    heliacal_visibility_verified: Literal[False] | None = None
    author_transition_endpoints_certified: Literal[False] | None = None


class ClassicalPlanet(PartialOutput):
    above_horizon: bool | None = None
    angularity: str | None = None
    combustion: str | None = None
    dodekatemorion: str | None = None
    essential: EssentialDignities | None = None
    in_halb: bool | None = None
    joy: bool | None = None
    melothesia: Melothesia | None = None
    ninth_part: str | None = None
    orientality: str | None = None
    out_of_bounds: bool | None = None
    retrograde: bool | None = None
    sect_placement: str | None = None


class PtolemyTerm(PartialOutput):
    lord: str | None = None
    start_degree: int | None = Field(default=None, ge=0, lt=30)
    end_degree: int | None = Field(default=None, gt=0, le=30)
    chapter_ref: str | None = None


class PtolemyPlanet(PartialOutput):
    longitude: float | None = Field(default=None, ge=0, lt=360)
    sign: str | None = None
    degree_in_sign: float | None = Field(default=None, ge=0, lt=30)
    domicile_lord: str | None = None
    in_domicile: bool | None = None
    in_exaltation: bool | None = None
    in_depression: bool | None = None
    triplicity_primary: str | None = None
    triplicity_co_ruler: str | None = None
    natural_sect: str | None = None
    terms: dict[str, PtolemyTerm] | None = None


class PtolemyFortune(PartialOutput):
    formula: str | None = None
    longitude: float | None = Field(default=None, ge=0, lt=360)
    sign: str | None = None
    degree_in_sign: float | None = Field(default=None, ge=0, lt=30)
    source_url: str | None = None


class PtolemySignRelationship(PartialOutput):
    planet_a: str | None = None
    planet_b: str | None = None
    sign_a: str | None = None
    sign_b: str | None = None
    separation_signs: int | None = None
    same_sign: bool | None = None
    sign_aspect: str | None = None
    aspect_quality: str | None = None
    commanding_sign: str | None = None
    obeying_sign: str | None = None
    beholding_equal_power: bool | None = None
    disjunct: bool | None = None
    chapter_refs: list[str] | None = None


class PtolemyLayer(PartialOutput):
    orientality_policy: OrientalityPolicy | None = None
    term_policy: str | None = None
    term_source_url: str | None = None
    term_transcription_note: str | None = None
    sign_relationships: list[PtolemySignRelationship] | None = None
    sign_relationship_policy: str | None = None
    lot_of_fortune: PtolemyFortune | None = None
    ruleset_id: str | None = None
    author: str | None = None
    edition: str | None = None
    source_url: str | None = None
    chapters: dict[str, str] | None = None
    status: str | None = None
    scope: str | None = None
    planets: dict[str, PtolemyPlanet] | None = None


class AlmutenPoint(PartialOutput):
    degree_in_sign: float | None = None
    sign: str | None = None
    totals: dict[str, int] | None = None
    winner: str | None = None


AlmutenPointId = Literal["Sun", "Moon", "Ascendant", "fortune", "syzygy"]


class AlmutenMethodSource(PartialOutput):
    title: str | None = None
    author: str | None = None
    edition: str | None = None
    url: str | None = None
    section: str | None = None
    scope: str | None = None


class AlmutenFigurisMethod(PartialOutput):
    method_id: str | None = None
    source_profile: str | None = None
    scope: str | None = None
    dignity_weights: (
        dict[Literal["domicile", "exaltation", "triplicity", "term", "face"], int]
        | None
    ) = None
    triplicity_policy: str | None = None
    is_day: bool | None = None
    bounds_policy: str | None = None
    face_policy: str | None = None
    tie_break_policy: str | None = None
    tie_break_order: list[str] | None = None
    expected_points: list[AlmutenPointId] | None = None
    included_points: list[AlmutenPointId] | None = None
    missing_points: list[AlmutenPointId] | None = None
    historical_method_status: Literal["selected_mixed_subset"] | None = None
    source_refs: list[AlmutenMethodSource] | None = None


class AlmutenFiguris(PartialOutput):
    status: Literal["partial"] | None = None
    unknown_points: list[AlmutenPointId] | None = None
    known_totals: dict[str, int] | None = None
    method: AlmutenFigurisMethod | None = None
    points: dict[str, AlmutenPoint] | None = None
    totals: dict[str, int] | None = None
    winner: str | None = None


class DispositorChain(PartialOutput):
    chain: list[str] | None = None
    terminal: str | None = None
    terminal_type: str | None = None


class Dispositors(PartialOutput):
    chains: dict[str, DispositorChain] | None = None
    final_dispositors: list[str] | None = None
    mutual_receptions: list[list[str]] | None = None


class SyzygySolver(PartialOutput):
    method: str | None = None
    target_elongation: float | None = None
    residual_degrees: float | None = Field(default=None, ge=0, lt=1e-6)
    strictly_before_birth: bool | None = None


class SyzygySampleSource(PartialOutput):
    body: str | None = None
    stage: str | None = None
    model: str | None = None
    status: str | None = None
    file_ids: list[str] | None = None
    sample_count: int | None = Field(default=None, ge=1)
    minimum_jd_tt: float | None = None
    maximum_jd_tt: float | None = None


class SyzygyEphemerisSource(PartialOutput):
    method_id: str | None = None
    models_by_body: dict[str, list[str]] | None = None
    models_stable: bool | None = None
    sample_contexts: list[SyzygySampleSource] | None = None
    physical_ephemeris_source: PhysicalEphemerisSource | None = None
    absolute_accuracy_certified: bool | None = None
    scope: str | None = None
    note_zh: str | None = None


class Syzygy(PartialOutput):
    degree_in_sign: float | None = Field(default=None, ge=0, lt=30)
    julian_day: float | None = None
    julian_day_ut1: float | None = None
    julian_day_tt: float | None = None
    event_datetime_utc: str | None = None
    utc_representation: WesternUTCRepresentation | None = None
    longitude: float | None = Field(default=None, ge=0, lt=360)
    tropical_longitude: float | None = Field(default=None, ge=0, lt=360)
    sign: str | None = None
    type: str | None = None
    zodiac: str | None = None
    solver: SyzygySolver | None = None
    ephemeris_source: SyzygyEphemerisSource | None = None


class Temperament(PartialOutput):
    status: Literal["partial"] | None = None
    unknown_components: list[Literal["ascendant_sign", "ascendant_ruler"]] | None = None
    known_tally: dict[str, int] | None = None
    cn: str | None = None
    humor: str | None = None
    hygral: str | None = None
    tally: dict[str, int] | None = None
    thermal: str | None = None


class TopicAlmuten(PartialOutput):
    sign: str | None = None
    winner: str | None = None


class SolarConditionPolicy(PartialOutput):
    rule_id: str | None = None
    source_edition: str | None = None
    source_url: str | None = None
    printed_page: int | None = None
    cazimi_limit_exact_degrees: str | None = None
    combust_limit_degrees: float | None = None
    under_beams_limit_degrees: float | None = None
    combust_requires_same_sign: bool | None = None
    interval_policy: str | None = None
    zodiac_policy: str | None = None
    printed_example_discrepancy: str | None = None
    full_page_acceptance: bool | None = None


class Classical(PartialOutput):
    orientality_policy: OrientalityPolicy | None = None
    solar_condition_policy: SolarConditionPolicy | None = None
    obliquity: float | None = None
    source_profile: str | None = None
    ptolemy: PtolemyLayer | None = None
    almuten_figuris: AlmutenFiguris | None = None
    dispositors: Dispositors | None = None
    lots: dict[str, ClassicalLot] | None = None
    planets: dict[str, ClassicalPlanet] | None = None
    sect: str | None = None
    syzygy: Syzygy | None = None
    temperament: Temperament | None = None
    topic_almutens: dict[str, TopicAlmuten] | None = None


class Bonification(PartialOutput):
    bonified_by: list[str] | None = None
    maltreated_by: list[str] | None = None


class Overcoming(PartialOutput):
    overcome: str | None = None
    overcomer: str | None = None


class Translation(PartialOutput):
    from_: str | None = Field(default=None, alias="from")
    translator: str | None = None
    to: str | None = None


class Collection(PartialOutput):
    from_: list[str] | None = Field(default=None, alias="from")
    collector: str | None = None


class NodalBending(PartialOutput):
    planet: str | None = None
    bending: str | None = None
    orb: float | None = None


class PtolemyLatitudeCondition(PartialOutput):
    status: str | None = None
    latitude_a: float | None = None
    latitude_b: float | None = None
    source_url: str | None = None
    policy: str | None = None


class AspectMotion(PartialOutput):
    ptolemy_latitude_condition: PtolemyLatitudeCondition | None = None
    planet_a: str | None = None
    planet_b: str | None = None
    aspect: str | None = None
    exact_angle: float | None = None
    separation: float | None = None
    orb: float | None = None
    relative_longitude_speed: float | None = None
    phase: (
        Literal["applying", "separating", "exact", "stationary", "unavailable"] | None
    ) = None


class AspectApplicationPolicy(PartialOutput):
    rule_id: str | None = None
    method: str | None = None
    speed_unit: str | None = None
    scope: str | None = None
    source_url: str | None = None


class LightConfigurationPolicy(PartialOutput):
    rule_id: str | None = None
    source_edition: str | None = None
    source_url: str | None = None
    translation_definition_page: int | None = None
    collection_judgement_page: int | None = None
    weight_order: list[str] | None = None
    status: str | None = None
    full_original_text_acceptance: bool | None = None
    unverified_conditions: list[str] | None = None


class ClassicalPatterns(PartialOutput):
    light_configuration_policy: LightConfigurationPolicy | None = None
    aspect_motion: list[AspectMotion] | None = None
    application_policy: AspectApplicationPolicy | None = None
    aversions: list[list[str]] | None = None
    besiegement: dict[str, str] | None = None
    bonification: dict[str, Bonification] | None = None
    collection_of_light: list[Collection] | None = None
    nodal_bending: list[NodalBending] | None = None
    overcoming: list[Overcoming] | None = None
    sect_benefic: str | None = None
    sect_malefic: str | None = None
    translation_of_light: list[Translation] | None = None


class Hellenistic(PartialOutput):
    angular_planets: list[str] | None = None
    ascendant_ruler: str | None = None
    lot_of_fortune: ChartPoint | None = None
    sect: str | None = None


class MoiraPattern(PartialOutput):
    basis: str | None = None
    classical_acceptance: bool | None = None
    detail: str | None = None
    dsl: str | None = None
    level: str | None = None
    name: str | None = None
    source: str | None = None
    rule_id: str | None = None
    evidence: GuolaoPatternEvidence | None = None
