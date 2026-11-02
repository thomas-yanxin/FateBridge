"""Whole-chapter and edition boundaries must survive a successful label replay."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from tests.test_bazi_seasonal_studies import (
    frozen,
    historical_v5,
    run,
    study_tree,
)

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "tests/fixtures/bazi_seasonal_bureau_v4"


@pytest.fixture(scope="module")
def shuaiwang_tree(study_tree):
    destination = study_tree / FOLDER.relative_to(ROOT)
    shutil.copytree(FOLDER, destination)
    for relative, expected in frozen(FOLDER / "pre-first-run.json")[
        "frozen_files"
    ].items():
        target = study_tree / relative
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        assert hashlib.sha256(target.read_bytes()).hexdigest() == expected
    return study_tree


def test_complete_twenty_cases_keep_source_substates_and_same_case_exposure():
    reference = frozen(FOLDER / "reference.json")
    assert reference["source"]["selected_pdf_pages"] == list(range(175, 189))
    assert len(reference["cases"]) == 20
    assert all(c["expected_strength"] is not None for c in reference["cases"])
    assert not any(c["fresh_gate_eligible"] for c in reference["cases"])
    assert {c["source_strength_state"][1:] for c in reference["cases"]} == {
        "太旺",
        "旺极",
        "太衰",
        "衰极",
    }
    assert reference["exposure_policy_addendum"]["relaxes_adoption_gate"] is False


def test_following_three_units_are_fixed_without_tuning_the_candidate():
    following = ROOT / "tests/fixtures/bazi_seasonal_bureau_v5"
    protocol = frozen(following / "protocol.json")
    assert protocol["source_plan"]["selected_pdf_pages"] == list(range(188, 202))
    assert protocol["source_plan"]["chapters"] == ["中和", "源流", "通关"]
    assert (following / "candidate-core.py.txt").read_bytes() == (
        FOLDER / "candidate-core.py.txt"
    ).read_bytes()
    assert protocol["production_default_changed"] is False
    assert protocol["overall_score"] is None


def test_scanned_hour_variant_and_old_reference_are_both_preserved():
    reference = frozen(FOLDER / "reference.json")
    variant = next(c for c in reference["cases"] if c["id"] == "SW-12")
    assert variant["source_pdf_pages"] == [184]
    assert variant["pillars"] == ["癸酉", "甲子", "戊子", "壬子"]
    assert variant["expected_strength"] == "弱"
    assert variant["prior_exact_pillar_overlaps"] == []
    assert variant["fresh_gate_eligible"] is False
    legacy_path = ROOT / "tests/fixtures/bazi-strength-reference.json"
    assert (
        hashlib.sha256(legacy_path.read_bytes()).hexdigest()
        == reference["overlap_source_hashes"][str(legacy_path.relative_to(ROOT))]
    )
    legacy = json.loads(legacy_path.read_text())
    old = next(c for c in legacy["cases"] if c["id"] == "ditian_shuaiwang_12")
    assert old["pillars"]["hour"] == "戊午"
    assert len(legacy["cases"]) == 20 and len(legacy["additional_cases"]) == 1


def test_full_replay_cannot_promote_exposed_twenty_of_twenty_to_a_new_gate(
    shuaiwang_tree, tmp_path
):
    expected = frozen(
        ROOT / "docs/validation/bazi-seasonal-bureau-shuaiwang-first-v4.json"
    )
    output = tmp_path / "replay.json"
    process = run(shuaiwang_tree, "audit_bazi_seasonal_bureau_v4.py", output)
    assert process.returncode == 1, process.stderr
    actual = json.loads(output.read_text())
    actual["candidate_root"] = expected["candidate_root"]
    assert actual == expected
    group = actual["groups"]["complete_shuaiwang_scanned_edition"]
    assert (group["cases"], group["baseline_matched"], group["candidate_matched"]) == (
        20,
        20,
        20,
    )
    assert actual["source_exposure"]["exact_nonoverlap_cases"] == ["SW-12"]
    assert actual["source_exposure"]["fresh_gate_eligible_cases"] == []
    assert actual["numerical_gates_passed"] is False
    assert actual["production_default_changed"] is False
    assert actual["classical_acceptance_passed"] is False
    assert actual["overall_score"] is None


def test_first_report_counter_is_clarified_separately_without_overwriting():
    review = frozen(
        ROOT / "docs/validation/bazi-seasonal-bureau-shuaiwang-review-v1.json"
    )
    first = ROOT / review["first_report"]
    assert (
        hashlib.sha256(first.read_bytes()).hexdigest() == review["first_report_sha256"]
    )
    detail = review["metadata_clarification"]
    assert detail["literal_exact_nonoverlap_count"] == 1
    assert detail["gate_eligible_count"] == 0
    assert detail["original_report_overwritten"] is False
    assert detail["numerical_output_changed"] is False
    assert review["full_goal_achieved"] is False


def test_existing_first_result_is_not_overwritten(shuaiwang_tree, tmp_path):
    output = tmp_path / "keep.json"
    output.write_text("keep original bytes")
    process = run(shuaiwang_tree, "audit_bazi_seasonal_bureau_v4.py", output)
    assert process.returncode == 2
    assert output.read_text() == "keep original bytes"


def test_changed_legacy_edition_cannot_silently_replace_the_new_source(
    shuaiwang_tree, tmp_path
):
    tree = tmp_path / "tampered"
    shutil.copytree(shuaiwang_tree, tree)
    path = tree / "tests/fixtures/bazi-strength-reference.json"
    data = json.loads(path.read_text())
    data["cases"][11]["pillars"]["hour"] = "壬子"
    path.write_text(json.dumps(data))
    output = tmp_path / "forbidden.json"
    process = run(tree, "audit_bazi_seasonal_bureau_v4.py", output)
    assert process.returncode == 1
    assert "Edition crosscheck differs" in process.stderr
    assert not output.exists()
