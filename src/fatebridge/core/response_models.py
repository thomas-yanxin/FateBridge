"""Public output contracts, shared by REST, MCP and CLI discovery.

Business fields are optional because every tool supports arbitrary projections.
Validation does not dump models back into responses: absent fields stay absent,
extension fields and existing numeric values survive unchanged. Stable expert
facts use the same nested contracts in validation and transport discovery.
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import Field, JsonValue, create_model

from fatebridge.core.output_astrodice import ASTRODICE_FIELDS
from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_bazi import BAZI_FIELDS
from fatebridge.core.output_bazi_evidence import EvidenceStructureProfile
from fatebridge.core.output_charts import (
    CHART_FIELDS,
    CHART_TOOL_FIELDS,
    ChartPlanet,
    SolarConditionPolicy,
)
from fatebridge.core.output_chinese import (
    CHINESE_FIELDS,
    CHINESE_TOOL_FIELDS,
    CalendarContext,
    FourPillars,
    PersonInfo,
)
from fatebridge.core.output_classical_roots import ClassicalOverview
from fatebridge.core.output_compatibility import (
    CompatibilityDetails,
    CompatibilitySummary,
    TraditionalCompatibility,
)
from fatebridge.core.output_jyotish import Vimshottari
from fatebridge.core.output_reference import REFERENCE_TOOL_FIELDS, SnapshotExport
from fatebridge.core.output_ren_anchors import RenAnchoredOutput
from fatebridge.core.output_source_annotations import (
    LiteralSourceInputContext,
    SourceAnnotationComparison,
    SourceCurrentCalculation,
)
from fatebridge.core.output_timing import (
    AnalysisReference,
    BirthTimeSensitivity,
    LifeDimensionAssessment,
    LifeDimensionScores,
    TimingInteractions,
)
from fatebridge.core.output_western import (
    WESTERN_FIELDS,
    HoraryMotionBasis,
    WesternCalculationBasis,
)
from fatebridge.core.output_western_policy import WesternDataPolicy
from fatebridge.utils.errors import ValidationIssue

Object = Dict[str, JsonValue]


class ResultDelivery(PartialOutput):
    compact_reference: Optional[bool] = None
    mode: Optional[str] = None
    result_id: Optional[str] = None
    total_chars: Optional[int] = None
    total_bytes: Optional[int] = None
    expires_at: Optional[float] = None
    page_chars: Optional[int] = None
    manifest_uri: Optional[str] = None
    first_page_uri: Optional[str] = None
    rest_manifest_path: Optional[str] = None
    file_path: Optional[str] = None
    file_payload_path: Optional[str] = None
    available_fields: Optional[List[str]] = None
    deferred_fields: Optional[List[str]] = None


class ProjectedOutput(PartialOutput):
    projection_warnings: Optional[List[ValidationIssue]] = None
    result_delivery: Optional[ResultDelivery] = None


class EffectiveTime(PartialOutput):
    as_of: str
    clock_timezones: List[str]


class ReplayControls(PartialOutput):
    as_of: str
    overrides: Object
    requires_original_input: bool


class Determinism(PartialOutput):
    uses_current_time: bool
    current_time_fields_defaulted: List[str]
    randomness_used: bool
    seed_generated: bool
    replayable_with_receipt: bool
    scope: str


class RunMetadata(PartialOutput):
    run_id: str
    trace_id: str
    tool_name: str
    generated_at: str
    engine: str
    engine_is_approximate: bool
    parent_run_id: Optional[str] = None
    metadata_schema_version: Optional[str] = None
    package_version: Optional[str] = None
    duration_ms: Optional[float] = Field(default=None, ge=0)
    effective_time: Optional[EffectiveTime] = None
    determinism: Optional[Determinism] = None
    runtime: Optional[Object] = None
    provenance: Optional[Dict[str, List[str]]] = None
    calculation_evidence: Optional[Object] = None
    replay: Optional[ReplayControls] = None
    warnings: Optional[List[str]] = None


class DayMaster(PartialOutput):
    stem: Optional[str] = None
    element: Optional[str] = None
    polarity: Optional[str] = None
    strength: Optional[str] = None
    assessment: Optional[Object] = None


class BaziBirth(PartialOutput):
    classical: Optional[ClassicalOverview] = None
    structure_profile: Optional[EvidenceStructureProfile] = None
    day_master: Optional[DayMaster] = None
    four_pillars: Optional[FourPillars] = None
    favorable_elements: Optional[List[JsonValue]] = None
    element_distribution: Optional[Object] = None
    person_info: Optional[PersonInfo] = None
    calendar_context: Optional[CalendarContext] = None
    patterns: Optional[Object] = None
    ten_gods: Optional[Object] = None
    analysis_date: Optional[str] = None


class ElectionFactor(PartialOutput):
    code: Optional[str] = None
    polarity: Optional[str] = None
    weight: Optional[int] = None
    hard: Optional[bool] = None
    detail: Optional[str] = None


class ElectionPlanet(PartialOutput):
    planet: Optional[str] = None
    sign: Optional[str] = None
    longitude: Optional[float] = None
    speed: Optional[float] = None
    retrograde: Optional[bool] = None
    house: Optional[str] = None
    dignity: Optional[str] = None
    dignity_scope: Optional[str] = None


class ElectionAxes(PartialOutput):
    ascendant_longitude: Optional[float] = None
    midheaven_longitude: Optional[float] = None
    first_house_cusp: Optional[float] = None
    tenth_house_cusp: Optional[float] = None
    policy: Optional[str] = None


class ElectionMoon(PartialOutput):
    sign: Optional[str] = None
    sign_label: Optional[str] = None
    longitude: Optional[float] = None
    void_of_course: Optional[bool] = None
    phase: Optional[str] = None
    elongation_degrees: Optional[float] = None
    solar_condition: Optional[str] = None
    motion_basis: Optional[HoraryMotionBasis] = None


class ElectionAscendant(PartialOutput):
    sign: Optional[str] = None
    sign_label: Optional[str] = None
    longitude: Optional[float] = None
    ruler: Optional[str] = None
    ruler_label: Optional[str] = None
    ruler_dignity: Optional[str] = None


class ElectionUnresolvedFactor(PartialOutput):
    code: Optional[str] = None
    minimum_weight: Optional[int] = None
    maximum_weight: Optional[int] = None
    may_be_hard: Optional[bool] = None
    reason: Optional[str] = None


class ElectionScoreEvidence(PartialOutput):
    status: Optional[str] = None
    base_score: Optional[int] = None
    known_contribution: Optional[int] = None
    raw_known_subtotal: Optional[int] = None
    missing_factor_codes: Optional[List[str]] = None
    bounds_scope: Optional[str] = None


class ElectionScoringPolicy(PartialOutput):
    rule_id: Optional[str] = None
    base_score: Optional[int] = None
    weights_and_band_boundaries_changed: Optional[bool] = None
    scope: Optional[str] = None
    full_original_text_acceptance: Optional[bool] = None
    empirically_calibrated: Optional[bool] = None
    moon_operational_policy: Optional[str] = None
    solar_rule: Optional[str] = None
    phase_weight_policy: Optional[str] = None


class Election(PartialOutput):
    reference_geometry: Optional[Dict[str, Any]] = None
    backend_convention: Optional[Dict[str, Any]] = None
    system: Optional[str] = None
    system_label: Optional[str] = None
    significator: Optional[str] = None
    significator_label: Optional[str] = None
    planets: Optional[Dict[str, ElectionPlanet]] = None
    axes: Optional[ElectionAxes] = None
    calculation_basis: Optional[WesternCalculationBasis] = None
    solar_condition_policy: Optional[SolarConditionPolicy] = None
    moon: Optional[ElectionMoon] = None
    ascendant: Optional[ElectionAscendant] = None
    score_bounds: Optional[List[int]] = None
    score_evidence: Optional[ElectionScoreEvidence] = None
    scoring_policy: Optional[ElectionScoringPolicy] = None
    unresolved_factors: Optional[List[ElectionUnresolvedFactor]] = None
    dignity_scope: Optional[str] = None
    topic_id: Optional[str] = None
    topic_label: Optional[str] = None
    topic_house: Optional[int] = None
    score: Optional[int] = Field(default=None, ge=0, le=100)
    verdict: Optional[str] = None
    has_hard_block: Optional[bool] = None
    recommendation: Optional[str] = None
    factors: Optional[List[ElectionFactor]] = None


def output_model_for(key: str, *, western_data_policy: bool = False) -> Any:
    """Build each catalog's public schema from explicit root-field contracts."""
    if key not in _TOOL_FIELDS:
        raise KeyError(f"Missing output contract for tool {key}")
    fields: Dict[str, Any] = {
        "run_metadata": (Optional[RunMetadata], None),
        "snapshot_text": (Optional[str], None),
        "snapshot_export": (Optional[SnapshotExport], None),
    }
    if western_data_policy:
        fields["ephemeris_data_policy"] = (Optional[WesternDataPolicy], None)
    overrides = {
        **CHINESE_FIELDS,
        **WESTERN_FIELDS,
        **CHART_FIELDS,
        **BAZI_FIELDS,
        "bazi_birth": BaziBirth,
        "day_master": DayMaster,
        "structure_profile": EvidenceStructureProfile,
        "planets": List[ChartPlanet],
        "election": Election,
        "vimshottari": Vimshottari,
        "interaction_analysis": TimingInteractions,
        "analysis_reference": AnalysisReference,
        "birth_time_sensitivity": BirthTimeSensitivity,
        "life_dimensions": LifeDimensionScores,
        "life_dimensions_assessment": LifeDimensionAssessment,
        **CHINESE_TOOL_FIELDS.get(key, {}),
        **CHART_TOOL_FIELDS.get(key, {}),
        **REFERENCE_TOOL_FIELDS.get(key, {}),
        **(ASTRODICE_FIELDS if key == "otherbu" else {}),
        **(
            {
                "summary": CompatibilitySummary,
                "detailed_analysis": CompatibilityDetails,
                "traditional_compatibility": TraditionalCompatibility,
            }
            if key == "two_person_compatibility"
            else {}
        ),
        **(
            {
                "input_context": LiteralSourceInputContext,
                "current_calculation": SourceCurrentCalculation,
                "source_comparison": SourceAnnotationComparison,
                "summary": str,
            }
            if key == "bazi_source_compare"
            else {}
        ),
    }
    for field in _TOOL_FIELDS[key].split():
        annotation = overrides.get(field, _FIELD_TYPES.get(field, Object))
        fields[field] = (
            Optional[annotation],
            (
                Field(
                    default=None,
                    min_length=7,
                    json_schema_extra={
                        "x-fatebridge-full-result-unique-by": "id",
                        "x-fatebridge-full-result-identities": [
                            "Sun",
                            "Moon",
                            "Mercury",
                            "Venus",
                            "Mars",
                            "Jupiter",
                            "Saturn",
                        ],
                    },
                )
                if field == "planets"
                else None
            ),
        )
    name = "".join(part.title() for part in key.split("_")) + "Output"
    bases = (
        (ProjectedOutput, RenAnchoredOutput)
        if key in {"jinkou", "liureng_gods", "liureng_runyear", "sanshiunited"}
        else (ProjectedOutput,)
    )
    return create_model(name, __base__=bases, **fields)


def required_output_fields_for(key: str) -> tuple[str, ...]:
    """Non-null roots required before any transport projects the full result.

    This separate contract preserves projection-compatible public models. A
    missing declaration fails catalog assembly instead of leaving new tools
    silently unprotected. Required objects must contain a fact or explicit
    status; empty lists can still be legitimate domain results.
    """
    return tuple(_REQUIRED_OUTPUT_FIELDS[key].split())


# Public root fields; specialized nested contracts are defined above.
_FIELD_TYPES: Dict[str, Any] = {
    "analysis_type": str,
    "aspects": List[JsonValue],
    "balance_basis": str,
    "birth": str,
    "bundle_version": int,
    "category": str,
    "challenges": List[JsonValue],
    "changed_code": str,
    "citation": str,
    "comprehensive_summary": str,
    "current_code": str,
    "day": str,
    "dayGanZi": str,
    "dayInt": int,
    "day_palace_branch": str,
    "dayun": Union[Object, List[JsonValue]],
    "domain": str,
    "domains": List[JsonValue],
    "element": str,
    "element_distribution_basis": str,
    "engine": str,
    "export_text": str,
    "favorable_elements": List[JsonValue],
    "fixed_stars": List[JsonValue],
    "house": int,
    "houses": List[JsonValue],
    "in_to_out_antiscia": List[JsonValue],
    "in_to_out_aspects": List[JsonValue],
    "in_to_out_contra_antiscia": List[JsonValue],
    "jiedelta": str,
    "jieqi": str,
    "jieqi_split_keys": List[JsonValue],
    "jieqi_timeline": List[JsonValue],
    "jieqi_year": List[JsonValue],
    "key": str,
    "leap": bool,
    "lines": List[JsonValue],
    "lookup_mode": str,
    "midpoint_aspects": List[JsonValue],
    "midpoints": List[JsonValue],
    "ming_gong": str,
    "missing_selected_sections": List[JsonValue],
    "module_snapshot_prefix": str,
    "month": str,
    "monthGanZi": str,
    "monthInt": int,
    "moving_lines": List[JsonValue],
    "nongli": Union[Object, str],
    "out_to_in_antiscia": List[JsonValue],
    "out_to_in_aspects": List[JsonValue],
    "out_to_in_contra_antiscia": List[JsonValue],
    "pair": str,
    "part_name": str,
    "patterns": Union[Object, List[JsonValue]],
    "planet": str,
    "planets": List[JsonValue],
    "queries": List[JsonValue],
    "query": str,
    "question": Union[JsonValue, str],
    "recommendations": List[JsonValue],
    "rendered_text": str,
    "requested_year_stem": str,
    "section_titles_detected": List[JsonValue],
    "sections": List[JsonValue],
    "selected_jieqi": List[JsonValue],
    "selected_sections": List[JsonValue],
    "settings_key": str,
    "settings_version": int,
    "sign": str,
    "source": str,
    "source_of_truth": str,
    "strengths": List[JsonValue],
    "su27_basis": str,
    "summary": Union[Object, List[JsonValue], str],
    "synastry_aspects": List[JsonValue],
    "target_year_jieqi": List[JsonValue],
    "techniques": List[JsonValue],
    "thirteen_sectors": List[JsonValue],
    "time": str,
    "timeGanZi": str,
    "tips": List[JsonValue],
    "title": str,
    "unknown_detected_sections": List[JsonValue],
    "year": Union[int, str],
    "yearGanZi": str,
    "yearJieqi": str,
}

_TOOL_FIELDS = {
    "bazi_source_compare": "analysis_type four_pillars input_context current_calculation source_comparison summary",
    "analyze_destiny": "calendar_context day_master element_distribution element_distribution_basis element_seasonal_phase favorable_elements four_pillars patterns person_info structure_profile ten_gods",
    "bazi_birth": "analysis_type bazi_birth",
    "bazi_marriage": "analysis_type marriage_analysis",
    "bazi_career": "analysis_type career_analysis",
    "bazi_wealth": "analysis_type wealth_analysis",
    "bazi_health": "analysis_type health_analysis",
    "bazi_children": "analysis_type children_analysis",
    "bazi_education": "analysis_type education_analysis",
    "bazi_personality": "analysis_type personality_analysis",
    "bazi_relatives": "analysis_type relatives_analysis",
    "bazi_romance": "analysis_type romance_analysis",
    "two_person_compatibility": "challenges detailed_analysis element_relationship person_info recommendations strengths summary traditional_compatibility",
    "timing_analysis": "analysis_reference analysis_calendar analysis_type birth_pillars birth_time_sensitivity calendar_context combined_effects comprehensive_summary dayun_analysis interaction_analysis liunian_analysis liuri_analysis liushi_analysis liuyue_analysis personal_info",
    "dayun_analysis": "analysis_reference analysis_type birth_time_sensitivity calendar_context dayun_info element_effects personal_info summary timing_context",
    "liunian_analysis": "analysis_type calendar_context element_effects liunian_info personal_info summary target_year_jieqi",
    "liuyue_analysis": "analysis_reference analysis_calendar analysis_type calendar_context combination_effects detailed_analysis element_effects liunian_info liuyue_info personal_info summary target_year_jieqi",
    "liuri_analysis": "analysis_reference analysis_calendar analysis_type calendar_context element_effects liuri_info personal_info summary",
    "liushi_analysis": "analysis_reference analysis_calendar analysis_type calendar_context detailed_analysis element_effects life_dimensions life_dimensions_assessment liushi_info personal_info summary",
    "jieqi_timeline_analysis": "analysis_type calendar_context jieqi_timeline personal_info summary target_year_jieqi",
    "jieqi_year": "analysis_type jieqi_year query_context selected_jieqi summary year",
    "nongli_time": "analysis_context analysis_type birth calendar_context day dayGanZi dayInt four_pillars input_context jiedelta jieqi leap lunar_calendar month monthGanZi monthInt nongli summary timeGanZi yearGanZi yearJieqi",
    "gua_lookup": "analysis_type lookup_mode query result summary",
    "gua_meiyi": "analysis_type queries results summary",
    "meihua_analysis": "analysis_context analysis_type calendar_context four_pillars interpretation meihua summary",
    "tongshefa": "analysis_type input_normalized summary tongshefa",
    "sixyao": "analysis_type calendar_context cast changed_code changed_hexagram classical_text_evidence current_code current_hexagram descriptions hexagram_info input_normalized lines liuyao_evidence moving_lines nongli pattern_flags patterns question summary",
    "canping": "analysis_context analysis_type benming calendar_context day_palace_branch dayun element four_pillars input_normalized liunian_series ming_gong part_name summary numerology_evidence canping_timing",
    "heluo": "analysis_context analysis_type calendar_context chart dayun four_pillars input_normalized judge solar_term summary numerology_evidence heluo_timing jiehou_evidence",
    "suzhan": "analysis_type astronomy chart input_normalized params rulesets sukuyo validation summary",
    "sukuyo_compatibility": "analysis_type status pair person1 person1_to_person2 person2 person2_to_person1 candidate_relation_analysis su27_basis rulesets interpretation_contract validation summary",
    "otherbu": "analysis_type chart diceChart house input_normalized interpretation planet question sign summary method_id symbolic_details rulesets rule_trace validation",
    "sanshiunited": "analysis_context analysis_type input_normalized liureng qimen sources subresults summary taiyi",
    "ziwei_birth": "analysis_context analysis_type calendar_context four_pillars person_info ziwei_birth",
    "ziwei_horoscope": "analysis_context analysis_type birth_context person_info ziwei_horoscope",
    "ziwei_rules": "analysis_type engine focused_rules requested_year_stem rule_catalogue",
    "liureng_gods": "analysis_context analysis_type calendar_context four_pillars liureng",
    "liureng_runyear": "analysis_context analysis_type calendar_context four_pillars liureng runyear",
    "qimen": "analysis_context analysis_type calendar_context four_pillars qimen",
    "taiyi": "analysis_context analysis_type calendar_context four_pillars taiyi",
    "jinkou": "analysis_context analysis_type calendar_context four_pillars jinkou liureng",
    "export_registry": "astro_meaning_default default_normalized_settings jieqi_split_keys module_snapshot_prefix planet_info_default selected_technique settings_key settings_version source_of_truth techniques",
    "export_parse": "export_text missing_selected_sections section_titles_detected sections selected_sections settings_used technique unknown_detected_sections",
    "knowledge_registry": "bundle_version domains provenance source",
    "knowledge_read": "bundle_version category citation domain key lines provenance query_normalized reference_only reference_details rendered_text source tips title",
    "astro_chart": "angles apparent_model_positions aspect_evidence aspects balance_basis chart_profile classical classical_patterns element_balance fixed_stars houses india interpretation interpretation_evidence modality_balance person_info planetary_hours planets summary sector_profile midpoint_analysis thirteen_sectors time_sensitivity midpoints midpoint_aspects base_chart",
    "astro_chart13": "angles aspect_evidence aspects balance_basis chart_profile classical classical_patterns element_balance fixed_stars houses interpretation interpretation_evidence modality_balance person_info planetary_hours planets summary thirteen_sectors sector_profile time_sensitivity",
    "astro_hellen": "angles aspect_evidence aspects balance_basis chart_profile classical classical_patterns element_balance fixed_stars hellenistic houses interpretation interpretation_evidence modality_balance person_info planetary_hours planets summary",
    "astro_guolao": "angles aspect_evidence aspects balance_basis chart_profile classical classical_patterns element_balance fixed_stars guolao houses interpretation interpretation_evidence modality_balance person_info planetary_hours planets summary",
    "astro_india": "angles aspect_evidence aspects balance_basis chart_profile classical classical_patterns element_balance fixed_stars houses india interpretation interpretation_evidence modality_balance person_info planetary_hours planets summary",
    "astro_vimshottari": "analysis_context person_info india vimshottari summary",
    "astro_germany": "base_chart chart_profile planets midpoint_aspects midpoints midpoint_analysis summary",
    "astro_relative": "chart compatibility compatibility_evidence in_to_out_antiscia in_to_out_aspects in_to_out_contra_antiscia in_to_out_midpoint inner inner_chart marks_charts out_to_in_antiscia out_to_in_aspects out_to_in_contra_antiscia out_to_in_midpoint outer outer_chart relationship_profile summary synastry_aspects",
    "astro_relative_chart": "chart compatibility compatibility_evidence in_to_out_antiscia in_to_out_aspects in_to_out_contra_antiscia in_to_out_midpoint inner inner_chart marks_charts out_to_in_antiscia out_to_in_aspects out_to_in_contra_antiscia out_to_in_midpoint outer outer_chart relationship_profile summary synastry_aspects",
    "western_timing_analysis": "analysis_context analysis_type directions natal_reference returns summary time_lords transits",
    "solarreturn": "analysis_context analysis_type engine natal_reference solarreturn summary",
    "lunarreturn": "analysis_context analysis_type engine lunarreturn natal_reference summary",
    "transit": "analysis_context analysis_type engine natal_reference summary transit",
    "solararc": "analysis_context analysis_type engine natal_reference solararc summary",
    "givenyear": "analysis_context analysis_type engine givenyear natal_reference summary",
    "profection": "analysis_context analysis_type engine natal_reference profection summary",
    "pd": "analysis_context analysis_type engine natal_reference pd summary",
    "pdchart": "analysis_context analysis_type engine natal_reference pdchart summary",
    "zr": "analysis_context analysis_type engine natal_reference summary zr",
    "firdaria": "analysis_context analysis_type engine firdaria natal_reference summary",
    "decennials": "analysis_context analysis_type decennials engine natal_reference summary",
    "astro_harmonic": "analysis_context analysis_type engine harmonic_chart natal_reference summary",
    "astro_planetary_ages": "analysis_context analysis_type engine natal_reference planetary_ages summary",
    "astro_triplicity_rulers": "analysis_context analysis_type engine natal_reference summary triplicity_rulers",
    "astro_lunation_phase": "analysis_context analysis_type engine lunation_phase natal_reference summary",
    "astro_distributions": "analysis_context analysis_type distributions engine natal_reference summary",
    "astro_balbillus": "analysis_context analysis_type balbillus engine natal_reference summary",
    "astro_keypoints": "analysis_context analysis_type engine keypoints natal_reference summary",
    "astro_yearsystem129": "analysis_context analysis_type engine natal_reference summary yearsystem129",
    "astro_planetaryarc": "analysis_context analysis_type engine natal_reference planetary_arc summary",
    "astro_persiandirected": "analysis_context analysis_type engine natal_reference persian_directed summary",
    "astro_agepoint": "age_point analysis_context analysis_type engine natal_reference summary",
    "astro_vedicprog": "analysis_context analysis_type engine natal_reference summary vedic_progression",
    "astro_jaynesprog": "analysis_context analysis_type engine jaynes_declination natal_reference summary",
    "astro_mundane": "analysis_context analysis_type engine mundane summary",
    "astro_extrareturns": "analysis_context analysis_type engine extrareturns summary",
    "astro_horary": "analysis_context analysis_type calendar_conversion clock_conversion engine horary summary",
    "astro_election": "analysis_context analysis_type calendar_conversion clock_conversion election engine summary",
}


# These are semantic business roots, not metadata or optional explanations.
# Conditional chart variants declare their invariant roots only.
_REQUIRED_OUTPUT_FIELDS = {
    "bazi_source_compare": "four_pillars input_context current_calculation source_comparison summary",
    "analyze_destiny": "four_pillars day_master",
    "bazi_birth": "bazi_birth",
    "bazi_marriage": "marriage_analysis",
    "bazi_career": "career_analysis",
    "bazi_wealth": "wealth_analysis",
    "bazi_health": "health_analysis",
    "bazi_children": "children_analysis",
    "bazi_education": "education_analysis",
    "bazi_personality": "personality_analysis",
    "bazi_relatives": "relatives_analysis",
    "bazi_romance": "romance_analysis",
    "two_person_compatibility": "summary detailed_analysis traditional_compatibility",
    "timing_analysis": "birth_pillars comprehensive_summary",
    "dayun_analysis": "dayun_info",
    "liunian_analysis": "liunian_info",
    "liuyue_analysis": "liuyue_info",
    "liuri_analysis": "liuri_info",
    "liushi_analysis": "liushi_info life_dimensions life_dimensions_assessment",
    "jieqi_timeline_analysis": "jieqi_timeline",
    "jieqi_year": "jieqi_year",
    "nongli_time": "nongli four_pillars",
    "gua_lookup": "result",
    "gua_meiyi": "results",
    "meihua_analysis": "meihua",
    "tongshefa": "tongshefa",
    "sixyao": "cast current_code current_hexagram",
    "canping": "benming numerology_evidence canping_timing",
    "heluo": "chart numerology_evidence",
    "suzhan": "analysis_type input_normalized params rulesets sukuyo validation summary",
    "sukuyo_compatibility": "person1 person2 rulesets status",
    "otherbu": "planet sign house",
    "sanshiunited": "subresults",
    "ziwei_birth": "ziwei_birth",
    "ziwei_horoscope": "ziwei_horoscope",
    "ziwei_rules": "rule_catalogue",
    "liureng_gods": "liureng",
    "liureng_runyear": "liureng runyear",
    "qimen": "qimen",
    "taiyi": "taiyi",
    "jinkou": "jinkou",
    "export_registry": "techniques",
    "export_parse": "export_text sections",
    "knowledge_registry": "domains provenance",
    "knowledge_read": "lines provenance",
    "astro_chart": "planets chart_profile",
    "astro_chart13": "planets chart_profile thirteen_sectors",
    "astro_hellen": "planets chart_profile hellenistic",
    "astro_guolao": "planets chart_profile guolao",
    "astro_india": "planets chart_profile india",
    "astro_vimshottari": "analysis_context person_info india vimshottari summary",
    "astro_germany": "base_chart midpoints chart_profile",
    "astro_relative": "relationship_profile",
    "astro_relative_chart": "relationship_profile",
    "western_timing_analysis": "directions returns time_lords transits",
    "solarreturn": "solarreturn",
    "lunarreturn": "lunarreturn",
    "transit": "transit",
    "solararc": "solararc",
    "givenyear": "givenyear",
    "profection": "profection",
    "pd": "pd",
    "pdchart": "pdchart",
    "zr": "zr",
    "firdaria": "firdaria",
    "decennials": "decennials",
    "astro_harmonic": "harmonic_chart",
    "astro_planetary_ages": "planetary_ages",
    "astro_triplicity_rulers": "triplicity_rulers",
    "astro_lunation_phase": "lunation_phase",
    "astro_distributions": "distributions",
    "astro_balbillus": "balbillus",
    "astro_keypoints": "keypoints",
    "astro_yearsystem129": "yearsystem129",
    "astro_planetaryarc": "planetary_arc",
    "astro_persiandirected": "persian_directed",
    "astro_agepoint": "age_point",
    "astro_vedicprog": "vedic_progression",
    "astro_jaynesprog": "jaynes_declination",
    "astro_mundane": "mundane",
    "astro_extrareturns": "extrareturns",
    "astro_horary": "horary",
    "astro_election": "election",
    "fengshui_directions": "status layers rulesets coverage rule_trace",
    "fengshui_minggua": "status layers rulesets coverage rule_trace",
    "fengshui_bazhai": "status layers rulesets coverage rule_trace",
    "fengshui_jinsuo": "status layers rulesets coverage rule_trace",
    "fengshui_annual_stars": "status layers rulesets coverage rule_trace",
    "fengshui_monthly_stars": "status layers rulesets coverage rule_trace",
    "fengshui_xuankong_natal": "status layers rulesets coverage rule_trace",
    # Form-only assessment legitimately has layers={}; its typed FullFact
    # still requires the map to be present and non-null in complete output.
    "fengshui_assess": "status rulesets coverage rule_trace",
}
