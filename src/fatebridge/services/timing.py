"""Timing use cases composed from shared states and separate snapshot renderers."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fatebridge.analysis.timing_effects import TimingEffectsAnalysis
from fatebridge.core.almanac import (
    build_calendar_context,
    current_local_datetime,
    get_jieqi_year_grid,
)
from fatebridge.core.timing import TimingAnalysis
from fatebridge.services.birth_context import build_birth_computation_context
from fatebridge.services.snapshot_builders import (
    build_snapshot_export as _build_snapshot_export,
)
from fatebridge.services.timing_snapshots import (
    _build_comprehensive_timing_snapshot_text,
    _build_dayun_snapshot_text,
    _build_jieqi_timeline_snapshot_text,
    _build_liunian_snapshot_text,
    _build_liuri_snapshot_text,
    _build_liushi_snapshot_text,
    _build_liuyue_snapshot_text,
)
from fatebridge.services.timing_state import (
    build_current_timing_state,
    compute_life_dimensions_for_moment,
    enrich_jieqi_timeline,
    enrich_liuyue_timeline,
    serialize_element_effects,
)
from fatebridge.utils.analysis_clock import get_current_analysis_date
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.errors import calculation_guard
from fatebridge.utils.formatting import create_pillar_dict


@calculation_guard("时运分析计算")
def calculate_comprehensive_timing(
    person: PersonInfo,
    analysis_year: Optional[int] = None,
    analysis_month: Optional[int] = None,
    analysis_age: Optional[int] = None,
    analysis_day: Optional[int] = None,
    analysis_hour: Optional[int] = None,
    analysis_minute: Optional[int] = None,
    selected_sections: Optional[List[str]] = None,
) -> Dict:
    """
    计算时运分析，包括大运、流年、流月、流日、流时的影响分析
    """
    birth_context = build_birth_computation_context(person)
    normalized_birth_time = birth_context.normalized_birth_time
    input_birth_datetime = normalized_birth_time.input_datetime
    birth_date = normalized_birth_time.corrected_datetime

    # 设置分析日期
    analysis_year, analysis_month = get_current_analysis_date(
        analysis_year, analysis_month
    )
    if analysis_day is None:
        analysis_day = 1
    if analysis_hour is None:
        analysis_hour = 0
    if analysis_minute is None:
        analysis_minute = 0
    analysis_date = datetime(
        analysis_year,
        analysis_month,
        analysis_day,
        analysis_hour,
        analysis_minute,
    )
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

    # 构建最终结果结构
    result: Dict[str, Any] = {
        "analysis_type": "综合时运分析",
        "personal_info": {
            "name": person.name,
            "birth_datetime": input_birth_datetime.strftime("%Y-%m-%d %H:%M"),
            "normalized_birth_datetime": birth_date.strftime("%Y-%m-%d %H:%M"),
            "gender": person.gender,
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

    # 大运分析
    dayun_analysis = timing_result["dayun_analysis"]
    if "dayun_info" in dayun_analysis:
        dayun_info = dayun_analysis["dayun_info"]
        age_info = dayun_analysis["age_info"]
        dayun_section: Dict[str, Any] = {
            "current_dayun": dayun_info["pillar"],
            "stem": dayun_info["stem"],
            "branch": dayun_info["branch"],
            "start_age": age_info["start_age"],
            "start_age_precise": age_info.get("start_age_precise"),
            "dayun_age": age_info["dayun_age"],
            "years_in_period": age_info["years_in_period"],
            "direction": age_info.get("direction"),
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
            "error": dayun_analysis.get("message", "大运信息不可用")
        }

    # 流年分析
    liunian_analysis = timing_result["liunian_analysis"]
    liunian_info = liunian_analysis["liunian_info"]
    liunian_section: Dict[str, Any] = {
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

    # 流月分析
    liuyue_analysis = timing_result["liuyue_analysis"]
    liuyue_info = liuyue_analysis["liuyue_info"]
    result["liuyue_analysis"] = {
        "pillar": liuyue_info["pillar"],
        "stem": liuyue_info["stem"],
        "branch": liuyue_info["branch"],
        "summary": liuyue_analysis["summary"],
    }

    # 流日分析
    liuri_analysis = timing_result["liuri_analysis"]
    liuri_info = liuri_analysis["liuri_info"]
    result["liuri_analysis"] = {
        "pillar": liuri_info["pillar"],
        "stem": liuri_info["stem"],
        "branch": liuri_info["branch"],
        "summary": liuri_analysis["summary"],
    }

    # 流时分析
    liushi_analysis = timing_result["liushi_analysis"]
    liushi_info = liushi_analysis["liushi_info"]
    result["liushi_analysis"] = {
        "pillar": liushi_info["pillar"],
        "stem": liushi_info["stem"],
        "branch": liushi_info["branch"],
        "hour": liushi_info["hour"],
        "summary": liushi_analysis["summary"],
    }

    # 综合影响
    combined_effects = timing_result["combined_effects"]
    result["combined_effects"] = serialize_element_effects(combined_effects)

    # 综合总结
    result["comprehensive_summary"] = timing_result["comprehensive_summary"]
    result["snapshot_text"] = _build_comprehensive_timing_snapshot_text(
        person_name=person.name,
        birth_datetime=input_birth_datetime,
        normalized_birth_datetime=birth_date,
        timezone_name=normalized_birth_time.timezone,
        analysis_date=analysis_date,
        current_age=current_age,
        analysis_calendar_context=analysis_calendar_context,
        dayun_info=result["dayun_analysis"],
        liunian_info=result["liunian_analysis"],
        liuyue_info=result["liuyue_analysis"],
        liuri_info=result["liuri_analysis"],
        liushi_info=result["liushi_analysis"],
        combined_effects=result["combined_effects"],
        summary=result["comprehensive_summary"],
    )
    result["snapshot_export"] = _build_snapshot_export(
        technique="timing_analysis",
        snapshot_text=result["snapshot_text"],
        selected_sections=selected_sections,
    )

    return result


@calculation_guard("大运分析计算")
def calculate_dayun_analysis(
    person: PersonInfo,
    analysis_age: int,
    selected_sections: Optional[List[str]] = None,
) -> Dict:
    """
    大运分析工具 - 专门分析指定年龄的大运情况
    """
    birth_context = build_birth_computation_context(person)
    normalized_birth_time = birth_context.normalized_birth_time
    birth_date = normalized_birth_time.corrected_datetime

    dayun_result = TimingEffectsAnalysis.analyze_dayun_effects(
        birth_context.birth_pillars,
        normalized_birth_time.input_datetime,
        person.gender,
        analysis_age,
        timezone_name=normalized_birth_time.timezone,
        original_element_counts=birth_context.original_element_counts,
    )

    result: Dict[str, Any] = {
        "analysis_type": "大运专项分析",
        "personal_info": {
            "name": person.name,
            "gender": person.gender,
            "analysis_age": analysis_age,
            "birth_datetime": normalized_birth_time.input_datetime.strftime(
                "%Y-%m-%d %H:%M"
            ),
            "normalized_birth_datetime": birth_date.strftime("%Y-%m-%d %H:%M"),
            "time_adjustment": normalized_birth_time.as_dict(),
        },
        "calendar_context": birth_context.birth_calendar_context,
    }

    dayun_info: Optional[Dict[str, Any]] = None
    element_effects: Dict[str, Any] = {}

    if "dayun_info" in dayun_result:
        dayun_info = dayun_result["dayun_info"]
        age_info = dayun_result["age_info"]
        element_effects = dayun_result["element_effects"]

        result["dayun_info"] = {
            "current_dayun": dayun_info["pillar"],
            "stem": dayun_info["stem"],
            "branch": dayun_info["branch"],
            "start_age": age_info["start_age"],
            # start_age is the classical ceil-rounded display value;
            # ``dayun_age`` and ``years_in_period`` are computed from the
            # precise fractional起运岁, so surface it too to let callers
            # reconcile ``age - start_age_precise ≈ dayun_age``.
            "start_age_precise": age_info.get("start_age_precise"),
            "dayun_age": age_info["dayun_age"],
            "years_in_period": age_info["years_in_period"],
            "direction": age_info.get("direction"),
        }

        result["element_effects"] = serialize_element_effects(element_effects)

        result["summary"] = dayun_result["summary"]
    else:
        result["error"] = dayun_result.get("message", "大运信息不可用")
        result["summary"] = result["error"]

    snapshot_text = _build_dayun_snapshot_text(
        person_name=person.name,
        birth_datetime=normalized_birth_time.input_datetime,
        normalized_birth_datetime=birth_date,
        timezone_name=normalized_birth_time.timezone,
        analysis_age=analysis_age,
        dayun_info=result.get("dayun_info") or dayun_info,
        element_effects=result.get("element_effects", element_effects),
        summary=result.get("summary", "大运信息不可用"),
    )
    result["snapshot_text"] = snapshot_text
    result["snapshot_export"] = _build_snapshot_export(
        technique="dayun_analysis",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )

    return result


@calculation_guard("流年分析计算")
def calculate_liunian_analysis(
    person: PersonInfo,
    target_year: int,
    selected_sections: Optional[List[str]] = None,
) -> Dict:
    """
    流年分析工具 - 专门分析指定年份的流年影响
    """
    birth_context = build_birth_computation_context(person)
    normalized_birth_time = birth_context.normalized_birth_time
    birth_date = normalized_birth_time.corrected_datetime

    liunian_result = TimingEffectsAnalysis.analyze_liunian_effects(
        birth_context.birth_pillars,
        target_year,
        original_element_counts=birth_context.original_element_counts,
    )

    liunian_info = liunian_result["liunian_info"]
    element_effects = liunian_result["element_effects"]
    summary = liunian_result["summary"]
    snapshot_text = _build_liunian_snapshot_text(
        person_name=person.name,
        birth_datetime=normalized_birth_time.input_datetime,
        normalized_birth_datetime=birth_date,
        timezone_name=normalized_birth_time.timezone,
        target_year=target_year,
        liunian_info=liunian_info,
        element_effects=element_effects,
        summary=summary,
    )
    snapshot_export = _build_snapshot_export(
        technique="liunian_analysis",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )

    result: Dict[str, Any] = {
        "analysis_type": "流年专项分析",
        "personal_info": {
            "name": person.name,
            "target_year": target_year,
            "birth_datetime": normalized_birth_time.input_datetime.strftime(
                "%Y-%m-%d %H:%M"
            ),
            "normalized_birth_datetime": birth_date.strftime("%Y-%m-%d %H:%M"),
            "time_adjustment": normalized_birth_time.as_dict(),
        },
        "calendar_context": birth_context.birth_calendar_context,
        "target_year_jieqi": get_jieqi_year_grid(
            target_year, normalized_birth_time.timezone
        ),
        "liunian_info": {
            "pillar": liunian_info["pillar"],
            "stem": liunian_info["stem"],
            "branch": liunian_info["branch"],
            "element": liunian_info["element"],
        },
        "element_effects": serialize_element_effects(element_effects),
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }

    result["summary"] = summary
    return result


@calculation_guard("流月分析计算")
def calculate_liuyue_analysis(
    person: PersonInfo,
    analysis_year: Optional[int] = None,
    analysis_month: Optional[int] = None,
    analysis_day: Optional[int] = None,
    analysis_hour: Optional[int] = None,
    analysis_minute: Optional[int] = None,
    selected_sections: Optional[List[str]] = None,
) -> Dict:
    """
    流月分析工具 - 专门分析指定日期所在节令月的影响
    """
    birth_context = build_birth_computation_context(person)
    normalized_birth_time = birth_context.normalized_birth_time
    birth_date = normalized_birth_time.corrected_datetime

    now = current_local_datetime(normalized_birth_time.timezone)
    if analysis_year is None:
        analysis_year = now.year
    if analysis_month is None:
        analysis_month = now.month
    if analysis_day is None:
        # 节气月起点 (立春/惊蛰/清明/立夏...) 大多落在阳历月上旬 5-9 日；
        # 若 user 只指定 analysis_month 而未指定 day，取日=15 能稳定落到
        # 该阳历月"主导"的节气月中段，避免默认到 day=1 时仍滞留在上一节气月，
        # 产生 "四月流月=卯月" 这种反直觉结果。
        analysis_day = 15
    if analysis_hour is None:
        analysis_hour = 0
    if analysis_minute is None:
        analysis_minute = 0

    analysis_date = datetime(
        analysis_year,
        analysis_month,
        analysis_day,
        analysis_hour,
        analysis_minute,
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
    liunian_analysis: Optional[Dict[str, Any]] = (
        TimingEffectsAnalysis.analyze_liunian_effects(
            birth_context.birth_pillars,
            analysis_year,
            original_element_counts=birth_context.original_element_counts,
            moment=analysis_date,
            timezone_name=normalized_birth_time.timezone,
        )
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
    liunian_analysis = liuyue_result.get("liunian_analysis")
    liunian_info: Optional[Dict[str, Any]] = None
    if liunian_analysis:
        liunian_info = liunian_analysis["liunian_info"]
    summary = liuyue_result["comprehensive_summary"]
    snapshot_text = _build_liuyue_snapshot_text(
        person_name=person.name,
        birth_datetime=normalized_birth_time.input_datetime,
        normalized_birth_datetime=birth_date,
        timezone_name=normalized_birth_time.timezone,
        analysis_date=analysis_date,
        analysis_calendar_context=analysis_calendar_context,
        liuyue_info=liuyue_info,
        liunian_info=liunian_info,
        detailed_analysis=detailed_analysis,
        element_effects=element_effects,
        combination_effects=liuyue_result.get("combination_effects", {}),
        summary=summary,
    )
    snapshot_export = _build_snapshot_export(
        technique="liuyue_analysis",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )

    result: Dict[str, Any] = {
        "analysis_type": "流月专项分析",
        "personal_info": {
            "name": person.name,
            "analysis_date": analysis_date.strftime("%Y-%m-%d"),
            "analysis_datetime": analysis_date.strftime("%Y-%m-%d %H:%M"),
            "birth_datetime": normalized_birth_time.input_datetime.strftime(
                "%Y-%m-%d %H:%M"
            ),
            "normalized_birth_datetime": birth_date.strftime("%Y-%m-%d %H:%M"),
            "time_adjustment": normalized_birth_time.as_dict(),
        },
        "calendar_context": birth_context.birth_calendar_context,
        "analysis_calendar": {
            "analysis_date_context": analysis_calendar_context,
        },
        "target_year_jieqi": get_jieqi_year_grid(
            analysis_year, normalized_birth_time.timezone
        ),
        "liuyue_info": {
            "pillar": liuyue_info["pillar"],
            "stem": liuyue_info["stem"],
            "branch": liuyue_info["branch"],
            "element": liuyue_info["element"],
            "nayin": liuyue_info["nayin"],
            "solar_term_window": liuyue_info["solar_term_window"],
        },
        "detailed_analysis": {
            "stem_relation": detailed_analysis["shishen_analysis"]["stem_relation"],
            "branch_relations": detailed_analysis["branch_relations"],
            "fortune_analysis": detailed_analysis["fortune_analysis"],
            "suggestions": detailed_analysis["suggestions"],
        },
        "element_effects": serialize_element_effects(element_effects),
        "combination_effects": liuyue_result.get("combination_effects", {}),
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }

    if liunian_info is not None:
        result["liunian_info"] = {
            "pillar": liunian_info["pillar"],
            "stem": liunian_info["stem"],
            "branch": liunian_info["branch"],
            "element": liunian_info["element"],
        }

    result["summary"] = summary
    return result


@calculation_guard("流日分析计算")
def calculate_liuri_analysis(
    person: PersonInfo,
    analysis_year: Optional[int] = None,
    analysis_month: Optional[int] = None,
    analysis_day: Optional[int] = None,
    analysis_hour: Optional[int] = None,
    analysis_minute: Optional[int] = None,
    selected_sections: Optional[List[str]] = None,
) -> Dict:
    """
    流日分析工具 - 专门分析指定日期的流日影响
    """
    birth_context = build_birth_computation_context(person)
    normalized_birth_time = birth_context.normalized_birth_time
    birth_date = normalized_birth_time.corrected_datetime

    now = current_local_datetime(normalized_birth_time.timezone)
    if analysis_year is None:
        analysis_year = now.year
    if analysis_month is None:
        analysis_month = now.month
    if analysis_day is None:
        analysis_day = now.day
    if analysis_hour is None:
        analysis_hour = 0
    if analysis_minute is None:
        analysis_minute = 0

    analysis_date = datetime(
        analysis_year,
        analysis_month,
        analysis_day,
        analysis_hour,
        analysis_minute,
    )
    analysis_calendar_context = build_calendar_context(
        analysis_date,
        timezone_name=normalized_birth_time.timezone,
    )
    liuri_info = TimingAnalysis.calculate_liuri(
        analysis_date,
        timezone_name=normalized_birth_time.timezone,
    )

    liuri_result = TimingEffectsAnalysis.analyze_liuri_effects(
        birth_context.birth_pillars,
        analysis_date,
        timezone_name=normalized_birth_time.timezone,
        liuri_info=liuri_info,
        original_element_counts=birth_context.original_element_counts,
    )

    liuri_info = liuri_result["liuri_info"]
    element_effects = liuri_result["element_effects"]
    summary = liuri_result["enhanced_summary"]
    snapshot_text = _build_liuri_snapshot_text(
        person_name=person.name,
        birth_datetime=normalized_birth_time.input_datetime,
        normalized_birth_datetime=birth_date,
        timezone_name=normalized_birth_time.timezone,
        analysis_date=analysis_date,
        analysis_calendar_context=analysis_calendar_context,
        liuri_info=liuri_info,
        element_effects=element_effects,
        summary=summary,
    )
    snapshot_export = _build_snapshot_export(
        technique="liuri_analysis",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )

    result: Dict[str, Any] = {
        "analysis_type": "流日专项分析",
        "personal_info": {
            "name": person.name,
            "birth_datetime": normalized_birth_time.input_datetime.strftime(
                "%Y-%m-%d %H:%M"
            ),
            "normalized_birth_datetime": birth_date.strftime("%Y-%m-%d %H:%M"),
            "analysis_date": analysis_date.strftime("%Y-%m-%d"),
            "analysis_datetime": analysis_date.strftime("%Y-%m-%d %H:%M"),
            "time_adjustment": normalized_birth_time.as_dict(),
        },
        "calendar_context": birth_context.birth_calendar_context,
        "analysis_calendar": {
            "analysis_date_context": analysis_calendar_context,
        },
        "liuri_info": {
            "pillar": liuri_info["pillar"],
            "stem": liuri_info["stem"],
            "branch": liuri_info["branch"],
            "element": liuri_info["element"],
            "weekday": liuri_info["weekday"],
        },
        "element_effects": serialize_element_effects(element_effects),
        "summary": summary,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }

    return result


@calculation_guard("流时分析计算")
def calculate_liushi_analysis(
    person: PersonInfo,
    analysis_year: Optional[int] = None,
    analysis_month: Optional[int] = None,
    analysis_day: Optional[int] = None,
    analysis_hour: Optional[int] = None,
    analysis_minute: Optional[int] = None,
    selected_sections: Optional[List[str]] = None,
) -> Dict:
    """
    流时分析工具 - 专门分析指定时刻的流时影响
    """
    birth_context = build_birth_computation_context(person)
    normalized_birth_time = birth_context.normalized_birth_time
    birth_date = normalized_birth_time.corrected_datetime

    now = current_local_datetime(normalized_birth_time.timezone)
    if analysis_year is None:
        analysis_year = now.year
    if analysis_month is None:
        analysis_month = now.month
    if analysis_day is None:
        analysis_day = now.day
    if analysis_hour is None:
        analysis_hour = now.hour
    if analysis_minute is None:
        analysis_minute = 0

    analysis_date = datetime(
        analysis_year,
        analysis_month,
        analysis_day,
        analysis_hour,
        analysis_minute,
    )
    analysis_calendar_context = build_calendar_context(
        analysis_date,
        timezone_name=normalized_birth_time.timezone,
    )
    liushi_info = TimingAnalysis.calculate_liushi(
        analysis_date,
        timezone_name=normalized_birth_time.timezone,
    )

    liushi_result = TimingEffectsAnalysis.analyze_liushi_effects(
        birth_context.birth_pillars,
        analysis_date,
        timezone_name=normalized_birth_time.timezone,
        liushi_info=liushi_info,
        original_element_counts=birth_context.original_element_counts,
    )

    liushi_info = liushi_result["liushi_info"]
    detailed_analysis = liushi_result["detailed_analysis"]
    element_effects = liushi_result["element_effects"]
    summary = liushi_result["enhanced_summary"]
    snapshot_text = _build_liushi_snapshot_text(
        person_name=person.name,
        birth_datetime=normalized_birth_time.input_datetime,
        normalized_birth_datetime=birth_date,
        timezone_name=normalized_birth_time.timezone,
        analysis_date=analysis_date,
        analysis_calendar_context=analysis_calendar_context,
        liushi_info=liushi_info,
        detailed_analysis={
            "stem_relation": detailed_analysis["shishen_analysis"]["stem_relation"],
            "branch_relations": detailed_analysis["branch_relations"],
            "fortune_analysis": detailed_analysis["fortune_analysis"],
            "suggestions": detailed_analysis["suggestions"],
        },
        element_effects=element_effects,
        summary=summary,
    )
    snapshot_export = _build_snapshot_export(
        technique="liushi_analysis",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )

    return {
        "analysis_type": "流时专项分析",
        "personal_info": {
            "name": person.name,
            "birth_datetime": normalized_birth_time.input_datetime.strftime(
                "%Y-%m-%d %H:%M"
            ),
            "normalized_birth_datetime": birth_date.strftime("%Y-%m-%d %H:%M"),
            "analysis_date": analysis_date.strftime("%Y-%m-%d"),
            "analysis_datetime": analysis_date.strftime("%Y-%m-%d %H:%M"),
            "time_adjustment": normalized_birth_time.as_dict(),
        },
        "calendar_context": birth_context.birth_calendar_context,
        "analysis_calendar": {
            "analysis_date_context": analysis_calendar_context,
        },
        "liushi_info": {
            "pillar": liushi_info["pillar"],
            "stem": liushi_info["stem"],
            "branch": liushi_info["branch"],
            "element": liushi_info["element"],
            "nayin": liushi_info["nayin"],
            "hour": liushi_info["hour"],
            "analysis_datetime": liushi_info["analysis_datetime"],
            "shichen": liushi_info["shichen"],
        },
        "detailed_analysis": {
            "stem_relation": detailed_analysis["shishen_analysis"]["stem_relation"],
            "branch_relations": detailed_analysis["branch_relations"],
            "fortune_analysis": detailed_analysis["fortune_analysis"],
            "suggestions": detailed_analysis["suggestions"],
        },
        "element_effects": serialize_element_effects(element_effects),
        "life_dimensions": compute_life_dimensions_for_moment(
            birth_context, analysis_date
        ),
        "summary": summary,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }


@calculation_guard("节气时间轴分析计算")
def calculate_jieqi_timeline_analysis(
    person: PersonInfo,
    target_year: Optional[int] = None,
    selected_sections: Optional[List[str]] = None,
) -> Dict:
    """
    节气节点时间轴分析 - 输出全年 24 节气节点的流月/流日切换信息
    """
    birth_context = build_birth_computation_context(person)
    normalized_birth_time = birth_context.normalized_birth_time
    birth_date = normalized_birth_time.corrected_datetime

    if target_year is None:
        target_year = current_local_datetime(normalized_birth_time.timezone).year

    jieqi_timeline = enrich_jieqi_timeline(
        birth_context,
        target_year=target_year,
    )

    target_year_jieqi = get_jieqi_year_grid(target_year, normalized_birth_time.timezone)
    summary = (
        f"{target_year}年共生成{len(jieqi_timeline)}个节气节点时间轴，"
        f"覆盖全年流月与流日切换。"
    )
    snapshot_text = _build_jieqi_timeline_snapshot_text(
        person_name=person.name,
        birth_datetime=normalized_birth_time.input_datetime,
        normalized_birth_datetime=birth_date,
        timezone_name=normalized_birth_time.timezone,
        target_year=target_year,
        target_year_jieqi=target_year_jieqi,
        jieqi_timeline=jieqi_timeline,
        summary=summary,
    )
    snapshot_export = _build_snapshot_export(
        technique="jieqi_timeline_analysis",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )

    return {
        "analysis_type": "节气节点时间轴分析",
        "personal_info": {
            "name": person.name,
            "target_year": target_year,
            "birth_datetime": normalized_birth_time.input_datetime.strftime(
                "%Y-%m-%d %H:%M"
            ),
            "normalized_birth_datetime": birth_date.strftime("%Y-%m-%d %H:%M"),
            "time_adjustment": normalized_birth_time.as_dict(),
        },
        "calendar_context": birth_context.birth_calendar_context,
        "target_year_jieqi": target_year_jieqi,
        "jieqi_timeline": jieqi_timeline,
        "summary": summary,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }
