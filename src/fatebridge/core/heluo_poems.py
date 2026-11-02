"""Partial volume-three poem witness, distinct from the commentary edition."""

import json
import re
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from fatebridge.utils.errors import NumerologySourceError

COLLATION_PATH = (
    Path(__file__).resolve().parents[1] / "data/heluo/poem-collation-v1.json"
)
CONTENT_SHA256 = "5e956c49d71db1879743ad9e4ac4511f58a0cae036ebd5d30abc9e595020703d"
SOURCE_PDF_SHA256 = "4a04e1e32a42719f001b56936e3c7561b5f68563ae54f0a23ed004af146cfcd7"
REVIEW_PATH = COLLATION_PATH.with_name("song-independent-review-v1.json")
REVIEW_CONTENT_SHA256 = (
    "146493f391a4c30917afa4259025989d7c0196074ca1ea14947cec901d023f9c"
)
# Heading page and each individual poem's text page, in printed gua/line order.
# A heading at a page end does not put the following poem on that page.
LAYOUTS = {
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


@lru_cache(maxsize=1)
def _collation() -> dict[str, Any]:
    try:
        raw = COLLATION_PATH.read_bytes()
        data: dict[str, Any] = json.loads(raw)
        if (
            data["corpus_id"] != "heluo_nlc_volume3_line_poems_v2"
            or data["version"] != "2.6.0"
            or data["source_pdf_sha256"] != SOURCE_PDF_SHA256
            or type(data["source_pdf_pages"]) is not int
            or data["source_pdf_pages"] != 154
            or type(data["total_line_poem_groups"]) is not int
            or data["total_line_poem_groups"] != 384
            or not isinstance(data["entries"], list)
            or len(data["entries"]) != 6 * len(LAYOUTS)
        ):
            raise ValueError("河洛卷三诗诀来源或覆盖范围不符。")
        expected = [
            (gua, pos, heading, text_pages)
            for gua, rows in LAYOUTS.items()
            for pos, (heading, text_pages) in enumerate(rows, 1)
        ]
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
            for index, poem in enumerate(entry["poems"], 1):
                label = None if index == 1 else ("其二" if index == 2 else "其三")
                if (
                    type(poem["index"]) is not int
                    or poem["index"] != index
                    or poem["printed_label"] != label
                    or poem["pdf_pages"] != [text_pages[index - 1]]
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
        content_sha = sha256(
            json.dumps(
                data,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()
        if content_sha != CONTENT_SHA256:
            raise ValueError("该版本诗诀正文、标签或来源元数据被改写。")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_heluo_poem_collation") from exc
    data["_loaded_sha256"] = sha256(raw).hexdigest()
    data["_content_sha256"] = content_sha
    return data


def collation_summary() -> dict[str, Any]:
    data = _collation()
    count = len(data["entries"])
    return {
        **{
            k: data[k]
            for k in (
                "corpus_id",
                "version",
                "source_title",
                "source_url",
                "catalog_url",
                "source_pdf_sha256",
                "source_pdf_pages",
                "catalog_publication_date",
                "review_status",
                "scope",
                "transcription_policy",
                "selection_policy",
                "total_line_poem_groups",
            )
        },
        "sha256": data["_loaded_sha256"],
        "content_sha256": data["_content_sha256"],
        "content_identity_policy": "version_pinned_canonical_JSON_text_labels_and_metadata; formatting_independent",
        "collated_line_poem_groups": count,
        "covered_hexagrams": list(LAYOUTS),
        "pending_line_poem_groups": data["total_line_poem_groups"] - count,
        "collated_individual_poems": sum(len(e["poems"]) for e in data["entries"]),
        "total_individual_poems": None,
        "automatic_poem_selection": False,
    }


def poems_for_line(gua: str, pos: int) -> dict[str, Any] | None:
    entry = next(
        (
            e
            for e in _collation()["entries"]
            if (e["hexagram"], e["line"]) == (gua, pos)
        ),
        None,
    )
    return deepcopy(entry)


@lru_cache(maxsize=1)
def _review_supplement() -> dict[str, Any]:
    """A later bounded review must not rewrite the original collation history."""
    try:
        data = json.loads(REVIEW_PATH.read_bytes())
        identity = sha256(
            json.dumps(
                data,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()
        if (
            identity != REVIEW_CONTENT_SHA256
            or data["source_pdf_sha256"] != SOURCE_PDF_SHA256
            or [(e["line"], e["poem_index"]) for e in data["entries"]]
            != [(1, 1), (2, 2), (4, 2), (5, 3), (6, 1)]
        ):
            raise ValueError("河洛五首复核内容身份或范围不符。")
        for review in data["entries"]:
            entry = poems_for_line(review["hexagram"], review["line"])
            if (
                entry is None
                or entry["poems"][review["poem_index"] - 1]["text"]
                != review["current_text"]
            ):
                raise ValueError("后续读稿复核与当前所录诗文不符。")
    except (OSError, IndexError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_heluo_poem_collation") from exc
    return cast(dict[str, Any], data)


def _apply_review_supplement(gua: str, pos: int, result: dict) -> None:
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
            "content_sha256": REVIEW_CONTENT_SHA256,
            "entries": selected,
        }
    )


def apply_poems(gua: str, pos: int, result: dict, provenance: dict) -> None:
    entry = poems_for_line(gua, pos)
    if entry is None:
        return
    summary = collation_summary()
    inherited = result["shige"]
    first, _, _ = inherited.partition("\n")
    provenance.update(
        poem_status="source_poems_visually_collated",
        poem_corpus_id=summary["corpus_id"],
        poem_sha256=summary["sha256"],
        poem_content_sha256=summary["content_sha256"],
        poem_source_pdf_sha256=summary["source_pdf_sha256"],
        poem_source_url=summary["source_url"],
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
