"""Readable timing and calendar snapshots without calculation orchestration."""

from datetime import datetime
from typing import Any

from fatebridge.core.timing_carriers import timing_carrier_snapshot_lines
from fatebridge.core.timing_roots import timing_root_snapshot_lines
from fatebridge.core.timing_strength import timing_strength_snapshot_lines
from fatebridge.services.snapshot_builders import (
    build_snapshot_export,
)
from fatebridge.services.snapshot_builders import (
    render_snapshot_lines as _render_snapshot_text,
)
from fatebridge.services.timing_calendar_snapshots import (
    build_jieqi_year_snapshot_text as _build_jieqi_year_snapshot_text,
)
from fatebridge.services.timing_calendar_snapshots import (
    build_nongli_time_snapshot_text as _build_nongli_time_snapshot_text,
)
from fatebridge.services.timing_calendar_snapshots import term_clock_text
from fatebridge.services.timing_clock import (
    AnalysisClockReference,
    analysis_clock_snapshot_lines,
)
from fatebridge.utils.birth_clock import birth_clock_snapshot_lines
from fatebridge.utils.formatting import format_clock_datetime

__all__ = ["_build_jieqi_year_snapshot_text", "_build_nongli_time_snapshot_text"]


def _element_change_lines(effects: dict[str, Any]) -> list[str]:
    return [
        f"{element}：{row['change_type']} ({row['original']:.3f}% -> {row['new']:.3f}%)"
        for element, row in (effects.get("element_changes") or {}).items()
        if row["change"]
    ]


def _dayun_start_age_lines(info: dict[str, Any]) -> list[str]:
    raw = info.get("start_age_unrounded")
    if raw is None:
        return [f"起运年龄：{info.get('start_age', '未知')}"]
    else:
        pass
    return [
        f"起运年龄：{info.get('start_age', '未知')}（原始间隔折算后向上取整，至少1岁，仅展示）",
        f"起运折算年龄：{raw!r}（浮点展示）；{info.get('start_age_precise', '未知')}（两位展示）",
    ]


def _build_liuyue_snapshot_text(
    *,
    person_name: str | None,
    birth_datetime: datetime,
    normalized_birth_datetime: datetime,
    timezone_name: str,
    analysis_date: datetime,
    analysis_calendar_context: dict[str, Any],
    liuyue_info: dict[str, Any],
    liunian_info: dict[str, Any] | None,
    detailed_analysis: dict[str, Any],
    element_effects: dict[str, Any],
    combination_effects: dict[str, Any],
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
        f"出生时间：{format_clock_datetime(birth_datetime)}",
        f"归一时间：{format_clock_datetime(normalized_birth_datetime)}",
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
        f"窗口时刻：{term_clock_text(solar_term_window.get('start_term', {}))} -> {term_clock_text(solar_term_window.get('next_term', {}))}",
    ]

    combo_lines: list[str] = []
    if liunian_info:
        combo_lines.append(f"流年：{liunian_info.get('pillar', '未知')}")
        combo_lines.append(
            f"流年月支：{liuyue_info.get('branch', '未知')} / 流年支：{liunian_info.get('branch', '未知')}"
        )
    else:
        pass
    liuyue_liunian = combination_effects.get("liuyue_liunian") or {}
    if liuyue_liunian:
        combo_lines.append(
            f"组合总效应：{liuyue_liunian.get('overall_effect', '未知')}"
        )
        for relation in liuyue_liunian.get("relations") or []:
            combo_lines.append(
                f"{relation.get('type', '普通')}：{relation.get('description', '无')} / "
                f"{relation.get('effect', '无')}"
            )
    else:
        pass
    if not combo_lines:
        combo_lines.append("无流年联动信息")
    else:
        pass

    effect_lines = [
        f"十神关系：{detailed_analysis.get('stem_relation', '未知')}",
        f"总体五行：{element_effects.get('overall_effect', '未知')}",
    ]
    for relation in detailed_analysis.get("branch_relations") or []:
        effect_lines.append(
            f"{relation.get('type', '普通')}：{relation.get('description', '无')}"
        )

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


def _birth_range_snapshot_lines(data: dict[str, Any] | None) -> list[str]:
    if data is None:
        return []
    else:
        pass
    candidates = data.get("current_dayun_candidates") or []
    status_labels = {"before_dayun": "尚未起运", "beyond_calculation": "超出已配置期数"}
    labels = [
        item.get("pillar")
        or status_labels.get(item.get("status"), item.get("status", "不可用"))
        for item in candidates
    ]
    candidate_text = "、".join(labels)
    if data.get("dayun_assessment_status") == "unavailable_missing_gender":
        candidate_text = "未计算（顺逆所需性别未提供）"
    else:
        pass
    lines = [
        f"已声明出生时间范围：±{data['uncertainty_minutes']}分钟；逐分钟核对{data['sample_count']}个输入",
        f"本命四柱候选数：{len(data.get('pillars_candidates') or [])}",
        f"当前大运候选：{candidate_text}",
        "下列单盘和时运摘要对应名义出生输入；范围敏感时须结合全部候选解读。",
        "采样数量不是概率，逐分钟核对未证明采样间秒级无变化。",
    ]
    if data.get("event_analysis") is not None:
        lines.append(
            f"另核对{data.get('additional_event_probe_count', 0)}个派生事件探针；"
            "无分钟样本的事件候选也须保留，探针频次不是概率，派生微秒不认证出生记录。"
        )
        lines.append(
            "事件括区间不是物理精度；全部连续候选、交运状态与边界极值仍未认证。"
        )
        if data["event_analysis"].get("unresolved_event_orders"):
            lines.append("校正钟面与节令事件存在未决顺序，不能只选其中一种解释。")
        else:
            pass
    else:
        pass
    if data.get("dayun_event_analysis") is not None:
        lines.append(
            f"大运历法事件探针{data.get('dayun_event_probe_count', 0)}个；"
            "公历月长、闰日裁剪与未来跳时或回拨可使交运边界跳变，须保留尚未起运、相邻期数等全部状态；连续极值仍未认证。计算覆盖期数不是寿命估计。"
        )
        kinds = {e.get("kind") for e in data["dayun_event_analysis"].get("events", [])}
        names = [
            label
            for kind, label in (
                ("dayun_analysis_moment", "分析时刻逆像"),
                ("dayun_decade_leap_clip", "十年闰日裁剪"),
                ("dayun_future_civil_fold_end", "未来回拨结束"),
            )
            if kind in kinds
        ]
        if names:
            lines.append("本次实际核对的补充事件：" + "、".join(names) + "。")
        else:
            pass
        if data["dayun_event_analysis"].get("unresolved_cells"):
            lines.append("大运事件分区存在未决项，已核对点未证明整段候选完整。")
        else:
            pass
    else:
        pass
    if data.get("boundary_ranges_vary"):
        lines.append(
            "交运边界随出生输入变化，已核对探针的起止包络见birth_time_sensitivity.dayun_boundary_ranges；未认证连续极值。"
        )
    else:
        pass
    return lines


def _build_dayun_snapshot_text(
    *,
    person_name: str | None,
    birth_datetime: datetime,
    normalized_birth_datetime: datetime,
    timezone_name: str,
    analysis_age: int,
    dayun_info: dict[str, Any] | None,
    element_effects: dict[str, Any],
    summary: str,
    birth_time_sensitivity: dict[str, Any] | None = None,
) -> str:
    query_lines = [
        f"姓名：{person_name or '未提供'}",
        f"分析年龄：{analysis_age}",
        f"出生时间：{format_clock_datetime(birth_datetime)}",
        f"归一时间：{format_clock_datetime(normalized_birth_datetime)}",
        f"时区：{timezone_name}",
        f"摘要：{summary}",
    ]
    query_lines.extend(_birth_range_snapshot_lines(birth_time_sensitivity))
    if dayun_info and dayun_info.get("status"):
        dayun_lines = [f"大运状态：{dayun_info.get('message', '本次未选出大运')}"]
    elif dayun_info:
        dayun_lines = [
            f"当前大运：{dayun_info.get('pillar', dayun_info.get('current_dayun', '未知'))}",
            f"大运干支：{dayun_info.get('stem', '未知')}{dayun_info.get('branch', '未知')}",
            *_dayun_start_age_lines(dayun_info),
            f"累计行运年数(起运至今)：{dayun_info.get('dayun_age', '未知')}",
            f"本运已行年数：{dayun_info.get('years_in_period', '未知')}",
            f"选运依据：{dayun_info.get('selection_basis', '未知')}",
            f"本运起止（含起不含止）：{dayun_info.get('start_at', '未知')} -> {dayun_info.get('end_at', '未知')}",
        ]
    else:
        dayun_lines = ["当前大运：不可用"]

    effect_lines = [
        f"总体五行：{element_effects.get('overall_effect', '未知')}",
        *_element_change_lines(element_effects),
    ]

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
    person_name: str | None,
    birth_datetime: datetime,
    normalized_birth_datetime: datetime,
    timezone_name: str,
    target_year: int,
    liunian_info: dict[str, Any],
    element_effects: dict[str, Any],
    summary: str,
) -> str:
    query_lines = [
        f"姓名：{person_name or '未提供'}",
        f"目标年份：{target_year}",
        f"出生时间：{format_clock_datetime(birth_datetime)}",
        f"归一时间：{format_clock_datetime(normalized_birth_datetime)}",
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
        *_element_change_lines(element_effects),
    ]
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
    person_name: str | None,
    birth_datetime: datetime,
    normalized_birth_datetime: datetime,
    timezone_name: str,
    analysis_date: datetime,
    analysis_calendar_context: dict[str, Any],
    liuri_info: dict[str, Any],
    element_effects: dict[str, Any],
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
        f"出生时间：{format_clock_datetime(birth_datetime)}",
        f"归一时间：{format_clock_datetime(normalized_birth_datetime)}",
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
        *_element_change_lines(element_effects),
    ]
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
    person_name: str | None,
    birth_datetime: datetime,
    normalized_birth_datetime: datetime,
    timezone_name: str,
    analysis_date: datetime,
    analysis_calendar_context: dict[str, Any],
    liushi_info: dict[str, Any],
    detailed_analysis: dict[str, Any],
    element_effects: dict[str, Any],
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
        f"出生时间：{format_clock_datetime(birth_datetime)}",
        f"归一时间：{format_clock_datetime(normalized_birth_datetime)}",
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
    for relation in detailed_analysis.get("branch_relations") or []:
        effect_lines.append(
            f"{relation.get('type', '普通')}：{relation.get('description', '无')}"
        )

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
    person_name: str | None,
    birth_datetime: datetime,
    normalized_birth_datetime: datetime,
    timezone_name: str,
    target_year: int,
    target_year_jieqi: list[dict[str, Any]],
    jieqi_timeline: list[dict[str, Any]],
    summary: str,
) -> str:
    query_lines = [
        f"姓名：{person_name or '未提供'}",
        f"目标年份：{target_year}",
        f"出生时间：{format_clock_datetime(birth_datetime)}",
        f"归一时间：{format_clock_datetime(normalized_birth_datetime)}",
        f"时区：{timezone_name}",
        f"节点数量：{len(jieqi_timeline)}",
        f"摘要：{summary}",
    ]
    annual_lines = [
        f"{item.get('name', '未知')}：{term_clock_text(item)} / 日干支 {item.get('day_ganzhi', '未定义' if 'datetime_utc' in item else '未知')}"
        for item in target_year_jieqi
    ]
    timeline_lines = [
        f"{item.get('order', '?')}. {item.get('jieqi', {}).get('name', '未知')} / "
        + (
            "本节气区间无可重放的当地整分"
            if "analysis_anchor_status" in item
            else f"{item.get('analysis_anchor', '未知')} / 流月 {item.get('liuyue', {}).get('pillar', '未知')} / "
            f"流日 {item.get('liuri', {}).get('pillar', '未知')} / {item.get('overall_effect', '未知')}"
        )
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
    person_name: str | None,
    birth_datetime: datetime,
    normalized_birth_datetime: datetime,
    timezone_name: str,
    analysis_date: datetime,
    current_age: int,
    analysis_calendar_context: dict[str, Any],
    dayun_info: dict[str, Any],
    liunian_info: dict[str, Any],
    liuyue_info: dict[str, Any],
    liuri_info: dict[str, Any],
    liushi_info: dict[str, Any],
    combined_effects: dict[str, Any],
    summary: str,
    birth_time_sensitivity: dict[str, Any] | None = None,
    interaction_analysis: dict[str, Any] | None = None,
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
        f"出生时间：{format_clock_datetime(birth_datetime)}",
        f"归一时间：{format_clock_datetime(normalized_birth_datetime)}",
        f"时区：{timezone_name}",
        f"分析日节气：{current_term} -> {next_term}",
        f"摘要：{summary}",
    ]
    query_lines.extend(_birth_range_snapshot_lines(birth_time_sensitivity))

    if dayun_info.get("error"):
        dayun_lines = [f"当前大运：{dayun_info['error']}"]
    else:
        dayun_lines = [
            f"当前大运：{dayun_info.get('current_dayun', '未知')}",
            f"大运干支：{dayun_info.get('stem', '未知')}{dayun_info.get('branch', '未知')}",
            *_dayun_start_age_lines(dayun_info),
            f"累计行运年数(起运至今)：{dayun_info.get('dayun_age', '未知')}",
            f"本运已行年数：{dayun_info.get('years_in_period', '未知')}",
            f"选运依据：{dayun_info.get('selection_basis', '未知')}",
            f"本运起止（含起不含止）：{dayun_info.get('start_at', '未知')} -> {dayun_info.get('end_at', '未知')}",
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
        *_element_change_lines(combined_effects),
    ]

    source_lines = [
        "来源：FateBridge 离线综合时运分析",
        "引用：fatebridge.services.timing_state / build_current_timing_state",
    ]
    impact_lines.extend(timing_carrier_snapshot_lines(interaction_analysis or {}))
    if interaction_analysis and "root_context" in interaction_analysis:
        impact_lines.extend(
            timing_root_snapshot_lines(interaction_analysis["root_context"])
        )
    else:
        pass
    if interaction_analysis and "strength_projection" in interaction_analysis:
        impact_lines.extend(
            timing_strength_snapshot_lines(interaction_analysis["strength_projection"])
        )
    else:
        pass
    return _render_snapshot_text(
        [
            ("查询信息", query_lines),
            ("大运摘要", dayun_lines),
            ("流年流月流日", flow_lines),
            ("综合影响", impact_lines),
            ("来源", source_lines),
        ]
    )


def with_birth_clock_reference(
    result: dict[str, Any], *, technique: str, selected_sections: list[str] | None
) -> dict[str, Any]:
    lines = birth_clock_snapshot_lines(result["calendar_context"]["birth_time_input"])
    # note (snapshot): Keep birth-clock evidence in the recognized query section for filtered exports.
    marker = "[查询信息]\n"
    if marker not in result["snapshot_text"]:
        raise ValueError("时运快照缺少查询信息，无法交付出生钟时输入依据")
    else:
        pass
    result["snapshot_text"] = result["snapshot_text"].replace(
        marker, marker + "\n".join(lines) + "\n", 1
    )
    result["snapshot_export"] = build_snapshot_export(
        technique=technique,
        snapshot_text=result["snapshot_text"],
        selected_sections=selected_sections,
    )
    return result


def with_analysis_reference(
    result: dict[str, Any],
    reference: AnalysisClockReference,
    *,
    technique: str,
    selected_sections: list[str] | None,
) -> dict[str, Any]:
    result["analysis_reference"] = reference
    lines = analysis_clock_snapshot_lines(reference)
    if lines:
        result["snapshot_text"] += "\n\n" + _render_snapshot_text(
            [("分析时刻依据", lines)]
        )
        result["snapshot_export"] = build_snapshot_export(
            technique=technique,
            snapshot_text=result["snapshot_text"],
            selected_sections=selected_sections,
        )
    else:
        pass
    return with_birth_clock_reference(
        result, technique=technique, selected_sections=selected_sections
    )
