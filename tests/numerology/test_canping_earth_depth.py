"""Earth readings follow the primary witness without filling its circles."""

import csv
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.canping_texts import collation_summary, lookup_record

ROOT = Path(__file__).parents[1] / "fixtures/canping_earth_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())
ROWS = list(csv.DictReader((ROOT / "literal.tsv").open(), delimiter="\t"))
SPECIAL = {
    (r["number"], r["kind"]): r["state"] for r in REFERENCE["expected_special_states"]
}
CELLS = [(r, k) for r in ROWS for k in ("male", "female", "luck")]
REREADINGS = {
    (c["number"], c["kind"]): c
    for c in json.loads(
        (ROOT.parent / "canping_earth_rereading_v1/reference.json").read_text()
    )["cells"]
}


@pytest.mark.parametrize("row,kind", CELLS)
def test_all_earth_cells_keep_literal_text_column_page_and_state(row, kind):
    number = int(row["number"])
    result = lookup_record("土", number, kind)
    selected = result["selection"]
    revision = REREADINGS.get((number, kind))
    assert result["text"] == (revision["text"] if revision else row[kind])
    if revision:
        assert selected["reading_revision"]["previous_text"] == row[kind]
    assert selected["number"] == number and selected["kind"] == kind
    assert selected["corpus_key"] == f"土.{number}.{kind}"
    assert selected["source_pdf_page"] == int(row["pdf_page"])
    assert selected["cell_status"] == (
        revision["state"]
        if revision
        else SPECIAL.get((number, kind), "source_cell_visually_collated")
    )
    assert "number_attribution_status" not in selected
    if "□" in (revision["text"] if revision else row[kind]):
        assert selected["reading_uncertainties"]
        assert selected["editorial_unknown_marker"] == "□"
    else:
        assert "reading_uncertainties" not in selected


def test_earth_scope_reuses_three_cells_and_two_pages_without_claiming_complete_conformity():
    assert len(ROWS) == len({r["number"] for r in ROWS}) == 78
    assert len(CELLS) == 234
    assert (
        hashlib.sha256((ROOT / "literal.tsv").read_bytes()).hexdigest()
        == REFERENCE["literal_sha256"]
    )
    assert [p["pdf_page"] for p in REFERENCE["images"]] == list(range(97, 105))
    assert sum(p["reused_from_previous_round"] for p in REFERENCE["images"]) == 2
    for page in REFERENCE["images"]:
        assert (
            hashlib.sha256((ROOT / page["file"]).read_bytes()).hexdigest()
            == page["sha256"]
        )
    assert sum("□" in r[k] for r, k in CELLS) == 3
    assert len(REFERENCE["uncertain_cells"]) == 3
    assert REFERENCE["number_reading_uncertainties"] == []
    assert REFERENCE["previously_collated_earth_cells"] == 3
    assert REFERENCE["new_unambiguous_earth_cells"] == 228
    summary = collation_summary()
    assert summary["part_coverage"]["土"] == {
        "total_cells": 234,
        "visually_examined_cells": 234,
        "collated_cells": 232,
        "unresolved_reading_cells": 2,
        "unexamined_cells": 0,
    }
    assert summary["collated_cells"] == 1123
    assert summary["unresolved_reading_cells"] == summary["pending_cells"] == 47
    assert summary["unexamined_cells"] == 0
    assert summary["visually_examined_cells"] == summary["total_cells"] == 1170
    assert summary["numbered_table_visual_review_complete"] is True
    assert summary["numbered_table_clear_readings_complete"] is False
    assert "independent_second_review_pending" in summary["review_status"]
    assert summary["inherited_corpus_sha256"] == (
        "b3eca6e5fb8ff7ae97dbf61e2a9fe9a50ee08beeb28fd797b2bc047f19d2dedc"
    )
    assert REFERENCE["new_classical_birth_examples"] == 0
    assert REFERENCE["new_independent_calendar_instants"] == 0
    assert REFERENCE["new_real_world_outcomes"] == 0


def test_remaining_earth_uncertainties_are_not_filled_from_inherited_text():
    assert lookup_record("土", 2460, "luck")["text"] == "再磨龍劍用，銳氣徹青□。"
    assert lookup_record("土", 3363, "luck")["text"] == "魚龍在釣□，志樂在其中。"
    assert lookup_record("土", 3377, "female")["text"] == "晝夕掩重門，虛空久寂寞。"
    for number, kind in [(2460, "luck"), (3363, "luck")]:
        selected = lookup_record("土", number, kind)["selection"]
        assert selected["cell_status"] == "source_reading_uncertain"
        assert selected["reading_uncertainties"]


def test_earth_unusual_readings_and_circles_remain_separate_from_allusion_emendation():
    assert lookup_record("土", 2666, "female")["text"] == "汀蘭井岸芷，泛○奉浮家。"
    assert lookup_record("土", 2365, "female")["text"] == "一曲神仙○，風吹別調聞。"
    assert lookup_record("土", 2474, "female")["text"] == "雖是好羅裙，猶同紗○裡。"
    assert lookup_record("土", 2771, "luck")["text"] == "舜日得升空，堅冰須盡什。"
    assert lookup_record("土", 2773, "luck")["text"] == "水由地中行，江淮朝宗漢。"
    assert lookup_record("土", 2476, "male")["text"] == "水由地中行，江漢朝宗海。"


def test_reused_corrected_header_and_unassigned_note_are_not_reinterpreted():
    for kind in ("male", "female", "luck"):
        assert lookup_record("土", 3373, kind)["selection"]["inherited_number"] == 3372
        retired = lookup_record("土", 3372, kind)
        assert retired["text"] == ""
        assert retired["selection"]["corrected_number"] == 3373
        special = lookup_record("土", 2869, kind)
        assert special["text"] == ""
        assert special["selection"]["unapplied_note"]["applied_to_lookup"] is False
