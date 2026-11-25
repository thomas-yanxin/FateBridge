"""Format core chart coordinates and Guolao snapshot sections."""

from __future__ import annotations

from typing import Any

from fatebridge.core.guolao import guolao_moira

PLANET_LABELS_ZH: dict[Any, str] = {
    "Sun": "太阳",
    "Moon": "月亮",
    "Mercury": "水星",
    "Venus": "金星",
    "Mars": "火星",
    "Jupiter": "木星",
    "Saturn": "土星",
    "Uranus": "天王星",
    "Neptune": "海王星",
    "Pluto": "冥王星",
    "North Node": "北交点",
}

ASPECT_LABELS_ZH: dict[Any, str] = {
    "conjunction": "合相",
    "sextile": "六合",
    "square": "刑相",
    "trine": "拱相",
    "opposition": "冲相",
}

ELEMENT_LABELS_ZH = {
    "Fire": "火",
    "Earth": "土",
    "Air": "风",
    "Water": "水",
}


MODALITY_LABELS_ZH = {
    "Cardinal": "基本",
    "Fixed": "固定",
    "Mutable": "变动",
}


def _format_degree(value: Any) -> str:
    try:
        return f"{float(value):.2f}°"
    except (TypeError, ValueError):
        return "—"


def _format_zodiac_degree(value: Any) -> str:
    """A sign-relative display must never promote the coordinate to 30°."""
    try:
        degree = float(value) % 30.0
        if degree < 30 and round(degree, 2) == 30:
            return "29.99…°"
        else:
            pass
        return _format_degree(degree)
    except (TypeError, ValueError):
        return "—"


def _build_balance_line(balance: dict[str, Any], labels: dict[str, str]) -> str:
    ordered_keys = [key for key in labels if key in balance]
    if not ordered_keys:
        return "无"
    else:
        pass
    return "，".join(f"{labels[key]} {balance.get(key, 0)}" for key in ordered_keys)


def _build_house_lines(houses: list[dict[str, Any]]) -> str:
    return (
        "\n".join(
            f"第{item['house']}宫：{item['sign_zh']} {_format_zodiac_degree(item['cusp_longitude'])}"
            for item in houses
        ).strip()
        or "无"
    )


def _build_angle_lines(angles: dict[str, Any]) -> str:
    ascendant = angles.get("ascendant", {})
    midheaven = angles.get("midheaven", {})
    return "\n".join(
        [
            f"Asc：{ascendant.get('sign_zh', '未知')} {_format_zodiac_degree(ascendant.get('longitude'))}",
            f"MC：{midheaven.get('sign_zh', '未知')} {_format_zodiac_degree(midheaven.get('longitude'))}",
        ]
    ).strip()


def _build_planet_lines(planets: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in planets:
        extras: list[str] = []
        dignity = item.get("dignity")
        if dignity and dignity.get("dignity") in {
            "rulership",
            "exaltation",
            "detriment",
            "fall",
        }:
            extras.append(f"{dignity['status_zh']}（{dignity['dignity']}）")
        else:
            pass
        if item.get("sector13") is not None:
            extras.append(f"13扇区 {item['sector13']}")
        else:
            pass
        if item.get("nakshatra"):
            extras.append(f"宿 {item['nakshatra']}")
        else:
            pass
        if item.get("su28"):
            extras.append(f"二十八宿 {item['su28']}")
        else:
            pass
        extras_text = f"，{'，'.join(extras)}" if extras else ""
        lines.append(
            f"{PLANET_LABELS_ZH.get(item['id'], item['id'])}："
            f"{item.get('sign_zh', '未知')} {_format_zodiac_degree(item.get('degree_in_sign'))}，"
            f"第{item.get('house', '—')}宫，黄纬 {_format_degree(item.get('latitude'))}"
            f"{extras_text}"
        )
    return "\n".join(lines).strip() or "无"


def _build_aspect_lines(aspects: list[dict[str, Any]]) -> str:
    if not aspects:
        return "无"
    else:
        pass
    return "\n".join(
        f"{PLANET_LABELS_ZH.get(item['planet_a'], item['planet_a'])}"
        f" 与 {PLANET_LABELS_ZH.get(item['planet_b'], item['planet_b'])}"
        f" 形成 {ASPECT_LABELS_ZH.get(item['aspect'], item['aspect'])}，"
        f"容许度 {_format_degree(item['orb'])}"
        for item in aspects
    )


def _chart_calculation_notes(payload: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for field in (
        "ephemeris_reference_points",
        "angle_definition",
        "house_axis_convention",
        "house_position_projection",
        "orbital_fallback",
        "fixed_stars",
    ):
        qualification = payload.get("chart_profile", {}).get(field) or {}
        note = qualification.get("note_zh")
        if note and note not in notes:
            notes.append(note)
        else:
            pass
    return notes


def _build_guolao_snapshot_sections(payload: dict[str, Any]) -> list[tuple[str, str]]:
    person_info = payload["person_info"]
    chart_profile = payload["chart_profile"]
    guolao = payload["guolao"]
    life = guolao["life_palace"]
    profile = guolao["profile"]
    validation = guolao["validation"]

    setup_lines = [
        f"姓名：{person_info.get('name', '未提供')}",
        f"出生地：{person_info.get('birth_place', '未提供')}",
        f"出生时间：{str(person_info.get('birth_datetime', '未提供')).replace('T', ' ')}",
        f"时区：{person_info.get('birth_timezone', '未提供')}",
        f"经纬度：{_format_degree(person_info.get('birth_longitude'))} / {_format_degree(person_info.get('birth_latitude'))}",
        f"黄道：{chart_profile.get('zodiac_label_zh', chart_profile.get('zodiac', '未知'))}",
        f"天文参考宫制：{chart_profile.get('house_system_label_zh', chart_profile.get('house_system', '未知'))}；功能十二宫另按安命逆布",
    ]

    star_lines = [
        f"{item['name_zh']}：黄经 {_format_degree(item['longitude'])}，"
        f"{item['palace_branch']}宫（宫主{item['palace_lord']}），"
        f"研究宿位{item['mansion']['su28']} {_format_degree(item['mansion']['degree_in_mansion'])}，"
        f"度主{item['mansion']['degree_lord']}"
        for item in guolao.get("bodies", [])
    ]
    if input_clock := profile.get("input_clock"):
        setup_lines[3] = (
            "输入钟制："
            + (
                "地方平太阳时"
                if input_clock["input_clock_basis"] == "local_mean_solar"
                else "地方真太阳时"
            )
            + "；不视为民用时区"
        )
    else:
        pass
    if profile["reference_geometry"]["houses_status"] != "available":
        setup_lines.append("天文参考宫头未分配，未替换为其他宫制。")
    else:
        pass

    life_lines = [
        f"命宫：{life['branch']}，宫主{life['palace_lord']}，生时{life['birth_hour_branch']}。",
    ]
    if life["longitude"] is None and life["mansion"] is None:
        life_lines.append("原典命度与命宿未定。")
    else:
        pass

    shensha_lines = [
        f"星期主星：{PLANET_LABELS_ZH.get(guolao.get('weekday_ruler', ''), guolao.get('weekday_ruler', '未知'))}",
        f"月宿：{guolao.get('moon_mansion', '未知')}",
        f"底本贵人及岁驾宫支：{guolao.get('god_positions', {}).get('branches', {})}",
        "天贵对应天乙昼贵，玉贵对应玉堂夜贵；年干支暂按立春换年。",
    ]
    timing = guolao.get("timing", {})
    timing_sections = []
    if timing.get("status") == "research_partial":
        annual = timing["small_limit"]
        limits = [
            f"{annual['target_year_stem']}{annual['target_year_branch']}年小限："
            f"{annual['branch']}宫，临本命{annual['natal_functional_palace']}。"
        ]
        if monthly := timing.get("month_limit"):
            month_branch = monthly["branch"] or "未分配"
            limits.append(f"月限（{monthly['month_basis']}）：{month_branch}。")
        else:
            pass
        calendar_datetime = timing["calendar_datetime"]
        calendar_timezone = timing["calendar_timezone"]
        calendar_label = (
            f"{calendar_datetime}（{calendar_timezone}）"
            if calendar_datetime is not None
            else f"出生区未定义目标时刻的当地钟面（{calendar_timezone}），按UTC年份选立春窗口"
        )
        timing_sections.append(
            (
                "目标时刻小限与十一曜研究位置",
                "\n".join(
                    [
                        *limits,
                        f"换年钟面：{calendar_label}；天文计算保留同一目标瞬间。",
                        *[
                            f"{b['name_zh']}：所选黄道黄经{_format_degree(b['zodiac_longitude'])}，"
                            f"{b['palace_branch']}宫，{b['mansion']['su28']} "
                            f"{_format_degree(b['mansion']['degree_in_mansion'])}，"
                            f"临本命{b['natal_functional_palace']}"
                            for b in timing["transit_bodies"]
                        ],
                        *timing["limitations"],
                    ]
                ),
            )
        )
    else:
        pass

    return [
        ("起盘信息", "\n".join(setup_lines).strip()),
        (
            "安命与十二功能宫",
            "\n".join(
                [
                    *life_lines,
                    *[
                        f"{p['palace']}：{p['branch']}宫，宫主{p['lord']}"
                        for p in guolao.get("palaces", [])
                    ],
                ]
            ),
        ),
        ("七政四余宫位与二十八宿星曜", "\n".join(star_lines).strip() or "无"),
        ("神煞", "\n".join(shensha_lines).strip()),
        ("政余格局", guolao_moira.build_section_text(guolao.get("moira_patterns", []))),
        *timing_sections,
        (
            "规则与验收",
            "\n".join(
                [
                    "研究口径：" + guolao.get("lunar_mansion_system", "未知"),
                    (
                        "已通过原典验收。"
                        if validation["classical_acceptance_passed"]
                        else "尚未通过原典验收。"
                    ),
                    *[
                        r["title"] + "：" + r["source_url"]
                        for r in guolao.get("rulesets", [])
                    ],
                    *validation["limitations"],
                ]
            ),
        ),
    ]
