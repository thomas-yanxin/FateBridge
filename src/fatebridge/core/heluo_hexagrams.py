"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Tuple

TRIGRAM_BITS: Dict[str, List[int]] = {
    "乾": [1, 1, 1],
    "兌": [1, 1, 0],
    "離": [1, 0, 1],
    "震": [1, 0, 0],
    "巽": [0, 1, 1],
    "坎": [0, 1, 0],
    "艮": [0, 0, 1],
    "坤": [0, 0, 0],
}


GAN: List[str] = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]


ZHI: List[str] = [
    "子",
    "丑",
    "寅",
    "卯",
    "辰",
    "巳",
    "午",
    "未",
    "申",
    "酉",
    "戌",
    "亥",
]


NATURAL: Dict[str, str] = {
    "天": "乾",
    "地": "坤",
    "水": "坎",
    "火": "離",
    "雷": "震",
    "山": "艮",
    "風": "巽",
    "澤": "兌",
}


_DATA_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "heluo" / "heluoTiaowen.json"
)


@lru_cache(maxsize=1)
def _tiaowen() -> Dict[str, Any]:
    with _DATA_PATH.open(encoding="utf-8") as handle:
        data: Dict[str, Any] = json.load(handle)
    return data


@lru_cache(maxsize=1)
def _gua_tables() -> Tuple[Dict[str, Dict[str, str]], Dict[str, str], Dict[str, int]]:
    """由条文 64 卦名解析 (上卦,下卦) ↔ 卦名 ↔ 王弗序。"""
    name_to_tri: Dict[str, Dict[str, str]] = {}
    tri_to_name: Dict[str, str] = {}
    name_index: Dict[str, int] = {}
    for name, payload in _tiaowen().items():
        if name[1] == "為":  # 纯卦 乾為天
            up = low = name[0]
        else:  # 复合 上象+下象
            up = NATURAL.get(name[0], "")
            low = NATURAL.get(name[1], "")
        if up in TRIGRAM_BITS and low in TRIGRAM_BITS:
            name_to_tri[name] = {"up": up, "low": low}
            tri_to_name[f"{up}|{low}"] = name
            name_index[name] = payload["index"]
    return name_to_tri, tri_to_name, name_index


def _gua_name(up: str, low: str) -> str:
    return _gua_tables()[1].get(f"{up}|{low}", "")


def gua_lines(up: str, low: str) -> List[int]:
    """六爻 bit（自下而上 1-6）= 下卦三爻 + 上卦三爻。"""
    return [*TRIGRAM_BITS[low], *TRIGRAM_BITS[up]]


def lines_to_gua(lines: List[int]) -> Dict[str, str]:
    low = next(
        (t for t, b in TRIGRAM_BITS.items() if all(b[i] == lines[i] for i in range(3))),
        "",
    )
    up = next(
        (
            t
            for t, b in TRIGRAM_BITS.items()
            if all(b[i] == lines[i + 3] for i in range(3))
        ),
        "",
    )
    return {"up": up, "low": low, "name": _gua_name(up, low)}


def _trigram_of(bits: List[int]) -> str:
    return next(
        (t for t, b in TRIGRAM_BITS.items() if all(b[i] == bits[i] for i in range(3))),
        "",
    )
