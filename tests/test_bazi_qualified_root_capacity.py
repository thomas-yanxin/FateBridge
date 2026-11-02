"""A net gain cannot erase the first qualified-root candidate's regression."""

import gzip
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_qualified_root_capacity_v1"
SCRIPT = ROOT / "scripts/audit_bazi_qualified_root_capacity.py"
FIRST = ROOT / "docs/validation/bazi-qualified-roots-development-first-v1.json.gz"


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module():
    spec = importlib.util.spec_from_file_location("qualified_capacity_audit", SCRIPT)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def first():
    assert digest(FIRST) == Path(str(FIRST) + ".sha256").read_text().strip()
    return json.loads(gzip.decompress(FIRST.read_bytes()))


def test_full_old_objects_and_failed_gate_cannot_be_replaced_by_net_gain():
    result = first()
    summary = result["development_summary"]
    assert result["baseline_full_objects_reproduced"] == 304
    assert summary["different_inputs"] == 258
    assert summary["declared_strength_records"] == 98
    assert summary["baseline_matching_records"] == 73
    assert summary["candidate_matching_records"] == 79
    assert len(summary["gain_records"]) == 7
    assert len(summary["regressions"]) == 1
    assert summary["regressions"][0]["id"] == "DTCW1947-JC-01"
    assert not result["development_gate"] and not result["adopted"]
    assert not result["production_default_changed"]
    bad = next(r for r in result["development_rows"] if r["id"] == "DTCW1947-JC-01")
    assert bad["expected_strength"] == "弱"
    assert bad["observed"]["grades"]["qualified_roots"] == "强"
    assert bad["observed"]["candidate_receipts"]["qualified_roots"][
        "qualified_body_positions"
    ] == ["year", "day"]
    assert all(
        r["matches"]["qualified_roots"] is None
        for r in result["development_rows"]
        if r["expected_strength"] is None
    )


def test_exact_archived_exposure_and_frozen_chronology():
    inputs = module().load_inputs()
    assert inputs["exposure"]["distinct_inputs"] == 295
    assert len(inputs["exposure"]["source_hashes"]) == 575
    pre = read(FIXTURE / "pre-development.json")
    assert (
        digest(FIXTURE / "development-first-runner.py.txt")
        == pre["runner_sha256"]
        == digest(SCRIPT)
    )
    assert (
        datetime.fromisoformat(inputs["protocol"]["frozen_at_utc"])
        < datetime.fromisoformat(pre["recorded_at_utc"])
        < datetime.fromisoformat(first()["recorded_at_utc"])
    )
    assert not (FIXTURE / "reference.json").exists()
    assert inputs["protocol"]["prospective_source_plan"]["units"] == [
        "君象",
        "臣象",
        "母象",
        "子象",
    ]


def test_candidate_change_is_rejected_before_any_comparison(tmp_path, monkeypatch):
    audit = module()
    copy = tmp_path / "fixture"
    shutil.copytree(FIXTURE, copy)
    monkeypatch.setattr(audit, "FIXTURE", copy)
    target = copy / "candidate.py.txt"
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="changed"):
        audit.load_inputs()


def test_frozen_replay_and_first_result_overwrite_protection(tmp_path):
    target = tmp_path / "replay.json.gz"
    process = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--stage",
            "development",
            "--output",
            str(target),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    replay = json.loads(gzip.decompress(target.read_bytes()))
    original = first()
    replay.pop("recorded_at_utc")
    original.pop("recorded_at_utc")
    assert original == replay
    kept = FIRST.read_bytes()
    process = subprocess.run(
        [sys.executable, str(SCRIPT), "--stage", "development", "--output", str(FIRST)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert process.returncode != 0 and "reserved" in process.stderr
    assert FIRST.read_bytes() == kept
