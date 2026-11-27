"""Fixed reference frame: 8 directions, LuoShu, 24 mountains, KongWang, and interval support."""

from __future__ import annotations

import json
from bisect import bisect_right
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

_KONGWANG_SEAM_HALF_WIDTH = 0.5
_ZHENGXIANG_HALF_WIDTH = 1.5
_JIANXIANG_LOWER_HALF_WIDTH = 4.5
_DIRECTION_BOUNDARIES = [22.5 + 45 * i for i in range(8)]
_MOUNTAIN_BOUNDARIES = [7.5 + 15 * i for i in range(24)]

# 24 mountains in clockwise order starting at 0° (子 center), with 3-yuan & polarity.
MOUNTAINS_24: tuple[dict[str, Any], ...] = (
    {
        "name": "子",
        "center_degrees": 0,
        "direction": "N",
        "yuan": "heaven",
        "polarity": "yin",
    },
    {
        "name": "癸",
        "center_degrees": 15,
        "direction": "N",
        "yuan": "human",
        "polarity": "yin",
    },
    {
        "name": "丑",
        "center_degrees": 30,
        "direction": "NE",
        "yuan": "earth",
        "polarity": "yin",
    },
    {
        "name": "艮",
        "center_degrees": 45,
        "direction": "NE",
        "yuan": "heaven",
        "polarity": "yang",
    },
    {
        "name": "寅",
        "center_degrees": 60,
        "direction": "NE",
        "yuan": "human",
        "polarity": "yang",
    },
    {
        "name": "甲",
        "center_degrees": 75,
        "direction": "E",
        "yuan": "earth",
        "polarity": "yang",
    },
    {
        "name": "卯",
        "center_degrees": 90,
        "direction": "E",
        "yuan": "heaven",
        "polarity": "yin",
    },
    {
        "name": "乙",
        "center_degrees": 105,
        "direction": "E",
        "yuan": "human",
        "polarity": "yin",
    },
    {
        "name": "辰",
        "center_degrees": 120,
        "direction": "SE",
        "yuan": "earth",
        "polarity": "yin",
    },
    {
        "name": "巽",
        "center_degrees": 135,
        "direction": "SE",
        "yuan": "heaven",
        "polarity": "yang",
    },
    {
        "name": "巳",
        "center_degrees": 150,
        "direction": "SE",
        "yuan": "human",
        "polarity": "yang",
    },
    {
        "name": "丙",
        "center_degrees": 165,
        "direction": "S",
        "yuan": "earth",
        "polarity": "yang",
    },
    {
        "name": "午",
        "center_degrees": 180,
        "direction": "S",
        "yuan": "heaven",
        "polarity": "yin",
    },
    {
        "name": "丁",
        "center_degrees": 195,
        "direction": "S",
        "yuan": "human",
        "polarity": "yin",
    },
    {
        "name": "未",
        "center_degrees": 210,
        "direction": "SW",
        "yuan": "earth",
        "polarity": "yin",
    },
    {
        "name": "坤",
        "center_degrees": 225,
        "direction": "SW",
        "yuan": "heaven",
        "polarity": "yang",
    },
    {
        "name": "申",
        "center_degrees": 240,
        "direction": "SW",
        "yuan": "human",
        "polarity": "yang",
    },
    {
        "name": "庚",
        "center_degrees": 255,
        "direction": "W",
        "yuan": "earth",
        "polarity": "yang",
    },
    {
        "name": "酉",
        "center_degrees": 270,
        "direction": "W",
        "yuan": "heaven",
        "polarity": "yin",
    },
    {
        "name": "辛",
        "center_degrees": 285,
        "direction": "W",
        "yuan": "human",
        "polarity": "yin",
    },
    {
        "name": "戌",
        "center_degrees": 300,
        "direction": "NW",
        "yuan": "earth",
        "polarity": "yin",
    },
    {
        "name": "乾",
        "center_degrees": 315,
        "direction": "NW",
        "yuan": "heaven",
        "polarity": "yang",
    },
    {
        "name": "亥",
        "center_degrees": 330,
        "direction": "NW",
        "yuan": "human",
        "polarity": "yang",
    },
    {
        "name": "壬",
        "center_degrees": 345,
        "direction": "N",
        "yuan": "earth",
        "polarity": "yang",
    },
)
MOUNTAIN_BY_NAME: dict[str, dict[str, Any]] = {m["name"]: m for m in MOUNTAINS_24}


@lru_cache(maxsize=1)
def _bundle() -> dict[str, Any]:
    path = Path(__file__).parents[2] / "data" / "fengshui" / "rules-v1.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def raw_rule_data(key: str) -> Any:
    """Read-only cached lookup into rules-v1.json without deep-copy overhead."""
    return _bundle()[key]


def rule_data(key: str) -> Any:
    """Return a shallow copy of top-level mappings/lists from rules-v1.json."""
    val = _bundle()[key]
    if isinstance(val, dict):
        return dict(val)
    if isinstance(val, list):
        return list(val)
    return val


def sitting_from_mountain(mountain: str) -> dict[str, Any]:
    directions = _bundle()["directions"]
    mountains = _bundle()["mountains"]
    idx = mountains.index(mountain)
    facing_info = MOUNTAIN_BY_NAME[mountain]
    sitting_name = mountains[(idx + 12) % 24]
    sitting_info = MOUNTAIN_BY_NAME[sitting_name]
    s_dir = sitting_info["direction"]
    return {
        "facing_mountain": mountain,
        "facing_direction": facing_info["direction"],
        "facing_trigram": directions[facing_info["direction"]]["trigram"],
        "mountain": sitting_name,
        "direction": s_dir,
        "trigram": directions[s_dir]["trigram"],
    }


def wrap9(number: int) -> int:
    return (number - 1) % 9 + 1


def classify_facing_band(degrees: float | Fraction) -> dict[str, Any]:
    """Classify 24-mountain sub-band (zhengxiang/jianxiang) and KongWang void seams."""
    angle = float(degrees % 360) % 360
    index = bisect_right(_MOUNTAIN_BOUNDARIES, angle) % 24
    mountain = MOUNTAINS_24[index]
    offset = (angle - mountain["center_degrees"] + 180.0) % 360.0 - 180.0
    abs_offset = abs(offset)

    if abs_offset <= _ZHENGXIANG_HALF_WIDTH:
        subband = "zhengxiang"
    elif abs_offset <= _JIANXIANG_LOWER_HALF_WIDTH:
        subband = "jianxiang_lower"
    else:
        subband = "jianxiang_replacement"

    adjacent_mountain: str | None = None
    if abs_offset > _ZHENGXIANG_HALF_WIDTH or abs_offset == 7.5:
        step = -1 if offset <= 0 else 1
        adjacent_mountain = MOUNTAINS_24[(index + step) % 24]["name"]

    kongwang: str | None = None
    seam_degrees: float | None = None
    seam_dist = 7.5 - abs_offset
    if seam_dist <= _KONGWANG_SEAM_HALF_WIDTH:
        step = -1 if offset <= 0 else 1
        neighbour = MOUNTAINS_24[(index + step) % 24]
        seam_degrees = (mountain["center_degrees"] + step * 7.5) % 360.0
        if mountain["direction"] != neighbour["direction"]:
            kongwang = "da_kongwang"
        elif mountain["polarity"] != neighbour["polarity"]:
            kongwang = "yinyang_chacuo"
        else:
            kongwang = "xiao_kongwang"
        adjacent_mountain = neighbour["name"]

    return {
        "mountain_index": index,
        "mountain": mountain,
        "offset_degrees": round(offset, 6),
        "facing_subband": subband,
        "adjacent_mountain": adjacent_mountain,
        "kongwang": kongwang,
        "kongwang_seam_degrees": seam_degrees,
    }


def bearing_context(degrees: float | Fraction, north_reference: str) -> dict[str, Any]:
    angle = degrees % 360
    directions = _bundle()["directions"]
    index = bisect_right(_DIRECTION_BOUNDARIES, angle) % 8
    direction = list(directions)[index]
    band = classify_facing_band(angle)
    return {
        "bearing_degrees": float(angle) % 360,
        "north_reference": north_reference,
        "direction": direction,
        "trigram": directions[direction]["trigram"],
        "mountain": band["mountain"]["name"],
        "facing_subband": band["facing_subband"],
        "adjacent_mountain": band["adjacent_mountain"],
        "kongwang": band["kongwang"],
        "kongwang_seam_degrees": band["kongwang_seam_degrees"],
        "boundary_policy": "left_closed_right_open",
    }


def sitting_from_facing(degrees: float, north_reference: str) -> dict[str, Any]:
    # Derive opposite sectors before adding 180 to avoid rounding edge flips.
    facing = bearing_context(degrees, north_reference)
    directions = _bundle()["directions"]
    dir_keys = list(directions)
    direction = dir_keys[(dir_keys.index(facing["direction"]) + 4) % 8]
    facing_m_idx = _bundle()["mountains"].index(facing["mountain"])
    return {
        **facing,
        "bearing_degrees": (degrees + 180) % 360,
        "direction": direction,
        "trigram": directions[direction]["trigram"],
        "mountain": _bundle()["mountains"][(facing_m_idx + 12) % 24],
    }


def sitting_support(
    degrees: float, radius: float, north_reference: str
) -> list[dict[str, Any]]:
    """Enumerate every intersecting eight-sector cell using exact input values."""
    directions_map = _bundle()["directions"]
    directions = list(directions_map)
    if radius == 0:
        sitting = sitting_from_facing(degrees, north_reference)
        return [
            {
                "sitting_direction": sitting["direction"],
                "sitting_trigram": sitting["trigram"],
                "regions": [],
            }
        ]
    center = Fraction(degrees) % 360
    lower, upper = center - Fraction(radius), center + Fraction(radius)
    found: dict[str, dict[str, Any]] = {}
    for index in range(-4, 13):
        start = max(lower, index * 45 - Fraction(45, 2))
        end = min(upper, index * 45 + Fraction(45, 2))
        if start > end:
            continue
        direction = directions[(index + 4) % 8]
        candidate = found.setdefault(
            direction,
            {
                "sitting_direction": direction,
                "sitting_trigram": directions_map[direction]["trigram"],
                "regions": [],
            },
        )
        candidate["regions"].append(
            {
                "from_facing_degrees_exact": str(start),
                "until_facing_degrees_exact": str(end),
                "endpoints_included": True,
            }
        )
    return list(found.values())
