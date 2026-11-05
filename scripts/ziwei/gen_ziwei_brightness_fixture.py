#!/usr/bin/env python3
"""Generate tests/data/ziwei_brightness_reference.json.

PATH B (source-derived full-table fixture) — this script does NOT require
py-iztro to run.  It is a second, independent transcription of the star
brightness data from iztro ``src/data/stars.ts`` (``STARS_INFO[*].brightness``).
The fixture it produces is a transcription regression guard: any divergence
between this file and ``src/fatebridge/core/ziwei_tables.py`` indicates a
copy-error in one of the two transcriptions.

Provenance: iztro src/data/stars.ts, STARS_INFO array, ``brightness`` field.
Branch order: 寅,卯,辰,巳,午,未,申,酉,戌,亥,子,丑  (寅-indexed, same as iztro).
Romanization map: miao=庙 wang=旺 de=得 li=利 ping=平 bu=不 xian=陷.
Empty string in the original (star has no brightness at that branch) is
represented here as an explicit None in the 擎羊/陀罗 lists and produces no
key in the output JSON.

The horoscope oracle is generated separately by gen_ziwei_horoscope_fixture.py
using the pinned JS iztro 2.5.8 implementation. No Python iztro extra is needed.
"""

from __future__ import annotations

import json
import pathlib

# ---------------------------------------------------------------------------
# Authoritative data — second transcription from iztro src/data/stars.ts
# STARS_INFO[*].brightness, 寅-indexed, romanized
# ---------------------------------------------------------------------------

ROMAJI_TO_CHINESE = {
    "miao": "庙",
    "wang": "旺",
    "de": "得",
    "li": "利",
    "ping": "平",
    "bu": "不",
    "xian": "陷",
}

BRANCHES = ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"]

# 18 stars whose brightness rows are single-spaced (safe to .split())
_SINGLE_SPACED: dict[str, str] = {
    "紫微": "wang wang de wang miao miao wang wang de wang ping miao",
    "天机": "de wang li ping miao xian de wang li ping miao xian",
    "太阳": "wang miao wang wang wang de de xian bu xian xian bu",
    "武曲": "de li miao ping wang miao de li miao ping wang miao",
    "天同": "li ping ping miao xian bu wang ping ping miao wang bu",
    "廉贞": "miao ping li xian ping li miao ping li xian ping li",
    "天府": "miao de miao de wang miao de wang miao de miao miao",
    "太阴": "wang xian xian xian bu bu li bu wang miao miao miao",
    "贪狼": "ping li miao xian wang miao ping li miao xian wang miao",
    "巨门": "miao miao xian wang wang bu miao miao xian wang wang bu",
    "天相": "miao xian de de miao de miao xian de de miao miao",
    "天梁": "miao miao miao xian miao wang xian de miao xian miao wang",
    "七杀": "miao wang miao ping wang miao miao miao miao ping wang miao",
    "破军": "de xian wang ping miao wang de xian wang ping miao wang",
    "文昌": "xian li de miao xian li de miao xian li de miao",
    "文曲": "ping wang de miao xian wang de miao xian wang de miao",
    "火星": "miao li xian de miao li xian de miao li xian de",
    "铃星": "miao li xian de miao li xian de miao li xian de",
}

# 擎羊 and 陀罗 have gaps (original '').
# Positions are 0-based (寅=0 … 丑=11).
# 擎羊: None at indices 0,3,6,9; 陀罗: None at indices 1,4,7,10.
_GAPPED: dict[str, list[str | None]] = {
    "擎羊": [
        None,
        "xian",
        "miao",
        None,
        "xian",
        "miao",
        None,
        "xian",
        "miao",
        None,
        "xian",
        "miao",
    ],
    "陀罗": [
        "xian",
        None,
        "miao",
        "xian",
        None,
        "miao",
        "xian",
        None,
        "miao",
        "xian",
        None,
        "miao",
    ],
}


assert len(_SINGLE_SPACED) == 18, "expected 18 single-spaced stars"
assert set(_GAPPED) == {"擎羊", "陀罗"}, "only 擎羊/陀罗 have brightness gaps"


def _build_rows() -> dict[str, list[str | None]]:
    rows: dict[str, list[str | None]] = {}
    for star, romaji_str in _SINGLE_SPACED.items():
        tokens = romaji_str.split()
        assert len(tokens) == 12, f"{star}: expected 12 tokens, got {len(tokens)}"
        rows[star] = [ROMAJI_TO_CHINESE[t] for t in tokens]
    for star, romaji_list in _GAPPED.items():
        assert len(romaji_list) == 12, f"{star}: expected 12 elements"
        rows[star] = [
            ROMAJI_TO_CHINESE[t] if t is not None else None for t in romaji_list
        ]
    return rows


def build_fixture() -> dict[str, str]:
    """Return mapping ``"<star>@<branch>": "<chinese_brightness>"`` for every
    non-None (star, branch) pair."""
    rows = _build_rows()
    fixture: dict[str, str] = {}
    for star, brightness_list in rows.items():
        for branch, value in zip(BRANCHES, brightness_list):
            if value is not None:
                fixture[f"{star}@{branch}"] = value
    return fixture


def main() -> None:
    fixture = build_fixture()
    out_path = (
        pathlib.Path(__file__).resolve().parents[1].parent
        / "tests"
        / "data"
        / "ziwei_brightness_reference.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(fixture)} entries to {out_path}")


if __name__ == "__main__":
    main()
