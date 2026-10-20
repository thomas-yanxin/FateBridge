"""Readable timing and calendar snapshots without calculation orchestration."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fatebridge.services.snapshot_builders import (
    render_snapshot_lines as _render_snapshot_text,
)


def _format_location_line(
    *,
    lat: Optional[str],
    lon: Optional[str],
    gps_lat: Optional[float],
    gps_lon: Optional[float],
) -> str:
    parts: list[str] = []
    if lat or lon:
        parts.append(f"文本提示：{lat or '未提供'} / {lon or '未提供'}")
    if gps_lat is not None or gps_lon is not None:
        parts.append(
            f"GPS：{gps_lat if gps_lat is not None else '未提供'} / {gps_lon if gps_lon is not None else '未提供'}"
        )
    return "；".join(parts) if parts else "位置：未提供"


def _build_jieqi_year_snapshot_text(
    *,
    year: int,
    timezone_name: str,
    lat: Optional[str],
    lon: Optional[str],
    gps_lat: Optional[float],
    gps_lon: Optional[float],
    requested_terms: List[str],
    annual_grid: List[Dict[str, Any]],
    selected_terms: List[Dict[str, Any]],
    missing_terms: List[str],
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

    annual_lines = [
        f"{item.get('name', '未知')}：{item.get('datetime', '未知')} / 日干支 {item.get('day_ganzhi', '未知')}"
        for item in annual_grid
    ]
    selected_lines = [
        f"{item.get('name', '未知')}：{item.get('datetime', '未知')} / 日干支 {item.get('day_ganzhi', '未知')}"
        for item in selected_terms
    ] or ["无"]
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


def _build_nongli_time_snapshot_text(
    *,
    date: str,
    time: str,
    timezone_name: str,
    lat: Optional[str],
    lon: Optional[str],
    gps_lat: Optional[float],
    gps_lon: Optional[float],
    gender: Optional[Any],
    time_alg: int,
    time_algorithm_label: str,
    ad: int,
    effective_longitude: Optional[float],
    total_correction_minutes: float,
    calendar_context: Dict[str, Any],
    lunar_calendar: Dict[str, Any],
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
        f"当前节气：{current_term.get('name', '未知')} / {current_term.get('datetime', '未知')}",
        f"下一节气：{next_term.get('name', '未知')} / {next_term.get('datetime', '未知')}",
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


def _build_liuyue_snapshot_text(
    *,
    person_name: Optional[str],
    birth_datetime: datetime,
    normalized_birth_datetime: datetime,
    timezone_name: str,
    analysis_date: datetime,
    analysis_calendar_context: Dict[str, Any],
    liuyue_info: Dict[str, Any],
    liunian_info: Optional[Dict[str, Any]],
    detailed_analysis: Dict[str, Any],
    element_effects: Dict[str, Any],
    combination_effects: Dict[str, Any],
    summary: str,
) -> str:
    current_term = (analysis_calendar_context.get("current_solar_term") or {}).get(
        "name", "未知"
    )
    next_term = (analysis_calendar_context.get("next_solar_term") or {}).get(
        "name", "未知"
    )
    query_lines = [
        f"姓名：{person_name or '未提供'}",
        f"分析时刻：{analysis_date.strftime('%Y-%m-%d %H:%M')}",
        f"出生时间：{birth_datetime.strftime('%Y-%m-%d %H:%M')}",
        f"归一时间：{normalized_birth_datetime.strftime('%Y-%m-%d %H:%M')}",
        f"时区：{timezone_name}",
        f"分析日节气：{current_term} -> {next_term}",
        f"摘要：{summary}",
    ]

    solar_term_window = liuyue_info.get("solar_term_window") or {}
    liuyue_lines = [
        f"流月：{liuyue_info.get('pillar', '未知')}",
        f"月干支：{liuyue_info.get('stem', '未知')}{liuyue_info.get('branch', '未知')}",
        f"五行：{liuyue_info.get('element', '未知')}",
        f"纳音：{liuyue_info.get('nayin', '未知')}",
        f"节令窗口：{solar_term_window.get('start_term', {}).get('name', '未知')} -> {solar_term_window.get('next_term', {}).get('name', '未知')}",
        f"窗口时刻：{solar_term_window.get('start_term', {}).get('datetime', '未知')} -> {solar_term_window.get('next_term', {}).get('datetime', '未知')}",
    ]

    combo_lines: list[str] = []
    if liunian_info:
        combo_lines.append(f"流年：{liunian_info.get('pillar', '未知')}")
        combo_lines.append(
            f"流年月支：{liuyue_info.get('branch', '未知')} / 流年支：{liunian_info.get('branch', '未知')}"
        )
    liuyue_liunian = combination_effects.get("liuyue_liunian") or {}
    if liuyue_liunian:
        combo_lines.append(
            f"组合总效应：{liuyue_liunian.get('overall_effect', '未知')}"
        )
        combo_lines.append(
            f"组合影响分：{liuyue_liunian.get('total_impact_score', '未知')}"
        )
        for relation in liuyue_liunian.get("relations") or []:
            combo_lines.append(
                f"{relation.get('type', '普通')}：{relation.get('description', '无')} / "
                f"{relation.get('effect', '无')} / 分值 {relation.get('impact_score', '未知')}"
            )
    if not combo_lines:
        combo_lines.append("无流年联动信息")

    effect_lines = [
        f"十神关系：{detailed_analysis.get('stem_relation', '未知')}",
        f"总体五行：{element_effects.get('overall_effect', '未知')}",
    ]
    fortune_analysis = detailed_analysis.get("fortune_analysis") or {}
    if fortune_analysis:
        effect_lines.append(
            f"运势等级：{fortune_analysis.get('overall_fortune', '未知')}"
        )
        effect_lines.append(
            f"运势分数：{fortune_analysis.get('fortune_score', '未知')}"
        )
        effect_lines.append(f"细断：{fortune_analysis.get('detailed_analysis', '无')}")
    for relation in detailed_analysis.get("branch_relations") or []:
        effect_lines.append(
            f"{relation.get('type', '普通')}：{relation.get('description', '无')}"
        )
    for suggestion in detailed_analysis.get("suggestions") or []:
        effect_lines.append(f"建议：{suggestion}")

    source_lines = [
        "来源：FateBridge 离线时运分析",
        "引用：fatebridge.analysis.timing_effects / analyze_liuyue_comprehensive",
    ]

    return _render_snapshot_text(
        [
            ("查询信息", query_lines),
            ("流月信息", liuyue_lines),
            ("流年联动", combo_lines),
            ("影响摘要", effect_lines),
            ("来源", source_lines),
        ]
    )


def _build_dayun_snapshot_text(
    *,
    person_name: Optional[str],
    birth_datetime: datetime,
    normalized_birth_datetime: datetime,
    timezone_name: str,
    analysis_age: int,
    dayun_info: Optional[Dict[str, Any]],
    element_effects: Dict[str, Any],
    summary: str,
) -> str:
    query_lines = [
        f"姓名：{person_name or '未提供'}",
        f"分析年龄：{analysis_age}",
        f"出生时间：{birth_datetime.strftime('%Y-%m-%d %H:%M')}",
        f"归一时间：{normalized_birth_datetime.strftime('%Y-%m-%d %H:%M')}",
        f"时区：{timezone_name}",
        f"摘要：{summary}",
    ]
    if dayun_info:
        dayun_lines = [
            f"当前大运：{dayun_info.get('pillar', dayun_info.get('current_dayun', '未知'))}",
            f"大运干支：{dayun_info.get('stem', '未知')}{dayun_info.get('branch', '未知')}",
            f"起运年龄：{dayun_info.get('start_age', '未知')}",
            f"累计行运年数(起运至今)：{dayun_info.get('dayun_age', '未知')}",
            f"本运已行年数：{dayun_info.get('years_in_period', '未知')}",
        ]
    else:
        dayun_lines = ["当前大运：不可用"]

    effect_lines = [
        f"总体五行：{element_effects.get('overall_effect', '未知')}",
    ]
    for element, change_info in (element_effects.get("element_changes") or {}).items():
        if change_info.get("change") != 0:
            effect_lines.append(
                f"{element}：{change_info.get('change_type', '变化')} "
                f"({change_info.get('original', '未知')} -> {change_info.get('new', '未知')})"
            )

    source_lines = [
        "来源：FateBridge 离线大运分析",
        "引用：fatebridge.analysis.timing_effects / analyze_dayun_effects",
    ]
    return _render_snapshot_text(
        [
            ("查询信息", query_lines),
            ("大运信息", dayun_lines),
            ("影响摘要", effect_lines),
            ("来源", source_lines),
        ]
    )


def _build_liunian_snapshot_text(
    *,
    person_name: Optional[str],
    birth_datetime: datetime,
    normalized_birth_datetime: datetime,
    timezone_name: str,
    target_year: int,
    liunian_info: Dict[str, Any],
    element_effects: Dict[str, Any],
    summary: str,
) -> str:
    query_lines = [
        f"姓名：{person_name or '未提供'}",
        f"目标年份：{target_year}",
        f"出生时间：{birth_datetime.strftime('%Y-%m-%d %H:%M')}",
        f"归一时间：{normalized_birth_datetime.strftime('%Y-%m-%d %H:%M')}",
        f"时区：{timezone_name}",
        f"摘要：{summary}",
    ]
    year_lines = [
        f"流年：{liunian_info.get('pillar', '未知')}",
        f"年干支：{liunian_info.get('stem', '未知')}{liunian_info.get('branch', '未知')}",
        f"五行：{liunian_info.get('element', '未知')}",
    ]
    effect_lines = [
        f"总体五行：{element_effects.get('overall_effect', '未知')}",
    ]
    for element, change_info in (element_effects.get("element_changes") or {}).items():
        if change_info.get("change") != 0:
            effect_lines.append(
                f"{element}：{change_info.get('change_type', '变化')} "
                f"({change_info.get('original', '未知')} -> {change_info.get('new', '未知')})"
            )
    source_lines = [
        "来源：FateBridge 离线流年分析",
        "引用：fatebridge.analysis.timing_effects / analyze_liunian_effects",
    ]
    return _render_snapshot_text(
        [
            ("查询信息", query_lines),
            ("流年信息", year_lines),
            ("影响摘要", effect_lines),
            ("来源", source_lines),
        ]
    )


def _build_liuri_snapshot_text(
    *,
    person_name: Optional[str],
    birth_datetime: datetime,
    normalized_birth_datetime: datetime,
    timezone_name: str,
    analysis_date: datetime,
    analysis_calendar_context: Dict[str, Any],
    liuri_info: Dict[str, Any],
    element_effects: Dict[str, Any],
    summary: str,
) -> str:
    current_term = (analysis_calendar_context.get("current_solar_term") or {}).get(
        "name", "未知"
    )
    next_term = (analysis_calendar_context.get("next_solar_term") or {}).get(
        "name", "未知"
    )
    query_lines = [
        f"姓名：{person_name or '未提供'}",
        f"分析时刻：{analysis_date.strftime('%Y-%m-%d %H:%M')}",
        f"出生时间：{birth_datetime.strftime('%Y-%m-%d %H:%M')}",
        f"归一时间：{normalized_birth_datetime.strftime('%Y-%m-%d %H:%M')}",
        f"时区：{timezone_name}",
        f"分析日节气：{current_term} -> {next_term}",
        f"摘要：{summary}",
    ]
    day_lines = [
        f"流日：{liuri_info.get('pillar', '未知')}",
        f"日干支：{liuri_info.get('stem', '未知')}{liuri_info.get('branch', '未知')}",
        f"五行：{liuri_info.get('element', '未知')}",
        f"星期：{liuri_info.get('weekday', '未知')}",
    ]
    effect_lines = [
        f"总体五行：{element_effects.get('overall_effect', '未知')}",
    ]
    for element, change_info in (element_effects.get("element_changes") or {}).items():
        if change_info.get("change") != 0:
            effect_lines.append(
                f"{element}：{change_info.get('change_type', '变化')} "
                f"({change_info.get('original', '未知')} -> {change_info.get('new', '未知')})"
            )
    source_lines = [
        "来源：FateBridge 离线流日分析",
        "引用：fatebridge.analysis.timing_effects / analyze_liuri_effects",
    ]
    return _render_snapshot_text(
        [
            ("查询信息", query_lines),
            ("流日信息", day_lines),
            ("影响摘要", effect_lines),
            ("来源", source_lines),
        ]
    )


def _build_liushi_snapshot_text(
    *,
    person_name: Optional[str],
    birth_datetime: datetime,
    normalized_birth_datetime: datetime,
    timezone_name: str,
    analysis_date: datetime,
    analysis_calendar_context: Dict[str, Any],
    liushi_info: Dict[str, Any],
    detailed_analysis: Dict[str, Any],
    element_effects: Dict[str, Any],
    summary: str,
) -> str:
    current_term = (analysis_calendar_context.get("current_solar_term") or {}).get(
        "name", "未知"
    )
    next_term = (analysis_calendar_context.get("next_solar_term") or {}).get(
        "name", "未知"
    )
    query_lines = [
        f"姓名：{person_name or '未提供'}",
        f"分析时刻：{analysis_date.strftime('%Y-%m-%d %H:%M')}",
        f"出生时间：{birth_datetime.strftime('%Y-%m-%d %H:%M')}",
        f"归一时间：{normalized_birth_datetime.strftime('%Y-%m-%d %H:%M')}",
        f"时区：{timezone_name}",
        f"分析日节气：{current_term} -> {next_term}",
        f"摘要：{summary}",
    ]
    hour_lines = [
        f"流时：{liushi_info.get('pillar', '未知')}",
        f"时干支：{liushi_info.get('stem', '未知')}{liushi_info.get('branch', '未知')}",
        f"五行：{liushi_info.get('element', '未知')}",
        f"纳音：{liushi_info.get('nayin', '未知')}",
        f"时刻：{liushi_info.get('analysis_datetime', '未知')}",
        f"时辰支：{liushi_info.get('shichen', '未知')}",
    ]
    effect_lines = [
        f"总体五行：{element_effects.get('overall_effect', '未知')}",
        f"十神关系：{detailed_analysis.get('stem_relation', '未知')}",
    ]
    fortune_analysis = detailed_analysis.get("fortune_analysis") or {}
    if fortune_analysis:
        effect_lines.append(
            f"运势等级：{fortune_analysis.get('overall_fortune', '未知')}"
        )
        effect_lines.append(
            f"运势分数：{fortune_analysis.get('fortune_score', '未知')}"
        )
        effect_lines.append(f"细断：{fortune_analysis.get('detailed_analysis', '无')}")
    for relation in detailed_analysis.get("branch_relations") or []:
        effect_lines.append(
            f"{relation.get('type', '普通')}：{relation.get('description', '无')}"
        )
    for suggestion in detailed_analysis.get("suggestions") or []:
        effect_lines.append(f"建议：{suggestion}")

    source_lines = [
        "来源：FateBridge 离线流时分析",
        "引用：fatebridge.analysis.timing_effects / analyze_liushi_effects",
    ]
    return _render_snapshot_text(
        [
            ("查询信息", query_lines),
            ("流时信息", hour_lines),
            ("影响摘要", effect_lines),
            ("来源", source_lines),
        ]
    )


def _build_jieqi_timeline_snapshot_text(
    *,
    person_name: Optional[str],
    birth_datetime: datetime,
    normalized_birth_datetime: datetime,
    timezone_name: str,
    target_year: int,
    target_year_jieqi: List[Dict[str, Any]],
    jieqi_timeline: List[Dict[str, Any]],
    summary: str,
) -> str:
    query_lines = [
        f"姓名：{person_name or '未提供'}",
        f"目标年份：{target_year}",
        f"出生时间：{birth_datetime.strftime('%Y-%m-%d %H:%M')}",
        f"归一时间：{normalized_birth_datetime.strftime('%Y-%m-%d %H:%M')}",
        f"时区：{timezone_name}",
        f"节点数量：{len(jieqi_timeline)}",
        f"摘要：{summary}",
    ]
    annual_lines = [
        f"{item.get('name', '未知')}：{item.get('datetime', '未知')} / 日干支 {item.get('day_ganzhi', '未知')}"
        for item in target_year_jieqi
    ]
    timeline_lines = [
        f"{item.get('order', '?')}. {item.get('jieqi', {}).get('name', '未知')} / "
        f"{item.get('analysis_anchor', '未知')} / 流月 {item.get('liuyue', {}).get('pillar', '未知')} / "
        f"流日 {item.get('liuri', {}).get('pillar', '未知')} / {item.get('overall_effect', '未知')}"
        for item in jieqi_timeline
    ]
    source_lines = [
        "来源：FateBridge 离线节气时间轴分析",
        "引用：fatebridge.core.timing.calculate_jieqi_transition_timeline",
    ]

    return _render_snapshot_text(
        [
            ("查询信息", query_lines),
            ("年度节气", annual_lines),
            ("节点时间轴", timeline_lines),
            ("来源", source_lines),
        ]
    )


def _build_comprehensive_timing_snapshot_text(
    *,
    person_name: Optional[str],
    birth_datetime: datetime,
    normalized_birth_datetime: datetime,
    timezone_name: str,
    analysis_date: datetime,
    current_age: int,
    analysis_calendar_context: Dict[str, Any],
    dayun_info: Dict[str, Any],
    liunian_info: Dict[str, Any],
    liuyue_info: Dict[str, Any],
    liuri_info: Dict[str, Any],
    liushi_info: Dict[str, Any],
    combined_effects: Dict[str, Any],
    summary: str,
) -> str:
    current_term = (analysis_calendar_context.get("current_solar_term") or {}).get(
        "name", "未知"
    )
    next_term = (analysis_calendar_context.get("next_solar_term") or {}).get(
        "name", "未知"
    )
    query_lines = [
        f"姓名：{person_name or '未提供'}",
        f"分析时刻：{analysis_date.strftime('%Y-%m-%d %H:%M')}",
        f"当前年龄：{current_age}",
        f"出生时间：{birth_datetime.strftime('%Y-%m-%d %H:%M')}",
        f"归一时间：{normalized_birth_datetime.strftime('%Y-%m-%d %H:%M')}",
        f"时区：{timezone_name}",
        f"分析日节气：{current_term} -> {next_term}",
        f"摘要：{summary}",
    ]

    if dayun_info.get("error"):
        dayun_lines = [f"当前大运：{dayun_info['error']}"]
    else:
        dayun_lines = [
            f"当前大运：{dayun_info.get('current_dayun', '未知')}",
            f"大运干支：{dayun_info.get('stem', '未知')}{dayun_info.get('branch', '未知')}",
            f"起运年龄：{dayun_info.get('start_age', '未知')}",
            f"累计行运年数(起运至今)：{dayun_info.get('dayun_age', '未知')}",
            f"本运已行年数：{dayun_info.get('years_in_period', '未知')}",
            f"概览：{dayun_info.get('summary', '无')}",
        ]

    flow_lines = [
        f"流年：{liunian_info.get('pillar', '未知')} / {liunian_info.get('summary', '无')}",
        f"流月：{liuyue_info.get('pillar', '未知')} / {liuyue_info.get('summary', '无')}",
        f"流日：{liuri_info.get('pillar', '未知')} / {liuri_info.get('summary', '无')}",
        f"流时：{liushi_info.get('pillar', '未知')} / {liushi_info.get('summary', '无')}",
    ]

    impact_lines = [
        f"综合效应：{combined_effects.get('overall_effect', '未知')}",
    ]
    for element, change_info in (combined_effects.get("element_changes") or {}).items():
        if change_info.get("change") != 0:
            impact_lines.append(
                f"{element}：{change_info.get('change_type', '变化')} "
                f"({change_info.get('original', '未知')} -> {change_info.get('new', '未知')})"
            )

    source_lines = [
        "来源：FateBridge 离线综合时运分析",
        "引用：fatebridge.analysis.timing_effects / comprehensive_timing_analysis",
    ]
    return _render_snapshot_text(
        [
            ("查询信息", query_lines),
            ("大运摘要", dayun_lines),
            ("流年流月流日", flow_lines),
            ("综合影响", impact_lines),
            ("来源", source_lines),
        ]
    )
