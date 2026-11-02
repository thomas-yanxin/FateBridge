"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from ...utils.data import EARTHLY_BRANCHES
from .common import (
    GUI_REN_SEQUENCE,
    LIURENG_GUIREN_DAY,
    LIURENG_GUIREN_NIGHT,
    rotate_sequence,
)
from .ren_diurnal import resolve_diurnal

GUISHEN_IDENTITIES = dict(
    zip(
        GUI_REN_SEQUENCE,
        (
            "己丑",
            "丁巳",
            "丙午",
            "乙卯",
            "戊辰",
            "甲寅",
            "戊戌",
            "庚申",
            "己未",
            "壬子",
            "辛酉",
            "癸亥",
        ),
    )
)


def _build_guishen_mapping(
    day_stem: str, hour_branch: str, is_diurnal_override: Optional[bool] = None
) -> Tuple[str, Dict[str, str]]:
    is_day = resolve_diurnal(hour_branch, is_diurnal_override)["is_diurnal"]
    start = (LIURENG_GUIREN_DAY if is_day else LIURENG_GUIREN_NIGHT)[day_stem]
    # Place 贵 on the day/night start, count directly to 地分, not via 天盘.
    branches = rotate_sequence(EARTHLY_BRANCHES, start, reverse=start in "巳午未申酉戌")
    return start, dict(zip(branches, GUI_REN_SEQUENCE))
