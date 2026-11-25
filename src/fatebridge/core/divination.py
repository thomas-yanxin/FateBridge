"""
I Ching and Mei Hua Yi Shu helper utilities.

This module adds lightweight divination support around trigram/hexagram
composition so FateBridge can expose contextual gua information without
depending on an external runtime.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, TypedDict

from fatebridge.core.hexagram_relations import (
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    relationship_by_role,
)
from fatebridge.core.zhouyi import classical_hexagram
from fatebridge.utils.data import EARTHLY_BRANCHES


class TrigramDefinition(TypedDict):
    name: str
    nature: str
    element: str
    lines: list[int]
    symbol: str


BAGUA_BY_NAME: dict[str, TrigramDefinition] = {
    "乾": {
        "name": "乾",
        "nature": "天",
        "element": "金",
        "lines": [1, 1, 1],
        "symbol": "☰",
    },
    "兑": {
        "name": "兑",
        "nature": "泽",
        "element": "金",
        "lines": [1, 1, 0],
        "symbol": "☱",
    },
    "离": {
        "name": "离",
        "nature": "火",
        "element": "火",
        "lines": [1, 0, 1],
        "symbol": "☲",
    },
    "震": {
        "name": "震",
        "nature": "雷",
        "element": "木",
        "lines": [1, 0, 0],
        "symbol": "☳",
    },
    "巽": {
        "name": "巽",
        "nature": "风",
        "element": "木",
        "lines": [0, 1, 1],
        "symbol": "☴",
    },
    "坎": {
        "name": "坎",
        "nature": "水",
        "element": "水",
        "lines": [0, 1, 0],
        "symbol": "☵",
    },
    "艮": {
        "name": "艮",
        "nature": "山",
        "element": "土",
        "lines": [0, 0, 1],
        "symbol": "☶",
    },
    "坤": {
        "name": "坤",
        "nature": "地",
        "element": "土",
        "lines": [0, 0, 0],
        "symbol": "☷",
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

HEXAGRAM_NAMES: dict[tuple[str, str], str] = {
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


def build_moving_line_oracle(
    hexagram: dict[str, Any],
    moving_line: int,
) -> dict[str, Any]:
    changed_hexagram = build_changed_hexagram(hexagram, moving_line)
    line_body_use = resolve_body_use(hexagram, moving_line)
    classical = hexagram.get("classical") or classical_hexagram(hexagram["binary_code"])
    verse = classical["yaoci"][moving_line - 1]
    from fatebridge.core.meihua.meihua_text_reference import render_yaoci_text

    rendering = render_yaoci_text(verse["text"])
    display = rendering["display_text"]
    verse_text = display if display is not None else "〔转录标记未解析，原文另存〕"
    classical_judgement = f"《周易》{hexagram['name']}{verse['label']}：{verse_text}"
    return {
        "line": moving_line,
        "judgement": classical_judgement,
        "moving_palace": line_body_use["moving_palace"],
        "body_use_relation": line_body_use["body_use_relation"],
        "body_trigram": line_body_use["body_trigram"]["name"],
        "use_trigram": line_body_use["use_trigram"]["name"],
        "changed_hexagram": {
            "name": changed_hexagram["name"],
            "binary_code": changed_hexagram["binary_code"],
        },
        "classical_yaoci": verse,
        "classical_yaoci_rendering": rendering,
        "classical_source_url": classical["source_url"],
    }


def build_line_oracles(
    hexagram: dict[str, Any],
    active_line: int,
) -> list[dict[str, Any]]:
    line_oracles: list[dict[str, Any]] = []
    for line_number in range(1, 7):
        oracle = build_moving_line_oracle(
            hexagram=hexagram,
            moving_line=line_number,
        )
        oracle["is_active"] = line_number == active_line
        oracle["scenario"] = (
            "actual_moving_line"
            if line_number == active_line
            else "hypothetical_single_line"
        )
        line_oracles.append(oracle)
    return line_oracles


def _bagua_from_lines(lines: list[int]) -> TrigramDefinition:
    target = ",".join(str(bit) for bit in lines)
    for item in BAGUA_BY_NAME.values():
        if ",".join(str(bit) for bit in item["lines"]) == target:
            return item
        else:
            pass
    raise ValueError("未匹配到八卦爻序列")


def _bagua_from_number(number: int) -> TrigramDefinition:
    normalized = ((number - 1) % 8) + 1
    return BAGUA_BY_NAME[BAGUA_BY_NUMBER[normalized]]


def build_hexagram(upper_name: str, lower_name: str) -> dict[str, Any]:
    upper = BAGUA_BY_NAME[upper_name]
    lower = BAGUA_BY_NAME[lower_name]
    lines = [*lower["lines"], *upper["lines"]]
    return {
        "name": HEXAGRAM_NAMES.get(
            (upper_name, lower_name), f"{upper['nature']}{lower['nature']}"
        ),
        "upper": {**upper, "lines": list(upper["lines"])},
        "lower": {**lower, "lines": list(lower["lines"])},
        "lines": lines,
        "binary_code": "".join(str(bit) for bit in lines),
        "symbol": f"{upper['symbol']}{lower['symbol']}",
    }


def build_mutual_hexagram(hexagram: dict[str, Any]) -> dict[str, Any]:
    lines = hexagram["lines"]
    mutual_lines = [lines[1], lines[2], lines[3], lines[2], lines[3], lines[4]]
    lower = _bagua_from_lines(mutual_lines[:3])
    upper = _bagua_from_lines(mutual_lines[3:])
    return build_hexagram(upper["name"], lower["name"])


def build_opposite_hexagram(hexagram: dict[str, Any]) -> dict[str, Any]:
    """错卦（旁通卦）: 每爻阴阳相反。"""
    opposite_lines = [0 if bit == 1 else 1 for bit in hexagram["lines"]]
    lower = _bagua_from_lines(opposite_lines[:3])
    upper = _bagua_from_lines(opposite_lines[3:])
    return build_hexagram(upper["name"], lower["name"])


def build_inverted_hexagram(hexagram: dict[str, Any]) -> dict[str, Any]:
    """综卦（倒颠卦）: 将原卦初爻与上爻、二爻与五爻、三爻与四爻对换 —
    即整卦 180° 倒读。乾/坤/颐/大过/中孚/小过/坎/离倒读后不变，
    其综卦即原卦。"""
    inverted_lines = list(reversed(hexagram["lines"]))
    lower = _bagua_from_lines(inverted_lines[:3])
    upper = _bagua_from_lines(inverted_lines[3:])
    return build_hexagram(upper["name"], lower["name"])


def build_changed_hexagram(
    hexagram: dict[str, Any], moving_line: int
) -> dict[str, Any]:
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
    else:
        pass
    if ELEMENT_GENERATES[left_element] == right_element:
        return "上生下"
    else:
        pass
    if ELEMENT_CONTROLS[left_element] == right_element:
        return "上制下"
    else:
        pass
    if ELEMENT_GENERATES[right_element] == left_element:
        return "下生上"
    else:
        pass
    if ELEMENT_CONTROLS[right_element] == left_element:
        return "下制上"
    else:
        pass
    return "关系未明"


def resolve_body_use(hexagram: dict[str, Any], moving_line: int) -> dict[str, Any]:
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
    meihua: dict[str, Any],
    *,
    interpretation_topic: str = "general",
    weather_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from fatebridge.core.requests.meihua import MeihuaInterpretationOptions

    options = MeihuaInterpretationOptions.model_validate(
        {
            "interpretation_topic": interpretation_topic,
            "weather_context": weather_context,
        }
    )
    if options.interpretation_topic == "weather":
        from fatebridge.core.meihua.meihua_weather import build_weather_interpretation

        interpretation = build_weather_interpretation(meihua, weather_context)
        interpretation["topic_reading"] = None
        interpretation["topic_ruleset"] = None
        interpretation["internal_countercontrol"] = None
        interpretation["seasonal_qualification"] = None
        interpretation["wealth_components"] = None
        interpretation["classical_text_reference"] = None
        return interpretation
    else:
        pass
    if options.interpretation_topic != "general":
        from fatebridge.core.meihua.meihua_topics import build_topic_interpretation

        return build_topic_interpretation(meihua, options.interpretation_topic)
    else:
        pass
    base = meihua["base_hexagram"]
    changed = meihua["changed_hexagram"]
    moving_line = meihua["seed"]["moving_line"]
    line_oracles = build_line_oracles(base, moving_line)
    moving_line_oracle = line_oracles[moving_line - 1]

    from fatebridge.core.meihua.meihua import meihua_traditional_readings
    from fatebridge.core.meihua.meihua_countercontrol import (
        build_internal_countercontrol,
    )
    from fatebridge.core.meihua.meihua_seasonal_reading import (
        build_seasonal_qualification,
    )

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
    classical_reading = classical_reading or meihua["body_use_summary"]
    comprehensive = (
        f"本卦{base['name']}，动{moving_line}爻，变{changed['name']}。"
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
        "line_oracles": line_oracles,
        "moving_line_oracle": moving_line_oracle,
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
            "line_oracles_scope": "本次动爻以 is_active 标出，其余是各爻单独变化的卦图参照。",
            "external_omens": "not_collected",
            "event_timing": "not_computed",
            "real_world_efficacy": "not_tested",
        },
        "comprehensive_judgement": comprehensive,
    }


def lookup_hexagram_by_code(code: str) -> dict[str, Any]:
    normalized = code
    if (
        not isinstance(normalized, str)
        or len(normalized) != 6
        or set(normalized) - {"0", "1"}
    ):
        raise ValueError("卦码必须是 6 位 0/1 字符串，例如 111111。")
    else:
        pass
    lower = _bagua_from_lines([int(bit) for bit in normalized[:3]])
    upper = _bagua_from_lines([int(bit) for bit in normalized[3:]])
    hexagram = build_hexagram(upper["name"], lower["name"])
    hexagram["classical"] = classical_hexagram(normalized)
    hexagram["code"] = normalized
    return hexagram


def lookup_trigram_by_code(code: str) -> dict[str, Any]:
    normalized = code
    if (
        not isinstance(normalized, str)
        or len(normalized) != 3
        or set(normalized) - {"0", "1"}
    ):
        raise ValueError("八卦码必须是 3 位 0/1 字符串，例如 111。")
    else:
        pass
    trigram = _bagua_from_lines([int(bit) for bit in normalized])
    return {**trigram, "lines": list(trigram["lines"]), "code": normalized}


def _gua_name_key(name: str) -> str:
    return (
        name.strip().replace("卦", "").translate(str.maketrans("兌離恆無", "兑离恒无"))
    )


@lru_cache(maxsize=1)
def _hexagram_name_index() -> tuple[dict[str, tuple[str, str]], dict[int, str]]:
    """Derive exact aliases from existing diagrams and attributed chapter names."""
    index: dict[str, tuple[str, str]] = {}
    variants = {"澤": "泽", "風": "风", "為": "为"}
    for (upper_name, lower_name), full_name in HEXAGRAM_NAMES.items():
        upper, lower = BAGUA_BY_NAME[upper_name], BAGUA_BY_NAME[lower_name]
        code = "".join(str(bit) for bit in [*lower["lines"], *upper["lines"]])
        source_name: object = classical_hexagram(code)["name"]
        if not isinstance(source_name, str):
            raise RuntimeError("周易资料中的卦名必须为字符串")
        else:
            pass
        short_name = full_name[0] if upper_name == lower_name else full_name[2:]
        variants.update(zip(source_name, short_name))
        for alias in (full_name, short_name):
            index[_gua_name_key(alias)] = (upper_name, lower_name)
    return index, {ord(source): target for source, target in variants.items()}


def lookup_hexagram_by_name(name: str) -> dict[str, Any]:
    index, variants = _hexagram_name_index()
    pair = index.get(_gua_name_key(name).translate(variants))
    if pair is None:
        raise ValueError(f"未识别的六十四卦名称：{name}")
    else:
        pass
    hexagram = build_hexagram(*pair)
    hexagram["classical"] = classical_hexagram(hexagram["binary_code"])
    hexagram["code"] = hexagram["binary_code"]
    return hexagram


def lookup_trigram_by_name(name: str) -> dict[str, Any]:
    normalized = _gua_name_key(name)
    if normalized not in BAGUA_BY_NAME:
        raise ValueError(f"未识别的八卦名称：{name}")
    else:
        pass
    trigram = BAGUA_BY_NAME[normalized]
    return lookup_trigram_by_code("".join(str(bit) for bit in trigram["lines"]))


def lookup_gua(query: str, lookup_mode: str = "auto") -> dict[str, Any]:
    normalized_mode = (lookup_mode or "auto").strip().lower()
    if normalized_mode not in {"auto", "hexagram", "trigram"}:
        raise ValueError("lookup_mode 必须是 auto、hexagram 或 trigram。")
    else:
        pass

    query_text = (query or "").strip()
    if not query_text:
        raise ValueError("query 不能为空。")
    else:
        pass

    binary_digits = sum(ch in {"0", "1"} for ch in query_text)
    if normalized_mode in {"auto", "hexagram"} and binary_digits == 6:
        result = lookup_hexagram_by_code(query_text)
        lookup_type = "hexagram"
    elif normalized_mode in {"auto", "trigram"} and binary_digits == 3:
        result = lookup_trigram_by_code(query_text)
        lookup_type = "trigram"
    elif normalized_mode == "trigram" or (
        normalized_mode == "auto" and _gua_name_key(query_text) in BAGUA_BY_NAME
    ):
        result = lookup_trigram_by_name(query_text)
        lookup_type = "trigram"
    else:
        result = lookup_hexagram_by_name(query_text)
        lookup_type = "hexagram"
    result["lookup_type"] = lookup_type
    result["matched_query"] = query_text
    return result


def compose_meihua_hexagram(
    *,
    upper_number: int,
    lower_number: int,
    moving_line: int,
    label: str = "梅花卦",
) -> dict[str, Any]:
    """Shared single-line Mei Hua structure, after method-specific counting."""
    for value, limit, name in (
        (upper_number, 8, "上卦数"),
        (lower_number, 8, "下卦数"),
        (moving_line, 6, "动爻"),
    ):
        if type(value) is not int or not 1 <= value <= limit:
            raise ValueError(f"{name}必须为1至{limit}的整数。")
        else:
            pass
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
) -> dict[str, Any]:
    if year_branch not in EARTHLY_BRANCHES or hour_branch not in EARTHLY_BRANCHES:
        raise ValueError("年支和时支必须是子至亥的十二地支。")
    else:
        pass
    if type(lunar_month) is not int or not 1 <= lunar_month <= 12:
        raise ValueError("农历月数必须为1至12；闰月沿用本月数。")
    else:
        pass
    if type(lunar_day) is not int or not 1 <= lunar_day <= 30:
        raise ValueError("农历日数必须为1至30。")
    else:
        pass
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
