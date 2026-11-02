"""Frozen source clocks, failed analytic substitutions, and honest scope."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.audit_astrodice_tt_models import audit
from scripts.verify_astrodice_tt_models import NativeModel, verify

FIXTURE = Path(__file__).parent / "fixtures/astrodice-tt-models-v1"


def load(name, root=FIXTURE):
    return json.loads((root / name).read_text())


def test_frozen_protocol_raw_failures_and_sources_have_not_changed():
    manifest = FIXTURE / "manifest.json"
    assert (
        hashlib.sha256(manifest.read_bytes()).hexdigest()
        == "c8a9a152d102cbe30e180e7358c8d3b6236632a9e2497892f821d68b01d3b094"
    )
    for name, digest in load("manifest.json")["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    assert load("A-independent-replay-first-process.json")["exit_code"] == 1
    assert not (FIXTURE / "A-independent-replay-first.json").exists()
    assert load("retained/B-analysis-first-process.json")["exit_code"] == 1


def test_separate_author_C_and_exact_source_proofs_replay():
    for cohort, name in [
        ("A", "A-independent-replay-repaired.json"),
        ("B", "B-independent-replay-first.json"),
    ]:
        actual = verify(FIXTURE, cohort)
        original = load(name)
        attempts = actual.pop("native_compilation_attempts")
        original_attempts = original.pop("native_compilation_attempts")
        assert actual == original
        assert attempts and attempts[-1]["exit_code"] == 0
        assert all(row["exit_code"] != 0 for row in attempts[:-1])
        assert original_attempts and original_attempts[-1]["exit_code"] == 0


def test_replay_rejects_unavailable_author_C_compilation(monkeypatch):
    def fail_compilation(args, **kwargs):
        return subprocess.CompletedProcess(
            args, 1, stdout="", stderr="injected compiler failure"
        )

    monkeypatch.setattr(
        "scripts.verify_astrodice_tt_models.subprocess.run", fail_compilation
    )
    with pytest.raises(ValueError, match="Author C compilation unavailable"):
        NativeModel((FIXTURE / "authority/dtdb.c").read_bytes())


@pytest.mark.parametrize("reseal", [False, True])
def test_audit_rejects_rewritten_historical_compiler_receipt(tmp_path, reseal):
    root = tmp_path / "input"
    shutil.copytree(FIXTURE, root)
    path = root / "A-independent-replay-repaired.json"
    original = load(path.name, root)
    original["native_compilation_attempts"][0]["compiler"] = "rewritten compiler"
    path.write_text(json.dumps(original))
    if reseal:
        manifest = load("manifest.json", root)
        manifest["files"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(
        ValueError, match="Frozen (manifest|independent replay receipt) changed"
    ):
        audit(root)


def test_posthoc_audit_keeps_original_continuous_failures():
    actual = audit(FIXTURE)
    assert actual == load("posthoc-audit-first.json")
    for row in actual["summary"]["B"].values():
        assert row["rows"] == 30 and row["qualified_not_refuted"] == row["overlap"] == 0
    assert actual["production_acceptance_exit_code"] == 2
    assert actual["retained_overall_numeric_gate_exit_code"] == 1
    assert not actual["full_goal_complete"]


def test_five_new_contexts_are_not_thirty_candidate_accuracy_holdouts():
    value = load("posthoc-audit-first.json")
    assert (
        value["new_TT_source_conditions"] == 5 and value["new_candidate_holdouts"] == 0
    )
    assert len(value["same_TT_pairs"]) == 30
    wide = [
        r
        for r in value["same_TT_pairs"]
        if r["profile"] == "printing_plus_64_ULP_hypothesis"
    ]
    assert len(wide) == 15 and all(r["joint_necessary_not_refuted"] for r in wide)
    narrow = [r for r in value["same_TT_pairs"] if r["profile"] == "printing_only"]
    assert len(narrow) == 15 and not any(
        r["joint_necessary_not_refuted"] for r in narrow
    )


def test_rounding_diagnostics_are_not_a_regraded_prospective_result():
    d = load("posthoc-audit-first.json")
    assert not d["posthoc_rounding_is_new_independent_holdout"]
    rows = [
        r
        for r in d["posthoc_rounding_only"]
        if r["cohort"] == "B"
        and r["model"] == "NAIF_LSK_periodic"
        and r["profile"] == "printing_plus_64_ULP_hypothesis"
    ]
    assert len(rows) == 30
    for name in rows[0]["policies"]:
        assert sum(r["policies"][name]["compatible"] for r in rows) < 30
    assert d["TT_minus_TDB_series_in_original_DE441"].startswith("not_present")


@pytest.mark.parametrize("mutation", ["promote", "drop", "body", "count"])
def test_independent_check_rejects_forged_success_or_lost_coverage(tmp_path, mutation):
    root = tmp_path / "input"
    shutil.copytree(FIXTURE, root)
    path = root / "B-first-analysis.json"
    value = load("B-first-analysis.json", root)
    if mutation == "promote":
        model = value["queries"][0]["rows"][0]["models"]["NAIF_LSK_periodic"]
        model["printing_plus_64_ULP_hypothesis"]["qualified_not_refuted"] = True
    elif mutation == "drop":
        value["queries"][0]["rows"].pop()
    elif mutation == "body":
        value["queries"][0]["body"] = "Venus"
    else:
        value["new_TT_source_conditions"] = 30
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        verify(root, "B")
