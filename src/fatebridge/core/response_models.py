"""Lazy registry mapping each tool name to its static Pydantic output contract."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel

__all__ = ["output_model_for"]

_OUTPUT_MODEL_REFS: dict[str, tuple[str, str]] = {
    "compare_bazi_sources": (
        "fatebridge.core.contracts.bazi",
        "CompareBaziSourcesOutput",
    ),
    "bazi_overview": ("fatebridge.core.contracts.bazi", "BaziOverviewOutput"),
    "bazi_birth_chart": ("fatebridge.core.contracts.bazi", "BaziBirthChartOutput"),
    "bazi_marriage": ("fatebridge.core.contracts.bazi", "BaziMarriageOutput"),
    "bazi_career": ("fatebridge.core.contracts.bazi", "BaziCareerOutput"),
    "bazi_wealth": ("fatebridge.core.contracts.bazi", "BaziWealthOutput"),
    "bazi_health": ("fatebridge.core.contracts.bazi", "BaziHealthOutput"),
    "bazi_children": ("fatebridge.core.contracts.bazi", "BaziChildrenOutput"),
    "bazi_education": ("fatebridge.core.contracts.bazi", "BaziEducationOutput"),
    "bazi_personality": ("fatebridge.core.contracts.bazi", "BaziPersonalityOutput"),
    "bazi_relatives": ("fatebridge.core.contracts.bazi", "BaziRelativesOutput"),
    "bazi_romance": ("fatebridge.core.contracts.bazi", "BaziRomanceOutput"),
    "bazi_compatibility": ("fatebridge.core.contracts.bazi", "BaziCompatibilityOutput"),
    "bazi_timing": ("fatebridge.core.contracts.bazi", "BaziTimingOutput"),
    "bazi_luck_cycles": ("fatebridge.core.contracts.bazi", "BaziLuckCyclesOutput"),
    "bazi_yearly_timing": ("fatebridge.core.contracts.bazi", "BaziYearlyTimingOutput"),
    "bazi_monthly_timing": (
        "fatebridge.core.contracts.bazi",
        "BaziMonthlyTimingOutput",
    ),
    "bazi_daily_timing": ("fatebridge.core.contracts.bazi", "BaziDailyTimingOutput"),
    "bazi_hourly_timing": ("fatebridge.core.contracts.bazi", "BaziHourlyTimingOutput"),
    "solar_term_timeline": (
        "fatebridge.core.contracts.bazi",
        "SolarTermTimelineOutput",
    ),
    "solar_terms_for_year": (
        "fatebridge.core.contracts.bazi",
        "SolarTermsForYearOutput",
    ),
    "lunar_calendar_time": (
        "fatebridge.core.contracts.bazi",
        "LunarCalendarTimeOutput",
    ),
    "ziwei_birth_chart": ("fatebridge.core.contracts.ziwei", "ZiweiBirthChartOutput"),
    "ziwei_timing": ("fatebridge.core.contracts.ziwei", "ZiweiTimingOutput"),
    "ziwei_rules": ("fatebridge.core.contracts.ziwei", "ZiweiRulesOutput"),
    "gua_lookup": ("fatebridge.core.contracts.divination", "GuaLookupOutput"),
    "meihua_time_cast": (
        "fatebridge.core.contracts.divination",
        "MeihuaTimeCastOutput",
    ),
    "meihua_cast": ("fatebridge.core.contracts.meihua", "MeihuaCastOutput"),
    "combine_four_gua": (
        "fatebridge.core.contracts.divination",
        "CombineFourGuaOutput",
    ),
    "liuyao": ("fatebridge.core.contracts.divination", "LiuyaoOutput"),
    "canping": ("fatebridge.core.contracts.numerology", "CanpingOutput"),
    "heluo": ("fatebridge.core.contracts.numerology", "HeluoOutput"),
    "liuren_chart": ("fatebridge.core.contracts.sanshi", "LiurenChartOutput"),
    "liuren_yearly_timing": (
        "fatebridge.core.contracts.sanshi",
        "LiurenYearlyTimingOutput",
    ),
    "jinkou": ("fatebridge.core.contracts.sanshi", "JinkouOutput"),
    "qimen": ("fatebridge.core.contracts.qimen", "QimenOutput"),
    "taiyi": ("fatebridge.core.contracts.taiyi", "TaiyiOutput"),
    "sanshi_combined_chart": (
        "fatebridge.core.contracts.sanshi",
        "SanshiCombinedChartOutput",
    ),
    "knowledge_catalog": (
        "fatebridge.core.contracts.knowledge",
        "KnowledgeCatalogOutput",
    ),
    "knowledge_read": ("fatebridge.core.contracts.knowledge", "KnowledgeReadOutput"),
    "place_lookup": ("fatebridge.core.contracts.knowledge", "PlaceLookupOutput"),
    "human_design": ("fatebridge.core.contracts.human_design", "HumanDesignOutput"),
    "ipip_big_five": ("fatebridge.core.contracts.psychometrics", "IpipBigFiveOutput"),
    "astrology_chart": ("fatebridge.core.contracts.astro", "AstrologyChartOutput"),
    "thirteen_sector_chart": (
        "fatebridge.core.contracts.astro",
        "ThirteenSectorChartOutput",
    ),
    "hellenistic_chart": ("fatebridge.core.contracts.astro", "HellenisticChartOutput"),
    "guolao_chart": ("fatebridge.core.contracts.astro", "GuolaoChartOutput"),
    "vedic_chart": ("fatebridge.core.contracts.astro", "VedicChartOutput"),
    "vimshottari_dasha": ("fatebridge.core.contracts.astro", "VimshottariDashaOutput"),
    "hamburg_midpoint_chart": (
        "fatebridge.core.contracts.astro",
        "HamburgMidpointChartOutput",
    ),
    "relationship_chart": (
        "fatebridge.core.contracts.astro",
        "RelationshipChartOutput",
    ),
    "interpret_astrology_dice": (
        "fatebridge.core.contracts.astro",
        "InterpretAstrologyDiceOutput",
    ),
    "western_timing": ("fatebridge.core.contracts.western", "WesternTimingOutput"),
    "solar_return": ("fatebridge.core.contracts.western", "SolarReturnOutput"),
    "lunar_return": ("fatebridge.core.contracts.western", "LunarReturnOutput"),
    "transit_chart": ("fatebridge.core.contracts.western", "TransitChartOutput"),
    "solar_arc": ("fatebridge.core.contracts.western", "SolarArcOutput"),
    "chart_for_year": ("fatebridge.core.contracts.western", "ChartForYearOutput"),
    "profection": ("fatebridge.core.contracts.western", "ProfectionOutput"),
    "primary_directions": (
        "fatebridge.core.contracts.western",
        "PrimaryDirectionsOutput",
    ),
    "primary_directions_chart": (
        "fatebridge.core.contracts.western",
        "PrimaryDirectionsChartOutput",
    ),
    "zodiacal_releasing": (
        "fatebridge.core.contracts.western",
        "ZodiacalReleasingOutput",
    ),
    "firdaria": ("fatebridge.core.contracts.western", "FirdariaOutput"),
    "decennials": ("fatebridge.core.contracts.western", "DecennialsOutput"),
    "harmonic_chart": ("fatebridge.core.contracts.western", "HarmonicChartOutput"),
    "planetary_ages": ("fatebridge.core.contracts.western", "PlanetaryAgesOutput"),
    "triplicity_ruler_periods": (
        "fatebridge.core.contracts.western",
        "TriplicityRulerPeriodsOutput",
    ),
    "lunar_phase_progressions": (
        "fatebridge.core.contracts.western",
        "LunarPhaseProgressionsOutput",
    ),
    "bounds_directions": (
        "fatebridge.core.contracts.western",
        "BoundsDirectionsOutput",
    ),
    "balbillus_periods": (
        "fatebridge.core.contracts.western",
        "BalbillusPeriodsOutput",
    ),
    "numeric_aspect_periods": (
        "fatebridge.core.contracts.western",
        "NumericAspectPeriodsOutput",
    ),
    "planetary_periods_129_years": (
        "fatebridge.core.contracts.western",
        "PlanetaryPeriods129YearsOutput",
    ),
    "planetary_arc_directions": (
        "fatebridge.core.contracts.western",
        "PlanetaryArcDirectionsOutput",
    ),
    "persian_directions": (
        "fatebridge.core.contracts.western",
        "PersianDirectionsOutput",
    ),
    "age_point": ("fatebridge.core.contracts.western", "AgePointOutput"),
    "sidereal_progressions": (
        "fatebridge.core.contracts.western",
        "SiderealProgressionsOutput",
    ),
    "declination_progressions": (
        "fatebridge.core.contracts.western",
        "DeclinationProgressionsOutput",
    ),
    "mundane_ingress_chart": (
        "fatebridge.core.contracts.western",
        "MundaneIngressChartOutput",
    ),
    "planetary_returns": (
        "fatebridge.core.contracts.western",
        "PlanetaryReturnsOutput",
    ),
    "horary_chart": ("fatebridge.core.contracts.western", "HoraryChartOutput"),
    "evaluate_election_time": (
        "fatebridge.core.contracts.western",
        "EvaluateElectionTimeOutput",
    ),
    "suzhan": ("fatebridge.core.contracts.sukuyo", "SuzhanOutput"),
    "sukuyo_compatibility": (
        "fatebridge.core.contracts.sukuyo",
        "SukuyoCompatibilityOutput",
    ),
    "fengshui_directions": ("fatebridge.core.fengshui.models", "FengshuiOutput"),
    "fengshui_minggua": ("fatebridge.core.fengshui.models", "FengshuiOutput"),
    "fengshui_bazhai": ("fatebridge.core.fengshui.models", "FengshuiOutput"),
    "fengshui_jinsuo": ("fatebridge.core.fengshui.models", "FengshuiOutput"),
    "fengshui_annual_stars": ("fatebridge.core.fengshui.models", "FengshuiOutput"),
    "fengshui_monthly_stars": ("fatebridge.core.fengshui.models", "FengshuiOutput"),
    "fengshui_xuankong_house_chart": (
        "fatebridge.core.fengshui.models",
        "FengshuiOutput",
    ),
    "fengshui_assess": ("fatebridge.core.fengshui.models", "FengshuiOutput"),
}


@lru_cache(maxsize=None)
def output_model_for(tool_name: str) -> type[BaseModel]:
    """Load a tool's static output contract lazily from its domain module."""
    ref = _OUTPUT_MODEL_REFS.get(tool_name)
    if ref is None:
        raise KeyError(f"Missing output contract for tool {tool_name}")
    module_name, attr_name = ref
    model = getattr(import_module(module_name), attr_name)
    base_model: type[BaseModel] = import_module("pydantic").BaseModel
    if not isinstance(model, type) or not issubclass(model, base_model):
        raise TypeError(
            f"Invalid output contract {module_name}.{attr_name} for tool {tool_name}"
        )
    return model
