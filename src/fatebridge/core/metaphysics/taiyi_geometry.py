"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

from typing import Any, Dict, List

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


SOURCES = {
    str(n): f"https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷{n:02}"
    for n in (1, 2, 3, 6, 9)
}


def count_to_taiyi(marker: str, taiyi_number: int) -> Dict[str, Any]:
    """Count the starting intercalary spirit once, then principal palaces.

    Volume 2's example: 亥 -> 太乙巽九 = 1 + 子8 + 艮3 + 卯4 = 16.
    A principal starting palace coincident with Taiyi uses its own number,
    as in volume 3's ju 9/11/17/38/43. The terminal palace is excluded.
    """
    if (
        type(marker) is not str
        or marker not in set(RING)
        or type(taiyi_number) is not int
        or taiyi_number not in PALACE_ORDER
    ):
        raise ValueError("太乙计数需要十六神及非中五的太乙宫数")
    principal = {label: number for number, label in PALACES.items() if number != 5}
    path: List[Dict[str, Any]] = []
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
    same_principal_palace = not path
    if same_principal_palace:
        path.append({"palace": marker, "value": taiyi_number, "kind": "本宫数"})
    return {
        "count": sum(item["value"] for item in path),
        "path": path,
        "terminal_palace": PALACES[taiyi_number],
        "terminal_excluded": not same_principal_palace,
        "counting_rule": "同宫取本宫数" if same_principal_palace else "数至太乙宫前",
        "source": SOURCES["2"] + "#推太乙運式法",
    }


def general_for_count(count: int) -> int:
    """Discard tens; exact tens use their leading digit (10->1, 40->4).

    Vol. 2 explicitly gives 10->1; vol. 9 gives 40->4 and vice general 2.
    """
    if not 1 <= count <= 40:
        raise ValueError("太乙主客算必须在1至40之间")
    return count % 10 or count // 10
