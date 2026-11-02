"""Keep rejected improvements, ungraded branch coverage and source overlap visible."""

import hashlib
import importlib.util
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_root_force_experiment_v2"
FIRST = ROOT / "docs/validation/bazi-root-force-first-v2.json"


def load(path):
    return json.loads(path.read_text())


def runner():
    spec = importlib.util.spec_from_file_location(
        "root_force_v2_audit", ROOT / "scripts/audit_bazi_root_force_v2.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_candidate_reference_and_first_failure_remain_frozen_in_order():
    for path in [FIXTURE / "protocol.json", FIXTURE / "reference.json", FIRST]:
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest()
            == path.with_suffix(".sha256").read_text().strip()
        )
    protocol, reference, _ = runner().load_frozen()
    first = load(FIRST)
    assert (
        datetime.fromisoformat(protocol["frozen_at_utc"])
        < datetime.fromisoformat(reference["frozen_at_utc"])
        < datetime.fromisoformat(first["recorded_at_utc"])
    )
    assert first["dependency_sha256_before"] == protocol["candidate_dependencies"]
    assert first["dependency_sha256_after"] == protocol["candidate_dependencies"]
    assert first["numerical_dependency_drift"] == []


def test_whole_chapter_keeps_both_natal_examples_and_excludes_luck_sequences():
    reference = load(FIXTURE / "reference.json")
    chapter = (FIXTURE / "source-chapter.txt").read_text()
    token = r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]"
    four_pillars = [
        re.findall(token, line)
        for line in chapter.splitlines()
        if re.fullmatch(rf"{token}(?: {token}){{3}}", line)
    ]
    assert four_pillars == [c["pillars"] for c in reference["cases"]]
    six_luck_columns = [
        line
        for line in chapter.splitlines()
        if re.fullmatch(rf"{token}(?: {token}){{5}}", line)
    ]
    assert len(four_pillars) == len(six_luck_columns) == 2
    mo, wang = reference["cases"]
    assert mo["expected_strength"] is None and mo["unseen_input"]
    assert wang["expected_strength"] == "弱" and not wang["unseen_input"]
    assert wang["prior_exact_pillar_overlaps"] == [
        {
            "source": "tests/fixtures/bazi-strength-reference.json",
            "id": "ditian_zhonghe_wang_example",
        }
    ]
    assert reference["nonoverlapping_adjudicated"] == 0


def test_six_exposed_improvements_do_not_cancel_two_new_errors():
    first = load(FIRST)
    groups = first["development_groups"]
    legacy = groups["legacy_strength"]["summary"]
    assert legacy["baseline_matches"] == 21
    assert legacy["candidate_matches"] == 19
    assert legacy["regression_ids"] == ["ditian_shuaiwang_07", "ditian_shuaiwang_12"]
    assert sum(len(g["summary"]["resolved_ids"]) for g in groups.values()) == 6
    assert not first["adoption_gates"]["no_exposed_matching_label_regression"]
    fresh = first["nonoverlapping_chapter_summary"]
    assert fresh["changed_ids"] == ["DTCW-ZHONGHE-MO"]
    assert fresh["adjudicated"] == fresh["candidate_matches"] == 0
    mo = first["chapter_cases"][0]
    assert mo["baseline_matches"] is mo["candidate_matches"] is None
    assert not first["adoption_gates"]["nonoverlap_adjudicated_branch_change"]
    assert not first["adoption_gates"]["nonoverlap_adjudicated_improvement"]
    assert not first["adoptable"] and not first["production_default_changed"]
    assert not first["classical_acceptance_passed"]
    # Even assuming a later source review, the failed numerical gates remain.
    gates = {
        **first["adoption_gates"],
        "source_and_survival_adoption_review_completed": True,
    }
    assert not all(gates.values())


def test_runner_refuses_changed_candidate_and_dependency_drift(tmp_path, monkeypatch):
    audit = runner()
    audit_dir = tmp_path / "fixture"
    audit_dir.mkdir()
    for path in FIXTURE.iterdir():
        if path.is_file():
            (audit_dir / path.name).write_bytes(path.read_bytes())
    monkeypatch.setattr(audit, "FIXTURE", audit_dir)
    candidate = audit_dir / "candidate.py.txt"
    candidate.write_text(candidate.read_text() + "\n# changed after seeing outcomes\n")
    with pytest.raises(ValueError, match="Frozen candidate changed"):
        audit.load_frozen()
    candidate.write_bytes((FIXTURE / candidate.name).read_bytes())
    protocol = load(FIXTURE / "protocol.json")
    frozen = tmp_path / "candidate"
    for name in protocol["candidate_dependencies"]:
        path = frozen / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not the frozen numerical dependency")
    with pytest.raises(ValueError, match="numerical dependencies differ"):
        audit.audit(frozen)


def test_runner_cannot_overwrite_a_rejected_first_outcome(tmp_path, monkeypatch):
    audit = runner()
    output = tmp_path / "first.json"
    original = FIRST.read_bytes()
    output.write_bytes(original)
    monkeypatch.setattr(
        sys,
        "argv",
        ["audit", "--candidate-root", str(tmp_path), "--output", str(output)],
    )
    with pytest.raises(FileExistsError, match="immutable"):
        audit.main()
    assert output.read_bytes() == original
