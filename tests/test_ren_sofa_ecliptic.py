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


@pytest.mark.parametrize("change", ["edit", "extra_member", "duplicate_source"])
def test_generator_archive_preserves_its_original_logical_hash(tmp_path, change):
    corpus = tmp_path / "source"
    shutil.copytree(AUDIT.CORPUS, corpus)
    archive = corpus / "reference-generator.zip"
    with zipfile.ZipFile(archive) as z:
        original = z.read("build_reference.py")
    if change == "duplicate_source":
        (corpus / "build_reference.py").write_bytes(original)
    else:
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr(
                "build_reference.py",
                original + b"changed" if change == "edit" else original,
            )
            if change == "extra_member":
                z.writestr("extra.txt", b"unexpected")
    with pytest.raises(ValueError):
        AUDIT.reference(corpus)


@pytest.mark.parametrize(
    "change", ["threshold", "anchor", "omit_case", "input_ra", "tt_proxy"]
)
def test_rehashing_does_not_excuse_a_different_cohort_or_input(tmp_path, change):
    corpus = tmp_path / "corpus"
    shutil.copytree(AUDIT.CORPUS, corpus)
    p = corpus / (
        "protocol.json" if change in {"threshold", "anchor"} else "reference.json"
    )
    data = json.loads(p.read_text())
    if change == "threshold":
        data["criteria"]["transformed_direction_arcseconds"] = 1
    elif change == "anchor":
        data["cohort"][0]["query_label"] = "wrong"
    elif change == "omit_case":
        data["records"].pop()
    elif change == "input_ra":
        data["records"][0]["ra_icrf_degrees"] += 1
    else:
        data["records"][0]["jd_tt_proxy"] += 1
    p.write_text(json.dumps(data))
    reseal(corpus)
    with pytest.raises(ValueError):
        AUDIT.reference(corpus)


@pytest.mark.parametrize(
    "change",
    [
        "shape",
        "orthogonal",
        "determinant",
        "nonfinite",
        "vector",
        "multiplication",
        "angle",
        "nonfinite_nutation",
    ],
)
def test_matrix_and_direction_receipts_do_not_accept_incoherent_values(change):
    row = deepcopy(AUDIT.reference()["reference"]["records"][0])
    if change == "shape":
        row["mean_ecliptic_matrix"].pop()
    elif change == "orthogonal":
        row["mean_ecliptic_matrix"][0][0] += 0.1
    elif change == "determinant":
        row["mean_ecliptic_matrix"][0] = [-v for v in row["mean_ecliptic_matrix"][0]]
    elif change == "nonfinite":
        row["mean_ecliptic_matrix"][0][0] = float("nan")
    elif change == "vector":
        row["reference_vector"][0] += 0.1
    elif change == "multiplication":
        row["transformed_mean_vector"][0] += 0.1
    elif change == "nonfinite_nutation":
        row["nutation_longitude_radians"] = float("nan")
    else:
        row["true_ecliptic_longitude_degrees"] += 1
    with pytest.raises(ValueError):
        AUDIT.validate_matrix_record(row)


@pytest.mark.parametrize("kind", ["missing", "error", "geometry", "nonfinite"])
def test_unavailable_or_invalid_calculation_cannot_drop_an_anchor(monkeypatch, kind):
    from fatebridge.core import ephemeris_runtime as runtime

    if kind == "missing":
        monkeypatch.setattr(runtime, "swe", None)
    else:

        def wrong(operation, jd, planet, flags):
            if kind == "error":
                raise RuntimeError("unavailable")
            return (float("nan") if kind == "nonfinite" else 0, 0, 1, 0, 0, 0), (
                2 if kind == "nonfinite" else 4098
            )

        monkeypatch.setattr(runtime, "ephemeris_call", wrong)
    result = AUDIT.audit()
    assert result["expected_count"] == 113 and result["compared_count"] == 0
    assert (
        len(result["calculation_errors"]) == 113
        and not result["selected_alignment_checks_passed"]
    )


def test_fallback_model_is_reported_without_relabelling_it_swiss():
    from tests.golden.runner import golden_ephemeris

    with golden_ephemeris():
        result = AUDIT.audit()
    assert {r["actual_model"] for r in result["comparisons"]} == {"moshier"}
    assert result["selected_alignment_checks_passed"]
    assert not result["full_supported_calendar_domain_certified"]
