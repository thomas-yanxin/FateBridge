"""
Shared primitives for the FateBridge metaphysics package.

Sexagenary-cycle / five-element / xun-kongwang tables and the leaf helpers that
every technique module (zi wei, liu ren, qi men, tai yi, jin kou) builds on,
plus the ``MetaphysicsSeed`` input record. Kept free of any single technique's
logic so domain modules can import from here without cycling back through the
package facade (``metaphysics/__init__.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ...utils.data import (
    BRANCH_COMBINATIONS,
    BRANCH_CONFLICTS,
    BRANCH_ELEMENTS,
    BRANCH_HARMS,
    EARTHLY_BRANCHES,
    HEAVENLY_STEMS,
    STEM_ELEMENTS,
)

SEXAGENARY_CYCLE = [
    f"{HEAVENLY_STEMS[index % 10]}{EARTHLY_BRANCHES[index % 12]}" for index in range(60)
]
SEXAGENARY_INDEX = {value: index for index, value in enumerate(SEXAGENARY_CYCLE)}

ELEMENT_GENERATES = {
    "木": "火",
    "火": "土",
    "土": "金",
    "金": "水",
    "水": "木",
}

ELEMENT_CONTROLS = {
    "木": "土",
    "火": "金",
    "土": "水",
    "金": "木",
    "水": "火",
}

XUN_HEADS = ("甲子", "甲戌", "甲申", "甲午", "甲辰", "甲寅")
KONGWANG_BY_XUN_HEAD = {
    "甲子": "戌亥空",
    "甲戌": "申酉空",
    "甲申": "午未空",
    "甲午": "辰巳空",
    "甲辰": "寅卯空",
    "甲寅": "子丑空",
}

SIX_HARMONY_BRANCHES = BRANCH_COMBINATIONS

SIX_CLASH_BRANCHES = BRANCH_CONFLICTS

SIX_HARM_BRANCHES = BRANCH_HARMS

# 大六壬 月将（神后…）与昼夜贵人/贵人顺序——金口诀与太乙也复用，故归 common。
YUE_JIANG_NAMES = {
    "子": "神后",
    "丑": "大吉",
    "寅": "功曹",
    "卯": "太冲",
    "辰": "天罡",
    "巳": "太乙",
    "午": "胜光",
    "未": "小吉",
    "申": "传送",
    "酉": "从魁",
    "戌": "河魁",
    "亥": "登明",
}


LIURENG_GUIREN_DAY = {
    "甲": "丑",
    "乙": "子",
    "丙": "亥",
    "丁": "亥",
    "戊": "丑",
    "己": "子",
    "庚": "丑",
    "辛": "午",
    "壬": "巳",
    "癸": "巳",
}


LIURENG_GUIREN_NIGHT = {
    "甲": "未",
    "乙": "申",
    "丙": "酉",
    "丁": "酉",
    "戊": "未",
    "己": "申",
    "庚": "未",
    "辛": "寅",
    "壬": "卯",
    "癸": "卯",
}


GUI_REN_REVERSED_STARTS = {"巳", "午", "未", "申", "酉"}


GUI_REN_SEQUENCE = [
    "贵人",
    "螣蛇",
    "朱雀",
    "六合",
    "勾陈",
    "青龙",
    "天空",
    "白虎",
    "太常",
    "玄武",
    "太阴",
    "天后",
]


@dataclass(frozen=True)
class MetaphysicsSeed:
    input_datetime: datetime
    corrected_datetime: datetime
    timezone: str
    longitude: Optional[float]
    applied_true_solar: bool
    total_correction_minutes: float
    pillars: Dict[str, Tuple[str, str]]
    calendar_context: Dict[str, Any]
    birth_time_normalization: Optional[Dict[str, Any]] = None
    solar_time_adjustment: Optional[Dict[str, Any]] = None


def require_lunar_month_day(
    seed: "MetaphysicsSeed", technique: str
) -> Tuple[Dict[str, Any], int, int]:
    """Return ``(lunar_context, lunar_month, lunar_day)`` or raise loudly.

    紫微 / 太乙 等技法以农历月日定盘。当离线农历换算不可用时
    (公历超出 1900–2100 支持区间，或缺少 lunardate)，``lunar_calendar``
    为 None，旧代码用 ``int(lunar.get("month") or 1)`` 静默回退到正月初一，
    算出一张看似正常却整体错位的盘。这里改为显式拒绝并透传原因，让调用方
    的 ``handle_calculation_error`` 返回 400 而不是悄悄给出错误结果。
    """
    lunar = seed.calendar_context.get("lunar_calendar")
    if not lunar or lunar.get("month") is None or lunar.get("day") is None:
        support = seed.calendar_context.get("lunar_calendar_support") or {}
        reason = support.get("reason") or "离线农历换算不可用"
        raise ValueError(f"{technique}需要农历月日，无法起盘：{reason}")
    return lunar, int(lunar["month"]), int(lunar["day"])


def rotate_sequence(
    values: Iterable[str], start_value: str, reverse: bool = False
) -> List[str]:
    ordered = list(values)
    if not ordered:
        return []
    if reverse:
        ordered = list(reversed(ordered))
    if start_value not in ordered:
        return ordered
    start_index = ordered.index(start_value)
    return ordered[start_index:] + ordered[:start_index]


def stem_element_text(stem: str) -> str:
    return STEM_ELEMENTS[stem][0].value


def branch_element_text(branch: str) -> str:
    return BRANCH_ELEMENTS[branch][0].value


def ganzhi_text(pillar: Tuple[str, str]) -> str:
    return f"{pillar[0]}{pillar[1]}"


def sexagenary_index_for(text: str) -> int:
    return SEXAGENARY_INDEX[text]


def sexagenary_text(index: int) -> str:
    return SEXAGENARY_CYCLE[index % 60]


def xun_head_for_ganzhi(text: str) -> str:
    cycle_index = sexagenary_index_for(text)
    return XUN_HEADS[cycle_index // 10]


def kongwang_for_ganzhi(text: str) -> str:
    return KONGWANG_BY_XUN_HEAD[xun_head_for_ganzhi(text)]


def liuqin_against_day(day_element: str, target_element: str) -> str:
    if day_element == target_element:
        return "兄弟"
    if ELEMENT_GENERATES[day_element] == target_element:
        return "子孙"
    if ELEMENT_GENERATES[target_element] == day_element:
        return "父母"
    if ELEMENT_CONTROLS[day_element] == target_element:
        return "妻财"
    if ELEMENT_CONTROLS[target_element] == day_element:
        return "官鬼"
    return "比和"


def status_against_anchor(anchor: str, target: str) -> str:
    if anchor == target:
        return "旺"
    if ELEMENT_GENERATES[anchor] == target:
        return "相"
    if ELEMENT_GENERATES[target] == anchor:
        return "休"
    if ELEMENT_CONTROLS[anchor] == target:
        return "死"
    return "囚"


def chinese_numeral(value: int) -> str:
    mapping = "零一二三四五六七八九"
    if value < 10:
        return mapping[value]
    if value < 20:
        suffix = "" if value == 10 else mapping[value % 10]
        return f"十{suffix}"
    tens = value // 10
    ones = value % 10
    if ones == 0:
        return f"{mapping[tens]}十"
    return f"{mapping[tens]}十{mapping[ones]}"
