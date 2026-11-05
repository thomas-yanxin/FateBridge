"""Twelve source-read commentaries; conditional branches stay unevaluated."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import heluo_texts
from fatebridge.core.heluo import _tiaowen, yao_text
from fatebridge.core.heluo_timing import _selected_text
from fatebridge.utils.errors import NumerologySourceError
from tests.heluo_source_facts import HEADER_COUNT, PENDING_COUNT

ROOT = Path(__file__).parent / "fixtures/heluo_tunmeng_v1"
REF = json.loads((ROOT / "reference.json").read_text())
VERIFIED = json.loads((ROOT / "verified-readings.json").read_text())


@pytest.mark.parametrize(
    "row", VERIFIED["entries"], ids=lambda e: e["hexagram"] + str(e["line"])
)
def test_complete_source_reading_is_used_for_the_actual_selected_line(row):
    text = yao_text(row["hexagram"], row["line"])
    assert text["detail"] == "".join(s["text"] for s in row["sections"])
    assert text["text_provenance"]["commentary_pdf_pages"] == row["pdf_pages"]
    assert text["text_provenance"]["commentary_reading_notes"] == row["reading_notes"]
    expected = [dict(s, applicability=None) for s in row["sections"]]
    assert text["commentary_sections"] == expected
    assert text["commentary_branch_selection"]["status"] == "not_evaluated"
    assert text["commentary_branch_selection"]["selected_section_ids"] == []
    inherited = _tiaowen()[row["hexagram"]]["yao"][str(row["line"])]
    assert text["text_provenance"]["inherited_detail"] == inherited["detail"]
    assert text["verdict"] == inherited["verdict"]
    assert text["text_provenance"]["poem_status"] == "source_poems_visually_collated"
    assert text["text_provenance"]["inherited_shige"] == inherited["shige"]
    assert (
        text["text_provenance"]["poem_source_pdf_sha256"]
        != text["text_provenance"]["commentary_source_pdf_sha256"]
    )
    if row["hexagram"] == "山水蒙":
        # The earlier commentary fixture predates the separately frozen poem
        # witness. Keep its inherited text while checking that new literal.
        source = json.loads(
            (
                Path(__file__).parent
                / "fixtures/heluo_sui17_meng4_v1/verified-readings.json"
            ).read_bytes()
        )
        poems = next(e["poems"] for e in source["poems"] if e["line"] == row["line"])
        assert text["shige"] == "\n".join(poem["text"] for poem in poems)
    assert text["text_provenance"]["poem_presence_in_reviewed_sections"] is False
    timed = _selected_text(
        dict(
            gua=row["hexagram"],
            pos=row["line"],
            changed_pos=7 - row["line"],
            lines=(
                [1, 0, 0, 0, 1, 0]
                if row["hexagram"] == "水雷屯"
                else [0, 1, 0, 0, 0, 1]
            ),
        ),
        "day_ordinal",
    )
    assert timed["heluo_commentary"] == text


def test_corrections_do_not_normalize_the_primary_edition_into_expected_meaning():
    tun = yao_text("水雷屯", 1)
    assert (
        "顯達之選" in tun["detail"]
        and "顯越之選" in tun["text_provenance"]["inherited_detail"]
    )
    assert (
        "建明之議" in tun["detail"]
        and "建明之義" in tun["text_provenance"]["inherited_detail"]
    )
    army = yao_text("水雷屯", 2)
    assert (
        "禦兵邊" in army["detail"]
        and "禦兵寇" in army["text_provenance"]["inherited_detail"]
    )
    four = yao_text("水雷屯", 4)
    assert (
        "雖遇提攜" in four["detail"]
        and "難遇提攜" in four["text_provenance"]["inherited_detail"]
    )
    meng = yao_text("山水蒙", 1)
    assert (
        "掌無權" in meng["detail"]
        and "掌兵權" in meng["text_provenance"]["inherited_detail"]
    )
    assert "詳君子" in meng["detail"] and "誨君子" not in meng["detail"]
    girl = yao_text("山水蒙", 3)
    assert (
        "龍妾" in girl["detail"]
        and "寵妾" in girl["text_provenance"]["inherited_detail"]
    )
    assert "燕僻" in girl["detail"] and "燕儔" not in girl["detail"]
    upper = yao_text("山水蒙", 6)
    assert "蘊其用" in upper["detail"] and "擅其用" not in upper["detail"]


def test_nested_conditions_stay_in_their_printed_parent_and_are_not_applied():
    girl = yao_text("山水蒙", 3)
    assert "女命則為龍妾" in girl["commentary_sections"][1]["text"]
    assert [s["section_id"] for s in girl["commentary_sections"]] == [
        "opening",
        "xie",
        "buxie",
        "annual",
    ]
    assert "數凶者" in yao_text("水雷屯", 6)["commentary_sections"][-1]["text"]
    assert "幼而明敏" in yao_text("山水蒙", 5)["commentary_sections"][1]["text"]
    assert all(s["applicability"] is None for s in girl["commentary_sections"])


def test_reference_reinspection_keeps_draft_withdrawals_and_does_not_inflate_evidence():
    assert (
        VERIFIED["draft_sha256"]
        == hashlib.sha256((ROOT / "reference.json").read_bytes()).hexdigest()
    )
    assert (
        VERIFIED["amendments_sha256"]
        == hashlib.sha256((ROOT / "amendments.json").read_bytes()).hexdigest()
    )
    amended = copy.deepcopy(REF["entries"])
    amendments = json.loads((ROOT / "amendments.json").read_text())
    assert len(amendments["replacements"]) == 8
    for change in amendments["replacements"]:
        e = next(
            e
            for e in amended
            if (e["hexagram"], e["line"]) == (change["hexagram"], change["line"])
        )
        s = next(s for s in e["sections"] if s["section_id"] == change["section_id"])
        assert s["text"].count(change["old"]) == 1
        s["text"] = s["text"].replace(change["old"], change["new"])
    for notes in amendments["reading_notes"]:
        e = next(
            e
            for e in amended
            if (e["hexagram"], e["line"]) == (notes["hexagram"], notes["line"])
        )
        e["reading_notes"] = notes["notes"]
    assert amended == VERIFIED["entries"]
    assert len(REF["images"]) == 6 and REF["new_complete_line_commentaries"] == 12
    assert (
        REF["new_original_horoscopes"]
        == REF["new_calendar_instants"]
        == REF["new_independent_reviewers"]
        == REF["new_source_editions"]
        == 0
    )
    for w in REF["images"]:
        assert (
            hashlib.sha256((ROOT / w["file"]).read_bytes()).hexdigest() == w["sha256"]
        )
    old = ROOT.parent / "numerology_nlc_v1/commentary-reference.json"
    assert (
        hashlib.sha256(old.read_bytes()).hexdigest() == REF["previous_reference_sha256"]
    )
    assert (
        heluo_texts.commentary_collation_summary()["collated_line_commentaries"]
        == HEADER_COUNT
    )
    assert (
        heluo_texts.commentary_collation_summary()["pending_line_commentaries"]
        == PENDING_COUNT
    )


@pytest.mark.parametrize("layer", ["header", "commentary"])
@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "json",
        "identity",
        "empty",
        "removed",
        "duplicate",
        "bool_line",
        "blank_text",
    ],
)
def test_damaged_or_incomplete_source_is_an_internal_source_fault(
    layer, fault, tmp_path, monkeypatch
):
    path_name, loader, reason = (
        ("COLLATION_PATH", heluo_texts._collation, "invalid_heluo_header_collation")
        if layer == "header"
        else (
            "COMMENTARY_PATH",
            heluo_texts._commentary_collation,
            "invalid_heluo_commentary_collation",
        )
    )
    data = json.loads(getattr(heluo_texts, path_name).read_text())
    p = tmp_path / "source.json"
    if fault == "identity":
        data["source_pdf_sha256"] = "0" * 64
    if fault == "empty":
        data["entries"] = []
    if fault == "removed":
        data["entries"].pop()
    if fault == "duplicate":
        data["entries"][-1] = data["entries"][0]
    if fault == "bool_line":
        data["entries"][0]["line"] = True
    if fault == "blank_text":
        if layer == "header":
            data["entries"][0]["yaoci"] = " "
        else:
            data["entries"][0]["sections"][0]["text"] = " "
    if fault != "missing":
        p.write_text("{" if fault == "json" else json.dumps(data))
    loader.cache_clear()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(heluo_texts, path_name, p)
            with pytest.raises(NumerologySourceError) as err:
                loader()
            assert err.value.reason == reason
    finally:
        loader.cache_clear()


@pytest.mark.parametrize(
    "fault", ["wrong_label", "missing_branch", "wrong_order", "invalid_page"]
)
def test_commentary_preserves_literal_sections_and_pages(fault, tmp_path, monkeypatch):
    data = json.loads(heluo_texts.COMMENTARY_PATH.read_text())
    e = data["entries"][0]
    if fault == "wrong_label":
        e["sections"][1]["condition_label"] = "不葉者"
    if fault == "missing_branch":
        e["sections"].pop(2)
    if fault == "wrong_order":
        e["sections"][1], e["sections"][2] = e["sections"][2], e["sections"][1]
    if fault == "invalid_page":
        e["pdf_pages"] = [True]
    p = tmp_path / "source.json"
    p.write_text(json.dumps(data))
    heluo_texts._commentary_collation.cache_clear()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(heluo_texts, "COMMENTARY_PATH", p)
            with pytest.raises(NumerologySourceError):
                heluo_texts._commentary_collation()
    finally:
        heluo_texts._commentary_collation.cache_clear()


def test_finite_audit_rejects_normalizing_a_literal_primary_reading(monkeypatch):
    from scripts import audit_numerology as audit

    original = audit.yao_text

    def normalize_primary(gua, pos):
        text = original(gua, pos)
        if gua == "山水蒙" and pos == 3:
            text["detail"] = text["detail"].replace("龍妾", "寵妾")
        return text

    monkeypatch.setattr(audit, "yao_text", normalize_primary)
    result = audit.commentary_collation_checks()
    assert result["checks_passed"] is False
    assert {"kind": "tunmeng_complete_commentary", "case": ["山水蒙", 3]} in result[
        "failures"
    ]
