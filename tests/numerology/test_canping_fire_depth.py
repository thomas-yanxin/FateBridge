"""Fire table follows the chosen primary edition, including unresolved headers."""

import copy
import csv
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import canping_texts as texts
from fatebridge.core.canping_texts import lookup_record
from fatebridge.utils.errors import NumerologySourceError

ROOT = Path(__file__).parents[1] / "fixtures/canping_fire_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())
ROWS = list(csv.DictReader((ROOT / "literal.tsv").open(), delimiter="\t"))
SPECIAL = {
    (r["number"], r["kind"]): r["state"] for r in REFERENCE["expected_special_states"]
}
HEADERS = {r["number"] for r in REFERENCE["number_reading_uncertainties"]}
CELLS = [(row, kind) for row in ROWS for kind in ("male", "female", "luck")]
REREADINGS = {
    (c["number"], c["kind"]): c
    for c in json.loads(
        (ROOT.parent / "canping_fire_rereading_v1/reference.json").read_text()
    )["cells"]
}


@pytest.mark.parametrize("row,kind", CELLS)
def test_all_fire_cells_keep_literal_text_column_page_and_provisional_status(row, kind):
    n = int(row["number"])
    r = lookup_record("火", n, kind)
    s = r["selection"]
    revision = REREADINGS.get((n, kind))
    assert r["text"] == (revision["text"] if revision else row[kind])
    if revision:
        assert s["reading_revision"]["previous_text"] == row[kind]
    assert s["number"] == n and s["kind"] == kind
    assert s["source_pdf_page"] == int(row["pdf_page"])
    assert s["cell_status"] == (
        revision["state"]
        if revision
        else SPECIAL.get((n, kind), "source_cell_visually_collated")
    )
    if s["cell_status"] == "source_reading_uncertain":
        assert s["reading_uncertainties"]
        assert ("editorial_unknown_marker" in s) == ("□" in row[kind])
    if n in HEADERS:
        assert s["number_attribution_status"] == "provisional_inherited_key"
        assert s["number_reading_uncertainties"]
        assert s["cell_status"] == "source_reading_uncertain"
    if n == 2838:
        assert s["inherited_number"] == 3838


def test_fire_and_global_counts_exclude_uncertain_headers_without_double_counting():
    assert len(ROWS) == len({r["number"] for r in ROWS}) == 78
    assert len(CELLS) == 234
    assert (
        hashlib.sha256((ROOT / "literal.tsv").read_bytes()).hexdigest()
        == REFERENCE["literal_sha256"]
    )
    assert len(REFERENCE["images"]) == 9
    for page in REFERENCE["images"]:
        assert (
            hashlib.sha256((ROOT / page["file"]).read_bytes()).hexdigest()
            == page["sha256"]
        )
    assert sum("□" in row[k] for row, k in CELLS) == 12
    assert len(HEADERS) * 3 == 6
    assert sum(int(row["number"]) in HEADERS and "□" in row[k] for row, k in CELLS) == 1
    assert len(REFERENCE["uncertain_cells"]) == 17
    assert REFERENCE["new_unambiguous_fire_cells"] == 213
    summary = texts.collation_summary()
    assert summary["collated_cells"] == 1123
    assert summary["unresolved_reading_cells"] == 47
    assert summary["unexamined_cells"] == 0
    assert summary["pending_cells"] == 47
    assert summary["visually_examined_cells"] == 1170
    assert summary["part_coverage"]["火"] == {
        "total_cells": 234,
        "visually_examined_cells": 234,
        "collated_cells": 223,
        "unresolved_reading_cells": 11,
        "unexamined_cells": 0,
    }
    assert sum(p["collated_cells"] for p in summary["part_coverage"].values()) == 1123
    assert summary["total_cells"] == 1170
    assert REFERENCE["new_classical_birth_examples"] == 0
    assert REFERENCE["new_independent_calendar_instants"] == 0
    assert REFERENCE["new_real_world_outcomes"] == 0


@pytest.mark.parametrize("number", [2743, 2248])
@pytest.mark.parametrize("kind", ["male", "female", "luck"])
def test_clear_body_or_printed_circles_do_not_certify_an_obscured_header(number, kind):
    selected = lookup_record("火", number, kind)["selection"]
    assert selected["number"] == number
    assert selected["number_attribution_status"] == "provisional_inherited_key"
    assert selected["cell_status"] == "source_reading_uncertain"
    assert selected["row_status"] == "present"
    assert "inherited_number" not in selected
    assert selected["reading_notes"]


def test_literal_readings_and_printed_circles_are_not_normalized_to_familiar_phrases():
    assert lookup_record("火", 2638, "male")["text"] == "鐵船再江水，船內有魚遊。"
    assert lookup_record("火", 2244, "luck")["text"] == "百煉忘真金，自然添火力。"
    assert lookup_record("火", 2444, "female")["text"] == "山水珊瑚樹，春風費力栽。"
    assert lookup_record("火", 3351, "male")["text"] == "彤弓架朱箭，用卵石麒麟。"
    assert lookup_record("火", 3351, "luck")["text"] == "花間逢○○，多不減芸香。"
    assert lookup_record("火", 2743, "luck")["text"] == "意欲搆舟子，得乘□。"


@pytest.mark.parametrize("change", ["empty_header_reason", "clear_one_column"])
def test_obscured_number_cannot_be_counted_as_a_confirmed_column(monkeypatch, change):
    original = texts._loaded
    data = copy.deepcopy(original(texts.COLLATION_PATH))
    row = next(
        r
        for r in data["data"]["entries"]
        if r["element"] == "火" and r["number"] == 2743
    )
    if change == "empty_header_reason":
        row["number_reading_uncertainties"] = []
    else:
        row["reading_uncertainties"].pop("male")
    monkeypatch.setattr(
        texts,
        "_loaded",
        lambda path: data if path == texts.COLLATION_PATH else original(path),
    )
    with pytest.raises(ValueError, match="编号疑读"):
        texts._collation()
    with pytest.raises(NumerologySourceError) as error:
        texts.collation_summary()
    assert error.value.reason == "invalid_canping_text_collation"
    assert isinstance(error.value.__cause__, ValueError)
    assert "编号疑读" in str(error.value.__cause__)
    assert error.value.as_result()["status_code"] == 503
    assert error.value.as_result()["retryable"] is False


def test_number_notes_are_independent_copies():
    selected = lookup_record("火", 2743, "male")["selection"]
    selected["number_reading_uncertainties"].append("tampered")
    selected["reading_uncertainties"].clear()
    again = lookup_record("火", 2743, "male")["selection"]
    assert "tampered" not in again["number_reading_uncertainties"]
    assert again["reading_uncertainties"]


def test_snapshot_differentiates_obscured_header_from_unknown_body_glyph():
    from fatebridge.core.canping import _verses

    v = _verses("火", {"numShun": 2248, "numNi": 2743}, "male")
    snapshot = texts.selection_snapshot(v)
    assert "编号遮损，暂按继承键定位，号文归属未定" in snapshot
    assert "正文□" not in snapshot
    v = _verses("火", {"numShun": 2743, "numNi": 2248}, "luck")
    assert "正文□为编辑方框而非原页圈空" in texts.selection_snapshot(v)
