"""A readable body does not establish an obscured source number."""

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from fatebridge.core.canping_texts import (
    collation_summary,
    lookup_record,
    selection_snapshot,
)
from fatebridge.utils.errors import NumerologySourceError
from tests.test_canping_rereading_depth import jpeg_dimensions


@pytest.mark.parametrize(
    "element,number,kind,body_status",
    [
        ("火", 2248, "female", "source_body_printed_blank"),
        ("木", 2816, "male", "source_body_visually_read"),
    ],
)
def test_number_uncertainty_and_observed_body_status_are_separate(
    element, number, kind, body_status
):
    selected = lookup_record(element, number, kind)["selection"]
    assert selected["body_reading_status"] == body_status
    assert selected["cell_status"] == "source_reading_uncertain"
    assert selected["number_attribution_status"] == "provisional_inherited_key"
    assert selected["number_reading_evidence"]["resolution_status"] == "unresolved"


ROOT = Path(__file__).parent / "fixtures/canping_header_evidence_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())


@pytest.mark.parametrize("cell", REFERENCE["cells"])
def test_all_eighteen_bodies_and_unresolved_number_attributions_stay_separate(cell):
    result = lookup_record(cell["element"], cell["number"], cell["kind"])
    selected = result["selection"]
    assert result["text"] == cell["text"]
    assert selected["cell_status"] == "source_reading_uncertain"
    assert selected["body_reading_status"] == cell["body_reading_status"]
    assert selected["number_attribution_status"] == "provisional_inherited_key"
    assert (
        selected["number_reading_uncertainties"] and selected["reading_uncertainties"]
    )
    evidence = selected["number_reading_evidence"]
    assert evidence["witness_id"] == REFERENCE["fixture_id"]
    assert evidence["provisional_number"] == cell["number"]
    assert evidence["pdf_page"] == cell["pdf_page"]
    assert evidence["resolution_status"] == "unresolved"
    assert "□" in evidence["observed_header"]
    assert evidence["body_evidence_basis"] == cell["body_evidence_basis"]
    assert ("editorial_unknown_marker" in selected) == ("□" in cell["text"])


@pytest.mark.parametrize("page", REFERENCE["pages"])
def test_native_regions_cover_the_same_copy_and_keep_actual_source_pixels(page):
    manifest = json.loads((ROOT / REFERENCE["source_manifest_file"]).read_text())
    canvas = manifest["sequences"][0]["canvases"][page["pdf_page"] - 1]
    assert (
        [canvas["width"], canvas["height"]] == page["canvas_dimensions"] == [5900, 4400]
    )
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


def test_native_reinspection_does_not_promote_any_header_or_whole_cell():
    assert len(REFERENCE["headers"]) == 6 and len(REFERENCE["cells"]) == 18
    assert len(REFERENCE["pages"]) == 5
    assert Counter(h["obstruction_kind"] for h in REFERENCE["headers"]) == {
        "seal_overprint": 5,
        "faded_digit": 1,
    }
    assert Counter(c["body_reading_status"] for c in REFERENCE["cells"]) == {
        "source_body_visually_read": 14,
        "source_body_printed_blank": 1,
        "source_body_printed_partial_blank": 1,
        "source_body_reading_uncertain": 2,
    }
    for key in (
        "headers_resolved",
        "new_confirmed_cells",
        "new_numbered_cells_examined",
        "new_independent_reviews",
        "new_classical_birth_examples",
        "new_independent_calendar_instants",
        "new_real_world_outcomes",
    ):
        assert REFERENCE[key] == 0
    for file, digest in (
        ("literal.tsv", REFERENCE["literal_sha256"]),
        (REFERENCE["source_manifest_file"], REFERENCE["source_manifest_sha256"]),
    ):
        assert hashlib.sha256((ROOT / file).read_bytes()).hexdigest() == digest
    summary = collation_summary()
    assert summary["collated_cells"] == 1123
    assert summary["pending_cells"] == summary["unresolved_reading_cells"] == 47
    assert summary["visually_examined_cells"] == summary["total_cells"] == 1170
    assert summary["numbered_table_clear_readings_complete"] is False
    assert summary["number_reading_witness"]["headers_resolved"] == 0
    assert summary["number_reading_witness"]["headers_still_uncertain"] == 6


@pytest.mark.parametrize(
    "change",
    [
        "remove_all_flags",
        "clear_one_column",
        "complete_observation",
        "wrong_page",
        "remove_row",
    ],
)
def test_unresolved_native_header_evidence_cannot_be_silently_promoted(
    monkeypatch, change
):
    from fatebridge.core import canping_texts as texts

    original = texts._loaded
    loaded = copy.deepcopy(original(texts.COLLATION_PATH))
    data = loaded["data"]
    row = next(
        e for e in data["entries"] if (e["element"], e["number"]) == ("火", 2248)
    )
    observed = next(
        h
        for h in data["number_reading_witness"]["headers"]
        if (h["element"], h["provisional_number"]) == ("火", 2248)
    )
    if change == "remove_all_flags":
        del row["number_reading_uncertainties"]
        del row["reading_uncertainties"]
    elif change == "clear_one_column":
        del row["reading_uncertainties"]["female"]
    elif change == "complete_observation":
        observed["observed_header"] = "二二四八"
    elif change == "wrong_page":
        observed["pdf_page"] = 79
    else:
        data["entries"].remove(row)
    monkeypatch.setattr(
        texts, "_loaded", lambda p: loaded if p == texts.COLLATION_PATH else original(p)
    )
    with pytest.raises(ValueError, match="编号"):
        texts._collation()
    with pytest.raises(NumerologySourceError) as error:
        texts.collation_summary()
    assert error.value.reason == "invalid_canping_text_collation"
    assert isinstance(error.value.__cause__, ValueError)
    assert "编号" in str(error.value.__cause__)
    assert error.value.as_result()["status_code"] == 503
    assert error.value.as_result()["retryable"] is False


def test_body_state_and_snapshot_cannot_relabel_a_provisional_number():
    female = lookup_record("火", 2248, "female")
    v = {"selectionShun": female["selection"], "selectionNi": female["selection"]}
    text = selection_snapshot(v)
    assert "正文为原页全圈空" in text
    assert "原图编号仍未定，整格不计入已确定数" in text
    assert "编号遮损，暂按继承键定位，号文归属未定" in text
    ordinary = lookup_record("火", 2335, "male")["selection"]
    assert "number_reading_evidence" not in ordinary
    assert "body_reading_status" not in ordinary


def test_native_number_evidence_and_global_registry_are_isolated():
    selected = lookup_record("木", 2816, "male")["selection"]
    selected["number_reading_evidence"]["observed_header"] = "二八一六"
    summary = collation_summary()
    summary["number_reading_witness"]["headers"].clear()
    assert (
        lookup_record("木", 2816, "male")["selection"]["number_reading_evidence"][
            "observed_header"
        ]
        == "□八一六"
    )
    assert len(collation_summary()["number_reading_witness"]["headers"]) == 6


@pytest.mark.parametrize(
    "value",
    [
        {"body_reading_status": "source_cell_visually_collated"},
        {"number_attribution_status": "confirmed"},
        {"number_reading_evidence": {"provisional_number": True}},
        {"number_reading_evidence": {"resolution_status": "resolved"}},
        {"reading_revision": {"previous_cell_status": "source_cell_visually_collated"}},
    ],
)
def test_public_selection_contract_rejects_wrong_present_evidence_types(value):
    from pydantic import ValidationError

    from fatebridge.core.output_numerology import CanpingTextSelection

    with pytest.raises(ValidationError):
        CanpingTextSelection.model_validate(value)


@pytest.mark.parametrize(
    "value",
    [
        {"body_reading_status": "source_body_printed_blank"},
        {"number_reading_evidence": {"observed_header": "□□四八"}},
        {"reading_revision": {"previous_text": "□女乘龍去，□□結子□。"}},
    ],
)
def test_public_evidence_leaves_project_without_requiring_siblings(value):
    from fatebridge.core.output_numerology import CanpingTextSelection

    CanpingTextSelection.model_validate(value)
