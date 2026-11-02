"""One unchanged event cohort, aligned geometry and retained failed gates."""

import hashlib
import importlib.util
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ren_inertial_audit", ROOT / "scripts/audit_ren_horizons_inertial.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_complete_prior_cohort_and_matching_of_date_controls():
    ref = AUDIT.reference()
    assert len(ref["rows"]) == len(ref["protocol"]["cohort"]) == 113
    assert sum(row["UT1-UTC"] is None for row in ref["rows"]) == 33
    assert all(row["matched"] for row in ref["repeated_of_date_controls"])
    assert ref["protocol"]["criteria"] == {
        "inertial_angular_separation_arcseconds": 0.1,
        "original_cross_frame_component_arcseconds": 0.1,
        "original_pmo_absolute_seconds": 30,
        "tdb_tt_proxy_max_seconds": 0.002,
    }


def test_aligned_directions_keep_actual_flags_models_and_limit_of_claim():
    report = AUDIT.audit()
    assert report["expected_count"] == report["compared_count"] == 113
    assert report["repeated_of_date_equal_count"] == 113
    assert not report["calculation_errors"] and not report["inertial_failure_count"]
    assert report["max_inertial_separation_arcseconds"] <= 0.1
    assert report["selected_inertial_comparison_passed"]
    assert report["implementation_unchanged_during_audit"]
    assert report["ephemeris_environment_unchanged_during_audit"]
    assert not report["original_pmo_criterion_changed"]
    assert not report["original_cross_frame_criterion_changed"]
    assert report["cross_frame_component_failure_count"] > 0
    assert not report["date_frame_equivalence_certified"]
    assert not report["goal_complete"]
    assert not report["full_supported_calendar_domain_certified"]
    assert not report["classical_acceptance_passed"]
    assert not report["free_text_semantic_acceptance_passed"]
    assert report["model_invocations"] == 0
    assert {r["query_label_scale"] for r in report["comparisons"]} == {"UT1", "UTC"}


@pytest.mark.parametrize("change", ["edit", "missing", "extra"])
def test_source_changes_cannot_reduce_the_denominator(tmp_path, change):
    corpus = tmp_path / "source"
    shutil.copytree(AUDIT.CORPUS, corpus)
    path = corpus / "collection/batch-00.attempt-1.response.json"
    if change == "edit":
        path.write_text(path.read_text() + "changed")
    elif change == "missing":
        path.unlink()
    else:
        (corpus / "extra.json").write_text("{}")
    with pytest.raises(ValueError, match="Frozen inertial source"):
        AUDIT.reference(corpus)


def reseal(corpus):
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    files = {
        str(p.relative_to(corpus)): sha(p)
        for p in corpus.rglob("*")
        if p.is_file() and p.name not in {"freeze.json", "precomparison-freeze.json"}
    }
    (corpus / "precomparison-freeze.json").write_text(
        json.dumps(dict(files=files, production_calculations_performed=False))
    )
    files["precomparison-freeze.json"] = sha(corpus / "precomparison-freeze.json")
    (corpus / "freeze.json").write_text(json.dumps(dict(files=files)))


@pytest.mark.parametrize(
    "change", ["threshold", "anchor", "scale", "frame", "submitted_text"]
)
def test_rehashing_does_not_excuse_changed_criteria_or_wrong_geometry(tmp_path, change):
    corpus = tmp_path / "source"
    shutil.copytree(AUDIT.CORPUS, corpus)
    p = corpus / "protocol.json"
    d = json.loads(p.read_text())
    if change == "threshold":
        d["criteria"]["inertial_angular_separation_arcseconds"] = 1
        p.write_text(json.dumps(d))
    elif change in {"anchor", "scale"}:
        d["cohort"][0][
            "query_label" if change == "anchor" else "label_time_scale"
        ] = "wrong"
        p.write_text(json.dumps(d))
    else:
        p = corpus / "collection/batch-00.query.json"
        d = json.loads(p.read_text())
        if change == "frame":
            d["params"]["REF_SYSTEM"] = "'B1950'"
            text = (
                "!$$SOF\n"
                + "\n".join(k + "=" + v for k, v in d["params"].items())
                + "\n"
            )
        else:
            text = "!$$SOF\nCOMMAND='301'\n"
        submitted = corpus / "collection/batch-00.input.txt"
        submitted.write_text(text)
        d["input_sha256"] = hashlib.sha256(submitted.read_bytes()).hexdigest()
        p.write_text(json.dumps(d))
    reseal(corpus)
    with pytest.raises(ValueError):
        AUDIT.reference(corpus)


def test_treating_ut_as_tt_is_detected_by_the_independent_positions(monkeypatch):
    bad = deepcopy(AUDIT.reference())
    for row in bad["rows"]:
        row["TDB-UT"] = 0
    monkeypatch.setattr(AUDIT, "reference", lambda: bad)
    report = AUDIT.audit()
    assert report["compared_count"] == 113 and not report["calculation_errors"]
    assert report["inertial_failure_count"] > 0
    assert not report["selected_inertial_comparison_passed"]
    assert all(
        not r["within_inertial_criterion"]
        for r in report["comparisons"]
        if r["query_label_scale"] == "UTC"
    )


def test_unavailable_native_module_keeps_the_entire_cohort(monkeypatch):
    from fatebridge.core import ephemeris_runtime as runtime

    monkeypatch.setattr(runtime, "swe", None)
    report = AUDIT.audit()
    assert report["compared_count"] == 0 and len(report["calculation_errors"]) == 113
    assert not report["selected_inertial_comparison_passed"]


@pytest.mark.parametrize("kind", ["error", "geometry", "nonfinite"])
def test_calculation_failures_keep_all_113_cases_and_cannot_pass(monkeypatch, kind):
    from fatebridge.core import ephemeris_runtime as runtime

    def wrong(operation, jd, planet, flags):
        if kind == "error":
            raise RuntimeError("unavailable test engine")
        return ((float("nan") if kind == "nonfinite" else 0), 0, 1, 0, 0, 0), (
            flags if kind == "nonfinite" else 2
        )

    monkeypatch.setattr(runtime, "ephemeris_call", wrong)
    report = AUDIT.audit()
    assert report["expected_count"] == 113 and report["compared_count"] == 0
    assert len(report["calculation_errors"]) == 113
    assert not report["selected_inertial_comparison_passed"]


def test_observed_source_drift_prevents_a_pass(monkeypatch):
    original = AUDIT.sha
    calls = 0

    def changed(path):
        nonlocal calls
        if path == ROOT / "src/fatebridge/core/almanac.py":
            calls += 1
            if calls > 1:
                return "0" * 64
        return original(path)

    monkeypatch.setattr(AUDIT, "sha", changed)
    report = AUDIT.audit()
    assert not report["implementation_unchanged_during_audit"]
    assert not report["selected_inertial_comparison_passed"]


def test_requested_swieph_fallback_is_reported_as_actual_moshier():
    from tests.golden.runner import golden_ephemeris

    with golden_ephemeris():
        report = AUDIT.audit()
    assert {r["actual_model"] for r in report["comparisons"]} == {"moshier"}
    assert report["selected_inertial_comparison_passed"]


def test_vector_separation_handles_wrap_poles_and_small_angles():
    assert AUDIT.separation_arcseconds(20, 5, 20, 5) == 0
    assert AUDIT.separation_arcseconds(359.999, 0, 0.001, 0) == pytest.approx(7.2)
    assert AUDIT.separation_arcseconds(0, 90, 180, 90) < 1e-9
    assert AUDIT.separation_arcseconds(0, 0, 0, 1 / 3600) == pytest.approx(1)
