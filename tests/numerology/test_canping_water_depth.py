"""Whole water-part review, without counting uncertain readings as collated."""

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from fatebridge.core.canping import BRANCHES, _verses, compute_number
from fatebridge.core.canping_texts import (
    _collation,
    collation_summary,
    lookup_record,
    selection_snapshot,
)

ROOT = Path(__file__).parents[1] / "fixtures/canping_water_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text(encoding="utf-8"))
ROWS = list(
    csv.DictReader((ROOT / "literal.tsv").open(encoding="utf-8"), delimiter="\t")
)
STATES = {
    (r["number"], r["kind"]): r["state"] for r in REFERENCE["expected_special_states"]
}
REREAD = {
    (r["number"], r["kind"]): r
    for r in json.loads(
        (ROOT.parent / "canping_rereading_v1/reference.json").read_text()
    )["cells"]
}
CELLS = [(r, k) for r in ROWS for k in ("male", "female", "luck")]


@pytest.mark.parametrize("row,kind", CELLS)
def test_actual_water_numbered_cell_and_its_specific_reading_status(row, kind):
    n = int(row["number"])
    selected = lookup_record("水", n, kind)
    revision = REREAD.get((n, kind))
    assert selected["text"] == (revision["text"] if revision else row[kind])
    evidence = selected["selection"]
    if revision:
        assert evidence["reading_revision"]["previous_text"] == row[kind]
    assert evidence["source_pdf_page"] == int(row["pdf_page"])
    assert evidence["cell_status"] == (
        revision["state"]
        if revision
        else STATES.get((n, kind), "source_cell_visually_collated")
    )
    assert evidence["corpus_key"] == f"水.{n}.{kind}"
    if evidence["cell_status"] == "source_reading_uncertain":
        assert evidence["editorial_unknown_marker"] == "□"
        assert evidence["reading_uncertainties"]
    else:
        assert "□" not in selected["text"]
        assert "editorial_unknown_marker" not in evidence


def test_source_identity_and_coverage_separate_uncertainty_from_unexamined_cells():
    assert len(ROWS) == len({r["number"] for r in ROWS}) == 78
    assert (
        hashlib.sha256((ROOT / "literal.tsv").read_bytes()).hexdigest()
        == REFERENCE["literal_sha256"]
    )
    for row in REFERENCE["images"]:
        assert (
            hashlib.sha256((ROOT / row["file"]).read_bytes()).hexdigest()
            == row["sha256"]
        )
    assert len(REFERENCE["images"]) == 9
    assert REFERENCE["unambiguous_water_cells"] == 194
    assert REFERENCE["unresolved_reading_cells"] == 40
    assert REFERENCE["new_unambiguous_water_cells"] == 188
    assert REFERENCE["new_classical_birth_examples"] == 0
    assert REFERENCE["new_independent_calendar_instants"] == 0
    counts = collation_summary()
    assert counts["source_pdf_sha256"] == REFERENCE["source_pdf_sha256"]
    assert counts["visually_examined_cells"] == 1170
    assert counts["collated_cells"] == 1123
    assert counts["unresolved_reading_cells"] == 47
    assert counts["unexamined_cells"] == 0
    assert counts["pending_cells"] == 47
    assert counts["collated_cells"] + counts["pending_cells"] == 1170
    assert (
        counts["pending_cells"]
        == counts["unexamined_cells"] + counts["unresolved_reading_cells"]
    )


def test_known_source_circles_are_not_filled_from_inherited_or_familiar_wording():
    row = lookup_record("水", 2344, "female")
    assert row["text"] == "春歸當斷○，梅子釀酸時。"
    assert row["selection"]["cell_status"] == "source_printed_partial_blank"
    assert row["selection"]["inherited_text"] == "春歸當斷路，梅子釀酸時。"
    reread = lookup_record("水", 3041, "luck")
    assert reread["text"] == "畫舫過洪波，棹○難得太。"
    assert reread["selection"]["cell_status"] == "source_printed_partial_blank"
    assert reread["selection"]["reading_revision"]["previous_text"] == (
        "畫舫過洪波，棹○難得□。"
    )
    assert reread["selection"]["inherited_text"] == "畫航過洪波，棹短難得渡。"
    v = _verses("水", {"numShun": 3041, "numNi": 2344}, "luck")
    assert v["statusShun"] == "source_printed_partial_blank"
    assert v["statusNi"] == "source_cell_visually_collated"
    assert "同馆藏原图复读，旧疑读另存" in selection_snapshot(v)


def test_partial_and_complete_printed_blanks_keep_their_different_statuses():
    partial = _verses("水", {"numShun": 2344, "numNi": 3336}, "female")
    assert partial["statusShun"] == "source_printed_partial_blank"
    assert partial["statusNi"] == "source_printed_blank"
    assert partial["pair_resolution"]["local_text_availability"] == "shun_only"


@pytest.mark.parametrize("element", list("水火木金土"))
def test_all_day_hour_inputs_have_a_row_without_inventing_missing_direction_text(
    element,
):
    states = Counter()
    for day in BRANCHES:
        for hour in BRANCHES:
            n = compute_number(day, hour, element)
            a = lookup_record(element, n["numShun"], "male")
            b = lookup_record(element, n["numNi"], "male")
            pair = tuple(x["selection"]["row_status"] == "present" for x in (a, b))
            assert any(pair), (day, hour, element, n)
            states[pair] += 1
    assert states == {(True, True): 84, (True, False): 30, (False, True): 30}


def test_untagged_editorial_unknown_cannot_be_promoted_to_collated(monkeypatch):
    import fatebridge.core.canping_texts as module

    raw = json.loads(json.dumps(_collation()))
    entry = next(
        e for e in raw["entries"] if e["number"] == 2740 and e["element"] == "水"
    )
    del entry["reading_uncertainties"]
    monkeypatch.setattr(module, "_loaded", lambda path: {"data": raw})
    with pytest.raises(ValueError, match="编辑方框"):
        module._collation()


def test_reading_uncertainties_are_isolated_between_calls():
    a = lookup_record("水", 2740, "luck")
    a["selection"]["reading_uncertainties"].clear()
    assert lookup_record("水", 2740, "luck")["selection"]["reading_uncertainties"]
