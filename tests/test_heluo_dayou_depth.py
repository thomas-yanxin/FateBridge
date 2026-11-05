"""Primary Dayou readings, literal conditions and unchanged calculation facts."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core import heluo_texts as ht
from fatebridge.core.heluo import _tiaowen, yao_text
from fatebridge.core.heluo_timing import _selected_text
from fatebridge.utils.errors import NumerologySourceError
from tests.heluo_source_facts import HEADER_COUNT, PENDING_COUNT

ROOT = Path(__file__).parent / "fixtures/heluo_dayou_v1"
READINGS = json.loads((ROOT / "verified-readings.json").read_bytes())
FREEZE = json.loads((ROOT / "freeze.json").read_bytes())


def canonical(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def test_reference_keeps_all_six_lines_and_the_first_reader_corrections():
    assert [e["line"] for e in READINGS["entries"]] == list(range(1, 7))
    for name, digest in FREEZE["files"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert FREEZE["frozen_before_production_edits"] is False
    assert FREEZE["original_reference_frozen_before_production_edits"] is True
    assert FREEZE["postimplementation_native_amendment"] is True
    assert len(json.loads((ROOT / "amendments.json").read_bytes())) == 8
    assert {x["pdf_page"] for x in FREEZE["images"]} == {151, 152, 153}
    for key in (
        "new_original_horoscopes",
        "new_physical_reference_instants",
        "new_consultation_model_evaluation_runs",
        "new_real_world_outcomes",
    ):
        assert FREEZE[key] == 0
    assert FREEZE["new_independent_second_reviews"] == 1
    assert FREEZE["new_model_runs"] == 1
    assert FREEZE["independent_human_expert_reviews"] == 0
    assert FREEZE["unresolved_model_review_glyphs"] == 1
    assert (
        hashlib.sha256(
            (ROOT / "independent-model-reread/first-reading.json").read_bytes()
        ).hexdigest()
        == "3008fc843ae771a34597dc1e1eecb31579f5a58f57856379c60b977aec552aa9"
    )


@pytest.mark.parametrize("entry", READINGS["entries"], ids=lambda e: str(e["line"]))
def test_complete_prose_and_all_parent_conditions_use_the_primary_reading(entry):
    t = yao_text(entry["hexagram"], entry["line"])
    assert t["detail"] == "".join(s["text"] for s in entry["sections"])
    assert t["commentary_sections"] == [
        dict(s, applicability=None) for s in entry["sections"]
    ]
    p = t["text_provenance"]
    assert p["commentary_pdf_pages"] == entry["pdf_pages"]
    assert p["commentary_reading_notes"] == entry["reading_notes"]
    assert (
        "independent_model_source_only_reread_completed"
        in p["commentary_review_status"]
    )
    assert "human_expert_review_pending" in p["commentary_review_status"]
    assert t["commentary_branch_selection"]["selected_section_ids"] == []
    assert p["automatic_branch_selection"] is False
    old = _tiaowen()[entry["hexagram"]]["yao"][str(entry["line"])]
    assert p["inherited_detail"] == old["detail"]
    assert (t["shige"], t["verdict"]) == (old["shige"], old["verdict"])
    assert p["poem_status"] == "inherited_poem_source_unverified"
    assert bool(t.get("commentary_cross_references")) is (entry["line"] == 3)
    # This is a selected-line probe, not a dated horoscope or automatic branch.
    selected = _selected_text(
        {"gua": "火天大有", "pos": entry["line"], "lines": [1, 1, 1, 1, 0, 1]},
        "annual",
    )
    assert selected["heluo_commentary"] == t


@pytest.mark.parametrize("entry", READINGS["headers"], ids=lambda e: str(e["line"]))
def test_header_does_not_inherit_other_editions_character_substitution(entry):
    t = yao_text(entry["hexagram"], entry["line"])
    assert t["yaoci"] == entry["yaoci"]
    assert t["text_provenance"]["pdf_page"] == entry["pdf_page"]


@pytest.mark.parametrize(
    "line,wrong,right",
    [
        (1, "此爻其知", "此爻是知"),
        (1, "常隨毀辱", "常遭毀辱"),
        (1, "災管", "災害"),
        (2, "關官驛車", "閑官驛車"),
        (2, "才谷豐裕", "財穀豐裕"),
        (2, "軟車", "輭車"),
        (3, "貪謀私已", "貪謀私己"),
        (3, "變（睽）", "變睽"),
        (4, "知所志成", "知所戒"),
        (4, "僭越之禍", "僭竊之禍"),
        (5, "因徒施", "恩徒施"),
        (6, "足躡以契", "足以契"),
    ],
)
def test_inherited_source_errors_keep_the_old_reading_and_repair_the_new(
    line, wrong, right
):
    t = yao_text("火天大有", line)
    assert wrong in t["text_provenance"]["inherited_detail"]
    assert wrong not in t["detail"] and right in t["detail"]


def test_source_condition_labels_do_not_predict_polarity_or_change_another_section():
    second = yao_text("火天大有", 2)
    assert "亦有福有壽" in second["commentary_sections"][2]["text"]
    assert second["commentary_sections"][2]["applicability"] is None
    assert "不利老壽" in second["commentary_sections"][3]["text"]
    assert "不利老壽" not in second["commentary_sections"][2]["text"]
    for line, term, pages in [(1, "庶免傾危", [151, 152]), (4, "免褫革", [152, 153])]:
        t = yao_text("火天大有", line)
        assert term in t["commentary_sections"][3]["text"]
        assert t["text_provenance"]["commentary_pdf_pages"] == pages


def test_unnumbered_kui_reference_is_conditional_not_a_natal_transform():
    from fatebridge.core.heluo import lines_to_gua, transform_houtian

    t = yao_text("火天大有", 3)
    assert "凶則變睽刑傷難免" in t["detail"]
    assert "變哭" not in t["detail"]
    ref = t["commentary_cross_references"][0]
    assert ref["target_hexagram"] == "火澤睽"
    assert ref["target_line"] is ref["target_quote"] is None
    assert ref["target_line_source_status"] == "not_printed"
    assert ref["source_section_id"] == "annual"
    assert ref["source_condition_label"] == "歲運逢之"
    assert ref["condition_text"] == "凶則"
    assert ref["source_context_text"].startswith("在庶俗")
    assert ref["applicability"] is None
    assert ref["automatic_application"] is ref["replaces_chart"] is False
    original = [1, 1, 1, 1, 0, 1]
    flipped = [1, 1, 0, 1, 0, 1]
    assert ref["source_lines"] == original and ref["target_lines"] == flipped
    assert lines_to_gua(flipped)["name"] == "火澤睽"
    formal = transform_houtian("火天大有", original, 3, True)
    assert (formal["name"], formal["yuan"]) == ("澤火革", 6)
    assert ref["target_hexagram"] != formal["name"]
    assert "未指定目标爻" in ht.text_status_snapshot(t)
    assert "None爻" not in ht.text_status_snapshot(t)


@pytest.mark.parametrize("layer", ["header", "commentary"])
def test_new_nonempty_source_corruption_cannot_keep_the_collated_identity(
    layer, monkeypatch, tmp_path
):
    name, loader, reason = (
        ("COLLATION_PATH", ht._collation, "invalid_heluo_header_collation")
        if layer == "header"
        else (
            "COMMENTARY_PATH",
            ht._commentary_collation,
            "invalid_heluo_commentary_collation",
        )
    )
    data = json.loads(getattr(ht, name).read_bytes())
    entry = next(e for e in data["entries"] if e["hexagram"] == "火天大有")
    if layer == "header":
        entry["yaoci"] = "非空錯文"
    else:
        entry["sections"][1]["text"] = "葉者非空錯文"
    path = tmp_path / "corrupt.json"
    path.write_text(json.dumps(data, ensure_ascii=False))
    loader.cache_clear()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(ht, name, path)
            with pytest.raises(NumerologySourceError) as error:
                loader()
            assert error.value.reason == reason
    finally:
        loader.cache_clear()


def test_selections_remain_detached_from_the_inherited_and_collated_caches():
    before = deepcopy(_tiaowen())
    text = yao_text("火天大有", 4)
    text["commentary_sections"][1]["text"] = "污染"
    text["text_provenance"]["commentary_reading_notes"].clear()
    clean = yao_text("火天大有", 4)
    assert "污染" not in clean["detail"]
    assert clean["text_provenance"]["commentary_reading_notes"]
    assert _tiaowen() == before


def test_independent_review_repairs_literal_errors_and_retains_uncertain_glyph():
    for line, right, wrong in [
        (2, "或曰輭車之兆", "輿車事之兆"),
        (4, "守常", "守當"),
        (5, "反召怨", "反招怨"),
        (3, "招灾難", "招災難"),
    ]:
        text = yao_text("火天大有", line)
        assert right in text["detail"] and wrong not in text["detail"]
    p = yao_text("火天大有", 4)["text_provenance"]
    assert "glyph_disagreement_unresolved" in p["commentary_review_status"]
    assert any("矜／衿未決" in note for note in p["commentary_reading_notes"])
    decisions = json.loads((ROOT / "independent-review-adjudication.json").read_bytes())
    assert decisions["unresolved_glyphs"] == 1
    assert not decisions["full_book_review_completed"]
