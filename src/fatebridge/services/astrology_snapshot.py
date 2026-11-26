"""Assemble and export natal chart snapshots."""

from __future__ import annotations

from typing import Any

from fatebridge.core.export_parser import parse_export_content
from fatebridge.services.astrology_classical_snapshot import (
    _build_almuten_figuris_line,
    _build_classical_lines,
    _build_classical_patterns_lines,
    _build_dispositor_lines,
    _build_fixed_stars_lines,
    _build_lots_lines,
    _build_planetary_hours_line,
    _build_temperament_lines,
    _build_topic_almuten_line,
)
from fatebridge.services.astrology_snapshot_sections import (
    ELEMENT_LABELS_ZH,
    MODALITY_LABELS_ZH,
    PLANET_LABELS_ZH,
    _build_angle_lines,
    _build_aspect_lines,
    _build_balance_line,
    _build_guolao_snapshot_sections,
    _build_house_lines,
    _build_planet_lines,
    _chart_calculation_notes,
    _format_degree,
    _format_zodiac_degree,
)
from fatebridge.services.snapshot_builders import render_snapshot_text

CORE_CHART_EXPORT_TECHNIQUES = {
    "chart": "astrochart",
    "chart13": "astrochart",
    "hellen_chart": "astrochart_like",
    "india_chart": "indiachart",
    "guolao_chart": "guolao",
}


def _build_standard_chart_snapshot_sections(
    payload: dict[str, Any], *, chart_variant: str
) -> list[tuple[str, str]]:
    person_info = payload.get("person_info", {})
    chart_profile = payload.get("chart_profile", {})
    info_lines = [
        f"姓名：{person_info.get('name', '未提供')}",
        f"出生地：{person_info.get('birth_place', '未提供')}",
        f"出生时间：{str(person_info.get('birth_datetime', '未提供')).replace('T', ' ')}",
        f"时区：{person_info.get('birth_timezone', '未提供')}",
        f"经纬度：{_format_degree(person_info.get('birth_longitude'))} / {_format_degree(person_info.get('birth_latitude'))}",
        f"盘型：{chart_profile.get('chart_type', chart_variant)}",
        f"黄道：{chart_profile.get('zodiac_label_zh', chart_profile.get('zodiac', '未知'))}",
        f"宫制：{chart_profile.get('house_system_label_zh', chart_profile.get('house_system', '未知'))}",
        f"精度层：{chart_profile.get('engine_precision', '未知')}",
    ]
    info_lines.extend(_chart_calculation_notes(payload))
    if clock := person_info.get("clock_conversion"):
        clock_label = (
            "地方平太阳时"
            if clock["input_clock_basis"] == "local_mean_solar"
            else "地方真太阳时"
        )
        info_lines.append(
            f"声明的输入钟时：{clock['input_wall_datetime']}（{clock_label}）"
        )

    detail_lines = [
        f"元素分布：{_build_balance_line(payload.get('element_balance', {}), ELEMENT_LABELS_ZH)}",
        f"模式分布：{_build_balance_line(payload.get('modality_balance', {}), MODALITY_LABELS_ZH)}",
    ]

    if chart_variant == "chart13":
        detail_lines.append(f"13扇区数量：{len(payload.get('thirteen_sectors', []))}")

    hellenistic = payload.get("hellenistic", {})
    if chart_variant == "hellen_chart":
        ascendant_ruler = hellenistic.get("ascendant_ruler")
        angular_planets = hellenistic.get("angular_planets")
        angular_labels = ", ".join(
            PLANET_LABELS_ZH.get(item, item) for item in (angular_planets or [])
        )
        detail_lines.extend(
            [
                f"昼夜属性：{hellenistic.get('sect', '未知')}",
                f"上升主星：{PLANET_LABELS_ZH.get(ascendant_ruler, '未知')}",
                f"角宫星体：{angular_labels or ('未知' if angular_planets is None else '无')}",
            ]
        )

    india = payload.get("india", {})
    if chart_variant == "india_chart":
        info_lines.append(
            "印占证据使用独立 Parashari 规则；通用古典、元素和西占角度相位段仅保留为历史参考。"
        )
        detail_lines.extend(
            [
                f"Ayanamsha：{_format_degree(india.get('ayanamsha'))}",
                f"上升宿：{india.get('rising_nakshatra', '未知')}",
                f"月宿：{india.get('moon_nakshatra', '未知')}",
            ]
        )
        detail_lines.append(
            f"印占状态：{india.get('status', 'legacy')}；规则：{india.get('ruleset_id', '未计算核心')}"
        )
        for chart_name, chart in india.get("charts", {}).items():
            detail_lines.append(
                f"{chart_name} 上升：{chart['ascendant']['sign_zh']}（该分盘整宫起点）"
            )
            for planet in chart["planets"]:
                detail_lines.append(
                    f"{chart_name} {planet['label_zh']}：{planet['sign_zh']} {_format_zodiac_degree(planet['degree_in_sign'])}，第{planet['house']}宫，尊贵状态 {planet['dignity']['state']}"
                )
        for source in india.get("rulesets", []):
            detail_lines.append(f"印占来源：{source['title']}")
        if "birth_time_sensitivity" in india:
            detail_lines.append(
                f"生时敏感性：{india['birth_time_sensitivity']['status']}；{india['birth_time_sensitivity']['limitation']}"
            )

    greek_lines = (
        ["福点：未知（上升无法确定）。"]
        if chart_variant == "hellen_chart"
        and hellenistic.get("ascendant_ruler") is None
        else ["无"]
    )
    lot_of_fortune = hellenistic.get("lot_of_fortune")
    if isinstance(lot_of_fortune, dict):
        greek_lines = [
            f"福点：{lot_of_fortune.get('sign_zh', '未知')} {_format_zodiac_degree(lot_of_fortune.get('degree_in_sign'))}，第{lot_of_fortune.get('house', '—')}宫"
        ]

    return [
        ("起盘信息", "\n".join(info_lines).strip()),
        ("宫位宫头", _build_house_lines(payload.get("houses", []))),
        ("星与虚点", _build_angle_lines(payload.get("angles", {}))),
        ("信息", "\n".join(detail_lines).strip()),
        ("相位", _build_aspect_lines(payload.get("aspects", []))),
        ("行星", _build_planet_lines(payload.get("planets", []))),
        ("古典", _build_classical_lines(payload)),
        ("主宰", _build_dispositor_lines(payload)),
        ("命主", _build_almuten_figuris_line(payload)),
        ("宫主星", _build_topic_almuten_line(payload)),
        ("阿拉伯点", _build_lots_lines(payload)),
        ("古典格局", _build_classical_patterns_lines(payload)),
        ("恒星", _build_fixed_stars_lines(payload)),
        ("行星时", _build_planetary_hours_line(payload)),
        ("体质", _build_temperament_lines(payload)),
        ("希腊点", "\n".join(greek_lines).strip()),
    ]


def _build_chart_snapshot(
    payload: dict[str, Any], chart_variant: str
) -> dict[str, Any]:
    technique = CORE_CHART_EXPORT_TECHNIQUES.get(chart_variant, "astrochart")
    sections = (
        _build_guolao_snapshot_sections(payload)
        if chart_variant == "guolao_chart"
        else _build_standard_chart_snapshot_sections(
            payload, chart_variant=chart_variant
        )
    )
    snapshot_text = render_snapshot_text(sections)
    snapshot_export = parse_export_content(
        technique=technique,
        content=snapshot_text,
    )
    return {
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }
