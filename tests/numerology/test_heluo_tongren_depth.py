"""Primary Tongren readings, literal conditions and unchanged calculation facts."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core import heluo_texts as ht
from fatebridge.core.heluo import _tiaowen, yao_text
from fatebridge.core.heluo_timing import _selected_text
from fatebridge.utils.errors import NumerologySourceError

ROOT = Path(__file__).parents[1] / "fixtures/heluo_tongren_v1"
READINGS = json.loads((ROOT / "verified-readings.json").read_bytes())
FREEZE = json.loads((ROOT / "freeze.json").read_bytes())


def test_reference_keeps_all_six_lines_and_the_first_reader_corrections():
    assert [e["line"] for e in READINGS["entries"]] == list(range(1, 7))
    for name, digest in FREEZE["files"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert FREEZE["frozen_before_production_edits"]
    assert len(json.loads((ROOT / "amendments.json").read_bytes())) == 3
    assert {x["pdf_page"] for x in FREEZE["images"]} == {149, 150, 151}
    for key in (
        "new_independent_second_reviews",
        "new_original_horoscopes",
        "new_physical_reference_instants",
        "new_model_runs",
        "new_real_world_outcomes",
    ):
        assert FREEZE[key] == 0


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
    assert "independent_second_review_pending" in p["commentary_review_status"]
    assert t["commentary_branch_selection"]["selected_section_ids"] == []
    assert p["automatic_branch_selection"] is False
    old = _tiaowen()[entry["hexagram"]]["yao"][str(entry["line"])]
    assert p["inherited_detail"] == old["detail"]
    assert (t["shige"], t["verdict"]) == (old["shige"], old["verdict"])
    assert p["poem_status"] == "inherited_poem_source_unverified"
    assert "commentary_cross_references" not in t
    # This is a selected-line probe, not a dated horoscope or automatic branch.
    selected = _selected_text(
        {"gua": "天火同人", "pos": entry["line"], "lines": [1, 0, 1, 1, 1, 1]},
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
        (1, "歲起逢之", "歲運逢之"),
        (2, "小誠", "小試"),
        (2, "飛騰難為", "飛黃難為"),
        (2, "宗俗朋友", "宗族朋友"),
        (3, "失職之憂", "在仕防失職"),
        (4, "鎮守過域", "鎮守邊城"),
        (4, "專誠守士", "專城守土"),
        (4, "疑忌斜之事", "疑忌爭鬭之事"),
        (5, "或中書", "或為中書"),
        (6, "常出遠郡", "當出遠郡"),
        (6, "消灑", "瀟洒"),
    ],
)
def test_recorded_inherited_errors_are_repaired_without_erasing_the_old_text(
    line, wrong, right
):
    t = yao_text("天火同人", line)
    assert wrong in t["text_provenance"]["inherited_detail"]
    assert wrong not in t["detail"]
    assert right in t["detail"]


def test_negative_xie_cross_page_buxie_and_awkward_source_wording_stay_scoped():
    third = yao_text("天火同人", 3)
    assert "好強逞勢" in third["commentary_sections"][1]["text"]
    assert "心事難測" in third["commentary_sections"][1]["text"]
    assert third["commentary_sections"][1]["applicability"] is None
    fifth = yao_text("天火同人", 5)
    assert "晚雖有遇，福淺禍深" in fifth["commentary_sections"][2]["text"]
    assert "福淺禍深" not in fifth["commentary_sections"][3]["text"]
    assert fifth["text_provenance"]["commentary_pdf_pages"] == [150, 151]
    fourth = yao_text("天火同人", 4)
    assert "士後見榮" in fourth["commentary_sections"][3]["text"]
    assert (
        "不據語意改成辱後見榮"
        in fourth["text_provenance"]["commentary_reading_notes"][0]
    )


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
    entry = next(e for e in data["entries"] if e["hexagram"] == "天火同人")
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
    text = yao_text("天火同人", 4)
    text["commentary_sections"][1]["text"] = "污染"
    text["text_provenance"]["commentary_reading_notes"].clear()
    clean = yao_text("天火同人", 4)
    assert "污染" not in clean["detail"]
    assert clean["text_provenance"]["commentary_reading_notes"]
    assert _tiaowen() == before
