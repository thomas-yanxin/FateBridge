"""Sukuyo mansions, daily references and relationships."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_guolao import GuolaoBoundary, GuolaoMansion
from fatebridge.core.contracts.output_sukuyo_activities import (
    SukuyoActivityAssessment,
    SukuyoConjunctionDoctrine,
    SukuyoDirectionalTravel,
    SukuyoLowerMansion,
    SukuyoLowerMethods,
    SukuyoSpecialDays,
)
from fatebridge.core.contracts.output_sukuyo_calendar import (
    SukuyoCalendar,
    SukuyoCalendarDay,
)


class SukuyoPalace(PartialOutput):
    ordinal: int | None = None
    name: str | None = None
    literal_name: str | None = None
    ruler_literal: str | None = None
    ruler_luminary: str | None = None
    division: str | None = None
    locator: str | None = None
    textual_variants: list[dict[str, OpenJsonValue]] | None = None


class SukuyoPadaCell(PartialOutput):
    mansion: str | None = None
    pada: int | None = None
    palace_ordinal: int | None = None
    palace_name: str | None = None
    ruler_luminary: str | None = None
    locator: str | None = None


class SukuyoPalaceReference(PartialOutput):
    ruleset_id: str | None = None
    status: str | None = None
    basis: str | None = None
    mansion: str | None = None
    mansion_candidates: list[str] | None = None
    textual_pada: int | None = None
    candidate_set_complete_within_calendar_profile: bool | None = None
    selected_palace: SukuyoPalace | None = None
    candidate_palaces: list[SukuyoPalace] | None = None
    rows: list[SukuyoPadaCell] | None = None
    pada_numbering_basis: str | None = None
    pada_ordinals_explicit_in_source: bool | None = None
    source_url: str | None = None
    locator: str | None = None
    applied_to_calendar_mansion: bool | None = None
    applied_to_sanjiu: bool | None = None
    applied_to_modern_chart: bool | None = None
    birth_pada_established: bool | None = None
    physical_longitude_status: str | None = None
    scope: str | None = None


class SukuyoSanjiuDayWitness(PartialOutput):
    volume: str | None = None
    source_witness: str | None = None
    locator: str | None = None
    source_excerpts: list[str] | None = None
    meaning: str | None = None
    primary_paragraph_id: str | None = None


class SukuyoSanjiuDayEvidence(PartialOutput):
    ruleset_id: str | None = None
    relation: str | None = None
    source_url: str | None = None
    witnesses: list[SukuyoSanjiuDayWitness] | None = None
    upper_day_entry_individually_listed: bool | None = None
    priority_clause: SukuyoSanjiuDayWitness | None = None
    priority_clause_applied_to_aggregate: bool | None = None
    scope: str | None = None


class SukuyoPersonalDay(PartialOutput):
    relation: dict[str, OpenJsonValue] | None = None
    source_day_evidence: SukuyoSanjiuDayEvidence | None = None
    upper_volume: dict[str, OpenJsonValue] | None = None
    textual_conflict: bool | None = None
    lower_volume_variant: dict[str, OpenJsonValue] | None = None
    scope: str | None = None


class SukuyoSixPalaceMember(PartialOutput):
    name: str | None = None
    inclusive_ordinal: int | None = None
    mansion: str | None = None
    locator: str | None = None


class SukuyoJointReadingRequirement(PartialOutput):
    source_excerpt: str | None = None
    locator: str | None = None
    evaluated: bool | None = None


class SukuyoSixPalaceReference(PartialOutput):
    ruleset_id: str | None = None
    status: str | None = None
    natal_mansion: str | None = None
    members: list[SukuyoSixPalaceMember] | None = None
    counting_basis: str | None = None
    source_url: str | None = None
    locator: str | None = None
    counting_excerpt: str | None = None
    joint_reading_requirement: SukuyoJointReadingRequirement | None = None
    seven_luminary_transits_evaluated: bool | None = None
    applied_to_day_assessment: bool | None = None
    scope: str | None = None


class SukuyoTaibaiWitness(PartialOutput):
    witness: str | None = None
    status: str | None = None
    location: str | None = None
    horizontal_direction: str | None = None
    realm: str | None = None
    source_excerpt: str | None = None
    locator: str | None = None
    reading_complete_for_selected_day: bool | None = None
    applied_to_primary: bool | None = None


class SukuyoTaibaiReference(PartialOutput):
    ruleset_id: str | None = None
    status: str | None = None
    lunar_day: int | None = None
    selected_witness: str | None = None
    location: str | None = None
    horizontal_direction: str | None = None
    realm: str | None = None
    row_id: str | None = None
    row_lunar_days: list[int] | None = None
    witnesses: list[SukuyoTaibaiWitness] | None = None
    witnesses_agree_for_selected_day: bool | None = None
    title_literal: str | None = None
    table_apparatus: list[dict[str, OpenJsonValue]] | None = None
    source_url: str | None = None
    locator: str | None = None
    publisher_primary: dict[str, OpenJsonValue] | None = None
    doctrine: dict[str, OpenJsonValue] | None = None
    physical_venus_position_evaluated: bool | None = None
    astronomical_retrograde_evaluated: bool | None = None
    movement_alignment_evaluated: bool | None = None
    applied_to_activity_assessment: bool | None = None
    independent_ming_edition_collated: bool | None = None
    scope: str | None = None


class SukuyoClothingVerse(PartialOutput):
    mansion: str | None = None
    literal_mansion: str | None = None
    taisho_text: str | None = None
    ming_apparatus_text: str | None = None
    locator: str | None = None


class SukuyoClothingWitness(PartialOutput):
    witness: str | None = None
    membership: str | None = None
    assessment: str | None = None
    source_excerpt: str | None = None
    applied_to_primary: bool | None = None
    unlisted_complement_assessment: str | None = None


class SukuyoClothingCandidate(PartialOutput):
    mansion: str | None = None
    verse: SukuyoClothingVerse | None = None
    upper_literal_cutting_statement: dict[str, OpenJsonValue] | None = None
    primary_assessment: str | None = None
    comparisons: list[SukuyoClothingWitness] | None = None


class SukuyoClothingReference(PartialOutput):
    ruleset_id: str | None = None
    status: str | None = None
    mansion: str | None = None
    candidate_mansions: list[str] | None = None
    candidate_set_complete_under_declared_profile: bool | None = None
    primary_assessment: str | None = None
    selected_witness: str | None = None
    candidate_references: list[SukuyoClothingCandidate] | None = None
    primary_positive_mansions: list[str] | None = None
    ming_literal_list: list[str] | None = None
    ming_unresolved_tokens: list[str] | None = None
    ming_unlisted_complement_assessment: str | None = None
    verse_and_literal_forecasts_applied_to_aggregate: bool | None = None
    independent_ming_edition_collated: bool | None = None
    historical_clock_mapping_evaluated: bool | None = None
    source_url: str | None = None
    locator: str | None = None
    unmapped_clothing_predicates: list[dict[str, OpenJsonValue]] | None = None
    scope: str | None = None


class SukuyoDay(PartialOutput):
    kenyu_lingbi_reference: dict[str, OpenJsonValue] | None = None
    clothing_reference: SukuyoClothingReference | None = None
    calendar: SukuyoCalendar | None = None
    calendar_day: SukuyoCalendarDay | None = None
    day_mansion: str | None = None
    nature: str | None = None
    lunar_half: str | None = None
    half_day: int | None = None
    weekday: dict[str, OpenJsonValue] | None = None
    special_day_labels: list[str] | None = None
    special_day_evidence: SukuyoSpecialDays | None = None
    rule_trace: list[dict[str, OpenJsonValue]] | None = None
    personal_day: SukuyoPersonalDay | None = None
    six_palace_reference: SukuyoSixPalaceReference | None = None
    taibai_direction_reference: SukuyoTaibaiReference | None = None
    activity_assessment: SukuyoActivityAssessment | None = None
    lower_mansion_day: SukuyoLowerMansion | None = None
    lower_methods: SukuyoLowerMethods | None = None
    directional_travel: SukuyoDirectionalTravel | None = None
    conjunction_doctrine: SukuyoConjunctionDoctrine | None = None
    palace_reference: SukuyoPalaceReference | None = None
    reading_text: str | None = None
    candidate_days: list[dict[str, OpenJsonValue]] | None = None
    candidate_mansion_days: list[dict[str, OpenJsonValue]] | None = None


class SuzhanAstronomyBody(PartialOutput):
    id: str | None = None
    longitude: float | None = None
    latitude: float | None = None
    right_ascension: float | None = None
    declination: float | None = None
    mansion: GuolaoMansion | None = None


class SuzhanAstronomy(PartialOutput):
    method_id: str | None = None
    coordinate_frame: str | None = None
    julian_day_tt: float | None = None
    julian_day_ut1: float | None = None
    utc_datetime: str | None = None
    bodies: list[SuzhanAstronomyBody] | None = None
    boundaries: list[GuolaoBoundary] | None = None
    classical_boundary_acceptance: bool | None = None


class SukuyoPerson(PartialOutput):
    name: str | None = None
    natal_su27: str | None = None
    calendar: SukuyoCalendar | None = None
    palace_reference: SukuyoPalaceReference | None = None


class SukuyoRelation(PartialOutput):
    relation: str | None = None
    pair: str | None = None
    distance: str | None = None
    meaning: str | None = None
    self_su27: str | None = None
    other_su27: str | None = None
    offset: int | None = None
    sequence_group: int | None = None
    traditional_assessment: str | None = None
    rule_trace: list[dict[str, OpenJsonValue]] | None = None


class SukuyoJointPersonSupport(PartialOutput):
    calendar_date: str | None = None
    calendar_day_part: str | None = None
    natal_su27: str | None = None
    assignment_origin: str | None = None


class SukuyoJointSupport(PartialOutput):
    reconstruction_id: str | None = None
    person1: SukuyoJointPersonSupport | None = None
    person2: SukuyoJointPersonSupport | None = None


class SukuyoSharedReconstruction(PartialOutput):
    method_id: str | None = None
    status: str | None = None
    model_ids: list[str] | None = None
    model_identity: dict[str, OpenJsonValue] | None = None
    assumption: str | None = None
    person_half_days_independent: bool | None = None
    source_priority_established: bool | None = None
    historical_uniformity_established: bool | None = None
    unconstrained_row_count: int | None = None
    supported_row_count: int | None = None
    unsupported_row_count: int | None = None
    support_coverage_complete: bool | None = None
    resolved_support: list[SukuyoJointSupport] | None = None
    reason: str | None = None


class SukuyoCandidateRelation(PartialOutput):
    person1_su27: str | None = None
    person2_su27: str | None = None
    person1_to_person2: SukuyoRelation | None = None
    person2_to_person1: SukuyoRelation | None = None
    pair: str | None = None
    applied_to_primary: bool | None = None
    person1_calendar_dates: list[str] | None = None
    person2_calendar_dates: list[str] | None = None
    shared_reconstruction_ids: list[str] | None = None
    joint_support_status: str | None = None
    joint_support: list[SukuyoJointSupport] | None = None


class SukuyoCandidateAnalysis(PartialOutput):
    status: str | None = None
    candidate_set_complete_within_profile: bool | None = None
    rows: list[SukuyoCandidateRelation] | None = None
    scope: str | None = None
    calendar_date_uncertainty_remains: bool | None = None
    unconstrained_rows: list[SukuyoCandidateRelation] | None = None
    shared_reconstruction_analysis: SukuyoSharedReconstruction | None = None
