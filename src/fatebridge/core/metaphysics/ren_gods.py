"""Explicitly distinct Liu Ren noble-start tables, never a silent substitution."""

from __future__ import annotations

from typing import Literal

from .common import LIURENG_GUIREN_DAY, LIURENG_GUIREN_NIGHT

GuirenProfile = Literal["liuren_common_v1", "tanyuan_xieji_v1"]
DEFAULT_GUIREN_PROFILE: GuirenProfile = "liuren_common_v1"
TANYUAN_TRANSCRIPTION = "https://www.yiology.mobi/books/卜/大六壬/大六壬探原/"

# 探原·卷上·日贵人歌 / 夜贵人歌 (author explicitly follows 协纪辨方).
TANYUAN_DAY = dict(zip("甲乙丙丁戊己庚辛壬癸", "未申酉亥丑子丑寅卯巳"))
TANYUAN_NIGHT = dict(zip("甲乙丙丁戊己庚辛壬癸", "丑子亥酉未申未午巳卯"))


def noble_start(day_stem: str, is_day: bool, profile: GuirenProfile) -> str:
    if profile == "liuren_common_v1":
        return (LIURENG_GUIREN_DAY if is_day else LIURENG_GUIREN_NIGHT)[day_stem]
    if profile == "tanyuan_xieji_v1":
        return (TANYUAN_DAY if is_day else TANYUAN_NIGHT)[day_stem]
    raise ValueError("未知贵人规则配置")
