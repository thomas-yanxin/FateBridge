"""Current exact budgets and source claims, independent of old software outputs.

The Fraction reference checks arithmetic conditional on supplied relations.
Source disagreements, unknown grades and unadjudicated force remain evidence.
"""

import json
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from itertools import product
from pathlib import Path

import pytest

from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_source_annotations import SourceAnnotationComparison
from fatebridge.core.strength import DEFAULT_POLICY, evaluate_strength_policy
from fatebridge.services.source_comparison import calculate_bazi_source_compare
from scripts.audit_bazi_source_corpus import (
    audit,
    compare_application,
    compare_direction,
)
from tests.bazi_geometry_reference import ORDER, geometries, identifier
from tests.bazi_punishment_reference import GEOMETRIES, remaining_masses
from tests.bazi_strength_reference_v3 import assert_current_assessment_arithmetic

DATA = Path(__file__).parent / "data/bazi"
SOURCE = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "src/fatebridge/data/reference/bazi-source-annotations.json"
    ).read_text()
)


@pytest.mark.parametrize(
    "row",
    json.loads((DATA / "arithmetic-inputs.json").read_text()),
    ids=lambda r: r["group"] + ":" + r["id"],
)
def test_every_current_raw_budget_matches_literal_fraction_ledger(row):
    values = row["pillars"]
    chart = dict(zip(ORDER, map(tuple, values)))
    assessment = ElementAnalysis.analyze_day_master_strength(chart)["assessment"]
    assert_current_assessment_arithmetic(values, assessment)
    assert evaluate_strength_policy(
        chart, ElementAnalysis.seasonal_phases(chart["month"][1]), DEFAULT_POLICY
    ) == evaluate_strength_policy(
        dict(reversed(list(chart.items()))),
        ElementAnalysis.seasonal_phases(chart["month"][1]),
        DEFAULT_POLICY,
    )


@pytest.mark.parametrize("row", SOURCE["records"], ids=lambda r: r["reference_id"])
def test_every_registered_source_preserves_literal_input_and_unknown_grade(row):
    values = row["pillars"]
    result = calculate_bazi_source_compare(*values)
    assert "error" not in result
    actual = next(
        r
        for r in result["source_comparison"]["records"]
        if r["reference_id"] == row["reference_id"]
    )
    assert actual["pillars"] == values
    assert actual["retained_strength_annotation"] == row["retained_strength_annotation"]
    assert actual["source_reference"] == row["source_reference"]
    if row["retained_strength_annotation"] is None:
        assert actual["comparison"] == "unadjudicated"
    comparison = result["source_comparison"]
    assert comparison["new_independent_validation_credit"] == 0
    assert result["current_calculation"]["calculation_overridden"] is False
    assert_current_assessment_arithmetic(
        values, result["current_calculation"]["assessment"]
    )
    SourceAnnotationComparison.model_validate(comparison)


def test_source_labels_conflicts_bounds_and_unknowns_remain_separate_from_model():
    report = audit()
    assert report["record_count"] == 367 and report["distinct_inputs"] == 321
    assert report["unknown_strength_records"] == 244
    # Repairs may reduce disagreements. Check the complete original population
    # and literal grades instead of requiring the old number of wrong answers.
    labels = {
        row["reference_id"]: row["retained_strength_annotation"]
        for row in SOURCE["records"]
    }
    assert {row["group"] + ":" + row["id"] for row in report["rows"]} == set(labels)
    expected_disagreements = set()
    for row in report["rows"]:
        label = labels[row["group"] + ":" + row["id"]]
        assert row["expected_strength"] == label
        if label is not None and row["actual_strength"] != label:
            expected_disagreements.add(tuple(row["pillars"]))
    assert {
        tuple(row["pillars"]) for row in report["all_distinct_disagreements"]
    } == expected_disagreements
    claims = report["local_and_negative_claims"]
    assert len(claims) == 19
    assert (
        sum(r["matches"] is False for r in claims if r["kind"] == "local_clash_labels")
        == 4
    )
    assert (
        sum(r["matches"] is False for r in claims if r["kind"] == "body_constraints")
        == 2
    )
    assert report["classical_acceptance_passed"] is False
    assert report["overall_score"] is None
    assert report["reality_prediction_efficacy"] == "not_tested"


def test_source_lookups_and_editorial_annotation_are_read_only(monkeypatch):
    from fatebridge.core import source_annotations

    values = SOURCE["records"][0]["pillars"]
    before = calculate_bazi_source_compare(*values)
    current = deepcopy(before["current_calculation"])
    records, metadata = source_annotations._index()
    baseline = deepcopy(records)
    with monkeypatch.context() as local:
        stripped = deepcopy(records)
        for rows in stripped.values():
            for record in rows:
                record.pop("annotation_basis", None)
                record.pop("editorial_annotation_provenance", None)
        local.setattr(source_annotations, "_index", lambda: (stripped, metadata))
        after = calculate_bazi_source_compare(*values)
        assert after["current_calculation"] == current
    assert records == baseline
    first = source_annotations.compare_registered_annotations(
        dict(zip(ORDER, map(tuple, values))),
        before["current_calculation"]["strength_level"],
    )["records"]
    first[0]["pillars"][0] = "甲子"
    assert calculate_bazi_source_compare(*values) == before


@pytest.mark.parametrize("branches", GEOMETRIES)
@pytest.mark.parametrize("coefficient", [Fraction(9, 10), Fraction(4, 5)])
def test_contested_combinations_cannot_resolve_punishment_or_reuse_roots(
    branches, coefficient
):
    chart = dict(zip(ORDER, (("甲", b) for b in branches)))
    result = evaluate_strength_policy(
        chart,
        ElementAnalysis.seasonal_phases(chart["month"][1]),
        replace(DEFAULT_POLICY, punishment=float(coefficient)),
    )
    assert (
        next(e for e in result["relations"] if e["kind"] == "刑")["status"] == "active"
    )
    masses = remaining_masses(branches, coefficient)
    for row in result["hidden_stem_ledger"]:
        assert row["remaining_mass"] == pytest.approx(
            float(masses[row["pillar"], row["stem"]]), rel=0, abs=1e-12
        )


def test_all_branch_geometry_uses_literal_candidate_enumeration():
    from fatebridge.core.branch_candidates import build_branch_combination_candidates

    for branches in product("子丑寅卯辰巳午未申酉戌亥", repeat=4):
        chart = dict(zip(ORDER, (("甲", branch) for branch in branches)))
        result = build_branch_combination_candidates(chart, {})
        assert [r["id"] for r in result["candidates"]] == [
            identifier(kind, target, seats)
            for kind, target, seats in geometries(branches)
        ]
        assert result["effects_status"] == "not_supplied"


def test_missing_events_and_tied_clash_are_not_certified_source_matches():
    annotation = {"positions": ["year", "month"], "weaker_position": "year"}
    assert compare_direction({"relations": []}, annotation)["matches"] is None
    tied = {
        "kind": "六冲",
        "positions": ["year", "month"],
        "status": "active",
        "root_multipliers": {"year": 0.75, "month": 0.75},
    }
    assert compare_direction({"relations": [tied]}, annotation)["matches"] is False
    assert (
        compare_application(
            {"relations": []}, {**annotation, "expected_clash_effect": "applied"}
        )["matches"]
        is None
    )
