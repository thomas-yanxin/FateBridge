"""Tai/Pi source words and parent conditions, without automatic branch selection."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import heluo_texts as ht
from fatebridge.core.heluo import _tiaowen, transform_houtian, yao_text
from fatebridge.core.heluo_timing import _selected_text
from fatebridge.utils.errors import NumerologySourceError
from tests.support.heluo_source_facts import HEADER_COUNT, PENDING_COUNT

ROOT = Path(__file__).parents[1] / "fixtures/heluo_taipi_v1"
DRAFT = json.loads((ROOT / "reference.json").read_bytes())
VERIFIED = json.loads((ROOT / "verified-readings.json").read_bytes())


@pytest.mark.parametrize(
    "e", VERIFIED["entries"], ids=lambda e: e["hexagram"] + str(e["line"])
)
def test_complete_source_commentary_preserves_parent_and_all_conditions(e):
    t = yao_text(e["hexagram"], e["line"])
    assert t["detail"] == "".join(s["text"] for s in e["sections"])
    assert t["commentary_sections"] == [
        dict(s, applicability=None) for s in e["sections"]
    ]
    p = t["text_provenance"]
    assert p["commentary_pdf_pages"] == e["pdf_pages"]
    assert p["commentary_reading_notes"] == e["reading_notes"]
    assert "independent_second_review_pending" in p["commentary_review_status"]
    assert t["commentary_branch_selection"]["selected_section_ids"] == []
    old = _tiaowen()[e["hexagram"]]["yao"][str(e["line"])]
    assert p["inherited_detail"] == old["detail"]
    assert (t["shige"], t["verdict"]) == (old["shige"], old["verdict"])
    bits = [1, 1, 1, 0, 0, 0] if e["hexagram"] == "地天泰" else [0, 0, 0, 1, 1, 1]
    timed = _selected_text(dict(gua=e["hexagram"], pos=e["line"], lines=bits), "annual")
    assert timed["heluo_commentary"] == t


@pytest.mark.parametrize(
    "e", VERIFIED["headers"], ids=lambda e: e["hexagram"] + str(e["line"])
)
def test_headers_use_this_printing_not_a_silent_zhouyi_replacement(e):
    t = yao_text(e["hexagram"], e["line"])
    assert t["yaoci"] == e["yaoci"]
    assert t["text_provenance"]["pdf_page"] == e["pdf_page"]
    assert t["text_provenance"]["header_content_sha256"] == ht.HEADER_CONTENT_SHA256


def test_negative_xie_and_nested_female_conditions_are_not_flattened():
    t = yao_text("地天泰", 4)
    assert "功名難全" in t["commentary_sections"][1]["text"]
    assert t["commentary_branch_selection"]["status"] == "not_evaluated"
    t = yao_text("地天泰", 5)
    assert "女命得此" in t["commentary_sections"][1]["text"]
    assert [s["section_id"] for s in t["commentary_sections"]] == [
        "opening",
        "xie",
        "buxie",
        "annual",
    ]
    assert "縱爻辭美不足羨也" in yao_text("天地否", 1)["detail"]
    assert "commentary_cross_references" not in yao_text("天地否", 6)
    assert "尚遜者" in yao_text("天地否", 5)["detail"]


def test_original_images_old_entries_and_withdrawn_draft_are_preserved():
    for name, key in [
        ("reference.json", "draft_sha256"),
        ("amendments.json", "amendments_sha256"),
    ]:
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == VERIFIED[key]
    for w in DRAFT["images"]:
        assert (
            hashlib.sha256((ROOT / w["file"]).read_bytes()).hexdigest() == w["sha256"]
        )
    assert (
        ht.commentary_collation_summary()["collated_line_commentaries"],
        ht.commentary_collation_summary()["pending_line_commentaries"],
    ) == (HEADER_COUNT, PENDING_COUNT)
    assert (
        ht.collation_summary()["collated_line_headers"],
        ht.collation_summary()["pending_line_headers"],
    ) == (HEADER_COUNT, PENDING_COUNT)
    assert (
        VERIFIED["independent_second_reviews"]
        == VERIFIED["new_calendar_instants"]
        == VERIFIED["new_original_horoscopes"]
        == VERIFIED["new_real_world_outcomes"]
        == 0
    )


def test_parent_section_tampering_fails_even_if_quote_exists_elsewhere():
    e = copy.deepcopy(
        next(
            e
            for e in VERIFIED["entries"]
            if (e["hexagram"], e["line"]) == ("天地否", 4)
        )
    )
    quote = VERIFIED["conditional_references"][1]["source_quote"]
    e["sections"][1]["text"] = e["sections"][1]["text"].replace(quote, "")
    e["sections"][-1]["text"] += quote
    with pytest.raises(NumerologySourceError):
        ht._commentary_cross_references(e)


def test_tai2_cross_page_reference_does_not_omit_the_continued_sentence():
    t = yao_text("地天泰", 2)
    ref = t["commentary_cross_references"][0]
    assert ref["source_quote"].endswith("長上有損，言語有傷。")
    assert (
        ref["pdf_pages"] == t["text_provenance"]["commentary_pdf_pages"] == [144, 145]
    )
