"""The second reference cohort remains frozen and separate from development."""

import json
import sys
from pathlib import Path

from fatebridge.core import ephemeris_runtime as e
from scripts.guolao import audit_guolao_moshier_motion as audit
from scripts.guolao.audit_guolao_motion import evaluate, load_reference
from tests.western import test_other_chart_physical_sources as shared_sources

ephemeris_files = shared_sources.ephemeris_files
restore_configuration = shared_sources.restore_configuration
ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/data/astro/guolao_moshier_motion/protocol.json"
REFERENCE = ROOT / "tests/data/astro/guolao_moshier_motion/reference.json"


def loaded():
    return load_reference(
        PROTOCOL,
        REFERENCE,
        protocol_sha256=audit.PROTOCOL_SHA256,
        reference_sha256=audit.REFERENCE_SHA256,
    )


def test_separate_declared_dates_and_reference_uncertainties():
    protocol, reference = loaded()
    old = json.loads(
        (ROOT / "tests/data/astro/guolao_motion/protocol.json").read_text()
    )
    assert not set(old["dates_tt"]) & set(protocol["dates_tt"])
    assert reference["forbidden_implementation_imports"] == []
    assert len(reference["references"]) == 7
    assert all(len(body["rows"]) == 12 for body in reference["references"])
    assert protocol["display_longitude_speed_tolerance_arcsec_per_day"] == 0.002


def test_swiss_new_holdout_uses_the_unchanged_accuracy_line(ephemeris_files):
    _, path = ephemeris_files
    e.swe.close()
    e.configure_ephemeris_path(str(path))
    report = evaluate(*loaded())
    assert report["requested"] == len(report["rows"]) == 84
    assert report["source_errors"] == report["unresolved_reference"] == 0
    assert {row["actual_model"] for row in report["rows"]} == {"swieph"}
    assert report["passed"] == 84
    assert report["numerical_subset_checks_passed"]
    assert not report["all_four_objectives_validated"]
    assert not report["authority_certified"]


def test_moshier_audit_retains_all_external_failures_and_correct_exit(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    e.swe.close()
    e.configure_ephemeris_path(str(tmp_path))
    output = tmp_path / "audit.json"
    monkeypatch.setattr(sys, "argv", ["audit", "--output", str(output)])
    code = audit.main()
    report = json.loads(output.read_text())
    assert report["requested"] == len(report["rows"]) == 84
    assert report["source_errors"] == report["unresolved_reference"] == 0
    assert {row["actual_model"] for row in report["rows"]} == {"moshier"}
    assert len({(row["body"], row["date_tt"]) for row in report["rows"]}) == 84
    assert report["passed"] == sum(row["passed"] for row in report["rows"])
    assert code == (0 if all(row["passed"] for row in report["rows"]) else 1)
    for row in report["rows"]:
        assert "native_signed_residual_arcsec_per_day" in row
        assert "signed_residual_arcsec_per_day" in row
    assert not report["all_four_objectives_validated"]
    assert not report["authority_certified"]


def test_changed_reference_is_rejected_before_any_candidate_evaluation(
    tmp_path, monkeypatch
):
    altered = tmp_path / "changed.json"
    altered.write_bytes(REFERENCE.read_bytes() + b"\n")
    output = tmp_path / "audit.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["audit", "--reference", str(altered), "--output", str(output)],
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Reference integrity must fail before evaluation")

    monkeypatch.setattr(audit, "evaluate", forbidden)
    assert audit.main() == 2
    report = json.loads(output.read_text())
    assert "reference_validation_error" in report
    assert not report["all_four_objectives_validated"]
