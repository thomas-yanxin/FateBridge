"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

JINKOU_SCAN_URL = "https://upload.wikimedia.org/wikipedia/commons/1/10/CNTS-00047981961_2_六壬神課金口訣.pdf"


JINKOU_SCAN_SHA256 = "ee80bf68c7f87570540c88f073814af7adcd142b22ae71f6679253f59387785b"


TRINES = {
    frozenset(s): e
    for s, e in (("寅午戌", "火"), ("申子辰", "水"), ("亥卯未", "木"), ("巳酉丑", "金"))
}


BRANCH_COMBINES = dict(zip("子丑寅亥卯戌辰酉巳申午未", "丑子亥寅戌卯酉辰申巳未午"))


STEM_COMBINES = dict(zip("甲己乙庚丙辛丁壬戊癸", "己甲庚乙辛丙壬丁癸戊"))


HOUSE_BRANCH = dict(
    zip(
        "甲乙丙丁戊己庚辛壬癸",
        ("寅", "卯", "午", "巳", "辰戌", "丑未", "申", "酉", "子", "亥"),
    )
)
