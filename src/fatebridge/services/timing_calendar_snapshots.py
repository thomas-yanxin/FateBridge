"""Render solar-term and civil calendar snapshots."""

from typing import Any, Mapping

from fatebridge.services.snapshot_builders import (
    render_snapshot_lines as _render_snapshot_text,
)


def term_clock_text(term: Mapping[str, object]) -> str:
    if (utc := term.get("datetime_utc")) is not None:
        return f"{utc} UTC（当地钟时未定义）"
    return str(term.get("datetime", "未知"))


def _format_location_line(
    *,
    lat: str | None,
    lon: str | None,
    gps_lat: float | None,
    gps_lon: float | None,
) -> str:
    parts: list[str] = []
    if lat or lon:
        parts.append(f"文本提示：{lat or '未提供'} / {lon or '未提供'}")
    if gps_lat is not None or gps_lon is not None:
        parts.append(
            f"GPS：{gps_lat if gps_lat is not None else '未提供'} / {gps_lon if gps_lon is not None else '未提供'}"
        )
    return "；".join(parts) if parts else "位置：未提供"


def build_jieqi_year_snapshot_text(
    *,
    year: int,
    timezone_name: str,
    lat: str | None,
    lon: str | None,
    gps_lat: float | None,
    gps_lon: float | None,
    requested_terms: list[str],
    annual_grid: list[dict[str, Any]],
    selected_terms: list[dict[str, Any]],
    missing_terms: list[str],
    summary: str,
) -> str:
    query_lines = [
        f"年份：{year}",
        f"时区：{timezone_name}",
        _format_location_line(lat=lat, lon=lon, gps_lat=gps_lat, gps_lon=gps_lon),
        f"请求节气：{'、'.join(requested_terms) if requested_terms else '全部'}",
        f"返回重点节气数：{len(selected_terms)}",
        f"摘要：{summary}",
    ]
    if missing_terms:
        query_lines.append(f"未识别节气：{'、'.join(missing_terms)}")

    def term_line(item: dict[str, Any]) -> str:
        day = item.get("day_ganzhi", "未定义" if "datetime_utc" in item else "未知")
        return f"{item.get('name', '未知')}：{term_clock_text(item)} / 日干支 {day}"

    annual_lines = [term_line(item) for item in annual_grid]
    selected_lines = [term_line(item) for item in selected_terms] or ["无"]
    source_lines = [
        "来源：FateBridge 离线节气算法",
        "引用：fatebridge.core.almanac.get_jieqi_year_grid",
    ]

    return _render_snapshot_text(
        [
            ("查询信息", query_lines),
            ("全年节气", annual_lines),
            ("重点节气", selected_lines),
            ("来源", source_lines),
        ]
    )


def build_nongli_time_snapshot_text(
    *,
    date: str,
    time: str,
    timezone_name: str,
    lat: str | None,
    lon: str | None,
    gps_lat: float | None,
    gps_lon: float | None,
    gender: Any | None,
    time_alg: int,
    time_algorithm_label: str,
    ad: int,
    effective_longitude: float | None,
    total_correction_minutes: float,
    calendar_context: dict[str, Any],
    lunar_calendar: dict[str, Any],
    year_ganzhi: str,
    month_ganzhi: str,
    day_ganzhi: str,
    time_ganzhi: str,
    summary: str,
) -> str:
    boundary = calendar_context.get("bazi_month_boundary") or {}
    current_term = calendar_context.get("current_solar_term") or {}
    next_term = calendar_context.get("next_solar_term") or {}
    query_lines = [
        f"输入公历：{date} {time}",
        f"时区：{timezone_name}",
        _format_location_line(lat=lat, lon=lon, gps_lat=gps_lat, gps_lon=gps_lon),
        f"gender 透传：{gender if gender is not None else '未提供'}",
        f"time_alg：{time_alg}（{time_algorithm_label}）",
        f"ad：{ad}",
        f"有效经度：{round(effective_longitude, 4) if effective_longitude is not None else '未提供'}",
        f"太阳时修正分钟：{round(total_correction_minutes, 2)}",
        f"摘要：{summary}",
    ]

    lunar_lines = [
        f"换算时刻：{calendar_context.get('solar_datetime', '未知')}",
        f"农历：{lunar_calendar.get('display', '未知')}",
        f"农历年月日：{lunar_calendar.get('year_cn', '')}年{lunar_calendar.get('month_cn', '')}{lunar_calendar.get('day_cn', '')}".strip(),
        f"当前节气：{current_term.get('name', '未知')} / {term_clock_text(current_term)}",
        f"下一节气：{next_term.get('name', '未知')} / {term_clock_text(next_term)}",
        f"节差：{lunar_calendar.get('jiedelta', '未知')}",
        f"月令窗口：{boundary.get('start_term', {}).get('name', '未知')} -> {boundary.get('next_term', {}).get('name', '未知')}",
        f"是否闰月：{'是' if lunar_calendar.get('is_leap_month') else '否'}",
    ]
    if lunar_calendar.get("meihua"):
        lunar_lines.append("梅花时卦辅助：已生成")

    pillar_lines = [
        f"年柱：{year_ganzhi}",
        f"节气分年：{lunar_calendar.get('year_jieqi_ganzhi', year_ganzhi)}",
        f"月柱：{month_ganzhi}",
        f"日柱：{day_ganzhi}",
        f"时柱：{time_ganzhi}",
        f"月令分支：{boundary.get('branch', '未知')}",
        f"距下个节气天数：{lunar_calendar.get('days_until_next_jieqi', '未知')}",
    ]

    source_lines = [
        "来源：FateBridge 离线农历/节气算法",
        "引用：fatebridge.core.almanac.build_calendar_context / fatebridge.core.calendar.BaZiCalendar",
    ]

    return _render_snapshot_text(
        [
            ("查询信息", query_lines),
            ("农历上下文", lunar_lines),
            ("四柱上下文", pillar_lines),
            ("来源", source_lines),
        ]
    )
