"""Shi/Bi source scope, conditional quotation and preserved natal operators."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import heluo
from fatebridge.core import heluo_texts as ht
from fatebridge.core.heluo import _tiaowen, transform_houtian, yao_text
from fatebridge.core.heluo_timing import _selected_text
from fatebridge.utils.errors import NumerologySourceError
from tests.heluo_source_facts import HEADER_COUNT

ROOT = Path(__file__).parent / "fixtures/heluo_shibi_v1"
DRAFT = json.loads((ROOT / "reference.json").read_bytes())
VERIFIED = json.loads((ROOT / "verified-readings.json").read_bytes())


def test_missing_column_draft_and_character_withdrawals_are_reproducible():
    assert (
        hashlib.sha256((ROOT / "reference.json").read_bytes()).hexdigest()
        == VERIFIED["draft_sha256"]
    )
    assert (
        hashlib.sha256((ROOT / "amendments.json").read_bytes()).hexdigest()
        == VERIFIED["amendments_sha256"]
    )
    entries = copy.deepcopy(DRAFT["entries"])
    amendments = json.loads((ROOT / "amendments.json").read_bytes())
    assert len(amendments) == 15
    for amendment in amendments:
        e = next(
            e
            for e in entries
            if (e["hexagram"], e["line"]) == (amendment["hexagram"], amendment["line"])
        )
        idx = amendment["section_index"]
        assert e["sections"][idx] == amendment["before"]
        e["sections"][idx] = amendment["after"]
    assert [{k: v for k, v in e.items() if k != "reading_notes"} for e in entries] == [
        {k: v for k, v in e.items() if k != "reading_notes"}
        for e in VERIFIED["entries"]
    ]
    for image in DRAFT["images"]:
        assert (
            hashlib.sha256((ROOT / image["file"]).read_bytes()).hexdigest()
            == image["sha256"]
        )
    assert VERIFIED["source_commentary_pages"] == list(range(134, 139))
    assert all(139 not in e["pdf_pages"] for e in VERIFIED["entries"])
    assert (
        VERIFIED["new_original_horoscopes"]
        == VERIFIED["new_calendar_instants"]
        == VERIFIED["new_real_world_outcomes"]
        == VERIFIED["independent_second_reviews"]
        == 0
    )
    assert ht.collation_summary()["collated_line_headers"] == HEADER_COUNT
    assert ht.commentary_collation_summary()["collated_poems"] == 0


def test_whole_gua_najia_is_removed_only_from_misplaced_bi2_commentary():
    from fatebridge.core.heluo_months import month_affinity

    t = yao_text("水地比", 2)
    assert "戊戌" in t["text_provenance"]["inherited_detail"]
    assert "戊戌" not in t["detail"]
    assert "福澤之厚，言發於真見，行出於本心" in t["detail"]
    # Scope correction cannot erase the source's separately registered whole-gua clause.
    result = month_affinity(
        {
            "xian": dict(name="水地比", lines=[0, 0, 0, 0, 1, 0]),
            "hou": dict(name="地水師", lines=[0, 1, 0, 0, 0, 0]),
        },
        "申",
        heluo.MONTH_GUA,
    )
    bi = result["phases"][0]
    assert bi["gua"] == "水地比"
    assert bi["natal_najia_clause"]["month_numbers"] == [7]
    assert bi["natal_najia_clause"]["najia"] is None
    assert bi["natal_najia_clause"]["match"] is None


def test_source_specific_readings_and_nested_conditions_survive():
    assert "才德大弱，大衆不服" in yao_text("地水師", 3)["detail"]
    assert "或服丁憂" in yao_text("地水師", 3)["detail"]
    assert "不倖成" in yao_text("地水師", 4)["detail"]
    shi5 = yao_text("地水師", 5)
    assert [s["section_id"] for s in shi5["commentary_sections"]] == [
        "opening",
        "xie",
        "buxie",
        "annual",
    ]
    assert "不葉者或居村野" in shi5["commentary_sections"][2]["text"]
    assert "下此則妄言妄動" in shi5["commentary_sections"][2]["text"]
    assert "先審後發，靖亂拯溺" in shi5["commentary_sections"][1]["text"]
    assert (
        "諫政" in shi5["detail"]
        and "職業日繁" in shi5["detail"]
        and "小子之阨" in shi5["detail"]
    )
    assert "少公道，恃時勢" in yao_text("地水師", 6)["detail"]
    assert "大抵宜防讒佞" in yao_text("地水師", 6)["detail"]
    assert "不歷艱辛，僧道技藝" in yao_text("水地比", 1)["detail"]
    assert "刑孝，多般撓括" in yao_text("水地比", 3)["detail"]
    assert (
        "罟網之徒" in yao_text("水地比", 5)["detail"]
        and "先逆後順" in yao_text("水地比", 5)["detail"]
    )
    assert "文清身正" in yao_text("水地比", 6)["detail"]


def test_shi3_conditional_sheng_quote_never_replaces_the_normal_houtian():
    r = VERIFIED["conditional_reference"]
    before = r["source_lines"][:]
    actual = yao_text("地水師", 3)["commentary_cross_references"][0]
    assert actual == {k: v for k, v in r.items() if k != "comparison_normal_houtian"}
    for ling in (True, False):
        hou = transform_houtian("地水師", before, 3, ling)
        assert hou == dict(name="風地觀", lines=[0, 0, 0, 0, 1, 1], yuan=6)
    assert before == [0, 1, 0, 0, 0, 0]
    assert actual["applicability"] is None and actual["automatic_application"] is False
    assert actual["replaces_chart"] is False
    assert "commentary_cross_references" not in yao_text("地水師", 2)
    # It is a quoted phrase, not a newly collated target commentary.
    assert (
        yao_text("地風升", 3)["text_provenance"]["commentary_status"]
        == "inherited_transcription_collation_pending"
    )


@pytest.mark.parametrize(
    "fault", ["swapped_target", "wrong_source_bits", "source_quote"]
)
def test_inconsistent_conditional_reference_fails_closed(fault, monkeypatch):
    from fatebridge.core import heluo_hexagrams

    entry = copy.deepcopy(
        next(
            e
            for e in VERIFIED["entries"]
            if (e["hexagram"], e["line"]) == ("地水師", 3)
        )
    )
    if fault == "swapped_target":
        monkeypatch.setattr(
            heluo_hexagrams, "lines_to_gua", lambda lines: dict(name="風地觀")
        )
    elif fault == "wrong_source_bits":
        monkeypatch.setattr(
            heluo_hexagrams, "gua_lines", lambda up, low: [0, 0, 0, 0, 1, 0]
        )
    else:
        entry["sections"][-1]["text"] = entry["sections"][-1]["text"].replace(
            "三爻", "二爻"
        )
    with pytest.raises(NumerologySourceError) as exc:
        ht._commentary_cross_references(entry)
    assert exc.value.reason == "invalid_heluo_commentary_collation"


def test_finite_audit_detects_dropped_conditional_link(monkeypatch):
    from scripts import audit_numerology as audit

    monkeypatch.setattr(ht, "_commentary_cross_references", lambda entry: [])
    result = audit.shibi_commentary_checks()
    assert not result["checks_passed"]
    assert dict(kind="shibi_conditional_reference") in result["failures"]
