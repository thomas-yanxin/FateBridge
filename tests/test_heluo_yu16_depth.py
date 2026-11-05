"""Yu16 selected-printing text, tentative headers and preserved conditions."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core import heluo_texts as ht
from fatebridge.core.heluo import _tiaowen, yao_text
from tests.heluo_source_facts import HEADER_COUNT, PENDING_COUNT

ROOT = Path(__file__).parent / "fixtures/heluo_yu16_v1"
READINGS = json.loads((ROOT / "verified-readings.json").read_bytes())
FREEZE = json.loads((ROOT / "freeze.json").read_bytes())


def canonical(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def test_header_uncertainty_is_not_suppressed_by_clear_commentary_status():
    view = {
        "text_provenance": {
            "commentary_status": "source_commentary_visually_collated",
            "commentary_pdf_pages": [157],
            "poem_status": "inherited_poem_source_unverified",
            "commentary_review_status": "single_reader; independent_second_review_pending",
            "review_status": "single_reader_header; glyph_choice_unresolved",
            "header_reading_notes": ["The last header glyph is provisional."],
        }
    }
    assert "爻辞仍有字形未决" in ht.text_status_snapshot(view)
    clear = deepcopy(view)
    clear["text_provenance"]["review_status"] = "single_reader_header"
    assert "爻辞仍有字形未决" not in ht.text_status_snapshot(clear)


def test_source_specific_header_review_and_notes_survive_the_public_line_view(
    monkeypatch,
):
    data = deepcopy(ht._collation())
    # Isolated view control: supplied source-reading metadata is independent
    # of the production corpus extension and must not become a global label.
    data["entries"] = [deepcopy(READINGS["headers"][3])]
    monkeypatch.setattr(ht, "_collation", lambda: data)
    text = ht.collated_line("雷地豫", 4, deepcopy(_tiaowen()["雷地豫"]["yao"]["4"]))
    p = text["text_provenance"]
    assert p["review_status"] == READINGS["headers"][3]["review_status"]
    assert p["header_reading_notes"] == READINGS["headers"][3]["reading_notes"]


def test_first_draft_and_withdrawn_proposals_are_retained():
    for name, digest in FREEZE["files"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert FREEZE["frozen_before_production_edits"] is True
    first = json.loads((ROOT / "first-draft-freeze.json").read_bytes())
    assert first["inherited_yu16_prose_exposed"] is False
    assert (
        hashlib.sha256((ROOT / "draft-transcription.json").read_bytes()).hexdigest()
        == first["draft_sha256"]
    )
    amendment = json.loads((ROOT / "postcomparison-amendments.json").read_bytes())
    assert {c["line"] for c in amendment["changes"]} == {1, 2, 6}
    assert all(c["production_error_claimed"] is False for c in amendment["changes"])
    assert (
        FREEZE["unresolved_prose_positions"],
        FREEZE["unresolved_header_positions"],
    ) == (1, 1)


@pytest.mark.parametrize("entry", READINGS["entries"], ids=lambda e: str(e["line"]))
def test_all_printed_parent_conditions_and_old_poem_verdict_are_preserved(entry):
    text = yao_text("雷地豫", entry["line"])
    assert text["detail"] == "".join(s["text"] for s in entry["sections"])
    assert text["commentary_sections"] == [
        dict(s, applicability=None) for s in entry["sections"]
    ]
    p = text["text_provenance"]
    assert p["commentary_pdf_pages"] == entry["pdf_pages"]
    assert p["commentary_reading_notes"] == entry["reading_notes"]
    assert p["commentary_review_status"] == entry["review_status"]
    old = _tiaowen()["雷地豫"]["yao"][str(entry["line"])]
    assert (text["shige"], text["verdict"]) == (old["shige"], old["verdict"])
    assert p["inherited_detail"] == old["detail"]
    assert p["poem_status"] == "inherited_poem_source_unverified"
    assert text["commentary_branch_selection"]["selected_section_ids"] == []


@pytest.mark.parametrize("entry", READINGS["headers"], ids=lambda e: str(e["line"]))
def test_header_has_its_actual_page_review_and_reading_notes(entry):
    text = yao_text("雷地豫", entry["line"])
    assert text["yaoci"] == entry["yaoci"]
    p = text["text_provenance"]
    assert p["pdf_page"] == entry["pdf_page"]
    assert p["review_status"] == entry["review_status"]
    assert p["header_reading_notes"] == entry["reading_notes"]


def test_nested_yin_ming_clause_keeps_its_printed_parent_and_uncertainties():
    text = yao_text("雷地豫", 4)
    buxie = next(s for s in text["commentary_sections"] if s["section_id"] == "buxie")
    assert "若陰命妻葉卦者，得福得壽，但不居正位。" in buxie["text"]
    assert buxie["condition_label"] == "不葉者" and buxie["applicability"] is None
    assert all(s["section_id"] != "female" for s in text["commentary_sections"])
    assert "爻辞仍有字形未决" in ht.text_status_snapshot(text)
    line2 = yao_text("雷地豫", 2)
    assert "固守" in line2["detail"] and "有守" not in line2["detail"]
    assert (
        "glyph_choice_unresolved"
        in line2["text_provenance"]["commentary_review_status"]
    )
    assert "字形未决" in ht.text_status_snapshot(line2)
