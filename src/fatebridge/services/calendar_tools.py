"""Solar-term and lunar-calendar query service entry points."""

from datetime import timedelta
from typing import Any, Dict, List, Optional

from fatebridge.core.almanac import build_calendar_context, get_jieqi_year_grid
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.services.calendar_input import (
    _normalize_time_alg,
    _parse_calendar_datetime,
)
from fatebridge.services.snapshot_builders import (
    build_snapshot_export as _build_snapshot_export,
)
from fatebridge.services.timing_snapshots import (
    _build_jieqi_year_snapshot_text,
    _build_nongli_time_snapshot_text,
)
from fatebridge.utils.coordinates import parse_geo_coordinate
from fatebridge.utils.errors import calculation_guard
from fatebridge.utils.formatting import create_pillar_dict
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE
from fatebridge.utils.solar_time import calculate_solar_time_adjustment


@calculation_guard("全年节气盘")
def calculate_jieqi_year(
    *,
    year: int,
    zone: Optional[str] = None,
    lat: Optional[str] = None,
    lon: Optional[str] = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
    jieqis: Optional[List[str]] = None,
    selected_sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    全年节气辅助工具 - 生成全年 24 节气列表，并可筛选重点节气。
    """
    timezone_name = zone or DEFAULT_BIRTH_TIMEZONE
    normalized_year = int(year)
    annual_grid = get_jieqi_year_grid(normalized_year, timezone_name)
    requested_terms = jieqis or []
    by_name = {item["name"]: item for item in annual_grid}
    selected_terms = (
        [by_name[name] for name in requested_terms if name in by_name]
        if requested_terms
        else annual_grid
    )
    missing_terms = [name for name in requested_terms if name not in by_name]

    summary = (
        f"{normalized_year}年共生成{len(annual_grid)}个节气节点，"
        f"当前返回{len(selected_terms)}个重点节气。"
    )
    snapshot_text = _build_jieqi_year_snapshot_text(
        year=normalized_year,
        timezone_name=timezone_name,
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        requested_terms=requested_terms,
        annual_grid=annual_grid,
        selected_terms=selected_terms,
        missing_terms=missing_terms,
        summary=summary,
    )
    snapshot_export = _build_snapshot_export(
        technique="jieqi_year",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )

    result: Dict[str, Any] = {
        "analysis_type": "全年节气盘",
        "query_context": {
            "year": normalized_year,
            "timezone": timezone_name,
            "lat": lat,
            "lon": lon,
            "gps_lat": gps_lat,
            "gps_lon": gps_lon,
            "requested_jieqis": requested_terms,
        },
        "year": normalized_year,
        "jieqi_year": annual_grid,
        "selected_jieqi": selected_terms,
        "summary": summary,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }
    if missing_terms:
        result["warnings"] = [f"未识别的节气名称：{'、'.join(missing_terms)}"]
    return result


@calculation_guard("农历换算")
def calculate_nongli_time(
    *,
    date: str,
    time: str,
    zone: Optional[str] = None,
    lat: Optional[str] = None,
    lon: Optional[str] = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
    gender: Optional[Any] = None,
    time_alg: int = 0,
    ad: int = 1,
    selected_sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    农历换算辅助工具 - 输出农历、节气与干支上下文。
    """
    if ad != 1:
        raise ValueError("离线农历换算当前仅支持公元日期（ad=1）。")

    timezone_name = zone or DEFAULT_BIRTH_TIMEZONE
    normalized_time_alg = _normalize_time_alg(time_alg)
    input_datetime = _parse_calendar_datetime(date, time)
    corrected_datetime = input_datetime
    analysis_datetime = input_datetime
    total_correction_minutes = 0.0
    effective_longitude = parse_geo_coordinate(
        gps_lon if gps_lon is not None else lon, axis="longitude"
    )
    parse_geo_coordinate(gps_lat if gps_lat is not None else lat, axis="latitude")
    time_algorithm_label = "直接时间"
    warnings: List[str] = []

    if normalized_time_alg == 0:
        if effective_longitude is not None:
            adjustment = calculate_solar_time_adjustment(
                input_datetime,
                timezone_name,
                effective_longitude,
            )
            total_correction_minutes = adjustment["total_correction_minutes"]
            corrected_datetime = input_datetime + timedelta(
                minutes=total_correction_minutes
            )
            analysis_datetime = corrected_datetime
            time_algorithm_label = "真太阳时"
        else:
            warnings.append(
                "time_alg=0 需要 lon 或 gps_lon 才能计算真太阳时，已回退为直接时间。"
            )

    pillars = BaZiCalendar.get_four_pillars(
        analysis_datetime,
        timezone_name=timezone_name,
        civil_datetime=input_datetime,
    )
    calendar_context = build_calendar_context(
        analysis_datetime,
        timezone_name=timezone_name,
        pillars=pillars,
        civil_datetime=input_datetime,
    )
    lunar_calendar = calendar_context.get("lunar_calendar") or {}
    lunar_support = calendar_context.get("lunar_calendar_support") or {}
    if not lunar_support.get("supported", bool(lunar_calendar)):
        raise ValueError(
            lunar_support.get("reason") or "离线农历换算当前不支持该日期。"
        )
    summary = (
        f"{calendar_context['solar_datetime']} 对应农历"
        f"{lunar_calendar.get('display', '未知')}，"
        f"当前节气为{calendar_context['current_solar_term']['name']}。"
    )

    year_ganzhi = f"{pillars['year'][0]}{pillars['year'][1]}"
    month_ganzhi = f"{pillars['month'][0]}{pillars['month'][1]}"
    day_ganzhi = f"{pillars['day'][0]}{pillars['day'][1]}"
    time_ganzhi = f"{pillars['hour'][0]}{pillars['hour'][1]}"
    nongli_display = (
        f"{lunar_calendar.get('year_cn', '')}年"
        f"{lunar_calendar.get('month_cn', '')}"
        f"{lunar_calendar.get('day_cn', '')}"
    ).strip() or lunar_calendar.get("display", "")
    snapshot_text = _build_nongli_time_snapshot_text(
        date=date,
        time=time,
        timezone_name=timezone_name,
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        gender=gender,
        time_alg=normalized_time_alg,
        time_algorithm_label=time_algorithm_label,
        ad=ad,
        effective_longitude=effective_longitude,
        total_correction_minutes=total_correction_minutes,
        calendar_context=calendar_context,
        lunar_calendar=lunar_calendar,
        year_ganzhi=year_ganzhi,
        month_ganzhi=lunar_calendar.get("month_ganzhi", month_ganzhi),
        day_ganzhi=lunar_calendar.get("day_ganzhi", day_ganzhi),
        time_ganzhi=lunar_calendar.get("time_ganzhi", time_ganzhi),
        summary=summary,
    )
    snapshot_export = _build_snapshot_export(
        technique="nongli_time",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )

    result: Dict[str, Any] = {
        "analysis_type": "农历换算",
        "input_context": {
            "date": date,
            "time": time,
            "timezone": timezone_name,
            "lat": lat,
            "lon": lon,
            "gps_lat": gps_lat,
            "gps_lon": gps_lon,
            "gender": gender,
            "time_alg": normalized_time_alg,
            "ad": ad,
        },
        "analysis_context": {
            "input_datetime": input_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "corrected_datetime": corrected_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "effective_datetime": analysis_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "time_algorithm": time_algorithm_label,
            "longitude": effective_longitude,
            "total_correction_minutes": round(total_correction_minutes, 2),
        },
        "birth": calendar_context["solar_datetime"],
        "nongli": nongli_display,
        "yearGanZi": year_ganzhi,
        "yearJieqi": lunar_calendar.get("year_jieqi_ganzhi", year_ganzhi),
        "monthGanZi": lunar_calendar.get("month_ganzhi", month_ganzhi),
        "dayGanZi": lunar_calendar.get("day_ganzhi", day_ganzhi),
        "timeGanZi": lunar_calendar.get("time_ganzhi", time_ganzhi),
        "jieqi": lunar_calendar.get("jieqi"),
        "jiedelta": lunar_calendar.get("jiedelta"),
        "month": lunar_calendar.get("month_cn"),
        "day": lunar_calendar.get("day_cn"),
        "monthInt": lunar_calendar.get("month"),
        "dayInt": lunar_calendar.get("day"),
        "leap": lunar_calendar.get("is_leap_month", False),
        "calendar_context": calendar_context,
        "lunar_calendar": lunar_calendar,
        "four_pillars": create_pillar_dict(pillars),
        "summary": summary,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }
    if warnings:
        result["warnings"] = warnings
    return result
