"""A successful proof replay must preserve the unresolved aggregate result."""

import hashlib
import json
import subprocess
import sys

import pytest

from scripts.audit_astrodice_grid5_replay import FIXTURE, audit
from scripts.audit_astrodice_local_motion import require_declared_derivative


def test_sealed_replay_retains_failed_controls_and_missing_evidence(tmp_path):
    output = tmp_path / "audit.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.audit_astrodice_grid5_replay",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    r = json.loads(output.read_text())
    assert r["exit_code"] == 2 and not r["full_goal_complete"]
    assert r["new_holdout_conditions_in_this_replay"] == 0
    assert r["reference_results"]["development"]["exit_code"] == 2
    baseline = r["reference_results"]["fresh"]["raw_integrity_and_baseline_quality"]
    assert baseline["exit_code"] == 2
    assert baseline["failures"][0]["id"] == "fresh-grid5-3301-Venus"
    assert len(r["exact_incompatibility_proofs"]) == 5
    assert r["exact_coarse_dense_containment"] == {
        "checked": 176,
        "strictly_tighter": 168,
    }
    assert not r["candidate_history"]["candidate_recomputed"]
    original = hashlib.sha256(output.read_bytes()).hexdigest()
    retry = subprocess.run(result.args, capture_output=True, text=True)
    assert retry.returncode == 1 and "FileExistsError" in retry.stderr
    assert hashlib.sha256(output.read_bytes()).hexdigest() == original


def test_changed_manifest_cannot_relabel_the_known_failure(tmp_path):
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    manifest["known_development_still_unqualified"] = False
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    try:
        audit(tmp_path)
    except ValueError as error:
        assert "manifest changed" in str(error)
    else:
        raise AssertionError("A relabelled frozen experiment was accepted")


def test_derivative_version_cannot_change_without_an_explicit_frozen_declaration():
    v6 = "fatebridge_complete_position_derivative_v6"
    v7 = "fatebridge_complete_position_derivative_v7"
    require_declared_derivative({}, {"status": "applied", "method_id": v6})
    with pytest.raises(ValueError, match="not applied"):
        require_declared_derivative({}, {"status": "applied", "method_id": v7})
    declared = {
        "expected_derivative_method_id": v7,
        "candidate_files": {"src/fatebridge/core/astro/position_motion.py": "frozen"},
    }
    require_declared_derivative(declared, {"status": "applied", "method_id": v7})
    with pytest.raises(ValueError, match="not applied"):
        require_declared_derivative(declared, {"status": "applied", "method_id": v6})
    with pytest.raises(ValueError, match="not applied"):
        require_declared_derivative(declared, {"status": "partial", "method_id": v7})
    with pytest.raises(ValueError, match="not frozen"):
        require_declared_derivative(
            {**declared, "candidate_files": {}}, {"status": "applied", "method_id": v7}
        )
    with pytest.raises(ValueError, match="Unplanned"):
        require_declared_derivative(
            {**declared, "expected_derivative_method_id": "any-method"},
            {"status": "applied", "method_id": "any-method"},
        )


def test_v8_requires_the_stable_reduction_dependency_and_an_explicit_declaration():
    method = "fatebridge_complete_position_derivative_v8"
    policy = {"status": "applied", "method_id": method}
    with pytest.raises(ValueError, match="not applied"):
        require_declared_derivative({}, policy)
    source = {
        "expected_derivative_method_id": method,
        "candidate_files": {
            "src/fatebridge/core/astro/position_motion.py": "frozen",
        },
    }
    with pytest.raises(ValueError, match="not frozen"):
        require_declared_derivative(source, policy)
    source["candidate_files"]["src/fatebridge/core/astro/solar_decimal.py"] = "frozen"
    require_declared_derivative(source, policy)
