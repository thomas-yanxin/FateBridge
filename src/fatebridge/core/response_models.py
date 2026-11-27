"""Public output contracts, shared by REST, MCP and CLI discovery.

Business fields are optional because every tool supports arbitrary projections.
Validation does not dump models back into responses: absent fields stay absent,
extension fields and existing numeric values survive unchanged. Stable expert
facts use the same nested contracts in validation and transport discovery.
"""

from __future__ import annotations

from functools import lru_cache
from types import GenericAlias
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import BaseModel, JsonValue

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
    "output_fields_for",
    "output_model_for",
    "required_output_fields_for",
]


@lru_cache(maxsize=1)
def _contract_symbols() -> dict[str, Any]:
    """Import domain output contract modules lazily on first schema/validation demand."""
    from pydantic import JsonValue

    from fatebridge.core.contracts.output_astrodice import ASTRODICE_FIELDS
    from fatebridge.core.contracts.output_base import PartialOutput
    from fatebridge.core.contracts.output_bazi import DimensionOutput
    from fatebridge.core.contracts.output_bazi_anchors import TOPICS
    from fatebridge.core.contracts.output_bazi_birth import BaziBirth, DayMaster
    from fatebridge.core.contracts.output_bazi_evidence import EvidenceStructureProfile
    from fatebridge.core.contracts.output_chart_geometry import ChartPlanet
    from fatebridge.core.contracts.output_charts import CHART_FIELDS, CHART_TOOL_FIELDS
    from fatebridge.core.contracts.output_chinese import (
        CHINESE_FIELDS,
        CHINESE_TOOL_FIELDS,
    )
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
    from fatebridge.core.receipt_models import Object, RunMetadata

    field_types: dict[str, Any] = {
        "analysis_type": str,
        "aspects": list[JsonValue],
        "balance_basis": str,
        "bundle_version": int,
        "category": str,
        "challenges": list[JsonValue],
        "changed_code": str,
        "citation": str,
        "combined_effects": Object,
        "comprehensive_summary": str,
        "current_code": str,
        "day": str,
        "day_ganzhi": str,
        "day_int": int,
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
        "liunian": Object,
        "liuri": Object,
        "liushi": Object,
        "liuyue": Object,
        "lookup_mode": str,
        "midpoint_aspects": list[JsonValue],
        "midpoints": list[JsonValue],
        "ming_gong": str,
        "month": str,
        "month_ganzhi": str,
        "month_int": int,
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
        "time_ganzhi": str,
        "tips": list[JsonValue],
        "title": str,
        "year": int | str,
        "year_ganzhi": str,
        "year_jieqi": str,
    }

    return {
        "PartialOutput": PartialOutput,
        "ProjectedOutput": ProjectedOutput,
        "Object": Object,
        "RunMetadata": RunMetadata,
        "FIELD_TYPES": field_types,
        "ASTRODICE_FIELDS": ASTRODICE_FIELDS,
        "DimensionOutput": DimensionOutput,
        "TOPICS": TOPICS,
        "BaziBirth": BaziBirth,
        "DayMaster": DayMaster,
        "EvidenceStructureProfile": EvidenceStructureProfile,
        "ChartPlanet": ChartPlanet,
        "CHART_FIELDS": CHART_FIELDS,
        "CHART_TOOL_FIELDS": CHART_TOOL_FIELDS,
        "CHINESE_FIELDS": CHINESE_FIELDS,
        "CHINESE_TOOL_FIELDS": CHINESE_TOOL_FIELDS,
        "COMPATIBILITY_FIELDS": COMPATIBILITY_FIELDS,
        "Vimshottari": Vimshottari,
        "REFERENCE_TOOL_FIELDS": REFERENCE_TOOL_FIELDS,
        "RenAnchoredOutput": RenAnchoredOutput,
        "LiteralSourceInputContext": LiteralSourceInputContext,
        "SourceAnnotationComparison": SourceAnnotationComparison,
        "SourceCurrentCalculation": SourceCurrentCalculation,
        "AnalysisReference": AnalysisReference,
        "BirthTimeSensitivity": BirthTimeSensitivity,
        "TimingInteractions": TimingInteractions,
        "WESTERN_FIELDS": WESTERN_FIELDS,
        "Election": Election,
    }


_DIRECT_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "PartialOutput": ("fatebridge.core.contracts.output_base", "PartialOutput"),
    "ProjectedOutput": (
        "fatebridge.core.contracts.output_projection",
        "ProjectedOutput",
    ),
    "Object": ("fatebridge.core.receipt_models", "Object"),
    "RunMetadata": ("fatebridge.core.receipt_models", "RunMetadata"),
}

_LAZY_CONTRACT_EXPORTS = frozenset(
    {
        "FIELD_TYPES",
        "ASTRODICE_FIELDS",
        "DimensionOutput",
        "TOPICS",
        "BaziBirth",
        "DayMaster",
        "EvidenceStructureProfile",
        "ChartPlanet",
        "CHART_FIELDS",
        "CHART_TOOL_FIELDS",
        "CHINESE_FIELDS",
        "CHINESE_TOOL_FIELDS",
        "COMPATIBILITY_FIELDS",
        "Vimshottari",
        "REFERENCE_TOOL_FIELDS",
        "RenAnchoredOutput",
        "LiteralSourceInputContext",
        "SourceAnnotationComparison",
        "SourceCurrentCalculation",
        "AnalysisReference",
        "BirthTimeSensitivity",
        "TimingInteractions",
        "WESTERN_FIELDS",
        "Election",
    }
)


def __getattr__(name: str) -> Any:
    if name in _DIRECT_LAZY_EXPORTS:
        from importlib import import_module

        module_name, attr_name = _DIRECT_LAZY_EXPORTS[name]
        return getattr(import_module(module_name), attr_name)
    if name in _LAZY_CONTRACT_EXPORTS:
        return _contract_symbols()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


@lru_cache(maxsize=None)
def output_model_for(tool_name: str) -> type[BaseModel]:
    """Build each catalog's public schema lazily from explicit root-field contracts."""
    from importlib import import_module

    standalone_refs = {
        "human_design": (
            "fatebridge.core.contracts.output_human_design",
            "HumanDesignOutput",
        ),
        "meihua_cast": (
            "fatebridge.core.contracts.output_meihua_cast",
            "MeihuaCastOutput",
        ),
        "ipip_big_five": (
            "fatebridge.core.psychometrics.ipip_big_five",
            "IpipBigFiveOutput",
        ),
    }
    if tool_name in standalone_refs:
        mod_name, attr_name = standalone_refs[tool_name]
        model: type[BaseModel] = getattr(import_module(mod_name), attr_name)
        return model
    if tool_name.startswith("fengshui_"):
        fengshui_model: type[BaseModel] = getattr(
            import_module("fatebridge.core.fengshui.models"), "FengshuiOutput"
        )
        return fengshui_model

    if tool_name not in TOOL_FIELDS:
        raise KeyError(f"Missing output contract for tool {tool_name}")

    from pydantic import Field, JsonValue, create_model

    symbols = _contract_symbols()
    field_types = symbols["FIELD_TYPES"]
    fields: dict[str, Any] = {
        "run_metadata": (symbols["RunMetadata"] | None, None),
    }
    tool_fields = {
        **symbols["CHINESE_TOOL_FIELDS"].get(tool_name, {}),
        **symbols["CHART_TOOL_FIELDS"].get(tool_name, {}),
        **symbols["REFERENCE_TOOL_FIELDS"].get(tool_name, {}),
        **(
            symbols["ASTRODICE_FIELDS"]
            if tool_name == "interpret_astrology_dice"
            else {}
        ),
        **(
            symbols["COMPATIBILITY_FIELDS"] if tool_name == "bazi_compatibility" else {}
        ),
        **(
            {
                "analysis_context": symbols["LiteralSourceInputContext"],
                "current_calculation": symbols["SourceCurrentCalculation"],
                "source_comparison": symbols["SourceAnnotationComparison"],
            }
            if tool_name == "compare_bazi_sources"
            else {}
        ),
        **(
            {"analysis_context": symbols["AnalysisReference"]}
            if tool_name
            in {
                "bazi_timing",
                "bazi_luck_cycles",
                "bazi_monthly_timing",
                "bazi_daily_timing",
                "bazi_hourly_timing",
            }
            else {}
        ),
    }
    overrides = {
        **symbols["CHINESE_FIELDS"],
        **symbols["WESTERN_FIELDS"],
        **symbols["CHART_FIELDS"],
        **{
            f"{topic}_analysis": symbols["DimensionOutput"]
            for topic in symbols["TOPICS"]
        },
        "bazi_birth": symbols["BaziBirth"],
        "day_master": symbols["DayMaster"],
        "structure_profile": symbols["EvidenceStructureProfile"],
        "planets": GenericAlias(list, (symbols["ChartPlanet"],)),
        "election": symbols["Election"],
        "vimshottari": symbols["Vimshottari"],
        "interaction_analysis": symbols["TimingInteractions"],
        "birth_time_sensitivity": symbols["BirthTimeSensitivity"],
        **tool_fields,
    }
    root_fields = dict.fromkeys([*TOOL_FIELDS[tool_name].split(), *tool_fields])
    for field_name in root_fields:
        annotation = overrides.get(
            field_name, field_types.get(field_name, symbols["Object"])
        )
        metadata: dict[str, JsonValue] = {}
        if field_name == "planets":
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
        fields[field_name] = (
            annotation | None,
            Field(
                default=None,
                min_length=7 if field_name == "planets" else None,
                json_schema_extra=metadata or None,
            ),
        )
    name = "".join(part.title() for part in tool_name.split("_")) + "Output"
    projected_output = symbols["ProjectedOutput"]
    bases = (
        (projected_output, symbols["RenAnchoredOutput"])
        if tool_name
        in {"jinkou", "liuren_chart", "liuren_yearly_timing", "sanshi_combined_chart"}
        else (projected_output,)
    )
    return create_model(name, __base__=bases, **fields)


def output_fields_for(tool_name: str) -> list[str] | None:
    """Return root output field names without importing Pydantic output contracts."""
    if tool_name in TOOL_FIELDS:
        extra = EXTRA_TOOL_OUTPUT_FIELDS.get(tool_name, ())
        return [
            "run_metadata",
            *dict.fromkeys([*TOOL_FIELDS[tool_name].split(), *extra]),
        ]
    if tool_name in STANDALONE_TOOL_OUTPUT_FIELDS:
        return list(STANDALONE_TOOL_OUTPUT_FIELDS[tool_name])
    if tool_name.startswith("fengshui_"):
        return list(STANDALONE_TOOL_OUTPUT_FIELDS["fengshui"])
    return None


def required_output_fields_for(tool_name: str) -> tuple[str, ...]:
    """Non-null roots required before any transport projects the full result.

    This separate contract preserves projection-compatible public models. A
    missing declaration fails catalog assembly instead of leaving new tools
    silently unprotected. Required objects must contain a fact or explicit
    status; empty lists can still be legitimate domain results.
    """
    return tuple(REQUIRED_OUTPUT_FIELDS[tool_name].split())


EXTRA_TOOL_OUTPUT_FIELDS: dict[str, tuple[str, ...]] = {
    "sanshi_combined_chart": ("synthesis",),
}

STANDALONE_TOOL_OUTPUT_FIELDS: dict[str, tuple[str, ...]] = {
    "human_design": (
        "run_metadata",
        "engine",
        "method_id",
        "name",
        "birth_utc",
        "birth_clock_evidence",
        "design_utc",
        "design_solver",
        "time_scales",
        "calculation_policy",
        "activations",
        "variables",
        "bodygraph",
        "definition_bridging",
        "profile",
        "incarnation_cross",
        "depth_evidence",
        "line_fixings",
        "cycle_context",
        "cycle_summary",
        "time_sensitivity",
        "transit_overlay",
        "composite",
        "summary",
    ),
    "meihua_cast": (
        "run_metadata",
        "analysis_type",
        "analysis_context",
        "meihua",
        "interpretation",
        "summary",
    ),
    "ipip_big_five": (
        "run_metadata",
        "mode",
        "scale_id",
        "status",
        "domain_filter",
        "item_count",
        "items",
        "answered_count",
        "missing_count",
        "total_items",
        "domains",
        "item_breakdown",
        "provenance",
        "summary",
    ),
    "fengshui": (
        "analysis_type",
        "engine",
        "status",
        "layers",
        "coverage",
        "conflicts",
        "summary",
        "run_metadata",
        "palace_overlay",
        "layout_analysis",
    ),
}


TOOL_FIELDS = {
    "compare_bazi_sources": "analysis_context analysis_type current_calculation four_pillars source_comparison",
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
    "bazi_compatibility": "relationship_type person_info natal_contexts element_relationship nayin_comparison day_pillar_synergy element_complementarity cross_shensha cross_chart_relations directional_ten_gods",
    "bazi_timing": "analysis_calendar analysis_context analysis_type birth_time_sensitivity calendar_context combined_effects dayun four_pillars interaction_analysis liunian liuri liushi liuyue person_info",
    "bazi_luck_cycles": "analysis_context analysis_type birth_time_sensitivity calendar_context dayun element_effects person_info summary timing_context",
    "bazi_yearly_timing": "analysis_type calendar_context element_effects liunian person_info summary target_year_jieqi",
    "bazi_monthly_timing": "analysis_calendar analysis_context analysis_type calendar_context combined_effects detailed_analysis element_effects liunian liuyue person_info summary target_year_jieqi",
    "bazi_daily_timing": "analysis_calendar analysis_context analysis_type calendar_context element_effects liuri person_info summary",
    "bazi_hourly_timing": "analysis_calendar analysis_context analysis_type calendar_context detailed_analysis element_effects liushi person_info summary",
    "solar_term_timeline": "analysis_type calendar_context jieqi_timeline person_info summary target_year_jieqi",
    "solar_terms_for_year": "analysis_context analysis_type jieqi_year selected_jieqi summary year",
    "lunar_calendar_time": "analysis_context analysis_type calendar_context day day_ganzhi day_int four_pillars jiedelta jieqi leap lunar_calendar month month_ganzhi month_int nongli person_info summary time_ganzhi year_ganzhi year_jieqi",
    "gua_lookup": "analysis_type lookup_mode queries results summary",
    "meihua_time_cast": "analysis_context analysis_type calendar_context four_pillars interpretation meihua summary",
    "combine_four_gua": "analysis_context analysis_type summary tongshefa",
    "liuyao": "analysis_context analysis_type calendar_context cast changed_code changed_hexagram current_code current_hexagram descriptions hexagram_info lines liuyao_evidence moving_lines nongli pattern_flags patterns question summary",
    "canping": "analysis_context analysis_type benming calendar_context canping_timing day_palace_branch dayun element four_pillars liunian_series ming_gong numerology_evidence part_name summary",
    "heluo": "analysis_context analysis_type calendar_context chart dayun four_pillars heluo_timing jiehou_evidence judge numerology_evidence solar_term summary",
    "suzhan": "analysis_context analysis_type astronomy chart params sukuyo summary validation",
    "sukuyo_compatibility": "analysis_type candidate_relation_analysis pair person1 person1_to_person2 person2 person2_to_person1 status su27_basis summary",
    "interpret_astrology_dice": "analysis_context analysis_type chart dice_chart house method_id planet question sign summary symbolic_details validation",
    "sanshi_combined_chart": "analysis_context analysis_type liuren qimen subresults summary taiyi",
    "ziwei_birth_chart": "analysis_context analysis_type calendar_context four_pillars person_info ziwei_birth",
    "ziwei_timing": "analysis_context analysis_type birth_context person_info ziwei_horoscope",
    "ziwei_rules": "analysis_type engine focused_rules requested_year_stem rule_catalogue",
    "liuren_chart": "analysis_context analysis_type calendar_context four_pillars liuren",
    "liuren_yearly_timing": "analysis_context analysis_type calendar_context four_pillars liuren runyear",
    "qimen": "analysis_context analysis_type calendar_context four_pillars qimen",
    "taiyi": "analysis_context analysis_type calendar_context four_pillars taiyi",
    "jinkou": "analysis_context analysis_type calendar_context four_pillars jinkou",
    "knowledge_catalog": "bundle_version domains provenance source",
    "knowledge_read": "bundle_version category citation domain key lines provenance query_normalized reference_only reference_details rendered_text source tips title",
    "astrology_chart": "angles apparent_model_positions aspect_evidence aspects balance_basis chart_profile classical classical_patterns element_balance fixed_stars houses modality_balance person_info planetary_hours planets summary",
    "thirteen_sector_chart": "angles aspect_evidence aspects balance_basis chart_profile classical classical_patterns element_balance fixed_stars houses modality_balance person_info planetary_hours planets summary thirteen_sectors sector_profile time_sensitivity",
    "hellenistic_chart": "angles aspect_evidence aspects balance_basis chart_profile classical classical_patterns element_balance fixed_stars hellenistic houses modality_balance person_info planetary_hours planets summary",
    "guolao_chart": "angles chart_profile guolao houses person_info planets summary",
    "vedic_chart": "person_info summary vedic_chart",
    "vimshottari_dasha": "analysis_context ashtottari chara person_info summary vimshottari yogini",
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
    "triplicity_ruler_periods": "analysis_context analysis_type engine natal_reference summary triplicity_ruler_periods",
    "lunar_phase_progressions": "analysis_context analysis_type engine lunar_phase_progressions natal_reference summary",
    "bounds_directions": "analysis_context analysis_type bounds_directions engine natal_reference summary",
    "balbillus_periods": "analysis_context analysis_type balbillus engine natal_reference summary",
    "numeric_aspect_periods": "analysis_context analysis_type engine natal_reference numeric_aspect_periods summary",
    "planetary_periods_129_years": "analysis_context analysis_type engine natal_reference planetary_periods_129_years summary",
    "planetary_arc_directions": "analysis_context analysis_type engine natal_reference planetary_arc summary",
    "persian_directions": "analysis_context analysis_type engine natal_reference persian_directions summary",
    "age_point": "age_point analysis_context analysis_type engine natal_reference summary",
    "sidereal_progressions": "analysis_context analysis_type engine natal_reference sidereal_progressions summary",
    "declination_progressions": "analysis_context analysis_type declination_progressions engine natal_reference summary",
    "mundane_ingress_chart": "analysis_context analysis_type engine mundane_ingress_chart summary",
    "planetary_returns": "analysis_context analysis_type engine planetary_returns summary",
    "horary_chart": "analysis_context analysis_type calendar_conversion clock_conversion engine horary_chart summary",
    "evaluate_election_time": "analysis_context analysis_type calendar_conversion clock_conversion election engine summary",
}


REQUIRED_OUTPUT_FIELDS = {
    "compare_bazi_sources": "analysis_context current_calculation four_pillars source_comparison",
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
    "bazi_timing": "four_pillars dayun liunian interaction_analysis",
    "bazi_luck_cycles": "dayun",
    "bazi_yearly_timing": "liunian",
    "bazi_monthly_timing": "liuyue",
    "bazi_daily_timing": "liuri",
    "bazi_hourly_timing": "liushi",
    "solar_term_timeline": "jieqi_timeline",
    "solar_terms_for_year": "jieqi_year",
    "lunar_calendar_time": "nongli four_pillars",
    "gua_lookup": "results",
    "meihua_time_cast": "meihua",
    "combine_four_gua": "tongshefa",
    "liuyao": "cast current_code current_hexagram",
    "canping": "benming numerology_evidence canping_timing",
    "heluo": "chart numerology_evidence",
    "suzhan": "analysis_context analysis_type params sukuyo summary validation",
    "sukuyo_compatibility": "person1 person2 status",
    "interpret_astrology_dice": "planet sign house",
    "sanshi_combined_chart": "qimen taiyi liuren subresults synthesis",
    "ziwei_birth_chart": "ziwei_birth",
    "ziwei_timing": "ziwei_horoscope",
    "ziwei_rules": "rule_catalogue",
    "liuren_chart": "liuren",
    "liuren_yearly_timing": "liuren runyear",
    "qimen": "qimen",
    "taiyi": "taiyi",
    "jinkou": "jinkou",
    "knowledge_catalog": "domains provenance",
    "knowledge_read": "lines provenance",
    "astrology_chart": "planets chart_profile",
    "thirteen_sector_chart": "planets chart_profile thirteen_sectors",
    "hellenistic_chart": "planets chart_profile hellenistic",
    "guolao_chart": "guolao",
    "vedic_chart": "vedic_chart",
    "vimshottari_dasha": "analysis_context person_info vimshottari summary",
    "hamburg_midpoint_chart": "base_chart midpoints chart_profile",
    "relationship_chart": "relationship_profile",
    "western_timing": "analysis_context natal_reference summary",
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
    "triplicity_ruler_periods": "triplicity_ruler_periods",
    "lunar_phase_progressions": "lunar_phase_progressions",
    "bounds_directions": "bounds_directions",
    "balbillus_periods": "balbillus",
    "numeric_aspect_periods": "numeric_aspect_periods",
    "planetary_periods_129_years": "planetary_periods_129_years",
    "planetary_arc_directions": "planetary_arc",
    "persian_directions": "persian_directions",
    "age_point": "age_point",
    "sidereal_progressions": "sidereal_progressions",
    "declination_progressions": "declination_progressions",
    "mundane_ingress_chart": "mundane_ingress_chart",
    "planetary_returns": "planetary_returns",
    "horary_chart": "horary_chart",
    "evaluate_election_time": "election",
    "fengshui_directions": "status layers coverage",
    "fengshui_minggua": "status layers coverage",
    "fengshui_bazhai": "status layers coverage",
    "fengshui_jinsuo": "status layers coverage",
    "fengshui_annual_stars": "status layers coverage",
    "fengshui_monthly_stars": "status layers coverage",
    "fengshui_xuankong_house_chart": "status layers coverage",
    # Form-only assessment legitimately has layers={}; its typed FULL_FACT
    # still requires the map to be present and non-null in complete output.
    "fengshui_assess": "status coverage",
}
