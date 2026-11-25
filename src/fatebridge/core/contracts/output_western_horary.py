"""Horary reading, radicality and fortitude outputs."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_chart_geometry import (
    FixedStarProfile,
    PlanetaryHours,
)
from fatebridge.core.contracts.output_midpoint_geometry import PhysicalEphemerisSource
from fatebridge.core.contracts.output_western_events import (
    LillyEventPaths,
    PlanetaryEvent,
    PlanetaryEventHistory,
)
from fatebridge.core.contracts.output_western_geometry import (
    WesternCalculationBasis,
    WesternPoint,
)
from fatebridge.core.contracts.output_western_horary_facts import (
    HoraryMoon,
    HoraryPlanet,
    HorarySignificators,
    LillyConditionalReading,
    LillyHouseAssignment,
    LillyPairReception,
    LillyRoute,
)
from fatebridge.core.contracts.output_western_timing import SystemOutput


class LillyDwellingClause(PartialOutput):
    rule_id: str | None = None
    source_url: str | None = None
    source_pages: list[int] | None = None
    quesited_occupied_house: int | None = None
    quesited_in_first_house: bool | None = None
    dwelling_alone_sufficient: bool | None = None
    distinct_lunar_transfer_actors: bool | None = None
    moon_last_contact_is_quesited: bool | None = None
    moon_next_contact_is_querent: bool | None = None
    moon_separating_from_prior_source_ray_now: bool | None = None
    moon_applying_to_next_recipient_ray_now: bool | None = None
    lunar_sequence_subconditions_satisfied: bool | None = None
    named_necessary_conditions_satisfied: bool | None = None
    prior_lunar_contact: PlanetaryEvent | None = None
    next_lunar_contact: PlanetaryEvent | None = None
    matching_p126_event_path_indexes: list[int] | None = None
    event_history_status: str | None = None
    event_history_unavailable_reason: str | None = None
    event_history_window_tt: list[float] | None = None
    event_history_completeness_scope: str | None = None
    scope: str | None = None
    conditional_reading_zh: str | None = None
    full_judgement_accepted: bool | None = None
    full_original_text_acceptance: bool | None = None


class LillyConditions(PartialOutput):
    rule_id: str | None = None
    chart_sect: str | None = None
    coordinate_scope: str | None = None
    principal_reception: LillyPairReception | None = None
    p112_mutual_reception: LillyConditionalReading | None = None
    p126_127_dwelling: LillyDwellingClause | None = None
    routes: list[LillyRoute] | None = None
    event_paths: LillyEventPaths | None = None
    same_body_not_bilateral: bool | None = None
    full_original_text_acceptance: bool | None = None
    scope: str | None = None


class HoraryPerfection(PartialOutput):
    lilly_conditions: LillyConditions | None = None
    event_history: PlanetaryEventHistory | None = None
    status: str | None = None
    missing_conditions: list[str] | None = None


class HoraryStricture(PartialOutput):
    code: str | None = None
    detail: str | None = None
    source_pages: list[int] | None = None
    status: str | None = None
    exception_satisfied: bool | None = None
    exception_applicable: bool | None = None
    attributed_variant: bool | None = None


class LillyRadicalityReportedContext(PartialOutput):
    figure_origin: str | None = None
    very_young_querent_reported: bool | None = None
    rising_description_agreement_reported: bool | None = None
    age_degree_agreement_reported: bool | None = None
    event_time_certain_reported: bool | None = None
    principal_significators_very_strong_reported: bool | None = None
    seventh_cusp_afflicted_reported: bool | None = None
    seventh_lord_impeded_reported: bool | None = None
    seventh_lord_unfortunate_reported: bool | None = None
    equal_fortune_infortune_testimonies_reported: bool | None = None
    figure_origin_source: str | None = None
    provided_fields: list[str] | None = None
    verification_scope: str | None = None


class LillyHourAffinity(PartialOutput):
    hour_ruler: str | None = None
    ascendant_sign: str | None = None
    ascendant_lord: str | None = None
    chart_sect: str | None = None
    same_ruler: bool | None = None
    ascendant_triplicity: bool | None = None
    same_own_nature: bool | None = None
    selected_triplicity_lord: str | None = None
    listed_triplicity_lords: list[str] | None = None
    hour_ruler_in_any_listed_triplicity: bool | None = None
    hour_ruler_own_nature: list[str] | None = None
    ascendant_lord_own_nature: list[str] | None = None
    supported_under_declared_policy: bool | None = None
    triplicity_policy: str | None = None
    nature_policy: str | None = None
    source_pages: list[int] | None = None
    full_original_text_acceptance: bool | None = None


class LillyRadicalityHourInputs(PartialOutput):
    status: str | None = None
    unavailable_reason: str | None = None
    hour: PlanetaryHours | None = None
    horizon_policy: str | None = None
    actual_solar_backend_verified: bool | None = None
    source_method_acceptance: bool | None = None
    epoch_jd_ut1: float | None = None
    geometric_chart_sect: str | None = None
    hour_and_geometric_sect_differ: bool | None = None
    sect_comparison_policy: str | None = None


class LillyConsideration(PartialOutput):
    code: str | None = None
    condition: str | None = None
    source_pages: list[int] | None = None
    condition_present: bool | None = None
    applicable: bool | None = None
    exception_satisfied: bool | None = None
    exception_applicable: bool | None = None
    attributed_variant: bool | None = None
    status: str | None = None
    inputs: dict[str, OpenJsonValue] | None = None
    conditional_reading_zh: str | None = None


class HoraryDegreeGate(PartialOutput):
    early: bool | None = None
    late: bool | None = None
    early_exception_satisfied: bool | None = None
    late_exception_satisfied: bool | None = None
    certain_timed_event_exception: bool | None = None


class HoraryRadicality(PartialOutput):
    method_id: str | None = None
    source_url: str | None = None
    source_pages: list[int] | None = None
    clause_count: int | None = None
    clauses: list[LillyConsideration] | None = None
    hour_inputs: LillyRadicalityHourInputs | None = None
    hour_affinity: LillyHourAffinity | None = None
    reported_context: LillyRadicalityReportedContext | None = None
    ascendant_degree_gate: HoraryDegreeGate | None = None
    unknown_clauses: list[str] | None = None
    status: str | None = None
    house_policy: str | None = None
    house_system: str | None = None
    zodiac_type: str | None = None
    source_method_scope: str | None = None
    conditional_reading_zh: str | None = None
    full_original_text_acceptance: bool | None = None
    full_judgement_accepted: bool | None = None
    real_world_prediction_established: bool | None = None
    safe_to_judge_scope: str | None = None
    safe_to_judge: bool | None = None
    strictures: list[HoraryStricture] | None = None


class LillyOrbTable(PartialOutput):
    profile_id: str | None = None
    source_url: str | None = None
    source_pages: list[int] | None = None
    full_orbs_degrees: dict[str, float] | None = None
    moieties_degrees: dict[str, float] | None = None
    available_profiles: list[str] | None = None
    pair_rule: str | None = None
    boundary_convention: str | None = None
    default_selection_basis: str | None = None
    full_original_text_acceptance: bool | None = None


class LillyFortitudeSample(PartialOutput):
    offset_days: float | None = None
    longitude: float | None = None


class LillyFortitudeMotion(PartialOutput):
    nominal_coordinate_check: str | None = None
    nominal_coordinate_roundoff_allowance_degrees: float | None = None
    direction: str | None = None
    daily_motion_degrees: float | None = None
    daily_motion_exact_degrees: str | None = None
    status: str | None = None
    samples: list[LillyFortitudeSample] | None = None
    instantaneous_speed_degrees_per_day: float | None = None
    source_model: str | None = None


class LillyFortitudeInputs(PartialOutput):
    status: str | None = None
    reason: str | None = None
    epoch_jd_tt: float | None = None
    motion: dict[str, LillyFortitudeMotion] | None = None
    north_node_longitude: float | None = None
    node_model: str | None = None
    star_longitudes: dict[str, float] | None = None
    star_position_policy: str | None = None
    daily_motion_policy: str | None = None
    day_interval_tt: list[float] | None = None
    longitude_frame: str | None = None
    physical_ephemeris_source: PhysicalEphemerisSource | None = None
    stars_profile: FixedStarProfile | None = None


class LillyFortitudeRow(PartialOutput):
    code: str | None = None
    group: str | None = None
    condition: str | None = None
    label_zh: str | None = None
    points: int | None = None
    applicable: bool | None = None
    satisfied: bool | None = None
    contribution: int | None = None
    status: str | None = None
    inputs: dict[str, OpenJsonValue] | None = None
    source_pages: list[int] | None = None


class LillyFortitudeAppliedCondition(PartialOutput):
    code: str | None = None
    label_zh: str | None = None
    contribution: int | None = None
    source_pages: list[int] | None = None


class LillyFortitudeSummary(PartialOutput):
    status: str | None = None
    known_fortitudes: int | None = None
    known_debilities: int | None = None
    known_balance: int | None = None
    literal_table_balance: int | None = None
    unknown_rows: list[str] | None = None
    applied_conditions: list[LillyFortitudeAppliedCondition] | None = None
    row_count: int | None = None
    conditional_reading_zh: str | None = None


class LillyFortitudePlanet(LillyFortitudeSummary):
    rows: list[LillyFortitudeRow] | None = None


class LillyFortitudes(PartialOutput):
    method_id: str | None = None
    source_url: str | None = None
    source_edition: str | None = None
    source_pages: list[int] | None = None
    row_count_per_planet: int | None = None
    planets: dict[str, LillyFortitudePlanet] | None = None
    summary: dict[str, LillyFortitudeSummary] | None = None
    physical_inputs: LillyFortitudeInputs | None = None
    solar_policy: dict[str, OpenJsonValue] | None = None
    zodiac_type: str | None = None
    house_system: str | None = None
    source_method_scope: str | None = None
    aggregation_policy: str | None = None
    source_conflicts: list[str] | None = None
    full_original_text_acceptance: bool | None = None
    full_judgement_accepted: bool | None = None
    real_world_prediction_established: bool | None = None


class LillyFortuneFormula(PartialOutput):
    expression: str | None = None
    reverses_at_night: bool | None = None
    ascendant: float | None = None
    sun: float | None = None
    moon: float | None = None
    uses_physical_ascendant_not_first_cusp: bool | None = None
    source_pages: list[int] | None = None
    scope: str | None = None


class LillyFortune(LillyFortitudeSummary):
    method_id: str | None = None
    source_url: str | None = None
    source_pages: list[int] | None = None
    longitude: float | None = None
    exact_longitude: str | None = None
    sign: str | None = None
    degree_in_sign: float | None = None
    formula: LillyFortuneFormula | None = None
    house_assignment: LillyHouseAssignment | None = None
    bound_lord: str | None = None
    solar_state: str | None = None
    rows: list[LillyFortitudeRow] | None = None
    source_method_scope: str | None = None
    interpretation_policies: list[str] | None = None
    full_original_text_acceptance: bool | None = None
    full_judgement_accepted: bool | None = None
    real_world_prediction_established: bool | None = None


class HoraryRuleProfile(PartialOutput):
    sign_relationship_policy: str | None = None
    radicality_policy: str | None = None
    cusp_virtue_policy: str | None = None
    fortune_policy: str | None = None
    fortitudes_policy: str | None = None
    orb_table: LillyOrbTable | None = None
    house_axis_policy: str | None = None
    essential_dignity_policy: str | None = None
    rule_id: str | None = None
    source_edition: str | None = None
    source_url: str | None = None
    chapter_pages: list[int] | None = None
    full_original_text_acceptance: bool | None = None
    instantaneous_phase: str | None = None
    orb_policy: str | None = None
    moon_policy: str | None = None
    judgement_status: str | None = None


class Horary(SystemOutput):
    reference_geometry: dict[str, OpenJsonValue] | None = None
    backend_convention: dict[str, OpenJsonValue] | None = None
    fortune: LillyFortune | None = None
    fortitudes: LillyFortitudes | None = None
    calculation_basis: WesternCalculationBasis | None = None
    rule_profile: HoraryRuleProfile | None = None
    category: str | None = None
    category_label: str | None = None
    ascendant: WesternPoint | None = None
    moon: HoraryMoon | None = None
    significators: HorarySignificators | None = None
    planets: dict[str, HoraryPlanet] | None = None
    perfection: HoraryPerfection | None = None
    quesited_house: int | None = None
    radicality: HoraryRadicality | None = None
