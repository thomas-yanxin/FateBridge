"""Compute BaZi time pillars, term boundaries, and pillar relationships."""

from copy import deepcopy
from typing import Any

from fatebridge.analysis.timing_effects import TimingEffectsAnalysis
from fatebridge.core.almanac import (
    build_calendar_context,
    current_local_datetime,
    get_jieqi_year_grid,
)
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
) -> dict[str, Any]:
    """
    计算时运分析，包括大运、流年、流月、流日、流时的影响分析
    """
    birth_context = build_birth_computation_context(person)
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
    analysis_year, analysis_month = analysis_date.year, analysis_date.month
    analysis_calendar_context = build_calendar_context(
        analysis_date,
        timezone_name=normalized_birth_time.timezone,
    )
    analysis_year_jieqi = get_jieqi_year_grid(
        analysis_year, normalized_birth_time.timezone
    )
    liuyue_timeline = enrich_liuyue_timeline(
        birth_context,
        target_year=analysis_year,
    )
    jieqi_timeline = enrich_jieqi_timeline(
        birth_context,
        target_year=analysis_year,
    )
    timing_result = build_current_timing_state(
        birth_context,
        analysis_date=analysis_date,
        analysis_age=analysis_age,
    )
    current_age = timing_result["current_age"]

    result: dict[str, Any] = {
        "analysis_type": "综合时运分析",
        "personal_info": {
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
            "time_adjustment": normalized_birth_time.as_dict(),
        },
        "birth_pillars": create_pillar_dict(birth_context.birth_pillars),
        "calendar_context": birth_context.birth_calendar_context,
        "analysis_calendar": {
            "analysis_date_context": analysis_calendar_context,
            "analysis_year_jieqi": analysis_year_jieqi,
            "liuyue_timeline": liuyue_timeline,
            "jieqi_timeline": jieqi_timeline,
        },
    }

    dayun_analysis = timing_result["dayun_analysis"]
    if "dayun_info" in dayun_analysis:
        dayun_info = dayun_analysis["dayun_info"]
        age_info = dayun_analysis["age_info"]
        dayun_section: dict[str, Any] = {
            "current_dayun": dayun_info["pillar"],
            "stem": dayun_info["stem"],
            "branch": dayun_info["branch"],
            "start_age": age_info["start_age"],
            "start_age_precise": age_info.get("start_age_precise"),
            "start_age_unrounded": age_info.get("start_age_unrounded"),
            "dayun_age": age_info["dayun_age"],
            "years_in_period": age_info["years_in_period"],
            "direction": age_info.get("direction"),
            "selection_basis": age_info["selection_basis"],
            "elapsed_year_basis": age_info["elapsed_year_basis"],
            "start_at": dayun_info["start_at"],
            "end_at": dayun_info["end_at"],
            "summary": dayun_analysis["summary"],
        }
        # Preserve structured element changes for clients reading the combined
        # timing response, without requiring them to parse summary text.
        if "element_effects" in dayun_analysis:
            dayun_section["element_effects"] = serialize_element_effects(
                dayun_analysis["element_effects"]
            )
        result["dayun_analysis"] = dayun_section
    else:
        result["dayun_analysis"] = {
            "error": dayun_analysis.get("message", "大运信息不可用"),
            "status": dayun_analysis.get("status"),
        }
    result["dayun_analysis"]["timing_context"] = dayun_analysis["timing_context"]

    liunian_analysis = timing_result["liunian_analysis"]
    liunian_info = liunian_analysis["liunian_info"]
    liunian_section: dict[str, Any] = {
        "pillar": liunian_info["pillar"],
        "stem": liunian_info["stem"],
        "branch": liunian_info["branch"],
        "summary": liunian_analysis["summary"],
    }
    if "element_effects" in liunian_analysis:
        liunian_section["element_effects"] = serialize_element_effects(
            liunian_analysis["element_effects"]
        )
    result["liunian_analysis"] = liunian_section

    liuyue_analysis = timing_result["liuyue_analysis"]
    liuyue_info = liuyue_analysis["liuyue_info"]
    result["liuyue_analysis"] = {
        "pillar": liuyue_info["pillar"],
        "stem": liuyue_info["stem"],
        "branch": liuyue_info["branch"],
        "summary": liuyue_analysis["summary"],
    }

    liuri_analysis = timing_result["liuri_analysis"]
    liuri_info = liuri_analysis["liuri_info"]
    result["liuri_analysis"] = {
        "pillar": liuri_info["pillar"],
        "stem": liuri_info["stem"],
        "branch": liuri_info["branch"],
        "summary": liuri_analysis["summary"],
    }

    liushi_analysis = timing_result["liushi_analysis"]
    liushi_info = liushi_analysis["liushi_info"]
    result["liushi_analysis"] = {
        "pillar": liushi_info["pillar"],
        "stem": liushi_info["stem"],
        "branch": liushi_info["branch"],
        "hour": liushi_info["hour"],
        "summary": liushi_analysis["summary"],
    }

    combined_effects = timing_result["combined_effects"]
    result["combined_effects"] = serialize_element_effects(combined_effects)
    result["interaction_analysis"] = timing_result["interaction_analysis"]
    if birth_time_uncertainty_minutes is not None:
        result["birth_time_sensitivity"] = analyze_birth_time_range(
            person,
            birth_time_uncertainty_minutes,
            analysis_moment=analysis_date if analysis_age is None else None,
            analysis_age=analysis_age,
        )

    result["comprehensive_summary"] = timing_result["comprehensive_summary"]

    # Keep every current-period fact/status. The starter view omits only the
    # complete twelve-period table; full JSON retains its original timeline.
    first_view = deepcopy(result["dayun_analysis"])
    context = first_view.get("timing_context")
    timeline = context.get("timeline") if isinstance(context, dict) else None
    if isinstance(timeline, dict):
        timeline.pop("periods", None)
    result["dayun_analysis"]["first_view"] = first_view
    result["analysis_reference"] = resolution.reference
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
) -> dict[str, Any]:
    """
    大运分析工具 - 专门分析指定年龄的大运情况
    """
    birth_context = build_birth_computation_context(person)
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
        "personal_info": {
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

        result["dayun_info"] = {
            "current_dayun": dayun_info["pillar"],
            "stem": dayun_info["stem"],
            "branch": dayun_info["branch"],
            "start_age": age_info["start_age"],
            # note (dayun): Retain the raw age behind the two-decimal display and integer ceiling.
            "start_age_precise": age_info.get("start_age_precise"),
            "start_age_unrounded": age_info.get("start_age_unrounded"),
            "dayun_age": age_info["dayun_age"],
            "years_in_period": age_info["years_in_period"],
            "direction": age_info.get("direction"),
            "selection_basis": age_info["selection_basis"],
            "elapsed_year_basis": age_info["elapsed_year_basis"],
            "start_at": dayun_info["start_at"],
            "end_at": dayun_info["end_at"],
        }

        result["element_effects"] = serialize_element_effects(
            dayun_result["element_effects"]
        )

        result["summary"] = dayun_result["summary"]
    else:
        result["summary"] = dayun_result.get("message", "大运信息不可用")
        result["dayun_info"] = {
            "status": dayun_result["status"],
            "current_dayun": None,
            "message": result["summary"],
            "selection_basis": dayun_result["timing_context"]["selection_basis"],
            "first_start_at": dayun_result["timing_context"]["timeline"]["start_at"],
        }

    result["timing_context"] = dayun_result["timing_context"]
    if birth_time_uncertainty_minutes is not None:
        result["birth_time_sensitivity"] = analyze_birth_time_range(
            person,
            birth_time_uncertainty_minutes,
            analysis_moment=analysis_moment,
            analysis_age=analysis_age if analysis_moment is None else None,
        )

    result["analysis_reference"] = analysis_reference
    return result


@calculation_guard("节气时间轴分析计算")
def calculate_jieqi_timeline_analysis(
    person: PersonInfo,
    analysis_year: int | None = None,
) -> dict[str, Any]:
    """
    节气节点时间轴分析 - 输出全年 24 节气节点的流月/流日切换信息
    """
    birth_context = build_birth_computation_context(person)
    normalized_birth_time = birth_context.normalized_birth_time
    birth_date = normalized_birth_time.corrected_datetime

    target_year = (
        analysis_year
        if analysis_year is not None
        else current_local_datetime(normalized_birth_time.timezone).year
    )

    jieqi_timeline = enrich_jieqi_timeline(
        birth_context,
        target_year=target_year,
    )

    target_year_jieqi = get_jieqi_year_grid(target_year, normalized_birth_time.timezone)
    summary = (
        f"{target_year}年共生成{len(jieqi_timeline)}个节气节点时间轴，"
        f"覆盖全年流月与流日切换。"
    )
    if any("analysis_anchor_status" in item for item in jieqi_timeline):
        unavailable = sum("analysis_anchor_status" in item for item in jieqi_timeline)
        summary = (
            f"{target_year}年共生成{len(jieqi_timeline)}个节气节点，"
            f"其中{unavailable}个区间没有可重放的当地整分。"
        )

    return {
        "analysis_type": "节气节点时间轴分析",
        "personal_info": {
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
        "summary": summary,
    }
