"""BaZi flow analyses from the annual to the hourly layer."""

from __future__ import annotations

from typing import Any

from fatebridge.analysis.timing_effects import TimingEffectsAnalysis
from fatebridge.core.almanac import build_calendar_context, get_jieqi_year_grid
from fatebridge.core.bazi.calendar import ChangshengSchool, DutyProfile, ZiHourPolicy
from fatebridge.core.bazi.timing import TimingAnalysis
from fatebridge.services.birth_context import build_birth_computation_context
from fatebridge.services.timing_clock import resolve_analysis_moment
from fatebridge.services.timing_state import serialize_element_effects
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.errors import calculation_guard
from fatebridge.utils.formatting import format_clock_datetime


@calculation_guard("流年分析计算")
def calculate_liunian_analysis(
    person: PersonInfo,
    analysis_year: int,
    *,
    zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    changsheng_school: ChangshengSchool = "fire_earth_same_palace",
    duty_profile: DutyProfile = "sanming",
) -> dict[str, Any]:
    """流年专项分析：包含年柱干支、十神、纳音、与命局完整刑冲合害破暗合及流年神煞。"""
    birth_context = build_birth_computation_context(
        person,
        zi_hour_policy=zi_hour_policy,
        changsheng_school=changsheng_school,
        duty_profile=duty_profile,
    )
    normalized_birth_time = birth_context.normalized_birth_time
    birth_date = normalized_birth_time.corrected_datetime

    liunian_result = TimingEffectsAnalysis.analyze_liunian_effects(
        birth_context.birth_pillars,
        analysis_year,
        original_element_counts=birth_context.original_element_counts,
    )

    liunian_info = liunian_result["liunian_info"]
    element_effects = liunian_result["element_effects"]

    return {
        "analysis_type": "流年专项分析",
        "person_info": {
            "name": person.name,
            "target_year": analysis_year,
            "birth_datetime": format_clock_datetime(
                normalized_birth_time.input_datetime,
                include_seconds=person.birth_second is not None,
            ),
            "normalized_birth_datetime": format_clock_datetime(
                birth_date, include_seconds=person.birth_second is not None
            ),
            "time_adjustment": normalized_birth_time.as_dict(),
        },
        "calendar_context": birth_context.birth_calendar_context,
        "liunian": liunian_info,
        "element_effects": serialize_element_effects(element_effects),
    }


@calculation_guard("流月分析计算")
def calculate_liuyue_analysis(
    person: PersonInfo,
    analysis_year: int | None = None,
    analysis_month: int | None = None,
    analysis_day: int | None = None,
    analysis_hour: int | None = None,
    analysis_minute: int | None = None,
    *,
    zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    changsheng_school: ChangshengSchool = "fire_earth_same_palace",
    duty_profile: DutyProfile = "sanming",
) -> dict[str, Any]:
    """流月专项分析：包含节令月干支、十神、与命局及流年完整交互关系及神煞。"""
    birth_context = build_birth_computation_context(
        person,
        zi_hour_policy=zi_hour_policy,
        changsheng_school=changsheng_school,
        duty_profile=duty_profile,
    )
    normalized_birth_time = birth_context.normalized_birth_time
    birth_date = normalized_birth_time.corrected_datetime

    resolution = resolve_analysis_moment(
        "liuyue_analysis",
        normalized_birth_time.timezone,
        analysis_year=analysis_year,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
        analysis_hour=analysis_hour,
        analysis_minute=analysis_minute,
    )
    analysis_date = resolution.moment
    analysis_year, analysis_month, analysis_day = (
        analysis_date.year,
        analysis_date.month,
        analysis_date.day,
    )
    analysis_calendar_context = build_calendar_context(
        analysis_date,
        timezone_name=normalized_birth_time.timezone,
    )
    liuyue_info = TimingAnalysis.calculate_liuyue(
        analysis_year,
        analysis_month,
        target_day=analysis_day,
        timezone_name=normalized_birth_time.timezone,
        target_date=analysis_date,
    )
    liunian_analysis = TimingEffectsAnalysis.analyze_liunian_effects(
        birth_context.birth_pillars,
        analysis_year,
        original_element_counts=birth_context.original_element_counts,
        moment=analysis_date,
        timezone_name=normalized_birth_time.timezone,
    )
    liuyue_result = TimingEffectsAnalysis.analyze_liuyue_comprehensive(
        birth_context.birth_pillars,
        analysis_year,
        analysis_month,
        include_liunian=True,
        target_day=analysis_day,
        timezone_name=normalized_birth_time.timezone,
        target_date=analysis_date,
        liuyue_info=liuyue_info,
        liunian_analysis=liunian_analysis,
        original_element_counts=birth_context.original_element_counts,
    )

    liuyue_analysis = liuyue_result["liuyue_analysis"]
    liuyue_info = liuyue_analysis["liuyue_info"]
    detailed_analysis = liuyue_analysis["detailed_analysis"]
    element_effects = liuyue_analysis["element_effects"]
    liunian_info = liunian_analysis["liunian_info"]

    return {
        "analysis_type": "流月专项分析",
        "person_info": {
            "name": person.name,
            "analysis_date": analysis_date.strftime("%Y-%m-%d"),
            "analysis_datetime": analysis_date.strftime("%Y-%m-%d %H:%M"),
            "birth_datetime": format_clock_datetime(
                normalized_birth_time.input_datetime,
                include_seconds=person.birth_second is not None,
            ),
            "normalized_birth_datetime": format_clock_datetime(
                birth_date, include_seconds=person.birth_second is not None
            ),
            "time_adjustment": normalized_birth_time.as_dict(),
        },
        "calendar_context": birth_context.birth_calendar_context,
        "analysis_calendar": {"analysis_date_context": analysis_calendar_context},
        "liuyue": {
            "pillar": liuyue_info["pillar"],
            "stem": liuyue_info["stem"],
            "branch": liuyue_info["branch"],
            "element": liuyue_info["element"],
            "nayin": liuyue_info["nayin"],
            "solar_term_window": liuyue_info["solar_term_window"],
        },
        "detailed_analysis": {
            "stem_relation": detailed_analysis["shishen_analysis"]["stem_relation"],
            "hidden_stems": detailed_analysis["shishen_analysis"]["hidden_stems"],
            "branch_relations": detailed_analysis["branch_relations"],
            "shensha": detailed_analysis["shensha"],
        },
        "element_effects": serialize_element_effects(element_effects),
        "combined_effects": liuyue_result.get("combination_effects", {}),
        "liunian": liunian_info,
        "analysis_context": resolution.reference,
    }


@calculation_guard("流日分析计算")
def calculate_liuri_analysis(
    person: PersonInfo,
    analysis_year: int | None = None,
    analysis_month: int | None = None,
    analysis_day: int | None = None,
    analysis_hour: int | None = None,
    analysis_minute: int | None = None,
    *,
    zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    changsheng_school: ChangshengSchool = "fire_earth_same_palace",
    duty_profile: DutyProfile = "sanming",
) -> dict[str, Any]:
    """流日专项分析：包含流日干支、十神、完整地支交互（含刑害破暗合三合三会）与神煞。"""
    birth_context = build_birth_computation_context(
        person,
        zi_hour_policy=zi_hour_policy,
        changsheng_school=changsheng_school,
        duty_profile=duty_profile,
    )
    normalized_birth_time = birth_context.normalized_birth_time
    birth_date = normalized_birth_time.corrected_datetime

    resolution = resolve_analysis_moment(
        "liuri_analysis",
        normalized_birth_time.timezone,
        analysis_year=analysis_year,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
        analysis_hour=analysis_hour,
        analysis_minute=analysis_minute,
    )
    analysis_date = resolution.moment
    analysis_calendar_context = build_calendar_context(
        analysis_date,
        timezone_name=normalized_birth_time.timezone,
    )
    liuri_result = TimingEffectsAnalysis.analyze_liuri_effects(
        birth_context.birth_pillars,
        analysis_date,
        timezone_name=normalized_birth_time.timezone,
        original_element_counts=birth_context.original_element_counts,
        zi_hour_policy=zi_hour_policy,
    )
    liuri_info = liuri_result["liuri_info"]
    detailed = liuri_result["detailed_analysis"]

    return {
        "analysis_type": "流日专项分析",
        "person_info": {
            "name": person.name,
            "birth_datetime": format_clock_datetime(
                normalized_birth_time.input_datetime,
                include_seconds=person.birth_second is not None,
            ),
            "normalized_birth_datetime": format_clock_datetime(
                birth_date, include_seconds=person.birth_second is not None
            ),
            "analysis_date": analysis_date.strftime("%Y-%m-%d"),
            "analysis_datetime": analysis_date.strftime("%Y-%m-%d %H:%M"),
            "time_adjustment": normalized_birth_time.as_dict(),
        },
        "calendar_context": birth_context.birth_calendar_context,
        "analysis_calendar": {"analysis_date_context": analysis_calendar_context},
        "liuri": {
            "pillar": liuri_info["pillar"],
            "stem": liuri_info["stem"],
            "branch": liuri_info["branch"],
            "element": liuri_info["element"],
            "nayin": liuri_info["nayin"],
            "weekday": liuri_info["weekday"],
            "zi_hour_policy": liuri_info["zi_hour_policy"],
            "late_zi_rollover_applied": liuri_info["late_zi_rollover_applied"],
        },
        "detailed_analysis": {
            "stem_relation": detailed["shishen_analysis"]["stem_relation"],
            "hidden_stems": detailed["shishen_analysis"]["hidden_stems"],
            "branch_relations": detailed["branch_relations"],
            "shensha": detailed["shensha"],
        },
        "element_effects": serialize_element_effects(liuri_result["element_effects"]),
        "analysis_context": resolution.reference,
    }


@calculation_guard("流时分析计算")
def calculate_liushi_analysis(
    person: PersonInfo,
    analysis_year: int | None = None,
    analysis_month: int | None = None,
    analysis_day: int | None = None,
    analysis_hour: int | None = None,
    analysis_minute: int | None = None,
    *,
    zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    changsheng_school: ChangshengSchool = "fire_earth_same_palace",
    duty_profile: DutyProfile = "sanming",
) -> dict[str, Any]:
    """流时专项分析：包含流时干支、十神、完整地支交互及神煞。"""
    birth_context = build_birth_computation_context(
        person,
        zi_hour_policy=zi_hour_policy,
        changsheng_school=changsheng_school,
        duty_profile=duty_profile,
    )
    normalized_birth_time = birth_context.normalized_birth_time
    birth_date = normalized_birth_time.corrected_datetime

    resolution = resolve_analysis_moment(
        "liushi_analysis",
        normalized_birth_time.timezone,
        analysis_year=analysis_year,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
        analysis_hour=analysis_hour,
        analysis_minute=analysis_minute,
    )
    analysis_date = resolution.moment
    analysis_calendar_context = build_calendar_context(
        analysis_date,
        timezone_name=normalized_birth_time.timezone,
    )
    liushi_result = TimingEffectsAnalysis.analyze_liushi_effects(
        birth_context.birth_pillars,
        analysis_date,
        timezone_name=normalized_birth_time.timezone,
        original_element_counts=birth_context.original_element_counts,
        zi_hour_policy=zi_hour_policy,
    )
    liushi_info = liushi_result["liushi_info"]
    detailed_analysis = liushi_result["detailed_analysis"]

    return {
        "analysis_type": "流时专项分析",
        "person_info": {
            "name": person.name,
            "birth_datetime": format_clock_datetime(
                normalized_birth_time.input_datetime,
                include_seconds=person.birth_second is not None,
            ),
            "normalized_birth_datetime": format_clock_datetime(
                birth_date, include_seconds=person.birth_second is not None
            ),
            "analysis_datetime": analysis_date.strftime("%Y-%m-%d %H:%M"),
            "time_adjustment": normalized_birth_time.as_dict(),
        },
        "calendar_context": birth_context.birth_calendar_context,
        "analysis_calendar": {"analysis_date_context": analysis_calendar_context},
        "liushi": {
            "pillar": liushi_info["pillar"],
            "stem": liushi_info["stem"],
            "branch": liushi_info["branch"],
            "element": liushi_info["element"],
            "nayin": liushi_info["nayin"],
            "hour": liushi_info["hour"],
            "shichen": liushi_info["shichen"],
        },
        "detailed_analysis": {
            "stem_relation": detailed_analysis["shishen_analysis"]["stem_relation"],
            "hidden_stems": detailed_analysis["shishen_analysis"]["hidden_stems"],
            "branch_relations": detailed_analysis["branch_relations"],
            "shensha": detailed_analysis["shensha"],
        },
        "element_effects": serialize_element_effects(liushi_result["element_effects"]),
        "analysis_context": resolution.reference,
    }
