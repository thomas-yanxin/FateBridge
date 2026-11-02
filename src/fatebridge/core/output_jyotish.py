"""Projection-compatible nested public contracts for the Indian subset."""

from typing import Dict, List, Optional

from pydantic import Field, JsonValue

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_ephemeris import (
    ApparentPositionPolicy,
    NativeCoordinateContext,
    NativeExecutionContext,
    SolarPositionBody,
)
from fatebridge.core.output_rotation import EarthRotationPolicy

Object = Dict[str, JsonValue]


class JyotishDignity(PartialOutput):
    state: Optional[str] = None
    own_sign: Optional[bool] = None
    rule_id: Optional[str] = None
    scope: Optional[str] = None


class JyotishPoint(PartialOutput):
    id: Optional[str] = None
    label_zh: Optional[str] = None
    longitude: Optional[float] = None
    sign: Optional[str] = None
    sign_zh: Optional[str] = None
    degree_in_sign: Optional[float] = None
    house: Optional[int] = None
    dignity: Optional[JyotishDignity] = None
    physical_state: Optional[Object] = None
    native_position_interpretation: Optional[SolarPositionBody] = None
    dispositor_relationship: Optional[Object] = None


class JyotishHouse(PartialOutput):
    house: Optional[int] = None
    sign: Optional[str] = None
    lord: Optional[str] = None
    lord_house: Optional[int] = None
    lord_dignity: Optional[JyotishDignity] = None
    occupants: Optional[List[str]] = None


class GrahaAspect(PartialOutput):
    from_planet: Optional[str] = None
    from_house: Optional[int] = None
    distance: Optional[int] = None
    target_house: Optional[int] = None
    target_planets: Optional[List[str]] = None
    rule_id: Optional[str] = None


class VargaChart(PartialOutput):
    division: Optional[int] = None
    method: Optional[str] = None
    coordinate_scope: Optional[str] = None
    ascendant: Optional[JyotishPoint] = None
    planets: Optional[List[JyotishPoint]] = None
    houses: Optional[List[JyotishHouse]] = None
    graha_aspects: Optional[List[GrahaAspect]] = None
    rule_ids: Optional[List[str]] = None


class VargaCharts(PartialOutput):
    D1: Optional[VargaChart] = None
    D2: Optional[VargaChart] = None
    D3: Optional[VargaChart] = None
    D7: Optional[VargaChart] = None
    D9: Optional[VargaChart] = None
    D10: Optional[VargaChart] = None
    D12: Optional[VargaChart] = None
    D30: Optional[VargaChart] = None


class Nakshatra(PartialOutput):
    index: Optional[int] = None
    name: Optional[str] = None
    lord: Optional[str] = None
    pada: Optional[int] = None
    fraction_elapsed: Optional[float] = None


class JyotishProfile(PartialOutput):
    engine: Optional[str] = None
    native_execution_context: Optional[NativeExecutionContext] = None
    native_coordinate_contexts: Optional[Dict[str, NativeCoordinateContext]] = None
    apparent_position_policy: Optional[ApparentPositionPolicy] = None
    earth_rotation: Optional[EarthRotationPolicy] = None
    local_apparent_sidereal_meridian_degrees: Optional[float] = Field(
        default=None,
        ge=0,
        lt=360,
        description="Local apparent sidereal meridian in right-ascension degrees, not the ecliptic MC longitude.",
    )
    ephemeris_model: Optional[str] = None
    zodiac: Optional[str] = None
    ayanamsha_id: Optional[str] = None
    position_method: Optional[str] = None
    house_system: Optional[str] = None
    node_mode: Optional[str] = None
    swisseph_version: Optional[str] = None
    ephemeris_models: Optional[List[str]] = None
    ephemeris_model_scope: Optional[str] = None
    physical_backend_policy: Optional[str] = None
    ephemeris_by_body: Optional[Dict[str, str]] = None
    nonphysical_factor_models: Optional[Dict[str, str]] = None
    native_node_return_flags: Optional[Dict[str, int]] = None
    ephemeris_quality: Optional[Object] = None
    julian_day_ut: Optional[float] = None
    julian_day_tt: Optional[float] = None
    julian_day_utc: Optional[float] = None
    time_scale_context: Optional[Object] = None
    time_conversion: Optional[str] = None
    clock: Optional[str] = None
    clock_context: Optional[Object] = None
    ruleset_id: Optional[str] = None
    saptavargaja_profile: Optional[str] = None
    drekkana_profile: Optional[str] = None
    cheshta_model: Optional[str] = None


class SthanaValues(PartialOutput):
    uchcha_bala: Optional[float] = None
    saptavargaja_bala: Optional[float] = None
    ojayugma_bala: Optional[float] = None
    kendradi_bala: Optional[float] = None
    drekkana_bala: Optional[float] = None
    total_virupa: Optional[float] = None
    total_rupa: Optional[float] = None


class SthanaBala(PartialOutput):
    status: Optional[str] = None
    profile: Optional[Object] = None
    unit: Optional[str] = None
    components: Optional[List[str]] = None
    summary: Optional[Dict[str, SthanaValues]] = None
    evidence: Optional[Dict[str, Object]] = None
    profile_comparison: Optional[Object] = None
    drekkana_profile_comparison: Optional[Object] = None
    source_reading_conflicts: Optional[List[Object]] = None
    comparison_scope: Optional[str] = None
    excluded_points: Optional[List[str]] = None
    remaining_shadbala: Optional[List[str]] = None
    shadbala_status: Optional[str] = None
    rule_ids: Optional[List[str]] = None
    interpretation_scope: Optional[str] = None


class BalaComponent(PartialOutput):
    status: Optional[str] = None
    method: Optional[str] = None
    unit: Optional[str] = None
    source_id: Optional[str] = None
    source_section: Optional[str] = None
    summary: Optional[Dict[str, Optional[float]]] = None
    evidence: Optional[Dict[str, Object]] = None
    basis: Optional[Object] = None
    rule_ids: Optional[List[str]] = None
    interpretation_scope: Optional[str] = None


class ConditionalDrik(BalaComponent):
    conditional_targets: Optional[List[str]] = None
    scenarios: Optional[Dict[str, Object]] = None
    matrix: Optional[Dict[str, Dict[str, float]]] = None
    nature_context: Optional[Object] = None
    calculation_scope: Optional[str] = None
    endpoint_convention: Optional[str] = None
    source_disagreements: Optional[List[str]] = None
    source_witness: Optional[Object] = None
    source_reading_conflicts: Optional[List[Object]] = None
    alternative_source_witnesses: Optional[Dict[str, Object]] = None


class TemporalBala(BalaComponent):
    model_context: Optional[Object] = None
    temporal_scope: Optional[str] = None
    components: Optional[Dict[str, Object]] = None
    scenarios: Optional[Dict[str, Object]] = None
    missing_components: Optional[List[str]] = None
    missing_planets: Optional[List[str]] = None
    calendar_context: Optional[Object] = None
    solar_context: Optional[Object] = None
    solar_events: Optional[Object] = None
    source_disagreements: Optional[List[str]] = None


class ShadbalaAssessment(PartialOutput):
    status: Optional[str] = None
    computed: Optional[List[str]] = None
    conditional: Optional[List[str]] = None
    partial: Optional[List[str]] = None
    missing: Optional[List[str]] = None
    total_virupa: Optional[float] = None
    scope: Optional[str] = None


class JyotishStrengths(PartialOutput):
    sthana_bala: Optional[SthanaBala] = None
    dig_bala: Optional[BalaComponent] = None
    naisargika_bala: Optional[BalaComponent] = None
    drik_bala: Optional[ConditionalDrik] = None
    kala_bala: Optional[TemporalBala] = None
    cheshta_bala: Optional[TemporalBala] = None
    shadbala_assessment: Optional[ShadbalaAssessment] = None


class PindaRow(PartialOutput):
    status: Optional[str] = None
    trikona: Optional[List[int]] = None
    sodhita: Optional[List[Optional[int]]] = None
    trikona_steps: Optional[List[Object]] = None
    coowned_steps: Optional[List[Object]] = None
    source_ambiguities: Optional[List[Object]] = None
    rasi_multipliers: Optional[List[int]] = None
    rasi_terms: Optional[List[Optional[int]]] = None
    graha_terms: Optional[List[Object]] = None
    rasi_pinda: Optional[int] = None
    graha_pinda: Optional[int] = None
    sodhya_pinda: Optional[int] = None


class AiyarReductionRow(PartialOutput):
    method_id: Optional[str] = None
    source_id: Optional[str] = None
    status: Optional[str] = None
    occupied_sign_indices: Optional[List[int]] = None
    trikona: Optional[List[int]] = None
    sodhita: Optional[List[int]] = None
    reduced_sum: Optional[int] = None
    trikona_steps: Optional[List[Object]] = None
    coowned_steps: Optional[List[Object]] = None
    scope: Optional[str] = None


class AiyarReductionComparison(PartialOutput):
    method_id: Optional[str] = None
    source_id: Optional[str] = None
    source_section: Optional[str] = None
    rule_ids: Optional[List[str]] = None
    input_sign_indices: Optional[Dict[str, int]] = None
    targets: Optional[Dict[str, AiyarReductionRow]] = None
    rao_default_replaced: Optional[bool] = None
    input_scope: Optional[str] = None
    interpretation_scope: Optional[str] = None


class PindaAnalysis(PartialOutput):
    status: Optional[str] = None
    method_id: Optional[str] = None
    source_id: Optional[str] = None
    source_section: Optional[str] = None
    rule_ids: Optional[List[str]] = None
    occupancy_planets: Optional[List[str]] = None
    input_sign_indices: Optional[Dict[str, int]] = None
    input_bhinna_totals: Optional[Dict[str, int]] = None
    targets: Optional[Dict[str, PindaRow]] = None
    source_profile_comparison: Optional[Dict[str, AiyarReductionComparison]] = None
    unreduced_tables_preserved: Optional[bool] = None
    assumptions: Optional[List[str]] = None
    interpretation_scope: Optional[str] = None
    basis_bhinna_rule_id: Optional[str] = None
    bhinna_fact_path: Optional[str] = None


class BavSourceDifference(PartialOutput):
    default_source_id: Optional[str] = None
    same_input_sign_indices: Optional[bool] = None
    bhinna_different_sign_indices: Optional[Dict[str, List[int]]] = None
    samudaya_different_sign_indices: Optional[List[int]] = None
    scope: Optional[str] = None


class AiyarBavProfile(PartialOutput):
    status: Optional[str] = None
    method_id: Optional[str] = None
    source_id: Optional[str] = None
    source_section: Optional[str] = None
    rule_ids: Optional[List[str]] = None
    input_sign_indices: Optional[Dict[str, int]] = None
    contributor_order: Optional[List[str]] = None
    target_order: Optional[List[str]] = None
    samudaya_targets: Optional[List[str]] = None
    prastara: Optional[Dict[str, Dict[str, List[int]]]] = None
    bhinna: Optional[Dict[str, List[int]]] = None
    samudaya: Optional[List[int]] = None
    bhinna_totals: Optional[Dict[str, int]] = None
    samudaya_total: Optional[int] = None
    notation: Optional[Object] = None
    reductions_applied: Optional[bool] = None
    reduction_analysis: Optional[AiyarReductionComparison] = None
    comparison_to_default: Optional[BavSourceDifference] = None
    chart_method: Optional[str] = None
    chart_rule_ids: Optional[List[str]] = None
    input_claims: Optional[List[Object]] = None
    interpretation_scope: Optional[str] = None


class AshtakavargaChart(PartialOutput):
    input_sign_indices: Optional[Dict[str, int]] = None
    prastara: Optional[Dict[str, Dict[str, List[int]]]] = None
    bhinna: Optional[Dict[str, List[int]]] = None
    samudaya: Optional[List[int]] = None
    bhinna_totals: Optional[Dict[str, int]] = None
    samudaya_total: Optional[int] = None
    chart_method: Optional[str] = None
    chart_rule_ids: Optional[List[str]] = None
    input_claims: Optional[List[Object]] = None
    reduction_analysis: Optional[PindaAnalysis] = None
    source_profile_comparison: Optional[Dict[str, AiyarBavProfile]] = None


class Ashtakavarga(PartialOutput):
    status: Optional[str] = None
    method_id: Optional[str] = None
    source_id: Optional[str] = None
    source_section: Optional[str] = None
    rule_ids: Optional[List[str]] = None
    reference_instant: Optional[str] = None
    sign_order: Optional[List[str]] = None
    contributor_order: Optional[List[str]] = None
    target_order: Optional[List[str]] = None
    samudaya_targets: Optional[List[str]] = None
    notation: Optional[Object] = None
    reductions_applied: Optional[bool] = None
    charts: Optional[Dict[str, AshtakavargaChart]] = None
    not_computed: Optional[List[str]] = None
    interpretation_scope: Optional[str] = None


class JyotishIndia(PartialOutput):
    reading_basis: Optional[Object] = None
    ayanamsha: Optional[float] = None
    moon_nakshatra: Optional[str] = None
    rising_nakshatra: Optional[str] = None
    status: Optional[str] = None
    ruleset_id: Optional[str] = None
    profile: Optional[JyotishProfile] = None
    nakshatras: Optional[Dict[str, Nakshatra]] = None
    charts: Optional[VargaCharts] = None
    strengths: Optional[JyotishStrengths] = None
    ashtakavarga: Optional[Ashtakavarga] = None
    topic_evidence: Optional[Dict[str, Object]] = None
    birth_time_sensitivity: Optional[Object] = None
    rulesets: Optional[List[Object]] = None
    rule_trace: Optional[List[Object]] = None
    coverage: Optional[Dict[str, List[str]]] = None
    interpretation_scope: Optional[str] = None


class DashaPeriod(PartialOutput):
    lord: Optional[str] = None
    major_lord: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    duration_years: Optional[float] = None


class Mahadasha(DashaPeriod):
    antardashas: Optional[List[DashaPeriod]] = None


class DashaLevel(DashaPeriod):
    level: Optional[int] = None
    name: Optional[str] = None
    abbreviation: Optional[str] = None
    lord_chain: Optional[List[str]] = None
    duration_years_fraction: Optional[List[int]] = None


class DashaSiblings(PartialOutput):
    level: Optional[int] = None
    parent_lord_chain: Optional[List[str]] = None
    periods: Optional[List[DashaLevel]] = None


class DashaExactFraction(PartialOutput):
    numerator: Optional[str] = Field(default=None, pattern=r"^-?(0|[1-9][0-9]*)$")
    denominator: Optional[str] = Field(default=None, pattern=r"^[1-9][0-9]*$")


class DashaEpochContext(PartialOutput):
    reference_epoch_utc: Optional[str] = None
    complete_major_start_offset_microseconds_fraction: Optional[DashaExactFraction] = (
        None
    )
    quantization_method_id: Optional[str] = None
    source_id: Optional[str] = None


class DashaTimeQuantization(PartialOutput):
    method_id: Optional[str] = None
    source_id: Optional[str] = None
    reference_epoch_utc: Optional[str] = None
    source_mansion_fraction_exact: Optional[DashaExactFraction] = None
    year_microseconds: Optional[int] = None
    quantum_microseconds: Optional[int] = None
    rounding: Optional[str] = None
    scope: Optional[str] = None


class DashaSubdivisions(PartialOutput):
    method_id: Optional[str] = None
    depth: Optional[int] = None
    source_id: Optional[str] = None
    rule_ids: Optional[List[str]] = None
    current_levels: Optional[List[DashaLevel]] = None
    siblings_by_level: Optional[List[DashaSiblings]] = None
    year_basis: Optional[str] = None
    rounding_policy: Optional[str] = None
    epoch_context: Optional[DashaEpochContext] = None
    scope: Optional[str] = None


class DashaSeed(Nakshatra):
    moon_longitude: Optional[float] = None


class DashaBirthBalance(PartialOutput):
    lord: Optional[str] = None
    elapsed_years: Optional[float] = None
    remaining_years: Optional[float] = None
    elapsed_microseconds: Optional[int] = None
    remaining_microseconds: Optional[int] = None
    major_start: Optional[str] = None
    major_end: Optional[str] = None


class Vimshottari(PartialOutput):
    method_id: Optional[str] = None
    year_basis: Optional[str] = None
    year_days: Optional[float] = None
    analysis_datetime: Optional[str] = None
    boundary_convention: Optional[str] = None
    elapsed_time_convention: Optional[str] = None
    time_quantization: Optional[DashaTimeQuantization] = None
    seed: Optional[DashaSeed] = None
    birth_balance: Optional[DashaBirthBalance] = None
    current_major: Optional[DashaPeriod] = None
    current_sub: Optional[DashaPeriod] = None
    subdivisions: Optional[DashaSubdivisions] = None
    timeline: Optional[List[Mahadasha]] = None
    timeline_scope: Optional[Object] = None
    birth_time_sensitivity: Optional[Object] = None
    natal_ruler_context: Optional[List[Object]] = None
    rule_ids: Optional[List[str]] = None
    interpretation_scope: Optional[str] = None
