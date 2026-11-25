"""Projection-compatible nested public contracts for the Indian subset."""

from pydantic import Field, JsonValue

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_ephemeris import (
    ApparentPositionPolicy,
    NativeCoordinateContext,
    NativeExecutionContext,
    SolarEphemerisReference,
    SolarPositionBody,
)
from fatebridge.core.contracts.output_rotation import EarthRotationPolicy

Object = dict[str, JsonValue]


class JyotishDignity(PartialOutput):
    state: str | None = None
    own_sign: bool | None = None
    rule_id: str | None = None
    scope: str | None = None


class JyotishPoint(PartialOutput):
    id: str | None = None
    label_zh: str | None = None
    longitude: float | None = None
    sign: str | None = None
    sign_zh: str | None = None
    degree_in_sign: float | None = None
    house: int | None = None
    dignity: JyotishDignity | None = None
    physical_state: Object | None = None
    native_position_interpretation: SolarPositionBody | None = None
    dispositor_relationship: Object | None = None


class JyotishHouse(PartialOutput):
    house: int | None = None
    sign: str | None = None
    lord: str | None = None
    lord_house: int | None = None
    lord_dignity: JyotishDignity | None = None
    occupants: list[str] | None = None


class GrahaAspect(PartialOutput):
    from_planet: str | None = None
    from_house: int | None = None
    distance: int | None = None
    target_house: int | None = None
    target_planets: list[str] | None = None
    rule_id: str | None = None


class VargaChart(PartialOutput):
    division: int | None = None
    method: str | None = None
    coordinate_scope: str | None = None
    ascendant: JyotishPoint | None = None
    planets: list[JyotishPoint] | None = None
    houses: list[JyotishHouse] | None = None
    graha_aspects: list[GrahaAspect] | None = None
    rule_ids: list[str] | None = None


class VargaCharts(PartialOutput):
    D1: VargaChart | None = None
    D2: VargaChart | None = None
    D3: VargaChart | None = None
    D4: VargaChart | None = None
    D7: VargaChart | None = None
    D9: VargaChart | None = None
    D10: VargaChart | None = None
    D12: VargaChart | None = None
    D16: VargaChart | None = None
    D20: VargaChart | None = None
    D24: VargaChart | None = None
    D27: VargaChart | None = None
    D30: VargaChart | None = None
    D40: VargaChart | None = None
    D45: VargaChart | None = None
    D60: VargaChart | None = None


class Nakshatra(PartialOutput):
    index: int | None = None
    name: str | None = None
    lord: str | None = None
    pada: int | None = None
    fraction_elapsed: float | None = None


class JyotishProfile(PartialOutput):
    engine: str | None = None
    native_execution_context: NativeExecutionContext | None = None
    native_coordinate_contexts: dict[str, NativeCoordinateContext] | None = None
    apparent_position_policy: ApparentPositionPolicy | None = None
    earth_rotation: EarthRotationPolicy | None = None
    local_apparent_sidereal_meridian_degrees: float | None = Field(
        default=None,
        ge=0,
        lt=360,
        description="Local apparent sidereal meridian in right-ascension degrees, not the ecliptic MC longitude.",
    )
    ephemeris_model: str | None = None
    zodiac: str | None = None
    ayanamsha_id: str | None = None
    position_method: str | None = None
    house_system: str | None = None
    node_mode: str | None = None
    swisseph_version: str | None = None
    ephemeris_models: list[str] | None = None
    ephemeris_model_scope: str | None = None
    physical_backend_policy: str | None = None
    ephemeris_by_body: dict[str, str] | None = None
    nonphysical_factor_models: dict[str, str] | None = None
    native_node_return_flags: dict[str, int] | None = None
    ephemeris_quality: Object | None = None
    julian_day_ut: float | None = None
    julian_day_tt: float | None = None
    julian_day_utc: float | None = None
    time_scale_context: Object | None = None
    time_conversion: str | None = None
    clock: str | None = None
    clock_context: Object | None = None
    ruleset_id: str | None = None
    saptavargaja_profile: str | None = None
    drekkana_profile: str | None = None
    cheshta_model: str | None = None


class SthanaValues(PartialOutput):
    uchcha_bala: float | None = None
    saptavargaja_bala: float | None = None
    ojayugma_bala: float | None = None
    kendradi_bala: float | None = None
    drekkana_bala: float | None = None
    total_virupa: float | None = None
    total_rupa: float | None = None


class SthanaBala(PartialOutput):
    status: str | None = None
    profile: Object | None = None
    unit: str | None = None
    components: list[str] | None = None
    summary: dict[str, SthanaValues] | None = None
    evidence: dict[str, Object] | None = None
    profile_comparison: Object | None = None
    drekkana_profile_comparison: Object | None = None
    source_reading_conflicts: list[Object] | None = None
    comparison_scope: str | None = None
    excluded_points: list[str] | None = None
    remaining_shadbala: list[str] | None = None
    shadbala_status: str | None = None
    rule_ids: list[str] | None = None
    interpretation_scope: str | None = None


class BalaComponent(PartialOutput):
    status: str | None = None
    method: str | None = None
    unit: str | None = None
    source_id: str | None = None
    source_section: str | None = None
    summary: dict[str, float | None] | None = None
    evidence: dict[str, Object] | None = None
    basis: Object | None = None
    rule_ids: list[str] | None = None
    interpretation_scope: str | None = None


class ConditionalDrik(BalaComponent):
    conditional_targets: list[str] | None = None
    scenarios: dict[str, Object] | None = None
    matrix: dict[str, dict[str, float]] | None = None
    nature_context: Object | None = None
    calculation_scope: str | None = None
    endpoint_convention: str | None = None
    source_disagreements: list[str] | None = None
    source_witness: Object | None = None
    source_reading_conflicts: list[Object] | None = None
    alternative_source_witnesses: dict[str, Object] | None = None


class SupportingSolarEvent(PartialOutput):
    kind: str | None = None
    julian_day_ut1: float | None = None
    julian_day_tt: float | None = None
    ephemeris_model: str | None = None


class SolarNoEventSearch(PartialOutput):
    search_jd_ut1: float | None = None
    kind: str | None = None


class SolarEventEnumeration(PartialOutput):
    method: str | None = None
    partition_hours: float | None = None
    scope: str | None = None


class SupportingSolarEvents(PartialOutput):
    events: list[SupportingSolarEvent] | None = None
    ephemeris_policy: str | None = None
    ephemeris_models: list[str] | None = None
    ephemeris_sources: dict[str, SolarEphemerisReference] | None = None
    ephemeris_source_policy: str | None = None
    no_event_searches: list[SolarNoEventSearch] | None = None
    search_start_jd_ut1: float | None = None
    search_end_jd_ut1: float | None = None
    enumeration: SolarEventEnumeration | None = None
    definition: str | None = None
    event_model: str | None = None
    equatorial_frame: str | None = None
    search_window_hours: float | None = None
    scope: str | None = None


class TemporalBala(BalaComponent):
    arithmetic_policy: str | None = None
    conditional_targets: list[str] | None = None
    model_context: Object | None = None
    temporal_scope: str | None = None
    components: dict[str, Object] | None = None
    scenarios: dict[str, Object] | None = None
    missing_components: list[str] | None = None
    missing_planets: list[str] | None = None
    calendar_context: Object | None = None
    solar_context: Object | None = None
    solar_events: SupportingSolarEvents | None = None
    source_disagreements: list[str] | None = None


class ShadbalaAssessment(PartialOutput):
    status: str | None = None
    computed: list[str] | None = None
    conditional: list[str] | None = None
    partial: list[str] | None = None
    missing: list[str] | None = None
    total_virupa: float | None = None
    scope: str | None = None


class JyotishStrengths(PartialOutput):
    sthana_bala: SthanaBala | None = None
    dig_bala: BalaComponent | None = None
    naisargika_bala: BalaComponent | None = None
    drik_bala: ConditionalDrik | None = None
    kala_bala: TemporalBala | None = None
    cheshta_bala: TemporalBala | None = None
    shadbala_assessment: ShadbalaAssessment | None = None


class PindaRow(PartialOutput):
    status: str | None = None
    trikona: list[int] | None = None
    sodhita: list[int | None] | None = None
    trikona_steps: list[Object] | None = None
    coowned_steps: list[Object] | None = None
    source_ambiguities: list[Object] | None = None
    rasi_multipliers: list[int] | None = None
    rasi_terms: list[int | None] | None = None
    graha_terms: list[Object] | None = None
    rasi_pinda: int | None = None
    graha_pinda: int | None = None
    sodhya_pinda: int | None = None


class AiyarReductionRow(PartialOutput):
    method_id: str | None = None
    source_id: str | None = None
    status: str | None = None
    occupied_sign_indices: list[int] | None = None
    trikona: list[int] | None = None
    sodhita: list[int] | None = None
    reduced_sum: int | None = None
    trikona_steps: list[Object] | None = None
    coowned_steps: list[Object] | None = None
    scope: str | None = None


class AiyarReductionComparison(PartialOutput):
    method_id: str | None = None
    source_id: str | None = None
    source_section: str | None = None
    rule_ids: list[str] | None = None
    input_sign_indices: dict[str, int] | None = None
    targets: dict[str, AiyarReductionRow] | None = None
    rao_default_replaced: bool | None = None
    input_scope: str | None = None
    interpretation_scope: str | None = None


class PindaAnalysis(PartialOutput):
    status: str | None = None
    method_id: str | None = None
    source_id: str | None = None
    source_section: str | None = None
    rule_ids: list[str] | None = None
    occupancy_planets: list[str] | None = None
    input_sign_indices: dict[str, int] | None = None
    input_bhinna_totals: dict[str, int] | None = None
    targets: dict[str, PindaRow] | None = None
    source_profile_comparison: dict[str, AiyarReductionComparison] | None = None
    unreduced_tables_preserved: bool | None = None
    assumptions: list[str] | None = None
    interpretation_scope: str | None = None
    basis_bhinna_rule_id: str | None = None
    bhinna_fact_path: str | None = None


class BavSourceDifference(PartialOutput):
    default_source_id: str | None = None
    same_input_sign_indices: bool | None = None
    bhinna_different_sign_indices: dict[str, list[int]] | None = None
    samudaya_different_sign_indices: list[int] | None = None
    scope: str | None = None


class AiyarBavProfile(PartialOutput):
    status: str | None = None
    method_id: str | None = None
    source_id: str | None = None
    source_section: str | None = None
    rule_ids: list[str] | None = None
    input_sign_indices: dict[str, int] | None = None
    contributor_order: list[str] | None = None
    target_order: list[str] | None = None
    samudaya_targets: list[str] | None = None
    prastara: dict[str, dict[str, list[int]]] | None = None
    bhinna: dict[str, list[int]] | None = None
    samudaya: list[int] | None = None
    bhinna_totals: dict[str, int] | None = None
    samudaya_total: int | None = None
    notation: Object | None = None
    reductions_applied: bool | None = None
    reduction_analysis: AiyarReductionComparison | None = None
    comparison_to_default: BavSourceDifference | None = None
    chart_method: str | None = None
    chart_rule_ids: list[str] | None = None
    input_claims: list[Object] | None = None
    interpretation_scope: str | None = None


class AshtakavargaChart(PartialOutput):
    input_sign_indices: dict[str, int] | None = None
    prastara: dict[str, dict[str, list[int]]] | None = None
    bhinna: dict[str, list[int]] | None = None
    samudaya: list[int] | None = None
    bhinna_totals: dict[str, int] | None = None
    samudaya_total: int | None = None
    chart_method: str | None = None
    chart_rule_ids: list[str] | None = None
    input_claims: list[Object] | None = None
    reduction_analysis: PindaAnalysis | None = None
    source_profile_comparison: dict[str, AiyarBavProfile] | None = None


class Ashtakavarga(PartialOutput):
    status: str | None = None
    method_id: str | None = None
    source_id: str | None = None
    source_section: str | None = None
    rule_ids: list[str] | None = None
    reference_instant: str | None = None
    sign_order: list[str] | None = None
    contributor_order: list[str] | None = None
    target_order: list[str] | None = None
    samudaya_targets: list[str] | None = None
    notation: Object | None = None
    reductions_applied: bool | None = None
    charts: dict[str, AshtakavargaChart] | None = None
    not_computed: list[str] | None = None
    interpretation_scope: str | None = None


class JyotishIndia(PartialOutput):
    reading_basis: Object | None = None
    ayanamsha: float | None = None
    moon_nakshatra: str | None = None
    rising_nakshatra: str | None = None
    status: str | None = None
    ruleset_id: str | None = None
    profile: JyotishProfile | None = None
    panchanga: Object | None = None
    nakshatras: dict[str, Nakshatra] | None = None
    charts: VargaCharts | None = None
    strengths: JyotishStrengths | None = None
    ashtakavarga: Ashtakavarga | None = None
    topic_evidence: dict[str, Object] | None = None
    birth_time_sensitivity: Object | None = None
    rulesets: list[Object] | None = None
    rule_trace: list[Object] | None = None
    coverage: dict[str, list[str]] | None = None
    interpretation_scope: str | None = None


class DashaPeriod(PartialOutput):
    lord: str | None = None
    major_lord: str | None = None
    start: str | None = None
    end: str | None = None
    duration_years: float | None = None


class Mahadasha(DashaPeriod):
    antardashas: list[DashaPeriod] | None = None


class DashaLevel(DashaPeriod):
    level: int | None = None
    name: str | None = None
    abbreviation: str | None = None
    lord_chain: list[str] | None = None
    duration_years_fraction: list[int] | None = None


class DashaSiblings(PartialOutput):
    level: int | None = None
    parent_lord_chain: list[str] | None = None
    periods: list[DashaLevel] | None = None


class DashaExactFraction(PartialOutput):
    numerator: str | None = Field(default=None, pattern=r"^-?(0|[1-9][0-9]*)$")
    denominator: str | None = Field(default=None, pattern=r"^[1-9][0-9]*$")


class DashaEpochContext(PartialOutput):
    reference_epoch_utc: str | None = None
    complete_major_start_offset_microseconds_fraction: DashaExactFraction | None = None
    quantization_method_id: str | None = None
    source_id: str | None = None


class DashaTimeQuantization(PartialOutput):
    method_id: str | None = None
    source_id: str | None = None
    reference_epoch_utc: str | None = None
    source_mansion_fraction_exact: DashaExactFraction | None = None
    year_microseconds: int | None = None
    quantum_microseconds: int | None = None
    rounding: str | None = None
    scope: str | None = None


class DashaSubdivisions(PartialOutput):
    method_id: str | None = None
    depth: int | None = None
    source_id: str | None = None
    rule_ids: list[str] | None = None
    current_levels: list[DashaLevel] | None = None
    siblings_by_level: list[DashaSiblings] | None = None
    year_basis: str | None = None
    rounding_policy: str | None = None
    epoch_context: DashaEpochContext | None = None
    scope: str | None = None


class DashaSeed(Nakshatra):
    moon_longitude: float | None = None


class DashaBirthBalance(PartialOutput):
    lord: str | None = None
    elapsed_years: float | None = None
    remaining_years: float | None = None
    elapsed_microseconds: int | None = None
    remaining_microseconds: int | None = None
    major_start: str | None = None
    major_end: str | None = None


class Vimshottari(PartialOutput):
    method_id: str | None = None
    year_basis: str | None = None
    year_days: float | None = None
    analysis_datetime: str | None = None
    boundary_convention: str | None = None
    elapsed_time_convention: str | None = None
    time_quantization: DashaTimeQuantization | None = None
    seed: DashaSeed | None = None
    birth_balance: DashaBirthBalance | None = None
    current_major: DashaPeriod | None = None
    current_sub: DashaPeriod | None = None
    subdivisions: DashaSubdivisions | None = None
    timeline: list[Mahadasha] | None = None
    timeline_scope: Object | None = None
    birth_time_sensitivity: Object | None = None
    natal_ruler_context: list[Object] | None = None
    rule_ids: list[str] | None = None
    interpretation_scope: str | None = None
