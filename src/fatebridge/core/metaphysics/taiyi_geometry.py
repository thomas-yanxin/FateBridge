"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

from typing import Literal, TypedDict

BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


RING = "子丑艮寅卯辰巽巳午未坤申酉戌乾亥"


PALACES = {
    1: "乾",
    2: "午",
    3: "艮",
    4: "卯",
    5: "中",
    6: "酉",
    7: "坤",
    8: "子",
    9: "巽",
}


PALACE_ORDER = (1, 8, 3, 4, 9, 2, 7, 6)


class CountStep(TypedDict):
    palace: str
    value: int
    kind: Literal["间神起算", "正宫", "本宫数"]


class CountTrace(TypedDict):
    count: int
    path: list[CountStep]
    terminal_palace: str
    terminal_excluded: bool
    counting_rule: str


def count_to_taiyi(marker: str, taiyi_number: int) -> CountTrace:
    """Count the starting intercalary spirit once, then the principal palaces before Taiyi."""
    if (
        type(marker) is not str
        or marker not in set(RING)
        or type(taiyi_number) is not int
        or taiyi_number not in PALACE_ORDER
    ):
        raise ValueError("太乙计数需要十六神及非中五的太乙宫数")
    principal = {label: number for number, label in PALACES.items() if number != 5}
    path: list[CountStep] = []
    if marker not in principal:
        path.append({"palace": marker, "value": 1, "kind": "间神起算"})
        start = (RING.index(marker) + 1) % 16
    else:
        start = RING.index(marker)
    index = start
    while RING[index] != PALACES[taiyi_number]:
        position = RING[index]
        if position in principal:
            path.append(
                {"palace": position, "value": principal[position], "kind": "正宫"}
            )
        index = (index + 1) % 16
    is_same_principal_palace = not path
    if is_same_principal_palace:
        path.append({"palace": marker, "value": taiyi_number, "kind": "本宫数"})
    return {
        "count": sum(step["value"] for step in path),
        "path": path,
        "terminal_palace": PALACES[taiyi_number],
        "terminal_excluded": not is_same_principal_palace,
        "counting_rule": "同宫取本宫数" if is_same_principal_palace else "数至太乙宫前",
    }


def general_for_count(count: int) -> int:
    """Return the palace number, including center five, from a general's count."""
    if not 1 <= count <= 40:
        raise ValueError("太乙主客算必须在1至40之间")
    else:
        return count % 10 or count // 10
