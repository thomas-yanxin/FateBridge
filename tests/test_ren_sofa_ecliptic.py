"""Reference-frame alignment cannot erase the old PMO/cross-frame failures."""

import hashlib
import importlib.util
import json
import shutil
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ren_sofa", ROOT / "scripts/audit_ren_sofa_ecliptic.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_same_113_anchors_and_independent_frame_transforms_keep_scope():
    ref = AUDIT.reference()
    assert len(ref["reference"]["records"]) == 113
    assert {r["label_time_scale"] for r in ref["reference"]["records"]} == {
        "UT1",
        "UTC",
    }
    assert (
        sum(r["label_time_scale"] == "UT1" for r in ref["reference"]["records"]) == 33
    )
    assert ref["reference"]["production_imported"] is False
    assert ref["protocol"]["transform"]["apply_aberration_or_deflection_again"] is False
    assert ref["protocol"]["transform"]["apply_observed_eop"] is False


def test_actual_default_coordinates_match_the_transformed_directions_only():
    result = AUDIT.audit()
    assert result["expected_count"] == result["compared_count"] == 113
    assert (
        not result["calculation_errors"]
        and not result["transformed_direction_failures"]
    )
    assert result["original_cross_frame_failures"] > 0
    assert result["max_transformed_separation_arcseconds"] <= 0.1
    assert result["max_internal_route_separation_arcseconds"] <= 0.0000001
    assert result["implementation_unchanged_during_audit"]
    assert result["ephemeris_environment_unchanged"]
    assert result["selected_alignment_checks_passed"]
    assert not result["all_performed_comparisons_passed"]
    for key in (
        "pmo_model_equivalence_certified",
        "full_supported_calendar_domain_certified",
        "classical_acceptance_passed",
        "free_text_semantic_acceptance_passed",
        "goal_complete",
    ):
        assert result[key] is False
    assert (
        result["new_independent_events"]
        == result["new_horizons_queries"]
        == result["model_invocations"]
        == 0
    )


@pytest.mark.parametrize("change", ["edit", "missing", "extra"])
def test_frozen_reference_inventory_is_complete(tmp_path, change):
    corpus = tmp_path / "corpus"
    shutil.copytree(AUDIT.CORPUS, corpus)
    path = corpus / "reference.json"
    if change == "edit":
        path.write_text(path.read_text() + "changed")
    elif change == "missing":
        path.unlink()
    else:
        (corpus / "extra.json").write_text("{}")
    with pytest.raises(ValueError, match="Frozen ecliptic"):
        AUDIT.reference(corpus)


def reseal(corpus):
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    files = {
        name: hashlib.sha256(data).hexdigest()
        for name, data in AUDIT.source_contents(corpus).items()
        if name != "precomparison-freeze.json"
    }
    (corpus / "precomparison-freeze.json").write_text(
        json.dumps(dict(files=files, production_calculations_performed=False))
    )
    files["precomparison-freeze.json"] = sha(corpus / "precomparison-freeze.json")
    (corpus / "freeze.json").write_text(json.dumps(dict(files=files)))


def test_fallback_model_is_reported_without_relabelling_it_swiss():
    from tests.ephemeris_context import moshier_ephemeris as golden_ephemeris

    with golden_ephemeris():
        result = AUDIT.audit()
    assert {r["actual_model"] for r in result["comparisons"]} == {"moshier"}
    assert result["selected_alignment_checks_passed"]
    assert not result["full_supported_calendar_domain_certified"]
