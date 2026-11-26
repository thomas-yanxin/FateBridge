"""Consolidated Heluo hexagram tables, text collations, and O(1) line lookups."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from fatebridge.utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS
from fatebridge.utils.errors import NumerologySourceError

TRIGRAM_BITS: dict[str, list[int]] = {
    "乾": [1, 1, 1],
    "兌": [1, 1, 0],
    "離": [1, 0, 1],
    "震": [1, 0, 0],
    "巽": [0, 1, 1],
    "坎": [0, 1, 0],
    "艮": [0, 0, 1],
    "坤": [0, 0, 0],
}

GAN = HEAVENLY_STEMS
ZHI = EARTHLY_BRANCHES

NATURAL: dict[str, str] = {
    "天": "乾",
    "地": "坤",
    "水": "坎",
    "火": "離",
    "雷": "震",
    "山": "艮",
    "風": "巽",
    "澤": "兌",
}

LINE_POSITION_LABELS = ["初", "二", "三", "四", "五", "上"]

_HELUO_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "heluo"
DATA_PATH = _HELUO_DATA_DIR / "heluoTiaowen.json"
COLLATION_PATH = _HELUO_DATA_DIR / "yaoci-collation-v1.json"
COMMENTARY_PATH = _HELUO_DATA_DIR / "commentary-collation-v1.json"
POEM_COLLATION_PATH = _HELUO_DATA_DIR / "poem-collation-v1.json"
POEM_REVIEW_PATH = _HELUO_DATA_DIR / "song-independent-review-v1.json"

COMMENTARY_HEXAGRAMS = (
    "乾為天",
    "坤為地",
    "水雷屯",
    "山水蒙",
    "水天需",
    "天水訟",
    "地水師",
    "水地比",
    "風天小畜",
    "天澤履",
    "地天泰",
    "天地否",
    "天火同人",
    "火天大有",
    "地山謙",
    "雷地豫",
    "澤雷隨",
    "山風蠱",
    "地澤臨",
    "風地觀",
    "火雷噬嗑",
    "山火賁",
    "山地剝",
    "地雷復",
    "天雷無妄",
    "山天大畜",
)
HEADER_HEXAGRAMS = COMMENTARY_HEXAGRAMS
SECTION_LAYOUT_EXCEPTIONS = {
    ("風天小畜", 3): ["opening", "xie", "annual"],
}

POEM_LAYOUTS = {
    "乾為天": (
        (2, (3, 3)),
        (3, (3, 3, 3)),
        (3, (3, 3)),
        (3, (3, 3)),
        (3, (3, 4, 4)),
        (4, (4, 4, 4)),
    ),
    "坤為地": (
        (4, (4, 4)),
        (4, (5, 5)),
        (5, (5, 5, 5)),
        (5, (5, 5, 5)),
        (5, (5, 5)),
        (5, (6, 6, 6)),
    ),
    "水雷屯": (
        (6, (6, 6)),
        (6, (6, 6, 6)),
        (6, (7, 7)),
        (7, (7,)),
        (7, (7, 7)),
        (7, (7, 7)),
    ),
    "山水蒙": (
        (8, (8, 8, 8)),
        (8, (8, 8)),
        (8, (8, 8)),
        (8, (8, 8)),
        (8, (9, 9)),
        (9, (9, 9)),
    ),
    "水天需": (
        (9, (9, 9, 9)),
        (9, (10, 10)),
        (10, (10, 10, 10)),
        (10, (10, 10)),
        (10, (10, 10, 10)),
        (10, (11, 11, 11)),
    ),
    "天水訟": (
        (11, (11, 11)),
        (11, (11, 11, 11)),
        (12, (12, 12, 12)),
        (12, (12, 12, 12)),
        (12, (12, 12, 12)),
        (12, (12, 13)),
    ),
    "地水師": (
        (13, (13, 13, 13)),
        (13, (13, 13)),
        (13, (13, 14, 14)),
        (14, (14, 14)),
        (14, (14, 14)),
        (14, (14, 14)),
    ),
    "水地比": (
        (15, (15, 15)),
        (15, (15, 15, 15)),
        (15, (15, 15, 15)),
        (15, (16, 16, 16)),
        (16, (16, 16)),
        (16, (16, 16, 16)),
    ),
}

_COMMENTARY_XREF_SOURCES: dict[tuple[str, int], dict[str, Any]] = {
    ("地水師", 3): {
        "up": "坤",
        "low": "坎",
        "before": [0, 1, 0, 0, 0, 0],
        "after": [0, 1, 1, 0, 0, 0],
        "target": "地風升",
        "quote": "如與命相合者變升三爻，有升虛邑之辭。",
        "condition": "如與命相合者",
        "target_quote": "升虛邑",
        "page": 135,
        "basis": "quotation_inside_Shi3_commentary; not_new_collation_of_Sheng3",
    },
    ("風天小畜", 1): {
        "up": "巽",
        "low": "乾",
        "before": [1, 1, 1, 0, 1, 1],
        "after": [0, 1, 1, 0, 1, 1],
        "target": "巽為風",
        "quote": "數凶者變巽初爻，進退志疑",
        "condition": "數凶者",
        "target_quote": "進退志疑",
        "page": 139,
        "basis": "quotation_inside_XiaoChu1_commentary; not_new_collation_of_Xun1",
    },
    ("地天泰", 2): {
        "up": "坤",
        "low": "乾",
        "before": [1, 1, 1, 0, 0, 0],
        "after": [1, 0, 1, 0, 0, 0],
        "target": "地火明夷",
        "quote": "如不入局不得位則變明夷。二爻防長上有損，言語有傷。",
        "condition": "如不入局不得位",
        "section": "annual",
        "label": "歲運逢之",
        "target_quote": "防長上有損，言語有傷",
        "page": 144,
        "pages": [144, 145],
        "basis": "quotation_inside_Tai2_commentary; adjacent_target_line_text_not_new_collation_of_MingYi2",
    },
    ("天地否", 4): {
        "up": "乾",
        "low": "坤",
        "before": [0, 0, 0, 1, 1, 1],
        "after": [0, 0, 0, 0, 1, 1],
        "target": "風地觀",
        "quote": "變為觀則觀光上國，利用賓于王，乃得志行道而無阻也。",
        "condition": "葉者",
        "section": "xie",
        "label": "葉者",
        "target_quote": "觀光上國，利用賓于王",
        "page": 147,
        "basis": "quotation_inside_Pi4_xie_commentary; not_new_collation_of_Guan4",
    },
    ("天地否", 5): {
        "up": "乾",
        "low": "坤",
        "before": [0, 0, 0, 1, 1, 1],
        "after": [0, 0, 0, 1, 0, 1],
        "target": "火地晉",
        "quote": "且變為晉五爻，有憂者喜矣，失者得矣",
        "condition": "歲運逢之",
        "section": "annual",
        "label": "歲運逢之",
        "target_quote": "有憂者喜矣，失者得矣",
        "page": 148,
        "basis": "quotation_inside_Pi5_annual_commentary; not_new_collation_of_Jin5",
    },
    ("火天大有", 3): {
        "up": "離",
        "low": "乾",
        "before": [1, 1, 1, 1, 0, 1],
        "after": [1, 1, 0, 1, 0, 1],
        "target": "火澤睽",
        "target_line": None,
        "quote": "凶則變睽刑傷難免。",
        "condition": "凶則",
        "section": "annual",
        "label": "歲運逢之",
        "context": "在庶俗必招灾難，晦滯蹇塞，小輩欺凌，凶則變睽刑傷難免。",
        "target_quote": None,
        "page": 152,
        "basis": "hexagram_name_inside_Dayou3_annual_context; target_line_and_target_text_not_printed; not_new_collation_of_Kui",
    },
    ("地山謙", 1): {
        "up": "坤",
        "low": "艮",
        "before": [0, 0, 1, 0, 0, 0],
        "after": [1, 0, 1, 0, 0, 0],
        "target": "地火明夷",
        "target_line": None,
        "quote": "凶者變明夷之傷也。",
        "condition": "凶者",
        "section": "annual",
        "label": "歲運逢之",
        "context": "歲運逢之，在仕為牧民之職，在士宜懷珍待聘，在庶俗宜遠涉江湖，以作商旅。凶者變明夷之傷也。",
        "target_quote": None,
        "page": 154,
        "basis": "reference_inside_Qian15_1_annual_context; target_line_not_printed; not_new_collation_of_Mingyi",
    },
    ("地山謙", 4): {
        "up": "坤",
        "low": "艮",
        "before": [0, 0, 1, 0, 0, 0],
        "after": [0, 0, 1, 1, 0, 0],
        "target": "雷山小過",
        "target_line": None,
        "quote": "蓋一變小過，往厲必戒勿用",
        "condition": "但士農工商宜固守退讓",
        "section": "annual",
        "label": "歲運逢之",
        "context": "歲運逢之，無所不通，但士農工商宜固守退讓，蓋一變小過，往厲必戒勿用，此亦當卑約，不然取損害爾。",
        "target_quote": "往厲必戒勿用",
        "page": 155,
        "basis": "quotation_inside_Qian15_4_annual_context; target_line_not_printed; not_new_collation_of_Xiaoguo",
    },
    ("山風蠱", 4): {
        "up": "艮",
        "low": "巽",
        "before": [0, 1, 1, 0, 0, 1],
        "after": [0, 1, 1, 1, 0, 1],
        "target": "火風鼎",
        "quote": "一變為鼎九四。",
        "condition": "歲運逢之",
        "section": "annual",
        "label": "歲運逢之",
        "target_line_printed": True,
        "target_quote": None,
        "page": 162,
        "basis": "hexagram_and_line_inside_Gu18_4_annual_commentary; no_target_text_printed; not_new_collation_of_Ding4",
    },
    ("地澤臨", 4): {
        "up": "坤",
        "low": "兌",
        "before": [1, 1, 0, 0, 0, 0],
        "after": [1, 1, 0, 1, 0, 0],
        "target": "雷澤歸妹",
        "target_line": None,
        "quote": "但變歸妹，愆期之辭，凡有為者審而後發方可。",
        "condition": "凡有為者",
        "section": "annual",
        "label": "歲運逢之",
        "context": "歲運逢之，在仕則得僚友之力，在士則得麗澤之美，在庶俗則得人情和合而經營順遂。但變歸妹，愆期之辭，凡有為者審而後發方可。",
        "target_quote": "愆期",
        "page": 165,
        "basis": "reference_inside_Lin19_4_annual_context; target_line_not_printed; not_new_collation_of_target_hexagram",
    },
    ("地澤臨", 5): {
        "up": "坤",
        "low": "兌",
        "before": [1, 1, 0, 0, 0, 0],
        "after": [1, 1, 0, 0, 1, 0],
        "target": "水澤節",
        "target_line": None,
        "quote": "蓋變節卦，不傷財，不害民也。",
        "condition": "不叶者",
        "section": "buxie",
        "label": "不叶者",
        "context": "不叶者亦是福人。蓋變節卦，不傷財，不害民也。",
        "target_quote": None,
        "page": 165,
        "basis": "reference_inside_Lin19_5_buxie_context; target_line_not_printed; not_new_collation_of_target_hexagram",
    },
    ("火雷噬嗑", 1): {
        "up": "離",
        "low": "震",
        "before": [1, 0, 0, 1, 0, 1],
        "after": [0, 0, 0, 1, 0, 1],
        "target": "火地晉",
        "target_line": None,
        "quote": "蓋變為晋，獨行正之象也，亦可作貴人。",
        "condition": "叶者",
        "section": "xie",
        "label": "叶者",
        "context": "叶者能防微杜漸，改行率德，先起卑賤，後至高大。蓋變為晋，獨行正之象也，亦可作貴人。",
        "target_quote": "獨行正",
        "page": 168,
        "basis": "quotation_inside_Shike21_1_xie_context; target_line_not_printed; not_new_collation_of_Jin",
    },
    ("火雷噬嗑", 6): {
        "up": "離",
        "low": "震",
        "before": [1, 0, 0, 1, 0, 1],
        "after": [1, 0, 0, 1, 0, 0],
        "target": "震為雷",
        "target_line": 6,
        "target_line_printed": True,
        "quote": "蓋變震上爻，為索索矍矍之象。",
        "condition": "叶者",
        "section": "xie",
        "label": "叶者",
        "target_quote": "索索矍矍",
        "page": 170,
        "basis": "quotation_inside_Shike21_6_xie_commentary; printed_target_upper_line; unresolved_quotation_glyphs_in_reading_notes; not_new_collation_of_Zhen6",
    },
    ("山火賁", 2): {
        "up": "艮",
        "low": "離",
        "before": [1, 0, 1, 0, 0, 1],
        "after": [1, 1, 1, 0, 0, 1],
        "target": "山天大畜",
        "target_line": None,
        "quote": "但變得大畜輿脫輹之象，",
        "condition": "歲運逢之",
        "section": "annual",
        "label": "歲運逢之",
        "context": "歲運逢之，在仕則有因人成事之功而陞遷有地。在士則有文章之善，而得上應援。在庶俗得人提舉，而營爲無阻。但變得大畜輿脫輹之象，亦要相時而動，雖有知己，不可恃勢妄作以取摧抑之患。數凶者喪仆而難救，弱不能立也。",
        "target_quote": "輿脫輹",
        "page": 171,
        "basis": "quotation_inside_Ben22_2_annual_commentary; target_line_not_printed; not_new_collation_of_DaChu",
    },
    ("山地剝", 4): {
        "up": "艮",
        "low": "坤",
        "before": [0, 0, 0, 0, 0, 1],
        "after": [0, 0, 0, 1, 0, 1],
        "target": "火地晉",
        "target_line": 4,
        "target_line_printed": True,
        "quote": "且變得晉四爻鼫鼠之厲，貪而畏人。",
        "condition": "叶者",
        "section": "xie",
        "label": "叶者",
        "context": "叶者以陰剝陽，權重勢盛，雖作貴人，終失大體。且變得晉四爻鼫鼠之厲，貪而畏人。",
        "target_quote": "鼫鼠之厲",
        "page": 174,
        "basis": "quotation_inside_Bo23_4_xie_parent; printed_target_line; applicability_not_assessed; not_new_collation_of_target",
    },
    ("山地剝", 6): {
        "up": "艮",
        "low": "坤",
        "before": [0, 0, 0, 0, 0, 1],
        "after": [0, 0, 0, 0, 0, 0],
        "target": "坤為地",
        "target_line": 6,
        "target_line_printed": True,
        "quote": "數凶變坤上爻其血玄黃之象，",
        "condition": "數凶",
        "section": "annual",
        "label": "歲運逢之",
        "context": "歲運逢之，在仕有權柄，在士得薦舉，逢知己而名就。在庶俗而謹慎奉公守法，斯有庇護而可保無虞。經營者多生意，或修造宮室。數凶變坤上爻其血玄黃之象，防下人侵損，死喪將臨，少年不利，有子不孤。",
        "target_quote": "其血玄黃",
        "page": 175,
        "basis": "quotation_inside_Bo23_6_annual_parent; printed_target_line; applicability_not_assessed; not_new_collation_of_target",
    },
    ("地雷復", 3): {
        "up": "坤",
        "low": "震",
        "before": [1, 0, 0, 0, 0, 0],
        "after": [1, 0, 1, 0, 0, 0],
        "target": "地火明夷",
        "target_line": None,
        "quote": "在士則變明夷，有得其大首之象，而名可成。",
        "condition": "在士",
        "section": "annual",
        "label": "歲運逢之",
        "context": "歲運逢之，在仕爵難穩，更變無定。在士則變明夷，有得其大首之象，而名可成。在庶俗求速應遲，事多反復，疑惑差錯而無定主。",
        "target_quote": "得其大首",
        "page": 176,
        "basis": "quotation_inside_Fu24_3_annual_parent; target_line_not_printed; source_commentator_words_only; applicability_not_assessed; not_new_collation_of_target",
    },
    ("地雷復", 6): {
        "up": "坤",
        "low": "震",
        "before": [1, 0, 0, 0, 0, 0],
        "after": [1, 0, 0, 0, 0, 1],
        "target": "山雷頤",
        "target_line": None,
        "quote": "蓋變為頤，吉。",
        "condition": "叶者",
        "section": "xie",
        "label": "叶者",
        "context": "故叶者改過自新，釋回增美，亦可常保其富貴而為吉人。蓋變為頤，吉。",
        "target_quote": None,
        "page": 177,
        "basis": "quotation_inside_Fu24_6_xie_parent; target_line_not_printed; source_commentator_words_only; applicability_not_assessed; not_new_collation_of_target",
    },
    ("山天大畜", 2): {
        "up": "艮",
        "low": "乾",
        "before": [1, 1, 1, 0, 0, 1],
        "after": [1, 0, 1, 0, 0, 1],
        "target": "山火賁",
        "target_line": None,
        "quote": "故叶者變為賁，有與上興之象。",
        "condition": "叶者",
        "section": "xie",
        "label": "叶者",
        "context": "故叶者變為賁，有與上興之象。必有才德，心性明敏，聞見廣博，守正不移，時上之用。或急流勇退，或掛冠致仕。",
        "target_quote": None,
        "page": 180,
        "basis": "quotation_inside_Daxu26_2_xie_parent; target_position_not_printed; applicability_not_assessed; target_quote_is_source_commentator_wording_not_new_target_collation",
    },
    ("山天大畜", 6): {
        "up": "艮",
        "low": "乾",
        "before": [1, 1, 1, 0, 0, 1],
        "after": [1, 1, 1, 0, 0, 0],
        "target": "地天泰",
        "target_line": 6,
        "quote": "變泰上爻，有城復于隍之象。",
        "condition": "不叶者",
        "section": "buxie",
        "label": "不叶者",
        "context": "不叶者志大心高，機深禍重，變泰上爻，有城復于隍之象。",
        "target_quote": "城復于隍",
        "page": 181,
        "basis": "quotation_inside_Daxu26_6_buxie_parent; target_position_explicit_upper_line; applicability_not_assessed; target_quote_is_source_commentator_wording_not_new_target_collation",
        "target_line_printed": True,
    },
}


@lru_cache(maxsize=1)
def _tiaowen() -> dict[str, Any]:
    with DATA_PATH.open(encoding="utf-8") as handle:
        return cast(dict[str, Any], json.load(handle))


@lru_cache(maxsize=1)
def _gua_tables() -> tuple[dict[str, dict[str, str]], dict[str, str], dict[str, int]]:
    """Build bidirectional lookup tables between trigrams, names, and Wang Bi index."""
    name_to_tri: dict[str, dict[str, str]] = {}
    tri_to_name: dict[str, str] = {}
    name_index: dict[str, int] = {}
    for name, payload in _tiaowen().items():
        if name[1] == "為":
            up = low = name[0]
        else:
            up = NATURAL.get(name[0], "")
            low = NATURAL.get(name[1], "")
        if up in TRIGRAM_BITS and low in TRIGRAM_BITS:
            name_to_tri[name] = {"up": up, "low": low}
            tri_to_name[f"{up}|{low}"] = name
            name_index[name] = payload["index"]
    return name_to_tri, tri_to_name, name_index


def _gua_name(up: str, low: str) -> str:
    return _gua_tables()[1].get(f"{up}|{low}", "")


def gua_lines(up: str, low: str) -> list[int]:
    """Six line bits (bottom-to-top 1..6) = lower trigram + upper trigram."""
    return [*TRIGRAM_BITS[low], *TRIGRAM_BITS[up]]


def lines_to_gua(lines: list[int]) -> dict[str, str]:
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


def _trigram_of(bits: list[int]) -> str:
    return next(
        (t for t, b in TRIGRAM_BITS.items() if all(b[i] == bits[i] for i in range(3))),
        "",
    )


def _source_identity(
    data: dict[str, Any], corpus: str, version: str, total_key: str
) -> None:
    if (
        not isinstance(data, dict)
        or data["corpus_id"] != corpus
        or data["version"] != version
        or type(data[total_key]) is not int
        or data[total_key] != 384
    ):
        raise ValueError("所选河洛文本来源身份不一致。")
    for key in ("review_status", "scope", "transcription_policy"):
        if not isinstance(data[key], str) or not data[key].strip():
            raise ValueError("河洛文本来源元数据缺失。")


def _entry_keys(data: dict[str, Any], hexagrams: tuple[str, ...]) -> None:
    if not isinstance(data["entries"], list):
        raise ValueError("河洛文本索引必须为条目列表。")
    keys = [(e["hexagram"], e["line"]) for e in data["entries"]]
    expected = {(g, p) for g in hexagrams for p in range(1, 7)}
    if (
        len(keys) != len(expected)
        or set(keys) != expected
        or any(type(p) is not int for _, p in keys)
    ):
        raise ValueError("已核河洛文本索引缺项、重复或爻位无效。")


@lru_cache(maxsize=1)
def _collation() -> tuple[dict[str, Any], dict[tuple[str, int], dict[str, Any]]]:
    try:
        data: dict[str, Any] = json.loads(COLLATION_PATH.read_bytes())
        _source_identity(
            data, "heluo_nlc_yaoci_headers_v16", "16.0.0", "total_line_headers"
        )
        _entry_keys(data, HEADER_HEXAGRAMS)
        index: dict[tuple[str, int], dict[str, Any]] = {}
        for entry in data["entries"]:
            if (
                type(entry["pdf_page"]) is not int
                or entry["pdf_page"] not in range(1, 280)
                or not isinstance(entry["yaoci"], str)
                or not entry["yaoci"].strip()
            ):
                raise ValueError("河洛爻辞缺原页或正文。")
            index[(entry["hexagram"], entry["line"])] = entry
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_heluo_header_collation") from exc
    return data, index


def collation_summary() -> dict[str, Any]:
    data, _ = _collation()
    count = len(data["entries"])
    return {
        "corpus_id": data["corpus_id"],
        "version": data["version"],
        "review_status": data["review_status"],
        "scope": data["scope"],
        "transcription_policy": data["transcription_policy"],
        "total_line_headers": data["total_line_headers"],
        "collated_line_headers": count,
        "pending_line_headers": data["total_line_headers"] - count,
    }


@lru_cache(maxsize=1)
def _commentary_collation() -> (
    tuple[dict[str, Any], dict[tuple[str, int], dict[str, Any]]]
):
    try:
        data: dict[str, Any] = json.loads(COMMENTARY_PATH.read_bytes())
        _source_identity(
            data, "heluo_nlc_line_commentary_v19", "19.0.0", "total_line_commentaries"
        )
        _entry_keys(data, COMMENTARY_HEXAGRAMS)
        labels = {
            "opening": None,
            "xie": "葉者",
            "buxie": "不葉者",
            "female": "若是女命",
            "annual": "歲運逢之",
        }
        ye_set = {
            "澤雷隨",
            "山風蠱",
            "地澤臨",
            "風地觀",
            "火雷噬嗑",
            "山火賁",
            "山地剝",
            "地雷復",
            "天雷無妄",
            "山天大畜",
        }
        index: dict[tuple[str, int], dict[str, Any]] = {}
        for entry in data["entries"]:
            entry_labels = {
                **labels,
                **(
                    {"xie": "叶者", "buxie": "不叶者"}
                    if entry["hexagram"] in ye_set
                    else {}
                ),
            }
            sections = entry["sections"]
            ids = [s["section_id"] for s in sections]
            pages = entry["pdf_pages"]
            layouts = (
                (SECTION_LAYOUT_EXCEPTIONS[(entry["hexagram"], entry["line"])],)
                if (entry["hexagram"], entry["line"]) in SECTION_LAYOUT_EXCEPTIONS
                else (
                    ["opening", "xie", "buxie", "annual"],
                    ["opening", "xie", "buxie", "female", "annual"],
                )
            )
            if (
                ids not in layouts
                or not isinstance(pages, list)
                or not pages
                or any(type(p) is not int or p not in range(1, 280) for p in pages)
                or pages != sorted(set(pages))
                or any(
                    not isinstance(s["text"], str)
                    or not s["text"].strip()
                    or s["condition_label"] != entry_labels[s["section_id"]]
                    for s in sections
                )
                or not isinstance(entry["reading_notes"], list)
                or any(
                    not isinstance(n, str) or not n.strip()
                    for n in entry["reading_notes"]
                )
            ):
                raise ValueError("河洛注文缺原页、段落或条件标签不一致。")
            index[(entry["hexagram"], entry["line"])] = entry
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_heluo_commentary_collation") from exc
    return data, index


def commentary_collation_summary() -> dict[str, Any]:
    data, _ = _commentary_collation()
    count = len(data["entries"])
    return {
        "corpus_id": data["corpus_id"],
        "version": data["version"],
        "review_status": data["review_status"],
        "scope": data["scope"],
        "transcription_policy": data["transcription_policy"],
        "total_line_commentaries": data["total_line_commentaries"],
        "collated_line_commentaries": count,
        "pending_line_commentaries": data["total_line_commentaries"] - count,
        "collated_poems": 0,
        "collated_poems_scope": "Reviewed volume-two commentary sections only; separate volume-three poem_collation has its own coverage.",
        "poem_source_status": data["poem_source_status"],
        "automatic_branch_selection": False,
    }


@lru_cache(maxsize=1)
def _poem_collation() -> tuple[dict[str, Any], dict[tuple[str, int], dict[str, Any]]]:
    try:
        data: dict[str, Any] = json.loads(POEM_COLLATION_PATH.read_bytes())
        if (
            data["corpus_id"] != "heluo_nlc_volume3_line_poems_v2"
            or data["version"] != "2.6.0"
            or type(data["source_pdf_pages"]) is not int
            or data["source_pdf_pages"] != 154
            or type(data["total_line_poem_groups"]) is not int
            or data["total_line_poem_groups"] != 384
            or not isinstance(data["entries"], list)
            or len(data["entries"]) != 6 * len(POEM_LAYOUTS)
        ):
            raise ValueError("河洛卷三诗诀来源或覆盖范围不符。")
        expected = [
            (gua, pos, heading, text_pages)
            for gua, rows in POEM_LAYOUTS.items()
            for pos, (heading, text_pages) in enumerate(rows, 1)
        ]
        index: dict[tuple[str, int], dict[str, Any]] = {}
        for entry, (gua, pos, heading, text_pages) in zip(
            data["entries"], expected, strict=True
        ):
            pages = sorted({heading, *text_pages})
            if (
                entry["hexagram"] != gua
                or type(entry["line"]) is not int
                or entry["line"] != pos
                or type(entry["heading_pdf_page"]) is not int
                or entry["heading_pdf_page"] != heading
                or entry["pdf_pages"] != pages
                or not isinstance(entry["poems"], list)
                or len(entry["poems"]) != len(text_pages)
            ):
                raise ValueError("河洛诗诀分组或页界不符。")
            for idx, poem in enumerate(entry["poems"], 1):
                label = None if idx == 1 else ("其二" if idx == 2 else "其三")
                if (
                    type(poem["index"]) is not int
                    or poem["index"] != idx
                    or poem["printed_label"] != label
                    or poem["pdf_pages"] != [text_pages[idx - 1]]
                    or not isinstance(poem["text"], str)
                    or not poem["text"].strip()
                ):
                    raise ValueError("河洛诗诀字序、首序或原页缺失。")
                if gua != "乾為天" and (
                    not isinstance(poem["printed_clauses"], list)
                    or poem["printed_clauses"]
                    != [s for s in re.split("[，。]", poem["text"]) if s]
                ):
                    raise ValueError("河洛诗诀转录句读与所录原印边界不符。")
            index[(gua, pos)] = entry
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_heluo_poem_collation") from exc
    return data, index


def poem_collation_summary() -> dict[str, Any]:
    data, _ = _poem_collation()
    count = len(data["entries"])
    return {
        **{
            k: data[k]
            for k in (
                "corpus_id",
                "version",
                "source_title",
                "source_pdf_pages",
                "catalog_publication_date",
                "review_status",
                "scope",
                "transcription_policy",
                "selection_policy",
                "total_line_poem_groups",
            )
        },
        "collated_line_poem_groups": count,
        "covered_hexagrams": list(POEM_LAYOUTS),
        "pending_line_poem_groups": data["total_line_poem_groups"] - count,
        "collated_individual_poems": sum(len(e["poems"]) for e in data["entries"]),
        "total_individual_poems": None,
        "automatic_poem_selection": False,
    }


@lru_cache(maxsize=1)
def _review_supplement() -> dict[str, Any]:
    try:
        data = json.loads(POEM_REVIEW_PATH.read_bytes())
        if [(e["line"], e["poem_index"]) for e in data["entries"]] != [
            (1, 1),
            (2, 2),
            (4, 2),
            (5, 3),
            (6, 1),
        ]:
            raise ValueError("河洛五首复核内容身份或范围不符。")
        _, poem_index = _poem_collation()
        for review in data["entries"]:
            entry = poem_index.get((review["hexagram"], review["line"]))
            if (
                entry is None
                or entry["poems"][review["poem_index"] - 1]["text"]
                != review["current_text"]
            ):
                raise ValueError("后续读稿复核与当前所录诗文不符。")
    except (OSError, IndexError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_heluo_poem_collation") from exc
    return cast(dict[str, Any], data)


def poems_for_line(gua: str, pos: int) -> dict[str, Any] | None:
    _, index = _poem_collation()
    entry = index.get((gua, pos))
    return deepcopy(entry) if entry is not None else None


def _apply_review_supplement(gua: str, pos: int, result: dict[str, Any]) -> None:
    if gua != "天水訟" or pos not in (1, 2, 4, 5, 6):
        return
    data = _review_supplement()
    selected = [e for e in data["entries"] if e["line"] == pos]
    if any(
        result["poem_sections"][e["poem_index"] - 1]["text"] != e["current_text"]
        for e in selected
    ):
        raise NumerologySourceError("invalid_heluo_poem_collation")
    result["poem_review_supplement"] = deepcopy(
        {
            **{key: value for key, value in data.items() if key != "entries"},
            "entries": selected,
        }
    )


def apply_poems(
    gua: str, pos: int, result: dict[str, Any], provenance: dict[str, Any]
) -> None:
    entry = poems_for_line(gua, pos)
    if entry is None:
        return
    summary = poem_collation_summary()
    inherited = result["shige"]
    first, _, _ = inherited.partition("\n")
    provenance.update(
        poem_status="source_poems_visually_collated",
        poem_corpus_id=summary["corpus_id"],
        poem_review_status=summary["review_status"],
        poem_transcription_policy=summary["transcription_policy"],
        poem_pdf_pages=entry["pdf_pages"],
        poem_heading_pdf_page=entry["heading_pdf_page"],
        inherited_shige=inherited,
    )
    if "heading_text" in entry:
        provenance["poem_heading_text"] = entry["heading_text"]
    result["poem_sections"] = [dict(p, applicability=None) for p in entry["poems"]]
    result["shige"] = "\n".join(p["text"] for p in entry["poems"])
    result["poem_selection"] = {
        "status": "all_printed_poems_retained",
        "selected_poem_indices": [],
        "automatic_selection": False,
        "reason": summary["selection_policy"],
    }
    result["inherited_xiang_reference"] = {
        "text": first if first.startswith("象曰") else None,
        "status": "inherited_reference_specific_source_unverified_by_poem_witness",
    }
    _apply_review_supplement(gua, pos, result)


def _commentary_cross_references(entry: dict[str, Any]) -> list[dict[str, Any]]:
    source = _COMMENTARY_XREF_SOURCES.get((entry["hexagram"], entry["line"]))
    if source is None:
        return []
    pos = entry["line"]
    before = gua_lines(source["up"], source["low"])
    after = before[:]
    after[pos - 1] = 1 - after[pos - 1]
    target = lines_to_gua(after)["name"]
    section = next(
        (
            s
            for s in entry["sections"]
            if s["section_id"] == source.get("section", "annual")
        ),
        None,
    )
    if (
        section is None
        or source["quote"] not in section["text"]
        or ("context" in source and source["context"] not in section["text"])
        or ("label" in source and section["condition_label"] != source["label"])
        or before != source["before"]
        or after != source["after"]
        or lines_to_gua(before)["name"] != entry["hexagram"]
        or target != source["target"]
    ):
        raise NumerologySourceError("invalid_heluo_commentary_collation")
    return [
        {
            "source_hexagram": entry["hexagram"],
            "source_line": pos,
            "source_lines": before,
            "source_quote": source["quote"],
            **(
                {
                    "source_section_id": source["section"],
                    "source_condition_label": source["label"],
                }
                if "section" in source
                else {}
            ),
            "condition_text": source["condition"],
            "operator": "single_line_flip_without_trigram_swap",
            "target_hexagram": target,
            "target_line": source.get("target_line", pos),
            "target_lines": after,
            "target_quote": source["target_quote"],
            "target_quote_basis": source["basis"],
            **(
                {
                    "source_context_text": source["context"],
                    "target_line_source_status": "not_printed",
                }
                if "context" in source
                else {}
            ),
            **(
                {"target_line_source_status": "printed"}
                if source.get("target_line_printed")
                else {}
            ),
            "pdf_pages": source.get("pages", [source["page"]])[:],
            "applicability": None,
            "automatic_application": False,
            "replaces_chart": False,
        }
    ]


def _apply_commentary(
    gua: str, pos: int, result: dict[str, Any], provenance: dict[str, Any]
) -> None:
    data, index = _commentary_collation()
    entry = index.get((gua, pos))
    if entry is None:
        return
    sections = deepcopy(entry["sections"])
    for section in sections:
        section["applicability"] = None
    provenance.update(
        commentary_status="source_commentary_visually_collated",
        commentary_corpus_id=data["corpus_id"],
        inherited_detail=result["detail"],
        commentary_pdf_pages=entry["pdf_pages"][:],
        commentary_review_status=entry.get("review_status", data["review_status"]),
        commentary_transcription_policy=data["transcription_policy"],
        commentary_reading_notes=entry["reading_notes"][:],
        poem_presence_in_reviewed_sections=False,
    )
    result["detail"] = "".join(s["text"] for s in sections)
    result["commentary_sections"] = sections
    result["commentary_branch_selection"] = {
        "status": "not_evaluated",
        "selected_section_ids": [],
        "reason": "段落边界为编辑标注；葉否、陽月、陰命及嵌套条件未综合裁定，judge.xie不能代选。歲運段不自动作为本命断语。",
    }
    if gua in {
        "澤雷隨",
        "山風蠱",
        "地澤臨",
        "風地觀",
        "火雷噬嗑",
        "山火賁",
        "山地剝",
        "地雷復",
        "天雷無妄",
        "山天大畜",
    }:
        result["commentary_branch_selection"][
            "reason"
        ] += "本卦保留原印叶字，不機械改作葉；字形保存不選定命局叶否。"
    if (gua, pos) in SECTION_LAYOUT_EXCEPTIONS:
        result["commentary_branch_selection"][
            "condition_labels_not_separately_printed"
        ] = ["不葉者"]
        result["commentary_branch_selection"][
            "reason"
        ] += "本爻原段未單列不葉者；未印標籤不表示條件為false，亦不將葉者段全判為吉。"
    references = _commentary_cross_references(entry)
    if references:
        result["commentary_cross_references"] = references


def collated_line(gua: str, pos: int, inherited: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(inherited)
    data, index = _collation()
    entry = index.get((gua, pos))
    provenance: dict[str, Any] = {
        "yaoci_status": "inherited_transcription_collation_pending",
        "commentary_status": "inherited_transcription_collation_pending",
        "poem_status": "inherited_poem_source_unverified",
        "verdict_status": "inherited_summary_not_source_branch_judgment",
        "automatic_branch_selection": False,
    }
    if entry is not None:
        result["yaoci"] = entry["yaoci"]
        provenance.update(
            yaoci_status="source_header_visually_collated",
            corpus_id=data["corpus_id"],
            inherited_yaoci=inherited["yaoci"],
            pdf_page=entry["pdf_page"],
            review_status=entry.get("review_status", data["review_status"]),
            transcription_policy=data["transcription_policy"],
        )
        if "reading_notes" in entry:
            provenance["header_reading_notes"] = deepcopy(entry["reading_notes"])
    _apply_commentary(gua, pos, result, provenance)
    apply_poems(gua, pos, result, provenance)
    result["text_provenance"] = provenance
    return result


def yao_text(gua_name: str, pos: int) -> dict[str, Any] | None:
    """Return collated line commentary and verse for ``(gua_name, pos)``."""
    g = _tiaowen().get(gua_name)
    if not g or not g.get("yao", {}).get(str(pos)):
        return None
    return collated_line(gua_name, pos, g["yao"][str(pos)])


def yao_name(lines: list[int], pos: int) -> str:
    yang = lines[pos - 1] == 1
    if pos == 1:
        return f"初{'九' if yang else '六'}"
    if pos == 6:
        return f"上{'九' if yang else '六'}"
    return f"{'九' if yang else '六'}{LINE_POSITION_LABELS[pos - 1]}"
