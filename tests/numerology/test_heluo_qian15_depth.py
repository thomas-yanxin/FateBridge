"""Qian15 primary readings, literal reference limits and calculation preservation."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core import heluo_texts as ht
from fatebridge.core.heluo import _tiaowen, gua_lines, lines_to_gua, yao_text
from fatebridge.core.heluo_timing import _selected_text
from fatebridge.utils.errors import NumerologySourceError
from tests.support.heluo_source_facts import HEADER_COUNT, PENDING_COUNT

ROOT = Path(__file__).parents[1] / "fixtures/heluo_qian15_v1"
READINGS = json.loads((ROOT / "verified-readings.json").read_bytes())
REFERENCES = json.loads((ROOT / "references.json").read_bytes())["references"]
FREEZE = json.loads((ROOT / "freeze.json").read_bytes())


def canonical(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def test_source_artifacts_preserve_first_misreadings_and_all_six_lines():
    assert [e["line"] for e in READINGS["entries"]] == list(range(1, 7))
    for name, digest in FREEZE["files"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert FREEZE["frozen_before_production_edits"] is True
    assert FREEZE["unresolved_glyph_choices"] == 2
    assert FREEZE["new_independent_second_reviews"] == 0
    assert FREEZE["new_original_horoscopes"] == 0
    assert FREEZE["new_physical_reference_instants"] == 0
    assert FREEZE["new_consultation_model_evaluation_runs"] == 0
    assert FREEZE["new_real_world_outcomes"] == 0
    revision = json.loads((ROOT / "postcomparison-amendments.json").read_bytes())
    assert revision["earlier_line5_proposed_glyph_revision_withdrawn"] is True
    assert revision["unresolved_glyph_choices"] == 2
    assert {r["pdf_page"] for r in FREEZE["images"]} == {154, 155, 156}
    assert all(r["png_bit_depth"] == 1 for r in FREEZE["images"])


@pytest.mark.parametrize("entry", READINGS["entries"], ids=lambda e: str(e["line"]))
def test_complete_primary_prose_preserves_every_condition_and_inherited_roles(entry):
    text = yao_text("地山謙", entry["line"])
    assert text["detail"] == "".join(s["text"] for s in entry["sections"])
    assert text["commentary_sections"] == [
        dict(s, applicability=None) for s in entry["sections"]
    ]
    p = text["text_provenance"]
    assert p["commentary_pdf_pages"] == entry["pdf_pages"]
    assert p["commentary_reading_notes"] == entry["reading_notes"]
    assert p["commentary_review_status"] == entry["review_status"]
    assert p["automatic_branch_selection"] is False
    assert text["commentary_branch_selection"]["selected_section_ids"] == []
    old = _tiaowen()["地山謙"]["yao"][str(entry["line"])]
    assert p["inherited_detail"] == old["detail"]
    assert (text["shige"], text["verdict"]) == (old["shige"], old["verdict"])
    assert p["poem_status"] == "inherited_poem_source_unverified"
    selected = _selected_text(
        {"gua": "地山謙", "pos": entry["line"], "lines": [0, 0, 1, 0, 0, 0]},
        "annual",
    )
    assert selected["heluo_commentary"] == text


@pytest.mark.parametrize("entry", READINGS["headers"], ids=lambda e: str(e["line"]))
def test_headers_use_the_selected_printing(entry):
    text = yao_text("地山謙", entry["line"])
    assert text["yaoci"] == entry["yaoci"]
    assert text["text_provenance"]["pdf_page"] == entry["pdf_page"]


@pytest.mark.parametrize("reference", REFERENCES, ids=lambda r: str(r["source_line"]))
def test_printed_reference_never_acquires_an_unprinted_line_or_replaces_chart(
    reference,
):
    text = yao_text("地山謙", reference["source_line"])
    actual = text["commentary_cross_references"]
    assert len(actual) == 1
    actual = actual[0]
    for key, expected in reference.items():
        assert actual[key] == expected
    assert actual["target_line_source_status"] == "not_printed"
    assert actual["operator"] == "single_line_flip_without_trigram_swap"
    assert gua_lines("坤", "艮") == reference["source_lines"]
    flipped = reference["source_lines"][:]
    flipped[reference["source_line"] - 1] ^= 1
    assert flipped == reference["target_lines"]
    assert lines_to_gua(flipped)["name"] == reference["target_hexagram"]


@pytest.mark.parametrize("reference", REFERENCES, ids=lambda r: str(r["source_line"]))
def test_status_uses_actual_condition_and_actual_printed_quote(reference):
    # A view input from the frozen literal reference, independent of the source
    # corpus extension. This reproduces the formerly hardcoded Dayou-only text.
    view = {
        "text_provenance": {
            "commentary_status": "source_commentary_visually_collated",
            "commentary_pdf_pages": reference["pdf_pages"],
            "poem_status": "inherited_poem_source_unverified",
            "commentary_review_status": "single_reader; independent_review_pending",
        },
        "commentary_cross_references": [deepcopy(reference)],
    }
    note = ht.text_status_snapshot(view)
    assert reference["condition_text"] in note
    assert "凶則" not in note
    assert reference["target_hexagram"] in note
    assert "未指定目标爻" in note
    if reference["target_quote"]:
        assert reference["target_quote"] in note
        assert "只印卦名" not in note
    assert "None爻" not in note


@pytest.mark.parametrize("line", [2, 5])
def test_unsettled_glyph_is_visible_without_becoming_a_negative_branch(line):
    text = yao_text("地山謙", line)
    assert (
        "glyph_choice_unresolved" in text["text_provenance"]["commentary_review_status"]
    )
    assert "字形未决" in ht.text_status_snapshot(text)
    assert text["commentary_branch_selection"]["selected_section_ids"] == []


def test_existing_dayou_uncertainty_is_also_visible_from_its_actual_status():
    text = yao_text("火天大有", 4)
    assert (
        "glyph_disagreement_unresolved"
        in text["text_provenance"]["commentary_review_status"]
    )
    assert "字形未决" in ht.text_status_snapshot(text)


@pytest.mark.parametrize("fault", ["parent", "text", "header"])
def test_nonempty_forged_source_or_swapped_parent_still_returns_source503(
    fault, monkeypatch, tmp_path
):
    path = ht.COLLATION_PATH if fault == "header" else ht.COMMENTARY_PATH
    data = json.loads(path.read_bytes())
    entry = next(e for e in data["entries"] if e["hexagram"] == "地山謙")
    if fault == "header":
        entry["yaoci"] = "借另一部经文替代非空正文"
    elif fault == "parent":
        entry["sections"][1], entry["sections"][2] = (
            entry["sections"][2],
            entry["sections"][1],
        )
    else:
        entry["sections"][3]["text"] = "省略凶者而宣称自动适用"
    altered = tmp_path / "forged.json"
    altered.write_text(json.dumps(data, ensure_ascii=False))
    monkeypatch.setattr(
        ht, "COLLATION_PATH" if fault == "header" else "COMMENTARY_PATH", altered
    )
    ht._collation.cache_clear()
    ht._commentary_collation.cache_clear()
    try:
        with pytest.raises(NumerologySourceError):
            yao_text("地山謙", 1)
    finally:
        ht._collation.cache_clear()
        ht._commentary_collation.cache_clear()
