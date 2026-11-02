"""A gain from an old predicate cannot certify a new unexercised operator."""

import hashlib
import importlib.util
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_root_force_experiment_v4"
FIRST = ROOT / "docs/validation/bazi-root-force-first-v4.json"


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runner():
    spec = importlib.util.spec_from_file_location(
        "force_v4_audit", ROOT / "scripts/audit_bazi_root_force_v4.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_candidate_annotation_runner_and_first_result_remain_frozen_in_order():
    for p in [
        FIXTURE / "protocol.json",
        FIXTURE / "reference.json",
        FIXTURE / "pre-first-run.json",
        FIXTURE / "dependency-archive.json",
        FIRST,
    ]:
        assert digest(p) == p.with_suffix(".sha256").read_text().strip()
    protocol, reference, development = runner().load_frozen()
    pre = load(FIXTURE / "pre-first-run.json")
    assert (
        datetime.fromisoformat(protocol["frozen_at_utc"])
        < datetime.fromisoformat(reference["frozen_at_utc"])
        < datetime.fromisoformat(pre["recorded_at_utc"])
        < datetime.fromisoformat(load(FIRST)["recorded_at_utc"])
    )
    assert (
        digest(FIXTURE / "first-runner.py.txt")
        == pre["files"]["scripts/audit_bazi_root_force_v4.py"]
    )
    assert {"previous_v2_chapter", "previous_v3_chapter"} <= set(development["groups"])
    for name, entry in load(FIXTURE / "dependency-archive.json")["files"].items():
        assert (
            digest(FIXTURE / entry["archive"])
            == entry["sha256"]
            == protocol["candidate_dependencies"][name]
        )


def test_full_source_chapter_keeps_all_unknowns_and_raw_count_units():
    ref = load(FIXTURE / "reference.json")
    assert ref["source"]["pdf_pages"] == list(range(201, 219))
    assert len(ref["cases"]) == 28
    assert sum(c["expected_strength"] is None for c in ref["cases"]) == 21
    assert all(
        c["unseen_input"] and not c["prior_exact_pillar_overlaps"] for c in ref["cases"]
    )
    first = load(FIRST)
    assert (
        first["local_source_checks"]["matches"]
        == first["local_source_checks"]["assertions"]
        == 9
    )
    assert all(
        c["baseline_matches"] is c["candidate_matches"] is None
        for c in first["chapter_cases"]
        if c["expected_strength"] is None
    )


def test_old_capacity_gain_does_not_satisfy_new_operator_adoption_gate():
    first = load(FIRST)
    summary = first["chapter_summary"]
    assert (
        summary["baseline_matches"],
        summary["previous_v3_matches"],
        summary["candidate_matches"],
    ) == (4, 5, 5)
    assert summary["resolved_ids"] == ["DTCW1947-GS-01"]
    assert summary["new_operator_resolved_ids"] == []
    assert summary["candidate_mismatch_ids"] == ["DTCW1947-GS-03", "DTCW1947-GS-12"]
    assert not first["adoption_gates"][
        "new_passage_operator_resolves_nonoverlap_adjudicated_case"
    ]
    assert (
        not first["adoptable"]
        and not first["production_default_changed"]
        and not first["classical_acceptance_passed"]
    )


@pytest.mark.parametrize(
    "name", ["candidate.py.txt", "baseline_v5.py.txt", "source-chapter.pdf"]
)
def test_changed_candidate_kernel_or_source_is_rejected(tmp_path, monkeypatch, name):
    target = tmp_path / "fixture"
    shutil.copytree(FIXTURE, target)
    path = target / name
    path.write_bytes(path.read_bytes() + b"\nchanged after comparison\n")
    module = runner()
    monkeypatch.setattr(module, "FIXTURE", target)
    with pytest.raises(ValueError, match="Frozen"):
        module.load_frozen()


def test_first_result_cannot_be_overwritten(tmp_path, monkeypatch):
    p = tmp_path / "first.json"
    p.write_bytes(FIRST.read_bytes())
    module = runner()
    monkeypatch.setattr(
        sys, "argv", ["audit", "--candidate-root", str(tmp_path), "--output", str(p)]
    )
    with pytest.raises(FileExistsError, match="immutable"):
        module.main()
    assert p.read_bytes() == FIRST.read_bytes()
