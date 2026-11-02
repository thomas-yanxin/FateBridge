"""
I Ching and Mei Hua Yi Shu helper utilities.

This module adds lightweight divination support around trigram/hexagram
composition so FateBridge can expose contextual gua information without
depending on an external runtime.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from fatebridge.core.hexagram_relations import (
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    relationship_by_role,
)

from ..utils.data import EARTHLY_BRANCHES
from .gua_meanings import (
    HEXAGRAM_INTERPRETATIONS,
    caution_phrase,
    get_hexagram_meaning,
    get_trigram_meaning,
)
from .zhouyi import classical_hexagram

BAGUA_BY_NAME: Dict[str, Dict[str, Any]] = {
    "乾": {
        "name": "乾",
        "nature": "天",
        "element": "金",
        "lines": [1, 1, 1],
        "symbol": "☰",
        "keywords": "刚健、开创、天道",
    },
    "兑": {
        "name": "兑",
        "nature": "泽",
        "element": "金",
        "lines": [1, 1, 0],
        "symbol": "☱",
        "keywords": "喜悦、交流、润泽",
    },
    "离": {
        "name": "离",
        "nature": "火",
        "element": "火",
        "lines": [1, 0, 1],
        "symbol": "☲",
        "keywords": "光明、表达、洞察",
    },
    "震": {
        "name": "震",
        "nature": "雷",
        "element": "木",
        "lines": [1, 0, 0],
        "symbol": "☳",
        "keywords": "发动、突破、惊醒",
    },
    "巽": {
        "name": "巽",
        "nature": "风",
        "element": "木",
        "lines": [0, 1, 1],
        "symbol": "☴",
        "keywords": "渗透、谋划、柔入",
    },
    "坎": {
        "name": "坎",
        "nature": "水",
        "element": "水",
        "lines": [0, 1, 0],
        "symbol": "☵",
        "keywords": "流动、隐忧、险中求通",
    },
    "艮": {
        "name": "艮",
        "nature": "山",
        "element": "土",
        "lines": [0, 0, 1],
        "symbol": "☶",
        "keywords": "止守、边界、收束",
    },
    "坤": {
        "name": "坤",
        "nature": "地",
        "element": "土",
        "lines": [0, 0, 0],
        "symbol": "☷",
        "keywords": "承载、包容、顺势",
    },
}

BAGUA_BY_NUMBER = {
    1: "乾",
    2: "兑",
    3: "离",
    4: "震",
    5: "巽",
    6: "坎",
    7: "艮",
    8: "坤",
}

HEXAGRAM_NAMES: Dict[Tuple[str, str], str] = {
    ("乾", "乾"): "乾为天",
    ("乾", "兑"): "天泽履",
    ("乾", "离"): "天火同人",
    ("乾", "震"): "天雷无妄",
    ("乾", "巽"): "天风姤",
    ("乾", "坎"): "天水讼",
    ("乾", "艮"): "天山遁",
    ("乾", "坤"): "天地否",
    ("兑", "乾"): "泽天夬",
    ("兑", "兑"): "兑为泽",
    ("兑", "离"): "泽火革",
    ("兑", "震"): "泽雷随",
    ("兑", "巽"): "泽风大过",
    ("兑", "坎"): "泽水困",
    ("兑", "艮"): "泽山咸",
    ("兑", "坤"): "泽地萃",
    ("离", "乾"): "火天大有",
    ("离", "兑"): "火泽睽",
    ("离", "离"): "离为火",
    ("离", "震"): "火雷噬嗑",
    ("离", "巽"): "火风鼎",
    ("离", "坎"): "火水未济",
    ("离", "艮"): "火山旅",
    ("离", "坤"): "火地晋",
    ("震", "乾"): "雷天大壮",
    ("震", "兑"): "雷泽归妹",
    ("震", "离"): "雷火丰",
    ("震", "震"): "震为雷",
    ("震", "巽"): "雷风恒",
    ("震", "坎"): "雷水解",
    ("震", "艮"): "雷山小过",
    ("震", "坤"): "雷地豫",
    ("巽", "乾"): "风天小畜",
    ("巽", "兑"): "风泽中孚",
    ("巽", "离"): "风火家人",
    ("巽", "震"): "风雷益",
    ("巽", "巽"): "巽为风",
    ("巽", "坎"): "风水涣",
    ("巽", "艮"): "风山渐",
    ("巽", "坤"): "风地观",
    ("坎", "乾"): "水天需",
    ("坎", "兑"): "水泽节",
    ("坎", "离"): "水火既济",
    ("坎", "震"): "水雷屯",
    ("坎", "巽"): "水风井",
    ("坎", "坎"): "坎为水",
    ("坎", "艮"): "水山蹇",
    ("坎", "坤"): "水地比",
    ("艮", "乾"): "山天大畜",
    ("艮", "兑"): "山泽损",
    ("艮", "离"): "山火贲",
    ("艮", "震"): "山雷颐",
    ("艮", "巽"): "山风蛊",
    ("艮", "坎"): "山水蒙",
    ("艮", "艮"): "艮为山",
    ("艮", "坤"): "山地剥",
    ("坤", "乾"): "地天泰",
    ("坤", "兑"): "地泽临",
    ("坤", "离"): "地火明夷",
    ("坤", "震"): "地雷复",
    ("坤", "巽"): "地风升",
    ("坤", "坎"): "地水师",
    ("坤", "艮"): "地山谦",
    ("坤", "坤"): "坤为地",
}


QUESTION_DOMAIN_RULES: Dict[str, Dict[str, Any]] = {
    "career": {
        "label": "事业/项目",
        "focus": "资源调度、节奏推进与结果落地",
        "keywords": (
            "事业",
            "工作",
            "项目",
            "推进",
            "合作",
            "职位",
            "升职",
            "创业",
            "客户",
            "career",
            "project",
            "work",
        ),
    },
    "relationship": {
        "label": "感情/关系",
        "focus": "双方态度、沟通温度与后续走向",
        "keywords": (
            "感情",
            "关系",
            "婚姻",
            "恋爱",
            "相处",
            "复合",
            "桃花",
            "relationship",
            "love",
        ),
    },
    "wealth": {
        "label": "财务/经营",
        "focus": "现金流、投入回报与风险边界",
        "keywords": (
            "财",
            "收入",
            "投资",
            "收益",
            "订单",
            "生意",
            "经营",
            "wealth",
            "money",
            "business",
        ),
    },
    "study": {
        "label": "学业/考试",
        "focus": "准备质量、临场状态与结果兑现",
        "keywords": (
            "学业",
            "考试",
            "申请",
            "论文",
            "面试",
            "留学",
            "study",
            "exam",
        ),
    },
    "health": {
        "label": "健康/恢复",
        "focus": "身体负担、恢复节奏与风险防控",
        "keywords": (
            "健康",
            "身体",
            "病",
            "恢复",
            "睡眠",
            "手术",
            "health",
        ),
    },
    "travel": {
        "label": "出行/迁动",
        "focus": "路径变化、外部阻力与安全边界",
        "keywords": (
            "出行",
            "旅行",
            "出差",
            "搬家",
            "迁移",
            "通勤",
            "travel",
            "move",
        ),
    },
}

BODY_USE_INTERPRETATIONS = {
    "体用比和": "传统取同气协调之意；现实中的配合与阻力仍须核实。",
    "体生用": "传统取主体有所耗泄之意，需审视投入；此关系本身不保证后续回报。",
    "体克用": "传统取主体制用之意；能否主动掌控须结合现实权限与资源判断。",
    "用生体": "传统取生助之意；可核实是否确有可用的外部支持，不据此确认资源已经到位。",
    "用克体": "传统取受制之意；可检查实际约束，不据此认定现实环境正在压制主体。",
    "体用关系未明": "此处未形成明确的体用关系，不能替代现实资料判断主客条件。",
}

MOVING_LINE_PHASES = {
    1: {
        "stage": "起念与启动",
        "meaning": "以初爻发端的比喻检查动机与第一步，实际阶段另据事实确认",
    },
    2: {
        "stage": "内部联系与配合",
        "meaning": "以二爻承接的比喻检查协同与资源，实际配合状况另据事实确认",
    },
    3: {
        "stage": "进退临界",
        "meaning": "以三爻转折的比喻检查进退选择，不据爻位认定现实已经遇到卡口",
    },
    4: {
        "stage": "外部执行",
        "meaning": "以四爻对外的比喻检查执行接口，不据爻位认定事情已经对外展开",
    },
    5: {
        "stage": "核心结果位",
        "meaning": "以五爻主位的比喻检查决策与关键资源，不据爻位认定现实已到结果阶段",
    },
    6: {
        "stage": "收尾与反思",
        "meaning": "以上爻收束的比喻检查边界与复盘，不据爻位认定事情接近结束",
    },
}

MOVING_LINE_ORACLE_DETAILS = {
    1: {
        "position": "初爻",
        "title": "发端位",
        "focus": "起势、试探与基础",
        "judgement": "可借发端的比喻检查如何把第一步踩稳；事情是否刚开始须核实现状。",
        "favorable": "试探、起步、先立基线",
        "caution": "起手过满、仓促定局",
        "timing": "先小后大",
    },
    2: {
        "position": "二爻",
        "title": "承接位",
        "focus": "内部协同、承接与近身关系",
        "judgement": "可借承接的比喻核对内部配合；爻位本身不确认现实关系顺逆或进度。",
        "favorable": "对齐、承接、稳住关键配合",
        "caution": "各做各的、近身失配",
        "timing": "先内后外",
    },
    3: {
        "position": "三爻",
        "title": "转折位",
        "focus": "门槛压力、进退选择与节奏校正",
        "judgement": "可借转折的比喻检查进退选项；是否确有门槛与两难须核实现状。",
        "favorable": "减速、复盘、换挡",
        "caution": "硬顶、赌气、边乱边冲",
        "timing": "先稳后进",
    },
    4: {
        "position": "四爻",
        "title": "外应位",
        "focus": "对外执行、接口与外部反馈",
        "judgement": "可借对外的比喻检查执行与反馈；是否已经进入执行阶段须核实现状。",
        "favorable": "执行、落地、处理外部接口",
        "caution": "纸上推进、对外失控",
        "timing": "由内转外",
    },
    5: {
        "position": "五爻",
        "title": "主位",
        "focus": "核心结果、主轴资源与拍板权",
        "judgement": "可借主位的比喻核对决策权与关键资源；爻位不证明结果将至或关键窗口已经出现。",
        "favorable": "聚焦主轴、拍板、拿结果",
        "caution": "贪多分心、权重失衡",
        "timing": "关键窗口",
    },
    6: {
        "position": "上爻",
        "title": "收束位",
        "focus": "收尾、过满与结构回看",
        "judgement": "可借收束的比喻检查是否需要定界或复盘；爻位不证明事情已经接近尾声。",
        "favorable": "收尾、止盈、回看结构",
        "caution": "临门再加码、强撑过头",
        "timing": "宜收不宜放",
    },
}

DOMAIN_LINE_ADJUSTMENTS = {
    "career": "在事业/项目上，更适合把角色、边界、里程碑先钉牢。",
    "relationship": "在感情/关系上，更应先看回应与温度，再决定推进深浅。",
    "wealth": "在财务/经营上，更要先控投入节奏，再看回收与扩张。",
    "study": "在学业/考试上，先稳准备质量，再谈临场发挥。",
    "health": "在健康/恢复上，以节律、恢复度和风险管理为先。",
    "travel": "在出行/迁动上，优先确认路径、安全与变动边界。",
    "general": "先把当前所在步骤看清，再决定发力还是收束。",
}

BODY_USE_LINE_ADJUSTMENTS = {
    "体用比和": "可据同气的传统象义检查现实配合条件，再决定推进方式。",
    "体生用": "可据耗泄的传统象义检查实际投入与承受能力。",
    "体克用": "可据制用的传统象义核实权限与资源；若要主动拿节奏，先确认实际条件允许。",
    "用生体": "可据生助的传统象义核实外援是否存在、可用及可持续。",
    "用克体": "可据受制的传统象义核实约束来源，再决定是否需要调整。",
    "体用关系未明": "体用关系未明时保留判断，另核实现实资料。",
}


def _enrich_trigram(trigram: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(trigram)
    enriched.update(get_trigram_meaning(trigram["name"]))
    return enriched


def _enrich_hexagram(hexagram: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(hexagram)
    detail = get_hexagram_meaning(enriched["name"])
    enriched.update(detail)
    if "summary" not in enriched:
        enriched["summary"] = (
            f"{enriched['name']}：{detail.get('theme', '卦义待补充')}。"
            f"{detail.get('judgement', detail.get('guidance', ''))}"
        ).strip()
    return enriched


def _build_oracle_payload(hexagram: Dict[str, Any]) -> Dict[str, str]:
    classical = hexagram.get("classical") or classical_hexagram(hexagram["binary_code"])
    return {
        "name": hexagram["name"],
        "source_kind": "modern_editorial_summary",
        "classical_guaci": classical["guaci"],
        "classical_source_url": classical["source_url"],
        "theme": str(hexagram.get("theme", "")),
        "judgement": str(hexagram.get("judgement", "")),
        "image": str(hexagram.get("image", "")),
        "favorable": str(hexagram.get("favorable", "")),
        "caution": str(hexagram.get("caution", "")),
    }


def build_moving_line_oracle(
    hexagram: Dict[str, Any],
    moving_line: int,
    domain: Dict[str, str],
) -> Dict[str, Any]:
    detail = MOVING_LINE_ORACLE_DETAILS[moving_line]
    changed_hexagram = build_changed_hexagram(hexagram, moving_line)
    line_body_use = resolve_body_use(hexagram, moving_line)
    body_use_relation = line_body_use["body_use_relation"]
    domain_hint = DOMAIN_LINE_ADJUSTMENTS.get(
        domain["key"],
        DOMAIN_LINE_ADJUSTMENTS["general"],
    )
    body_use_hint = BODY_USE_LINE_ADJUSTMENTS.get(
        body_use_relation,
        BODY_USE_LINE_ADJUSTMENTS["体用关系未明"],
    )
    judgement = (
        f"现代爻位联想：在{hexagram['name']}中，将{detail['position']}比作{detail['title']}，"
        f"可检查{detail['focus']}。{detail['judgement']}"
    )
    transition = (
        f"此爻改变后，计算所得变卦为{changed_hexagram['name']}；"
        f"其现代卦义参照为{changed_hexagram['theme']}：{changed_hexagram['judgement']}"
        "这项卦图变化不证明现实走势将如此发展。"
    )
    favorable = (
        f"{detail['favorable']}；并顺着本卦所宜{hexagram.get('favorable', '顺势推进')}"
    )
    caution = f"{detail['caution']}；并防本卦所忌{caution_phrase(hexagram.get('caution', '失衡冒进'))}"
    summary = (
        f"动{moving_line}爻居{detail['position']}，{judgement}{transition}"
        f"宜{favorable}，忌{caution}。"
        f"{domain_hint}{body_use_hint}"
    )
    classical = hexagram.get("classical") or classical_hexagram(hexagram["binary_code"])
    verse = classical["yaoci"][moving_line - 1]
    from .meihua_text_reference import render_yaoci_text

    rendering = render_yaoci_text(verse["text"])
    display = rendering["display_text"]
    verse_text = display if display is not None else "〔转录标记未解析，原文另存〕"
    classical_judgement = f"《周易》{hexagram['name']}{verse['label']}：{verse_text}"
    return {
        "line": moving_line,
        "position": detail["position"],
        "title": detail["title"],
        "focus": detail["focus"],
        "judgement": classical_judgement,
        "position_hint": judgement,
        "favorable": favorable,
        "caution": caution,
        "timing": detail["timing"],
        "timing_scope": "modern_action_order_hint_not_event_time",
        "transition_scope": "computed_hexagram_change_not_real_outcome_forecast",
        "moving_palace": line_body_use["moving_palace"],
        "body_use_relation": body_use_relation,
        "body_trigram": line_body_use["body_trigram"]["name"],
        "use_trigram": line_body_use["use_trigram"]["name"],
        "changed_hexagram": _build_oracle_payload(changed_hexagram),
        "domain_hint": domain_hint,
        "body_use_adjustment": body_use_hint,
        "transition": transition,
        "summary": classical_judgement + "以下为现代爻位提示：" + summary,
        "source_kind": "classical_yaoci_with_separate_modern_position_hint",
        "classical_yaoci": verse,
        "classical_yaoci_rendering": rendering,
        "classical_source_url": classical["source_url"],
    }


def build_line_oracles(
    hexagram: Dict[str, Any],
    active_line: int,
    domain: Dict[str, str],
) -> List[Dict[str, Any]]:
    line_oracles: List[Dict[str, Any]] = []
    for line_number in range(1, 7):
        oracle = build_moving_line_oracle(
            hexagram=hexagram,
            moving_line=line_number,
            domain=domain,
        )
        oracle["is_active"] = line_number == active_line
        oracle["scenario"] = (
            "actual_moving_line"
            if line_number == active_line
            else "hypothetical_single_line"
        )
        line_oracles.append(oracle)
    return line_oracles


def _bagua_from_lines(lines: List[int]) -> Dict[str, Any]:
    target = ",".join(str(bit) for bit in lines)
    for item in BAGUA_BY_NAME.values():
        if ",".join(str(bit) for bit in item["lines"]) == target:
            return _enrich_trigram(item)
    return _enrich_trigram(BAGUA_BY_NAME["乾"])


def _bagua_from_number(number: int) -> Dict[str, Any]:
    normalized = ((number - 1) % 8) + 1
    return _enrich_trigram(BAGUA_BY_NAME[BAGUA_BY_NUMBER[normalized]])


def build_hexagram(upper_name: str, lower_name: str) -> Dict[str, Any]:
    upper = _enrich_trigram(BAGUA_BY_NAME[upper_name])
    lower = _enrich_trigram(BAGUA_BY_NAME[lower_name])
    lines = [*lower["lines"], *upper["lines"]]
    return _enrich_hexagram(
        {
            "name": HEXAGRAM_NAMES.get(
                (upper_name, lower_name), f"{upper['nature']}{lower['nature']}"
            ),
            "upper": upper,
            "lower": lower,
            "lines": lines,
            "binary_code": "".join(str(bit) for bit in lines),
            "symbol": f"{upper['symbol']}{lower['symbol']}",
        }
    )


def build_mutual_hexagram(hexagram: Dict[str, Any]) -> Dict[str, Any]:
    lines = hexagram["lines"]
    mutual_lines = [lines[1], lines[2], lines[3], lines[2], lines[3], lines[4]]
    lower = _bagua_from_lines(mutual_lines[:3])
    upper = _bagua_from_lines(mutual_lines[3:])
    return build_hexagram(upper["name"], lower["name"])


def build_opposite_hexagram(hexagram: Dict[str, Any]) -> Dict[str, Any]:
    """错卦（旁通卦）: 每爻阴阳相反。"""
    opposite_lines = [0 if bit == 1 else 1 for bit in hexagram["lines"]]
    lower = _bagua_from_lines(opposite_lines[:3])
    upper = _bagua_from_lines(opposite_lines[3:])
    return build_hexagram(upper["name"], lower["name"])


def build_inverted_hexagram(hexagram: Dict[str, Any]) -> Dict[str, Any]:
    """综卦（倒颠卦）: 将原卦初爻与上爻、二爻与五爻、三爻与四爻对换 —
    即整卦 180° 倒读。当卦为"错自身"时（如乾/坤/颐/大过/中孚/小过/坎/离），
    返回的综卦即原卦。"""
    inverted_lines = list(reversed(hexagram["lines"]))
    lower = _bagua_from_lines(inverted_lines[:3])
    upper = _bagua_from_lines(inverted_lines[3:])
    return build_hexagram(upper["name"], lower["name"])


def build_changed_hexagram(
    hexagram: Dict[str, Any], moving_line: int
) -> Dict[str, Any]:
    normalized_line = 6 if moving_line % 6 == 0 else moving_line % 6
    changed_lines = list(hexagram["lines"])
    changed_lines[normalized_line - 1] = (
        0 if changed_lines[normalized_line - 1] == 1 else 1
    )
    lower = _bagua_from_lines(changed_lines[:3])
    upper = _bagua_from_lines(changed_lines[3:])
    changed = build_hexagram(upper["name"], lower["name"])
    changed["moving_line"] = normalized_line
    return changed


def relationship_by_element(left_element: str, right_element: str) -> str:
    if left_element == right_element:
        return "同气相应"
    if ELEMENT_GENERATES[left_element] == right_element:
        return "上生下"
    if ELEMENT_CONTROLS[left_element] == right_element:
        return "上制下"
    if ELEMENT_GENERATES[right_element] == left_element:
        return "下生上"
    if ELEMENT_CONTROLS[right_element] == left_element:
        return "下制上"
    return "关系未明"


def detect_question_domain(question: str) -> Dict[str, str]:
    query = (question or "").strip()
    if not query:
        return {
            "key": "general",
            "label": "综合问事",
            "focus": "整体趋势、主客力量与后续走向",
        }

    lowered = query.casefold()
    for key, info in QUESTION_DOMAIN_RULES.items():
        if any(keyword in query or keyword in lowered for keyword in info["keywords"]):
            return {
                "key": key,
                "label": info["label"],
                "focus": info["focus"],
            }

    return {
        "key": "general",
        "label": "综合问事",
        "focus": "整体趋势、主客力量与后续走向",
    }


def resolve_body_use(hexagram: Dict[str, Any], moving_line: int) -> Dict[str, Any]:
    normalized_line = 6 if moving_line % 6 == 0 else moving_line % 6
    moving_palace = "下卦" if normalized_line <= 3 else "上卦"
    if moving_palace == "下卦":
        body = hexagram["upper"]
        use = hexagram["lower"]
    else:
        body = hexagram["lower"]
        use = hexagram["upper"]

    relation = relationship_by_role(body["element"], use["element"])
    return {
        "moving_palace": moving_palace,
        "body_trigram": body,
        "use_trigram": use,
        "body_use_relation": relation,
        "body_use_summary": (
            f"动爻落{moving_palace}，体卦{body['name']}、用卦{use['name']}，"
            f"五行关系为{relation}。"
        ),
    }


def build_meihua_interpretation(
    meihua: Dict[str, Any],
    question: str = "",
    *,
    interpretation_topic: str = "general",
    weather_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    from .requests.meihua import MeihuaInterpretationOptions

    options = MeihuaInterpretationOptions.model_validate(
        {
            "interpretation_topic": interpretation_topic,
            "weather_context": weather_context,
        }
    )
    if options.interpretation_topic == "weather":
        from .meihua_weather import build_weather_interpretation

        interpretation = build_weather_interpretation(meihua, weather_context)
        interpretation["topic_reading"] = None
        interpretation["topic_ruleset"] = None
        interpretation["internal_countercontrol"] = None
        interpretation["seasonal_qualification"] = None
        interpretation["wealth_components"] = None
        interpretation["classical_text_reference"] = None
        interpretation["action_hint"] = None
        interpretation["risk_hint"] = None
        return interpretation
    if options.interpretation_topic != "general":
        from .meihua_topics import build_topic_interpretation

        return build_topic_interpretation(meihua, options.interpretation_topic)
    base = meihua["base_hexagram"]
    changed = meihua["changed_hexagram"]
    mutual = meihua["mutual_hexagram"]
    cuo = meihua["cuo_hexagram"]
    moving_line = meihua["seed"]["moving_line"]
    domain = detect_question_domain(question)
    phase = MOVING_LINE_PHASES[moving_line]
    line_oracles = build_line_oracles(
        hexagram=base,
        active_line=moving_line,
        domain=domain,
    )
    moving_line_oracle = next(oracle for oracle in line_oracles if oracle["is_active"])
    body_use_relation = moving_line_oracle["body_use_relation"]
    body_use_detail = BODY_USE_INTERPRETATIONS.get(
        body_use_relation, BODY_USE_INTERPRETATIONS["体用关系未明"]
    )

    question_reading = (
        f"若问{domain['label']}，重点看{domain['focus']}。"
        if domain["key"] != "general"
        else f"此卦宜先看{domain['focus']}。"
    )
    base_reading = (
        f"本卦{base['name']}的现代卦义参照为{base['theme']}：{base['judgement']}"
        f"{base['guidance']}"
    )
    changed_reading = (
        f"变卦{changed['name']}的现代卦义参照为{changed['theme']}：{changed['judgement']}"
        f"{changed['guidance']}"
    )
    mutual_reading = (
        f"互卦{mutual['name']}的现代卦义参照为{mutual['theme']}："
        f"{mutual['judgement']}{mutual['guidance']}"
    )
    cuo_reading = (
        f"错卦{cuo['name']}的现代对照联想为{cuo['theme']}："
        f"{cuo['judgement']}{cuo['guidance']}"
    )
    body_use_reading = f"{meihua['body_use_summary']}{body_use_detail}"
    phase_reading = (
        f"现代爻位联想：动{moving_line}爻对应{phase['stage']}，{phase['meaning']}。"
        f"{moving_line_oracle['summary']}"
    )
    action_hint = (
        f"现代建议参考：可为之处在于{base.get('favorable', '顺势推进')}，"
        f"动爻位的联想可用于检查{moving_line_oracle['favorable']}，"
        f"变卦的现代建议{changed.get('favorable', '稳步成事')}也可作为检查角度；"
        "是否适用须结合现实条件判断。"
    )
    risk_hint = (
        f"现代建议参考：需防{caution_phrase(base.get('caution', '失衡冒进'))}，"
        f"动爻位的联想提醒检查{moving_line_oracle['caution']}，"
        f"并留意反面镜像里的{caution_phrase(cuo.get('caution', '内外失序'))}。"
    )

    outline = [
        question_reading,
        base_reading,
        changed_reading,
        body_use_reading,
        phase_reading,
        mutual_reading,
        cuo_reading,
    ]

    from .meihua import meihua_traditional_readings
    from .meihua_countercontrol import build_internal_countercontrol
    from .meihua_seasonal_reading import build_seasonal_qualification

    control_stages = meihua.get("stage_relations", [])
    internal_control = (
        build_internal_countercontrol(control_stages) if control_stages else None
    )
    seasonal_qualification = (
        build_seasonal_qualification(
            control_stages, meihua.get("seasonal_strength"), internal_control
        )
        if internal_control is not None
        else None
    )

    stage_readings, classical_reading = meihua_traditional_readings(
        control_stages,
        meihua.get("seasonal_strength"),
        internal_countercontrol=internal_control,
        seasonal_qualification=seasonal_qualification,
    )
    classical_reading = classical_reading or body_use_reading
    comprehensive = (
        f"{question_reading}本卦{base['name']}，动{moving_line}爻，变{changed['name']}。"
        f"经文参照：{moving_line_oracle['judgement']}。"
        f"传统体用解读：{classical_reading}"
        "初中终指传统分析层次，不能据此认定现实阶段、具体事件或发生日期。"
    )

    return {
        "interpretation_topic": "general",
        "weather": None,
        "topic_reading": None,
        "topic_ruleset": None,
        "wealth_components": None,
        "internal_countercontrol": internal_control,
        "seasonal_qualification": seasonal_qualification,
        "question_domain": domain,
        "moving_line_phase": {
            "line": moving_line,
            "stage": phase["stage"],
            "meaning": phase["meaning"],
            "source_kind": "modern_editorial_position_template",
            "timing_scope": "metaphor_not_event_date",
            "real_stage_inferred": False,
        },
        "line_oracles": line_oracles,
        "moving_line_oracle": moving_line_oracle,
        "base_reading": base_reading,
        "changed_reading": changed_reading,
        "mutual_reading": mutual_reading,
        "cuo_reading": cuo_reading,
        "body_use_reading": body_use_reading,
        "base_oracle": _build_oracle_payload(base),
        "changed_oracle": _build_oracle_payload(changed),
        "mutual_oracle": _build_oracle_payload(mutual),
        "cuo_oracle": _build_oracle_payload(cuo),
        "action_hint": action_hint,
        "risk_hint": risk_hint,
        "traditional_stage_readings": stage_readings,
        "traditional_judgement": classical_reading,
        "classical_text_reference": {
            "moving_yaoci": moving_line_oracle.get("classical_yaoci"),
            "moving_yaoci_rendering": moving_line_oracle["classical_yaoci_rendering"],
            "source_url": moving_line_oracle.get("classical_source_url"),
            "selection_policy": "actual_moving_line_reference_only",
            "scope": "按实际卦码和动爻引用《周易》经文；所选原法的经文参照不自动推导现实成败。",
        },
        "evidence_scope": {
            "traditional_rules": "meihua.ruleset",
            "modern_editorial": [
                "base_reading",
                "changed_reading",
                "mutual_reading",
                "cuo_reading",
                "moving_line_phase",
                "action_hint",
                "risk_hint",
            ],
            "line_oracles_scope": "classical_yaoci为对应爻经文，position_hint等为现代联想与现实检查建议；爻位不确认现实阶段，timing不是应期计算，变卦不确认现实走势，体用不核实现实资源或阻力。仅is_active=true为本次动爻，其余是假设该爻单独变化的参考。",
            "external_omens": "not_collected",
            "event_timing": "not_computed",
            "real_world_efficacy": "not_tested",
        },
        "judgement_outline": outline,
        "comprehensive_judgement": comprehensive,
    }


def lookup_hexagram_by_code(code: str) -> Dict[str, Any]:
    normalized = code
    if (
        not isinstance(normalized, str)
        or len(normalized) != 6
        or set(normalized) - {"0", "1"}
    ):
        raise ValueError("卦码必须是 6 位 0/1 字符串，例如 111111。")
    lower = _bagua_from_lines([int(bit) for bit in normalized[:3]])
    upper = _bagua_from_lines([int(bit) for bit in normalized[3:]])
    hexagram = build_hexagram(upper["name"], lower["name"])
    hexagram["meaning_source_kind"] = "modern_editorial_summary"
    hexagram["classical"] = classical_hexagram(normalized)
    hexagram["code"] = normalized
    hexagram["summary"] = (
        f"{hexagram['name']}：{hexagram.get('theme', '卦意聚焦待补充')}。"
        f"{hexagram.get('judgement', '')}"
        f"上卦{upper['name']}({upper['keywords']})，下卦{lower['name']}({lower['keywords']})。"
        f"{hexagram.get('guidance', '')}"
        f"宜{hexagram.get('favorable', '顺势推进')}，忌{caution_phrase(hexagram.get('caution', '失衡冒进'))}。"
    )
    return hexagram


def lookup_trigram_by_code(code: str) -> Dict[str, Any]:
    normalized = code
    if (
        not isinstance(normalized, str)
        or len(normalized) != 3
        or set(normalized) - {"0", "1"}
    ):
        raise ValueError("八卦码必须是 3 位 0/1 字符串，例如 111。")
    trigram = _bagua_from_lines([int(bit) for bit in normalized])
    trigram["code"] = normalized
    trigram["summary"] = (
        f"{trigram['name']}卦：{trigram.get('theme', trigram['keywords'])}。"
        f"{trigram.get('guidance', '')}"
        f"宜{trigram.get('favorable', '顺势而行')}，忌{caution_phrase(trigram.get('caution', '避免失衡'))}。"
    )
    return trigram


def lookup_hexagram_by_name(name: str) -> Dict[str, Any]:
    normalized = (name or "").strip().replace("卦", "")
    candidates = {item.replace("卦", ""): item for item in HEXAGRAM_INTERPRETATIONS}
    if normalized not in candidates:
        raise ValueError(f"未识别的六十四卦名称：{name}")
    target = candidates[normalized]
    for (upper_name, lower_name), hexagram_name in HEXAGRAM_NAMES.items():
        if hexagram_name == target:
            hexagram = build_hexagram(upper_name, lower_name)
            hexagram["meaning_source_kind"] = "modern_editorial_summary"
            hexagram["classical"] = classical_hexagram(hexagram["binary_code"])
            hexagram["code"] = hexagram["binary_code"]
            hexagram["summary"] = (
                f"{hexagram['name']}：{hexagram.get('theme', '卦意聚焦待补充')}。"
                f"{hexagram.get('judgement', '')}"
                f"{hexagram.get('guidance', '')}"
                f"宜{hexagram.get('favorable', '顺势推进')}，忌{caution_phrase(hexagram.get('caution', '失衡冒进'))}。"
            )
            return hexagram
    raise ValueError(f"未能定位卦名对应的结构：{name}")


def lookup_trigram_by_name(name: str) -> Dict[str, Any]:
    normalized = (name or "").strip().replace("卦", "")
    if normalized not in BAGUA_BY_NAME:
        raise ValueError(f"未识别的八卦名称：{name}")
    trigram = _enrich_trigram(BAGUA_BY_NAME[normalized])
    trigram["code"] = "".join(str(bit) for bit in trigram["lines"])
    trigram["summary"] = (
        f"{trigram['name']}卦：{trigram.get('theme', trigram['keywords'])}。"
        f"{trigram.get('guidance', '')}"
        f"宜{trigram.get('favorable', '顺势而行')}，忌{caution_phrase(trigram.get('caution', '避免失衡'))}。"
    )
    return trigram


def lookup_gua(query: str, lookup_mode: str = "auto") -> Dict[str, Any]:
    normalized_mode = (lookup_mode or "auto").strip().lower()
    if normalized_mode not in {"auto", "hexagram", "trigram"}:
        raise ValueError("lookup_mode 必须是 auto、hexagram 或 trigram。")

    query_text = (query or "").strip()
    if not query_text:
        raise ValueError("query 不能为空。")

    if normalized_mode in {"auto", "hexagram"}:
        if len("".join(ch for ch in query_text if ch in {"0", "1"})) == 6:
            result = lookup_hexagram_by_code(query_text)
            result["lookup_type"] = "hexagram"
            result["matched_query"] = query_text
            return result
        if (
            normalized_mode == "hexagram"
            or query_text.replace("卦", "") not in BAGUA_BY_NAME
        ):
            try:
                result = lookup_hexagram_by_name(query_text)
                result["lookup_type"] = "hexagram"
                result["matched_query"] = query_text
                return result
            except ValueError:
                if normalized_mode == "hexagram":
                    raise

    if normalized_mode in {"auto", "trigram"}:
        if len("".join(ch for ch in query_text if ch in {"0", "1"})) == 3:
            result = lookup_trigram_by_code(query_text)
            result["lookup_type"] = "trigram"
            result["matched_query"] = query_text
            return result
        result = lookup_trigram_by_name(query_text)
        result["lookup_type"] = "trigram"
        result["matched_query"] = query_text
        return result

    raise ValueError(f"未找到可匹配的卦象：{query}")


def compose_meihua_hexagram(
    *,
    upper_number: int,
    lower_number: int,
    moving_line: int,
    label: str = "梅花卦",
) -> Dict[str, Any]:
    """Shared single-line Mei Hua structure, after method-specific counting."""
    for value, limit, name in (
        (upper_number, 8, "上卦数"),
        (lower_number, 8, "下卦数"),
        (moving_line, 6, "动爻"),
    ):
        if type(value) is not int or not 1 <= value <= limit:
            raise ValueError(f"{name}必须为1至{limit}的整数。")
    upper = _bagua_from_number(upper_number)
    lower = _bagua_from_number(lower_number)
    base = build_hexagram(upper["name"], lower["name"])
    changed = build_changed_hexagram(base, moving_line)
    mutual_source = changed if base["binary_code"] in {"111111", "000000"} else base
    relation = relationship_by_element(upper["element"], lower["element"])
    return {
        "base_hexagram": base,
        "changed_hexagram": changed,
        "mutual_hexagram": build_mutual_hexagram(mutual_source),
        "cuo_hexagram": build_opposite_hexagram(base),
        "zong_hexagram": build_inverted_hexagram(base),
        "element_relation": relation,
        **resolve_body_use(base, moving_line),
        "summary": (
            f"{label}得{base['name']}，动{moving_line}爻，之{changed['name']}；"
            f"上卦{upper['name']}、下卦{lower['name']}，五行关系为{relation}。"
        ),
    }


def derive_meihua_hexagram(
    *,
    year_branch: str,
    lunar_month: int,
    lunar_day: int,
    hour_branch: str,
) -> Dict[str, Any]:
    if year_branch not in EARTHLY_BRANCHES or hour_branch not in EARTHLY_BRANCHES:
        raise ValueError("年支和时支必须是子至亥的十二地支。")
    if type(lunar_month) is not int or not 1 <= lunar_month <= 12:
        raise ValueError("农历月数必须为1至12；闰月沿用本月数。")
    if type(lunar_day) is not int or not 1 <= lunar_day <= 30:
        raise ValueError("农历日数必须为1至30。")
    year_number = EARTHLY_BRANCHES.index(year_branch) + 1
    hour_number = EARTHLY_BRANCHES.index(hour_branch) + 1
    upper_number = (year_number + lunar_month + lunar_day) % 8 or 8
    lower_number = (year_number + lunar_month + lunar_day + hour_number) % 8 or 8
    moving_line = (year_number + lunar_month + lunar_day + hour_number) % 6 or 6

    return {
        "method": "meihua_time_seed",
        "seed": {
            "year_branch": year_branch,
            "lunar_month": lunar_month,
            "lunar_day": lunar_day,
            "hour_branch": hour_branch,
            "upper_number": upper_number,
            "lower_number": lower_number,
            "moving_line": moving_line,
        },
        **compose_meihua_hexagram(
            upper_number=upper_number,
            lower_number=lower_number,
            moving_line=moving_line,
            label="梅花时卦",
        ),
    }
