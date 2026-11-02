"""Old gains cannot replace the fixed prospective adoption requirement."""

import gzip
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_root_load_capacity_v2"
DEVELOPMENT = ROOT / "docs/validation/bazi-root-load-development-first-v2.json.gz"
PROSPECTIVE = ROOT / "docs/validation/bazi-root-load-prospective-first-v2.json.gz"
CORPUS = ROOT / "docs/validation/bazi-source-corpus-first-v4.json.gz"
SCRIPT = ROOT / "scripts/audit_bazi_root_load_prospective.py"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache
def frozen_report(path):
    assert digest(path) == Path(str(path) + ".sha256").read_text().strip()
    return json.loads(gzip.decompress(path.read_bytes()))


def read(name):
    path = FIXTURE / name
    assert digest(path) == path.with_suffix(".sha256").read_text().strip()
    return json.loads(path.read_text())


def test_chronology_preserves_annotation_before_prospective_comparison():
    protocol, pre = read("protocol.json"), read("pre-development.json")
    development = frozen_report(DEVELOPMENT)
    before_source, reference = read("pre-source-reading.json"), read(
        "reference-freeze.json"
    )
    first_launch, repaired_launch = read("pre-prospective.json"), read(
        "pre-prospective-r2.json"
    )
    prospective = frozen_report(PROSPECTIVE)
    times = [
        protocol["frozen_at_utc"],
        pre["recorded_at_utc"],
        development["recorded_at_utc"],
        before_source["recorded_at_utc"],
        reference["recorded_at_utc"],
        first_launch["recorded_at_utc"],
        repaired_launch["recorded_at_utc"],
        prospective["recorded_at_utc"],
    ]
    parsed = [datetime.fromisoformat(t) for t in times]
    assert parsed == sorted(set(parsed))
    assert pre["prospective_units_not_read"]
    assert reference["all_four_units_transcribed_before_prospective_calculation"]
    assert reference["fresh_candidate_comparison_not_run"]
    assert first_launch["inputs"] == repaired_launch["inputs"]
    assert reference["candidate_sha256"] == protocol["candidate_sha256"]
    assert prospective["candidate_sha256"] == protocol["candidate_sha256"]
    assert reference["reference_sha256"] == prospective["reference_sha256"]


def test_first_v1_regression_and_all_its_receipts_are_still_present():
    old = json.loads(
        gzip.decompress(
            (FIXTURE / "qualified-roots-development-first-v1.json.gz").read_bytes()
        )
    )
    result = frozen_report(DEVELOPMENT)
    assert not old["development_gate"]
    assert old["development_summary"]["regressions"][0]["id"] == "DTCW1947-JC-01"
    assert (
        len(result["development_rows"])
        == result["failed_v1_full_receipts_reproduced"]
        == 304
    )
    for previous, current in zip(
        old["development_rows"], result["development_rows"], strict=True
    ):
        assert (
            previous["group"],
            previous["id"],
            previous["pillars"],
            previous["expected_strength"],
        ) == (
            current["group"],
            current["id"],
            current["pillars"],
            current["expected_strength"],
        )
        assert previous["observed"]["assessment"] == current["observed"]["assessment"]
        assert (
            previous["observed"]["candidate_receipts"]["qualified_roots"]
            == current["observed"]["candidate_receipts"]["qualified_roots_v1"]
        )


def test_root_quantity_rejects_jc01_without_deleting_jisi_roots():
    result = frozen_report(DEVELOPMENT)
    row = next(r for r in result["development_rows"] if r["id"] == "DTCW1947-JC-01")
    receipt = row["observed"]["candidate_receipts"]["root_load_v2"]
    assert row["expected_strength"] == row["observed"]["grades"]["root_load_v2"] == "弱"
    assert row["observed"]["grades"]["qualified_roots_v1"] == "强"
    assert receipt["qualified_body_positions"] == ["year", "day"]
    assert receipt["root_count_eligibility"] and not receipt["budget_eligibility"]
    assert receipt["qualified_body_physical_budget"] == pytest.approx(4 / 7)
    assert receipt["all_controller_physical_budget"] == 3.6
    assert not receipt["changed"]


def test_development_gains_receive_no_unseen_credit_or_adoption():
    result = frozen_report(DEVELOPMENT)
    summary = result["development_summary"]
    assert (
        summary["records"],
        summary["different_inputs"],
        summary["declared_strength_records"],
    ) == (304, 258, 98)
    assert (
        summary["baseline_matching_records"],
        summary["candidate_matching_records"],
    ) == (73, 80)
    assert len(summary["gain_records"]) == 7 and not summary["regressions"]
    assert summary["new_independent_credit"] == 0
    assert result["development_gate"] and not result["adopted"]
    negatives = result["negative_constraints"]
    assert [(r["id"], r["matches"]["root_load_v2"]) for r in negatives] == [
        ("GH-07", True),
        ("DTCW1947-SJ05", False),
    ]
    assert all(
        r["matches"]["production_v6"] == r["matches"]["root_load_v2"] for r in negatives
    )


def test_physical_budget_receipts_never_pool_seal_or_synthetic_tokens():
    result = frozen_report(DEVELOPMENT)
    for row in result["development_rows"]:
        assessment = row["observed"]["assessment"]
        receipt = row["observed"]["candidate_receipts"]["root_load_v2"]
        assert receipt["qualified_body_physical_budget"] == sum(
            r["remaining_hidden_mass"]
            for r in assessment["root_qualifications"]
            if r["qualified_for_structural_rule"]
        )
        assert receipt["all_controller_physical_budget"] == sum(
            r["remaining_mass"]
            for r in assessment["hidden_stem_ledger"]
            if r["element"] == receipt["controller_element"]
        )
        assert receipt["retention_policy_reused"] == 0.75
    protocol = read("protocol.json")
    for name, item in protocol["numerical_dependencies"].items():
        assert digest(FIXTURE / item["archive"]) == item["sha256"]


def test_complete_source_cohort_has_no_selected_success_subset():
    reference, result = read("reference.json"), frozen_report(PROSPECTIVE)
    assert [r["id"] for r in result["rows"]] == [r["id"] for r in reference["cases"]]
    assert [r["unit"] for r in reference["cases"]] == ["君象"] * 2 + ["臣象"] * 4 + [
        "母象"
    ] * 2 + ["子象"] * 2
    summary = result["source_summary"]
    assert (
        summary["records"],
        summary["distinct_inputs"],
        summary["exact_labeled_records"],
        summary["unknown_records"],
    ) == (10, 10, 7, 3)
    assert (summary["nonoverlap_records"], summary["nonoverlap_labeled_records"]) == (
        10,
        7,
    )
    assert summary["matching_records"] == {
        "production_v6": 6,
        "capacity_v3": 7,
        "hidden_seal_v5": 7,
        "qualified_roots_v1": 6,
        "root_load_v2": 6,
    }
    assert not summary["specific_nonoverlap_improvements"]
    assert not result["gates"]["at_least_one_specific_nonoverlap_improvement"]
    assert not result["gates"]["independent_source_force_grade_equivalence_review"]
    assert not result["adopted"] and not result["production_default_changed"]


def test_source_roles_and_unknowns_are_not_replaced_by_strength_or_duty_guesses():
    reference = read("reference.json")
    assert "日主为臣" in reference["role_map"]["臣象"]
    assert "日主为母" in reference["role_map"]["母象"]
    assert "生日者为母" in reference["role_map"]["子象"]
    unknown = [r for r in reference["cases"] if r["expected_strength"] is None]
    assert [r["id"] for r in unknown] == [
        "DTCW1947-CX-02",
        "DTCW1947-MX-02",
        "DTCW1947-ZX-02",
    ]
    for row in frozen_report(PROSPECTIVE)["rows"]:
        assert row["duty_day_after_term"] is None
        if row["expected_strength"] is None:
            assert all(v is None for v in row["matches"].values())


def test_new_failure_extends_corpus_without_erasing_original_nineteen():
    result = frozen_report(CORPUS)
    assert (
        len(result["groups"]),
        result["record_count"],
        result["input_index"]["distinct_four_pillar_inputs"],
    ) == (24, 314, 268)
    assert len(result["all_distinct_disagreements"]) == 25
    assert len(result["original_nineteen"]) == 19
    assert all(r["matches"] is False for r in result["original_nineteen"])
    old = frozen_report(ROOT / "docs/validation/bazi-source-corpus-first-v3.json.gz")
    for name, group in old["groups"].items():
        assert result["groups"][name] == group
    row = next(
        r for r in frozen_report(PROSPECTIVE)["rows"] if r["id"] == "DTCW1947-CX-04"
    )
    assert row["expected_strength"] == "强" and row["grades"]["production_v6"] == "弱"
    assert row["candidate_receipts"]["root_load_v2"]["qualified_body_positions"] == [
        "hour"
    ]
    assert not result["source_drift"] and result["new_independent_cases"] == 0


def test_all_original_nineteen_have_individual_body_seal_and_predicate_receipts():
    result = frozen_report(
        ROOT / "docs/validation/bazi-nineteen-root-load-first-v2.json.gz"
    )
    assert (
        result["records"],
        result["production_unresolved"],
        result["isolated_candidate_matching_records"],
    ) == (19, 19, 6)
    original = json.loads(
        (ROOT / "tests/fixtures/bazi_disagreement_review_v1/review.json").read_text()
    )
    for row, source in zip(result["rows"], original["cases"], strict=True):
        assert (row["id"], row["pillars"], row["expected_strength"]) == (
            source["id"],
            source["pillars"],
            source["expected_strength"],
        )
        assert not row["production_matches"]
        assert row["production_issue_status"] == "unresolved"
        assert row["body_seal_unrounded_components"][
            "reconciles_supplied_support_and_weaken"
        ]
        assert (
            row["body_seal_unrounded_components"]["quantity_kind"]
            == "engineering_energy_not_classical_force_or_probability"
        )
        assert row["effective_passage_adjudicated"] is None
        assert row["source_duty_stem_adjudicated"] is None
        assert row["source_month_day_after_term"] == (
            6 if row["id"] == "ML-02" else None
        )
    assert not result["candidate_adopted"]


def test_first_execution_failure_and_exact_successful_replay_are_retained(tmp_path):
    repair = read("test-repair.json")
    for name, expected in repair["sha256"].items():
        assert digest(FIXTURE / name) == expected
    assert "1 failed, 22 passed" in (FIXTURE / "pytest-first.log").read_text()
    pre = read("pre-prospective-r2.json")
    for name, expected in pre["preserved_first_launch"].items():
        assert digest(FIXTURE / name) == expected
    assert (
        "AttributeError: module 'importlib' has no attribute 'machinery'"
        in (FIXTURE / "prospective-first-import-failure.log").read_text()
    )
    output = tmp_path / "replay.json.gz"
    process = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    repeated, first = frozen_report(output), frozen_report(PROSPECTIVE)
    assert {k: v for k, v in repeated.items() if k != "recorded_at_utc"} == {
        k: v for k, v in first.items() if k != "recorded_at_utc"
    }


def test_first_result_cannot_be_overwritten_and_real_world_remains_unverified():
    original = PROSPECTIVE.read_bytes()
    process = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(PROSPECTIVE)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert process.returncode != 0 and "preserve first result" in process.stderr
    assert PROSPECTIVE.read_bytes() == original
    for result in [frozen_report(DEVELOPMENT), frozen_report(PROSPECTIVE)]:
        assert result["real_world_predictive_validity"] == "not_tested"
        assert not result["full_goal_complete"] and result["overall_score"] is None
