"""Source-specific, explicitly partial collation of Heluo line texts.

This layer never treats a matching Zhouyi reading as proof of the Heluo edition.
Header, commentary, poem and verdict provenance remain separate.
"""

import json
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any

from fatebridge.core.heluo_poems import apply_poems
from fatebridge.utils.errors import NumerologySourceError

COLLATION_PATH = (
    Path(__file__).resolve().parents[1] / "data/heluo/yaoci-collation-v1.json"
)
COMMENTARY_PATH = (
    Path(__file__).resolve().parents[1] / "data/heluo/commentary-collation-v1.json"
)
SOURCE_PDF_SHA256 = "fd203ebcd4dc355dbb1ddd3cbee0a72051a2ca6f7a3e0945027690aac8de0b0c"
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
HEADER_CONTENT_SHA256 = (
    "61e5f891792122d73c84faef09b46bbc40864ac122a79100f9bdf0decfe0c5e3"
)
COMMENTARY_CONTENT_SHA256 = (
    "0b0bca66080f6e3c8822bc8269d2241b433197b92e1348764057ae1744b765ed"
)
CONTENT_IDENTITY_POLICY = (
    "version_pinned_canonical_JSON_text_labels_and_metadata; formatting_independent"
)
SECTION_LAYOUT_EXCEPTIONS = {
    ("風天小畜", 3): ["opening", "xie", "annual"],
}


def _pin_content(data: dict[str, Any], expected: str) -> str:
    digest = sha256(
        json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    if digest != expected:
        raise ValueError("该版本的河洛原文、标签或来源元数据被改写。")
    return digest


def _source_identity(
    data: dict[str, Any], corpus: str, version: str, total_key: str
) -> None:
    if (
        not isinstance(data, dict)
        or data["corpus_id"] != corpus
        or data["version"] != version
        or data["source_pdf_sha256"] != SOURCE_PDF_SHA256
        or type(data[total_key]) is not int
        or data[total_key] != 384
    ):
        raise ValueError("所选河洛文本来源身份不一致。")
    for key in ("source_url", "review_status", "scope", "transcription_policy"):
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
def _collation() -> dict[str, Any]:
    try:
        raw = COLLATION_PATH.read_bytes()
        data: dict[str, Any] = json.loads(raw)
        _source_identity(
            data, "heluo_nlc_yaoci_headers_v16", "16.0.0", "total_line_headers"
        )
        _entry_keys(data, HEADER_HEXAGRAMS)
        for entry in data["entries"]:
            if (
                type(entry["pdf_page"]) is not int
                or entry["pdf_page"] not in range(1, 280)
                or not isinstance(entry["yaoci"], str)
                or not entry["yaoci"].strip()
            ):
                raise ValueError("河洛爻辞缺原页或正文。")
        content_sha = _pin_content(data, HEADER_CONTENT_SHA256)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_heluo_header_collation") from exc
    data["_loaded_sha256"] = sha256(raw).hexdigest()
    data["_content_sha256"] = content_sha
    return data


def collation_summary() -> dict[str, Any]:
    data = _collation()
    count = len(data["entries"])
    return {
        "corpus_id": data["corpus_id"],
        "version": data["version"],
        "sha256": data["_loaded_sha256"],
        "content_sha256": data["_content_sha256"],
        "content_identity_policy": CONTENT_IDENTITY_POLICY,
        "source_pdf_sha256": data["source_pdf_sha256"],
        "source_url": data["source_url"],
        "review_status": data["review_status"],
        "scope": data["scope"],
        "transcription_policy": data["transcription_policy"],
        "total_line_headers": data["total_line_headers"],
        "collated_line_headers": count,
        "pending_line_headers": data["total_line_headers"] - count,
    }


@lru_cache(maxsize=1)
def _commentary_collation() -> dict[str, Any]:
    try:
        raw = COMMENTARY_PATH.read_bytes()
        data: dict[str, Any] = json.loads(raw)
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
        for entry in data["entries"]:
            # Sui17 through Daxu26 retain the printed historical 叶. Earlier
            # entries retain their disclosed normalization, not a silent edit.
            entry_labels = {
                **labels,
                **(
                    {"xie": "叶者", "buxie": "不叶者"}
                    if entry["hexagram"]
                    in {
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
        content_sha = _pin_content(data, COMMENTARY_CONTENT_SHA256)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_heluo_commentary_collation") from exc
    data["_loaded_sha256"] = sha256(raw).hexdigest()
    data["_content_sha256"] = content_sha
    return data


def commentary_collation_summary() -> dict[str, Any]:
    data = _commentary_collation()
    count = len(data["entries"])
    return {
        "corpus_id": data["corpus_id"],
        "version": data["version"],
        "sha256": data["_loaded_sha256"],
        "content_sha256": data["_content_sha256"],
        "content_identity_policy": CONTENT_IDENTITY_POLICY,
        "source_pdf_sha256": data["source_pdf_sha256"],
        "source_url": data["source_url"],
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


def _commentary_cross_references(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Source-attested conditional quotations, separate from natal transforms."""
    sources: dict[tuple[str, int], dict[str, Any]] = {
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
    }
    sources[("火天大有", 3)] = {
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
    }
    sources[("地山謙", 1)] = {
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
    }
    sources[("地山謙", 4)] = {
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
    }
    sources[("山風蠱", 4)] = {
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
    }
    sources[("地澤臨", 4)] = {
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
    }
    sources[("地澤臨", 5)] = {
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
    }
    sources[("火雷噬嗑", 1)] = {
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
    }
    sources[("火雷噬嗑", 6)] = {
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
    }
    sources[("山火賁", 2)] = {
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
    }
    sources[("山地剝", 4)] = {
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
        "basis": "quotation_inside_Bo23_4_xie_parent; printed_target_line; "
        "applicability_not_assessed; not_new_collation_of_target",
    }
    sources[("山地剝", 6)] = {
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
        "basis": "quotation_inside_Bo23_6_annual_parent; printed_target_line; "
        "applicability_not_assessed; not_new_collation_of_target",
    }
    sources[("地雷復", 3)] = {
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
        "basis": "quotation_inside_Fu24_3_annual_parent; target_line_not_printed; "
        "source_commentator_words_only; applicability_not_assessed; "
        "not_new_collation_of_target",
    }
    sources[("地雷復", 6)] = {
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
        "basis": "quotation_inside_Fu24_6_xie_parent; target_line_not_printed; "
        "source_commentator_words_only; applicability_not_assessed; "
        "not_new_collation_of_target",
    }
    sources[("山天大畜", 2)] = {
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
        "basis": "quotation_inside_Daxu26_2_xie_parent; target_position_not_printed; "
        "applicability_not_assessed; "
        "target_quote_is_source_commentator_wording_not_new_target_collation",
    }
    sources[("山天大畜", 6)] = {
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
        "basis": "quotation_inside_Daxu26_6_buxie_parent; "
        "target_position_explicit_upper_line; applicability_not_assessed; "
        "target_quote_is_source_commentator_wording_not_new_target_collation",
        "target_line_printed": True,
    }
    source = sources.get((entry["hexagram"], entry["line"]))
    if source is None:
        return []
    from fatebridge.core.heluo_hexagrams import gua_lines, lines_to_gua

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
    data = _commentary_collation()
    entry = next(
        (e for e in data["entries"] if (e["hexagram"], e["line"]) == (gua, pos)),
        None,
    )
    if entry is None:
        return
    sections = deepcopy(entry["sections"])
    for section in sections:
        section["applicability"] = None
    provenance.update(
        commentary_status="source_commentary_visually_collated",
        commentary_corpus_id=data["corpus_id"],
        commentary_sha256=commentary_collation_summary()["sha256"],
        commentary_content_sha256=data["_content_sha256"],
        inherited_detail=result["detail"],
        commentary_pdf_pages=entry["pdf_pages"][:],
        commentary_source_url=data["source_url"],
        commentary_source_pdf_sha256=data["source_pdf_sha256"],
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


def text_reading_notes_snapshot(text: dict[str, Any]) -> list[str]:
    """Render the supplied record's qualifications without reselecting text."""
    provenance = text["text_provenance"]
    notes: list[str] = []
    for label, key in (
        ("爻辞", "header_reading_notes"),
        ("注文", "commentary_reading_notes"),
    ):
        notes.extend(f"{label}读文说明：{note}" for note in provenance.get(key, []))
    for poem in text.get("poem_sections", []):
        notes.extend(
            f"第{poem['index']}首诗读文说明：{note}"
            for note in poem.get("reading_notes", [])
        )
    supplement = text.get("poem_review_supplement")
    if supplement:
        notes.append("后续五首复核范围：" + supplement["scope_note"])
        for entry in supplement["entries"]:
            notes.extend(
                f"第{entry['poem_index']}首后续复核：{note}"
                for note in entry["review_notes"]
            )
    return notes


def poem_text_snapshot(text: dict[str, Any]) -> str:
    """Label the actual poem layer, retaining all printed poems and doubts."""
    if text["text_provenance"]["poem_status"] == "source_poems_visually_collated":
        label = "诗歌（卷三局部目校，按印次全列，未择用）"
    else:
        label = "诗歌（继承文本，来源待核）"
    return f"{label}：{text['shige']}"


def text_status_snapshot(text: dict[str, Any]) -> str:
    provenance = text["text_provenance"]
    if provenance["commentary_status"] == "source_commentary_visually_collated":
        pages = "、".join(map(str, provenance["commentary_pdf_pages"]))
        note = f"注文据影印PDF第{pages}页单次目校，待独立复核"
        if provenance["poem_status"] == "source_poems_visually_collated":
            poem_pages = "、".join(map(str, provenance["poem_pdf_pages"]))
            note += f"；另据卷三PDF第{poem_pages}页单次目校本爻{len(text['poem_sections'])}首诗，按印次全列，未择用；象曰的具体来源未由诗诀底本核定"
        else:
            note += "；诗歌未见于这些爻解段落，来源待核"
        if any(
            "unresolved" in p.get("review_status", "")
            for p in text.get("poem_sections", [])
        ):
            note += "；诗诀仍有字形未决，暂读与候选见逐首读稿说明"
        if "unresolved" in provenance.get("commentary_review_status", ""):
            note += "；本条仍有字形未决，暂读与候选见读稿说明"
        if "unresolved" in provenance.get("review_status", ""):
            note += "；爻辞仍有字形未决，暂读与候选见头辞读稿说明"
        for reference in text.get("commentary_cross_references", []):
            if reference["source_hexagram"] == "地水師":
                note += "；师三引升三仅为有条件的单爻变引用，适用未定，不替代后天卦"
            elif reference["source_hexagram"] == "風天小畜":
                note += (
                    "；小畜初引巽初仅为有条件的单爻变引用，适用未定，不替代后天巽四爻"
                )
            elif reference["target_line"] is None:
                quotation = (
                    f"原注另引“{reference['target_quote']}”、未指定目标爻"
                    if reference["target_quote"] is not None
                    else "只印卦名、未指定目标爻"
                )
                note += (
                    f"；{reference['source_hexagram']}第{reference['source_line']}爻在"
                    f"{reference['source_condition_label']}段的{reference['condition_text']}语境引{reference['target_hexagram']}"
                    f"，{quotation}；单爻翻转核对相符，适用未定，不替代正式后天卦"
                )
            else:
                condition_context = (
                    f"的{reference['condition_text']}语境"
                    if reference.get("condition_text")
                    and reference["condition_text"]
                    != reference["source_condition_label"]
                    else ""
                )
                note += (
                    f"；{reference['source_hexagram']}第{reference['source_line']}爻在"
                    f"{reference['source_condition_label']}段{condition_context}引{reference['target_hexagram']}"
                    f"第{reference['target_line']}爻，属有条件的单爻变引用，适用未定，不替代后天卦"
                )
        if text.get("commentary_branch_selection", {}).get(
            "condition_labels_not_separately_printed"
        ):
            note += "；本爻未单列不葉者，未印标签不表示不匹配"
        return note
    return "摘要注文及诗歌尚未逐字核对，诗歌来源待核"


def collated_line(gua: str, pos: int, inherited: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(inherited)
    entry = next(
        (
            e
            for e in _collation()["entries"]
            if (e["hexagram"], e["line"]) == (gua, pos)
        ),
        None,
    )
    provenance: dict[str, Any] = {
        "yaoci_status": "inherited_transcription_collation_pending",
        "commentary_status": "inherited_transcription_collation_pending",
        "poem_status": "inherited_poem_source_unverified",
        "verdict_status": "inherited_summary_not_source_branch_judgment",
        "automatic_branch_selection": False,
    }
    if entry is not None:
        data = _collation()
        result["yaoci"] = entry["yaoci"]
        provenance.update(
            yaoci_status="source_header_visually_collated",
            corpus_id=data["corpus_id"],
            inherited_yaoci=inherited["yaoci"],
            pdf_page=entry["pdf_page"],
            source_url=f"{data['source_url']}#page={entry['pdf_page']}",
            source_pdf_sha256=data["source_pdf_sha256"],
            header_content_sha256=data["_content_sha256"],
            review_status=entry.get("review_status", data["review_status"]),
            transcription_policy=data["transcription_policy"],
        )
        if "reading_notes" in entry:
            provenance["header_reading_notes"] = deepcopy(entry["reading_notes"])
    _apply_commentary(gua, pos, result, provenance)
    apply_poems(gua, pos, result, provenance)
    result["text_provenance"] = provenance
    return result
