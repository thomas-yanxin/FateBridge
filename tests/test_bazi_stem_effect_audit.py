"""First failures, unknown source judgments and post-comparison errata persist."""

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_stem_transformation_v1"
FIRST = ROOT / "docs/validation/bazi-stem-effects-first-v1.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def test_trial_order_and_every_numerical_dependency_are_preserved():
    for path in [
        FIXTURE / "protocol.json",
        FIXTURE / "reference.json",
        FIXTURE / "pre-first-run.json",
        FIRST,
    ]:
        assert digest(path) == path.with_suffix(".sha256").read_text().strip()
    protocol = load(FIXTURE / "protocol.json")
    reference = load(FIXTURE / "reference.json")
    before = load(FIXTURE / "pre-first-run.json")
    first = load(FIRST)
    assert (
        datetime.fromisoformat(protocol["frozen_at_utc"])
        < datetime.fromisoformat(reference["frozen_at_utc"])
        < datetime.fromisoformat(before["recorded_at_utc"])
        < datetime.fromisoformat(first["recorded_at_utc"])
    )
    assert digest(FIXTURE / "first-runner.py.txt") == before["runner_sha256"]
    for receipt in protocol["candidate_dependencies"].values():
        assert digest(FIXTURE / receipt["archive"]) == receipt["sha256"]
    assert digest(FIXTURE / "baseline-v5.py.txt") == protocol["baseline_sha256"]
    for path, expected in reference["source_files"].items():
        assert digest(FIXTURE / path) == expected


def test_complete_chapter_keeps_unknowns_and_failed_unrevealed_target():
    reference = load(FIXTURE / "reference.json")
    assert len(reference["cases"]) == 6
    assert sum(c["expected_strength"] is None for c in reference["cases"]) == 2
    first = load(FIRST)
    summary = first["summaries"]["new_heju_whole_chapter"]
    assert summary["source_known_conversion"] == 2
    assert summary["source_matches"] == summary["source_mismatches"] == 1
    assert summary["known_negative_matches"] == 0
    assert summary["strength_matches"] == {
        "baseline": 2,
        "precise_binding": 2,
        "candidate": 2,
    }
    failed = next(
        c
        for c in first["groups"]["new_heju_whole_chapter"]
        if c["id"] == "DTCW1947-HJ-03"
    )
    assert failed["source_checks"][0]["expected_converted"] is True
    assert failed["source_checks"][0]["matches"] is False
    assert not failed["stem_effects"]["decisions"][0]["conditions"][
        "target_physically_revealed"
    ]
    assert not first["adopted"] and not first["full_classical_acceptance"]
    assert not first["gates"]["fresh_explicit_positive_and_negative"]


def test_postcomparison_correction_does_not_rewrite_original_labels_or_scores():
    old = ROOT / "tests/fixtures/bazi_root_force_experiment_v4/reference.json"
    errata = ROOT / "tests/fixtures/bazi_classical_corrections_v1/errata.json"
    correction = load(errata)
    assert digest(old) == correction["original_reference_sha256"]
    assert digest(errata) == errata.with_suffix(".sha256").read_text().strip()
    original = next(c for c in load(old)["cases"] if c["id"] == "DTCW1947-GS-18")
    assert original["expected_strength"] is None
    assert correction["corrections"][0]["corrected_value"] == "强"
    assert not correction["corrections"][0]["new_independent_validation_case"]
    summaries = load(FIRST)["summaries"]
    assert summaries["exposed_v4"]["known_strength"] == 7
    assert summaries["exposed_v4_postcomparison_correction"]["known_strength"] == 8


def test_runner_cannot_overwrite_frozen_first_result():
    before = FIRST.read_bytes()
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/audit_bazi_stem_effects.py"),
            "--output",
            str(FIRST),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 and "reserved" in result.stderr
    assert FIRST.read_bytes() == before


def test_historical_candidate_replays_from_archived_dependencies(tmp_path):
    output = tmp_path / "replay.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/audit_bazi_stem_effects.py"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    first = load(FIRST)
    replay = load(output)
    for key in (
        "groups",
        "summaries",
        "gates",
        "candidate_dependencies",
        "protocol_sha256",
        "reference_sha256",
    ):
        assert replay[key] == first[key]
