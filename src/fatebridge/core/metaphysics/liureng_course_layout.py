"""Necessary stage/god compatibility across explicit supported noble layouts.

The alternatives do not assert the current diurnal state or select transmissions.
A compatible pair may still never be selected by a given four-lesson board.
"""

from __future__ import annotations

import copy
from typing import Any, TypedDict

from fatebridge.core.metaphysics.common import GUI_REN_SEQUENCE, rotate_sequence
from fatebridge.core.metaphysics.liureng_life_stages import life_stage_cycle
from fatebridge.core.metaphysics.ren_gods import (
    DEFAULT_GUIREN_PROFILE,
    GuirenProfile,
    noble_start,
)
from fatebridge.utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS

LIURENG_MONTH_GENERAL_BY_TERM = {
    "大寒": "子",
    "立春": "子",
    "雨水": "亥",
    "惊蛰": "亥",
    "春分": "戌",
    "清明": "戌",
    "谷雨": "酉",
    "立夏": "酉",
    "小满": "申",
    "芒种": "申",
    "夏至": "未",
    "小暑": "未",
    "大暑": "午",
    "立秋": "午",
    "处暑": "巳",
    "白露": "巳",
    "秋分": "辰",
    "寒露": "辰",
    "霜降": "卯",
    "立冬": "卯",
    "小雪": "寅",
    "大雪": "寅",
    "冬至": "丑",
    "小寒": "丑",
}


LIURENG_GUIREN_REVERSED_EARTH = frozenset("巳午未申酉戌")


def _liureng_month_general_for_term(current_term: str) -> str:
    if current_term not in LIURENG_MONTH_GENERAL_BY_TERM:
        raise ValueError(f"未知节气 {current_term!r}，不能用月建代替月将")
    return LIURENG_MONTH_GENERAL_BY_TERM[current_term]


def _liureng_month_general_on_hour(
    *,
    hour_branch: str,
    month_general_branch: str,
) -> dict[str, str]:
    earth_order = rotate_sequence(EARTHLY_BRANCHES, hour_branch)
    sky_order = rotate_sequence(EARTHLY_BRANCHES, month_general_branch)
    return {
        earth_branch: sky_order[index] for index, earth_branch in enumerate(earth_order)
    }


class TwelveGodLayout(TypedDict):
    sky_by_earth: dict[str, str]
    god_by_sky: dict[str, str]
    noble_start_branch: str
    noble_earth_branch: str
    is_reverse: bool


def twelve_god_layout(
    *,
    hour_branch: str,
    month_general_branch: str,
    day_stem: str,
    is_diurnal: bool,
    guiren_profile: GuirenProfile = DEFAULT_GUIREN_PROFILE,
) -> TwelveGodLayout:
    """Lay out supplied symbolic conditions without inventing a civil date.

    The normal board builder resolves calendar/diurnal conditions first, then
    uses this same layout. A source-conditioned replay cannot certify those
    upstream conditions or a Taiyi four-corner lodging rule.
    """
    if (
        hour_branch not in tuple(EARTHLY_BRANCHES)
        or month_general_branch not in tuple(EARTHLY_BRANCHES)
        or day_stem not in tuple(HEAVENLY_STEMS)
        or type(is_diurnal) is not bool
    ):
        raise ValueError("十二神将布置需要明确的时支、月将、日干与昼夜条件")
    start = noble_start(day_stem, is_diurnal, guiren_profile)
    sky = _liureng_month_general_on_hour(
        hour_branch=hour_branch, month_general_branch=month_general_branch
    )
    earth = next(branch for branch, upper in sky.items() if upper == start)
    reverse = earth in LIURENG_GUIREN_REVERSED_EARTH
    branches = rotate_sequence(EARTHLY_BRANCHES, start, reverse=reverse)
    return {
        "sky_by_earth": sky,
        "god_by_sky": dict(zip(branches, GUI_REN_SEQUENCE)),
        "noble_start_branch": start,
        "noble_earth_branch": earth,
        "is_reverse": reverse,
    }


PROFILES: tuple[GuirenProfile, ...] = ("liuren_common_v1", "tanyuan_xieji_v1")
BASIS = {
    "ruleset_id": "tanyuan_supported_noble_layout_necessity_v1",
    "stage_subject": "day_stem",
    "noble_profiles": ["liuren_common_v1", "tanyuan_xieji_v1"],
    "diurnal_alternatives": [False, True],
    "direction_alternatives": ["顺", "逆"],
    "conditions_are_alternatives": True,
    "is_initial_transmission_guarantee": False,
    "unresolved_authorial_intent_ids": ["S05"],
    "authorial_intent_adjudicated": None,
    "original_conditions_rewritten": False,
    "witnesses": [
        {
            "id": "zhuji_zhuji-1",
            "source_title": "毛志道《六壬经纬》",
            "edition": "清金阊书业堂刻本，诸暨图书馆藏",
            "original_pdf_pages": [31, 32, 33],
        },
        {
            "id": "zhuji_zhuji-2",
            "source_title": "毛志道《六壬经纬》",
            "edition": "清金阊书业堂刻本，诸暨图书馆藏",
            "original_pdf_pages": [37, 38, 39, 40, 41, 79, 80, 81],
        },
        {
            "id": "gugong_gugong-419",
            "source_title": "毛志道《六壬经纬》",
            "edition": "故宫珍本丛刊419所收六壬经纬，目录标雍正刊本",
            "original_pdf_pages": [10, 11, 53, 54, 55, 65, 66],
        },
    ],
    "scope": "只枚举两张声明贵人表、昼夜及顺逆的配将必要配置；候选支位集合不保证九宗取传选中，不是当前昼夜的另一次判定，也不作占事吉凶。崇位字面条件保留，原意未裁。",
}


def layout_compatibility_basis() -> dict[str, Any]:
    return copy.deepcopy(BASIS)


def pair_layout_necessity(day_stem: str, stage: str, god: str) -> dict[str, Any]:
    cycle = life_stage_cycle(day_stem)
    if stage not in cycle.values() or god not in GUI_REN_SEQUENCE:
        raise ValueError("配将必要条件需要有效十二运与天将")
    required_branch = next(b for b, s in cycle.items() if s == stage)
    rank = GUI_REN_SEQUENCE.index(god)
    candidates = set()
    for profile in PROFILES:
        for daylight in (False, True):
            start = EARTHLY_BRANCHES.index(noble_start(day_stem, daylight, profile))
            for direction in (1, -1):
                candidates.add(EARTHLY_BRANCHES[(start + direction * rank) % 12])
    return dict(
        required_stage_branch=required_branch,
        possible_god_branches=[b for b in EARTHLY_BRANCHES if b in candidates],
        compatible_in_any_supported_noble_layout=required_branch in candidates,
    )
