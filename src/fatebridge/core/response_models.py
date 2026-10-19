"""Public output contracts, shared by REST, MCP and CLI discovery.

Business fields are optional because every tool supports arbitrary projections.
Validation does not dump models back into responses: absent fields stay absent,
extension fields and existing numeric values survive unchanged. Stable expert
facts use the same nested contracts in validation and transport discovery.
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import Field, JsonValue, create_model

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_bazi import BAZI_FIELDS
from fatebridge.core.output_charts import CHART_FIELDS, CHART_TOOL_FIELDS, ChartPlanet
from fatebridge.core.output_chinese import (
    CHINESE_FIELDS,
    CHINESE_TOOL_FIELDS,
    CalendarContext,
    FourPillars,
    PersonInfo,
)
from fatebridge.core.output_reference import REFERENCE_TOOL_FIELDS, SnapshotExport
from fatebridge.core.output_western import WESTERN_FIELDS
from fatebridge.utils.errors import ValidationIssue

Object = Dict[str, JsonValue]


class ResultDelivery(PartialOutput):
    mode: Optional[str] = None
    result_id: Optional[str] = None
    sha256: Optional[str] = None
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
    contract_sha256: Optional[str] = None
    input_sha256: Optional[str] = None
    business_output_sha256: Optional[str] = None
    duration_ms: Optional[float] = Field(default=None, ge=0)
    effective_time: Optional[EffectiveTime] = None
    determinism: Optional[Determinism] = None
    runtime: Optional[Object] = None
    provenance: Optional[Dict[str, List[str]]] = None
    replay: Optional[ReplayControls] = None
    warnings: Optional[List[str]] = None


class DayMaster(PartialOutput):
    stem: Optional[str] = None
    element: Optional[str] = None
    polarity: Optional[str] = None
    strength: Optional[str] = None
    assessment: Optional[Object] = None


class BaziBirth(PartialOutput):
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


class Election(PartialOutput):
    topic_id: Optional[str] = None
    topic_label: Optional[str] = None
    topic_house: Optional[int] = None
    score: Optional[int] = Field(default=None, ge=0, le=100)
    verdict: Optional[str] = None
    has_hard_block: Optional[bool] = None
    recommendation: Optional[str] = None
    factors: Optional[List[ElectionFactor]] = None


def output_model_for(key: str) -> Any:
    """Build each catalog's public schema from explicit root-field contracts."""
    if key not in _TOOL_FIELDS:
        raise KeyError(f"Missing output contract for tool {key}")
    fields: Dict[str, Any] = {
        "run_metadata": (Optional[RunMetadata], None),
        "snapshot_text": (Optional[str], None),
        "snapshot_export": (Optional[SnapshotExport], None),
    }
    overrides = {
        **CHINESE_FIELDS,
        **WESTERN_FIELDS,
        **CHART_FIELDS,
        **BAZI_FIELDS,
        "bazi_birth": BaziBirth,
        "day_master": DayMaster,
        "planets": List[ChartPlanet],
        "election": Election,
        **CHINESE_TOOL_FIELDS.get(key, {}),
        **CHART_TOOL_FIELDS.get(key, {}),
        **REFERENCE_TOOL_FIELDS.get(key, {}),
    }
    for field in _TOOL_FIELDS[key].split():
        annotation = overrides.get(field, _FIELD_TYPES.get(field, Object))
        fields[field] = (Optional[annotation], None)
    name = "".join(part.title() for part in key.split("_")) + "Output"
    return create_model(name, __base__=ProjectedOutput, **fields)


def required_output_fields_for(key: str) -> tuple[str, ...]:
    """Non-null roots required before any transport projects the full result.

    This separate contract preserves projection-compatible public models. A
    missing declaration fails catalog assembly instead of leaving new tools
    silently unprotected. Empty collections remain legitimate domain results.
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
    "element_relations": List[JsonValue],
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
    "jieqi24": List[JsonValue],
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
    "analyze_destiny": "calendar_context day_master element_distribution element_distribution_adjusted element_distribution_basis element_relations element_seasonal_phase favorable_elements four_pillars patterns person_info structure_profile ten_gods",
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
    "timing_analysis": "analysis_calendar analysis_type birth_pillars calendar_context combined_effects comprehensive_summary dayun_analysis liunian_analysis liuri_analysis liushi_analysis liuyue_analysis personal_info",
    "dayun_analysis": "analysis_type calendar_context dayun_info element_effects personal_info summary",
    "liunian_analysis": "analysis_type calendar_context element_effects liunian_info personal_info summary target_year_jieqi",
    "liuyue_analysis": "analysis_calendar analysis_type calendar_context combination_effects detailed_analysis element_effects liunian_info liuyue_info personal_info summary target_year_jieqi",
    "liuri_analysis": "analysis_calendar analysis_type calendar_context element_effects liuri_info personal_info summary",
    "liushi_analysis": "analysis_calendar analysis_type calendar_context detailed_analysis element_effects life_dimensions liushi_info personal_info summary",
    "jieqi_timeline_analysis": "analysis_type calendar_context jieqi_timeline personal_info summary target_year_jieqi",
    "jieqi_year": "analysis_type jieqi24 jieqi_year query_context selected_jieqi summary year",
    "nongli_time": "analysis_context analysis_type birth calendar_context day dayGanZi dayInt four_pillars input_context jiedelta jieqi leap lunar_calendar month monthGanZi monthInt nongli summary time timeGanZi year yearGanZi yearJieqi",
    "gua_lookup": "analysis_type lookup_mode query result summary",
    "gua_meiyi": "analysis_type queries results summary",
    "meihua_analysis": "analysis_context analysis_type calendar_context four_pillars interpretation meihua summary",
    "tongshefa": "analysis_type input_normalized summary tongshefa",
    "sixyao": "analysis_type cast changed_code changed_hexagram current_code current_hexagram descriptions hexagram_info input_normalized lines moving_lines nongli pattern_flags patterns question summary",
    "canping": "analysis_context analysis_type benming calendar_context day_palace_branch dayun element four_pillars input_normalized liunian_series ming_gong part_name summary",
    "heluo": "analysis_context analysis_type calendar_context chart dayun four_pillars input_normalized judge solar_term summary",
    "suzhan": "analysis_type chart input_normalized params summary",
    "sukuyo_compatibility": "analysis_type pair person1 person1_to_person2 person2 person2_to_person1 su27_basis summary",
    "otherbu": "analysis_type chart diceChart house input_normalized interpretation planet question sign summary",
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
    "knowledge_read": "bundle_version category citation domain key lines provenance query_normalized rendered_text source tips title",
    "astro_chart": "angles aspects balance_basis chart_profile classical classical_patterns element_balance fixed_stars houses interpretation modality_balance person_info planetary_hours planets summary",
    "astro_chart13": "angles aspects balance_basis chart_profile classical classical_patterns element_balance fixed_stars houses interpretation modality_balance person_info planetary_hours planets summary thirteen_sectors",
    "astro_hellen": "angles aspects balance_basis chart_profile classical classical_patterns element_balance fixed_stars hellenistic houses interpretation modality_balance person_info planetary_hours planets summary",
    "astro_guolao": "angles aspects balance_basis chart_profile classical classical_patterns element_balance fixed_stars guolao houses interpretation modality_balance person_info planetary_hours planets summary",
    "astro_india": "angles aspects balance_basis chart_profile classical classical_patterns element_balance fixed_stars houses india interpretation modality_balance person_info planetary_hours planets summary",
    "astro_germany": "base_chart chart_profile midpoint_aspects midpoints summary",
    "astro_relative": "chart compatibility in_to_out_antiscia in_to_out_aspects in_to_out_contra_antiscia in_to_out_midpoint inner inner_chart out_to_in_antiscia out_to_in_aspects out_to_in_contra_antiscia out_to_in_midpoint outer outer_chart relationship_profile summary synastry_aspects",
    "astro_relative_chart": "chart compatibility in_to_out_antiscia in_to_out_aspects in_to_out_contra_antiscia in_to_out_midpoint inner inner_chart out_to_in_antiscia out_to_in_aspects out_to_in_contra_antiscia out_to_in_midpoint outer outer_chart relationship_profile summary synastry_aspects",
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
    "astro_horary": "analysis_context analysis_type engine horary summary",
    "astro_election": "analysis_context analysis_type election engine summary",
}


# These are semantic business roots, not metadata or optional explanations.
# Conditional chart variants declare their invariant roots only.
_REQUIRED_OUTPUT_FIELDS = {
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
    "liushi_analysis": "liushi_info",
    "jieqi_timeline_analysis": "jieqi_timeline",
    "jieqi_year": "jieqi_year",
    "nongli_time": "nongli four_pillars",
    "gua_lookup": "result",
    "gua_meiyi": "results",
    "meihua_analysis": "meihua",
    "tongshefa": "tongshefa",
    "sixyao": "cast current_code current_hexagram",
    "canping": "benming",
    "heluo": "chart",
    "suzhan": "chart",
    "sukuyo_compatibility": "person1 person2 person1_to_person2 person2_to_person1",
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
    "fengshui_xuankong_natal": "status layers rulesets coverage rule_trace",
    "fengshui_assess": "status layers rulesets coverage rule_trace",
}
