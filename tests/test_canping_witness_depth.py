"""Named edition comparisons do not silently substitute the selected reading."""

import csv
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.canping import _verses
from fatebridge.core.canping_texts import (
    WITNESSES_PATH,
    _witness_corpus,
    collation_summary,
    lookup_record,
    selection_snapshot,
    witness_summary,
)

ROOT = Path(__file__).parent / "fixtures/canping_witness_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text(encoding="utf-8"))
ROWS = list(
    csv.DictReader((ROOT / "literal.tsv").open(encoding="utf-8"), delimiter="\t")
)


@pytest.mark.parametrize("row", ROWS)
def test_literal_same_element_number_and_column_witness(row):
    selected = lookup_record("水", int(row["number"]), row["kind"])
    witness = selected["selection"]["witnesses"][0]
    assert witness["text"] == row["text"]
    assert witness["number"] == int(row["number"])
    assert witness["kind"] == row["kind"]
    assert witness["pdf_pages"] == [int(p) for p in row["pdf_pages"].split(",")]
    assert witness["body_pdf_page"] == int(row["body_pdf_page"])
    assert witness["replaces_selected_text"] is False
    assert witness["source_corpus_id"] == REFERENCE["corpus_id"]
    if "□" in row["text"]:
        assert witness["text_status"] == "source_reading_uncertain"
        assert witness["reading_uncertainties"]
    elif not row["text"].replace("○", "").replace("，", "").replace("。", ""):
        assert witness["text_status"] == "source_printed_blank"
    else:
        assert witness["text_status"] == "source_cell_visually_collated"


def test_witness_hashes_and_uncertainty_do_not_inflate_primary_collation():
    assert (
        hashlib.sha256((ROOT / "literal.tsv").read_bytes()).hexdigest()
        == REFERENCE["literal_sha256"]
    )
    for row in REFERENCE["images"]:
        assert (
            hashlib.sha256((ROOT / row["file"]).read_bytes()).hexdigest()
            == row["sha256"]
        )
    summary = witness_summary()
    assert len(ROWS) == 36 and len(REFERENCE["images"]) == 11
    assert summary["cells_examined"] == 72 and summary["clear_readings"] == 70
    water = summary["part_coverage"]["水"]
    assert water["cells_examined"] == 36 and water["clear_readings"] == 34
    assert water["uncertain_readings"] == 2
    assert summary["registered_counterpart_cells"] == 69
    assert summary["registered_counterpart_keys"] == 66
    assert summary["ambiguous_counterpart_keys"] == 3
    assert summary["unmatched_observed_cells"] == 3
    assert (
        summary["uncertain_readings"] == 2
        and summary["primary_collation_count_increase"] == 0
    )
    assert summary["sha256"] == hashlib.sha256(WITNESSES_PATH.read_bytes()).hexdigest()
    base = collation_summary()
    assert base["collated_cells"] == 1123 and base["pending_cells"] == 47
    assert base["unresolved_reading_cells"] == 47
    assert base["comparison_witness"] == summary


@pytest.mark.parametrize(
    "number,kind,main,other",
    [
        (2231, "luck", "酒醒何處去，柳岸臨風輕。", "酒醒何處去，柳岸晚風輕。"),
        (2332, "male", "南山秦嶺花，開向三冬雪。", "商山秦嶺花，開向三冬雪。"),
        (2536, "male", "繡針為鐵杵，江海暗中瀛。", "繡針為鐵柱，江海暗中瀛。"),
        (2344, "female", "春歸當斷○，梅子釀酸時。", "春歸當斷路，梅子釀酸時。"),
    ],
)
def test_inherited_reading_can_have_another_edition_basis(number, kind, main, other):
    row = lookup_record("水", number, kind)
    assert row["text"] == main and row["selection"]["inherited_text"] == other
    witness = row["selection"]["witnesses"][0]
    assert witness["text"] == other and witness["inherited_reading_matches"] is True
    assert witness["relation"] == "different_text"


def test_uncertain_primary_is_not_completed_by_a_clear_witness():
    row = lookup_record("水", 2538, "female")
    assert row["text"] == "荷葉疊青錢，□鴦永向風。"
    witness = row["selection"]["witnesses"][0]
    assert witness["text"] == "荷葉疊青錢，鴛鴦水面風。"
    assert witness["relation"] == "selected_reading_uncertain"
    assert row["selection"]["cell_status"] == "source_reading_uncertain"


def test_both_editions_uncertain_stay_uncertain_and_columns_do_not_leak():
    row = lookup_record("水", 2249, "female")
    assert row["selection"]["witnesses"][0]["relation"] == "both_readings_uncertain"
    resolved = lookup_record("水", 2449, "female")
    assert resolved["text"] == "月娥雷桂子，圓缺又同情。"
    assert resolved["selection"]["cell_status"] == "source_cell_visually_collated"
    assert (
        resolved["selection"]["witnesses"][0]["relation"] == "witness_reading_uncertain"
    )
    male = lookup_record("水", 2449, "male")
    assert male["selection"]["witnesses"][0]["relation"] == "same_text"
    assert "witnesses" not in lookup_record("火", 2449, "female")["selection"]
    assert "witnesses" not in lookup_record("水", 2449, None)["selection"]


def test_snapshot_distinguishes_actual_reading_and_unselected_counterpart():
    v = _verses("水", {"numShun": 2332, "numNi": 2536}, "male")
    text = selection_snapshot(v)
    assert "商山秦嶺花" in text and "鐵柱" in text
    assert "未替换本次主选文" in text and "差异归因待校定" in text
    assert v["textShun"].startswith("南山") and "鐵杵" in v["textNi"]


def test_witness_result_and_summary_are_isolated():
    row = lookup_record("水", 2332, "male")
    row["selection"]["witnesses"][0]["text"] = "changed"
    summary = witness_summary()
    summary["source_title"] = "changed"
    assert lookup_record("水", 2332, "male")["selection"]["witnesses"][0][
        "text"
    ].startswith("商山")
    assert witness_summary()["source_title"] != "changed"


def test_duplicate_or_untagged_uncertain_witnesses_are_rejected(monkeypatch):
    import fatebridge.core.canping_texts as module

    original = json.loads(json.dumps(_witness_corpus()))
    duplicate = json.loads(json.dumps(original))
    duplicate["entries"].append(duplicate["entries"][0])
    monkeypatch.setattr(module, "_loaded", lambda path: {"data": duplicate})
    with pytest.raises(ValueError, match="重复"):
        module._witness_corpus()
    for row in original["entries"]:
        if row.get("reading_uncertainties"):
            del row["reading_uncertainties"]
    monkeypatch.setattr(module, "_loaded", lambda path: {"data": original})
    with pytest.raises(ValueError, match="编辑方框"):
        module._witness_corpus()
