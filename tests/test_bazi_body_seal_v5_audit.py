"""Keep the failed first ablation and source uncertainties independently auditable."""

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
FIXTURE = ROOT / "tests/fixtures/bazi_root_force_experiment_v5"
FIRST = ROOT / "docs/validation/bazi-body-seal-first-v5.json"
SCRIPT = ROOT / "scripts/audit_bazi_body_seal_v5.py"


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module():
    spec = importlib.util.spec_from_file_location("body_seal_v5_audit_guard", SCRIPT)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_frozen_chapter_keeps_unknowns_input_warning_and_boundary_exposure():
    for path in [
        FIXTURE / "protocol.json",
        FIXTURE / "prior-exposure.json",
        FIXTURE / "reference.json",
        FIXTURE / "pre-first-run.json",
        FIRST,
    ]:
        assert digest(path) == path.with_suffix(".sha256").read_text().strip()
    protocol, reference, exposure = module().load_frozen()
    pre = read(FIXTURE / "pre-first-run.json")
    times = [
        protocol["frozen_at_utc"],
        reference["frozen_at_utc"],
        pre["recorded_at_utc"],
        read(FIRST)["recorded_at_utc"],
    ]
    assert all(
        datetime.fromisoformat(a) < datetime.fromisoformat(b)
        for a, b in zip(times, times[1:])
    )
    assert digest(FIXTURE / "first-runner.py.txt") == pre["runner_sha256"]
    assert len(reference["cases"]) == 5
    assert sum(c["expected_strength"] is None for c in reference["cases"]) == 3
    warning = next(c for c in reference["cases"] if c["id"] == "DTCW1947-JC-04")
    assert warning["pillars"][1] == "丙寅"
    assert not warning["input_consistency"]["month_stem_matches_modern_year_rule"]
    assert all(c["new_nonoverlap_input"] for c in reference["cases"])
    known = {tuple(p) for p in exposure["pillars"]}
    assert all(
        tuple(p.split()) in known
        for p in reference["review"]["preceding_chapter_boundary379"]
    )


def test_exposed_repair_cannot_replace_a_new_operator_gain():
    first = read(FIRST)
    assert first["all_previous_v6_outputs_reproduced"]
    fresh = first["fresh_summary"]
    assert fresh["matches"] == {
        "production_v6": 1,
        "capacity_v3": 1,
        "hidden_seal_v5": 1,
    }
    assert fresh["v5_mismatch_ids"] == ["DTCW1947-JC-02"]
    assert not fresh["v5_specific_gain_ids"]
    development = first["summaries"]["new_jiahua_suiyun_whole_chapters"]
    assert development["v5_specific_gain_ids"] == ["DTCW1947-JH-02"]
    assert first["adoption_gates"]["no_exposed_regression"]
    assert not first["adoption_gates"]["new_v5_specific_gain"]
    assert not first["adopted"] and not first["production_default_changed"]
    unknown = next(
        c
        for c in first["groups"]["new_jiacong_whole_chapter"]
        if c["id"] == "DTCW1947-JC-03"
    )
    assert unknown["strengths"]["hidden_seal_v5"] == "强"
    assert unknown["expected_strength"] is None
    assert unknown["matches"]["hidden_seal_v5"] is None


def test_archived_replay_is_closed_and_original_output_cannot_be_overwritten(
    tmp_path, monkeypatch
):
    result = tmp_path / "replay.json"
    run = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(result)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    assert read(result)["groups"] == read(FIRST)["groups"]
    assert read(result)["adoption_gates"] == read(FIRST)["adoption_gates"]
    preserved = FIRST.read_bytes()
    run = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(FIRST)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert run.returncode != 0 and "reserved" in run.stderr
    assert FIRST.read_bytes() == preserved
    audit = module()
    copy = tmp_path / "fixture"
    shutil.copytree(FIXTURE, copy)
    monkeypatch.setattr(audit, "FIXTURE", copy)
    (copy / "candidate.py.txt").write_bytes(
        (copy / "candidate.py.txt").read_bytes() + b"\n"
    )
    with pytest.raises(ValueError, match="candidate changed"):
        audit.load_frozen()
