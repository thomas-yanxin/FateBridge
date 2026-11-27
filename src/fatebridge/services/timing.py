"""Compute BaZi time pillars, Dayun/小运, and timing interactions."""

from __future__ import annotations

from typing import Any

from fatebridge.analysis.timing_effects import TimingEffectsAnalysis
from fatebridge.core.almanac import (
    build_calendar_context,
    get_jieqi_year_grid,
)
from fatebridge.core.bazi.calendar import ChangshengSchool, DutyProfile, ZiHourPolicy
from fatebridge.core.bazi.policies import YearBoundaryPolicy
from fatebridge.services.birth_context import build_birth_computation_context
from fatebridge.services.timing_clock import (
    AnalysisClockReference,
    age_only_reference,
    resolve_analysis_moment,
)
from fatebridge.services.timing_periods import (
    calculate_liunian_analysis,
    calculate_liuri_analysis,
    calculate_liushi_analysis,
    calculate_liuyue_analysis,
)
from fatebridge.services.timing_state import (
    build_current_timing_state,
    calculate_analysis_age,
    enrich_jieqi_timeline,
    enrich_liuyue_timeline,
    serialize_element_effects,
)
from fatebridge.services.timing_uncertainty import analyze_birth_time_range
from fatebridge.utils.birth_input import PersonInfo, normalize_gender
from fatebridge.utils.data import get_shishen
from fatebridge.utils.errors import calculation_guard
from fatebridge.utils.formatting import create_pillar_dict, format_clock_datetime

__all__ = [
    "calculate_comprehensive_timing",
    "calculate_dayun_analysis",
    "calculate_jieqi_timeline_analysis",
    "calculate_liunian_analysis",
    "calculate_liuri_analysis",
    "calculate_liushi_analysis",
    "calculate_liuyue_analysis",
]


@calculation_guard("时运分析计算")
def calculate_comprehensive_timing(
    person: PersonInfo,
    analysis_year: int | None = None,
    analysis_month: int | None = None,
    analysis_age: int | None = None,
    analysis_day: int | None = None,
    analysis_hour: int | None = None,
    analysis_minute: int | None = None,
    birth_time_uncertainty_minutes: int | None = None,
    *,
    year_boundary_policy: YearBoundaryPolicy = "lichun",
    zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    changsheng_school: ChangshengSchool = "fire_earth_same_palace",
    duty_profile: DutyProfile = "sanming",
    include_timelines: bool = False,
) -> dict[str, Any]:
    """综合时运分析：大运（或起运前小运+童限）、流年、流月、流日、流时及完整干支交互。"""
    birth_context = build_birth_computation_context(
        person,
        zi_hour_policy=zi_hour_policy,
        changsheng_school=changsheng_school,
        duty_profile=duty_profile,
    )
    normalized_birth_time = birth_context.normalized_birth_time
    input_birth_datetime = normalized_birth_time.input_datetime
    birth_date = normalized_birth_time.corrected_datetime

    resolution = resolve_analysis_moment(
        "timing_analysis",
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
    timing_result = build_current_timing_state(
        birth_context,
        analysis_date=analysis_date,
        analysis_age=analysis_age,
        year_boundary_policy=year_boundary_policy,
    )
    current_age = timing_result["current_age"]

    analysis_calendar: dict[str, Any] = {
        "analysis_date_context": analysis_calendar_context,
    }
    if include_timelines:
        analysis_calendar["analysis_year_jieqi"] = get_jieqi_year_grid(
            analysis_date.year, normalized_birth_time.timezone
        )
        analysis_calendar["liuyue_timeline"] = enrich_liuyue_timeline(
            birth_context, target_year=analysis_date.year
        )
        analysis_calendar["jieqi_timeline"] = enrich_jieqi_timeline(
            birth_context, target_year=analysis_date.year
        )

    result: dict[str, Any] = {
        "analysis_type": "综合时运分析",
        "person_info": {
            "name": person.name,
            "birth_datetime": format_clock_datetime(
                input_birth_datetime, include_seconds=person.birth_second is not None
            ),
            "normalized_birth_datetime": format_clock_datetime(
                birth_date, include_seconds=person.birth_second is not None
            ),
            "gender": normalize_gender(person.gender),
            "analysis_date": analysis_date.strftime("%Y-%m-%d"),
            "analysis_datetime": analysis_date.strftime("%Y-%m-%d %H:%M"),
            "current_age": current_age,
            "zi_hour_policy": zi_hour_policy,
            "time_adjustment": normalized_birth_time.as_dict(),
        },
        "four_pillars": create_pillar_dict(birth_context.birth_pillars),
        "calendar_context": birth_context.birth_calendar_context,
        "analysis_calendar": analysis_calendar,
    }

    dayun_analysis = timing_result["dayun_analysis"]
    if "dayun_info" in dayun_analysis:
        dayun_info = dayun_analysis["dayun_info"]
        age_info = dayun_analysis["age_info"]
        dayun_section: dict[str, Any] = {
            "status": "active",
            "current_dayun": dayun_info["pillar"],
            "stem": dayun_info["stem"],
            "branch": dayun_info["branch"],
            "stem_ten_god": dayun_info["stem_ten_god"],
            "nayin": dayun_info["nayin"],
            "start_age": age_info["start_age"],
            "start_age_precise": age_info.get("start_age_precise"),
            "start_age_unrounded": age_info.get("start_age_unrounded"),
            "dayun_age": age_info["dayun_age"],
            "years_in_period": age_info["years_in_period"],
            "direction": age_info.get("direction"),
            "selection_basis": age_info["selection_basis"],
            "start_at": dayun_info["start_at"],
            "end_at": dayun_info["end_at"],
            "child_limit": dayun_analysis["child_limit"],
            "natal_relations": dayun_info["natal_relations"],
            "shensha": dayun_info["shensha"],
            "element_effects": serialize_element_effects(
                dayun_analysis["element_effects"]
            ),
        }
        result["dayun"] = dayun_section
    elif dayun_analysis.get("status") == "before_dayun":
        result["dayun"] = {
            "status": "before_dayun",
            "current_dayun": None,
            "child_limit": dayun_analysis["child_limit"],
            "xiaoyun": dayun_analysis["xiaoyun_info"],
            "xiaoyun_timeline": dayun_analysis["xiaoyun_timeline"],
            "first_dayun": dayun_analysis["first_dayun"],
            "element_effects": serialize_element_effects(
                dayun_analysis["element_effects"]
            ),
        }
    else:
        result["dayun"] = {
            "status": dayun_analysis.get("status"),
            "current_dayun": None,
            "message": dayun_analysis.get("message", "大运信息不可用"),
        }
    result["dayun"]["timing_context"] = dayun_analysis["timing_context"]

    liunian_analysis = timing_result["liunian_analysis"]
    liunian_info = liunian_analysis["liunian_info"]
    result["liunian"] = {
        **liunian_info,
        "element_effects": serialize_element_effects(
            liunian_analysis["element_effects"]
        ),
    }

    liuyue_analysis = timing_result["liuyue_analysis"]
    liuyue_info = liuyue_analysis["liuyue_info"]
    result["liuyue"] = {
        "pillar": liuyue_info["pillar"],
        "stem": liuyue_info["stem"],
        "branch": liuyue_info["branch"],
        "nayin": liuyue_info["nayin"],
        "detailed_analysis": liuyue_analysis["detailed_analysis"],
    }

    liuri_analysis = timing_result["liuri_analysis"]
    liuri_info = liuri_analysis["liuri_info"]
    result["liuri"] = {
        "pillar": liuri_info["pillar"],
        "stem": liuri_info["stem"],
        "branch": liuri_info["branch"],
        "nayin": liuri_info["nayin"],
        "weekday": liuri_info["weekday"],
        "detailed_analysis": liuri_analysis["detailed_analysis"],
    }

    liushi_analysis = timing_result["liushi_analysis"]
    liushi_info = liushi_analysis["liushi_info"]
    result["liushi"] = {
        "pillar": liushi_info["pillar"],
        "stem": liushi_info["stem"],
        "branch": liushi_info["branch"],
        "nayin": liushi_info["nayin"],
        "hour": liushi_info["hour"],
        "detailed_analysis": liushi_analysis["detailed_analysis"],
    }

    result["combined_effects"] = serialize_element_effects(
        timing_result["combined_effects"]
    )
    result["interaction_analysis"] = timing_result["interaction_analysis"]
    dayun_summary = result["dayun"].get("current_dayun") or (
        result["dayun"].get("xiaoyun", {}).get("pillar")
        if result["dayun"].get("status") == "before_dayun"
        else None
    )
    result["summary"] = {
        "analysis_datetime": result["person_info"]["analysis_datetime"],
        "current_age": current_age,
        "dayun": dayun_summary,
        "liunian": result["liunian"]["pillar"],
        "liuyue": result["liuyue"]["pillar"],
        "liuri": result["liuri"]["pillar"],
        "liushi": result["liushi"]["pillar"],
        "overall_effect": result["combined_effects"].get("overall_effect"),
    }
    if birth_time_uncertainty_minutes is not None:
        result["birth_time_sensitivity"] = analyze_birth_time_range(
            person,
            birth_time_uncertainty_minutes,
            analysis_moment=analysis_date if analysis_age is None else None,
            analysis_age=analysis_age,
        )
    result["analysis_context"] = resolution.reference
    return result


@calculation_guard("大运分析计算")
def calculate_dayun_analysis(
    person: PersonInfo,
    analysis_age: int | None = None,
    analysis_year: int | None = None,
    analysis_month: int | None = None,
    analysis_day: int | None = None,
    analysis_hour: int | None = None,
    analysis_minute: int | None = None,
    birth_time_uncertainty_minutes: int | None = None,
    *,
    zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    changsheng_school: ChangshengSchool = "fire_earth_same_palace",
    duty_profile: DutyProfile = "sanming",
) -> dict[str, Any]:
    """大运专项分析：包含起运童限(X年Y月Z日)、交运时刻与干支、十年一运及起运前小运。"""
    birth_context = build_birth_computation_context(
        person,
        zi_hour_policy=zi_hour_policy,
        changsheng_school=changsheng_school,
        duty_profile=duty_profile,
    )
    normalized_birth_time = birth_context.normalized_birth_time
    birth_date = normalized_birth_time.corrected_datetime

    date_parts = (
        analysis_year,
        analysis_month,
        analysis_day,
        analysis_hour,
        analysis_minute,
    )
    if analysis_age is not None and any(part is not None for part in date_parts):
        raise ValueError("analysis_age年龄参考不能与analysis_*分析日期同时使用")
    analysis_moment = None
    analysis_reference: AnalysisClockReference = age_only_reference()
    if analysis_age is None:
        resolution = resolve_analysis_moment(
            "dayun_analysis",
            normalized_birth_time.timezone,
            analysis_year=analysis_year,
            analysis_month=analysis_month,
            analysis_day=analysis_day,
            analysis_hour=analysis_hour,
            analysis_minute=analysis_minute,
        )
        analysis_moment = resolution.moment
        analysis_reference = resolution.reference
        analysis_age = calculate_analysis_age(
            normalized_birth_time.input_datetime, analysis_moment
        )

    dayun_result = TimingEffectsAnalysis.analyze_dayun_effects(
        birth_context.birth_pillars,
        normalized_birth_time.input_datetime,
        person.gender,
        analysis_age,
        timezone_name=normalized_birth_time.timezone,
        original_element_counts=birth_context.original_element_counts,
        analysis_moment=analysis_moment,
    )

    result: dict[str, Any] = {
        "analysis_type": "大运专项分析",
        "person_info": {
            "name": person.name,
            "gender": person.gender,
            "analysis_age": analysis_age,
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
    }

    if "dayun_info" in dayun_result:
        dayun_info = dayun_result["dayun_info"]
        age_info = dayun_result["age_info"]
        result["dayun"] = {
            "status": "active",
            "current_dayun": dayun_info["pillar"],
            "stem": dayun_info["stem"],
            "branch": dayun_info["branch"],
            "stem_ten_god": dayun_info["stem_ten_god"],
            "nayin": dayun_info["nayin"],
            "start_age": age_info["start_age"],
            "start_age_precise": age_info.get("start_age_precise"),
            "start_age_unrounded": age_info.get("start_age_unrounded"),
            "dayun_age": age_info["dayun_age"],
            "years_in_period": age_info["years_in_period"],
            "direction": age_info.get("direction"),
            "selection_basis": age_info["selection_basis"],
            "start_at": dayun_info["start_at"],
            "end_at": dayun_info["end_at"],
            "child_limit": dayun_result["child_limit"],
            "natal_relations": dayun_info["natal_relations"],
            "shensha": dayun_info["shensha"],
        }
        result["element_effects"] = serialize_element_effects(
            dayun_result["element_effects"]
        )
    elif dayun_result.get("status") == "before_dayun":
        result["dayun"] = {
            "status": "before_dayun",
            "current_dayun": None,
            "child_limit": dayun_result["child_limit"],
            "xiaoyun": dayun_result["xiaoyun_info"],
            "xiaoyun_timeline": dayun_result["xiaoyun_timeline"],
            "first_dayun": dayun_result["first_dayun"],
            "first_start_at": dayun_result["timing_context"]["timeline"]["start_at"],
        }
        result["element_effects"] = serialize_element_effects(
            dayun_result["element_effects"]
        )
    else:
        result["dayun"] = {
            "status": dayun_result.get("status"),
            "current_dayun": None,
            "message": dayun_result.get("message", "大运信息不可用"),
        }

    result["timing_context"] = dayun_result["timing_context"]
    timeline = dayun_result["timing_context"].get("timeline")
    if isinstance(timeline, dict) and isinstance(timeline.get("periods"), list):
        day_stem = birth_context.birth_pillars["day"][0]
        result["dayun_timeline"] = [
            {
                "period": period["period"],
                "pillar": period["pillar"],
                "stem": period["stem"],
                "branch": period["branch"],
                "stem_ten_god": get_shishen(day_stem, period["stem"]),
                "nayin": period["nayin"],
                "age_range": period["age_range"],
                "start_at": period.get("start_at"),
                "end_at": period.get("end_at"),
            }
            for period in timeline["periods"]
        ]
    if birth_time_uncertainty_minutes is not None:
        result["birth_time_sensitivity"] = analyze_birth_time_range(
            person,
            birth_time_uncertainty_minutes,
            analysis_moment=analysis_moment,
            analysis_age=analysis_age if analysis_moment is None else None,
        )
    result["analysis_context"] = analysis_reference
    return result


@calculation_guard("节气时间轴分析计算")
def calculate_jieqi_timeline_analysis(
    person: PersonInfo,
    analysis_year: int | None = None,
    *,
    zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    changsheng_school: ChangshengSchool = "fire_earth_same_palace",
    duty_profile: DutyProfile = "sanming",
) -> dict[str, Any]:
    birth_context = build_birth_computation_context(
        person,
        zi_hour_policy=zi_hour_policy,
        changsheng_school=changsheng_school,
        duty_profile=duty_profile,
    )
    normalized_birth_time = birth_context.normalized_birth_time
    birth_date = normalized_birth_time.corrected_datetime
    resolution = resolve_analysis_moment(
        "jieqi_timeline",
        normalized_birth_time.timezone,
        analysis_year=analysis_year,
    )
    target_year = resolution.moment.year
    jieqi_timeline = enrich_jieqi_timeline(birth_context, target_year=target_year)
    target_year_jieqi = get_jieqi_year_grid(target_year, normalized_birth_time.timezone)
    return {
        "analysis_type": "节气节点时间轴分析",
        "person_info": {
            "name": person.name,
            "target_year": target_year,
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
        "target_year_jieqi": target_year_jieqi,
        "jieqi_timeline": jieqi_timeline,
        "analysis_context": resolution.reference,
    }
