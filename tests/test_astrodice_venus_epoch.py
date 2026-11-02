"""Partial support improvements never erase full-grid failures or outages."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts.audit_astrodice_venus_epoch import (
    audit,
    coverage_summary,
    support_comparison,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/astrodice-venus-epoch-v1"


def read(name):
    return json.loads((FIXTURE / name).read_text())


def test_all_original_data_and_first_failure_records_stay_bound():
    assert hashlib.sha256((FIXTURE / "manifest.json").read_bytes()).hexdigest() == (
        "1919f12a6a6ff3a6ba646e4b7152882f2095b5d5eba43d7b04241610b95353b4"
    )
    for name, digest in read("manifest.json")["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    source = read("candidate-seal-before-A.json")["candidate_files"]
    for name in [
        "scripts/astrodice_interval_reference.py",
        "scripts/astrodice_reference_infeasibility.py",
        "scripts/astrodice_reference_math.py",
        "scripts/audit_astrodice_local_reference.py",
        "scripts/audit_astrodice_horizons_wide_reference.py",
    ]:
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == source[name]
    assert read("original-overall-gate.json")["overall_numeric_gate_exit_code"] == 1


def test_partial_support_signal_and_complete_failures_both_replay():
    result = audit(FIXTURE)
    assert result == read("complete-reviewed-replay.json")
    assert result["candidate_accuracy_passes"] == 0
    assert not result["original_five_proofs_regraded"]
    assert {
        value["exit_code"] for value in result["complete_reference_chains"].values()
    } == {2}
    for encoding, changes in [("JD", 0), ("MJD", 8), ("CAL", 9)]:
        support = result["support_diagnostics"][encoding]
        assert support["primary_points"] == 13
        assert support["changed_printed_pairs_from_old"] == changes
        assert len(support["witnesses"]) == 5
        assert all(
            value["same_support_still_strictly_negative"] == (encoding == "JD")
            and not value["new_curve_feasibility_certified"]
            for value in support["witnesses"]
        )
    for encoding in ["MJD", "CAL"]:
        assert result["complete_coverage"]["A-" + encoding]["rejected_epoch_rows"] == 8
    # The invalid first summary is retained, not silently overwritten.
    assert read("first-coverage-summary.json")["B-JD"]["http_503_terminal_batches"] == 0
    assert result["complete_coverage"]["B-JD"]["http_503_terminal_batches"] == 13


def test_terminal_http_failure_is_counted_from_last_attempt_even_without_anchor_status():
    reference = {
        "batches": [{"batch": 1}, {"batch": 2}],
        "rows": [{"samples": {"0": None, "5": {"printed_angles": ["1", "2"]}}}],
    }
    journal = [
        {"batch": 1, "http_status": 503},
        {"batch": 1, "http_status": 200},
        {"batch": 2, "http_status": 503},
        {"batch": 2, "http_status": 503},
    ]
    result = coverage_summary(reference, journal)
    assert result["http_503_attempts"] == 3
    assert result["http_503_terminal_batches"] == 1
    assert result["accepted_primary_points"] == 1


def test_rebinding_reference_hash_does_not_relax_the_prequery_epoch_budget(tmp_path):
    copied = tmp_path / "fixture"
    shutil.copytree(FIXTURE, copied)
    protocol = copied / "A-JD-protocol.json"
    data = json.loads(protocol.read_text())
    data["timestamp_printing_tolerance_days"] = "0.000000002"
    protocol.write_text(json.dumps(data))
    new_hash = hashlib.sha256(protocol.read_bytes()).hexdigest()
    seal = copied / "A-JD-reference-seal.json"
    data = json.loads(seal.read_text())
    data["protocol_sha256"] = new_hash
    seal.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Predeclared complete protocol changed"):
        audit(copied)


def test_original_witness_cannot_be_replaced_by_a_more_favorable_support_list(tmp_path):
    copied = tmp_path / "fixture"
    shutil.copytree(FIXTURE, copied)
    plan = copied / "support-plan-before-queries.json"
    data = json.loads(plan.read_text())
    data["all_diagnostic_offsets_seconds"].remove(-1435)
    plan.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="support coverage changed"):
        support_comparison(copied)
