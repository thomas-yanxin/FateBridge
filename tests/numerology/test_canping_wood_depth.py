"""Wood table follows its named primary edition and keeps unresolved attributions."""

import csv
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.canping_texts import collation_summary, lookup_record

ROOT = Path(__file__).parents[1] / "fixtures/canping_wood_v1"
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
        (ROOT.parent / "canping_wood_rereading_v1/reference.json").read_text()
    )["cells"]
}


@pytest.mark.parametrize("row,kind", CELLS)
def test_all_wood_cells_keep_literal_text_column_page_and_reading_state(row, kind):
    n = int(row["number"])
    result = lookup_record("木", n, kind)
    selection = result["selection"]
    revision = REREADINGS.get((n, kind))
    assert result["text"] == (revision["text"] if revision else row[kind])
    if revision:
        assert selection["reading_revision"]["previous_text"] == row[kind]
    assert selection["number"] == n and selection["kind"] == kind
    assert selection["corpus_key"] == f"木.{n}.{kind}"
    assert selection["source_pdf_page"] == int(row["pdf_page"])
    assert selection["cell_status"] == (
        revision["state"]
        if revision
        else SPECIAL.get((n, kind), "source_cell_visually_collated")
    )
    if selection["cell_status"] == "source_reading_uncertain":
        assert selection["reading_uncertainties"]
        assert ("editorial_unknown_marker" in selection) == ("□" in row[kind])


def test_wood_scope_reuses_boundary_witnesses_and_excludes_uncertainty_without_double_counting():
    assert len(ROWS) == len({r["number"] for r in ROWS}) == 78
    assert len(CELLS) == 234
    assert (
        hashlib.sha256((ROOT / "literal.tsv").read_bytes()).hexdigest()
        == REFERENCE["literal_sha256"]
    )
    assert len(REFERENCE["images"]) == 9
    assert sum(p["reused_from_previous_round"] for p in REFERENCE["images"]) == 2
    for page in REFERENCE["images"]:
        assert (
            hashlib.sha256((ROOT / page["file"]).read_bytes()).hexdigest()
            == page["sha256"]
        )
    assert sum("□" in row[k] for row, k in CELLS) == 5
    assert len(HEADERS) * 3 == 12
    assert sum(int(row["number"]) in HEADERS and "□" in row[k] for row, k in CELLS) == 1
    assert len(REFERENCE["uncertain_cells"]) == 16
    assert REFERENCE["previously_collated_wood_cells"] == 0
    assert REFERENCE["new_unambiguous_wood_cells"] == 218
    summary = collation_summary()
    assert summary["collated_cells"] == 1123
    assert summary["unresolved_reading_cells"] == 47
    assert summary["unexamined_cells"] == 0
    assert summary["pending_cells"] == 47
    assert summary["visually_examined_cells"] == 1170
    assert summary["total_cells"] == 1170
    assert summary["part_coverage"]["木"] == {
        "total_cells": 234,
        "visually_examined_cells": 234,
        "collated_cells": 221,
        "unresolved_reading_cells": 13,
        "unexamined_cells": 0,
    }
    assert sum(p["collated_cells"] for p in summary["part_coverage"].values()) == 1123
    assert (
        summary["inherited_corpus_sha256"]
        == "b3eca6e5fb8ff7ae97dbf61e2a9fe9a50ee08beeb28fd797b2bc047f19d2dedc"
    )
    assert REFERENCE["new_classical_birth_examples"] == 0
    assert REFERENCE["new_independent_calendar_instants"] == 0
    assert REFERENCE["new_real_world_outcomes"] == 0


@pytest.mark.parametrize("number", [2816, 2917, 3315, 2424])
@pytest.mark.parametrize("kind", ["male", "female", "luck"])
def test_obscured_wood_headers_keep_all_columns_provisional(number, kind):
    selected = lookup_record("木", number, kind)["selection"]
    assert selected["number"] == number
    assert selected["row_status"] == "present"
    assert selected["number_attribution_status"] == "provisional_inherited_key"
    assert selected["number_reading_uncertainties"]
    assert selected["reading_uncertainties"]
    assert selected["cell_status"] == "source_reading_uncertain"
    assert "inherited_number" not in selected


def test_wood_printed_circles_are_not_filled_from_inherited_text():
    assert lookup_record("木", 3115, "luck")["text"] == "登高○○○，傳命探梅花。"
    assert lookup_record("木", 2208, "luck")["text"] == "藍橋玉壺○，鴛鴦解鳴雨。"
    assert lookup_record("木", 2412, "female")["text"] == "還解○香祝，清虛度化生。"
    assert lookup_record("木", 2325, "female")["text"] == "芳草碧連天，塵○臨絃索。"
    assert lookup_record("木", 2424, "luck")["text"] == "杏花雨濛濛，喜蘇人○犁。"
    assert (
        lookup_record("木", 2424, "luck")["selection"]["cell_status"]
        == "source_reading_uncertain"
    )
    assert (
        lookup_record("木", 2313, "luck")["selection"]["cell_status"]
        == "source_printed_blank"
    )


def test_unusual_wood_readings_are_not_emended_to_familiar_phrases():
    assert lookup_record("木", 3309, "male")["text"] == "牛溲馬渤功，不假金丹術。"
    assert lookup_record("木", 2513, "female")["text"] == "風蒲美轉定，能化青蛇銅。"
    assert lookup_record("木", 2313, "female")["text"] == "日口任東風，女子貞不字。"
    assert lookup_record("木", 2321, "luck")["text"] == "花開向波心，天香施紅味。"
    assert lookup_record("木", 2519, "luck")["text"] == "遇水得逢橋，憂心傾□然。"
