"""Bounded source evidence must not erase unknowns or alter calculated grades."""

import gzip
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.source_annotations import (
    annotation_comparison_summary,
    compare_records,
)
from fatebridge.services.source_comparison import calculate_bazi_source_compare
from fatebridge.validation.bazi_source_corpus import load_registry
from tests.bazi_refactor_reference import assert_assessment_matches_before_repair

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-source-bounds-v1"


def row(forbidden, exact=None):
    return {
        "retained_strength_annotation": exact,
        "bounded_strength_constraints": [{"forbidden_strengths": forbidden}],
    }


@pytest.mark.parametrize(
    "grade,status",
    [
        ("弱", "violates_registered_bounds"),
        ("中和", "satisfies_registered_bounds"),
        ("强", "satisfies_registered_bounds"),
        (None, "current_grade_missing"),
    ],
)
def test_unknown_exact_annotation_remains_unknown_with_any_bounded_outcome(
    grade, status
):
    records = [row(["弱"])]
    before = deepcopy(records)
    result = compare_records(records, grade)
    bounds = result["bounded_comparison"]
    assert records == before
    assert result["status"] == "unadjudicated_records_only"
    assert result["known_annotation_count"] == 0
    assert result["unknown_or_unannotated_count"] == 1
    assert result["agreeing_known_count"] == 0
    assert bounds["status"] == status
    assert bounds["remaining_strengths_under_all_bounds"] == ["中和", "强"]
    assert bounds["exact_strength_label_assigned"] is False
    assert result["calculation_overridden"] is False
    assert bounds["new_independent_validation_credit"] == 0
    if grade == "弱":
        assert "集合约束被当前计算违反" in annotation_comparison_summary(result)


def test_contradictory_bounds_and_exact_labels_are_all_preserved():
    result = compare_records([row(["弱"], "弱"), row(["强", "中和"])], "弱")
    bounds = result["bounded_comparison"]
    assert result["status"] == "agrees_with_known_annotations"
    assert bounds["status"] == "contradictory_registered_bounds"
    assert bounds["conflicts_with_retained_exact_annotations"] is True
    assert bounds["claim_count"] == 2
    assert bounds["violated_count"] == bounds["satisfied_count"] == 1
    assert bounds["remaining_strengths_under_all_bounds"] == []
    assert "彼此冲突" in annotation_comparison_summary(result)


@pytest.mark.parametrize("forbidden", [[], ["旺"], [None], "弱", [3]])
def test_malformed_bounds_cannot_be_dropped_or_converted_to_unknown(forbidden):
    with pytest.raises(ValueError, match="集合约束"):
        compare_records([row(forbidden)], "弱")


def test_registry_and_index_append_all_six_cases_without_rewriting_old_records():
    old = load_registry(
        ROOT,
        ROOT / "tests/fixtures/bazi_source_corpus_v7/registry.json",
        current_coverage=False,
    )
    new = load_registry(
        ROOT, ROOT / "tests/fixtures/bazi_source_corpus_v8/registry.json"
    )
    for name in ("groups", "source_sha256", "auxiliary_sha256"):
        assert new[name].items() >= old[name].items()
    package = ROOT / "src/fatebridge/data/reference"
    parent = json.loads((package / "bazi-source-annotations-v4.json").read_text())
    current = json.loads((package / "bazi-source-annotations-v5.json").read_text())
    assert current["records"][:361] == parent["records"]
    assert current["record_count"] == 367
    assert current["literal_input_count"] == 321
    assert (
        sum(r["retained_strength_annotation"] is not None for r in current["records"])
        == 123
    )
    assert (
        sum(r["retained_strength_annotation"] is None for r in current["records"])
        == 244
    )
    assert (
        current["strength_constraint_count"]
        == len(current["strength_constraints"])
        == 3
    )
    source = json.loads(
        (ROOT / "tests/fixtures/bazi_qingqi_zhuoqi_v1/reference.json").read_text()
    )
    frozen = json.loads(
        (
            ROOT / "docs/validation/bazi-controller-root-load-v1/reference.json"
        ).read_text()
    )
    assert source == frozen
    assert {r["case_id"] for r in current["records"][361:]} == {
        r["id"] for r in source["cases"]
    }


def test_entire_old_corpus_and_new_frozen_cases_keep_full_numerical_assessments():
    old = json.loads(
        gzip.decompress(
            (
                ROOT
                / "docs/validation/bazi-controller-root-load-v1/corpus-nested-constraints-first.json.gz"
            ).read_bytes()
        )
    )
    prospective = json.loads(
        gzip.decompress(
            (
                ROOT
                / "docs/validation/bazi-controller-root-load-v1/prospective-first.json.gz"
            ).read_bytes()
        )
    )
    count = 0
    for group in old["groups"].values():
        for case in group["rows"]:
            actual = calculate_bazi_source_compare(*case["pillars"])
            assert_assessment_matches_before_repair(
                case["pillars"], actual["current_calculation"]["assessment"]
            )
            count += 1
    # Prospective result shape is guarded by the existing complete-unit auditor.
    for case in prospective["rows"]:
        actual = calculate_bazi_source_compare(*case["source_case"]["pillars"])
        assert_assessment_matches_before_repair(
            case["source_case"]["pillars"], actual["current_calculation"]["assessment"]
        )
        count += 1
    assert count == 367
