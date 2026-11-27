"""BaZi flow analyses from the annual to the hourly layer."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from dateutil.tz import resolve_imaginary

from fatebridge.analysis.timing_effects import TimingEffectsAnalysis
from fatebridge.core.almanac import (
    build_calendar_context,
    get_bazi_month_boundaries,
    localize_datetime,
)
from fatebridge.core.bazi.calendar import ChangshengSchool, DutyProfile, ZiHourPolicy
from fatebridge.core.bazi.policies import YearBoundaryPolicy
from fatebridge.core.bazi.timing import TimingAnalysis
from fatebridge.services.birth_context import build_birth_computation_context
from fatebridge.services.timing_clock import resolve_analysis_moment
from fatebridge.services.timing_state import serialize_element_effects
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.errors import ParameterError, calculation_guard
from fatebridge.utils.formatting import format_clock_datetime


def _yearly_timeline_entry(liunian_result: dict[str, Any]) -> dict[str, Any]:
    return {
        **liunian_result["liunian_info"],
        "element_effects": serialize_element_effects(liunian_result["element_effects"]),
    }


def _monthly_timeline_entry(
    order: int,
    step_dt: datetime,
    liuyue_result: dict[str, Any],
    liunian_info: dict[str, Any],
) -> dict[str, Any]:
    liuyue_analysis = liuyue_result["liuyue_analysis"]
    liuyue_info = liuyue_analysis["liuyue_info"]
    detailed = liuyue_analysis["detailed_analysis"]
    element_effects = liuyue_analysis["element_effects"]
    return {
        "order": order,
        "analysis_datetime": step_dt.strftime("%Y-%m-%d %H:%M"),
        "pillar": liuyue_info["pillar"],
        "stem": liuyue_info["stem"],
        "branch": liuyue_info["branch"],
        "element": liuyue_info["element"],
        "nayin": liuyue_info["nayin"],
        "stem_ten_god": detailed["shishen_analysis"]["stem_relation"],
        "liunian_pillar": liunian_info["pillar"],
        "solar_term_window": liuyue_info["solar_term_window"],
        "overall_effect": element_effects["overall_effect"],
        "element_effects": serialize_element_effects(element_effects),
        "branch_relations": detailed["branch_relations"],
    }


def _daily_timeline_entry(
    order: int,
    step_dt: datetime,
    liuri_result: dict[str, Any],
) -> dict[str, Any]:
    liuri_info = liuri_result["liuri_info"]
    detailed = liuri_result["detailed_analysis"]
    element_effects = liuri_result["element_effects"]
    return {
        "order": order,
        "date": step_dt.strftime("%Y-%m-%d"),
        "pillar": liuri_info["pillar"],
        "stem": liuri_info["stem"],
        "branch": liuri_info["branch"],
        "element": liuri_info["element"],
        "nayin": liuri_info["nayin"],
        "weekday": liuri_info["weekday"],
        "stem_ten_god": detailed["shishen_analysis"]["stem_relation"],
        "late_zi_rollover_applied": liuri_info["late_zi_rollover_applied"],
        "overall_effect": element_effects["overall_effect"],
        "element_effects": serialize_element_effects(element_effects),
        "branch_relations": detailed["branch_relations"],
    }


@calculation_guard("流年分析计算")
def calculate_liunian_analysis(
    person: PersonInfo,
    analysis_year: int | None = None,
    analysis_month: int | None = None,
    analysis_day: int | None = None,
    analysis_hour: int | None = None,
    analysis_minute: int | None = None,
    *,
    end_year: int | None = None,
    year_boundary_policy: YearBoundaryPolicy = "lichun",
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
    timezone_name = normalized_birth_time.timezone

    resolution = resolve_analysis_moment(
        "liunian_analysis",
        timezone_name,
        analysis_year=analysis_year,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
        analysis_hour=analysis_hour,
        analysis_minute=analysis_minute,
    )
    analysis_date = resolution.moment
    target_year = analysis_date.year
    provided_fields = resolution.reference["provided_fields"]
    year_only = provided_fields == ["analysis_year"]

    if end_year is not None:
        if end_year < target_year:
            msg = "end_year不能小于analysis_year"
            raise ParameterError(
                msg,
                [
                    {
                        "path": "end_year",
                        "code": "invalid_year_range",
                        "message": msg,
                        "constraints": {"ge": target_year},
                    }
                ],
            )
        if end_year - target_year + 1 > 20:
            msg = "年份扫描范围最多20年（end_year - analysis_year + 1 <= 20）"
            raise ParameterError(
                msg,
                [
                    {
                        "path": "end_year",
                        "code": "year_range_too_large",
                        "message": msg,
                        "constraints": {"le": target_year + 19},
                    }
                ],
            )

    liunian_result = TimingEffectsAnalysis.analyze_liunian_effects(
        birth_context.birth_pillars,
        target_year,
        original_element_counts=birth_context.original_element_counts,
        moment=None if year_only else analysis_date,
        timezone_name=timezone_name,
        year_boundary_policy=year_boundary_policy,
    )

    liunian_info = liunian_result["liunian_info"]
    element_effects = liunian_result["element_effects"]

    result: dict[str, Any] = {
        "analysis_type": "流年专项分析",
        "person_info": {
            "name": person.name,
            "target_year": liunian_info["year"],
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
        "analysis_context": resolution.reference,
    }
    if end_year is not None:
        yearly_timeline: list[dict[str, Any]] = []
        for yr in range(target_year, end_year + 1):
            if year_only and yr == target_year:
                yr_result = liunian_result
            else:
                yr_result = TimingEffectsAnalysis.analyze_liunian_effects(
                    birth_context.birth_pillars,
                    yr,
                    original_element_counts=birth_context.original_element_counts,
                    timezone_name=timezone_name,
                    year_boundary_policy=year_boundary_policy,
                )
            yearly_timeline.append(_yearly_timeline_entry(yr_result))
        result["yearly_timeline"] = yearly_timeline
    return result


@calculation_guard("流月分析计算")
def calculate_liuyue_analysis(
    person: PersonInfo,
    analysis_year: int | None = None,
    analysis_month: int | None = None,
    analysis_day: int | None = None,
    analysis_hour: int | None = None,
    analysis_minute: int | None = None,
    *,
    year_boundary_policy: YearBoundaryPolicy = "lichun",
    scan_months: int | None = None,
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
    timezone_name = normalized_birth_time.timezone

    resolution = resolve_analysis_moment(
        "liuyue_analysis",
        timezone_name,
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
        timezone_name=timezone_name,
    )
    liuyue_info = TimingAnalysis.calculate_liuyue(
        analysis_year,
        analysis_month,
        target_day=analysis_day,
        timezone_name=timezone_name,
        target_date=analysis_date,
    )
    liunian_analysis = TimingEffectsAnalysis.analyze_liunian_effects(
        birth_context.birth_pillars,
        analysis_year,
        original_element_counts=birth_context.original_element_counts,
        moment=analysis_date,
        timezone_name=timezone_name,
        year_boundary_policy=year_boundary_policy,
    )
    liuyue_result = TimingEffectsAnalysis.analyze_liuyue_comprehensive(
        birth_context.birth_pillars,
        analysis_year,
        analysis_month,
        include_liunian=True,
        target_day=analysis_day,
        timezone_name=timezone_name,
        target_date=analysis_date,
        liuyue_info=liuyue_info,
        liunian_analysis=liunian_analysis,
        original_element_counts=birth_context.original_element_counts,
        year_boundary_policy=year_boundary_policy,
    )

    liuyue_analysis = liuyue_result["liuyue_analysis"]
    liuyue_info = liuyue_analysis["liuyue_info"]
    detailed_analysis = liuyue_analysis["detailed_analysis"]
    element_effects = liuyue_analysis["element_effects"]
    liunian_info = liunian_analysis["liunian_info"]

    result: dict[str, Any] = {
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
    if scan_months is not None:
        monthly_timeline = [
            _monthly_timeline_entry(1, analysis_date, liuyue_result, liunian_info)
        ]
        cursor_dt = analysis_date
        for order in range(2, scan_months + 1):
            _, next_boundary, _, _ = get_bazi_month_boundaries(cursor_dt, timezone_name)
            next_anchor = TimingAnalysis._next_supported_analysis_anchor(
                next_boundary, timezone_name
            )
            if next_anchor is None:
                break
            cursor_dt = next_anchor
            step_liuyue_info = TimingAnalysis.calculate_liuyue(
                cursor_dt.year,
                cursor_dt.month,
                target_day=cursor_dt.day,
                timezone_name=timezone_name,
                target_date=cursor_dt,
            )
            step_liunian = TimingEffectsAnalysis.analyze_liunian_effects(
                birth_context.birth_pillars,
                cursor_dt.year,
                original_element_counts=birth_context.original_element_counts,
                moment=cursor_dt,
                timezone_name=timezone_name,
                year_boundary_policy=year_boundary_policy,
            )
            step_result = TimingEffectsAnalysis.analyze_liuyue_comprehensive(
                birth_context.birth_pillars,
                cursor_dt.year,
                cursor_dt.month,
                include_liunian=True,
                target_day=cursor_dt.day,
                timezone_name=timezone_name,
                target_date=cursor_dt,
                liuyue_info=step_liuyue_info,
                liunian_analysis=step_liunian,
                original_element_counts=birth_context.original_element_counts,
                year_boundary_policy=year_boundary_policy,
            )
            monthly_timeline.append(
                _monthly_timeline_entry(
                    order, cursor_dt, step_result, step_liunian["liunian_info"]
                )
            )
        result["monthly_timeline"] = monthly_timeline
    return result


@calculation_guard("流日分析计算")
def calculate_liuri_analysis(
    person: PersonInfo,
    analysis_year: int | None = None,
    analysis_month: int | None = None,
    analysis_day: int | None = None,
    analysis_hour: int | None = None,
    analysis_minute: int | None = None,
    *,
    scan_days: int | None = None,
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
    timezone_name = normalized_birth_time.timezone

    resolution = resolve_analysis_moment(
        "liuri_analysis",
        timezone_name,
        analysis_year=analysis_year,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
        analysis_hour=analysis_hour,
        analysis_minute=analysis_minute,
    )
    analysis_date = resolution.moment
    analysis_calendar_context = build_calendar_context(
        analysis_date,
        timezone_name=timezone_name,
    )
    liuri_result = TimingEffectsAnalysis.analyze_liuri_effects(
        birth_context.birth_pillars,
        analysis_date,
        timezone_name=timezone_name,
        original_element_counts=birth_context.original_element_counts,
        zi_hour_policy=zi_hour_policy,
    )
    liuri_info = liuri_result["liuri_info"]
    detailed = liuri_result["detailed_analysis"]

    result: dict[str, Any] = {
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
    if scan_days is not None:
        base_wall = localize_datetime(analysis_date, timezone_name).replace(tzinfo=None)
        daily_timeline = [_daily_timeline_entry(1, analysis_date, liuri_result)]
        for offset in range(1, scan_days):
            step_dt = resolve_imaginary(
                localize_datetime(base_wall + timedelta(days=offset), timezone_name)
            )
            step_res = TimingEffectsAnalysis.analyze_liuri_effects(
                birth_context.birth_pillars,
                step_dt,
                timezone_name=timezone_name,
                original_element_counts=birth_context.original_element_counts,
                zi_hour_policy=zi_hour_policy,
            )
            daily_timeline.append(_daily_timeline_entry(offset + 1, step_dt, step_res))
        result["daily_timeline"] = daily_timeline
    return result


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
