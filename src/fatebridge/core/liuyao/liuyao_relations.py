"""Shared Liu Yao relation primitives, independent of evidence/judgment builders.

This module relocates the existing operators without changing rule arithmetic.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
ELEMENTS = dict(zip(BRANCHES, "水土木木土火火土金金土水"))
GENERATES = dict(zip("木火土金水", "火土金水木"))
CONTROLS = dict(zip("木土水火金", "土水火金木"))
COMBINES = dict(zip("子丑寅亥卯戌辰酉巳申午未", "丑子亥寅戌卯酉辰申巳未午"))
ADVANCES = {
    "亥": "子",
    "寅": "卯",
    "巳": "午",
    "申": "酉",
    "丑": "辰",
    "辰": "未",
    "未": "戌",
}
_SOURCE_MANIFEST = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-sources.json")
    .read_text(encoding="utf-8")
)
SOURCES = {
    int(n): record["source_url"]
    for n, record in _SOURCE_MANIFEST["sources_by_chapter"].items()
}


def xunkong(day_ganzhi: str) -> list[str]:
    if (
        len(day_ganzhi) != 2
        or day_ganzhi[0] not in STEMS
        or day_ganzhi[1] not in BRANCHES
    ):
        raise ValueError("旬空需要有效的日干支")
    stem_index = STEMS.index(day_ganzhi[0])
    branch_index = BRANCHES.index(day_ganzhi[1])
    if (stem_index - branch_index) % 2:
        raise ValueError("日干支不在六十甲子中")
    start = (branch_index - stem_index + 10) % 12
    return [BRANCHES[start], BRANCHES[(start + 1) % 12]]


def element_relation(actor: str, target: str) -> str:
    if actor == target:
        return "比和"
    if GENERATES[actor] == target:
        return "生爻"
    if CONTROLS[actor] == target:
        return "克爻"
    if GENERATES[target] == actor:
        return "爻生"
    return "爻克"


def branch_facts(branch: str, month: str, day: str, void: list[str]) -> dict[str, Any]:
    return {
        "is_xunkong": branch in void,
        "is_month_clash": (BRANCHES.index(branch) - BRANCHES.index(month)) % 12 == 6,
        "is_day_clash": (BRANCHES.index(branch) - BRANCHES.index(day)) % 12 == 6,
        "is_month_combination": COMBINES[month] == branch,
        "is_day_combination": COMBINES[day] == branch,
        "is_month_branch": branch == month,
        "is_day_branch": branch == day,
        "month_element_relation": element_relation(ELEMENTS[month], ELEMENTS[branch]),
        "day_element_relation": element_relation(ELEMENTS[day], ELEMENTS[branch]),
    }
