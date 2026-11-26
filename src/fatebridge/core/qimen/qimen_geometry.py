"""Rotate the Qimen plates and retain the centre palace hosting rules."""

import re
from collections.abc import Mapping
from typing import Literal, TypedDict

from fatebridge.core.divination import build_hexagram
from fatebridge.core.metaphysics.common import (
    rotate_sequence,
    sexagenary_index_for,
    xun_head_for_ganzhi,
)
from fatebridge.core.metaphysics.qimen_calendar_tables import QIMEN_FUHEAD_HEAVEN_STEM
from fatebridge.core.qimen.qimen_profiles import DEFAULT_GOD_PROFILE, GOD_PROFILES


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


def rotate_gua_sequence(yinyang: str) -> tuple[str, ...]:
    if yinyang == "阴":
        return tuple(reversed(QIMEN_CLOCKWISE_GUA_SEQUENCE))
    return QIMEN_CLOCKWISE_GUA_SEQUENCE


def build_qimen_leaders(
    time_ganzhi: str,
    earth: Mapping[str, str],
    *,
    dun_type: Literal["阳遁", "阴遁"],
) -> QimenLeaders:
    """Find the star by hour stem and the door by elapsed hours in the xun.

    Host the centre in Kun after finding the raw positions.
    """
    earth_palaces_by_stem = {stem: palace for palace, stem in earth.items()}
    head = xun_head_for_ganzhi(time_ganzhi)
    hidden = QIMEN_FUHEAD_HEAVEN_STEM[head]
    origin = earth_palaces_by_stem[hidden]
    star = QIMEN_JIU_XING_BY_NUMERAL[QIMEN_CN_NUMBERS[QIMEN_GUA_SEQUENCE.index(origin)]]
    door = QIMEN_DOOR_ROUTE[QIMEN_GUA_SEQUENCE.index(origin)]
    if door == "中":
        door = "死"
    stem = hidden if time_ganzhi[0] == "甲" else time_ganzhi[0]
    raw_star_gong = earth_palaces_by_stem[stem]
    elapsed = sexagenary_index_for(time_ganzhi) % 10
    step = -1 if dun_type == "阴遁" else 1
    raw_door_gong = QIMEN_GUA_SEQUENCE[
        (QIMEN_GUA_SEQUENCE.index(origin) + step * elapsed) % 9
    ]
    return {
        "xun_head": head,
        "zhifu_heaven_stem": hidden,
        "source_gong": origin,
        "star": star,
        "star_gong": "坤" if raw_star_gong == "中" else raw_star_gong,
        "raw_star_gong": raw_star_gong,
        "door": door,
        "door_gong": "坤" if raw_door_gong == "中" else raw_door_gong,
        "raw_door_gong": raw_door_gong,
        "dun_type": dun_type[0],
    }


def build_earth_plate(ju_text: str) -> dict[str, str]:
    if not re.fullmatch(r"[阴阳]遁[一二三四五六七八九]局[上中下]元", ju_text):
        raise ValueError(f"无效奇门局：{ju_text!r}")
    step = -1 if ju_text[0] == "阴" else 1
    start = QIMEN_CN_NUMBERS.index(ju_text[2])
    return {
        QIMEN_GUA_SEQUENCE[(start + step * offset) % 9]: stem
        for offset, stem in enumerate(QIMEN_EARTH_PLATE_YANG)
    }


def rotation_origins(leader: QimenLeaders) -> dict[str, str]:
    """All eight star/stem pairs rotate together, in both yin and yang dun."""
    ring = QIMEN_CLOCKWISE_GUA_SEQUENCE
    source = "坤" if leader["source_gong"] == "中" else leader["source_gong"]
    offset = ring.index(leader["star_gong"]) - ring.index(source)
    return {ring[(index + offset) % 8]: palace for index, palace in enumerate(ring)}


def build_palace_geometry(
    *,
    earth: Mapping[str, str],
    leader: QimenLeaders,
    god_profile: str = DEFAULT_GOD_PROFILE,
) -> list[PalaceGeometry]:
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
        if origin == "坤":
            heaven_stems.append(earth["中"])
        earth_stems = [earth[trigram]]
        if trigram == "坤":
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
                "god": None if is_center else gods[trigram],
                "god_sequence_index": None if is_center else god_indices[trigram],
                "door": door,
                "star": QIMEN_STAR_DISPLAY[star_code] if star_code else None,
                "hosted_stars": ["天禽"] if origin == "坤" else [],
                "door_hexagram": (
                    {"name": hexagram["name"], "binary_code": hexagram["binary_code"]}
                    if hexagram
                    else None
                ),
            }
        )
    return palaces
