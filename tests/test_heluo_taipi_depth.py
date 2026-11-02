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
from tests.heluo_current_source_reference import HEADER_COUNT, PENDING_COUNT
from tests.heluo_guan_shi_revision_reference import REVISION as R84_REVISION

ROOT = Path(__file__).parent / "fixtures/heluo_taipi_v1"
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


@pytest.mark.parametrize(
    "ref",
    VERIFIED["conditional_references"],
    ids=lambda e: e["source_hexagram"] + str(e["source_line"]),
)
def test_reference_is_bound_to_its_actual_parent_not_the_natal_transform(ref):
    t = yao_text(ref["source_hexagram"], ref["source_line"])
    assert t["commentary_cross_references"] == [ref]
    section = next(
        s
        for s in t["commentary_sections"]
        if s["section_id"] == ref["source_section_id"]
    )
    assert ref["source_quote"] in section["text"]
    assert section["condition_label"] == ref["source_condition_label"]
    assert section["applicability"] is ref["applicability"] is None
    for half in (False, True):
        normal = transform_houtian(
            ref["source_hexagram"], ref["source_lines"], ref["source_line"], half
        )
        assert (normal["name"], normal["yuan"]) != (
            ref["target_hexagram"],
            ref["target_line"],
        )
    assert ref["automatic_application"] is ref["replaces_chart"] is False
    target_key = f"{ref['target_hexagram']}:{ref['target_line']}"
    target = yao_text(ref["target_hexagram"], ref["target_line"])
    if target_key in R84_REVISION["record_extensions"]:
        frozen_target = R84_REVISION["record_extensions"][target_key]["fields"]
        assert target["detail"] == frozen_target["detail"]
        assert target["commentary_sections"] == frozen_target["commentary_sections"]
        assert (
            "independent_second_review_pending"
            in target["text_provenance"]["commentary_review_status"]
        )
        assert target["commentary_branch_selection"]["selected_section_ids"] == []
        assert all(s["applicability"] is None for s in target["commentary_sections"])
    else:
        assert "pending" in target["text_provenance"]["commentary_status"]


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
    for entries, key in [
        (ht._commentary_collation()["entries"][:60], "previous_sixty_entries_sha256"),
        (ht._collation()["entries"][:60], "previous_sixty_headers_sha256"),
    ]:
        assert (
            hashlib.sha256(
                json.dumps(
                    entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
            == VERIFIED[key]
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
