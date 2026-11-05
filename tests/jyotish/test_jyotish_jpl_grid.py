"""Integrity and refusal gates for the sealed multi-era geometry audit."""

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.jyotish import audit_jyotish_jpl_grid as audit

FIXTURES = Path(__file__).parents[1] / "fixtures"
PROTOCOL = FIXTURES / "jyotish-jpl-grid-protocol.json"
REFERENCE = FIXTURES / "jyotish-jpl-grid-reference.json"
SCRIPT = Path(audit.__file__)


def test_sealed_grid_has_all_target_epochs_and_actual_raw_responses():
    protocol, reference = audit.load_reference(PROTOCOL, REFERENCE)
    assert len(protocol["epochs"]) == 30
    assert len(reference["rows"]) == 150
    assert protocol["position_line_arcsec"] == 0.02
    assert protocol["previous_raw_reference_overlap_jds"] == [2415021.0, 2451545.0]
    assert len(reference["references"]) == 5
    for raw in reference["references"]:
        encoded = raw["raw_response_utf8"].encode()
        assert hashlib.sha256(encoded).hexdigest() == raw["raw_sha256"]
        result = json.loads(encoded)["result"]
        assert "JDTT" in result and "GEOMETRIC cartesian states" in result
        assert raw["parameters"]["TIME_TYPE"] == "'TT'"
        rows = [r for r in reference["rows"] if r["body"] == raw["body"]]
        assert len(rows) == 30
        assert all(r["reference_raw_sha256"] == raw["raw_sha256"] for r in rows)
        assert all(
            math.isclose(math.hypot(*r["ecliptic_unit_vector"]), 1, abs_tol=1e-14)
            for r in rows
        )


@pytest.mark.parametrize("which", ["protocol", "reference"])
def test_edited_input_is_rejected_before_candidate_evaluation(tmp_path, which):
    source = PROTOCOL if which == "protocol" else REFERENCE
    edited = tmp_path / source.name
    edited.write_bytes(source.read_bytes() + b" ")
    with pytest.raises(ValueError, match="changed"):
        audit.load_reference(
            edited if which == "protocol" else PROTOCOL,
            edited if which == "reference" else REFERENCE,
        )


@pytest.mark.parametrize(
    "destination", ["kernel", "protocol", "reference", "existing_report"]
)
def test_cli_preserves_every_existing_input_and_report(tmp_path, destination):
    paths = {
        name: tmp_path / f"{name}.json"
        for name in ("kernel", "protocol", "reference", "existing_report")
    }
    for name, path in paths.items():
        path.write_text(name)
    before = {name: p.read_bytes() for name, p in paths.items()}
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--kernel",
            str(paths["kernel"]),
            "--protocol",
            str(paths["protocol"]),
            "--reference",
            str(paths["reference"]),
            "--report",
            str(paths[destination]),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "must not overwrite" in result.stderr
    assert all(p.read_bytes() == before[name] for name, p in paths.items())


def test_missing_kernel_is_a_failed_audit_with_a_failure_receipt(tmp_path):
    report = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--kernel",
            str(tmp_path / "missing.eph"),
            "--report",
            str(report),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    receipt = json.loads(report.read_text())
    assert receipt["status"] == "audit_error"
    assert receipt["rows"] == []
    assert "FileNotFoundError" in receipt["error"]


def test_direction_residual_retains_opposition_and_wraps_longitude():
    a = audit.unit({"longitude": 0.0, "latitude": 0.0})
    assert (
        audit.error_arcsec(a, audit.unit({"longitude": 360.0, "latitude": 0.0})) < 1e-9
    )
    assert (
        audit.error_arcsec(a, audit.unit({"longitude": 180.0, "latitude": 0.0}))
        == 648000
    )


@pytest.mark.parametrize("original_ok", [False, True])
def test_supplementary_result_cannot_change_original_acceptance(
    tmp_path, monkeypatch, original_ok
):
    """Injected audit-gate control, not a native numerical-accuracy case."""
    from fatebridge.core import ephemeris_runtime as e
    from fatebridge.core import jyotish_mean

    protocol, reference = audit.load_reference(PROTOCOL, REFERENCE)
    epochs = [r["jd_tt"] for r in protocol["epochs"]]

    def injected_points(jd, policy):
        assert policy == "require_data_files"
        epoch = min(epochs, key=lambda t: abs(t - jd))
        accepted = original_ok if jd == epoch else not original_ok
        result = {}
        for ref in reference["rows"]:
            if ref["jd_tt"] != epoch:
                continue
            x, y, z = ref["ecliptic_unit_vector"]
            result[ref["body"]] = {
                "longitude": math.degrees(math.atan2(y, x)) + (0 if accepted else 1),
                "latitude": math.degrees(math.atan2(z, math.hypot(x, y))),
                "frame": protocol["frame"],
                "ephemeris_model": "jpl",
            }
        return result

    kernel = tmp_path / "injected-gate-only.eph"
    real_digest = audit.digest
    monkeypatch.setattr(
        audit,
        "digest",
        lambda p: audit.KERNEL_SHA256 if p == kernel else real_digest(p),
    )
    monkeypatch.setattr(jyotish_mean, "geometric_points", injected_points)
    monkeypatch.setattr(e, "configure_ephemeris_path", lambda: None)
    # Register the original environment with pytest before the standalone
    # audit changes its own process configuration.
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", kernel.name)
    result = audit.audit(kernel, PROTOCOL, REFERENCE)
    assert len(result["rows"]) == 150
    assert all(r["passed"] is original_ok for r in result["rows"])
    assert (result["status"] == "passed_original_TT_grid") is original_ok
    for row in result["rows"]:
        diagnostic = row["supplementary_time_argument"]
        assert diagnostic["used_for_acceptance"] is False
        if not original_ok and diagnostic["argument_jd"] != row["jd_tt"]:
            assert diagnostic["residual_arcsec"] < 0.02
