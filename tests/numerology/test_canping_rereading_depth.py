"""Native same-copy images can resolve readings without claiming independent review."""

import copy
import csv
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.canping_texts import collation_summary, lookup_record


@pytest.mark.parametrize(
    "number,kind,text",
    [
        (3241, "female", "江天欲暮時，惆悵神仙侶。"),
        (2538, "male", "坐井觀天象，明知八陣圖。"),
        (2443, "female", "□女乘龍去，猶疑結子。"),
    ],
)
def test_native_image_rereadings_are_selected(number, kind, text):
    assert lookup_record("水", number, kind)["text"] == text


ROOT = Path(__file__).parents[1] / "fixtures/canping_rereading_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())
ROWS = list(csv.DictReader((ROOT / "literal.tsv").open(), delimiter="\t"))
CELLS = REFERENCE["cells"]


@pytest.mark.parametrize("cell", CELLS)
def test_reread_cells_keep_exact_readings_prior_uncertainty_and_source_identity(cell):
    actual = lookup_record(cell["element"], cell["number"], cell["kind"])
    selected = actual["selection"]
    assert actual["text"] == cell["text"]
    assert selected["cell_status"] == cell["state"]
    assert selected["source_pdf_page"] == cell["pdf_page"]
    revision = selected["reading_revision"]
    assert revision["previous_text"] == cell["previous_text"]
    assert revision["previous_cell_status"] == "source_reading_uncertain"
    assert revision["previous_collation_version"] == "1.5.0"
    assert revision["source_pdf_page"] == cell["pdf_page"]
    assert revision["rereading_id"] == REFERENCE["fixture_id"]
    assert revision["note"] == cell["note"]
    assert ("editorial_unknown_marker" in selected) == ("□" in cell["text"])
    assert bool(selected.get("reading_uncertainties")) == ("□" in cell["text"])


def jpeg_dimensions(raw):
    assert raw[:2] == b"\xff\xd8"
    offset = 2
    while offset < len(raw):
        assert raw[offset] == 255
        marker = raw[offset + 1]
        length = int.from_bytes(raw[offset + 2 : offset + 4], "big")
        if marker in {0xC0, 0xC1, 0xC2}:
            return (
                int.from_bytes(raw[offset + 7 : offset + 9], "big"),
                int.from_bytes(raw[offset + 5 : offset + 7], "big"),
            )
        offset += 2 + length
    raise AssertionError("JPEG lacks a supported frame header")


@pytest.mark.parametrize("page", REFERENCE["pages"])
def test_native_regions_have_actual_pixels_and_cover_exactly_one_same_copy_page(page):
    manifest = json.loads((ROOT / REFERENCE["source_manifest_file"]).read_text())
    canvas = manifest["sequences"][0]["canvases"][page["pdf_page"] - 1]
    assert (canvas["width"], canvas["height"]) == (5900, 4400)
    assert page["full_request_actual_dimensions"] == [3000, 2237]
    assert {tuple(r["region"]) for r in page["regions"]} == {
        (0, 0, 2950, 2200),
        (2950, 0, 2950, 2200),
        (0, 2200, 2950, 2200),
        (2950, 2200, 2950, 2200),
    }
    for region in page["regions"]:
        raw = (ROOT / region["file"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == region["sha256"]
        assert jpeg_dimensions(raw) == (2950, 2200)
        assert region["canvas"] == canvas["@id"]
        assert region["url"].endswith(
            "/" + ",".join(map(str, region["region"])) + "/full/0/native.jpg"
        )


def test_rereading_does_not_inflate_numbered_cells_independent_reviews_or_full_acceptance():
    assert len(CELLS) == len(ROWS) == 40
    assert len({(r["number"], r["kind"]) for r in CELLS}) == 40
    assert sum("□" not in r["text"] for r in CELLS) == 30
    assert sum("□" in r["text"] for r in CELLS) == 10
    assert (
        hashlib.sha256((ROOT / "literal.tsv").read_bytes()).hexdigest()
        == REFERENCE["literal_sha256"]
    )
    assert (
        hashlib.sha256(
            (ROOT / REFERENCE["source_manifest_file"]).read_bytes()
        ).hexdigest()
        == REFERENCE["source_manifest_sha256"]
    )
    old = json.loads((ROOT.parent / "canping_water_v1/reference.json").read_text())
    assert old["unresolved_reading_cells"] == 40
    assert {(r["number"], r["kind"]) for r in old["uncertain_cells"]} == {
        (r["number"], r["kind"]) for r in CELLS
    }
    assert sum(r["state"] == "source_printed_partial_blank" for r in CELLS) == 2
    for key in (
        "new_numbered_cells_examined",
        "new_independent_reviews",
        "new_classical_birth_examples",
        "new_independent_calendar_instants",
        "new_real_world_outcomes",
    ):
        assert REFERENCE[key] == 0
    summary = collation_summary()
    assert summary["collated_cells"] == 1123
    assert summary["unresolved_reading_cells"] == summary["pending_cells"] == 47
    assert summary["visually_examined_cells"] == summary["total_cells"] == 1170
    assert summary["unexamined_cells"] == 0
    assert summary["part_coverage"]["水"]["collated_cells"] == 224
    assert summary["part_coverage"]["水"]["unresolved_reading_cells"] == 10
    assert summary["numbered_table_visual_review_complete"] is True
    assert summary["numbered_table_clear_readings_complete"] is False
    assert summary["rereading_witness"]["resolved_cells"] == 30
    assert summary["rereading_witness"]["still_uncertain_cells"] == 10
    assert summary["rereading_witness"]["new_independent_reviews"] == 0
    assert "independent_second_review_pending" in summary["review_status"]


@pytest.mark.parametrize(
    "change",
    ["previous_text", "previous_cell_status", "source_pdf_page", "rereading_id"],
)
def test_revision_cannot_discard_prior_uncertainty_or_claim_another_page(
    monkeypatch, change
):
    from fatebridge.core import canping_texts

    original = canping_texts._loaded
    record = copy.deepcopy(original(canping_texts.COLLATION_PATH))
    e = next(
        e
        for e in record["data"]["entries"]
        if (e["element"], e["number"]) == ("水", 3241)
    )
    e["reading_revisions"]["female"][change] = None
    monkeypatch.setattr(
        canping_texts,
        "_loaded",
        lambda p: record if p == canping_texts.COLLATION_PATH else original(p),
    )
    with pytest.raises(ValueError, match="复读修订"):
        canping_texts._collation()


def test_revisions_and_rereading_summary_are_isolated_between_calls():
    row = lookup_record("水", 3241, "female")
    row["selection"]["reading_revision"]["previous_text"] = "tampered"
    summary = collation_summary()
    summary["rereading_witness"]["pages"].clear()
    assert (
        "□"
        in lookup_record("水", 3241, "female")["selection"]["reading_revision"][
            "previous_text"
        ]
    )
    assert len(collation_summary()["rereading_witness"]["pages"]) == 7
