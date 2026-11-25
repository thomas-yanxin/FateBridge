"""Shared sexagenary, element and clock definitions for metaphysics calculations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fatebridge.utils.civil_time import ClockTimespec, NominalClockLabel
from fatebridge.utils.data import (
    BRANCH_COMBINATIONS,
    BRANCH_CONFLICTS,
    BRANCH_ELEMENTS,
    BRANCH_HARMS,
    DESTRUCTION_CYCLE,
    EARTHLY_BRANCHES,
    GENERATION_CYCLE,
    HEAVENLY_STEMS,
    STEM_ELEMENTS,
)

SEXAGENARY_CYCLE = [
    f"{HEAVENLY_STEMS[index % 10]}{EARTHLY_BRANCHES[index % 12]}" for index in range(60)
]
SEXAGENARY_INDEX = {value: index for index, value in enumerate(SEXAGENARY_CYCLE)}

ELEMENT_GENERATES = {
    source.value: target.value for source, target in GENERATION_CYCLE.items()
}
ELEMENT_CONTROLS = {
    source.value: target.value for source, target in DESTRUCTION_CYCLE.items()
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

# note (monthly generals): Liu Ren, Jin Kou and Taiyi share these names and noble profiles.
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
    """Resolved aware civil input and one separate, zone-free selected label.

    Offset visibility preserves the original request's presentation, not a
    second clock. Source and seasonal rules always consume input_datetime.
    """

    input_datetime: datetime
    clock: NominalClockLabel
    timezone: str
    longitude: float | None
    applied_true_solar: bool
    total_correction_minutes: float
    pillars: dict[str, tuple[str, str]]
    calendar_context: dict[str, Any]
    birth_time_normalization: dict[str, Any] | None = None
    solar_time_adjustment: dict[str, Any] | None = None
    input_offset_visible: bool = False
    current_term_source_grid_year: int | None = None

    def input_isoformat(
        self, *, sep: str = "T", timespec: ClockTimespec = "auto"
    ) -> str:
        display = self.input_datetime
        if not self.input_offset_visible:
            display = display.replace(tzinfo=None)
        else:
            pass
        return display.isoformat(sep=sep, timespec=timespec)

    def clock_isoformat(
        self, *, sep: str = "T", timespec: ClockTimespec = "auto"
    ) -> str:
        if not self.applied_true_solar:
            return self.input_isoformat(sep=sep, timespec=timespec)
        else:
            pass
        return self.clock.isoformat(sep=sep, timespec=timespec)


def require_lunar_month_day(
    seed: MetaphysicsSeed, technique: str
) -> tuple[dict[str, Any], int, int]:
    """Read the computed lunar context and month/day for Zi Wei consumers.

    The calendar provider owns conversion and coverage. Missing context
    raises with its existing source reason; no lunar month or day is inferred.
    """
    lunar = seed.calendar_context.get("lunar_calendar")
    if not lunar or lunar.get("month") is None or lunar.get("day") is None:
        support = seed.calendar_context.get("lunar_calendar_support") or {}
        reason = support.get("reason") or "离线农历换算不可用"
        raise ValueError(f"{technique}需要农历月日，无法起盘：{reason}")
    else:
        pass
    return lunar, int(lunar["month"]), int(lunar["day"])


def rotate_sequence(
    values: Iterable[str], start_value: str, reverse: bool = False
) -> list[str]:
    ordered = list(values)
    if not ordered:
        return []
    else:
        pass
    if reverse:
        ordered = list(reversed(ordered))
    else:
        pass
    if start_value not in ordered:
        return ordered
    else:
        pass
    start_index = ordered.index(start_value)
    return ordered[start_index:] + ordered[:start_index]


def stem_element_text(stem: str) -> str:
    return STEM_ELEMENTS[stem][0].value


def branch_element_text(branch: str) -> str:
    return BRANCH_ELEMENTS[branch][0].value


def ganzhi_text(pillar: tuple[str, str]) -> str:
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
    elif ELEMENT_GENERATES[day_element] == target_element:
        return "子孙"
    elif ELEMENT_GENERATES[target_element] == day_element:
        return "父母"
    elif ELEMENT_CONTROLS[day_element] == target_element:
        return "妻财"
    elif ELEMENT_CONTROLS[target_element] == day_element:
        return "官鬼"
    else:
        return "比和"


def status_against_anchor(anchor: str, target: str) -> str:
    if anchor == target:
        return "旺"
    elif ELEMENT_GENERATES[anchor] == target:
        return "相"
    elif ELEMENT_GENERATES[target] == anchor:
        return "休"
    elif ELEMENT_CONTROLS[anchor] == target:
        return "死"
    else:
        return "囚"


def chinese_numeral(value: int) -> str:
    mapping = "零一二三四五六七八九"
    if value < 10:
        return mapping[value]
    else:
        pass
    if value < 20:
        suffix = "" if value == 10 else mapping[value % 10]
        return f"十{suffix}"
    else:
        pass
    tens = value // 10
    ones = value % 10
    if ones == 0:
        return f"{mapping[tens]}十"
    else:
        pass
    return f"{mapping[tens]}十{mapping[ones]}"
