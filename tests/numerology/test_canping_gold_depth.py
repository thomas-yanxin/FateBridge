"""Complete gold table, including original numbered header/body pairings."""

import csv
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.canping_texts import (
    INHERITED_PATH,
    collation_summary,
    lookup_record,
)

ROOT = Path(__file__).parents[1] / "fixtures/canping_gold_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text(encoding="utf-8"))
ROWS = list(
    csv.DictReader((ROOT / "literal.tsv").open(encoding="utf-8"), delimiter="\t")
)
SPECIAL = {
    (int(r["number"]), r["kind"]): r["state"]
    for r in REFERENCE["expected_special_states"]
}
CELLS = [(r, k) for r in ROWS for k in ("male", "female", "luck")]
REREADINGS = {
    (c["number"], c["kind"]): c
    for c in json.loads(
        (ROOT.parent / "canping_gold_rereading_v1/reference.json").read_text()
    )["cells"]
}


@pytest.mark.parametrize("row,kind", CELLS)
def test_every_gold_cell_keeps_its_number_column_page_and_reading_state(row, kind):
    n = int(row["number"])
    result = lookup_record("金", n, kind)
    revision = REREADINGS.get((n, kind))
    assert result["text"] == (revision["text"] if revision else row[kind])
    selected = result["selection"]
    if revision:
        assert selected["reading_revision"]["previous_text"] == row[kind]
    assert selected["number"] == n and selected["kind"] == kind
    assert selected["corpus_key"] == f"金.{n}.{kind}"
    assert selected["source_pdf_page"] == int(row["pdf_page"])
    assert selected["cell_status"] == (
        revision["state"]
        if revision
        else SPECIAL.get((n, kind), "source_cell_visually_collated")
    )
    if selected["cell_status"] == "source_reading_uncertain":
        assert selected["editorial_unknown_marker"] == "□"
        assert selected["reading_uncertainties"]


def test_full_gold_scope_and_source_bytes_do_not_count_uncertainty_as_complete():
    assert len(ROWS) == len({r["number"] for r in ROWS}) == 78
    assert len(CELLS) == 234
    assert (
        hashlib.sha256((ROOT / "literal.tsv").read_bytes()).hexdigest()
        == REFERENCE["literal_sha256"]
    )
    for page in REFERENCE["images"]:
        assert (
            hashlib.sha256((ROOT / page["file"]).read_bytes()).hexdigest()
            == page["sha256"]
        )
    assert len(REFERENCE["images"]) == 9
    assert REFERENCE["unambiguous_gold_cells"] == 219
    assert REFERENCE["unresolved_reading_cells"] == 15
    assert REFERENCE["new_classical_birth_examples"] == 0
    assert REFERENCE["new_independent_calendar_instants"] == 0
    summary = collation_summary()
    assert summary["collated_cells"] == 1123
    assert summary["unresolved_reading_cells"] == 47
    assert summary["visually_examined_cells"] == 1170
    assert summary["unexamined_cells"] == 0
    assert summary["pending_cells"] == 47
    assert summary["part_coverage"]["金"] == {
        "total_cells": 234,
        "visually_examined_cells": 234,
        "collated_cells": 223,
        "unresolved_reading_cells": 11,
        "unexamined_cells": 0,
    }
    assert (
        sum(p["collated_cells"] for p in summary["part_coverage"].values())
        == summary["collated_cells"]
    )
    assert (
        sum(p["unexamined_cells"] for p in summary["part_coverage"].values())
        == summary["unexamined_cells"]
    )
    assert (
        summary["pending_cells"]
        == summary["unexamined_cells"] + summary["unresolved_reading_cells"]
    )
    assert "independent_second_review_pending" in summary["review_status"]


@pytest.mark.parametrize("pair", REFERENCE["numbered_content_correspondence"])
def test_eleven_number_body_pairings_follow_printed_headers_without_remapping_numbers(
    pair,
):
    raw = json.loads(INHERITED_PATH.read_text())["parts"]["金"]
    n = pair["source_number"]
    for kind in ("male", "female", "luck"):
        result = lookup_record("金", n, kind)
        selected = result["selection"]
        assert selected["number"] == n
        assert selected["source_pdf_page"] == pair["source_pdf_page"]
        assert selected["inherited_text"] == raw[str(n)][kind]
        assert selected["row_status"] == "present"
        assert "inherited_number" not in selected
        assert "reading_notes" in selected
    assert (
        lookup_record("金", pair["inherited_content_number"], "male")["selection"][
            "row_status"
        ]
        == "present"
    )


def test_printed_circles_and_faded_spans_are_not_filled_or_copied_between_columns():
    assert lookup_record("金", 2920, "female")["text"] == "青繩曾係足，何事○伐柯。"
    assert lookup_record("金", 2518, "luck")["text"] == "吞釣魚上鉤，沈機大小○。"
    assert lookup_record("金", 3314, "luck")["text"] == "蕙蘭花□，各自逞馨香。"
    assert lookup_record("金", 3314, "female")["text"] == "蕙蘭花一處，各自逞馨香。"
    assert (
        lookup_record("金", 2227, "luck")["selection"]["cell_status"]
        == "source_printed_blank"
    )
    assert (
        lookup_record("金", 3326, "luck")["selection"]["cell_status"]
        == "source_cell_visually_collated"
    )


def test_literal_unusual_readings_and_word_order_are_not_emended_by_familiarity():
    assert lookup_record("金", 2409, "male")["text"] == "花鈿委地戶，沙暖見春雲。"
    assert lookup_record("金", 2615, "luck")["text"] == "木生毫末間，從微須著至。"
