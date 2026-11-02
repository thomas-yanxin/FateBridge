"""Frozen trials must preserve unknowns, failures and the first comparison."""

import importlib
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def audit_module(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return importlib.import_module("audit_bazi_root_force")


def test_experiment_replays_its_first_result_without_claiming_acceptance(audit_module):
    first = json.loads(
        (ROOT / "docs/validation/bazi-root-force-first-v1.json").read_text()
    )
    actual = audit_module.audit(allow_environment_drift=True, historical_replay=True)
    if "environment_drift" in actual:
        assert set(actual["environment_drift"]) <= {
            "uv.lock",
            "src/fatebridge/core/strength.py",
            "src/fatebridge/core/classical_roots.py",
            "src/fatebridge/core/classical_stages.py",
        }
        assert not actual["adoption_conditions"][
            "frozen_candidate_and_dependencies_verified"
        ]
        assert not actual["predeclared_adoption_conditions_passed"]
        assert actual["development_cases"] == first["development_cases"]
        assert actual["prospective_cases"] == first["prospective_cases"]
        with pytest.raises(ValueError, match="dependency changed"):
            audit_module.audit()
    else:
        assert actual["development_cases"] == first["development_cases"]
        assert actual["prospective_cases"] == first["prospective_cases"]
    assert (
        actual["replay_mode"] == "verified_historical_strength_not_current_production"
    )
    assert actual["full_classical_acceptance"] is False
    assert actual["production_default_changed"] is False
    assert actual["prospective_summary"]["unknown_labels"] == 27
    assert actual["prospective_summary"]["candidate_matches"] == 4
    assert len(actual["prospective_summary"]["unresolved_candidate_cases"]) == 3
    assert all(
        not v["root_capacity"]["applied"]
        for c in actual["prospective_cases"]
        for v in c["variants"]
    )


@pytest.mark.parametrize(
    "target",
    ["reference.json", "candidate.py.txt", "protocol.json", "dependencies.json"],
)
def test_altering_labels_or_candidate_invalidates_the_trial(
    audit_module, monkeypatch, tmp_path, target
):
    fixture = tmp_path / "fixture"
    shutil.copytree(audit_module.FIXTURE, fixture)
    monkeypatch.setattr(audit_module, "FIXTURE", fixture)
    path = fixture / target
    if target == "dependencies.json":
        data = json.loads(path.read_text())
        data["uv.lock"] = "0" * 64
        path.write_text(json.dumps(data))
    else:
        path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="changed after freeze"):
        audit_module.load_frozen()


def test_replay_cannot_overwrite_the_frozen_first_output(audit_module, monkeypatch):
    first = ROOT / "docs/validation/bazi-root-force-first-v1.json"
    before = first.read_bytes()
    monkeypatch.setattr(sys, "argv", ["audit", "--output", str(first)])
    with pytest.raises(ValueError, match="reserved"):
        audit_module.main()
    assert first.read_bytes() == before


def test_historical_replay_rejects_archive_edits_and_keeps_production(
    audit_module, monkeypatch, tmp_path
):
    import fatebridge.core.strength as production

    original_evaluate = production._evaluate
    original_method = production.STRENGTH_METHOD_ID
    audit_module.audit(allow_environment_drift=True, historical_replay=True)
    assert production._evaluate is original_evaluate
    assert production.STRENGTH_METHOD_ID == original_method
    archive = tmp_path / "modified.py.txt"
    archive.write_bytes(audit_module.BASELINE_ARCHIVE.read_bytes() + b"\n")
    monkeypatch.setattr(audit_module, "BASELINE_ARCHIVE", archive)
    with pytest.raises(ValueError, match="archive differs"):
        audit_module.audit(allow_environment_drift=True, historical_replay=True)


@pytest.mark.parametrize(
    "relative",
    [
        "src/fatebridge/core/classical_roots.py",
        "src/fatebridge/core/classical_stages.py",
    ],
)
def test_historical_replay_rejects_changed_helper_archives(
    audit_module, monkeypatch, tmp_path, relative
):
    fixture = tmp_path / "fixture"
    shutil.copytree(audit_module.FIXTURE, fixture)
    path = fixture / "historical_dependencies" / relative
    path.write_bytes(path.read_bytes() + b"\n")
    monkeypatch.setattr(audit_module, "FIXTURE", fixture)
    with pytest.raises(ValueError, match="helper archive differs"):
        audit_module.audit(allow_environment_drift=True, historical_replay=True)
