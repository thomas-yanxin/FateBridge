"""BaZi flow analyses from the annual to the hourly layer."""

from typing import Any, Dict

from fatebridge.analysis.timing_effects import TimingEffectsAnalysis
from fatebridge.core.almanac import build_calendar_context, get_jieqi_year_grid
from fatebridge.core.timing import TimingAnalysis
from fatebridge.services.birth_context import build_birth_computation_context
from fatebridge.services.snapshot_builders import (
    build_snapshot_export as _build_snapshot_export,
)
from fatebridge.services.timing_clock import resolve_analysis_moment
from fatebridge.services.timing_snapshots import (
    _build_liunian_snapshot_text,
    _build_liuri_snapshot_text,
    _build_liushi_snapshot_text,
    _build_liuyue_snapshot_text,
    with_analysis_reference,
    with_birth_clock_reference,
)
from fatebridge.services.timing_state import serialize_element_effects
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.errors import calculation_guard
from fatebridge.utils.formatting import format_clock_datetime


@calculation_guard("流年分析计算")
def calculate_liunian_analysis(
    person: PersonInfo,
    target_year: int,
    selected_sections: list[str] | None = None,
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

    result: dict[str, Any] = {
        "analysis_type": "流年专项分析",
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
    return with_birth_clock_reference(
        result, technique="liunian_analysis", selected_sections=selected_sections
    )


@calculation_guard("流月分析计算")
def calculate_liuyue_analysis(
    person: PersonInfo,
    analysis_year: int | None = None,
    analysis_month: int | None = None,
    analysis_day: int | None = None,
    analysis_hour: int | None = None,
    analysis_minute: int | None = None,
    selected_sections: list[str] | None = None,
) -> Dict:
    """
    流月分析工具 - 专门分析指定日期所在节令月的影响
    """
    birth_context = build_birth_computation_context(person)
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
    analysis_year, analysis_month = analysis_date.year, analysis_date.month
    analysis_day = analysis_date.day
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
    liunian_analysis: dict[str, Any] | None = (
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
    liunian_info: dict[str, Any] | None = None
    if liunian_analysis:
        liunian_info = liunian_analysis["liunian_info"]
    else:
        pass
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

    result: dict[str, Any] = {
        "analysis_type": "流月专项分析",
        "personal_info": {
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
    else:
        pass

    result["summary"] = summary
    return with_analysis_reference(
        result,
        resolution.reference,
        technique="liuyue_analysis",
        selected_sections=selected_sections,
    )


@calculation_guard("流日分析计算")
def calculate_liuri_analysis(
    person: PersonInfo,
    analysis_year: int | None = None,
    analysis_month: int | None = None,
    analysis_day: int | None = None,
    analysis_hour: int | None = None,
    analysis_minute: int | None = None,
    selected_sections: list[str] | None = None,
) -> Dict:
    """
    流日分析工具 - 专门分析指定日期的流日影响
    """
    birth_context = build_birth_computation_context(person)
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
    analysis_year, analysis_month = analysis_date.year, analysis_date.month
    analysis_day = analysis_date.day
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

    result: dict[str, Any] = {
        "analysis_type": "流日专项分析",
        "personal_info": {
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

    return with_analysis_reference(
        result,
        resolution.reference,
        technique="liuri_analysis",
        selected_sections=selected_sections,
    )


@calculation_guard("流时分析计算")
def calculate_liushi_analysis(
    person: PersonInfo,
    analysis_year: int | None = None,
    analysis_month: int | None = None,
    analysis_day: int | None = None,
    analysis_hour: int | None = None,
    analysis_minute: int | None = None,
    selected_sections: list[str] | None = None,
) -> Dict:
    """
    流时分析工具 - 专门分析指定时刻的流时影响
    """
    birth_context = build_birth_computation_context(person)
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
    analysis_year, analysis_month = analysis_date.year, analysis_date.month
    analysis_day = analysis_date.day
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
        },
        element_effects=element_effects,
        summary=summary,
    )
    snapshot_export = _build_snapshot_export(
        technique="liushi_analysis",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )

    result = {
        "analysis_type": "流时专项分析",
        "personal_info": {
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
        },
        "element_effects": serialize_element_effects(element_effects),
        "summary": summary,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }

    return with_analysis_reference(
        result,
        resolution.reference,
        technique="liushi_analysis",
        selected_sections=selected_sections,
    )
