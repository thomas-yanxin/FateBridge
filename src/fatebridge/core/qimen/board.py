"""Qimen palace plates (rotating and flying), lodging policies, hidden stems, and horse star."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal, TypedDict

from fatebridge.core.divination import build_hexagram
from fatebridge.core.metaphysics.common import (
    rotate_sequence,
    sexagenary_index_for,
    xun_head_for_ganzhi,
)
from fatebridge.core.qimen.calendar import QIMEN_FUHEAD_HEAVEN_STEM

LayoutMode = Literal["direct", "rotating", "fei"]
LodgingPolicy = Literal["kun2", "gen8", "yin_gen_yang_kun"]
GodProfile = Literal["yanyi_text", "yanyi_diagrams"]

DEFAULT_GOD_PROFILE: GodProfile = "yanyi_text"
DEFAULT_LODGING_POLICY: LodgingPolicy = "kun2"

GOD_PROFILES: dict[str, dict[str, Any]] = {
    "yanyi_text": {
        "title": "卷三正文八神",
        "section": "卷三·天乙直符吉凶神说",
        "sequence": ["值符", "螣蛇", "太阴", "六合", "白虎", "玄武", "九地", "九天"],
    },
    "yanyi_diagrams": {
        "title": "卷四圆图八神",
        "section": "卷四·阴阳二遁圆图",
        "sequence": ["值符", "螣蛇", "太阴", "六合", "勾陈", "朱雀", "九地", "九天"],
    },
}

FEI_GOD_PROFILES: dict[str, list[str]] = {
    "yanyi_text": ["值符", "螣蛇", "太阴", "六合", "白虎", "玄武", "九地", "九天", "太常"],
    "yanyi_diagrams": ["值符", "螣蛇", "太阴", "六合", "勾陈", "朱雀", "九地", "九天", "太常"],
}


class PalacePosition(TypedDict):
    index: int
    label: str
    trigram: str


class QimenLeaders(TypedDict):
    xun_head: str
    zhifu_heaven_stem: str
    source_gong: str
    star: str
    star_gong: str
    raw_star_gong: str
    door: str
    door_gong: str
    raw_door_gong: str
    dun_type: str
    lodged_gong: str


class DoorHexagram(TypedDict):
    name: str
    binary_code: str


class PalaceGeometry(TypedDict):
    name: str
    index: int
    trigram: str
    content_palace: str
    content_trigram: str
    heaven_origin_trigram: str | None
    heaven_stem: str | None
    heaven_stems: list[str]
    earth_stem: str
    earth_stems: list[str]
    hidden_stem: str
    god: str | None
    god_sequence_index: int | None
    door: str | None
    star: str | None
    hosted_stars: list[str]
    door_hexagram: DoorHexagram | None


QIMEN_PALACES: list[PalacePosition] = [
    {"index": 1, "label": "坎一宫", "trigram": "坎"},
    {"index": 2, "label": "坤二宫", "trigram": "坤"},
    {"index": 3, "label": "震三宫", "trigram": "震"},
    {"index": 4, "label": "巽四宫", "trigram": "巽"},
    {"index": 5, "label": "中五宫", "trigram": "中"},
    {"index": 6, "label": "乾六宫", "trigram": "乾"},
    {"index": 7, "label": "兑七宫", "trigram": "兑"},
    {"index": 8, "label": "艮八宫", "trigram": "艮"},
    {"index": 9, "label": "离九宫", "trigram": "离"},
]

PALACE_BY_TRIGRAM: dict[str, PalacePosition] = {
    p["trigram"]: p for p in QIMEN_PALACES
}

QIMEN_CN_NUMBERS = tuple("一二三四五六七八九")
QIMEN_GUA_SEQUENCE = ("坎", "坤", "震", "巽", "中", "乾", "兑", "艮", "离")
QIMEN_CLOCKWISE_GUA_SEQUENCE = ("坎", "艮", "震", "巽", "离", "坤", "兑", "乾")
QIMEN_DOOR_RING = ("休", "生", "伤", "杜", "景", "死", "惊", "开")
QIMEN_JIU_XING_RING = ("蓬", "芮", "冲", "辅", "禽", "心", "柱", "任", "英")
QIMEN_DOOR_ROUTE = ("休", "死", "伤", "杜", "中", "开", "惊", "生", "景")

QIMEN_STAR_DISPLAY = {
    "蓬": "天蓬",
    "任": "天任",
    "冲": "天冲",
    "辅": "天辅",
    "英": "天英",
    "芮": "天芮",
    "禽": "天禽",
    "柱": "天柱",
    "心": "天心",
}

QIMEN_DOOR_DISPLAY = {
    "休": "休门",
    "生": "生门",
    "伤": "伤门",
    "杜": "杜门",
    "景": "景门",
    "死": "死门",
    "惊": "惊门",
    "开": "开门",
}

QIMEN_DOOR_CODE_BY_DISPLAY: dict[str, str] = {
    door_name: door_code for door_code, door_name in QIMEN_DOOR_DISPLAY.items()
}

QIMEN_DOOR_TO_TRIGRAM: dict[str, str] = {
    "休门": "坎",
    "生门": "艮",
    "伤门": "震",
    "杜门": "巽",
    "景门": "离",
    "死门": "坤",
    "惊门": "兑",
    "开门": "乾",
}

QIMEN_JIU_XING_BY_NUMERAL = dict(zip(QIMEN_CN_NUMBERS, QIMEN_JIU_XING_RING))
QIMEN_EARTH_PLATE_YANG = tuple("戊己庚辛壬癸丁丙乙")

# 驿马星按时支查地支及落宫
HORSE_BY_BRANCH: dict[str, tuple[str, str]] = {
    "申": ("寅", "艮"),
    "子": ("寅", "艮"),
    "辰": ("寅", "艮"),
    "亥": ("巳", "巽"),
    "卯": ("巳", "巽"),
    "未": ("巳", "巽"),
    "寅": ("申", "坤"),
    "午": ("申", "坤"),
    "戌": ("申", "坤"),
    "巳": ("亥", "乾"),
    "酉": ("亥", "乾"),
    "丑": ("亥", "乾"),
}


def resolve_lodged_trigram(
    dun_type: Literal["阳遁", "阴遁"],
    lodging_policy: LodgingPolicy = DEFAULT_LODGING_POLICY,
) -> str:
    if lodging_policy == "kun2":
        return "坤"
    if lodging_policy == "gen8":
        return "艮"
    if lodging_policy == "yin_gen_yang_kun":
        return "坤" if dun_type == "阳遁" else "艮"
    raise ValueError(f"不支持的寄宫策略：{lodging_policy!r}")


def rotate_gua_sequence(yinyang: str) -> tuple[str, ...]:
    if yinyang == "阴":
        return tuple(reversed(QIMEN_CLOCKWISE_GUA_SEQUENCE))
    return QIMEN_CLOCKWISE_GUA_SEQUENCE


def build_earth_plate(ju_text: str) -> dict[str, str]:
    if not re.fullmatch(r"[阴阳]遁[一二三四五六七八九]局[上中下]元", ju_text):
        raise ValueError(f"无效奇门局：{ju_text!r}")
    step = -1 if ju_text[0] == "阴" else 1
    start = QIMEN_CN_NUMBERS.index(ju_text[2])
    return {
        QIMEN_GUA_SEQUENCE[(start + step * offset) % 9]: stem
        for offset, stem in enumerate(QIMEN_EARTH_PLATE_YANG)
    }


def build_qimen_leaders(
    time_ganzhi: str,
    earth: Mapping[str, str],
    *,
    dun_type: Literal["阳遁", "阴遁"],
    lodging_policy: LodgingPolicy = DEFAULT_LODGING_POLICY,
    layout: LayoutMode = "direct",
) -> QimenLeaders:
    """Resolve 值符 (duty star) and 值使 (duty door) positions."""
    earth_palaces_by_stem = {stem: palace for palace, stem in earth.items()}
    head = xun_head_for_ganzhi(time_ganzhi)
    hidden = QIMEN_FUHEAD_HEAVEN_STEM[head]
    origin = earth_palaces_by_stem[hidden]
    lodged_gong = resolve_lodged_trigram(dun_type, lodging_policy)

    origin_index = QIMEN_GUA_SEQUENCE.index(origin)
    star = QIMEN_JIU_XING_BY_NUMERAL[QIMEN_CN_NUMBERS[origin_index]]
    door = QIMEN_DOOR_ROUTE[origin_index]
    if door == "中":
        door = "死" if lodged_gong == "坤" else "生"

    stem = hidden if time_ganzhi[0] == "甲" else time_ganzhi[0]
    raw_star_gong = earth_palaces_by_stem[stem]
    elapsed = sexagenary_index_for(time_ganzhi) % 10
    step = -1 if dun_type == "阴遁" else 1
    raw_door_gong = QIMEN_GUA_SEQUENCE[(origin_index + step * elapsed) % 9]

    if layout == "fei":
        star_gong = raw_star_gong
        door_gong = raw_door_gong
    else:
        star_gong = lodged_gong if raw_star_gong == "中" else raw_star_gong
        door_gong = lodged_gong if raw_door_gong == "中" else raw_door_gong

    return {
        "xun_head": head,
        "zhifu_heaven_stem": hidden,
        "source_gong": origin,
        "star": star,
        "star_gong": star_gong,
        "raw_star_gong": raw_star_gong,
        "door": door,
        "door_gong": door_gong,
        "raw_door_gong": raw_door_gong,
        "dun_type": dun_type[0],
        "lodged_gong": lodged_gong,
    }


def rotation_origins(leader: QimenLeaders) -> dict[str, str]:
    ring = QIMEN_CLOCKWISE_GUA_SEQUENCE
    lodged = leader["lodged_gong"]
    source = lodged if leader["source_gong"] == "中" else leader["source_gong"]
    offset = ring.index(leader["star_gong"]) - ring.index(source)
    return {ring[(index + offset) % 8]: palace for index, palace in enumerate(ring)}


def compute_hidden_stems(
    *,
    time_ganzhi: str,
    leader: QimenLeaders,
) -> dict[str, str]:
    """Compute 暗干 (hidden stems) starting from hour stem at 值使门 palace."""
    hour_stem = leader["zhifu_heaven_stem"] if time_ganzhi[0] == "甲" else time_ganzhi[0]
    start_palace = leader["door_gong"]
    start_palace_idx = QIMEN_GUA_SEQUENCE.index(start_palace)
    start_stem_idx = QIMEN_EARTH_PLATE_YANG.index(hour_stem)
    step = -1 if leader["dun_type"] == "阴" else 1
    return {
        QIMEN_GUA_SEQUENCE[(start_palace_idx + step * i) % 9]: QIMEN_EARTH_PLATE_YANG[
            (start_stem_idx + i) % 9
        ]
        for i in range(9)
    }


def compute_horse_star(time_ganzhi: str) -> dict[str, str]:
    hour_branch = time_ganzhi[1]
    horse_branch, trigram = HORSE_BY_BRANCH[hour_branch]
    palace = PALACE_BY_TRIGRAM[trigram]
    return {
        "branch": horse_branch,
        "trigram": trigram,
        "palace": palace["label"],
    }


def build_palace_geometry(
    *,
    earth: Mapping[str, str],
    leader: QimenLeaders,
    god_profile: str = DEFAULT_GOD_PROFILE,
    time_ganzhi: str = "甲子",
    layout: LayoutMode = "direct",
) -> list[PalaceGeometry]:
    hidden_stems = compute_hidden_stems(time_ganzhi=time_ganzhi, leader=leader)
    if layout == "fei":
        return _build_fei_palace_geometry(
            earth=earth,
            leader=leader,
            god_profile=god_profile,
            hidden_stems=hidden_stems,
        )

    lodged = leader["lodged_gong"]
    origins = rotation_origins(leader)
    ring = QIMEN_CLOCKWISE_GUA_SEQUENCE
    door_source = QIMEN_DOOR_TO_TRIGRAM[QIMEN_DOOR_DISPLAY[leader["door"]]]
    door_offset = ring.index(leader["door_gong"]) - ring.index(door_source)
    doors = {
        ring[(index + door_offset) % 8]: QIMEN_DOOR_RING[index] for index in range(8)
    }
    god_route = rotate_sequence(
        rotate_gua_sequence(leader["dun_type"]), leader["star_gong"]
    )
    gods = dict(zip(god_route, GOD_PROFILES[god_profile]["sequence"]))
    god_indices = {trigram: index for index, trigram in enumerate(god_route)}
    palaces: list[PalaceGeometry] = []
    for palace in QIMEN_PALACES:
        trigram = palace["trigram"]
        is_center = trigram == "中"
        origin = origins.get(trigram)
        star_code = (
            QIMEN_JIU_XING_RING[QIMEN_GUA_SEQUENCE.index(origin)] if origin else None
        )
        heaven_stems = [earth[origin]] if origin else []
        if origin == lodged:
            heaven_stems.append(earth["中"])
        earth_stems = [earth[trigram]]
        if trigram == lodged:
            earth_stems.append(earth["中"])
        door = None if is_center else QIMEN_DOOR_DISPLAY[doors[trigram]]
        hexagram = (
            build_hexagram(upper_name=trigram, lower_name=QIMEN_DOOR_TO_TRIGRAM[door])
            if door
            else None
        )
        palaces.append(
            {
                "name": palace["label"],
                "index": palace["index"],
                "trigram": trigram,
                "content_palace": palace["label"],
                "content_trigram": trigram,
                "heaven_origin_trigram": origin,
                "heaven_stem": heaven_stems[0] if heaven_stems else None,
                "heaven_stems": heaven_stems,
                "earth_stem": earth[trigram],
                "earth_stems": earth_stems,
                "hidden_stem": hidden_stems[trigram],
                "god": None if is_center else gods[trigram],
                "god_sequence_index": None if is_center else god_indices[trigram],
                "door": door,
                "star": QIMEN_STAR_DISPLAY[star_code] if star_code else None,
                "hosted_stars": ["天禽"] if origin == lodged else [],
                "door_hexagram": (
                    {"name": hexagram["name"], "binary_code": hexagram["binary_code"]}
                    if hexagram
                    else None
                ),
            }
        )
    return palaces


def _build_fei_palace_geometry(
    *,
    earth: Mapping[str, str],
    leader: QimenLeaders,
    god_profile: str,
    hidden_stems: Mapping[str, str],
) -> list[PalaceGeometry]:
    """Flying Plate (飞盘): all 9 palaces fly in Luo Shu order without center lodging."""
    seq = QIMEN_GUA_SEQUENCE
    step = -1 if leader["dun_type"] == "阴" else 1

    # 1. Nine stars & heaven stems fly through 1..9 in Luo Shu order (阳顺阴逆).
    star_idx = QIMEN_JIU_XING_RING.index(leader["star"])
    star_target_idx = seq.index(leader["star_gong"])
    origins: dict[str, str] = {}
    for offset in range(9):
        target = seq[(star_target_idx + step * offset) % 9]
        origin = seq[(star_idx + step * offset) % 9]
        origins[target] = origin

    # 2. Doors fly through 1..9 in Luo Shu order using QIMEN_DOOR_ROUTE.
    door_idx = QIMEN_DOOR_ROUTE.index(leader["door"])
    door_target_idx = seq.index(leader["door_gong"])
    doors: dict[str, str | None] = {}
    for offset in range(9):
        target = seq[(door_target_idx + step * offset) % 9]
        door_code = QIMEN_DOOR_ROUTE[(door_idx + step * offset) % 9]
        doors[target] = None if door_code == "中" else QIMEN_DOOR_DISPLAY[door_code]

    # 3. Nine gods fly through 1..9 starting at 值符宫.
    god_seq = FEI_GOD_PROFILES[god_profile]
    gods: dict[str, str] = {}
    god_indices: dict[str, int] = {}
    for offset in range(9):
        target = seq[(star_target_idx + step * offset) % 9]
        gods[target] = god_seq[offset]
        god_indices[target] = offset

    palaces: list[PalaceGeometry] = []
    for palace in QIMEN_PALACES:
        trigram = palace["trigram"]
        origin = origins[trigram]
        star_code = QIMEN_JIU_XING_RING[seq.index(origin)]
        door = doors[trigram]
        hexagram = (
            build_hexagram(
                upper_name="坤" if trigram == "中" else trigram,
                lower_name=QIMEN_DOOR_TO_TRIGRAM[door],
            )
            if door
            else None
        )
        palaces.append(
            {
                "name": palace["label"],
                "index": palace["index"],
                "trigram": trigram,
                "content_palace": palace["label"],
                "content_trigram": trigram,
                "heaven_origin_trigram": origin,
                "heaven_stem": earth[origin],
                "heaven_stems": [earth[origin]],
                "earth_stem": earth[trigram],
                "earth_stems": [earth[trigram]],
                "hidden_stem": hidden_stems[trigram],
                "god": gods[trigram],
                "god_sequence_index": god_indices[trigram],
                "door": door,
                "star": QIMEN_STAR_DISPLAY[star_code],
                "hosted_stars": [],
                "door_hexagram": (
                    {"name": hexagram["name"], "binary_code": hexagram["binary_code"]}
                    if hexagram
                    else None
                ),
            }
        )
    return palaces
