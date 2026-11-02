"""
FateBridge astrology services.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import datetime
from typing import Any, Dict, List, Optional

from fatebridge.core import guolao_moira
from fatebridge.core.astro.birth import AstroBirthInfo, build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload, build_midpoint_payload
from fatebridge.core.astro.reference import NODE_BODIES
from fatebridge.core.astro.relationship import build_relative_payload
from fatebridge.core.astrology_tables import SIGN_LABELS_ZH
from fatebridge.core.export_parser import parse_export_content
from fatebridge.core.guolao_birth_clock import coherent_guolao_solar_call
from fatebridge.core.jyotish_sources import coherent_india_call
from fatebridge.services.snapshot_builders import (
    render_snapshot_text as _render_snapshot_text,
)
from fatebridge.services.structured_snapshot import render_structured_snapshot_text
from fatebridge.utils.errors import calculation_guard

SUPPORTED_CHART_VARIANTS = {
    "chart",
    "chart13",
    "hellen_chart",
    "guolao_chart",
    "india_chart",
}

PLANET_LABELS_ZH: Dict[Any, str] = {
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

ASPECT_LABELS_ZH: Dict[Any, str] = {
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

CORE_CHART_EXPORT_TECHNIQUES = {
    "chart": "astrochart",
    "chart13": "astrochart",
    "hellen_chart": "astrochart_like",
    "india_chart": "indiachart",
    "guolao_chart": "guolao",
}

SIGN_INTERPRETATION = {
    "Aries": {
        "core": "主动开局、喜欢用直接行动证明自己",
        "emotion": "情绪反应快，越能立刻推进事情越安心",
        "persona": "给人果断、带头、不太拖泥带水的印象",
        "relationship": "相处时重视爽快、真实与行动回应",
        "growth": "学会在速度之外保留耐心与策略空间",
    },
    "Taurus": {
        "core": "重视稳定、质感与可持续累积",
        "emotion": "需要可预期的节奏和身体层面的安全感",
        "persona": "给人稳、慢热、抗压和讲究质感的印象",
        "relationship": "会用陪伴、资源与稳定投入表达在意",
        "growth": "在守成之外练习适度调整和试错",
    },
    "Gemini": {
        "core": "好奇、灵活，靠信息交换建立存在感",
        "emotion": "情绪需要被说出来、想清楚、聊明白",
        "persona": "给人机敏、会观察、反应快的印象",
        "relationship": "喜欢有来有往的沟通和脑力互动",
        "growth": "把分散兴趣收束成真正能沉淀的方向",
    },
    "Cancer": {
        "core": "重视归属、照顾与内在安全边界",
        "emotion": "情绪细腻，容易先感受气氛再决定行动",
        "persona": "给人温和、敏感、有保护欲的印象",
        "relationship": "会通过照料、记挂与情绪承接表达亲近",
        "growth": "在保护自己时也保留清晰表达需求的能力",
    },
    "Leo": {
        "core": "希望被看见，也愿意主动发光和承担",
        "emotion": "需要被尊重、被肯定，才能稳定输出热情",
        "persona": "给人有存在感、体面、愿意撑场面的印象",
        "relationship": "看重真诚欣赏、忠诚与明确的心意表达",
        "growth": "把自尊转化为稳定创作，而不是只靠外界回馈",
    },
    "Virgo": {
        "core": "靠辨析、修正和打磨细节建立秩序",
        "emotion": "情绪容易通过整理、复盘、改进来安放",
        "persona": "给人认真、克制、可靠且有标准的印象",
        "relationship": "会通过帮忙、照应细节和务实支持表达在乎",
        "growth": "把挑剔变成建设性判断，而不是过度消耗自己",
    },
    "Libra": {
        "core": "追求平衡、审美与关系中的恰当分寸",
        "emotion": "情绪常受关系气氛影响，需要和谐与对话",
        "persona": "给人有礼、讲究体面、会协调的印象",
        "relationship": "重视对等、好看、顺畅与互相体谅",
        "growth": "在顾及关系时别放掉自己的明确立场",
    },
    "Scorpio": {
        "core": "重视深度、真实和穿透表象的力量感",
        "emotion": "情绪浓度高，信任建立后才会真正敞开",
        "persona": "给人沉静、强烈、边界感重的印象",
        "relationship": "需要深度投入、忠诚与心理层面的链接",
        "growth": "把控制欲转化为洞察力和稳定承诺",
    },
    "Sagittarius": {
        "core": "靠探索、扩张和寻找意义感来确认方向",
        "emotion": "情绪需要空间、远景和更大的可能性",
        "persona": "给人开阔、直率、愿意尝试的印象",
        "relationship": "喜欢坦率、成长型、能一起看更远的关系",
        "growth": "把理想落到具体行动，避免只停留在热情",
    },
    "Capricorn": {
        "core": "重视结果、责任与长期结构的建立",
        "emotion": "情绪习惯先收住，再用规划与承担感处理",
        "persona": "给人稳重、专业、有边界的印象",
        "relationship": "重视可靠、兑现承诺和现实层面的共建",
        "growth": "在自律之外保留柔软和情绪表达的出口",
    },
    "Aquarius": {
        "core": "重视独立判断、系统视角和非传统路径",
        "emotion": "需要精神空间与自由度，先想明白再投入",
        "persona": "给人理性、特别、保持距离但有想法的印象",
        "relationship": "适合建立在理念认同和彼此尊重基础上的连结",
        "growth": "把抽离感转化为稳定参与，而不是只做旁观者",
    },
    "Pisces": {
        "core": "重视感受、想象和与更大整体的连接",
        "emotion": "情绪边界柔软，容易吸收环境中的细微波动",
        "persona": "给人温柔、感性、带点梦境感的印象",
        "relationship": "常以共情、包容和情绪理解来靠近别人",
        "growth": "学会在敏感之中建立边界和现实锚点",
    },
}

HOUSE_TOPICS: Dict[Any, str] = {
    1: "自我呈现、身体感受与个人启动方式",
    2: "资源、安全感与价值判断",
    3: "沟通、学习与近距离环境",
    4: "家庭根基、内在归属与私人空间",
    5: "创造表达、恋爱、兴趣与舞台感",
    6: "日常事务、工作方法、健康与服务意识",
    7: "亲密关系、合作与镜像课题",
    8: "共享资源、心理转化与深层牵引",
    9: "信念、远行、学术与世界观扩展",
    10: "事业方向、公众形象与成就目标",
    11: "社群、朋友、理想与未来议题",
    12: "潜意识、退隐、疗愈与无形压力",
}

ELEMENT_THEMES = {
    "Fire": "火元素偏强，行动与直觉往往先于迟疑，适合先点燃热情再校正路线。",
    "Earth": "土元素偏强，会优先考虑可落地、可持续、可验证的部分，耐力是优势。",
    "Air": "风元素偏强，思考、交流与观察是天然驱动力，适合在连接信息中找答案。",
    "Water": "水元素偏强，感受力和共情力很突出，很多决定先经过内在情绪过滤。",
}

MODALITY_THEMES = {
    "Cardinal": "基本模式偏强，适合起头、定方向、推动局面，但也要防止过早耗尽冲劲。",
    "Fixed": "固定模式偏强，定力和坚持是优势，但遇到转弯时要练习更柔软地调整。",
    "Mutable": "变动模式偏强，适应性和转译能力很强，但需要防止能量过于分散。",
}

ASPECT_INTERPRETATION = {
    "conjunction": "这组能量会被强力绑在一起，优点是集中，难点是容易彼此放大。",
    "sextile": "这组能量存在顺手的配合感，只要主动使用，就能形成实际助力。",
    "square": "这组能量之间摩擦较强，往往通过不舒服的过程逼出成长和行动。",
    "trine": "这组能量流动自然，常能形成天赋感，但也容易因为太顺而少了打磨。",
    "opposition": "这组能量像在两端拉扯，需要在对立面之间学会平衡和整合。",
}

CHALLENGING_ASPECTS = {"square", "opposition"}
HARMONIOUS_ASPECTS = {"sextile", "trine"}


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
        return _format_degree(degree)
    except (TypeError, ValueError):
        return "—"


def _build_balance_line(balance: Dict[str, Any], labels: Dict[str, str]) -> str:
    ordered_keys = [key for key in labels if key in balance]
    if not ordered_keys:
        return "无"
    return "，".join(f"{labels[key]} {balance.get(key, 0)}" for key in ordered_keys)


def _build_house_lines(houses: List[Dict[str, Any]]) -> str:
    return (
        "\n".join(
            f"第{item['house']}宫：{item['sign_zh']} {_format_zodiac_degree(item['cusp_longitude'])}"
            for item in houses
        ).strip()
        or "无"
    )


def _build_angle_lines(angles: Dict[str, Any]) -> str:
    ascendant = angles.get("ascendant", {})
    midheaven = angles.get("midheaven", {})
    return "\n".join(
        [
            f"Asc：{ascendant.get('sign_zh', '未知')} {_format_zodiac_degree(ascendant.get('longitude'))}",
            f"MC：{midheaven.get('sign_zh', '未知')} {_format_zodiac_degree(midheaven.get('longitude'))}",
        ]
    ).strip()


def _build_planet_lines(planets: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for item in planets:
        extras: List[str] = []
        dignity = item.get("dignity")
        if dignity and dignity.get("dignity") in {
            "rulership",
            "exaltation",
            "detriment",
            "fall",
        }:
            extras.append(f"{dignity['status_zh']}（{dignity['dignity']}）")
        if item.get("sector13") is not None:
            extras.append(f"13扇区 {item['sector13']}")
        if item.get("nakshatra"):
            extras.append(f"宿 {item['nakshatra']}")
        if item.get("su28"):
            extras.append(f"二十八宿 {item['su28']}")
        extras_text = f"，{'，'.join(extras)}" if extras else ""
        lines.append(
            f"{PLANET_LABELS_ZH.get(item['id'], item['id'])}："
            f"{item.get('sign_zh', '未知')} {_format_zodiac_degree(item.get('degree_in_sign'))}，"
            f"第{item.get('house', '—')}宫，黄纬 {_format_degree(item.get('latitude'))}"
            f"{extras_text}"
        )
    return "\n".join(lines).strip() or "无"


def _build_aspect_lines(aspects: List[Dict[str, Any]]) -> str:
    if not aspects:
        return "无"
    return "\n".join(
        f"{PLANET_LABELS_ZH.get(item['planet_a'], item['planet_a'])}"
        f" 与 {PLANET_LABELS_ZH.get(item['planet_b'], item['planet_b'])}"
        f" 形成 {ASPECT_LABELS_ZH.get(item['aspect'], item['aspect'])}，"
        f"容许度 {_format_degree(item['orb'])}"
        for item in aspects
    )


def _planet_by_id(planets: List[Dict[str, Any]], planet_id: str) -> Dict[str, Any]:
    return next((item for item in planets if item.get("id") == planet_id), {})


def _top_balance_keys(balance: Dict[str, Any]) -> List[str]:
    if not balance:
        return []
    maximum = max(int(value) for value in balance.values())
    return (
        sorted(key for key, value in balance.items() if int(value) == maximum)
        if maximum > 0
        else []
    )


def _house_focus(planets: List[Dict[str, Any]]) -> List[tuple[int, int]]:
    counter = Counter(
        int(item["house"])
        for item in planets
        if item.get("house") is not None and item.get("id") not in NODE_BODIES
    )
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def _sign_focus(planets: List[Dict[str, Any]]) -> List[tuple[str, int]]:
    counter = Counter(
        item["sign"]
        for item in planets
        if item.get("sign") and item.get("id") not in NODE_BODIES
    )
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def _format_topic_list(items: List[str]) -> str:
    filtered = [item for item in items if item]
    if not filtered:
        return "未知主题"
    if len(filtered) == 1:
        return filtered[0]
    if len(filtered) == 2:
        return f"{filtered[0]}与{filtered[1]}"
    return f"{'、'.join(filtered[:-1])}与{filtered[-1]}"


def _build_signature(planets: List[Dict[str, Any]], angles: Dict[str, Any]) -> str:
    sun = _planet_by_id(planets, "Sun")
    moon = _planet_by_id(planets, "Moon")
    ascendant = angles.get("ascendant", {})
    return (
        f"太阳{sun.get('sign_zh', '未知')}、"
        f"月亮{moon.get('sign_zh', '未知')}、"
        f"上升{ascendant.get('sign_zh', '未知')}"
    )


def _build_dominant_energy(
    element_balance: Dict[str, Any], modality_balance: Dict[str, Any]
) -> str:
    lines: List[str] = []
    for balance, labels, themes, category in [
        (element_balance, ELEMENT_LABELS_ZH, ELEMENT_THEMES, "元素"),
        (modality_balance, MODALITY_LABELS_ZH, MODALITY_THEMES, "模式"),
    ]:
        leaders = _top_balance_keys(balance)
        if len(leaders) == 1:
            leader = leaders[0]
            lines.append(
                f"{labels.get(leader, leader)}{category}数量最多（{balance[leader]}颗）；现代象征参考：{themes.get(leader, '')}"
            )
        elif leaders:
            names = "、".join(labels.get(key, key) for key in leaders)
            lines.append(
                f"{names}{category}数量并列最多（各{balance[leaders[0]]}颗），保留并列。"
            )
    return (
        " ".join(item for item in lines if item).strip() or "当前盘面主导能量尚不明显。"
    )


def _build_core_identity(planets: List[Dict[str, Any]]) -> str:
    sun = _planet_by_id(planets, "Sun")
    if not sun:
        return "本次未返回太阳落点。"
    sign = sun.get("sign")
    trait = SIGN_INTERPRETATION.get(sign or "", {})
    house_topic = HOUSE_TOPICS.get(sun.get("house"), "个人成长议题")
    return (
        f"太阳落在{sun.get('sign_zh', '未知')}第{sun.get('house', '—')}宫，"
        f"现代象征模板将其核心驱动力主题写作{trait.get('core', '自我方向')}；"
        f"该宫的象征领域是{house_topic}。"
    )


def _build_emotional_style(planets: List[Dict[str, Any]]) -> str:
    moon = _planet_by_id(planets, "Moon")
    if not moon:
        return "本次未返回月亮落点。"
    sign = moon.get("sign")
    trait = SIGN_INTERPRETATION.get(sign or "", {})
    house_topic = HOUSE_TOPICS.get(moon.get("house"), "情绪与安全感议题")
    return (
        f"月亮落在{moon.get('sign_zh', '未知')}第{moon.get('house', '—')}宫，"
        f"现代情绪与安全感象征模板为：{trait.get('emotion', '情绪处理方式')}；"
        f"该宫的象征领域是{house_topic}。"
    )


def _build_social_style(planets: List[Dict[str, Any]], angles: Dict[str, Any]) -> str:
    ascendant = angles.get("ascendant", {})
    midheaven = angles.get("midheaven", {})
    asc_trait = SIGN_INTERPRETATION.get(ascendant.get("sign") or "", {})
    mc_trait = SIGN_INTERPRETATION.get(midheaven.get("sign") or "", {})
    mc_topic = HOUSE_TOPICS.get(10, "事业与公众方向")
    lines = []
    if ascendant:
        lines.append(
            f"上升{ascendant.get('sign_zh', '未知')}的现代外在呈现象征是："
            f"{asc_trait.get('persona', '个人风格')}。"
        )
    if midheaven:
        lines.append(
            f"MC落在{midheaven.get('sign_zh', '未知')}，在{mc_topic}的象征读法中，"
            f"对应{mc_trait.get('core', '公众方向的主题')}。"
        )
    return "".join(lines) or "本次未返回上升或MC落点。"


def _build_relationship_pattern(planets: List[Dict[str, Any]]) -> str:
    venus = _planet_by_id(planets, "Venus")
    mars = _planet_by_id(planets, "Mars")
    venus_trait = SIGN_INTERPRETATION.get(venus.get("sign") or "", {})
    mars_trait = SIGN_INTERPRETATION.get(mars.get("sign") or "", {})
    venus_topic = HOUSE_TOPICS.get(venus.get("house"), "关系与价值议题")
    mars_topic = HOUSE_TOPICS.get(mars.get("house"), "行动与欲望议题")
    lines = []
    if venus:
        lines.append(
            f"金星在{venus.get('sign_zh', '未知')}第{venus.get('house', '—')}宫，"
            f"现代关系象征参考：{venus_trait.get('relationship', '关系中的价值感')}；"
            f"该宫领域为{venus_topic}。"
        )
    if mars:
        lines.append(
            f"火星在{mars.get('sign_zh', '未知')}第{mars.get('house', '—')}宫，"
            f"现代行动象征参考：{mars_trait.get('core', '推进目标')}；"
            f"该宫领域为{mars_topic}。"
        )
    return "".join(lines) or "本次未返回金星或火星落点。"


def _build_life_focus(planets: List[Dict[str, Any]]) -> str:
    house_focus = _house_focus(planets)
    sign_focus = _sign_focus(planets)
    lines: List[str] = []
    if house_focus:
        top_houses = [
            (house, count) for house, count in house_focus if count == house_focus[0][1]
        ]
        topics = _format_topic_list(
            [HOUSE_TOPICS.get(house, f"第{house}宫议题") for house, _ in top_houses]
        )
        labels = "、".join(f"第{house}宫({count})" for house, count in top_houses)
        lines.append(f"星体本体数量最多的宫位为{labels}；现代象征领域为{topics}。")
    if sign_focus and sign_focus[0][1] >= 3:
        top_signs = [name for name, count in sign_focus if count == sign_focus[0][1]]
        lines.append(
            "、".join(SIGN_LABELS_ZH.get(name, name) for name in top_signs)
            + f"的星体本体数量并列最多（各{sign_focus[0][1]}颗）。"
            if len(top_signs) > 1
            else f"{SIGN_LABELS_ZH.get(top_signs[0], top_signs[0])}的星体本体数量最多（{sign_focus[0][1]}颗）。"
        )
    north_node = _planet_by_id(planets, "North Node")
    if north_node:
        node_topic = HOUSE_TOPICS.get(north_node.get("house"), "长期成长课题")
        lines.append(
            f"北交点落在{north_node.get('sign_zh', '未知')}第{north_node.get('house', '—')}宫，"
            f"现代成长象征参考为{node_topic}。"
        )
    return " ".join(lines).strip() or "盘面焦点较平均，需要结合现实阶段观察重心。"


def _build_aspect_pattern(aspects: List[Dict[str, Any]]) -> str:
    if not aspects:
        return "本次容许度政策下没有返回主相位命中。"

    top_aspect = min(aspects, key=lambda item: float(item["orb"]))
    aspect_name = top_aspect.get("aspect")
    top_line = (
        f"偏离精确角度最小的主相位是{PLANET_LABELS_ZH.get(top_aspect.get('planet_a'), top_aspect.get('planet_a'))}"
        f"与{PLANET_LABELS_ZH.get(top_aspect.get('planet_b'), top_aspect.get('planet_b'))}"
        f"的{ASPECT_LABELS_ZH.get(aspect_name, aspect_name)}，"
        f"容许度{_format_degree(top_aspect.get('orb'))}。"
    )
    aspect_meaning = ASPECT_INTERPRETATION.get(
        aspect_name or "", "这组能量会成为盘面里很难忽略的主旋律。"
    )
    harmony_count = sum(
        1 for item in aspects if item.get("aspect") in HARMONIOUS_ASPECTS
    )
    tension_count = sum(
        1 for item in aspects if item.get("aspect") in CHALLENGING_ASPECTS
    )
    if tension_count > harmony_count:
        tone = f"所列相位中张力类{tension_count}条、协调类{harmony_count}条；张力类条数较多。"
    elif harmony_count > tension_count:
        tone = f"所列相位中协调类{harmony_count}条、张力类{tension_count}条；协调类条数较多。"
    else:
        tone = f"所列相位中协调类与张力类条数相同（各{harmony_count}条）。"
    return f"{top_line}现代象征参考：{aspect_meaning} {tone}"


def _build_ptolemy_sign_reading(payload: Dict[str, Any]) -> Optional[str]:
    layer = payload.get("classical", {}).get("ptolemy", {})
    if layer.get("status") != "computed_subset":
        return None
    pair = next(
        (
            p
            for p in layer.get("sign_relationships", [])
            if {p["planet_a"], p["planet_b"]} == {"Sun", "Moon"}
        ),
        None,
    )
    if pair is None:
        return None
    facts = []
    if pair["same_sign"]:
        facts.append("位于同一星座")
    if pair["sign_aspect"]:
        quality = {"harmonious": "和谐类", "disharmonious": "不和谐类"}[
            pair["aspect_quality"]
        ]
        facts.append(f"按I.13构成{ASPECT_LABELS_ZH[pair['sign_aspect']]}（{quality}）")
    if pair["commanding_sign"]:
        facts.append(
            f"按I.14，{SIGN_LABELS_ZH[pair['commanding_sign']]}为命令方、{SIGN_LABELS_ZH[pair['obeying_sign']]}为服从方"
        )
    if pair["beholding_equal_power"]:
        facts.append("按I.15属于相互注视、等力关系")
    if pair["disjunct"]:
        facts.append("按I.16排除其他亲缘关系后属于离隔")
    return (
        f"Robbins 1940《四书》I.13–16：{PLANET_LABELS_ZH[pair['planet_a']]}所在的{SIGN_LABELS_ZH[pair['sign_a']]}"
        f"与{PLANET_LABELS_ZH[pair['planet_b']]}所在的{SIGN_LABELS_ZH[pair['sign_b']]}，"
        + "；".join(facts)
        + "。此层按星座关系计算。"
    )


def _build_ptolemy_term_reading(payload: Dict[str, Any]) -> Optional[str]:
    """Report returned term ownership; never turn it into an outcome or score."""
    classical = payload.get("classical", {})
    layer = classical.get("ptolemy", {})
    if layer.get("status") != "computed_subset":
        return None
    lines = []
    for name, planet in layer.get("planets", {}).items():
        terms = planet.get("terms") or {}
        if not terms:
            continue
        owners = []
        for system, label in (
            ("egyptian", "埃及界"),
            ("chaldaean", "迦勒底界"),
            ("ptolemaic", "托勒密界"),
        ):
            term = terms.get(system)
            if term is not None:
                owners.append(
                    f"{label}主{PLANET_LABELS_ZH[term['lord']]}"
                    f"[{term['start_degree']},{term['end_degree']})°"
                )
        lines.append(
            f"{PLANET_LABELS_ZH[name]}在{SIGN_LABELS_ZH[planet['sign']]}："
            + "、".join(owners)
        )
    if not lines:
        return None
    sect = {"day": "昼盘", "night": "夜盘"}[classical["sect"]]
    return (
        f"Robbins 1940《四书》I.20–21（纸本表，{sect}）："
        + "；".join(lines)
        + "。区间含起点、不含终点，按未舍入黄经归界；三种表分别列示，"
        "界主表示该位置的传统归属，不据此推断整体强弱或现实事件。"
    )


def _build_development_advice(
    planets: List[Dict[str, Any]],
    element_balance: Dict[str, Any],
    modality_balance: Dict[str, Any],
) -> str:
    north_node = _planet_by_id(planets, "North Node")
    sign_trait = SIGN_INTERPRETATION.get(north_node.get("sign") or "", {})
    advice_parts: List[str] = []
    advice_parts.append(_build_dominant_energy(element_balance, modality_balance))
    if north_node:
        advice_parts.append(
            f"成长建议可以特别参考北交点：往{sign_trait.get('growth', '更成熟地承担长期课题')}"
            f"，并把重心逐步放到第{north_node.get('house', '—')}宫对应的人生领域。"
        )
    return (
        " ".join(item for item in advice_parts if item).strip()
        or "当前盘面建议先观察现实情境中的重复模式。"
    )


def _build_variant_note(payload: Dict[str, Any], chart_variant: str) -> Optional[str]:
    if chart_variant == "hellen_chart":
        hellenistic = payload.get("hellenistic", {})
        ascendant_ruler = PLANET_LABELS_ZH.get(
            hellenistic.get("ascendant_ruler", ""),
            hellenistic.get("ascendant_ruler", "未知"),
        )
        angular_planets = (
            "、".join(
                PLANET_LABELS_ZH.get(item, item)
                for item in hellenistic.get("angular_planets", [])
            )
            or "无"
        )
        return (
            f"希腊盘补充信息显示这是{ {'day': '日', 'night': '夜'}.get(hellenistic.get('sect'), '未知') }盘，"
            f"上升主星为{ascendant_ruler}，角宫星体有{angular_planets}。"
        )
    if chart_variant == "india_chart":
        india = payload.get("india", {})
        return (
            f"印度律盘里，上升宿为{india.get('rising_nakshatra', '未知')}，"
            f"月宿为{india.get('moon_nakshatra', '未知')}，"
            f"Ayanamsha约为{_format_degree(india.get('ayanamsha'))}。"
        )
    if chart_variant == "chart13":
        if (
            payload.get("sector_profile", {}).get("status")
            == "underdetermined_ascendant"
        ):
            return "角度模型无法解析唯一上升点，13等分扇区未定；后端约定值仅保留在sector_profile及sector13_evidence中供复核，不构成实际落区。"
        return (
            f"13等分扇区以实际上升为起点，分为{len(payload.get('thirteen_sectors', []))}个等宽区间；"
            "sector13是几何落区，不是IAU天文星座，也未建立独立的性格或事件解释规则。"
        )
    if chart_variant == "guolao_chart":
        guolao = payload.get("guolao", {})
        return (
            f"七政四余补充信息里，星期主星为"
            f"{PLANET_LABELS_ZH.get(guolao.get('weekday_ruler', ''), guolao.get('weekday_ruler', '未知'))}，"
            f"月宿为{guolao.get('moon_mansion', '未知')}。"
        )
    return None


def _build_chart_interpretation(
    payload: Dict[str, Any], chart_variant: str
) -> Dict[str, str]:
    planets = payload.get("planets", [])
    angles = payload.get("angles", {})
    element_balance = payload.get("element_balance", {})
    modality_balance = payload.get("modality_balance", {})
    interpretation = {
        "evidence_scope": (
            "以下现代象征模板绑定已返回星体、宫位和相位；原典关系另列，现实建议另列。"
            "classical 为多来源规则；classical.ptolemy 仅覆盖所列原典章节，"
            "不代表原典全文验收或现实预测已验证。"
        ),
        "signature": _build_signature(planets, angles),
        "dominant_energy": _build_dominant_energy(element_balance, modality_balance),
        "core_identity": _build_core_identity(planets),
        "emotional_style": _build_emotional_style(planets),
        "social_style": _build_social_style(planets, angles),
        "relationship_pattern": _build_relationship_pattern(planets),
        "life_focus": _build_life_focus(planets),
        "aspect_pattern": _build_aspect_pattern(payload.get("aspects", [])),
        "development_advice": _build_development_advice(
            planets, element_balance, modality_balance
        ),
    }
    variant_note = _build_variant_note(payload, chart_variant)
    if variant_note:
        interpretation["variant_note"] = variant_note
    original_text = _build_ptolemy_sign_reading(payload)
    if original_text:
        interpretation["original_text_relations"] = original_text
    terms = _build_ptolemy_term_reading(payload)
    if terms:
        interpretation["original_text_terms"] = terms
    return interpretation


def _chart_calculation_notes(payload: Dict[str, Any]) -> List[str]:
    notes: List[str] = []
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
    return notes


def _build_chart_summary(
    chart_variant: str,
    interpretation: Dict[str, str],
    *,
    engine_precision: str,
) -> List[str]:
    chart_label = (
        "FateBridge 离线高精度星盘"
        if engine_precision == "ephemeris_runtime_model"
        else "FateBridge 离线近似星盘"
    )
    lines = [
        f"已生成 {chart_variant} 的 {chart_label}。",
        f"核心签名：{interpretation['signature']}。",
        interpretation["core_identity"],
        interpretation["emotional_style"],
        interpretation["social_style"],
        interpretation["life_focus"],
        interpretation["aspect_pattern"],
        interpretation["development_advice"],
    ]
    if interpretation.get("variant_note"):
        lines.append(interpretation["variant_note"])
    if interpretation.get("original_text_relations"):
        lines.append(interpretation["original_text_relations"])
    if interpretation.get("original_text_terms"):
        lines.append(interpretation["original_text_terms"])
    return lines


def _augment_core_chart_reading(
    payload: Dict[str, Any], chart_variant: str
) -> Dict[str, Any]:
    if chart_variant == "guolao_chart":
        from fatebridge.core.guolao import reading

        return reading(payload)
    interpretation = _build_chart_interpretation(payload, chart_variant)
    planet_paths = {
        planet["id"]: f"planets.{index}"
        for index, planet in enumerate(payload.get("planets", []))
    }

    def refs(*names: str) -> List[str]:
        return [planet_paths[name] for name in names if name in planet_paths]

    # These paths let a host bind quotations to this run's receipt. They are
    # dependencies of deterministic templates, not a semantic grade for prose.
    sources = {
        "signature": refs("Sun", "Moon") + ["angles.ascendant"],
        "dominant_energy": ["element_balance", "modality_balance"],
        "core_identity": refs("Sun"),
        "emotional_style": refs("Moon"),
        "social_style": ["angles.ascendant", "angles.midheaven"],
        "relationship_pattern": refs("Venus", "Mars"),
        "life_focus": ["planets"],
        "aspect_pattern": ["aspects"],
        "development_advice": ["element_balance", "modality_balance"]
        + refs("North Node"),
    }
    if "original_text_relations" in interpretation:
        sources["original_text_relations"] = [
            "classical.ptolemy.sign_relationships",
            "classical.ptolemy.sign_relationship_policy",
        ]
    if "original_text_terms" in interpretation:
        sources["original_text_terms"] = [
            "classical.ptolemy.planets",
            "classical.ptolemy.term_policy",
            "classical.ptolemy.term_source_url",
            "classical.ptolemy.term_transcription_note",
            "classical.sect",
        ]
    if "variant_note" in interpretation:
        sources["variant_note"] = {
            "hellen_chart": ["hellenistic"],
            "india_chart": ["india"],
            "chart13": ["thirteen_sectors", "sector_profile"],
        }.get(chart_variant, ["chart_profile"])
    for key in ("signature", "social_style"):
        for qualification in (
            "angle_definition",
            "house_axis_convention",
            "house_position_projection",
        ):
            if payload.get("chart_profile", {}).get(qualification) is not None:
                sources[key].append(f"chart_profile.{qualification}")
    summary = _build_chart_summary(
        chart_variant,
        interpretation,
        engine_precision=payload.get("chart_profile", {}).get(
            "engine_precision", "approximate_orbital_model"
        ),
    )
    for note in _chart_calculation_notes(payload):
        if note not in summary:
            summary.append(note)
    return {
        "interpretation": interpretation,
        "interpretation_evidence": {
            key: {
                "source_paths": paths,
                "kind": (
                    "practical_suggestion"
                    if key == "development_advice"
                    else (
                        "primary_text_rule_interpretation"
                        if key in {"original_text_relations", "original_text_terms"}
                        else (
                            "calculation_summary"
                            if key in {"signature", "variant_note"}
                            else "modern_symbolic_template"
                        )
                    )
                ),
                "policy_id": (
                    "ptolemy_robbins_sign_relations_v1"
                    if key == "original_text_relations"
                    else (
                        "ptolemy_robbins_printed_terms_v1"
                        if key == "original_text_terms"
                        else "modern_symbolic_templates_v2"
                    )
                ),
            }
            for key, paths in sources.items()
        },
        "summary": summary,
    }


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


def _build_classical_lines(payload: Dict[str, Any]) -> str:
    """One readable line per traditional planet for the ``[古典]`` section."""
    classical = payload.get("classical", {})
    planets = classical.get("planets", {})
    if not planets:
        return "无"
    lines: List[str] = []
    if classical.get("solar_condition_policy"):
        lines.append(
            "太阳条件采用Lilly 1647第113页明文：日心≤17′、焦伤<8.5°且同星座、日下<17°；原页10°示例与8.5°定义的冲突尚未解决。"
        )
    for planet in _CLASSICAL_PLANET_ORDER:
        entry = planets.get(planet)
        if not entry:
            continue
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
        if entry.get("combustion"):
            parts.append(_COMBUSTION_ZH.get(entry["combustion"], entry["combustion"]))
        if entry.get("retrograde"):
            parts.append("逆行")
        if entry.get("out_of_bounds"):
            parts.append("出界")
        if entry.get("joy"):
            parts.append("喜乐宫")
        lines.append(" ".join(part for part in parts if part))
    return "\n".join(lines).strip() or "无"


_TERMINAL_ZH = {
    "domicile": "入庙自主",
    "mutual_reception": "互含",
    "loop": "循环",
    "unknown": "未定",
}


def _build_dispositor_lines(payload: Dict[str, Any]) -> str:
    """``[主宰]`` section: final dispositor(s) + each traditional planet's chain."""
    classical = payload.get("classical", {})
    dispositors = classical.get("dispositors", {})
    chains = dispositors.get("chains", {})
    if not chains:
        return "无"
    finals = dispositors.get("final_dispositors", [])
    finals_zh = (
        "、".join(PLANET_LABELS_ZH.get(p, p) for p in finals) or "无（多为互含/循环）"
    )
    lines = [f"终极主宰：{finals_zh}"]
    for planet in _CLASSICAL_PLANET_ORDER:
        info = chains.get(planet)
        if not info:
            continue
        arrow = "→".join(PLANET_LABELS_ZH.get(p, p) for p in info.get("chain", []))
        lines.append(f"{arrow}（{_TERMINAL_ZH.get(info.get('terminal_type'), '')}）")
    return "\n".join(lines).strip()


def _build_lots_lines(payload: Dict[str, Any]) -> str:
    """``[阿拉伯点]`` section: each lot's sign/degree + domicile lord and almuten."""
    lots = payload.get("classical", {}).get("lots", {})
    if not lots:
        return "无"
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


def _build_classical_patterns_lines(payload: Dict[str, Any]) -> str:
    """``[古典格局]`` section: sect benefics + overcoming + besiegement + 吉凶化."""
    patterns = payload.get("classical_patterns", {})
    if not patterns:
        return "无"

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
    besiegement = patterns.get("besiegement", {})
    if besiegement:
        lines.append(
            "围攻："
            + "；".join(
                f"{zh(p)}{_BESIEGE_ZH.get(s, s)}" for p, s in besiegement.items()
            )
        )
    bonification = patterns.get("bonification", {})
    for planet, info in bonification.items():
        parts = []
        if info["bonified_by"]:
            parts.append("吉化←" + "·".join(zh(p) for p in info["bonified_by"]))
        if info["maltreated_by"]:
            parts.append("凶伤←" + "·".join(zh(p) for p in info["maltreated_by"]))
        if parts:
            lines.append(f"{zh(planet)}：{'　'.join(parts)}")
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

        def motion_line(row: Dict[str, Any]) -> str:
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
            return line

        if motion:
            lines.append(
                "相位运动（瞬时黄经）：" + "；".join(motion_line(row) for row in motion)
            )
        lines.append(
            "入出相仅按当前黄经与相对速度判定；精确、同速及速度未知分别列示。合相黄纬同侧条件在逐项证据中单列（可为缺项），未检验未来成相及完整原典条件。"
        )
    return "\n".join(lines).strip()


def _build_temperament_lines(payload: Dict[str, Any]) -> str:
    """``[体质]`` section: humor (温/湿 tally) + each traditional planet's 12分度."""
    classical = payload.get("classical", {})
    temperament = classical.get("temperament")
    if not temperament:
        return "无"
    tally = temperament.get("tally", {})
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
        planet_zh = PLANET_LABELS_ZH.get(planet, planet)
        if entry.get("dodekatemorion"):
            sign = entry["dodekatemorion"]
            dodeka.append(f"{planet_zh}→{SIGN_LABELS_ZH.get(sign, sign)}")
        if entry.get("ninth_part"):
            sign = entry["ninth_part"]
            ninth.append(f"{planet_zh}→{SIGN_LABELS_ZH.get(sign, sign)}")
    if dodeka:
        lines.append("12分度：" + " ".join(dodeka))
    if ninth:
        lines.append("九分部：" + " ".join(ninth))
    return "\n".join(lines).strip()


def _build_topic_almuten_line(payload: Dict[str, Any]) -> str:
    topic = payload.get("classical", {}).get("topic_almutens", {})
    if not topic:
        return "无"
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


def _build_almuten_figuris_line(payload: Dict[str, Any]) -> str:
    """``[命主]`` section: the Almuten Figuris + its five hylegic points + 朔望."""
    classical = payload.get("classical", {})
    figuris = classical.get("almuten_figuris") or {}
    winner = figuris.get("winner")
    if not winner:
        return "无"
    totals = figuris.get("totals", {})
    lines = [
        f"命主：{PLANET_LABELS_ZH.get(winner, winner)}（{totals.get(winner, 0)}分）"
    ]
    points = figuris.get("points", {})
    point_parts = []
    for point_id in ("Sun", "Moon", "Ascendant", "fortune", "syzygy"):
        info = points.get(point_id)
        if not info:
            continue
        ruler = info.get("winner")
        point_parts.append(
            f"{_FIGURIS_POINT_ZH.get(point_id, point_id)}→"
            f"{PLANET_LABELS_ZH.get(ruler, ruler or '—')}"
        )
    if point_parts:
        lines.append("点主：" + " ".join(point_parts))
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
        representation = syzygy.get("utc_representation") or {}
        if representation.get("datetime_representable") is False:
            lines.append(
                "朔望采用扩展纪年或特殊UTC标签；Python日期表示受限，"
                "已保留TT／UT1及计算星位。"
            )
    return "\n".join(lines).strip()


def _build_fixed_stars_lines(payload: Dict[str, Any]) -> str:
    """``[恒星]`` section: each catalogue star conjunct a chart point (orb ≤ 1°)."""
    profile = payload.get("chart_profile", {}).get("fixed_stars") or {}
    if profile.get("status") == "unavailable":
        return profile.get("note_zh") or "恒星层未计算"
    hits = payload.get("fixed_stars")
    if not isinstance(hits, list) or not hits:
        return "无"
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
        lines.append(
            f"{hit.get('cn', '')}({hit.get('star', '?')}) 合 {point}"
            f" {_format_degree(hit.get('orb'))}　[{nature}]"
        )
    return "\n".join(lines).strip()


def _build_planetary_hours_line(payload: Dict[str, Any]) -> str:
    """``[行星时]`` section: the birth's planetary hour + the planetary day ruler."""
    hours = payload.get("planetary_hours")
    if not isinstance(hours, dict) or not hours.get("hour_ruler"):
        return "无"
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


def _build_standard_chart_snapshot_sections(
    payload: Dict[str, Any], *, chart_variant: str
) -> List[tuple[str, str]]:
    person_info = payload.get("person_info", {})
    chart_profile = payload.get("chart_profile", {})
    interpretation = payload.get("interpretation", {})
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
        interpretation.get("evidence_scope", ""),
        f"元素分布：{_build_balance_line(payload.get('element_balance', {}), ELEMENT_LABELS_ZH)}",
        f"模式分布：{_build_balance_line(payload.get('modality_balance', {}), MODALITY_LABELS_ZH)}",
        f"人格签名：{interpretation.get('signature', '无')}",
        f"主导能量：{interpretation.get('dominant_energy', '无')}",
        f"人生重心：{interpretation.get('life_focus', '无')}",
    ]
    if interpretation.get("original_text_relations"):
        detail_lines.append(interpretation["original_text_relations"])
    if interpretation.get("original_text_terms"):
        detail_lines.append(interpretation["original_text_terms"])

    if chart_variant == "chart13":
        detail_lines.append(f"13扇区数量：{len(payload.get('thirteen_sectors', []))}")

    hellenistic = payload.get("hellenistic", {})
    if chart_variant == "hellen_chart":
        detail_lines.extend(
            [
                f"昼夜属性：{hellenistic.get('sect', '未知')}",
                f"上升主星：{PLANET_LABELS_ZH.get(hellenistic.get('ascendant_ruler', ''), hellenistic.get('ascendant_ruler', '未知'))}",
                f"角宫星体：{', '.join(PLANET_LABELS_ZH.get(item, item) for item in hellenistic.get('angular_planets', [])) or '无'}",
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
            detail_lines.append(f"印占来源：{source['title']} {source['url']}")
        if "birth_time_sensitivity" in india:
            detail_lines.append(
                f"生时敏感性：{india['birth_time_sensitivity']['status']}；{india['birth_time_sensitivity']['limitation']}"
            )

    greek_lines = ["无"]
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
        (
            "可能性",
            "\n".join(
                [
                    f"核心人格：{interpretation.get('core_identity', '无')}",
                    f"情绪风格：{interpretation.get('emotional_style', '无')}",
                    f"外在呈现：{interpretation.get('social_style', '无')}",
                    f"关系模式：{interpretation.get('relationship_pattern', '无')}",
                    f"相位主题：{interpretation.get('aspect_pattern', '无')}",
                    f"成长建议：{interpretation.get('development_advice', '无')}",
                    (
                        f"盘型附注：{interpretation.get('variant_note')}"
                        if interpretation.get("variant_note")
                        else ""
                    ),
                ]
            ).strip(),
        ),
    ]


def _build_guolao_snapshot_sections(payload: Dict[str, Any]) -> List[tuple[str, str]]:
    person_info = payload.get("person_info", {})
    chart_profile = payload.get("chart_profile", {})
    guolao = payload.get("guolao", {})
    interpretation = payload.get("interpretation", {})

    setup_lines = [
        f"姓名：{person_info.get('name', '未提供')}",
        f"出生地：{person_info.get('birth_place', '未提供')}",
        f"出生时间：{str(person_info.get('birth_datetime', '未提供')).replace('T', ' ')}",
        f"时区：{person_info.get('birth_timezone', '未提供')}",
        f"经纬度：{_format_degree(person_info.get('birth_longitude'))} / {_format_degree(person_info.get('birth_latitude'))}",
        f"黄道：{chart_profile.get('zodiac_label_zh', chart_profile.get('zodiac', '未知'))}",
        f"天文参考宫制：{chart_profile.get('house_system_label_zh', chart_profile.get('house_system', '未知'))}；功能十二宫另按安命逆布",
        interpretation.get("signature", "未返回安命解释"),
        interpretation.get("core_identity", ""),
    ]

    star_lines = [
        f"{item['name_zh']}：黄经 {_format_degree(item['longitude'])}，"
        f"{item['palace_branch']}宫（宫主{item['palace_lord']}），"
        f"研究宿位{item['mansion']['su28']} {_format_degree(item['mansion']['degree_in_mansion'])}，"
        f"度主{item['mansion']['degree_lord']}"
        for item in guolao.get("bodies", [])
    ]
    if input_clock := guolao.get("profile", {}).get("input_clock"):
        setup_lines[3] = (
            "输入钟制："
            + (
                "地方平太阳时"
                if input_clock["input_clock_basis"] == "local_mean_solar"
                else "地方真太阳时"
            )
            + "；不视为民用时区"
        )
        setup_lines.append(interpretation["input_clock"])
    if interpretation.get("reference_geometry"):
        setup_lines.append(interpretation["reference_geometry"])

    shensha_lines = [
        f"星期主星：{PLANET_LABELS_ZH.get(guolao.get('weekday_ruler', ''), guolao.get('weekday_ruler', '未知'))}",
        f"月宿：{guolao.get('moon_mansion', '未知')}",
        f"底本贵人及岁驾宫支：{guolao.get('god_positions', {}).get('branches', {})}",
        "天贵对应天乙昼贵，玉贵对应玉堂夜贵；年干支暂按立春换年。",
    ]
    timing = guolao.get("timing", {})
    timing_sections = []
    if timing.get("status") == "research_partial":
        timing_sections.append(
            (
                "目标时刻小限与十一曜研究位置",
                "\n".join(
                    [
                        interpretation.get("timing", ""),
                        *(
                            [interpretation["month_limit"]]
                            if "month_limit" in interpretation
                            else []
                        ),
                        f"换年钟面：{timing['calendar_datetime']}（{timing['calendar_timezone']}）；天文计算保留同一目标瞬间。",
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

    return [
        ("起盘信息", "\n".join(setup_lines).strip()),
        (
            "安命与十二功能宫",
            "\n".join(
                [
                    interpretation.get("signature", "未返回安命解释"),
                    interpretation.get("core_identity", ""),
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
        ("计算对应解读", "\n".join(interpretation.values())),
        (
            "规则与验收",
            "\n".join(
                [
                    "研究口径：" + guolao.get("lunar_mansion_system", "未知"),
                    *[
                        r["title"] + "：" + r["source_url"]
                        for r in guolao.get("rulesets", [])
                    ],
                    *guolao.get("validation", {}).get("limitations", []),
                ]
            ),
        ),
    ]


def _build_chart_snapshot(
    payload: Dict[str, Any], chart_variant: str
) -> Dict[str, Any]:
    technique = CORE_CHART_EXPORT_TECHNIQUES.get(chart_variant, "astrochart")
    sections = (
        _build_guolao_snapshot_sections(payload)
        if chart_variant == "guolao_chart"
        else _build_standard_chart_snapshot_sections(
            payload, chart_variant=chart_variant
        )
    )
    snapshot_text = _render_snapshot_text(sections)
    snapshot_export = parse_export_content(
        technique=technique,
        content=snapshot_text,
    )
    return {
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }


def _build_birth_info(payload: Dict[str, Any]) -> AstroBirthInfo:
    return build_astro_birth_info(
        birth_year=payload["birth_year"],
        birth_month=payload["birth_month"],
        birth_day=payload["birth_day"],
        birth_hour=payload["birth_hour"],
        birth_minute=payload.get("birth_minute", 0),
        birth_second=payload.get("birth_second", 0),
        birth_microsecond=payload.get("birth_microsecond", 0),
        birth_clock_basis=payload.get("birth_clock_basis", "civil"),
        birth_timezone=payload.get("birth_timezone"),
        birth_longitude=payload.get("birth_longitude"),
        birth_latitude=payload.get("birth_latitude"),
        name=payload.get("name"),
        birth_place=payload.get("birth_place"),
        use_true_solar_time=payload.get("use_true_solar_time", False),
        preserve_instant=payload.get("preserve_instant", False),
        require_resolved_timezone=payload.get("require_resolved_timezone", True),
        solar_clock_ephemeris_policy=payload.get(
            "solar_clock_ephemeris_policy", "auto"
        ),
        allow_native_solar_epoch=payload.get("allow_native_solar_epoch", False),
    )


@calculation_guard("核心星盘分析")
@coherent_india_call
@coherent_guolao_solar_call
def calculate_core_chart_analysis(
    *,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int,
    birth_longitude: Optional[float],
    birth_latitude: Optional[float],
    chart_variant: str = "chart",
    birth_minute: int = 0,
    birth_second: int = 0,
    birth_microsecond: int = 0,
    birth_clock_basis: str = "civil",
    birth_timezone: Optional[str] = None,
    name: Optional[str] = None,
    birth_place: Optional[str] = None,
    gender: Optional[str] = None,  # accepted for uniform args; unused in chart math
    hsys: Optional[int] = None,
    zodiacal: Optional[int] = None,
    use_true_solar_time: bool = False,
    node_mode: str = "mean",
    ephemeris_policy: str = "auto",
    saptavargaja_profile: str = "santhanam_27",
    drekkana_profile: str = "santhanam_27_6",
    cheshta_model: str = "unadjudicated",
    divisions: Optional[List[int]] = None,
    birth_time_uncertainty_minutes: Optional[float] = None,
    analysis_datetime: Optional[datetime] = None,
    guolao_month_basis: Optional[str] = None,
    guolao_seasonal_anchor_policy: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build an offline core astrology chart family payload.

    Core charts prefer a local Swiss Ephemeris runtime when available and fall
    back to the bundled approximate orbital model when it is not.
    """
    if guolao_seasonal_anchor_policy is not None:
        from fatebridge.core.guolao_anchor_days import POLICIES

        if chart_variant != "guolao_chart":
            raise ValueError(
                "guolao_seasonal_anchor_policy requires chart_variant=guolao_chart"
            )
        if guolao_seasonal_anchor_policy not in POLICIES:
            raise ValueError("Unknown guolao_seasonal_anchor_policy")
        if guolao_seasonal_anchor_policy in POLICIES[1:] and not (
            use_true_solar_time or birth_clock_basis == "local_apparent_solar"
        ):
            raise ValueError(
                "Solar-day anchors require an apparent clock: use_true_solar_time=true or explicit LAT input"
            )
    if guolao_month_basis is not None and (
        chart_variant != "guolao_chart" or analysis_datetime is None
    ):
        raise ValueError(
            "guolao_month_basis requires chart_variant=guolao_chart and analysis_datetime"
        )
    if guolao_month_basis is not None and guolao_month_basis not in {
        "jie_month",
        "chinese_lunar_utc8",
    }:
        raise ValueError("guolao_month_basis must be jie_month or chinese_lunar_utc8")
    if chart_variant != "india_chart" and drekkana_profile != "santhanam_27_6":
        raise ValueError("drekkana_profile requires chart_variant=india_chart")
    if birth_clock_basis != "civil" and chart_variant not in {
        "germany",
        "chart13",
        "india_chart",
        "guolao_chart",
    }:
        raise ValueError(
            "Noncivil birth_clock_basis requires chart_variant=germany, chart13, india_chart or guolao_chart"
        )
    if birth_second and chart_variant not in {
        "germany",
        "chart13",
        "india_chart",
        "guolao_chart",
    }:
        raise ValueError(
            "nonzero birth_second requires chart_variant=germany, chart13, india_chart or guolao_chart"
        )
    if birth_microsecond and chart_variant not in {"india_chart", "guolao_chart"}:
        raise ValueError(
            "nonzero birth_microsecond requires chart_variant=india_chart or guolao_chart"
        )
    if chart_variant == "germany":
        return calculate_germany_chart_analysis(
            birth_year=birth_year,
            birth_month=birth_month,
            birth_day=birth_day,
            birth_hour=birth_hour,
            birth_minute=birth_minute,
            birth_second=birth_second,
            birth_clock_basis=birth_clock_basis,
            birth_longitude=birth_longitude,
            birth_latitude=birth_latitude,
            birth_timezone=birth_timezone,
            name=name,
            birth_place=birth_place,
            gender=gender,
            hsys=hsys,
            zodiacal=zodiacal,
            use_true_solar_time=use_true_solar_time,
            birth_time_uncertainty_minutes=birth_time_uncertainty_minutes,
            analysis_datetime=analysis_datetime,
        )

    if analysis_datetime is not None and chart_variant != "guolao_chart":
        raise ValueError(
            "analysis_datetime requires chart_variant=germany or guolao_chart"
        )
    if chart_variant not in SUPPORTED_CHART_VARIANTS:
        raise ValueError(
            f"不支持的 chart_variant: {chart_variant}。"
            f"可选值：{', '.join(sorted(SUPPORTED_CHART_VARIANTS))}"
        )

    birth_info = _build_birth_info(
        {
            "birth_year": birth_year,
            "birth_month": birth_month,
            "birth_day": birth_day,
            "birth_hour": birth_hour,
            "birth_minute": birth_minute,
            "birth_second": birth_second,
            "birth_clock_basis": birth_clock_basis,
            "birth_timezone": birth_timezone,
            "birth_longitude": birth_longitude,
            "birth_latitude": birth_latitude,
            "name": name,
            "birth_place": birth_place,
            "use_true_solar_time": (
                False
                if chart_variant == "guolao_chart"
                or (chart_variant == "india_chart" and birth_clock_basis == "civil")
                else use_true_solar_time
            ),
            "preserve_instant": chart_variant in {"guolao_chart", "india_chart"},
            "require_resolved_timezone": True,
            "allow_native_solar_epoch": chart_variant == "guolao_chart",
            "birth_microsecond": birth_microsecond,
            "solar_clock_ephemeris_policy": (
                ephemeris_policy if chart_variant == "india_chart" else "auto"
            ),
        }
    )
    if chart_variant == "guolao_chart":
        # Guolao derives its solar clock from its actual Sun/UT1 later. The
        # legacy constructor's independent display is unused and can fail
        # before that valid calculation. Keep only the requested clock policy.
        birth_info = replace(birth_info, applied_true_solar=use_true_solar_time)
    if chart_variant == "india_chart":
        from fatebridge.core.jyotish_display import normalize_solar_display

        birth_info, _ = normalize_solar_display(
            birth_info, ephemeris_policy, requested=use_true_solar_time
        )
    anchor_options: Dict[str, Any] = (
        {"guolao_seasonal_anchor_policy": guolao_seasonal_anchor_policy}
        if guolao_seasonal_anchor_policy is not None
        else {}
    )
    result = build_core_chart_payload(
        birth_info,
        chart_variant,
        hsys=hsys,
        zodiacal=zodiacal,
        **anchor_options,
    )
    if chart_variant == "guolao_chart":
        from fatebridge.core.guolao_timing import enrich_guolao_timing

        enrich_guolao_timing(
            result,
            birth_info,
            analysis_datetime,
            zodiacal=zodiacal,
            month_basis=guolao_month_basis,
        )
    result.update(_augment_core_chart_reading(result, chart_variant))
    if chart_variant == "india_chart":
        from fatebridge.core.jyotish import validate_clock
        from fatebridge.services.jyotish import enrich_india_chart

        validate_clock(birth_info.local_datetime, "解析后的出生时刻")
        enrich_india_chart(
            result,
            birth_info,
            node_mode=node_mode,
            ephemeris_policy=ephemeris_policy,
            saptavargaja_profile=saptavargaja_profile,
            drekkana_profile=drekkana_profile,
            cheshta_model=cheshta_model,
            divisions=divisions,
            birth_time_uncertainty_minutes=birth_time_uncertainty_minutes,
        )
    if chart_variant == "chart13":
        from fatebridge.core.astro.sensitivity import enrich_specialty_sensitivity

        enrich_specialty_sensitivity(
            result,
            birth_info,
            kind="chart13",
            uncertainty_minutes=birth_time_uncertainty_minutes,
        )
    result.update(_build_chart_snapshot(result, chart_variant))
    return result


@calculation_guard("量化盘分析")
def calculate_germany_chart_analysis(
    *,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int,
    birth_longitude: Optional[float],
    birth_latitude: Optional[float],
    birth_minute: int = 0,
    birth_second: int = 0,
    birth_clock_basis: str = "civil",
    birth_timezone: Optional[str] = None,
    name: Optional[str] = None,
    birth_place: Optional[str] = None,
    gender: Optional[str] = None,  # accepted for uniform args; unused in chart math
    hsys: Optional[int] = None,
    zodiacal: Optional[int] = None,
    use_true_solar_time: bool = False,
    birth_time_uncertainty_minutes: Optional[float] = None,
    analysis_datetime: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Build the FateBridge midpoint/germany chart payload.
    """
    birth_info = _build_birth_info(
        {
            "birth_year": birth_year,
            "birth_month": birth_month,
            "birth_day": birth_day,
            "birth_hour": birth_hour,
            "birth_minute": birth_minute,
            "birth_second": birth_second,
            "birth_clock_basis": birth_clock_basis,
            "birth_timezone": birth_timezone,
            "birth_longitude": birth_longitude,
            "birth_latitude": birth_latitude,
            "name": name,
            "birth_place": birth_place,
            "use_true_solar_time": use_true_solar_time,
        }
    )
    result = build_midpoint_payload(
        birth_info,
        hsys=hsys,
        zodiacal=zodiacal,
    )
    from fatebridge.core.astro.sensitivity import enrich_specialty_sensitivity

    enrich_specialty_sensitivity(
        result,
        birth_info,
        kind="germany",
        uncertainty_minutes=birth_time_uncertainty_minutes,
    )
    from fatebridge.core.astro.solar_arc import enrich_solar_arc

    enrich_solar_arc(result, birth_info, analysis_datetime)
    return result


@calculation_guard("关系星盘分析")
def calculate_relative_chart_analysis(
    *,
    inner_payload: Dict[str, Any],
    outer_payload: Dict[str, Any],
    relative_mode: Any = None,
    hsys: int = 3,
    zodiacal: int = 0,
    relationship_focus: Any = None,
    davison_variant: str = "uncorrected",
) -> Dict[str, Any]:
    """
    Build synastry/composite payloads for two parties.

    ``hsys`` defaults to Placidus (3), matching both published request forms.
    """
    inner_birth = _build_birth_info(inner_payload)
    outer_birth = _build_birth_info(outer_payload)
    payload = build_relative_payload(
        inner_birth=inner_birth,
        outer_birth=outer_birth,
        relative_mode=relative_mode,
        hsys=hsys,
        zodiacal=zodiacal,
        relationship_focus=relationship_focus,
        davison_variant=davison_variant,
    )
    if isinstance(payload, dict) and "error" not in payload:
        # Allowlist the relationship-facing summary; the raw inner/outer/
        # composite charts and the directional aspect/midpoint dumps stay in
        # the structured payload only (they would flood the snapshot).
        summary_view: Dict[str, Any] = {
            key: payload[key]
            for key in (
                "relationship_profile",
                "synastry_aspects",
                "compatibility",
                "compatibility_evidence",
                "summary",
            )
            if key in payload
        }
        snapshot_text = render_structured_snapshot_text(
            summary_view, title="关系星盘分析"
        )
        payload["snapshot_text"] = snapshot_text
        payload["snapshot_export"] = parse_export_content(
            technique="relative", content=snapshot_text
        )
    return payload
