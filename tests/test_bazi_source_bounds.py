"""Bounded source evidence must not erase unknowns or alter calculated grades."""

from copy import deepcopy

import pytest

from fatebridge.core.source_annotations import (
    annotation_comparison_summary,
    compare_records,
)


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
