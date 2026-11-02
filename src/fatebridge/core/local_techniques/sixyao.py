"""
Liu Yao (六爻) divination for the FateBridge local-techniques package.

Pure relocation from the package facade: hexagram-palace lookup, 六神/六亲
enrichment, pattern detection, and public ``build_sixyao_result``. Chart
substrate primitives are imported from ``.chart``.
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE
from fatebridge.utils.timezones import validate_local_clock

from ..almanac import build_calendar_context
from ..calendar import BaZiCalendar
from ..divination import lookup_hexagram_by_code
from ..liuyao_evidence import build_liuyao_evidence
from ..liuyao_penalty import penalty_explanation
from ..zhouyi import moving_text_evidence
from .chart import (
    _join_lines,
    _normalize_date_text,
    _normalize_time_text,
    _render_snapshot_text,
    parse_local_datetime,
)

SIX_YAO_GODS = ["青龙", "朱雀", "勾陈", "腾蛇", "白虎", "玄武"]


SIX_YAO_NAMES = ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"]


_TRIGRAM_LOWER_BRANCHES = {
    "乾": ("子", "寅", "辰"),
    "坎": ("寅", "辰", "午"),
    "艮": ("辰", "午", "申"),
    "震": ("子", "寅", "辰"),
    "巽": ("丑", "亥", "酉"),
    "离": ("卯", "丑", "亥"),
    "坤": ("未", "巳", "卯"),
    "兑": ("巳", "卯", "丑"),
}


_TRIGRAM_UPPER_BRANCHES = {
    "乾": ("午", "申", "戌"),
    "坎": ("申", "戌", "子"),
    "艮": ("戌", "子", "寅"),
    "震": ("午", "申", "戌"),
    "巽": ("未", "巳", "卯"),
    "离": ("酉", "未", "巳"),
    "坤": ("丑", "亥", "酉"),
    "兑": ("亥", "酉", "未"),
}


_BAGONG_BASES = [
    ("乾", "111111", "金"),
    ("坎", "010010", "水"),
    ("艮", "001001", "土"),
    ("震", "100100", "木"),
    ("巽", "011011", "木"),
    ("离", "101101", "火"),
    ("坤", "000000", "土"),
    ("兑", "110110", "金"),
]


_BAGONG_POSITION_INFO = [
    ("本宫", "000000", 6),
    ("一世", "100000", 1),
    ("二世", "110000", 2),
    ("三世", "111000", 3),
    ("四世", "111100", 4),
    ("五世", "111110", 5),
    ("游魂", "111010", 4),
    ("归魂", "000010", 3),
]


_BRANCH_TO_ELEMENT = {
    "寅": "木",
    "卯": "木",
    "巳": "火",
    "午": "火",
    "申": "金",
    "酉": "金",
    "亥": "水",
    "子": "水",
    "辰": "土",
    "戌": "土",
    "丑": "土",
    "未": "土",
}


_LIUSHEN_CYCLE = ("青龙", "朱雀", "勾陈", "腾蛇", "白虎", "玄武")


_LIUSHEN_OFFSET_BY_STEM = {
    "甲": 0,
    "乙": 0,
    "丙": 1,
    "丁": 1,
    "戊": 2,
    "己": 3,
    "庚": 4,
    "辛": 4,
    "壬": 5,
    "癸": 5,
}


def _xor_binary(code: str, mask: str) -> str:
    return "".join("1" if a != b else "0" for a, b in zip(code, mask))


def _build_hexagram_palace_lookup() -> Dict[str, Dict[str, Any]]:
    """根据 8 本宫 × 8 卦位 × XOR 掩码生成 64 卦 → 宫 / 世爻 / 宫五行 查表。"""
    lookup: Dict[str, Dict[str, Any]] = {}
    for palace_name, base_code, palace_element in _BAGONG_BASES:
        for position_name, mask, shi_line in _BAGONG_POSITION_INFO:
            code = _xor_binary(base_code, mask)
            # 应爻 = (世爻 + 3 - 1) % 6 + 1 (1-indexed)
            ying_line = ((shi_line + 2) % 6) + 1
            lookup[code] = {
                "palace": palace_name,
                "palace_element": palace_element,
                "position": position_name,
                "shi_line": shi_line,
                "ying_line": ying_line,
            }
    return lookup


_HEXAGRAM_PALACE_LOOKUP: Dict[str, Dict[str, Any]] = _build_hexagram_palace_lookup()


def _decode_trigrams(code: str) -> Tuple[str, str]:
    """拆分六位二进制到 (下卦, 上卦) 三画卦名。"""
    inv = {
        v: k
        for k, v in {
            "乾": "111",
            "坎": "010",
            "艮": "001",
            "震": "100",
            "巽": "011",
            "离": "101",
            "坤": "000",
            "兑": "110",
        }.items()
    }
    lower = inv.get(code[0:3])
    upper = inv.get(code[3:6])
    return lower or "?", upper or "?"


_LIUCHONG_HEXAGRAM_CODES = frozenset(
    {
        "111111",  # 乾为天
        "000000",  # 坤为地
        "100100",  # 震为雷
        "011011",  # 巽为风
        "010010",  # 坎为水
        "101101",  # 离为火
        "001001",  # 艮为山
        "110110",  # 兑为泽
        "100111",  # 天雷无妄
        "111100",  # 雷天大壮
    }
)


_LIUHE_HEXAGRAM_CODES = frozenset(
    {
        "111000",  # 地天泰
        "000111",  # 天地否
        "000100",  # 雷地豫
        "100000",  # 地雷复
        "010110",  # 泽水困
        "110010",  # 水泽节
        "001101",  # 火山旅
        "101001",  # 山火贲
    }
)


_BRANCH_CLASH = {
    "子": "午",
    "午": "子",
    "丑": "未",
    "未": "丑",
    "寅": "申",
    "申": "寅",
    "卯": "酉",
    "酉": "卯",
    "辰": "戌",
    "戌": "辰",
    "巳": "亥",
    "亥": "巳",
}


def _detect_sixyao_patterns(
    current_code: str,
    changed_code: str,
    current_branches: List[str],
    changed_branches: List[str],
    moving_indices: List[int],
    fanfu: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """识别六爻常见格局：六冲/六合/反吟/伏吟。"""
    patterns: List[Dict[str, str]] = []
    # 本卦六冲 / 六合
    if current_code in _LIUCHONG_HEXAGRAM_CODES:
        patterns.append(
            {"name": "本卦六冲", "basis": "本卦属十个六冲卦：八纯卦及无妄、大壮。"}
        )
    if current_code in _LIUHE_HEXAGRAM_CODES:
        patterns.append({"name": "本卦六合", "basis": "本卦为六合卦。"})
    # 之卦六冲 / 六合
    if current_code != changed_code:
        if changed_code in _LIUCHONG_HEXAGRAM_CODES:
            patterns.append({"name": "变卦六冲", "basis": "之卦转为六冲。"})
        if changed_code in _LIUHE_HEXAGRAM_CODES:
            patterns.append({"name": "变卦六合", "basis": "之卦归六合。"})

    # 伏吟 / 反吟 (只在动爻上判断, 避开 changed_branch 为空的静爻)
    fu_count = 0
    fan_count = 0
    for idx in moving_indices:
        if idx < 0 or idx >= 6:
            continue
        orig_branch = current_branches[idx]
        new_branch = changed_branches[idx]
        if not orig_branch or not new_branch:
            continue
        if orig_branch == new_branch:
            fu_count += 1
        elif _BRANCH_CLASH.get(orig_branch) == new_branch:
            fan_count += 1
    if fu_count and fu_count == len(moving_indices):
        patterns.append(
            {
                "name": "伏吟",
                "basis": "仅实际动爻的纳支均保持相同；动爻仍是动爻，不代表卦未变。",
            }
        )
    elif fu_count:
        patterns.append(
            {
                "name": "局部伏吟",
                "basis": f"{fu_count}个动爻之支与原支相同。",
            }
        )
    if fan_count and fan_count == len(moving_indices):
        patterns.append(
            {
                "name": "反吟",
                "basis": "仅实际动爻的变支均与本支相冲；内外卦盘与卦体另查反伏证据。",
            }
        )
    elif fan_count:
        patterns.append(
            {
                "name": "局部反吟",
                "basis": f"{fan_count}个动爻之支与原支相冲。",
            }
        )

    if fanfu:
        if fanfu["explicit_body_example"]:
            body = fanfu["explicit_body_example"]
            patterns.append({"name": "卦体" + body["kind"], "basis": body["basis"]})
        for region in fanfu["regions"]:
            if region["nazhi_relation"] in ("反吟", "伏吟"):
                label = "内卦" if region["region"] == "inner" else "外卦"
                patterns.append(
                    {
                        "name": label + "纳支" + region["nazhi_relation"],
                        "basis": "该经卦已变，三爻卦盘纳支"
                        + ("相冲" if region["nazhi_relation"] == "反吟" else "相同")
                        + "；静爻位置只作卦盘比较，不新增变爻作用。",
                    }
                )

    return {
        "patterns": patterns,
        "is_liuchong_base": current_code in _LIUCHONG_HEXAGRAM_CODES,
        "is_liuhe_base": current_code in _LIUHE_HEXAGRAM_CODES,
        "is_liuchong_changed": current_code != changed_code
        and changed_code in _LIUCHONG_HEXAGRAM_CODES,
        "is_liuhe_changed": current_code != changed_code
        and changed_code in _LIUHE_HEXAGRAM_CODES,
    }


def _liuqin_against_palace(palace_element: str, line_element: str) -> str:
    if palace_element == line_element:
        return "兄弟"
    generates = {"金": "水", "水": "木", "木": "火", "火": "土", "土": "金"}
    controls = {"金": "木", "木": "土", "土": "水", "水": "火", "火": "金"}
    if generates.get(line_element) == palace_element:
        return "父母"  # 生宫者
    if generates.get(palace_element) == line_element:
        return "子孙"  # 宫所生
    if controls.get(line_element) == palace_element:
        return "官鬼"  # 克宫者
    if controls.get(palace_element) == line_element:
        return "妻财"  # 宫所克
    return "平"


def _build_sixyao_enrichment(
    current_code: str,
    changed_code: str,
    day_gan: Optional[str],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """生成本卦信息 + 六爻纳甲/世应/六亲/六神。lines 下标 0=初爻，5=上爻。"""

    current_info = _HEXAGRAM_PALACE_LOOKUP.get(current_code, {})
    changed_info = _HEXAGRAM_PALACE_LOOKUP.get(changed_code, {})

    lower_trigram, upper_trigram = _decode_trigrams(current_code)
    lower_branches = _TRIGRAM_LOWER_BRANCHES.get(lower_trigram, ("", "", ""))
    upper_branches = _TRIGRAM_UPPER_BRANCHES.get(upper_trigram, ("", "", ""))
    branches = list(lower_branches) + list(upper_branches)

    # 之卦地支 (仅作参考, 用于动爻变后的六亲比对)
    changed_lower_trigram, changed_upper_trigram = _decode_trigrams(changed_code)
    changed_branches = list(
        _TRIGRAM_LOWER_BRANCHES.get(changed_lower_trigram, ("", "", ""))
    ) + list(_TRIGRAM_UPPER_BRANCHES.get(changed_upper_trigram, ("", "", "")))

    palace_element = current_info.get("palace_element", "")
    shi_line = current_info.get("shi_line", 0)
    ying_line = current_info.get("ying_line", 0)

    offset = _LIUSHEN_OFFSET_BY_STEM.get(day_gan or "", 0)

    enriched_lines: List[Dict[str, Any]] = []
    for i in range(6):
        branch = branches[i]
        element = _BRANCH_TO_ELEMENT.get(branch, "")
        liuqin = _liuqin_against_palace(palace_element, element) if element else "平"
        # 动爻后的变爻地支 + 之卦六亲 (用本宫五行)
        changed_branch = changed_branches[i] if changed_branches[i] else branch
        changed_element = _BRANCH_TO_ELEMENT.get(changed_branch, "")
        changed_liuqin = (
            _liuqin_against_palace(palace_element, changed_element)
            if changed_element
            else "平"
        )
        position_label = SIX_YAO_NAMES[i]
        position_num = i + 1
        shi_ying = ""
        if position_num == shi_line:
            shi_ying = "世"
        elif position_num == ying_line:
            shi_ying = "应"
        liushen = _LIUSHEN_CYCLE[(offset + i) % 6]
        enriched_lines.append(
            {
                "branch": branch,
                "element": element,
                "liuqin": liuqin,
                "shi_ying": shi_ying,
                "liushen": liushen,
                "position_label": position_label,
                "position": position_num,
                "changed_branch": changed_branch if changed_branch != branch else None,
                "changed_liuqin": changed_liuqin if changed_branch != branch else None,
            }
        )

    hexagram_info = {
        "current_palace": current_info.get("palace"),
        "current_position": current_info.get("position"),
        "current_palace_element": palace_element,
        "shi_line": shi_line,
        "ying_line": ying_line,
        "changed_palace": changed_info.get("palace"),
        "changed_position": changed_info.get("position"),
        "changed_palace_element": changed_info.get("palace_element"),
    }
    return hexagram_info, enriched_lines


def _build_context(
    *,
    date_text: str,
    time_text: str,
    timezone_name: Optional[str],
) -> Dict[str, Any]:
    moment = parse_local_datetime(date_text, time_text, timezone_name)
    raw_clock = datetime.fromisoformat(
        f"{_normalize_date_text(date_text)} {_normalize_time_text(time_text)}"
    )
    if raw_clock.tzinfo is None:
        # An explicit offset identifies an instant in a repeated DST hour;
        # an unqualified wall clock must not silently choose a fold or gap.
        validate_local_clock(moment)
    timezone_value = timezone_name or DEFAULT_BIRTH_TIMEZONE
    pillars = BaZiCalendar.get_four_pillars(moment, timezone_name=timezone_value)
    calendar_context = build_calendar_context(
        moment, timezone_name=timezone_value, pillars=pillars
    )
    lunar = calendar_context.get("lunar_calendar") or {}
    nongli = {
        "birth": calendar_context["solar_datetime"],
        "nongli": lunar.get("display"),
        "yearJieqi": f"{pillars['year'][0]}{pillars['year'][1]}",
        "year": f"{pillars['year'][0]}{pillars['year'][1]}",
        "yearGanZi": f"{pillars['year'][0]}{pillars['year'][1]}",
        "monthGanZi": f"{pillars['month'][0]}{pillars['month'][1]}",
        "dayGanZi": f"{pillars['day'][0]}{pillars['day'][1]}",
        "time": f"{pillars['hour'][0]}{pillars['hour'][1]}",
        "jieqi": calendar_context["current_solar_term"]["name"],
        "jiedelta": calendar_context["solar_term_delta"]["description"],
        "monthInt": lunar.get("month"),
        "dayInt": lunar.get("day"),
        "month": lunar.get("month_cn"),
        "day": lunar.get("day_cn"),
        "leap": lunar.get("is_leap_month"),
    }
    return {
        "moment": moment,
        "timezone_name": timezone_value,
        "pillars": pillars,
        "calendar_context": calendar_context,
        "lunar": lunar,
        "nongli": nongli,
    }


def _normalize_gua_lines(lines: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if lines and len(lines) != 6:
        raise ValueError("六爻 lines 必须恰为 6 条，按初爻至上爻排列")
    normalized: List[Dict[str, Any]] = []
    for item in lines or []:
        if not isinstance(item, dict):
            raise ValueError("六爻 lines 每条必须是爻线对象")
        value = item.get("value")
        if type(value) is not int or value not in (0, 1):
            raise ValueError("六爻 value 必须为 0 或 1")
        if type(item.get("change", False)) is not bool:
            raise ValueError("六爻 change 必须为布尔值")
        normalized.append(
            {
                "value": value,
                "change": bool(item.get("change")),
                "god": item.get("god"),
                "name": item.get("name"),
            }
        )
    return normalized


def _clean_code(code: Optional[str]) -> str:
    if code is None:
        return ""
    if not isinstance(code, str) or len(code) != 6 or set(code) - {"0", "1"}:
        raise ValueError("六爻卦码必须是 6 位 0/1 字符串，不接受被忽略的其他字符。")
    return code


def needs_random_coin_cast(inputs: Dict[str, Any]) -> bool:
    """Share the engine's manual-input precedence with replay seed handling."""
    return (
        (inputs.get("method") or "auto").strip().lower() == "coin"
        and inputs.get("coins") is None
        and not _normalize_gua_lines(inputs.get("lines"))
        and not (
            _clean_code(inputs.get("gua_code"))
            or _clean_code(inputs.get("changed_code"))
        )
    )


def _derive_gua_code(lines: List[Dict[str, Any]]) -> str:
    return "".join(str(int(line.get("value", 0))) for line in lines) or "000000"


def _derive_changed_code(lines: List[Dict[str, Any]]) -> str:
    chars: List[str] = []
    for line in lines:
        value = int(line.get("value", 0))
        if line.get("change"):
            value = 1 - value
        chars.append(str(value))
    return "".join(chars) or "000000"


def _lines_from_codes(
    current_code: str, changed_code: Optional[str] = None
) -> List[Dict[str, Any]]:
    current = _clean_code(current_code)
    changed = _clean_code(changed_code or current_code)
    if len(current) != 6 or len(changed) != 6:
        raise ValueError("六爻卦码必须是 6 位 0/1 字符串。")

    normalized: List[Dict[str, Any]] = []
    for index, (current_bit, changed_bit) in enumerate(zip(current, changed)):
        normalized.append(
            {
                "value": int(current_bit),
                "change": current_bit != changed_bit,
                "god": SIX_YAO_GODS[index],
                "name": SIX_YAO_NAMES[index],
            }
        )
    return normalized


# 摇钱起卦（三枚铜钱筮法）：每枚铜钱「字面(正)=2、背面(反)=3」，三枚之和定爻。
# 6=老阴(阴动)、7=少阳(阳静)、8=少阴(阴静)、9=老阳(阳动)。老阴/老阳为动爻。
_COIN_TOSS_YAO: Dict[int, Dict[str, Any]] = {
    6: {"yao": "老阴", "symbol": "× 交", "value": 0, "change": True},
    7: {"yao": "少阳", "symbol": "⚊", "value": 1, "change": False},
    8: {"yao": "少阴", "symbol": "⚋", "value": 0, "change": False},
    9: {"yao": "老阳", "symbol": "○ 重", "value": 1, "change": True},
}


def _random_coin_tosses(rng: random.Random) -> List[int]:
    """系统随机摇卦：六掷，每掷三枚铜钱（字面=2 / 背面=3 等概率），返回六个和。"""
    return [sum(rng.choice((2, 3)) for _ in range(3)) for _ in range(6)]


def _coin_lines_and_meta(
    coins: List[int],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """把六掷之和（初爻→上爻）转成爻线 + 每掷的可溯源元数据。"""
    if len(coins) != 6:
        raise ValueError("摇钱起卦需要 6 掷（初爻→上爻）。")
    lines: List[Dict[str, Any]] = []
    tosses: List[Dict[str, Any]] = []
    for index, raw in enumerate(coins):
        info = _COIN_TOSS_YAO.get(raw) if type(raw) is int else None
        if info is None:
            raise ValueError(
                "摇钱起卦每掷之和必须为 6/7/8/9（三枚铜钱，字面=2、背面=3）。"
            )
        lines.append(
            {
                "value": info["value"],
                "change": info["change"],
                "god": SIX_YAO_GODS[index],
                "name": SIX_YAO_NAMES[index],
            }
        )
        tosses.append(
            {
                "position": index + 1,
                "name": SIX_YAO_NAMES[index],
                "sum": int(raw),
                "yao": info["yao"],
                "symbol": info["symbol"],
                "moving": info["change"],
            }
        )
    return lines, tosses


def _hexagram_desc_payload(code: str) -> Dict[str, Any]:
    detail = lookup_hexagram_by_code(code)
    return {
        "code": code,
        "name": detail.get("name"),
        "theme": detail.get("theme"),
        "卦辞": detail["classical"]["guaci"],
        "象曰": detail["classical"]["daxiang"],
        "modern_judgement": detail.get("judgement"),
        "classical_source_url": detail["classical"]["source_url"],
        "guidance": detail.get("guidance"),
        "favorable": detail.get("favorable"),
        "caution": detail.get("caution"),
        "summary": detail.get("summary"),
        "raw": detail,
    }


def _build_sixyao_snapshot_text(
    *,
    input_normalized: Dict[str, Any],
    nongli: Dict[str, Any],
    current_payload: Dict[str, Any],
    changed_payload: Dict[str, Any],
    lines: List[Dict[str, Any]],
    evidence: Dict[str, Any],
    text_evidence: Dict[str, Any],
) -> str:
    line_texts = []
    for index, line in enumerate(lines, start=1):
        yao_type = "阳爻" if int(line.get("value", 0)) == 1 else "阴爻"
        moving = "（动）" if line.get("change") else "（静）"
        extras = []
        if line.get("god"):
            extras.append(f"六神:{line['god']}")
        if line.get("name"):
            extras.append(f"爻名:{line['name']}")
        suffix = f"，{'，'.join(extras)}" if extras else ""
        line_texts.append(f"第{index}爻：{yao_type}{moving}{suffix}")

    judge_lines = []
    if input_normalized.get("question"):
        judge_lines.append(f"问题：{input_normalized['question']}")
    judge_lines.append(
        f"本卦：{current_payload.get('name', input_normalized['gua_code'])}"
    )
    if current_payload.get("卦辞"):
        judge_lines.append(f"卦辞：{current_payload['卦辞']}")
    judge_lines.append(
        f"之卦：{changed_payload.get('name', input_normalized['changed_code'])}"
    )
    if changed_payload.get("卦辞"):
        judge_lines.append(f"之卦卦辞：{changed_payload['卦辞']}")

    conditional = evidence["conditional_analysis"]
    focus = conditional["focus"]
    condition_lines = [f"取用状态：{focus['status']}", focus["scope"]]
    if comparison := evidence["calendar_conventions"].get("month_model_comparison"):
        if comparison.get("month_changed") is True:
            condition_lines.append(
                f"同次交气模型比较：本次采用{comparison['calculation_month_branch']}月，"
                f"已完成的原生选择路径为{comparison['native_month_branch']}月；"
                "月令相关判断依本次采用月支解释。"
            )
            condition_lines.append(comparison["scope"])
        elif not comparison["coverage_complete"]:
            condition_lines.append("同次交气比较未完成，不能认定月令路径一致。")
    if focus["selected"]:
        selected = focus["selected"]
        location = {
            "visible": "",
            "changed": "变爻",
            "hidden": "伏神",
            "month": "月建",
            "day": "日辰",
        }[selected["location"]]
        anchor = (
            f"第{selected['position']}爻" if selected["position"] is not None else ""
        )
        condition_lines.append(
            f"明确用爻：{anchor}{location}{selected['liuqin']}{selected['branch']}；"
            "此为调用方给定的分析前提"
        )
    condition_lines.extend(
        f"第{row['position']}爻：月令层{row['monthly_strength']['category']}；{row['activity']}"
        + (f"；{'、'.join(row['binding_cues'])}" if row["binding_cues"] else "")
        + (
            "；暗动扶源待审，不能据原候选认定已活动"
            if row.get("activity_condition_status")
            == "activity_prerequisites_unresolved"
            else ""
        )
        for row in conditional["lines"]
    )
    control = conditional["control_conditions"]
    for row in conditional["month_break_conditions"]["lines"]:
        if row["day_value_exception"]:
            condition_lines.append(
                f"第{row['position']}爻{row['branch']}：原月令月破，本日同支值日，本项月令反制不计入当前克制；"
                + (
                    "仍有其他反制待审，不据此确认全局不破。"
                    if row["retained_other_oppositions"]
                    else "没有因此免除其他独立条件。"
                )
            )
        changed_month = row["changed"]
        if changed_month and changed_month["day_value_exception"]:
            condition_lines.append(
                f"第{row['position']}爻本位变{changed_month['branch']}：原月破，本日同支值日，仅解除本项月令阻碍；原爻其他生克效力另审。"
            )
    for row in conditional["month_break_conditions"]["hidden"]:
        for kind, label in (("hidden", "伏神"), ("flying", "飞神")):
            if row[kind]["day_value_exception"]:
                condition_lines.append(
                    f"第{row['position']}爻{label}{row[kind]['branch']}：原月破而本日同支值日，不能只据月破认定失力；飞伏关系与其他反制另审。"
                )
    back_support = conditional["back_generation_conditions"]
    for source in back_support["sources"]:
        if not source["is_back_generation"]:
            continue
        status = (
            "回头生空破门槛匹配"
            if source["condition_match"] is True
            else (
                "巳寅申特定条款排除本位寅回头生"
                if source["condition_match"] is False
                else (
                    "三支活动待审，寅回头生不能确认"
                    if source["status"] == "own_yin_generation_triad_activity_pending"
                    else "回头生变爻空破待审"
                )
            )
        )
        relations = source["changed_calendar_relations"]
        condition_lines.append(
            f"第{source['position']}爻{source['branch']}本位化{source['changed_branch']}：{status}；"
            f"变爻所受日月关系：月{relations['month']}，日{relations['day']}；原爻生克效力另审"
        )
    condition_lines.append(back_support["scope"])
    for pair in control["controls"]:
        if not pair["emit_edge"]:
            continue
        status = (
            "所列克制条件匹配，最终效力仍待审"
            if pair["condition_match"] is True
            else (
                "克制前提未决"
                if pair["condition_match"] is None
                else {
                    "static_cannot_control_active": "静爻不克活动爻",
                    "active_control_obstructs_static_control": "静爻受活动爻克，向外克暂受阻",
                    "back_control_obstructs_outgoing_candidate": "回头克来源受阻，先审解救",
                    "own_si_growth_or_back_control_pending": "金化巳的长生或回头克资格待审",
                }.get(pair["status"], "未匹配所列克制前提")
            )
        )
        if pair["source_rescue_used"]:
            status += (
                "；本位回头生支持该条件，原日月反制仍保留"
                if any(
                    a.get("harm_condition_match", True) is True
                    for a in pair["source_calendar_oppositions"]
                )
                else "；本位回头生支持该条件，三支总作用仍待审"
            )
        elif pair["source_void_fill_used"]:
            status += (
                "；当日冲空的同日日克资格已核，原旬空与日克事实仍保留，其他门槛另审"
            )
        elif pair["source_back_generation_condition"] is False and any(
            "三支总作用待审" in reason for reason in pair["source_obstructions"]
        ):
            status += "；三支总作用待审，本位回头生支持未确认"
        condition_lines.append(
            f"第{pair['source_position']}爻{pair['source_branch']}克第{pair['target_position']}爻{pair['target_branch']}：{status}"
        )
    condition_lines.append(control["scope"])
    condition_lines.append(control["void_fill_qualification"]["scope"])
    generation = conditional["generation_conditions"]
    if generation["focus"] is not None:
        generation_focus = generation["focus"]
        condition_lines.append(
            f"明确用爻第{generation_focus['position']}爻{generation_focus['branch']}："
            + generation_focus["source_explanation"]
        )
        condition_lines.append(generation_focus["target_explanation"])
    for pair in generation["generations"]:
        if pair["status"] == "static_outside_current_all_static_generation_scope":
            continue
        source_status = (
            "生源条件匹配"
            if pair["condition_match"] is True
            else (
                "生源条件待审"
                if pair["condition_match"] is None
                else "未匹配所列生源条件"
            )
        )
        reception = (
            "受生爻未见所列承受障碍"
            if pair["target_reception_condition"] is True
            else (
                "受生爻空破前提待审"
                if pair["target_reception_condition"] is None
                else "受生爻月破日克无独立根，不能据有生即作受益"
            )
        )
        pair_text = f"第{pair['source_position']}爻{pair['source_branch']}生第{pair['target_position']}爻{pair['target_branch']}：{source_status}；{reception}"
        if qualification_note := pair.get("qualification_explanation"):
            pair_text += "；" + qualification_note
        condition_lines.append(pair_text)
    condition_lines.append(generation["scope"])
    clash = conditional["clash_conditions"]
    for row in clash["lines"]:
        if not row["clash_actors"]:
            continue
        labels = []
        if row["is_day_clash"]:
            labels.append("日冲事实")
        if row["day_void_fill_condition"]:
            labels.append("当日冲空填实条件匹配；原旬空支表保留")
        if row["day_break_condition"] is True:
            labels.append("静爻日破条件匹配；未推永久无用")
        elif row["day_break_condition"] is None:
            labels.append("静爻日冲与生扶前提未决")
        if (
            row["scatter_status"]
            == "supported_or_qi_moving_not_scattered_by_clash_alone"
        ):
            labels.append("有气或旺相，冲本身不判散；独立克制仍另审")
        elif (
            row["scatter_status"]
            == "weak_or_pending_moving_scatter_not_automatically_decided"
        ):
            labels.append("衰动或气未决，不能因冲即判散")
        if row["back_clash"]:
            labels.append(
                "本位回头冲兼克"
                if row["back_control"]
                else "本位回头冲而不克；不自动作回头克"
            )
        condition_lines.append(
            f"第{row['position']}爻{row['branch']}冲的条件：" + "；".join(labels)
        )
    condition_lines.append(clash["scope"])
    progress_states = {
        "advance_supported_now": "已列旺相条件支持乘势而进",
        "advance_waits_for_strength": "待旺相条件，不作即时进",
        "advance_waits_for_void_break_relief": "本变有空破，待填实条件",
        "retreat_held_for_near_event": "近事有扶，按已列条件不退",
        "retreat_weak_now": "已列休囚条件匹配退神，不等于向外作用归零",
        "retreat_waits_for_weakness": "有旺相，待休囚条件",
        "retreat_waits_for_void_break_relief": "本变有空破，待填实条件",
        "requires_event_horizon": "须明确近事或久远，暂不判当下退",
        "requires_strength_resolution": "旺衰条件未决，暂不判当下进退",
    }
    for row in conditional["lines"]:
        progress = row.get("progress_conditions")
        if progress:
            condition_lines.append(
                f"第{row['position']}爻{progress['structural_pair']}配对："
                + progress_states[progress["state"]]
            )
            condition_lines.append(progress["scope"])
    harmony = conditional["three_harmony"]
    harmony_statuses = {
        "formation_requires_activity_resolution": "局的活动前提待审，不能据候选认定成局",
        "static_three_branches_only": "静三支，未按成局处理",
        "single_active_text_requires_review": "一动成局的其余条件须复核原文",
        "awaiting_missing_branch": "两支待补",
        "day_month_completion_candidate": "日月补支候选，效力待审",
        "awaiting_fill_or_tomb_review": "支齐，尚有空破墓待审",
        "formation_conditions_matched": "所列成局条件匹配，强弱效力待审",
        "completed_by_scoped_changed_path": "已有指定爻位动变补支路径",
        "changed_completion_requires_fill_or_review": "已有动变补支路径，空破墓仍待审",
    }
    for candidate in harmony["candidates"]:
        members = "、".join(
            f"{m['position']}爻{'变支' if m['location'] == 'changed' else '本支'}{m['branch']}"
            for m in candidate["members"]
        )
        condition_lines.append(
            f"三合{candidate['element']}局候选：{members}；"
            + harmony_statuses[candidate["status"]]
            + (
                "；" + "、".join(o["condition"] for o in candidate["obstructions"])
                if candidate["obstructions"]
                else ""
            )
        )
    if harmony["candidates"]:
        condition_lines.append(harmony["scope"])
    for hidden in conditional["hidden_conditions"]:
        condition_lines.append(
            f"第{hidden['position']}爻伏神{hidden['branch']}，飞神{hidden['flying_branch']}"
        )
        for key, label in (
            ("supporting_conditions", "支持关系"),
            ("obstructing_conditions", "阻碍关系"),
        ):
            matched = [
                c["condition"]
                for c in hidden[key]
                if c.get("qualified_matched", c["matched"]) is True
            ]
            pending = [
                c["condition"]
                for c in hidden[key]
                if c.get("qualified_matched", c["matched"]) is None
            ]
            condition_lines.append(
                f"{label}已匹配：{'、'.join(matched) or '未见已核关系'}；"
                f"待审：{'、'.join(pending) or '无'}"
            )
        condition_lines.extend([*hidden["table_gaps"], hidden["scope"]])
        phases = hidden["stage_conditions"]
        phase_match = phases["hidden_tomb_cessation"]["condition_match"]
        condition_lines.append(
            "伏神墓绝位置关系已核，尚未认定真墓真绝。"
            if phase_match is True
            else (
                "本次所查位置不匹配伏神墓绝关系。"
                if phase_match is False
                else "伏神墓绝位置含未校项，本次条件待审。"
            )
        )
        if phases["ignored_unknown_groups"]:
            condition_lines.append(
                "飞神不构成五行克伏，该阶段缺项仅作诊断，未据此新增克伏阻碍。"
            )
        condition_lines.append(phases["scope"])
        reception = hidden["reception"]
        gate_text = (
            "所列受生引拔门槛匹配，仍未裁定最终出伏"
            if reception["condition_match"] is True
            else (
                "当前所列受生门槛不匹配，不能据生向认定已受助"
                if reception["condition_match"] is False
                else "当前受生门槛待审，不能借同位飞神的受生结果"
            )
        )
        flying_text = (
            "飞生来源资格匹配"
            if reception["flying_generation"]["condition_match"] is True
            else (
                "飞生方向或来源资格不匹配"
                if reception["flying_generation"]["condition_match"] is False
                else "飞生来源资格待审"
            )
        )
        condition_lines.append(f"伏神{hidden['branch']}：{gate_text}；{flying_text}。")
        penalty = reception["penalty"]
        if (
            penalty["day_yin_growth_applicable"]
            and penalty["condition_match"] is not False
        ):
            text = (
                "寅日不按长生或同一日生扶计入"
                if penalty["condition_match"] is True
                else "申爻活动资格待审，寅日长生生扶不能先行确认"
            )
            condition_lines.append(f"伏神巳火：{text}；刑的总作用未裁定。")
        condition_lines.append(reception["scope"])
    role_effects = conditional["role_effects"]
    for row in conditional["growth_conditions"]["lines"]:
        moving_si = row.get("moving_si")
        if moving_si is not None:
            for value, text in [
                (
                    True,
                    "已核本项遇长生资格，普通火克金方向与许可仍保留；同版生克合并效力待审，其他反制另审",
                ),
                (
                    None,
                    "独立生扶或动巳来源门槛待审；普通火克金方向与所列许可另列，生克合并效力未裁定",
                ),
                (
                    False,
                    "这些动巳来源当前门槛未匹配，不认定本项已获长生；不据此认定金爻无气",
                ),
            ]:
                positions = [
                    str(s["source_position"])
                    for s in moving_si["sources"]
                    if s["growth_condition_match"] is value
                ]
                if positions:
                    condition_lines.append(
                        f"第{row['position']}爻{row['branch']}金遇第{'、'.join(positions)}爻实际动巳：{text}。"
                    )
        own_si = row.get("own_changed_si")
        if own_si is not None:
            own_text = (
                "已核独立生扶及变支门槛，本位化巳按长生，不计同一本位巳火回头克；其他反制另审"
                if own_si["condition_match"] is True
                else "本位化巳位置已列，独立生扶或变支门槛仍待审，不能将本项认定为已克或已生"
            )
            condition_lines.append(
                f"第{row['position']}爻{row['branch']}金本位化巳：{own_text}。"
            )
        if row["element"] == "金" and row["day_branch"] == "巳":
            text = (
                (
                    "已核月令独立生扶，巳日按长生条件；其他反制另审"
                    if row["independent_month_support"] is True
                    else "已核有独立根的实际动土生扶，巳日按长生条件；其他反制另审"
                )
                if row["condition_match"] is True
                else "长生位置已列，独立旺相生扶尚待裁定，不能据位置作得生"
            )
            condition_lines.append(f"第{row['position']}爻{row['branch']}金：{text}。")
    for row in conditional["penalty_conditions"]["lines"]:
        penalty_text = penalty_explanation(row)
        if penalty_text is None:
            continue
        condition_lines.append(f"第{row['position']}爻巳火：{penalty_text}。")
    for row in conditional["cessation_conditions"]["lines"]:
        if row["element"] != "土":
            continue
        for key, label in (("day", "日支"), ("changed", "本位变支")):
            query = row[key]
            if query["position_match"] is not True:
                continue
            text = (
                "已核独立生扶且未见所列反制，本项论生不论绝；其他作用另审"
                if query["condition_match"] is False
                else "气根或反制尚待裁定，不能仅据位置判真绝"
            )
            condition_lines.append(
                f"第{row['position']}爻{row['branch']}土：{label}巳见绝位；{text}。"
            )
    routing = conditional["routing_conditions"]
    for route in routing["routes"]:
        j, y, f = route["positions"]
        location = {"visible": "明爻", "hidden": "伏神"}[route["focus_location"]]
        if route["condition_match"] is True:
            message = "所列接续相生条件匹配；直接克制是否转化及最终效力仍待全局审查"
        elif route["condition_match"] is None:
            message = "接续条件待审：" + "、".join(
                s["label"] for s in route["conditions"] if s["matched"] is None
            )
        elif route["obstructed_positions"]:
            message = "回头克阻断当前接续条件，先审解救；不能据同动自动解克"
        elif y in route["binding_positions"]:
            message = "元神受合，不能据同动自动解克"
        elif j in route["binding_positions"]:
            message = "忌神受合，不能据同动自动断接续相生"
        elif "focus_reception" in route["blocked_conditions"]:
            message = "用神月破日克无独立根，不能据路径认定已受生"
        else:
            message = "接续条件未通过：" + "、".join(
                s["label"] for s in route["conditions"] if s["matched"] is False
            )
        condition_lines.append(
            f"元忌同动路径：第{j}爻忌神→第{y}爻元神→第{f}爻{location}用神；" + message
        )
    if routing["routes"]:
        condition_lines.append(routing["scope"])
    if role_effects["lines"]:
        condition_lines.append(role_effects["scope"])
        condition_lines.append(
            "第53页五字异文保留；墓法按同版第100、127页三种定义处理。"
        )
    assessed_focus = conditional["classical_assessment"]["focus"]
    if assessed_focus:
        strength_names = {
            "day_broken_unsupported": "静爻日破条件匹配，未见已列独立生扶",
            "supported_unopposed": "有根生扶，未见已列反制",
            "harmed_unsupported": "休囚受克，未见已列生扶",
            "contested_or_pending": "扶克并见或来源效力待审",
            "unresolved_no_grounded_support": "尚无充分裁定依据",
        }
        condition_lines.append(
            f"第{assessed_focus['position']}爻原典生扶裁定："
            + strength_names[assessed_focus["strength"]["status"]]
        )
        for tomb in assessed_focus["tombs"]:
            location = {"day": "日墓", "moving": "动墓", "changed": "本位化墓"}[
                tomb["location"]
            ]
            verdict = (
                "原典真墓条件匹配"
                if tomb["is_true_tomb"] is True
                else (
                    "当前不作真墓" if tomb["is_true_tomb"] is False else "真墓效力待审"
                )
            )
            condition_lines.append(
                f"{location}{tomb['branch']}：{verdict}；不据此断现实吉凶"
            )
    timing = conditional["timing_candidates"]
    condition_lines.extend([f"日级候选状态：{timing['status']}", conditional["scope"]])
    if timing.get("scope"):
        condition_lines.append(timing["scope"])
    for window in timing["windows"]:
        if civil := window.get("civil_interval"):
            condition_lines.append(
                f"日柱标签{window['effective_date']}（{window['day_ganzhi']}）"
                f"实际UTC分段{civil['interval_index']}/{civil['interval_count']}："
                f"{civil['start_utc']}至{civil['end_utc']}，"
                f"时长{civil['duration_seconds']:g}秒；"
                + "、".join(window["matched_rules"])
            )
            condition_lines.append(civil["scope"])
    for excluded in timing.get("calendar_exclusions", []):
        condition_lines.append(
            f"日柱标签{excluded['effective_date']}（{excluded['day_ganzhi']}）"
            "的钟面区间没有实际UTC时刻，不输出候选窗口。"
        )
    void_conditions = conditional["void_conditions"]
    void_focus = void_conditions["focus"]
    if void_focus:
        label = (
            "伏神"
            if void_focus["location"] == "hidden"
            else f"第{void_focus['position']}爻"
        )
        vacancy = "原旬旬空" if void_focus["is_xunkong"] else "原支不在旬空"
        condition_lines.append(
            f"{label}{void_focus['branch']}：{vacancy}；空亡条件状态{void_focus['classification']}"
        )
        if void_focus["changed_is_xunkong"] is not None:
            condition_lines.append(
                "本位变支"
                + ("在旬空" if void_focus["changed_is_xunkong"] else "不在旬空")
            )
        condition_lines.append(void_conditions["scope"])
    obstructed = [
        r["position"]
        for r in conditional["lines"]
        if r.get("outgoing_obstructions")
        and (
            conditional["growth_conditions"]["lines"][r["position"] - 1]
            .get("own_changed_si", {})
            .get("condition_match", False)
            is not None
        )
    ]
    if obstructed:
        condition_lines.append(
            f"回头克受阻爻位：{obstructed}；未按可用的向外生扶计入，解救效力仍待审"
        )
    fanfu = evidence["fanfu"]
    if fanfu["explicit_body_example"]:
        condition_lines.append(
            "底本明列卦体"
            + fanfu["explicit_body_example"]["kind"]
            + "；不由动爻支冲推得"
        )
    for region in fanfu["regions"]:
        if region["nazhi_relation"] in ("反吟", "伏吟"):
            label = "内卦" if region["region"] == "inner" else "外卦"
            condition_lines.append(
                label + "纳支" + region["nazhi_relation"] + "结构；静爻位置仅作卦盘比较"
            )
    condition_lines.append(fanfu["scope"])

    return _render_snapshot_text(
        [
            (
                "起盘信息",
                _join_lines(
                    [
                        f"日期：{input_normalized['date']} {input_normalized['time']}",
                        f"时区：{input_normalized['zone']}",
                        f"经纬度：{input_normalized['lon'] if input_normalized.get('lon') is not None else '无'} {input_normalized['lat'] if input_normalized.get('lat') is not None else '无'}",
                        f"起卦时间：{nongli.get('birth', '无')}",
                        f"干支：年{nongli.get('yearJieqi', '无')} 月{nongli.get('monthGanZi', '无')} 日{nongli.get('dayGanZi', '无')} 时{nongli.get('time', '无')}",
                    ]
                ),
            ),
            (
                "卦象",
                _join_lines(
                    [
                        f"本卦：{current_payload.get('name', input_normalized['gua_code'])}",
                        f"之卦：{changed_payload.get('name', input_normalized['changed_code'])}",
                    ]
                ),
            ),
            ("六爻与动爻", _join_lines(line_texts) or "暂无爻线数据"),
            ("卦辞与断语", _join_lines(judge_lines) or "无"),
            (
                "原典动爻",
                _join_lines(
                    [
                        *[
                            f"{v['label']}：{v['text']}"
                            for v in text_evidence["moving_yaoci"]
                        ],
                        f"原文来源：{text_evidence['base_source_url']}",
                        text_evidence["scope"],
                    ]
                ),
            ),
            (
                "专业关系依据",
                _join_lines(
                    [
                        f"月建：{evidence['calendar_conventions']['month_branch']}；日辰：{evidence['calendar_conventions']['day_ganzhi']}；旬空：{''.join(evidence['calendar_conventions']['xunkong'])}",
                        evidence["conformance_scope"],
                        "空破冲合只是结构事实，须结合用神旺衰与动静条件解读。",
                        evidence["prediction_validation"]["scope"],
                    ]
                ),
            ),
            ("取用与条件证据", _join_lines(condition_lines)),
        ]
    )


def build_sixyao_result(
    *,
    date: str,
    time: str,
    zone: Optional[str] = None,
    lat: Any = None,
    lon: Any = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
    question: Optional[str] = None,
    gua_code: Optional[str] = None,
    changed_code: Optional[str] = None,
    lines: Optional[List[Dict[str, Any]]] = None,
    method: str = "auto",
    coins: Optional[List[int]] = None,
    seed: Optional[int] = None,
    focus_line: Optional[int] = None,
    focus_kinship: Optional[str] = None,
    focus_kind: Optional[str] = None,
    timing_days: int = 0,
    event_horizon: Optional[str] = None,
) -> Dict[str, Any]:
    if event_horizon not in (None, "near", "long_term"):
        raise ValueError("event_horizon 必须是 near、long_term 或省略。")
    method = (method or "auto").strip().lower()
    if method not in {"auto", "coin", "time"}:
        raise ValueError("method 必须是 auto、coin 或 time。")
    if (
        timing_days
        and focus_line is None
        and focus_kinship is None
        and focus_kind is None
    ):
        raise ValueError("展开日级候选需要先明确focus_line或focus_kinship")

    context = _build_context(date_text=date, time_text=time, timezone_name=zone)
    normalized_lines = _normalize_gua_lines(lines)
    explicit_lines_provided = bool(normalized_lines)
    explicit_code_provided = bool(_clean_code(gua_code) or _clean_code(changed_code))
    if (
        changed_code is not None
        and gua_code is None
        and not normalized_lines
        and coins is None
    ):
        raise ValueError("changed_code 需要同时提供本卦 gua_code 或完整 lines/coins")
    if normalized_lines:
        if gua_code is not None and gua_code != _derive_gua_code(normalized_lines):
            raise ValueError("gua_code 与 lines 本卦不一致")
        if changed_code is not None and changed_code != _derive_changed_code(
            normalized_lines
        ):
            raise ValueError("changed_code 与 lines 动爻不一致")

    coin_source: Optional[str] = None
    coin_tosses: Optional[List[Dict[str, Any]]] = None

    if coins is not None:
        # 摇钱起卦（用户提供六掷）：调用方报来真实摇出的铜钱结果。
        cast_method = "coin"
        coin_source = "provided"
        coin_lines, coin_tosses = _coin_lines_and_meta(coins)
        coin_current, coin_changed = (
            _derive_gua_code(coin_lines),
            _derive_changed_code(coin_lines),
        )
        if (gua_code is not None and gua_code != coin_current) or (
            changed_code is not None and changed_code != coin_changed
        ):
            raise ValueError("coins 与所提供卦码不一致")
        if normalized_lines and (
            _derive_gua_code(normalized_lines),
            _derive_changed_code(normalized_lines),
        ) != (coin_current, coin_changed):
            raise ValueError("coins 与 lines 不一致")
        normalized_lines = coin_lines
        current_code = _derive_gua_code(normalized_lines)
        next_code = _derive_changed_code(normalized_lines)
    elif explicit_lines_provided or explicit_code_provided:
        # 手动起卦：调用方已指定卦码 / 爻线。
        cast_method = "manual"
        current_code = _clean_code(gua_code) or _derive_gua_code(normalized_lines)
        next_code = (
            _clean_code(changed_code)
            or (_derive_changed_code(normalized_lines) if normalized_lines else "")
            or current_code
        )
        if len(current_code) != 6 or len(next_code) != 6:
            raise ValueError("六爻卦码必须是 6 位 0/1 字符串。")
        # When the caller supplied codes but no explicit lines, derive the
        # canonical line set from the authoritative codes so moving-line
        # detection reflects the real request.
        if not explicit_lines_provided:
            normalized_lines = _lines_from_codes(current_code, next_code)
    elif needs_random_coin_cast(
        {
            "method": method,
            "coins": coins,
            "lines": lines,
            "gua_code": gua_code,
            "changed_code": changed_code,
        }
    ):
        # 摇钱起卦（系统随机六掷）：真·铜钱筮法，seed 可复现。
        cast_method = "coin"
        coin_source = "random"
        normalized_lines, coin_tosses = _coin_lines_and_meta(
            _random_coin_tosses(random.Random(seed))
        )
        current_code = _derive_gua_code(normalized_lines)
        next_code = _derive_changed_code(normalized_lines)
    else:
        # 时间起卦（method=auto/time）：按起卦时刻以梅花口径真实装卦
        # （本卦 / 动爻 / 变卦取自同一时刻的农历上下文），而不是返回固定演示卦。
        cast_method = "time_meihua"
        meihua = (context.get("lunar") or {}).get("meihua")
        if not meihua:
            raise ValueError(
                "六爻需先起卦：当前环境缺少农历上下文，无法做时间起卦，"
                "请改为提供 coins/gua_code/changed_code 或 lines。"
            )
        current_code = _clean_code(meihua["base_hexagram"]["binary_code"])
        next_code = _clean_code(meihua["changed_hexagram"]["binary_code"])
        if len(current_code) != 6 or len(next_code) != 6:
            raise ValueError("六爻卦码必须是 6 位 0/1 字符串。")
        normalized_lines = _lines_from_codes(current_code, next_code)

    input_normalized = {
        "date": _normalize_date_text(date),
        "time": _normalize_time_text(time),
        "zone": zone or DEFAULT_BIRTH_TIMEZONE,
        "lat": lat,
        "lon": lon,
        "gpsLat": gps_lat,
        "gpsLon": gps_lon,
        "question": question,
        "gua_code": current_code,
        "changed_code": next_code,
        "focus_line": focus_line,
        "focus_kinship": focus_kinship,
        "focus_kind": focus_kind,
        "timing_days": timing_days,
        "event_horizon": event_horizon,
    }
    current_payload = _hexagram_desc_payload(current_code)
    changed_payload = _hexagram_desc_payload(next_code)
    descriptions = {
        current_code: current_payload,
        next_code: changed_payload,
    }

    # 按起卦日干 + 卦码排纳甲、世应、六亲、六神，并写回每爻。
    day_ganzhi = context.get("nongli", {}).get("dayGanZi") or ""
    day_gan = day_ganzhi[0] if day_ganzhi else None
    hexagram_info, enrichment = _build_sixyao_enrichment(
        current_code=current_code, changed_code=next_code, day_gan=day_gan
    )
    for line_dict, extra in zip(normalized_lines, enrichment):
        # 六神与 SIX_YAO_GODS 的固定位置不同——按日干重算 god。
        line_dict["god"] = extra["liushen"]
        line_dict["name"] = extra["position_label"]
        line_dict["position"] = extra["position"]
        line_dict["branch"] = extra["branch"]
        line_dict["element"] = extra["element"]
        line_dict["liuqin"] = extra["liuqin"]
        line_dict["liushen"] = extra["liushen"]
        line_dict["shi_ying"] = extra["shi_ying"]
        if line_dict["change"] and extra["changed_branch"]:
            line_dict["changed_branch"] = extra["changed_branch"]
            line_dict["changed_liuqin"] = extra["changed_liuqin"]
        elif line_dict.get("change"):
            # 动爻但变后地支与原支相同——标记为伏吟位的提示
            line_dict["changed_branch"] = extra["branch"]
            line_dict["changed_liuqin"] = extra["liuqin"]
            line_dict["is_fuyin_line"] = True

    # Only missing kinship categories are candidates for 伏神, located at the
    # same position of the original palace's pure hexagram.
    palace_base = next(
        code
        for palace, code, _ in _BAGONG_BASES
        if palace == hexagram_info["current_palace"]
    )
    _, palace_lines = _build_sixyao_enrichment(palace_base, palace_base, day_gan)
    present_kin = {line["liuqin"] for line in normalized_lines} | {
        line["changed_liuqin"] for line in normalized_lines if line["change"]
    }
    hidden = [
        {
            "position": row["position"],
            "branch": row["branch"],
            "element": row["element"],
            "liuqin": row["liuqin"],
            "flying_branch": normalized_lines[i]["branch"],
            "flying_liuqin": normalized_lines[i]["liuqin"],
        }
        for i, row in enumerate(palace_lines)
        if row["liuqin"] not in present_kin
    ]
    evidence = build_liuyao_evidence(
        day_ganzhi=day_ganzhi,
        month_branch=context["pillars"]["month"][1],
        current_code=current_code,
        changed_code=next_code,
        lines=normalized_lines,
        hidden=hidden,
        palace_element=hexagram_info["current_palace_element"],
        moment=context["moment"],
        focus_line=focus_line,
        focus_kinship=focus_kinship,
        focus_kind=focus_kind,
        timing_days=timing_days,
        event_horizon=event_horizon,
    )
    from ..liuyao_calendar_models import month_model_comparison

    comparison = month_model_comparison(
        context["moment"],
        context["timezone_name"],
        context["calendar_context"]["bazi_month_boundary"],
    )
    if comparison is not None:
        evidence["calendar_conventions"]["month_model_comparison"] = comparison
    from ..liuyao_fanfu import build_fanfu_evidence

    # The full changed chart is a structural comparison. It must never
    # populate changed_branch on an original static line.
    _, changed_chart = _build_sixyao_enrichment(next_code, next_code, day_gan)
    evidence["fanfu"] = build_fanfu_evidence(
        current_code=current_code,
        changed_code=next_code,
        base_branches=[r["branch"] for r in normalized_lines],
        changed_chart_branches=[r["branch"] for r in changed_chart],
    )
    evidence["rule_trace"].append(
        {
            "rule_id": "separate_body_region_and_active_line_fanfu",
            "fact_path": "liuyao_evidence.fanfu",
            "inputs": {"current_code": current_code, "changed_code": next_code},
            "sources": [evidence["fanfu"]["source_url"]],
        }
    )
    text_evidence = moving_text_evidence(current_code, next_code)
    evidence["rule_trace"].append(
        {
            "rule_id": "actual_moving_classical_text",
            "fact_path": "classical_text_evidence",
            "inputs": {"current_code": current_code, "changed_code": next_code},
            "sources": [
                text_evidence["base_source_url"],
                text_evidence["changed_source_url"],
            ],
        }
    )

    snapshot_text = _build_sixyao_snapshot_text(
        input_normalized=input_normalized,
        nongli=context["nongli"],
        current_payload=current_payload,
        changed_payload=changed_payload,
        lines=normalized_lines,
        evidence=evidence,
        text_evidence=text_evidence,
    )

    moving_lines = [
        index + 1 for index, line in enumerate(normalized_lines) if line.get("change")
    ]
    moving_indices = [
        i for i, line in enumerate(normalized_lines) if line.get("change")
    ]
    current_branches = [line.get("branch", "") for line in normalized_lines]
    changed_branches = [
        line.get("changed_branch") or line.get("branch", "")
        for line in normalized_lines
    ]
    pattern_info = _detect_sixyao_patterns(
        current_code=current_code,
        changed_code=next_code,
        current_branches=current_branches,
        changed_branches=changed_branches,
        moving_indices=moving_indices,
        fanfu=evidence["fanfu"],
    )
    _cast_sources = {
        "time_meihua": "梅花时间起卦（按起卦时刻装卦）",
        "coin_provided": "三枚铜钱摇卦（用户提供六掷）",
        "coin_random": "三枚铜钱摇卦（系统随机六掷）",
        "manual": "调用方指定卦码 / 爻线",
    }
    cast_info: Dict[str, Any] = {
        "method": cast_method,
        "source": _cast_sources[
            f"coin_{coin_source}" if cast_method == "coin" else cast_method
        ],
    }
    if cast_method == "coin":
        cast_info["coin_source"] = coin_source
        cast_info["tosses"] = coin_tosses
    elif cast_method == "time_meihua":
        cast_info["time_ruleset"] = {
            "ruleset_id": "meihua_lunar_time_v1",
            "year_boundary": "lunar_new_year",
            "seed": context["lunar"]["meihua"]["seed"],
            "source_url": "https://zh.wikisource.org/wiki/梅花易數/卷一",
        }
    return {
        "analysis_type": "六爻 / 易卦",
        "input_normalized": input_normalized,
        "nongli": context["nongli"],
        "calendar_context": context["calendar_context"],
        "liuyao_evidence": evidence,
        "classical_text_evidence": text_evidence,
        "current_code": current_code,
        "changed_code": next_code,
        "cast": cast_info,
        "lines": normalized_lines,
        "moving_lines": moving_lines,
        "hexagram_info": hexagram_info,
        "patterns": pattern_info["patterns"],
        "pattern_flags": {
            "liuchong_base": pattern_info["is_liuchong_base"],
            "liuhe_base": pattern_info["is_liuhe_base"],
            "liuchong_changed": pattern_info["is_liuchong_changed"],
            "liuhe_changed": pattern_info["is_liuhe_changed"],
        },
        "question": question,
        "descriptions": descriptions,
        "current_hexagram": current_payload["raw"],
        "changed_hexagram": changed_payload["raw"],
        "snapshot_text": snapshot_text,
        "summary": f"本卦{current_payload['name']}（{current_code}），之卦{changed_payload['name']}（{next_code}），动爻{moving_lines or '无'}。已装世应、六亲、六神并列日月关系与原典动爻；尚未据用神旺衰断现实成败。",
    }
