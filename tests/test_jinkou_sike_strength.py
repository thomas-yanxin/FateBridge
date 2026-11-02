"""Preserve raw context differences rather than optimizing a conformance score."""

import copy
import json
import shutil

import pytest

from scripts.audit_jinkou_sike_strength import CORPUS, audit, reference, sha


def test_entire_five_example_cohort_preserves_missing_months_and_duplicate_quotation():
    data = reference()
    cases = data["readings"]["cases"]
    assert len(cases) == 5
    assert [c["month_number_literal"] for c in cases] == [2, None, None, None, None]
    assert cases[1]["day_ganzhi_literal"] is None
    assert cases[4]["day_ganzhi_literal"] is None
    assert len(data["readings"]["mentions"]) == 8
    assert data["readings"]["mentions"][-1]["duplicate_of"] == "R07"
    assert data["witness"]["source_pdf_pages"] == list(range(178, 191))
    assert data["witness"]["reader_count"] == 1
    assert data["witness"]["blinded"] is False


def test_source_failures_unknown_layer_and_old_failed_row_remain_visible():
    result = audit()
    assert result["engineering_guard_passed"] is True
    assert result["all_raw_strength_mentions_agree"] is False
    assert (
        result["raw_same_count"],
        result["raw_different_count"],
        result["raw_unmapped_count"],
    ) == (4, 3, 1)
    assert [
        r["reading"]["id"]
        for r in result["raw_strength_mentions"]
        if r["raw_same_state"] is False
    ] == ["R01", "R02", "R03"]
    assert result["raw_strength_mentions"][2]["reading"]["stated"] == "旺"
    assert result["raw_strength_mentions"][2]["current_bounded_state"] == "死"
    assert result["raw_strength_mentions"][2]["source_intended_layer"] is None
    assert result["raw_strength_mentions"][5]["reading"]["stated"] == "衰"
    assert result["raw_strength_mentions"][5]["raw_same_state"] is None
    old = result["original_scan_audit"]
    assert (old["scan_case_count"], old["scan_matched_count"]) == (12, 11)
    assert old["scan_failures"][0]["id"] == "S01"
    assert old["older_online_matched_count"] == 12
    assert result["source_intended_layers_adjudicated"] is False
    assert result["classical_acceptance_passed"] is False
    assert result["goal_complete"] is False


def test_case_specific_fire_override_is_detected_instead_of_hiding_raw_difference(
    monkeypatch,
):
    import fatebridge.core.metaphysics.jinkou_strength as production

    original = production.internal_strength

    def wrong(rows):
        value = copy.deepcopy(original(rows))
        if [r["element"] for r in rows] == list("木水金火"):
            value["anchor_element"] = "火"
        return value

    monkeypatch.setattr(production, "internal_strength", wrong)
    result = audit()
    assert result["engineering_guard_passed"] is False
    assert result["engineering_guard_failures"][0]["reading"]["id"] == "C02"
    assert result["goal_complete"] is False


@pytest.mark.parametrize(
    "field", ["daily_five_states_adjudicated", "complete_classical_acceptance"]
)
def test_new_chapter_does_not_authorize_an_unqualified_certificate(monkeypatch, field):
    import fatebridge.core.metaphysics.jinkou_strength as production

    original = production.internal_strength

    def wrong(rows):
        value = copy.deepcopy(original(rows))
        value["source_evidence"][field] = True
        return value

    monkeypatch.setattr(production, "internal_strength", wrong)
    result = audit()
    assert result["engineering_guard_passed"] is False
    assert all(not c["unqualified_certificate_absent"] for c in result["cases"])


@pytest.mark.parametrize("fault", ["image", "coordinated_answer_and_manifest"])
def test_changing_source_or_rehashing_a_fixed_answer_does_not_redefine_acceptance(
    tmp_path, fault
):
    shutil.copytree(CORPUS, tmp_path / "reference")
    folder = tmp_path / "reference"
    if fault == "image":
        path = folder / "jingben-183.jpg"
        path.write_bytes(path.read_bytes() + b"changed")
        message = "content changed"
    else:
        path = folder / "readings.json"
        value = json.loads(path.read_text())
        value["mentions"][2]["stated"] = "死"
        path.write_text(json.dumps(value))
        manifest = json.loads((folder / "freeze.json").read_text())
        manifest["files"][path.name] = sha(path)
        (folder / "freeze.json").write_text(json.dumps(manifest))
        message = "identity changed"
    with pytest.raises(ValueError, match=message):
        reference(folder)
