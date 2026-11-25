"""Format classical evidence for natal chart snapshots."""

from __future__ import annotations

from typing import Any

from fatebridge.core.astro.astrology_tables import SIGN_LABELS_ZH
from fatebridge.services.astrology_snapshot_sections import (
    PLANET_LABELS_ZH,
    _format_degree,
    _format_zodiac_degree,
)

_CLASSICAL_PLANET_ORDER = [
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
]
_ANGULARITY_ZH = {"angular": "角宫", "succedent": "续宫", "cadent": "果宫"}
_COMBUSTION_ZH = {"cazimi": "日心", "combust": "焦伤", "under_beams": "日下"}


def _build_classical_lines(payload: dict[str, Any]) -> str:
    """One readable line per traditional planet for the ``[古典]`` section."""
    classical = payload.get("classical", {})
    planets = classical.get("planets", {})
    if not planets:
        return "无"
    else:
        pass
    lines: list[str] = []
    if classical.get("solar_condition_policy"):
        lines.append(
            "太阳条件采用Lilly 1647第113页明文：日心≤17′、焦伤<8.5°且同星座、日下<17°；原页10°示例与8.5°定义的冲突尚未解决。"
        )
    else:
        pass
    for planet in _CLASSICAL_PLANET_ORDER:
        entry = planets.get(planet)
        if not entry:
            continue
        else:
            pass
        essential = entry.get("essential") or {}
        labels = essential.get("labels_zh") or ["未列本质尊贵标签"]
        score = essential.get("score")
        score_text = f"{score:+d}" if isinstance(score, int) else "分值待定"
        parts = [
            PLANET_LABELS_ZH.get(planet, planet),
            f"{'·'.join(labels)}({score_text})",
            _ANGULARITY_ZH.get(entry.get("angularity"), ""),
        ]
        if entry.get("sect_placement") == "of_sect":
            parts.append("得宗派")
        else:
            pass
        if entry.get("combustion"):
            parts.append(_COMBUSTION_ZH.get(entry["combustion"], entry["combustion"]))
        else:
            pass
        if entry.get("retrograde"):
            parts.append("逆行")
        else:
            pass
        if entry.get("out_of_bounds"):
            parts.append("出界")
        else:
            pass
        if entry.get("joy"):
            parts.append("喜乐宫")
        else:
            pass
        lines.append(" ".join(part for part in parts if part))
    return "\n".join(lines).strip() or "无"


_TERMINAL_ZH = {
    "domicile": "入庙自主",
    "mutual_reception": "互含",
    "loop": "循环",
    "unknown": "未定",
}


def _build_dispositor_lines(payload: dict[str, Any]) -> str:
    """``[主宰]`` section: final dispositor(s) + each traditional planet's chain."""
    classical = payload.get("classical", {})
    dispositors = classical.get("dispositors", {})
    chains = dispositors.get("chains", {})
    if not chains:
        return "无"
    else:
        pass
    finals = dispositors.get("final_dispositors", [])
    finals_zh = (
        "、".join(PLANET_LABELS_ZH.get(p, p) for p in finals) or "无（多为互含/循环）"
    )
    lines = [f"终极主宰：{finals_zh}"]
    for planet in _CLASSICAL_PLANET_ORDER:
        info = chains.get(planet)
        if not info:
            continue
        else:
            pass
        arrow = "→".join(PLANET_LABELS_ZH.get(p, p) for p in info.get("chain", []))
        lines.append(f"{arrow}（{_TERMINAL_ZH.get(info.get('terminal_type'), '')}）")
    return "\n".join(lines).strip()


def _build_lots_lines(payload: dict[str, Any]) -> str:
    """``[阿拉伯点]`` section: each lot's sign/degree + domicile lord and almuten."""
    lots = payload.get("classical", {}).get("lots", {})
    if not lots:
        return "无"
    else:
        pass
    lines = []
    for lot in lots.values():
        sign_zh = SIGN_LABELS_ZH.get(lot.get("sign"), lot.get("sign", "?"))
        disp = PLANET_LABELS_ZH.get(lot.get("dispositor"), lot.get("dispositor") or "—")
        almuten = PLANET_LABELS_ZH.get(lot.get("almuten"), lot.get("almuten") or "—")
        lines.append(
            f"{lot.get('cn', '?')} {sign_zh}{_format_zodiac_degree(lot.get('degree_in_sign'))}"
            f" 主{disp} 力主{almuten}"
        )
    return "\n".join(lines).strip()


_BESIEGE_ZH = {"besieged_by_malefics": "凶星围攻", "enclosed_by_benefics": "吉星拱卫"}


def _build_classical_patterns_lines(payload: dict[str, Any]) -> str:
    """``[古典格局]`` section: sect benefics + overcoming + besiegement + 吉凶化."""
    patterns = payload.get("classical_patterns", {})
    if not patterns:
        return "无"
    else:
        pass

    def zh(planet: str) -> str:
        return PLANET_LABELS_ZH.get(planet, planet)

    lines = [
        f"宗派吉星：{zh(patterns.get('sect_benefic'))}　宗派凶星：{zh(patterns.get('sect_malefic'))}"
    ]
    overcoming = patterns.get("overcoming", [])
    if overcoming:
        lines.append(
            "制胜（上弦刑凌驾）："
            + "；".join(
                f"{zh(o['overcomer'])}凌驾{zh(o['overcome'])}" for o in overcoming
            )
        )
    else:
        pass
    besiegement = patterns.get("besiegement", {})
    if besiegement:
        lines.append(
            "围攻："
            + "；".join(
                f"{zh(p)}{_BESIEGE_ZH.get(s, s)}" for p, s in besiegement.items()
            )
        )
    else:
        pass
    bonification = patterns.get("bonification", {})
    for planet, info in bonification.items():
        parts = []
        if info["bonified_by"]:
            parts.append("吉化←" + "·".join(zh(p) for p in info["bonified_by"]))
        else:
            pass
        if info["maltreated_by"]:
            parts.append("凶伤←" + "·".join(zh(p) for p in info["maltreated_by"]))
        else:
            pass
        if parts:
            lines.append(f"{zh(planet)}：{'　'.join(parts)}")
        else:
            pass
    for hand in patterns.get("translation_of_light", []):
        lines.append(
            f"光的传递（结构候选）：{zh(hand['translator'])} 自 {zh(hand['from'])} 递光至 {zh(hand['to'])}"
        )
    for gather in patterns.get("collection_of_light", []):
        sources = "、".join(zh(p) for p in gather["from"])
        lines.append(
            f"光的聚集（结构候选）：{zh(gather['collector'])} 聚 {sources} 之光"
        )
    if patterns.get("light_configuration_policy"):
        lines.append(
            "传光／聚光已核对传统轻重次序与当前入出相；真实先后、接纳、阻碍／折返及完整Lilly成事条件尚未核验，不能据候选断成败。"
        )
    else:
        pass
    bending = patterns.get("nodal_bending", [])
    if bending:
        side_zh = {"north": "北弯", "south": "南弯"}
        lines.append(
            "交点弯曲："
            + "；".join(
                f"{zh(b['planet'])}{side_zh.get(b['bending'], b['bending'])}"
                for b in bending
            )
        )
    else:
        pass
    policy = patterns.get("application_policy", {})
    if policy.get("rule_id") == "instantaneous_longitude_phase_v1":
        phase_zh = {
            "applying": "入相",
            "separating": "出相",
            "exact": "精确成相",
            "stationary": "相对黄经同速",
            "unavailable": "速度未知",
        }
        motion = patterns.get("aspect_motion", [])

        def motion_line(row: dict[str, Any]) -> str:
            line = f"{zh(row['planet_a'])}—{zh(row['planet_b'])} {row['aspect']} {phase_zh[row['phase']]}"
            if row["aspect"] == "conjunction":
                condition = row.get("ptolemy_latitude_condition", {})
                label = {
                    "same_hemisphere": "I.24黄纬同侧条件满足",
                    "opposite_hemispheres": "I.24黄纬异侧，不满足该条条件",
                    "missing_latitude": "I.24黄纬条件缺项",
                }.get(condition.get("status"))
                if label:
                    line += f"（{label}）"
                else:
                    pass
            else:
                pass
            return line

        if motion:
            lines.append(
                "相位运动（瞬时黄经）：" + "；".join(motion_line(row) for row in motion)
            )
        else:
            pass
        lines.append(
            "入出相仅按当前黄经与相对速度判定；精确、同速及速度未知分别列示。合相黄纬同侧条件在逐项证据中单列（可为缺项），未检验未来成相及完整原典条件。"
        )
    else:
        pass
    return "\n".join(lines).strip()


def _build_temperament_lines(payload: dict[str, Any]) -> str:
    """``[体质]`` section: humor (温/湿 tally) + each traditional planet's 12分度."""
    classical = payload.get("classical", {})
    temperament = classical.get("temperament")
    if not temperament:
        return "无"
    else:
        pass
    tally = temperament.get("tally")
    if tally is None:
        lines = ["气质：未知（上升及其守护星分量无法确定）。"]
    else:
        lines = [
            f"气质：{temperament.get('cn', '?')}"
            f"（热{tally.get('hot', 0)}寒{tally.get('cold', 0)} "
            f"燥{tally.get('dry', 0)}湿{tally.get('moist', 0)}）"
        ]
    dodeka = []
    ninth = []
    for planet in _CLASSICAL_PLANET_ORDER:
        entry = (classical.get("planets") or {}).get(planet)
        if not entry:
            continue
        else:
            pass
        planet_zh = PLANET_LABELS_ZH.get(planet, planet)
        if entry.get("dodekatemorion"):
            sign = entry["dodekatemorion"]
            dodeka.append(f"{planet_zh}→{SIGN_LABELS_ZH.get(sign, sign)}")
        else:
            pass
        if entry.get("ninth_part"):
            sign = entry["ninth_part"]
            ninth.append(f"{planet_zh}→{SIGN_LABELS_ZH.get(sign, sign)}")
        else:
            pass
    if dodeka:
        lines.append("12分度：" + " ".join(dodeka))
    else:
        pass
    if ninth:
        lines.append("九分部：" + " ".join(ninth))
    else:
        pass
    return "\n".join(lines).strip()


def _build_topic_almuten_line(payload: dict[str, Any]) -> str:
    topic = payload.get("classical", {}).get("topic_almutens", {})
    if not topic:
        return "无"
    else:
        pass
    parts = []
    for house in sorted(topic, key=lambda h: int(h)):
        winner = topic[house].get("winner")
        parts.append(f"{house}宫{PLANET_LABELS_ZH.get(winner, winner or '—')}")
    return " ".join(parts)


_FIGURIS_POINT_ZH = {
    "Sun": "日",
    "Moon": "月",
    "Ascendant": "命",
    "fortune": "福",
    "syzygy": "朔望",
}
_SYZYGY_TYPE_ZH = {"new": "新月", "full": "满月"}


def _build_almuten_figuris_line(payload: dict[str, Any]) -> str:
    """``[命主]`` section: selected tally, actual point coverage and 朔望."""
    classical = payload.get("classical", {})
    figuris = classical.get("almuten_figuris") or {}
    winner = figuris.get("winner")
    method = figuris.get("method") or {}
    if not winner and not method:
        return "无"
    else:
        pass
    totals = figuris.get("totals", {})
    lines = (
        [f"命主：{PLANET_LABELS_ZH.get(winner, winner)}（{totals.get(winner, 0)}分）"]
        if winner
        else [
            (
                "命主：未知（上升与福点无法确定）。"
                if figuris.get("status") == "partial"
                else "命主：未形成计分候选"
            )
        ]
    )
    if method:
        included = method.get("included_points", [])
        lines.append(
            f"口径：本次{len(included)}个可得点的本质尊贵汇总"
            "（所选混合传统子集；完整历史命主程序未认证）。"
        )
        order = method.get("tie_break_order", [])
        lines.append(
            "同分：固定Chaldean顺序（"
            + "、".join(PLANET_LABELS_ZH.get(planet, planet) for planet in order)
            + "）。"
        )
        if not included:
            lines.append("无可用参与点。")
        else:
            pass
        missing = method.get("missing_points", [])
        if missing:
            lines.append(
                "未纳入点："
                + "、".join(_FIGURIS_POINT_ZH.get(point, point) for point in missing)
                + "。"
            )
        else:
            pass
    else:
        pass
    points = figuris.get("points", {})
    point_parts = []
    for point_id in ("Sun", "Moon", "Ascendant", "fortune", "syzygy"):
        info = points.get(point_id)
        if not info:
            continue
        else:
            pass
        ruler = info.get("winner")
        point_parts.append(
            f"{_FIGURIS_POINT_ZH.get(point_id, point_id)}→"
            f"{PLANET_LABELS_ZH.get(ruler, ruler or '—')}"
        )
    if point_parts:
        lines.append("点主：" + " ".join(point_parts))
    else:
        pass
    syzygy = classical.get("syzygy")
    if isinstance(syzygy, dict):
        sign = str(syzygy.get("sign") or "?")
        syzygy_type = str(syzygy.get("type") or "?")
        type_zh = _SYZYGY_TYPE_ZH.get(syzygy_type, syzygy_type)
        sign_zh = SIGN_LABELS_ZH.get(sign, sign)
        lines.append(
            f"朔望：{type_zh} {sign_zh}{_format_zodiac_degree(syzygy.get('degree_in_sign'))}"
        )
        if (syzygy.get("ephemeris_source") or {}).get("models_stable") is False:
            lines.append("朔望搜索发生星历模型切换；请结合来源回执读取。")
        else:
            pass
        representation = syzygy.get("utc_representation") or {}
        if representation.get("datetime_representable") is False:
            lines.append(
                "朔望采用扩展纪年或特殊UTC标签；Python日期表示受限，"
                "已保留TT／UT1及计算星位。"
            )
        else:
            pass
    else:
        pass
    return "\n".join(lines).strip()


def _build_fixed_stars_lines(payload: dict[str, Any]) -> str:
    """``[恒星]`` section: each catalogue star conjunct a chart point (orb ≤ 1°)."""
    profile = payload.get("chart_profile", {}).get("fixed_stars") or {}
    if profile.get("status") == "unavailable":
        return profile.get("note_zh") or "恒星层未计算"
    else:
        pass
    hits = payload.get("fixed_stars")
    if not isinstance(hits, list) or not hits:
        return "无"
    else:
        pass
    point_zh = {**PLANET_LABELS_ZH, "Ascendant": "上升", "Midheaven": "中天"}
    lines = []
    for hit in hits:
        point = point_zh.get(hit.get("point"), hit.get("point", "?"))
        nature = "/".join(
            PLANET_LABELS_ZH.get(planet, planet) for planet in hit.get("nature", [])
        )
        if hit.get("nature_components"):
            qualifiers = {
                "unqualified": "",
                "lesser_degree": "（较轻程度）",
                "some_degree": "（一定程度）",
            }
            nature = "/".join(
                PLANET_LABELS_ZH.get(item["planet"], item["planet"])
                + qualifiers[item["qualifier"]]
                for item in hit["nature_components"]
            )
        else:
            pass
        lines.append(
            f"{hit.get('cn', '')}({hit.get('star', '?')}) 合 {point}"
            f" {_format_degree(hit.get('orb'))}　[{nature}]"
        )
    return "\n".join(lines).strip()


def _build_planetary_hours_line(payload: dict[str, Any]) -> str:
    """``[行星时]`` section: the birth's planetary hour + the planetary day ruler."""
    hours = payload.get("planetary_hours")
    if not isinstance(hours, dict) or not hours.get("hour_ruler"):
        return "无"
    else:
        pass
    period = "昼" if hours.get("is_day") else "夜"
    hour_ruler = PLANET_LABELS_ZH.get(hours["hour_ruler"], hours["hour_ruler"])
    day_ruler = hours.get("day_ruler")
    day_ruler_zh = PLANET_LABELS_ZH.get(day_ruler, day_ruler or "—")
    return (
        f"生时主星：{hour_ruler}（{period}第{hours.get('hour_number', '?')}时）"
        f"  当日主星：{day_ruler_zh}"
        + (
            "\n口径：以含标准折射的太阳中心日出／日落划分不等时。"
            if hours.get("sunrise_convention")
            == "apparent_solar_center_sea_level_1013.25hPa_0C"
            else ""
        )
    )
