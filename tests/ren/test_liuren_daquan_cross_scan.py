"""Scan qualification keeps unknowns, subtype boundaries and original answers."""

import copy
import json
import shutil

import pytest

from scripts.ren.audit_liuren_daquan_cross_scan import CORPUS, audit, reference


def test_complete_printed_mention_cohort_preserves_unknowns_and_repeated_days():
    data = reference()
    rows = data["reference"]["rows"]
    assert len(rows) == 40
    assert sum(r["formula_expected"] is True for r in rows) == 26
    assert sum(r["formula_expected"] is False for r in rows) == 10
    assert {r["id"] for r in rows if r["formula_expected"] is None} == {
        "S13",
        "S22",
        "S24",
        "S36",
    }
    assert data["reference"]["distinct_assessable_contexts"] == 32
    assert data["reference"]["independent_real_events"] == 0
    assert data["witness"]["independent_blinded_reader"] is False
    assert data["witness"]["full_original_downloaded"] is False


def test_crossed_he_is_not_a_truth_label_for_every_named_jiaoche_subtype():
    result = audit()
    assert result["engineering_guard_passed"] is True
    assert len(result["selected_passages"]) == 3
    assert all(p["selected_passage_agrees"] for p in result["selected_passages"])
    assert result["coordinate_assessable"] == 36
    assert result["coordinate_unknown"] == 4
    assert result["original_contexts"] == 720
    assert result["failures"] == []
    harmed = [
        r
        for r in result["illustrations"]
        if r["reading"]["subheading"] in ("交車害", "交車沖")
    ]
    assert len(harmed) == 8
    assert all(r["actual"]["matched"] is False for r in harmed)
    assert all(r["calculation_agrees"] is True for r in harmed)
    assert result["source_qualification"] == (
        "three_selected_passages_visually_collated_not_whole_book"
    )
    assert result["subtype_formulae_adjudicated"] is False
    assert result["original_D11_D12_adjudicated"] is False
    assert result["production_source_metadata_requalified"] is False
    assert result["complete_classical_conformance"] is False
    assert result["goal_complete"] is False


@pytest.mark.parametrize("fault", ["named_heading_means_he", "certificate"])
def test_auditor_rejects_inflating_structure_or_whole_book_claims(monkeypatch, fault):
    import fatebridge.core.metaphysics.liureng_cross_harmony as production

    original = production.cross_harmony

    def wrong(*args):
        value = copy.deepcopy(original(*args))
        if fault == "named_heading_means_he":
            value["matched"] = True
        else:
            value["complete_classical_conformance"] = True
        return value

    monkeypatch.setattr(production, "cross_harmony", wrong)
    result = audit()
    assert result["engineering_guard_passed"] is False
    assert result["failures"]
    assert result["goal_complete"] is False


def test_new_source_cannot_silently_turn_original_nulls_into_an_answer(monkeypatch):
    import fatebridge.core.metaphysics.liureng_day_placements as production

    original = production.day_placement_patterns

    def wrong(*args):
        value = copy.deepcopy(original(*args))
        value["evaluations"][-2]["matched"] = False
        return value

    monkeypatch.setattr(production, "day_placement_patterns", wrong)
    result = audit()
    assert result["engineering_guard_passed"] is False
    assert len(result["failures"]) == 720
    assert all(not r["placement_facts_unchanged"] for r in result["original_rows"])


@pytest.mark.parametrize("fault", ["image", "coordinated_answer_and_manifest"])
def test_changed_source_or_jointly_rehashed_answer_is_rejected(tmp_path, fault):
    shutil.copytree(CORPUS, tmp_path / "reference")
    folder = tmp_path / "reference"
    if fault == "image":
        path = folder / "siku-0808-747.jpg"
        path.write_bytes(path.read_bytes() + b"changed")
        message = "content changed"
    else:
        path = folder / "reference.json"
        value = json.loads(path.read_text())
        value["rows"][12]["formula_expected"] = True
        path.write_text(json.dumps(value))
        from scripts.ren.audit_liuren_daquan_cross_scan import sha

        manifest = json.loads((folder / "freeze.json").read_text())
        manifest["files"]["reference.json"] = sha(path)
        (folder / "freeze.json").write_text(json.dumps(manifest))
        message = "identity changed"
    with pytest.raises(ValueError, match=message):
        reference(folder)
