"""Public output contracts, shared by REST, MCP and CLI discovery.

Business fields are optional because every tool supports arbitrary projections.
Validation does not dump models back into responses: absent fields stay absent,
extension fields and existing numeric values survive unchanged. Stable expert
facts use the same nested contracts in validation and transport discovery.
"""

from typing import Any

from pydantic import BaseModel, Field, JsonValue, create_model

from fatebridge.core.contracts.output_astrodice import ASTRODICE_FIELDS
from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_bazi import DimensionOutput
from fatebridge.core.contracts.output_bazi_anchors import TOPICS
from fatebridge.core.contracts.output_bazi_birth import BaziBirth, DayMaster
from fatebridge.core.contracts.output_bazi_evidence import EvidenceStructureProfile
from fatebridge.core.contracts.output_chart_geometry import ChartPlanet
from fatebridge.core.contracts.output_charts import CHART_FIELDS, CHART_TOOL_FIELDS
from fatebridge.core.contracts.output_chinese import CHINESE_FIELDS, CHINESE_TOOL_FIELDS
from fatebridge.core.contracts.output_compatibility import COMPATIBILITY_FIELDS
from fatebridge.core.contracts.output_jyotish import Vimshottari
from fatebridge.core.contracts.output_projection import ProjectedOutput
from fatebridge.core.contracts.output_reference import REFERENCE_TOOL_FIELDS
from fatebridge.core.contracts.output_ren_anchors import RenAnchoredOutput
from fatebridge.core.contracts.output_source_annotations import (
    LiteralSourceInputContext,
    SourceAnnotationComparison,
    SourceCurrentCalculation,
)
from fatebridge.core.contracts.output_timing import (
    AnalysisReference,
    BirthTimeSensitivity,
    TimingInteractions,
)
from fatebridge.core.contracts.output_western import WESTERN_FIELDS
from fatebridge.core.contracts.output_western_election import Election
from fatebridge.core.contracts.output_western_policy import WesternDataPolicy
from fatebridge.core.receipt_models import Object, RunMetadata

__all__ = [
    "CHART_TOOL_FIELDS",
    "CHINESE_TOOL_FIELDS",
    "DayMaster",
    "Election",
    "Object",
    "PartialOutput",
    "ProjectedOutput",
    "REFERENCE_TOOL_FIELDS",
    "RunMetadata",
    "output_model_for",
    "required_output_fields_for",
]


def output_model_for(key: str, *, western_data_policy: bool = False) -> type[BaseModel]:
    """Build each catalog's public schema from explicit root-field contracts."""
    if key not in TOOL_FIELDS:
        raise KeyError(f"Missing output contract for tool {key}")
    fields: dict[str, Any] = {
        "run_metadata": (RunMetadata | None, None),
    }
    if western_data_policy:
        fields["ephemeris_data_policy"] = (WesternDataPolicy | None, None)
    tool_fields = {
        **CHINESE_TOOL_FIELDS.get(key, {}),
        **CHART_TOOL_FIELDS.get(key, {}),
        **REFERENCE_TOOL_FIELDS.get(key, {}),
        **(ASTRODICE_FIELDS if key == "interpret_astrology_dice" else {}),
        **(COMPATIBILITY_FIELDS if key == "bazi_compatibility" else {}),
        **(
            {
                "input_context": LiteralSourceInputContext,
                "current_calculation": SourceCurrentCalculation,
                "source_comparison": SourceAnnotationComparison,
                "summary": str,
            }
            if key == "compare_bazi_sources"
            else {}
        ),
    }
    overrides = {
        **CHINESE_FIELDS,
        **WESTERN_FIELDS,
        **CHART_FIELDS,
        **{f"{topic}_analysis": DimensionOutput for topic in TOPICS},
        "bazi_birth": BaziBirth,
        "day_master": DayMaster,
        "structure_profile": EvidenceStructureProfile,
        "planets": list[ChartPlanet],
        "election": Election,
        "vimshottari": Vimshottari,
        "interaction_analysis": TimingInteractions,
        "analysis_reference": AnalysisReference,
        "birth_time_sensitivity": BirthTimeSensitivity,
        **tool_fields,
    }
    root_fields = dict.fromkeys([*TOOL_FIELDS[key].split(), *tool_fields])
    for field in root_fields:
        annotation = overrides.get(field, FIELD_TYPES.get(field, Object))
        metadata: dict[str, JsonValue] = {}
        if field == "planets":
            metadata.update(
                {
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
                }
            )
        fields[field] = (
            annotation | None,
            Field(
                default=None,
                min_length=7 if field == "planets" else None,
                json_schema_extra=metadata or None,
            ),
        )
    name = "".join(part.title() for part in key.split("_")) + "Output"
    bases = (
        (ProjectedOutput, RenAnchoredOutput)
        if key
        in {"jinkou", "liuren_chart", "liuren_yearly_timing", "sanshi_combined_chart"}
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
    return tuple(REQUIRED_OUTPUT_FIELDS[key].split())


FIELD_TYPES: dict[str, Any] = {
    "analysis_type": str,
    "aspects": list[JsonValue],
    "balance_basis": str,
    "birth": str,
    "bundle_version": int,
    "category": str,
    "challenges": list[JsonValue],
    "changed_code": str,
    "citation": str,
    "comprehensive_summary": str,
    "current_code": str,
    "day": str,
    "dayGanZi": str,
    "dayInt": int,
    "day_palace_branch": str,
    "dayun": Object | list[JsonValue],
    "domain": str,
    "domains": list[JsonValue],
    "element": str,
    "element_distribution_basis": str,
    "engine": str,
    "favorable_elements": list[JsonValue],
    "favorable_elements_status": str,
    "engineering_favorable_elements": list[str],
    "fixed_stars": list[JsonValue],
    "house": int,
    "houses": list[JsonValue],
    "in_to_out_antiscia": list[JsonValue],
    "in_to_out_aspects": list[JsonValue],
    "in_to_out_contra_antiscia": list[JsonValue],
    "jiedelta": str,
    "jieqi": str,
    "jieqi_split_keys": list[JsonValue],
    "jieqi_timeline": list[JsonValue],
    "jieqi_year": list[JsonValue],
    "key": str,
    "leap": bool,
    "lines": list[JsonValue],
    "lookup_mode": str,
    "midpoint_aspects": list[JsonValue],
    "midpoints": list[JsonValue],
    "ming_gong": str,
    "month": str,
    "monthGanZi": str,
    "monthInt": int,
    "moving_lines": list[JsonValue],
    "nongli": Object | str,
    "out_to_in_antiscia": list[JsonValue],
    "out_to_in_aspects": list[JsonValue],
    "out_to_in_contra_antiscia": list[JsonValue],
    "pair": str,
    "part_name": str,
    "patterns": Object | list[JsonValue],
    "planet": str,
    "planets": list[JsonValue],
    "queries": list[JsonValue],
    "query": str,
    "question": JsonValue | str,
    "rendered_text": str,
    "requested_year_stem": str,
    "selected_jieqi": list[JsonValue],
    "sign": str,
    "source": str,
    "su27_basis": str,
    "summary": Object | list[JsonValue] | str,
    "synastry_aspects": list[JsonValue],
    "target_year_jieqi": list[JsonValue],
    "techniques": list[JsonValue],
    "thirteen_sectors": list[JsonValue],
    "time": str,
    "timeGanZi": str,
    "tips": list[JsonValue],
    "title": str,
    "year": int | str,
    "yearGanZi": str,
    "yearJieqi": str,
}


TOOL_FIELDS = {
    "compare_bazi_sources": "analysis_type four_pillars input_context current_calculation source_comparison summary",
    "bazi_overview": "calendar_context day_master element_distribution element_distribution_basis element_seasonal_phase favorable_elements four_pillars patterns person_info structure_profile ten_gods",
    "bazi_birth_chart": "analysis_type bazi_birth",
    "bazi_marriage": "analysis_type marriage_analysis",
    "bazi_career": "analysis_type career_analysis",
    "bazi_wealth": "analysis_type wealth_analysis",
    "bazi_health": "analysis_type health_analysis",
    "bazi_children": "analysis_type children_analysis",
    "bazi_education": "analysis_type education_analysis",
    "bazi_personality": "analysis_type personality_analysis",
    "bazi_relatives": "analysis_type relatives_analysis",
    "bazi_romance": "analysis_type romance_analysis",
    "bazi_compatibility": "relationship_type person_info natal_contexts element_relationship cross_chart_relations directional_ten_gods",
    "bazi_timing": "analysis_reference analysis_calendar analysis_type birth_pillars birth_time_sensitivity calendar_context combined_effects comprehensive_summary dayun_analysis interaction_analysis liunian_analysis liuri_analysis liushi_analysis liuyue_analysis personal_info",
    "bazi_luck_cycles": "analysis_reference analysis_type birth_time_sensitivity calendar_context dayun_info element_effects personal_info summary timing_context",
    "bazi_yearly_timing": "analysis_type calendar_context element_effects liunian_info personal_info summary target_year_jieqi",
    "bazi_monthly_timing": "analysis_reference analysis_calendar analysis_type calendar_context combination_effects detailed_analysis element_effects liunian_info liuyue_info personal_info summary target_year_jieqi",
    "bazi_daily_timing": "analysis_reference analysis_calendar analysis_type calendar_context element_effects liuri_info personal_info summary",
    "bazi_hourly_timing": "analysis_reference analysis_calendar analysis_type calendar_context detailed_analysis element_effects liushi_info personal_info summary",
    "solar_term_timeline": "analysis_type calendar_context jieqi_timeline personal_info summary target_year_jieqi",
    "solar_terms_for_year": "analysis_type jieqi_year query_context selected_jieqi summary year",
    "lunar_calendar_time": "analysis_context analysis_type birth calendar_context day dayGanZi dayInt four_pillars input_context jiedelta jieqi leap lunar_calendar month monthGanZi monthInt nongli summary timeGanZi yearGanZi yearJieqi",
    "gua_lookup": "analysis_type lookup_mode query result summary",
    "gua_meanings": "analysis_type queries results summary",
    "meihua_time_cast": "analysis_context analysis_type calendar_context four_pillars interpretation meihua summary",
    "combine_four_gua": "analysis_type input_normalized summary tongshefa",
    "liuyao": "analysis_type calendar_context cast changed_code changed_hexagram classical_text_evidence current_code current_hexagram descriptions hexagram_info input_normalized lines liuyao_evidence moving_lines nongli pattern_flags patterns question summary",
    "canping": "analysis_context analysis_type benming calendar_context day_palace_branch dayun element four_pillars input_normalized liunian_series ming_gong part_name summary numerology_evidence canping_timing",
    "heluo": "analysis_context analysis_type calendar_context chart dayun four_pillars input_normalized judge solar_term summary numerology_evidence heluo_timing jiehou_evidence",
    "suzhan": "analysis_type astronomy chart input_normalized params rulesets sukuyo validation summary",
    "sukuyo_compatibility": "analysis_type status pair person1 person1_to_person2 person2 person2_to_person1 candidate_relation_analysis su27_basis rulesets interpretation_contract summary",
    "interpret_astrology_dice": "analysis_type chart diceChart house input_normalized planet question sign summary method_id symbolic_details rulesets rule_trace validation",
    "sanshi_combined_chart": "analysis_context analysis_type input_normalized liureng qimen subresults summary taiyi",
    "ziwei_birth_chart": "analysis_context analysis_type calendar_context four_pillars person_info ziwei_birth",
    "ziwei_timing": "analysis_context analysis_type birth_context person_info ziwei_horoscope",
    "ziwei_rules": "analysis_type engine focused_rules requested_year_stem rule_catalogue",
    "liuren_chart": "analysis_context analysis_type calendar_context four_pillars liureng",
    "liuren_yearly_timing": "analysis_context analysis_type calendar_context four_pillars liureng runyear",
    "qimen": "analysis_context analysis_type calendar_context four_pillars qimen",
    "taiyi": "analysis_context analysis_type calendar_context four_pillars taiyi",
    "jinkou": "analysis_context analysis_type calendar_context four_pillars jinkou liureng",
    "knowledge_catalog": "bundle_version domains provenance source",
    "knowledge_read": "bundle_version category citation domain key lines provenance query_normalized reference_only reference_details rendered_text source tips title",
    "astrology_chart": "angles apparent_model_positions aspect_evidence aspects balance_basis chart_profile classical classical_patterns element_balance fixed_stars houses modality_balance person_info planetary_hours planets summary",
    "thirteen_sector_chart": "angles aspect_evidence aspects balance_basis chart_profile classical classical_patterns element_balance fixed_stars houses modality_balance person_info planetary_hours planets summary thirteen_sectors sector_profile time_sensitivity",
    "hellenistic_chart": "angles aspect_evidence aspects balance_basis chart_profile classical classical_patterns element_balance fixed_stars hellenistic houses modality_balance person_info planetary_hours planets summary",
    "guolao_chart": "angles aspect_evidence aspects balance_basis chart_profile classical classical_patterns element_balance fixed_stars guolao houses modality_balance person_info planetary_hours planets summary",
    "vedic_chart": "angles aspect_evidence aspects balance_basis chart_profile classical classical_patterns element_balance fixed_stars houses india modality_balance person_info planetary_hours planets summary",
    "vimshottari_dasha": "analysis_context person_info india vimshottari summary",
    "hamburg_midpoint_chart": "base_chart chart_profile planets midpoint_aspects midpoints midpoint_analysis summary",
    "relationship_chart": "chart in_to_out_antiscia in_to_out_aspects in_to_out_contra_antiscia in_to_out_midpoint inner inner_chart marks_charts out_to_in_antiscia out_to_in_aspects out_to_in_contra_antiscia out_to_in_midpoint outer outer_chart relationship_profile summary synastry_aspects",
    "western_timing": "analysis_context analysis_type directions natal_reference returns summary time_lords transits",
    "solar_return": "analysis_context analysis_type engine natal_reference solar_return summary",
    "lunar_return": "analysis_context analysis_type engine lunar_return natal_reference summary",
    "transit_chart": "analysis_context analysis_type engine natal_reference summary transit_chart",
    "solar_arc": "analysis_context analysis_type engine natal_reference solar_arc summary",
    "chart_for_year": "analysis_context analysis_type chart_for_year engine natal_reference summary",
    "profection": "analysis_context analysis_type engine natal_reference profection summary",
    "primary_directions": "analysis_context analysis_type engine natal_reference primary_directions summary",
    "primary_directions_chart": "analysis_context analysis_type engine natal_reference primary_directions_chart summary",
    "zodiacal_releasing": "analysis_context analysis_type engine natal_reference summary zodiacal_releasing",
    "firdaria": "analysis_context analysis_type engine firdaria natal_reference summary",
    "decennials": "analysis_context analysis_type decennials engine natal_reference summary",
    "harmonic_chart": "analysis_context analysis_type engine harmonic_chart natal_reference summary",
    "planetary_ages": "analysis_context analysis_type engine natal_reference planetary_ages summary",
    "triplicity_ruler_periods": "analysis_context analysis_type engine natal_reference summary triplicity_rulers",
    "lunar_phase_progressions": "analysis_context analysis_type engine lunation_phase natal_reference summary",
    "bounds_directions": "analysis_context analysis_type distributions engine natal_reference summary",
    "balbillus_periods": "analysis_context analysis_type balbillus engine natal_reference summary",
    "numeric_aspect_periods": "analysis_context analysis_type engine keypoints natal_reference summary",
    "planetary_periods_129_years": "analysis_context analysis_type engine natal_reference summary yearsystem129",
    "planetary_arc_directions": "analysis_context analysis_type engine natal_reference planetary_arc summary",
    "persian_directions": "analysis_context analysis_type engine natal_reference persian_directed summary",
    "age_point": "age_point analysis_context analysis_type engine natal_reference summary",
    "sidereal_progressions": "analysis_context analysis_type engine natal_reference summary vedic_progression",
    "declination_progressions": "analysis_context analysis_type engine jaynes_declination natal_reference summary",
    "mundane_ingress_chart": "analysis_context analysis_type engine mundane summary",
    "planetary_returns": "analysis_context analysis_type engine extrareturns summary",
    "horary_chart": "analysis_context analysis_type calendar_conversion clock_conversion engine horary summary",
    "evaluate_election_time": "analysis_context analysis_type calendar_conversion clock_conversion election engine summary",
}


REQUIRED_OUTPUT_FIELDS = {
    "compare_bazi_sources": "four_pillars input_context current_calculation source_comparison summary",
    "bazi_overview": "four_pillars day_master",
    "bazi_birth_chart": "bazi_birth",
    "bazi_marriage": "marriage_analysis",
    "bazi_career": "career_analysis",
    "bazi_wealth": "wealth_analysis",
    "bazi_health": "health_analysis",
    "bazi_children": "children_analysis",
    "bazi_education": "education_analysis",
    "bazi_personality": "personality_analysis",
    "bazi_relatives": "relatives_analysis",
    "bazi_romance": "romance_analysis",
    "bazi_compatibility": "natal_contexts cross_chart_relations directional_ten_gods",
    "bazi_timing": "birth_pillars comprehensive_summary",
    "bazi_luck_cycles": "dayun_info",
    "bazi_yearly_timing": "liunian_info",
    "bazi_monthly_timing": "liuyue_info",
    "bazi_daily_timing": "liuri_info",
    "bazi_hourly_timing": "liushi_info",
    "solar_term_timeline": "jieqi_timeline",
    "solar_terms_for_year": "jieqi_year",
    "lunar_calendar_time": "nongli four_pillars",
    "gua_lookup": "result",
    "gua_meanings": "results",
    "meihua_time_cast": "meihua",
    "combine_four_gua": "tongshefa",
    "liuyao": "cast current_code current_hexagram",
    "canping": "benming numerology_evidence canping_timing",
    "heluo": "chart numerology_evidence",
    "suzhan": "analysis_type input_normalized params rulesets sukuyo validation summary",
    "sukuyo_compatibility": "person1 person2 rulesets status",
    "interpret_astrology_dice": "planet sign house",
    "sanshi_combined_chart": "qimen taiyi liureng subresults synthesis",
    "ziwei_birth_chart": "ziwei_birth",
    "ziwei_timing": "ziwei_horoscope",
    "ziwei_rules": "rule_catalogue",
    "liuren_chart": "liureng",
    "liuren_yearly_timing": "liureng runyear",
    "qimen": "qimen",
    "taiyi": "taiyi",
    "jinkou": "jinkou",
    "knowledge_catalog": "domains provenance",
    "knowledge_read": "lines provenance",
    "astrology_chart": "planets chart_profile",
    "thirteen_sector_chart": "planets chart_profile thirteen_sectors",
    "hellenistic_chart": "planets chart_profile hellenistic",
    "guolao_chart": "planets chart_profile guolao",
    "vedic_chart": "planets chart_profile india",
    "vimshottari_dasha": "analysis_context person_info india vimshottari summary",
    "hamburg_midpoint_chart": "base_chart midpoints chart_profile",
    "relationship_chart": "relationship_profile",
    "western_timing": "directions returns time_lords transits",
    "solar_return": "solar_return",
    "lunar_return": "lunar_return",
    "transit_chart": "transit_chart",
    "solar_arc": "solar_arc",
    "chart_for_year": "chart_for_year",
    "profection": "profection",
    "primary_directions": "primary_directions",
    "primary_directions_chart": "primary_directions_chart",
    "zodiacal_releasing": "zodiacal_releasing",
    "firdaria": "firdaria",
    "decennials": "decennials",
    "harmonic_chart": "harmonic_chart",
    "planetary_ages": "planetary_ages",
    "triplicity_ruler_periods": "triplicity_rulers",
    "lunar_phase_progressions": "lunation_phase",
    "bounds_directions": "distributions",
    "balbillus_periods": "balbillus",
    "numeric_aspect_periods": "keypoints",
    "planetary_periods_129_years": "yearsystem129",
    "planetary_arc_directions": "planetary_arc",
    "persian_directions": "persian_directed",
    "age_point": "age_point",
    "sidereal_progressions": "vedic_progression",
    "declination_progressions": "jaynes_declination",
    "mundane_ingress_chart": "mundane",
    "planetary_returns": "extrareturns",
    "horary_chart": "horary",
    "evaluate_election_time": "election",
    "fengshui_directions": "status layers rulesets coverage rule_trace",
    "fengshui_minggua": "status layers rulesets coverage rule_trace",
    "fengshui_bazhai": "status layers rulesets coverage rule_trace",
    "fengshui_jinsuo": "status layers rulesets coverage rule_trace",
    "fengshui_annual_stars": "status layers rulesets coverage rule_trace",
    "fengshui_monthly_stars": "status layers rulesets coverage rule_trace",
    "fengshui_xuankong_house_chart": "status layers rulesets coverage rule_trace",
    # Form-only assessment legitimately has layers={}; its typed FULL_FACT
    # still requires the map to be present and non-null in complete output.
    "fengshui_assess": "status rulesets coverage rule_trace",
}
