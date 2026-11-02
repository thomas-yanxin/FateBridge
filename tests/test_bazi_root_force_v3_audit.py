"""Retain prospective source failures, unknown glyphs and the runner correction."""

import hashlib
import importlib.util
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_root_force_experiment_v3"
FIRST = ROOT / "docs/validation/bazi-root-force-first-v3.json"
SUPPLEMENT = ROOT / "docs/validation/bazi-root-force-supplement-v3.json"


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runner():
    spec = importlib.util.spec_from_file_location(
        "root_force_v3_audit", ROOT / "scripts/audit_bazi_root_force_v3.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_labels_and_first_runner_are_frozen_before_comparison():
    for p in [
        FIXTURE / "protocol.json",
        FIXTURE / "reference.json",
        FIXTURE / "pre-first-run.json",
        FIRST,
        SUPPLEMENT,
    ]:
        assert digest(p) == p.with_suffix(".sha256").read_text().strip()
    protocol, reference, _ = runner().load_frozen()
    provenance = load(FIXTURE / "pre-first-run.json")
    assert (
        datetime.fromisoformat(protocol["frozen_at_utc"])
        < datetime.fromisoformat(reference["frozen_at_utc"])
        < datetime.fromisoformat(provenance["recorded_at_utc"])
        < datetime.fromisoformat(load(FIRST)["recorded_at_utc"])
    )
    assert not provenance["first_comparison_executed"]
    assert (
        digest(FIXTURE / "first-runner.py.txt")
        == provenance["files"]["scripts/audit_bazi_root_force_v3.py"]
    )
    assert (
        load(FIRST)["dependency_sha256_before"]
        == load(FIRST)["dependency_sha256_after"]
        == protocol["candidate_dependencies"]
    )


def test_complete_chapter_retains_unknown_and_inconsistent_day_glyph():
    reference = load(FIXTURE / "reference.json")
    cases = reference["cases"]
    assert reference["source"]["pdf_pages"] == [197, 198, 199, 200]
    assert len(cases) == reference["complete_natal_examples"] == 4
    assert [c["expected_strength"] for c in cases] == ["强", None, "弱", None]
    assert all(
        c["unseen_input"] and not c["prior_exact_pillar_overlaps"] for c in cases
    )
    fourth = cases[3]
    assert fourth["pillars"][2] == "己巳"
    assert not fourth["input_consistency"]["hour_stem_matches_recorded_day"]
    assert [v["pillars"][2] for v in fourth["variants"]] == ["己巳", "辛巳"]
    for row in load(FIRST)["chapter_cases"]:
        if row["expected_strength"] is None:
            assert row["baseline_matches"] is row["candidate_matches"] is None
    assert len(load(FIRST)["chapter_cases"]) == 4


def test_development_gains_do_not_hide_failed_prospective_branch():
    first, followup = load(FIRST), load(SUPPLEMENT)
    assert first["chapter_cases"] == followup["chapter_cases"]
    assert (
        first["chapter_summary"]["baseline_matches"]
        == first["chapter_summary"]["candidate_matches"]
        == 1
    )
    assert first["chapter_summary"]["changed_ids"] == ["DTCW1947-TG-04"]
    assert first["chapter_summary"]["candidate_mismatch_ids"] == ["DTCW1947-TG-01"]
    assert not first["adoption_gates"]["nonoverlap_adjudicated_improvement"]
    assert not first["adoption_gates"]["nonoverlap_adjudicated_branch_change"]
    assert "previous_v2_chapter" not in first["development_groups"]
    previous = followup["development_groups"]["previous_v2_chapter"]
    assert previous["summary"]["complete_cases"] == 2
    assert previous["summary"]["candidate_matches"] == 1
    assert previous["summary"]["changed_ids"] == []
    assert not first["adoptable"] and not followup["adoptable"]
    assert (
        not followup["production_default_changed"]
        and not followup["classical_acceptance_passed"]
    )


@pytest.mark.parametrize(
    "name, message",
    [
        ("candidate.py.txt", "Frozen candidate"),
        ("source-chapter.pdf", "Frozen source"),
        ("reference.json", "Frozen file"),
    ],
)
def test_runner_rejects_changed_candidate_source_or_labels(
    tmp_path, monkeypatch, name, message
):
    fixture = tmp_path / "fixture"
    shutil.copytree(FIXTURE, fixture)
    module = runner()
    monkeypatch.setattr(module, "FIXTURE", fixture)
    path = fixture / name
    path.write_bytes(path.read_bytes() + b"\nchanged after first comparison\n")
    with pytest.raises(ValueError, match=message):
        module.load_frozen()


def test_existing_first_outcome_cannot_be_overwritten(tmp_path, monkeypatch):
    output = tmp_path / "result.json"
    output.write_bytes(FIRST.read_bytes())
    module = runner()
    monkeypatch.setattr(
        sys,
        "argv",
        ["audit", "--candidate-root", str(tmp_path), "--output", str(output)],
    )
    with pytest.raises(FileExistsError, match="immutable"):
        module.main()
    assert output.read_bytes() == FIRST.read_bytes()
