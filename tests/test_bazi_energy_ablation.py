"""Arithmetic diagnostics retain failed and unknown source records verbatim."""

import gzip
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.audit_bazi_energy_ablation import audit

ROOT = Path(__file__).resolve().parents[1]
FIRST = ROOT / "docs/validation/bazi-energy-ablation-first-v1.json.gz"
FIXTURE = ROOT / "tests/fixtures/bazi_element_knowledge_v1"


def read_gzip(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def test_all349_original_objects_and_negative_claims_remain_exact():
    result = read_gzip(FIRST)
    corpus = read_gzip(ROOT / "docs/validation/bazi-source-corpus-first-v5.json.gz")
    expected = [
        (g, row) for g, value in corpus["groups"].items() for row in value["rows"]
    ]
    assert [(r["group"], r["original"]) for r in result["rows"]] == expected
    assert (
        result["original_local_and_negative_claims_unchanged"]
        == corpus["local_and_negative_claims"]
    )
    assert len(result["rows"]) == result["record_count"] == 349
    assert (
        sum(r["original"]["expected_strength"] is None for r in result["rows"]) == 234
    )
    assert not result["adopted"] and not result["production_policy_changed"]
    assert not result["source_labels_changed"] and not result["full_goal_complete"]
    assert result["overall_score"] is None
    assert result["real_world_efficacy"] == "not_tested"


def test_no_predeclared_simplification_resolves_the_focus_or_hides_regressions():
    result = read_gzip(FIRST)
    focus = result["focus"]
    assert focus["original"]["expected_strength"] == "弱"
    assert focus["original"]["actual_strength"] == "强"
    assert [a["numerical_ablation_grade"] for a in focus["arms"].values()] == [
        "强",
        "强",
        "强",
        "中和",
    ]
    for row in result["rows"]:
        a = row["original"]["assessment"]
        assert row["arms"]["baseline_weighted"]["arithmetic_share"] == pytest.approx(
            a["support_share"], abs=1e-12
        )
        assert all(
            arm["not_a_recomputed_final_strength"] for arm in row["arms"].values()
        )
    for arm, summary in result["summaries"].items():
        assert (
            summary["known_records"] == 115
            and summary["unknown_records_preserved"] == 234
        )
        if arm != "baseline_weighted":
            assert summary["new_mismatches_vs_baseline_arithmetic"]
            assert summary["changed_unknown_arithmetic_grades"]


def test_fresh_process_replays_first_receipt_and_refuses_to_overwrite(tmp_path):
    path = tmp_path / "new.json.gz"
    command = [
        sys.executable,
        str(ROOT / "scripts/audit_bazi_energy_ablation.py"),
        "--output",
        str(path),
    ]
    first = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    current, original = read_gzip(path), read_gzip(FIRST)
    assert current == audit()
    # Retain the first runner, then permit only its file digest to change after
    # wrapping a JSON-string equality in bool for mypy's no-any-return check.
    old_runner = FIXTURE / "ablation-runner-first.py"
    assert (
        hashlib.sha256(old_runner.read_bytes()).hexdigest() == original["runner_sha256"]
    )
    assert {k: v for k, v in current.items() if k != "runner_sha256"} == {
        k: v for k, v in original.items() if k != "runner_sha256"
    }
    sealed = path.read_bytes()
    second = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert second.returncode != 0 and "Refusing to overwrite" in second.stderr
    assert path.read_bytes() == sealed


def test_changed_protocol_is_rejected_before_reading_or_calculating(
    tmp_path, monkeypatch
):
    path = ROOT / "scripts/audit_bazi_energy_ablation.py"
    spec = importlib.util.spec_from_file_location("_ablation_corruption", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ["ablation-protocol.json", "ablation-protocol.sha256"]:
        shutil.copy2(FIXTURE / name, tmp_path / name)
    (tmp_path / "ablation-protocol.json").write_text("{}")
    monkeypatch.setattr(module, "FIXTURE", tmp_path)
    with pytest.raises(ValueError, match="Frozen ablation protocol changed"):
        module.audit()
