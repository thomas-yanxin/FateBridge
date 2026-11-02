"""Do not promote an exposed repair or an unsupported timing case to fresh success."""

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
FIXTURE = ROOT / "tests/fixtures/bazi_stem_transformation_v2"
FIRST = ROOT / "docs/validation/bazi-stem-effects-first-v2.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def runner():
    spec = importlib.util.spec_from_file_location(
        "bazi_v2_guard_runner", ROOT / "scripts/audit_bazi_stem_effects_v2.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ordered_freeze_and_every_dependency_remain_verifiable():
    for p in [
        FIXTURE / "protocol.json",
        FIXTURE / "reference.json",
        FIXTURE / "development-local-conversion.json",
        FIXTURE / "pre-first-run.json",
        FIRST,
    ]:
        assert digest(p) == p.with_suffix(".sha256").read_text().strip()
    protocol, reference, _ = runner().load_frozen()
    before = load(FIXTURE / "pre-first-run.json")
    assert (
        datetime.fromisoformat(protocol["frozen_at_utc"])
        < datetime.fromisoformat(reference["frozen_at_utc"])
        < datetime.fromisoformat(before["recorded_at_utc"])
        < datetime.fromisoformat(load(FIRST)["recorded_at_utc"])
    )
    assert digest(FIXTURE / "first-runner.py.txt") == before["runner_sha256"]


def test_complete_chapters_keep_all_eleven_charts_and_unsupported_pairs():
    reference = load(FIXTURE / "reference.json")
    assert len(reference["cases"]) == 11
    assert sum(c["expected_strength"] is None for c in reference["cases"]) == 9
    assert sum(len(c["local_conversion"]) for c in reference["cases"]) == 12
    assert (
        sum(
            p["expected_converted"] is not None
            for c in reference["cases"]
            for p in c["local_conversion"]
        )
        == 1
    )
    assert all(c["new_nonoverlap_input"] for c in reference["cases"])
    first = load(FIRST)
    new = first["summaries"]["new_jiahua_suiyun_whole_chapters"]
    assert new["applicable_source_known_pairs"] == 0
    assert new["known_positive_matches"] == new["known_negative_matches"] == 0
    assert new["strength_matches"] == {
        "production_v6": 1,
        "candidate_v1": 1,
        "candidate_v2": 1,
    }
    assert new["candidate_v2_mismatch_ids"] == ["DTCW1947-JH-02"]


def test_known_heju_repair_and_time_scope_gap_do_not_pass_adoption():
    first = load(FIRST)
    assert first["summaries"]["new_heju_whole_chapter"]["local_v2_gains_vs_v1"] == 1
    cross = first["cross_layer_negative"]
    assert cross["source"]["expected_converted"] is False
    assert (
        not cross["candidate_supports_scope"] and cross["predicted_converted"] is None
    )
    assert not cross["counted_as_success"]
    assert not first["adopted"] and not first["production_default_changed"]
    assert not first["adoption_gates"]["fresh_local_positive_and_negative"]
    assert not first["full_classical_acceptance"]


def test_later_full_passage_correction_keeps_the_wrong_first_label_visible():
    folder = ROOT / "tests/fixtures/bazi_classical_corrections_v2"
    correction = load(folder / "errata.json")
    old = ROOT / correction["original_development_labels"]
    assert digest(old) == correction["original_development_labels_sha256"]
    assert (
        next(
            c for c in load(old)["exposed_source_labels"] if c["id"] == "DTCW1947-GS-12"
        )["expected_converted"]
        is True
    )
    assert correction["corrections"][0]["corrected_value"] is False
    replay = load(folder / "corrected-exposed-replay.json")
    assert replay["matches"] == 2 and replay["distinct_development_cases"] == 3
    assert not replay["adopted"] and replay["new_independent_cases"] == 0
    assert not next(c for c in replay["cases"] if c["id"] == "DTCW1947-GS-12")[
        "matches"
    ]


def test_corrupt_candidate_is_rejected_and_first_result_cannot_be_overwritten(
    tmp_path, monkeypatch
):
    module = runner()
    fixture = tmp_path / "fixture"
    shutil.copytree(FIXTURE, fixture)
    monkeypatch.setattr(module, "FIXTURE", fixture)
    (fixture / "candidate.py.txt").write_bytes(
        (fixture / "candidate.py.txt").read_bytes() + b"\n"
    )
    with pytest.raises(ValueError, match="candidate changed"):
        module.load_frozen()
    before = FIRST.read_bytes()
    run = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/audit_bazi_stem_effects_v2.py"),
            "--output",
            str(FIRST),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert run.returncode != 0 and "reserved" in run.stderr
    assert FIRST.read_bytes() == before
