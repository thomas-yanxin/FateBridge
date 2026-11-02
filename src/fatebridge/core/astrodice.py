"""Symbolic astrodice rules; never invent a degree, aspect or event time.

Duvendack documents the twelve faces; Ptolemy documents sign relationships.
FateBridge owns the synthesis policy, which is not an ancient dice method.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Literal

from fatebridge.core.astrology_tables import (
    DOMICILE_RULERS,
    ELEMENT_BY_SIGN,
    EXALTATION_SIGNS,
    MODALITY_BY_SIGN,
    RULER_BY_SIGN,
    SIGN_LABELS_ZH,
    SIGNS,
)
from fatebridge.core.classical_western import planet_sect
from fatebridge.core.ptolemy import SOURCE_URL as TRIPLICITY_SOURCE
from fatebridge.core.ptolemy import triplicity_assigned_rulers, triplicity_rulers
from fatebridge.utils.coordinates import parse_geo_coordinate

METHOD_ID = "astrodice_symbolic_v7"
SIGN_RULESET = "ptolemy_ashmand_1822_signs"
EDITORIAL_RULESET = "fatebridge_astrodice_editorial_v7"
DETRIMENT_RULESET = "houlding_opposite_domicile_definition_v1"
DETRIMENT_SOURCE = "https://www.skyscript.co.uk/dig2.html"
FACE_SOURCE = (
    "https://418ascendant.com/wp-content/uploads/2012/01/What-are-Astro-Dice.pdf"
)
DOMICILE_SOURCE = "https://sacred-texts.com/astro/ptb/ptb23.htm"
EXALTATION_SOURCE = "https://sacred-texts.com/astro/ptb/ptb25.htm"
HOUSE_SOURCE = "https://www.skyscript.co.uk/lilly_houses.html"
HOUSE_RULESET = "lilly_1647_house_joys_v1"
TRIPLICITY_RULESET = "ptolemy_robbins_1940_symbolic_triangles_v2"
PLANET_SECT_RULESET = "ptolemy_robbins_1940_planet_sect_v1"
# Christian Astrology, 1647, pp. 51-56; these are joys, not sign dignities.
JOY_HOUSES = {
    "Mercury": 1,
    "Moon": 3,
    "Venus": 5,
    "Mars": 6,
    "Sun": 9,
    "Jupiter": 11,
    "Saturn": 12,
}

PLANET_KEYWORDS = {
    "Sun": "核心意志、主导权、表达与承担",
    "Moon": "情绪需求、回应与习惯",
    "Mercury": "沟通、文书、协商与策略细节",
    "Venus": "关系温度、吸引、资源交换与和气",
    "Mars": "行动力、冲突点、推进与突破",
    "Jupiter": "扩展、机会、信念与增长空间",
    "Saturn": "边界、责任、压力与长期结构",
    "Uranus": "变化、独立、跳出惯例与临时改道",
    "Neptune": "想象、模糊、投射与理想化",
    "Pluto": "深层变化、控制与结构重置",
    "NorthNode": "新的学习方向、尚待练习的经验与发展主题",
    "SouthNode": "熟悉的模式、已有经验与需要取舍的惯性",
}
PLANETS = tuple(PLANET_KEYWORDS)
PLANET_LABELS_ZH = dict(
    zip(
        PLANETS,
        (
            "太阳",
            "月亮",
            "水星",
            "金星",
            "火星",
            "木星",
            "土星",
            "天王星",
            "海王星",
            "冥王星",
            "北交点",
            "南交点",
        ),
    )
)
PLANET_GLYPHS = dict(
    zip(
        PLANETS,
        (
            "☉",
            "☽",
            "☿",
            "♀",
            "♂",
            "♃",
            "♄",
            "♅",
            "♆",
            "♇",
            "☊",
            "☋",
        ),
    )
)
SIGN_GLYPHS = dict(zip(SIGNS, "♈♉♊♋♌♍♎♏♐♑♒♓"))
SIGN_KEYWORDS = {
    "Aries": "先行动、直接尝试与开局",
    "Taurus": "稳定、持续投入与实际价值",
    "Gemini": "多线沟通、信息交换与机动调整",
    "Cancer": "照顾感受、安全感与根基",
    "Leo": "表达、创造与获得认可",
    "Virgo": "拆解细节、校对与改进",
    "Libra": "关系平衡、条件协商与共识",
    "Scorpio": "深入、信任边界与投入程度",
    "Sagittarius": "扩大视角、探索与方向感",
    "Capricorn": "规则、责任与长期安排",
    "Aquarius": "独立思考、新方法与群体连接",
    "Pisces": "感受、想象与边界辨识",
}
HOUSE_KEYWORDS = {
    0: "自己、形象、主动权与起手姿态",
    1: "个人金钱、资源与投入产出",
    2: "沟通、消息、手足、邻里与短途往来",
    3: "家庭、居所、基底与根系",
    4: "恋爱、子女、创作、兴趣与娱乐",
    5: "日常事务、劳动安排、服务与生活节律",
    6: "伴侣、合作、对手与一对一互动",
    7: "共同资金、债务、继承与资源绑定",
    8: "远行、深造、信念与远景",
    9: "事业、职责、名声与公共角色",
    10: "朋友、社群、团队、愿景与外部助力",
    11: "独处、隐私、休整与幕后事务",
}
HOUSE_CHECKS = (
    "明确自己能决定的事项和行动边界。",
    "核对预算、可动用资源和成本。",
    "核实消息来源，把关键沟通写清楚。",
    "确认居住安排和家庭成员的实际需求。",
    "确认兴趣与投入是否得到回应。",
    "核对任务量、分工和可持续的生活安排。",
    "向对方确认意愿、责任与合作条件。",
    "核实共同资金、债务条款与退出安排。",
    "核实资格、行程和学习所需的现实条件。",
    "确认目标、职责和评价标准。",
    "确认团队承诺和支持是否实际到位。",
    "核对尚未公开的信息，安排休整与隐私边界。",
)
CONDITION_TEXT = {
    "domicile": "入庙：传统上表示该符号在自身熟悉的表达环境中。",
    "exaltation": "擢升：传统上表示该符号在此星座受到抬举。",
    "detriment": "失势：按对宫约定，表示该符号需调整惯用的表达方式。",
    "fall": "落陷：传统上表示该符号在此星座的表达受到约束。",
}


def _key(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("必须提供实际骰面，不能使用默认骰面")
    return "".join(
        value.strip().casefold().replace("\ufe0f", "").replace("\ufe0e", "").split()
    )


def normalize_sign(value: Any) -> str:
    key = _key(value)
    for sign in SIGNS:
        if key in {
            _key(sign),
            SIGN_LABELS_ZH[sign],
            SIGN_LABELS_ZH[sign] + "座",
            SIGN_GLYPHS[sign],
        }:
            return sign
    raise ValueError("sign必须为十二星座名称、中文名或星座符号")


def normalize_planet(value: Any) -> str:
    key = _key(value)
    aliases = {
        "日": "Sun",
        "月": "Moon",
        "☾": "Moon",
        "⯓": "Pluto",
        "北交": "NorthNode",
        "南交": "SouthNode",
    }
    if key in aliases:
        return aliases[key]
    for planet in PLANETS:
        if key in {_key(planet), PLANET_LABELS_ZH[planet], PLANET_GLYPHS[planet]}:
            return planet
    raise ValueError("planet必须为日月、八颗行星或南北交点的名称、中文名或符号")


def normalize_house(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= 11:
        raise ValueError("house必须为0..11的整数索引；实际第N宫传N-1，不可截断或钳制")
    return value


def _validate_coordinate_aliases(
    text: Any, gps: Any, *, axis: Literal["latitude", "longitude"]
) -> None:
    first = parse_geo_coordinate(text, axis=axis)
    second = parse_geo_coordinate(gps, axis=axis)
    if (text is not None and first is None) or (gps is not None and second is None):
        raise ValueError("附加天象盘不能使用空白坐标")
    if first is not None and second is not None:
        difference = first - second
        if axis == "longitude":
            difference = (difference + 180.0) % 360.0 - 180.0
        if not math.isclose(difference, 0, rel_tol=0, abs_tol=1e-9):
            raise ValueError(
                f"{axis}文本坐标与GPS坐标不一致；请仅提供一套已核对坐标，不能静默覆盖"
            )


def validate_context(
    *, date: Any, time: Any, zone: Any, lat: Any, lon: Any, gps_lat: Any, gps_lon: Any
) -> None:
    if date is None and time is None:
        if any(v is not None for v in (zone, lat, lon, gps_lat, gps_lon)):
            raise ValueError(
                "附加天象盘需要同时提供date/time/zone和经纬度；仅骰面解读请省略这些参数"
            )
        return
    if not all(isinstance(v, str) and v.strip() for v in (date, time, zone)):
        raise ValueError("附加天象盘需要明确date/time/zone，不能补默认时刻或时区")
    if (lat is None and gps_lat is None) or (lon is None and gps_lon is None):
        raise ValueError("附加天象盘需要明确经纬度，不能补默认地点")
    _validate_coordinate_aliases(lat, gps_lat, axis="latitude")
    _validate_coordinate_aliases(lon, gps_lon, axis="longitude")
    if (
        re.fullmatch(r"\d{1,2}:\d{1,2}(?::\d{1,2}(?:\.\d{1,6})?)?", time.strip())
        is None
    ):
        raise ValueError("time须为本地HH:MM[:SS[.微秒]]，时区单独通过zone传入")


def sign_condition(planet: str, sign: str) -> Dict[str, Any]:
    """Only sign-level facts: no degrees, sect, terms, faces or total score."""
    supported = planet in DOMICILE_RULERS
    domiciles = list(DOMICILE_RULERS[planet]) if supported else []
    exaltations = [EXALTATION_SIGNS[planet]] if supported else []
    definitions = [
        (
            "domicile",
            domiciles,
            SIGN_RULESET,
            DOMICILE_SOURCE,
            "direct_sign_assignment",
        ),
        (
            "exaltation",
            exaltations,
            SIGN_RULESET,
            EXALTATION_SOURCE,
            "direct_sign_assignment",
        ),
        (
            "detriment",
            [SIGNS[(SIGNS.index(s) + 6) % 12] for s in domiciles],
            DETRIMENT_RULESET,
            DETRIMENT_SOURCE,
            "opposite_domicile_definition",
        ),
        (
            "fall",
            [SIGNS[(SIGNS.index(s) + 6) % 12] for s in exaltations],
            SIGN_RULESET,
            EXALTATION_SOURCE,
            "opposite_exaltation_explicit_in_source",
        ),
    ]
    evidence = [
        {
            "condition": name,
            "matched": sign in signs if supported else None,
            "basis_signs": signs if supported else None,
            "ruleset_id": ruleset,
            "source_url": source,
            "derivation": derivation,
            "status": (
                "evaluated_sign_only" if supported else "outside_seven_planet_scope"
            ),
        }
        for name, signs, ruleset, source, derivation in definitions
    ]
    return {
        "status": "evaluated_sign_only" if supported else "outside_seven_planet_scope",
        "conditions": [row["condition"] for row in evidence if row["matched"] is True],
        "condition_evidence": evidence,
        "domicile_ruler": RULER_BY_SIGN[sign],
        "dispositor_status": (
            "self_symbolic" if RULER_BY_SIGN[sign] == planet else "not_in_roll"
        ),
        "unassessed": [
            "applied_triplicity_sect",
            "bound",
            "face",
            "sect",
            "degree",
            "aspects",
            "reception",
        ],
        "note": "不据此判定游离、总尊贵分或事情成败；自定位仅为符号关系，其他定位星未由本次骰面给出。",
    }


def house_condition(planet: str, house: int) -> Dict[str, Any]:
    joy = JOY_HOUSES.get(planet)
    return {
        "status": (
            "evaluated_house_symbol_only"
            if joy is not None
            else "outside_seven_planet_scope"
        ),
        "joy_house_number": joy,
        "in_joy": house + 1 == joy if joy is not None else None,
        "ruleset_id": HOUSE_RULESET,
        "scope": "Dice house label only; not observed planetary placement or an event outcome",
    }


def triplicity_condition(planet: str, sign: str) -> Dict[str, Any]:
    """Keep both conditional relationships; the roll has no astronomical sect."""
    rulers = {sect: triplicity_rulers(sign, sect) for sect in ("day", "night")}
    assigned = triplicity_assigned_rulers(sign)
    supported = planet in DOMICILE_RULERS

    def conditional_role(rule: Dict[str, Any]) -> str:
        if not supported:
            return "outside_seven_planet_scope"
        if planet == rule["primary"]:
            return "primary"
        if planet == rule["co_ruler"]:
            return "co_ruler"
        return "assigned_not_selected" if planet in assigned else "not_assigned"

    roles = {sect: conditional_role(rule) for sect, rule in rulers.items()}
    return {
        "status": (
            "conditional_sect_not_in_roll"
            if supported
            else "outside_seven_planet_scope"
        ),
        "ruleset_id": TRIPLICITY_RULESET,
        "sect": None,
        "assigned_rulers": assigned,
        "in_assigned_group": planet in assigned if supported else None,
        "roles_by_sect": roles,
        "rulers_by_sect": rulers,
        "matches_by_sect": {
            sect: planet in assignment.values() if supported else None
            for sect, assignment in rulers.items()
        },
        "match_definition": "selected_primary_or_explicit_co_ruler_under_named_sect",
        "scope": "Overall triangle assignment and separately named conditional roles; no sect transferred from optional sky context, no total dignity or event score",
    }


def planet_sect_condition(planet: str) -> Dict[str, Any]:
    """I.7 natural assignment is not the unobserved chart's day/night sect.

    Mercury requires a solar phase absent from the dice. Neither its house
    label nor a separate optional sky chart supplies that symbolic-roll fact.
    """
    supported = planet in DOMICILE_RULERS
    return {
        "status": (
            "conditional_on_solar_phase_not_in_roll"
            if planet == "Mercury"
            else (
                "natural_assignment_without_chart_sect"
                if supported
                else "outside_seven_planet_scope"
            )
        ),
        "ruleset_id": PLANET_SECT_RULESET,
        "natural_sect": planet_sect(planet, None),
        "assignments_by_solar_phase": (
            {
                "morning_star": planet_sect(planet, "oriental"),
                "evening_star": planet_sect(planet, "occidental"),
            }
            if planet == "Mercury"
            else None
        ),
        "solar_phase": None,
        "applied_chart_sect": None,
        "matches_chart_sect": None,
        "scope": "I.7 natural planet assignment only; no chart sect, visibility, dignity score or event judgement inferred from dice or optional sky",
    }


def _planet_sect_meaning(planet: str, condition: Dict[str, Any]) -> str:
    if condition["status"] == "outside_seven_planet_scope":
        return "此骰面不在《四书》Robbins译本I.7的七曜昼夜分派范围；未定义不等于逆派或失势。"
    if planet == "Mercury":
        assignments = condition["assignments_by_solar_phase"]
        labels = {"day": "昼曜", "night": "夜曜"}
        text = (
            f"依《四书》Robbins译本I.7，水星为晨星时属{labels[assignments['morning_star']]}，"
            f"为昏星时属{labels[assignments['evening_star']]}；本次骰面没有晨昏位置，未选定水星的分派。"
        )
    else:
        label = "昼曜" if condition["natural_sect"] == "day" else "夜曜"
        text = f"依《四书》Robbins译本I.7，{PLANET_LABELS_ZH[planet]}分派为{label}。"
        if planet == "Saturn":
            text += "原文以白昼的温暖调和土星的冷性说明这一分派。"
        elif planet == "Mars":
            text += "原文以夜间的湿润调和火星的干性说明这一分派。"
    return text + (
        "星体的昼夜分派不等于实际盘的昼夜条件；骰面宫号和附加天象均不替骰面选定昼夜，"
        "因此不判定本骰是否合派或逆派，也不计入尊贵总分。"
    )


def _triplicity_meaning(condition: Dict[str, Any]) -> str:
    if condition["status"] == "outside_seven_planet_scope":
        return "此骰面不在托勒密七曜三分性规则范围；未定义不等于无尊贵。"
    rulers = condition["rulers_by_sect"]
    role_text = {
        "primary": "本骰星为该条件下的首要主星",
        "co_ruler": "本骰星为该条件下明确列出的共管主星",
        "assigned_not_selected": "本骰星属总体分派，未列为该条件的首要或明确共管主星",
        "not_assigned": "本骰星不在本章该三角的总体分派内",
    }
    descriptions = []
    for sect, label in (("day", "昼"), ("night", "夜")):
        names = f"首要主星为{rulers[sect]['primary']}"
        if rulers[sect]["co_ruler"] is not None:
            names += f"，明确共管主星为{rulers[sect]['co_ruler']}"
        descriptions.append(
            f"{label}条件下{names}，{role_text[condition['roles_by_sect'][sect]]}"
        )
    return (
        "依《四书》Robbins译本I.18，该三角总体分派给"
        + "、".join(condition["assigned_rulers"])
        + "；"
        + "；".join(descriptions)
        + "。总体分派与条件角色分别保留；骰面未给出昼夜，附加天象也不替骰面选定条件，不计入尊贵总分。"
    )


def _interpretation_evidence(condition: Dict[str, Any]) -> Dict[str, Any]:
    """Link each returned paragraph to facts and to its actual source scope.

    This records dependencies; it does not certify arbitrary host-written prose.
    Keywords and practical prompts remain explicitly editorial.
    """

    def basis(
        kind: str, facts: List[str], rules: List[str], sources: List[str]
    ) -> Dict[str, Any]:
        return {
            "kind": kind,
            "fact_paths": list(facts),
            "rule_ids": list(rules),
            "ruleset_ids": list(sources),
        }

    editorial = [EDITORIAL_RULESET]
    result = {
        "interpretation.summary": basis(
            "product_vocabulary",
            ["planet", "sign", "symbolic_details.house_number"],
            ["three_faces", "symbolic_traits"],
            editorial,
        ),
        "interpretation.dispositor_meaning": basis(
            "editorial_traditional_paraphrase",
            [
                "symbolic_details.sign_condition.domicile_ruler",
                "symbolic_details.sign_condition.dispositor_status",
            ],
            ["sign_relationships"],
            [SIGN_RULESET, EDITORIAL_RULESET],
        ),
        "interpretation.house_condition_meaning": basis(
            "editorial_traditional_paraphrase",
            ["symbolic_details.house_condition"],
            ["planetary_house_joy"],
            [HOUSE_RULESET, EDITORIAL_RULESET],
        ),
        "interpretation.triplicity_meaning": basis(
            "conditional_rule_paraphrase",
            ["symbolic_details.triplicity_condition"],
            ["conditional_triplicity"],
            [TRIPLICITY_RULESET, EDITORIAL_RULESET],
        ),
        "interpretation.planet_sect_meaning": basis(
            "conditional_rule_paraphrase",
            ["planet", "symbolic_details.planet_sect_condition"],
            ["natural_planet_sect"],
            [PLANET_SECT_RULESET, EDITORIAL_RULESET],
        ),
        "interpretation.symbolic_links": basis(
            "product_convention",
            [
                "symbolic_details.houses_ruled_by_rolled_planet",
                "symbolic_details.symbolic_house_ring",
            ],
            ["symbolic_whole_sign_ring"],
            editorial,
        ),
        "interpretation.reality_check": basis(
            "reality_check_prompt",
            ["symbolic_details.house_number"],
            ["symbolic_traits"],
            editorial,
        ),
        "interpretation.limits": basis(
            "epistemic_limit",
            ["symbolic_details.sign_condition.unassessed", "validation"],
            [],
            editorial,
        ),
    }
    text_index = 0
    for index, row in enumerate(condition["condition_evidence"]):
        if row["matched"] is True:
            result[f"interpretation.condition_meanings.{text_index}"] = basis(
                "editorial_traditional_paraphrase",
                [
                    f"symbolic_details.sign_condition.condition_evidence.{index}",
                    "symbolic_details.sign_condition.conditions",
                ],
                ["sign_relationships"],
                [row["ruleset_id"], EDITORIAL_RULESET],
            )
            text_index += 1
    return {
        path.removeprefix("interpretation.").replace(".", "_"): {
            "text_path": path,
            **entry,
        }
        for path, entry in result.items()
    }


def build_symbolic_evidence(planet: str, sign: str, house: int) -> Dict[str, Any]:
    condition = sign_condition(planet, sign)
    house_number = house + 1
    start = (SIGNS.index(sign) - house) % 12
    ring: List[Dict[str, Any]] = [
        {
            "house_number": i + 1,
            "sign": SIGNS[(start + i) % 12],
            "domicile_ruler": RULER_BY_SIGN[SIGNS[(start + i) % 12]],
        }
        for i in range(12)
    ]
    details: Dict[str, Any] = {
        "house_number": house_number,
        "planet_kind": (
            "lunar_node"
            if planet in {"NorthNode", "SouthNode"}
            else (
                "luminary"
                if planet in {"Sun", "Moon"}
                else "dwarf_planet" if planet == "Pluto" else "planet"
            )
        ),
        "element": ELEMENT_BY_SIGN[sign],
        "modality": MODALITY_BY_SIGN[sign],
        "house_group": ("angular", "succedent", "cadent")[house % 3],
        "sign_condition": condition,
        "house_condition": house_condition(planet, house),
        "triplicity_condition": triplicity_condition(planet, sign),
        "planet_sect_condition": planet_sect_condition(planet),
        "symbolic_house_ring": ring,
        "houses_ruled_by_rolled_planet": [
            row["house_number"] for row in ring if row["domicile_ruler"] == planet
        ],
    }
    rulesets: List[Dict[str, Any]] = [
        {
            "id": "duvendack_2013_faces",
            "author": "Rev Bill Duvendack",
            "version": "2013",
            "source_url": FACE_SOURCE,
            "source_kind": "author_primary_explanation",
            "scope": "十二种骰面与星体/星座/宫位组合；不采用作者另述的出生盘扩展法。",
        },
        {
            "id": SIGN_RULESET,
            "author": "Claudius Ptolemy; tr. J. M. Ashmand",
            "version": "Tetrabiblos, 1822, Book I, chapters XX and XXII",
            "source_url": DOMICILE_SOURCE,
            "additional_urls": [EXALTATION_SOURCE],
            "source_kind": "primary_text_translation",
            "scope": "七曜入庙、擢升与落陷；失势定义另有来源，不归给本章；不声称原典含星骰法。",
        },
        {
            "id": EDITORIAL_RULESET,
            "author": "FateBridge contributors",
            "version": METHOD_ID,
            "source_path": "docs/astrodice.md",
            "source_kind": "product_convention",
            "scope": "现代中文关键词、元素/模式、宫位组、假设整宫轮与现实核对提示；非原典逐句翻译。",
        },
        {
            "id": HOUSE_RULESET,
            "author": "William Lilly",
            "version": "Christian Astrology, 1647, pp.51-56; Skyscript transcription",
            "source_url": HOUSE_SOURCE,
            "source_kind": "primary_text_transcription",
            "scope": "七曜喜乐宫关系；不将原文的临床、生死或灾祸判断用于咨询，不以喜乐判定事件吉凶。",
        },
        {
            "id": TRIPLICITY_RULESET,
            "author": "Claudius Ptolemy; tr. F. E. Robbins",
            "version": "Tetrabiblos, Loeb Classical Library, 1940, I.18",
            "source_url": TRIPLICITY_SOURCE,
            "source_kind": "primary_text_translation",
            "scope": "分别保留三角总体分派与昼夜首要/明确共管角色；水象为火星与昼金星/夜月亮共管；不混入Dorotheus第三主星或从天象选定骰面昼夜。",
        },
        {
            "id": DETRIMENT_RULESET,
            "author": "Deborah Houlding",
            "version": "Understanding Planetary Dignity and Debility, part 2; undated",
            "source_url": DETRIMENT_SOURCE,
            "source_kind": "author_primary_explanation",
            "scope": "仅采用作者对失势为守护星座对宫的明确说明；不当作托勒密XX章原文或采用文中其他尊贵表。",
        },
        {
            "id": PLANET_SECT_RULESET,
            "author": "Claudius Ptolemy; tr. F. E. Robbins",
            "version": "Tetrabiblos, Loeb Classical Library, 1940, I.7",
            "source_url": TRIPLICITY_SOURCE + "#7",
            "source_kind": "primary_text_translation",
            "scope": "七曜昼夜分派；水星保留晨星昼曜与昏星夜曜两条件。星体分派不等于实际盘的昼夜；不由骰面宫号或附加天象补条件。",
        },
    ]
    trace = [
        {
            "rule_id": "three_faces",
            "ruleset_id": rulesets[0]["id"],
            "inputs": {"planet": planet, "sign": sign, "house": house},
            "result": {"house_number": house_number},
            "scope": "user_supplied_symbols",
        },
        {
            "rule_id": "sign_relationships",
            "ruleset_id": EDITORIAL_RULESET,
            "supporting_ruleset_ids": [SIGN_RULESET, DETRIMENT_RULESET],
            "inputs": {"planet": planet, "sign": sign},
            "result": condition,
            "scope": "sign_only",
        },
        {
            "rule_id": "symbolic_whole_sign_ring",
            "ruleset_id": rulesets[2]["id"],
            "inputs": {"sign": sign, "house": house},
            "result": {
                "first_sign": SIGNS[start],
                "houses_ruled_by_rolled_planet": details[
                    "houses_ruled_by_rolled_planet"
                ],
            },
            "scope": "hypothetical_wheel_not_observed_sky",
        },
        {
            "rule_id": "symbolic_traits",
            "ruleset_id": rulesets[2]["id"],
            "inputs": {"planet": planet, "sign": sign, "house": house},
            "result": {
                "planet_keyword": PLANET_KEYWORDS[planet],
                "sign_keyword": SIGN_KEYWORDS[sign],
                "house_keyword": HOUSE_KEYWORDS[house],
                "element": details["element"],
                "modality": details["modality"],
                "house_group": details["house_group"],
            },
            "scope": "editorial_symbolic_vocabulary",
        },
        {
            "rule_id": "planetary_house_joy",
            "ruleset_id": HOUSE_RULESET,
            "inputs": {"planet": planet, "house": house},
            "result": details["house_condition"],
            "scope": "symbolic_house_only",
        },
        {
            "rule_id": "conditional_triplicity",
            "ruleset_id": TRIPLICITY_RULESET,
            "inputs": {"planet": planet, "sign": sign},
            "result": details["triplicity_condition"],
            "scope": "overall_triangle_assignment_and_both_conditional_roles_without_selecting_a_sect",
        },
        {
            "rule_id": "natural_planet_sect",
            "ruleset_id": PLANET_SECT_RULESET,
            "inputs": {"planet": planet},
            "result": details["planet_sect_condition"],
            "scope": "natural_assignment_and_conditional_mercury_roles_without_chart_sect",
        },
    ]
    interpretation: Dict[str, Any] = {
        "planet_keyword": PLANET_KEYWORDS[planet],
        "sign_keyword": SIGN_KEYWORDS[sign],
        "house_keyword": HOUSE_KEYWORDS[house],
        "summary": f"{planet}主{PLANET_KEYWORDS[planet]}，{SIGN_LABELS_ZH[sign]}座描述{SIGN_KEYWORDS[sign]}的方式，"
        f"第{house_number}宫指向{HOUSE_KEYWORDS[house]}的议题。",
        "condition_meanings": [CONDITION_TEXT[c] for c in condition["conditions"]],
        "triplicity_meaning": _triplicity_meaning(details["triplicity_condition"]),
        "planet_sect_meaning": _planet_sect_meaning(
            planet, details["planet_sect_condition"]
        ),
        "dispositor_meaning": (
            f"{SIGN_LABELS_ZH[sign]}座的传统守护星就是本次骰面的{planet}，可确认符号层的自定位；没有据此得到实际天文位置或其他星体的互容。"
            if condition["dispositor_status"] == "self_symbolic"
            else f"{SIGN_LABELS_ZH[sign]}座的传统守护星为{condition['domicile_ruler']}；本次骰面未给出该定位星，不能推断接纳或互容。"
        ),
        "house_condition_meaning": (
            f"依Lilly，第{details['house_condition']['joy_house_number']}宫是{planet}的喜乐宫；本骰宫{'符合' if details['house_condition']['in_joy'] else '不符合'}该宫号关系。喜乐不是入庙、擢升或成功概率。"
            if details["house_condition"]["in_joy"] is not None
            else "此骰面不在七曜喜乐宫规则范围，不能当作不喜乐或凶象。"
        ),
        "symbolic_links": (
            f"按假设整宫轮，此骰星符号主持第{details['houses_ruled_by_rolled_planet']}宫；这只是议题连接约定，不代表实际宫主星落点。"
            if details["houses_ruled_by_rolled_planet"]
            else "此骰面无七曜守护宫位，不套用现代外行星或交点守护星约定。"
        ),
        "reality_check": HOUSE_CHECKS[house],
        "basis": [
            "three_faces",
            "sign_relationships",
            "symbolic_whole_sign_ring",
            "symbolic_traits",
            "planetary_house_joy",
            "conditional_triplicity",
            "natural_planet_sect",
        ],
        "limits": "上述为符号解释；不直接给出是非、成功概率、具体应期或他人事实。没有条件标签不等于没有尊贵。",
    }
    interpretation["evidence"] = _interpretation_evidence(condition)
    return {
        "method_id": METHOD_ID,
        "symbolic_details": details,
        "rulesets": rulesets,
        "rule_trace": trace,
        "interpretation": interpretation,
        "validation": {
            "calendar": "not_applicable_to_symbolic_roll",
            "classical": "specified_sign_joy_triangle_and_natural_planet_sect_subsets_only",
            "interpretation": "deterministic_symbol_grounding_with_field_provenance",
            "prediction": "not_validated",
            "real_world_sample_size": 0,
            "authority_certified": False,
            "limitations": [
                "天文参考不认证占卜效果。",
                "未完成独立前瞻现实预测研究，不能宣称100%准确或权威认证。",
            ],
        },
    }
