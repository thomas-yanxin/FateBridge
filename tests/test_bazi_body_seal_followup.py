"""An unchanged candidate, archived exposure and its failed fresh gate stay fixed."""

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
FIXTURE = ROOT / "tests/fixtures/bazi_body_seal_v5_followup_v1"
SCRIPT = ROOT / "scripts/audit_bazi_body_seal_followup.py"
FIRST = ROOT / "docs/validation/bazi-body-seal-followup-first-v1.json"


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module():
    spec = importlib.util.spec_from_file_location("body_seal_followup_guard", SCRIPT)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_exposure_reconstructs_from_exact_archived_bytes_and_source_is_complete():
    protocol, reference, exposure = module().load_inputs()
    pre = read(FIXTURE / "pre-first-run.json")
    first = read(FIRST)
    assert exposure["distinct_inputs"] == 248
    assert len(exposure["source_hashes"]) == 83
    assert len(reference["cases"]) == 26
    assert sum(c["new_nonoverlap_input"] for c in reference["cases"]) == 25
    assert sum(c["chapter"] == "順局" for c in reference["cases"]) == 9
    assert sum(c["chapter"] == "反局" for c in reference["cases"]) == 17
    times = [
        protocol["frozen_at_utc"],
        reference["frozen_at_utc"],
        pre["recorded_at_utc"],
        first["recorded_at_utc"],
    ]
    assert all(
        datetime.fromisoformat(a) < datetime.fromisoformat(b)
        for a, b in zip(times, times[1:])
    )
    assert digest(FIXTURE / "first-runner.py.txt") == pre["runner_sha256"]
    assert digest(SCRIPT) == pre["runner_sha256"]
    for path in [FIXTURE / "pre-first-run.json", FIRST]:
        assert digest(path) == path.with_suffix(".sha256").read_text().strip()


def test_unknown_functional_claims_do_not_become_ordinary_strength_passes():
    first = read(FIRST)
    summary = first["summary"]
    assert summary["new_known_strength"] == 1
    assert summary["new_unknown_strength"] == 24
    assert summary["new_strength_matches"] == {
        "production_v6": 1,
        "capacity_v3": 1,
        "hidden_seal_v5": 1,
    }
    assert summary["functional_or_structure_source_claims_retained"] == 26
    assert summary["functional_claims_scored_as_correct_from_ordinary_strength"] == 0
    assert not summary["new_v5_specific_gains"]
    assert not first["adoption_gates"]["fresh_v5_specific_gain"]
    assert not first["adopted"] and not first["production_default_changed"]
    # The new prohibition improves with the already-existing capacity v3 too;
    # it must not be counted as evidence for v5's hidden-seal modification.
    constraint = first["new_negative_constraints"][0]
    assert constraint["matches"] == {
        "production_v6": False,
        "capacity_v3": True,
        "hidden_seal_v5": True,
    }
    assert first["old_first_controls_reproduced"]
    assert all(
        r["matches"]["hidden_seal_v5"] is None
        for r in first["new_cases"]
        if r["expected_strength"] is None
    )


@pytest.mark.parametrize(
    "name", ["candidate.py.txt", "dependencies/src__fatebridge__core__strength.py.txt"]
)
def test_changed_candidate_or_dependency_cannot_reuse_the_frozen_study(
    name, tmp_path, monkeypatch
):
    audit = module()
    copy = tmp_path / "fixture"
    shutil.copytree(FIXTURE, copy)
    monkeypatch.setattr(audit, "FIXTURE", copy)
    target = copy / name
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="changed"):
        audit.load_inputs()


def test_archived_replay_preserves_first_result_and_refuses_overwrite(tmp_path):
    target = tmp_path / "replay.json"
    run = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    first, replay = read(FIRST), read(target)
    first.pop("recorded_at_utc")
    replay.pop("recorded_at_utc")
    assert first == replay
    preserved = FIRST.read_bytes()
    run = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(FIRST)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert run.returncode != 0 and "reserved" in run.stderr
    assert FIRST.read_bytes() == preserved
