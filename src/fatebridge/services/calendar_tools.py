"""Solar-term and lunar-calendar query service entry points."""

from datetime import timedelta
from typing import Any

from fatebridge.core.almanac import build_calendar_context, get_jieqi_year_grid
from fatebridge.core.bazi.calendar import BaZiCalendar
from fatebridge.services.calendar_input import _parse_calendar_datetime
from fatebridge.utils.civil_clock import resolve_civil_clock
from fatebridge.utils.civil_time import NominalClockLabel
from fatebridge.utils.coordinates import parse_geo_coordinate
from fatebridge.utils.errors import calculation_guard
from fatebridge.utils.formatting import create_pillar_dict
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE
from fatebridge.utils.solar_time import calculate_solar_time_adjustment


@calculation_guard("全年节气盘")
def calculate_jieqi_year(
    *,
    year: int,
    timezone: str | None = None,
    latitude: float | str | None = None,
    longitude: float | str | None = None,
    jieqis: list[str] | None = None,
) -> dict[str, Any]:
    """
    全年节气辅助工具 - 生成全年 24 节气列表，并可筛选重点节气。
    """
    timezone_name = timezone or DEFAULT_BIRTH_TIMEZONE
    parsed_latitude = parse_geo_coordinate(latitude, axis="latitude")
    parsed_longitude = parse_geo_coordinate(longitude, axis="longitude")
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
    result: dict[str, Any] = {
        "analysis_type": "全年节气盘",
        "analysis_context": {
            "year": normalized_year,
            "timezone": timezone_name,
            "latitude": parsed_latitude,
            "longitude": parsed_longitude,
            "requested_jieqis": requested_terms,
        },
        "year": normalized_year,
        "jieqi_year": annual_grid,
        "selected_jieqi": selected_terms,
        "summary": summary,
    }
    if missing_terms:
        result["warnings"] = [f"未识别的节气名称：{'、'.join(missing_terms)}"]
    return result


@calculation_guard("农历换算")
def calculate_nongli_time(
    *,
    date: str,
    time: str,
    timezone: str | None = None,
    analysis_utc_offset: str | None = None,
    latitude: float | str | None = None,
    longitude: float | str | None = None,
    gender: Any | None = None,
    time_alg: int = 0,
    ad: int = 1,
) -> dict[str, Any]:
    """
    农历换算辅助工具 - 输出农历、节气与干支上下文。
    """
    if ad != 1:
        raise ValueError("离线农历换算当前仅支持公元日期（ad=1）。")

    if time_alg not in (0, 1):
        raise ValueError("time_alg 仅支持 0（真太阳时）或 1（直接时间）。")

    timezone_name = timezone or DEFAULT_BIRTH_TIMEZONE
    input_datetime = _parse_calendar_datetime(date, time)
    civil_datetime = resolve_civil_clock(
        input_datetime, timezone_name, analysis_utc_offset, timezone_field="timezone"
    )
    clock = NominalClockLabel.from_local_datetime(input_datetime)
    total_correction_minutes = 0.0
    effective_longitude = parse_geo_coordinate(longitude, axis="longitude")
    parsed_latitude = parse_geo_coordinate(latitude, axis="latitude")
    time_algorithm_label = "直接时间"
    warnings: list[str] = []

    if time_alg == 0:
        if effective_longitude is not None:
            adjustment = calculate_solar_time_adjustment(
                civil_datetime,
                timezone_name,
                effective_longitude,
            )
            total_correction_minutes = adjustment["total_correction_minutes"]
            clock = clock.shifted(timedelta(minutes=total_correction_minutes))
            time_algorithm_label = "真太阳时"
        else:
            warnings.append(
                "time_alg=0 需要 longitude 才能计算真太阳时，已回退为直接时间。"
            )

    pillars = BaZiCalendar.get_four_pillars(
        clock,
        timezone_name=timezone_name,
        civil_datetime=civil_datetime,
    )
    calendar_context = build_calendar_context(
        clock,
        timezone_name=timezone_name,
        pillars=pillars,
        civil_datetime=civil_datetime,
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

    result: dict[str, Any] = {
        "analysis_type": "农历换算",
        "analysis_context": {
            "date": date,
            "time": time,
            "timezone": timezone_name,
            "latitude": parsed_latitude,
            "longitude": effective_longitude,
            "gender": gender,
            "time_alg": time_alg,
            "ad": ad,
            "input_datetime": input_datetime.isoformat(sep=" "),
            "corrected_datetime": clock.isoformat(sep=" "),
            "effective_datetime": clock.isoformat(sep=" "),
            "time_algorithm": time_algorithm_label,
            "total_correction_minutes": round(total_correction_minutes, 2),
        },
        "person_info": {
            "gender": gender,
            "birth_datetime": input_datetime.isoformat(sep=" "),
            "normalized_birth_datetime": clock.isoformat(sep=" "),
            "birth_timezone": timezone_name,
            "birth_longitude": effective_longitude,
            "birth_latitude": parsed_latitude,
            "time_algorithm": time_algorithm_label,
        },
        "nongli": nongli_display,
        "year_ganzhi": year_ganzhi,
        "year_jieqi": lunar_calendar.get("year_jieqi_ganzhi", year_ganzhi),
        "month_ganzhi": lunar_calendar.get("month_ganzhi", month_ganzhi),
        "day_ganzhi": lunar_calendar.get("day_ganzhi", day_ganzhi),
        "time_ganzhi": lunar_calendar.get("time_ganzhi", time_ganzhi),
        "jieqi": lunar_calendar.get("jieqi"),
        "jiedelta": lunar_calendar.get("jiedelta"),
        "month": lunar_calendar.get("month_cn"),
        "day": lunar_calendar.get("day_cn"),
        "month_int": lunar_calendar.get("month"),
        "day_int": lunar_calendar.get("day"),
        "leap": lunar_calendar.get("is_leap_month", False),
        "calendar_context": calendar_context,
        "lunar_calendar": lunar_calendar,
        "four_pillars": create_pillar_dict(pillars),
        "summary": summary,
    }
    if warnings:
        result["warnings"] = warnings
    return result
