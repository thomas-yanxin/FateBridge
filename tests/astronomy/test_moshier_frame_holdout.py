"""Frozen external residuals remain evidence even when a model fails."""

import json
import sys
from pathlib import Path

from fatebridge.core import ephemeris_runtime as e
from scripts.astronomy import audit_moshier_frames as audit
from tests.astronomy import test_moshier_motion_frames as motion_frames
from tests.western import test_other_chart_physical_sources as shared_sources

analytical = motion_frames.analytical
ephemeris_files = shared_sources.ephemeris_files
restore_configuration = shared_sources.restore_configuration

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/data/astro/moshier_frames/protocol.json"
REFERENCE = ROOT / "tests/data/astro/moshier_frames/reference.json"


def test_both_frames_and_all_ten_targets_preserve_frozen_reference_identity():
    protocol, reference = audit.loaded(PROTOCOL, REFERENCE)
    assert protocol["frames"] == ["tropical", "lahiri"]
    assert len(reference["references"]) == 10
    assert reference["forbidden_implementation_imports"] == []
    assert protocol["display_longitude_speed_tolerance_arcsec_per_day"] == 0.002
    for body in reference["references"]:
        assert len(body["rows"]) == 12
        assert all(row["status"] == "available" for row in body["rows"])
        assert all("erfa_lahiri_frame" in row for row in body["rows"])


def test_swiss_shared_frames_keep_the_external_accuracy_line(ephemeris_files):
    _, path = ephemeris_files
    e.swe.close()
    e.configure_ephemeris_path(str(path))
    result = audit.evaluate(*audit.loaded(PROTOCOL, REFERENCE))
    assert result["requested"] == len(result["rows"]) == result["passed"] == 240
    assert result["source_errors"] == result["unresolved_reference"] == 0
    assert {row["actual_model"] for row in result["rows"]} == {"swieph"}
    assert not result["all_four_objectives_validated"]
    assert not result["authority_certified"]


def test_moshier_keeps_failures_nonconvergence_and_exit_status(
    analytical, tmp_path, monkeypatch
):
    output = tmp_path / "audit.json"
    monkeypatch.setattr(sys, "argv", ["audit", "--output", str(output)])
    status = audit.main()
    result = json.loads(output.read_text())
    assert result["requested"] == len(result["rows"]) == 240
    assert result["source_errors"] == result["unresolved_reference"] == 0
    assert len({(r["body"], r["date_tt"], r["frame"]) for r in result["rows"]}) == 240
    assert result["passed"] == sum(row["passed"] for row in result["rows"])
    assert status == (0 if result["numerical_subset_checks_passed"] else 1)
    for row in result["rows"]:
        assert row["actual_model"] == "moshier"
        assert "native_signed_residual_arcsec_per_day" in row
        receipt = row["motion_policy"]["complete_position_derivatives"][
            row["body"] + ":" + row["frame"]
        ]
        if receipt["status"] == "not_applied":
            assert receipt["reason"] == "position_motion_not_converged"
            assert "longitude_speed_position_derivative_correction" not in row["state"]
    assert not result["all_four_objectives_validated"]
    assert not result["authority_certified"]


def test_modified_reference_is_rejected_before_querying_any_candidate(
    tmp_path, monkeypatch
):
    altered = tmp_path / "changed.json"
    altered.write_bytes(REFERENCE.read_bytes() + b"\n")
    output = tmp_path / "audit.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit",
            "--reference",
            str(altered),
            "--output",
            str(output),
        ],
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Reference integrity precedes candidate evaluation")

    monkeypatch.setattr(audit, "evaluate", forbidden)
    assert audit.main() == 2
    assert "reference_validation_error" in json.loads(output.read_text())
