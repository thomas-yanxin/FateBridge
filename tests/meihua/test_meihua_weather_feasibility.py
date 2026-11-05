"""A complete forecast vector cannot get a perfect score through abstention."""

import hashlib
import json
from itertools import product
from pathlib import Path

import pytest

from fatebridge.validation.meihua_weather_feasibility import (
    attainable_binary_skill_bound,
    audit_feasibility_vector,
)

REFERENCE = Path(__file__).parents[1] / "fixtures/meihua_weather_feasibility_v1"


def bound(labels):
    cases = [str(i) for i in range(len(labels))]
    return attainable_binary_skill_bound(cases, dict(zip(cases, labels)))


def test_preimplementation_enumeration_and_locked_primary_vector_are_preserved():
    manifest = json.loads((REFERENCE / "manifest.json").read_text())
    assert manifest["implementation_absent"]
    assert not manifest["expected_values_generated_by_production"]
    for name, digest in manifest["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == digest
    rows = json.loads((REFERENCE / "brute-force-cases.json").read_text())["cases"]
    assert len(rows) == 119
    for case in rows:
        actual = bound(case["labels"])
        assert (
            actual["exact_maximum_margin_over_better_constant"]
            == case["maximum_margin_by_outcome_enumeration"]
        )


def test_all3279_small_forecast_vectors_against335922_outcome_assignments():
    forecasts = outcomes = 0
    for n in range(1, 8):
        for labels in product(["rain", "dry", "abstain"], repeat=n):
            maximum = -n
            for truth in product(["rain", "dry"], repeat=n):
                score = sum(p == y for p, y in zip(labels, truth))
                baseline = max(truth.count("rain"), truth.count("dry"))
                maximum = max(maximum, score - baseline)
                outcomes += 1
            result = bound(labels)
            assert result["exact_maximum_margin_over_better_constant"] == maximum
            assert result["passing_is_possible_for_some_complete_binary_outcomes"] == (
                maximum > 0
            )
            forecasts += 1
    assert (forecasts, outcomes) == (3279, 335922)


def test_existing_primary_cannot_pass_even_if_all49_categorical_forecasts_are_right():
    saved = json.loads((REFERENCE / "primary273-vector.json").read_text())
    result = attainable_binary_skill_bound(
        saved["cohort_case_ids"], saved["forecast_labels"]
    )
    assert result["forecast_counts"] == {"rain": 0, "dry": 49, "abstain": 224}
    assert result["maximum_possible_correct_credit"] == 49
    assert result["better_constant_credit_lower_bound"] == 137
    assert result["exact_maximum_margin_over_better_constant"] == -88
    assert result["constant_baselines_weakly_dominating_on_every_outcome_vector"] == [
        "always_dry"
    ]
    assert not result["predictive_efficacy_established"]
    assert result["observed_accuracy"] is None
    assert not result["observed_outcomes_used"]


def test_coverage_alone_does_not_make_one_class_forecasts_competitive():
    result = bound(["rain"] * 365)
    assert result["maximum_possible_correct_credit"] == 365
    assert result["exact_maximum_margin_over_better_constant"] == 0
    assert not result["passing_is_possible_for_some_complete_binary_outcomes"]
    assert result["constant_baselines_weakly_dominating_on_every_outcome_vector"] == [
        "always_rain"
    ]


def test_two_classes_and_high_coverage_are_possibility_not_a_probability():
    result = bound(["rain", "dry"])
    assert result["exact_maximum_margin_over_better_constant"] == 1
    assert result["passing_is_possible_for_some_complete_binary_outcomes"]
    assert not result["predictive_efficacy_established"]
    assert result["supplied_cohort_seal_authenticated"] is False


def test_verified_vector_integrity_does_not_turn_impossible_score_into_a_pass():
    manifest = json.loads((REFERENCE / "manifest.json").read_text())
    report = audit_feasibility_vector(
        REFERENCE / "primary273-vector.json",
        expected_sha256=manifest["files"]["primary273-vector.json"],
    )
    assert report["file_commitment_verified"]
    assert not report["study_plan_or_timestamp_authenticated"]
    bound = report["attainable_skill_bound"]
    assert bound["cannot_strictly_beat_better_constant_for_any_complete_outcome_vector"]


def test_vector_tampering_is_rejected_before_any_feasibility_calculation(tmp_path):
    p = tmp_path / "vector.json"
    p.write_bytes((REFERENCE / "primary273-vector.json").read_bytes())
    expected = hashlib.sha256(p.read_bytes()).hexdigest()
    p.write_bytes(p.read_bytes() + b" ")
    with pytest.raises(ValueError, match="differs from its commitment"):
        audit_feasibility_vector(p, expected_sha256=expected)


def test_duplicate_json_keys_cannot_silently_replace_an_unfavorable_label(tmp_path):
    p = tmp_path / "vector.json"
    p.write_text(
        '{"cohort_case_ids":["a","b"],'
        '"forecast_labels":{"a":"abstain","a":"rain","b":"dry"}}'
    )
    with pytest.raises(ValueError, match="Duplicate JSON keys"):
        audit_feasibility_vector(
            p, expected_sha256=hashlib.sha256(p.read_bytes()).hexdigest()
        )


@pytest.mark.parametrize("commitment", [None, True, "A" * 64, "0" * 63])
def test_invalid_commitment_cannot_be_treated_as_a_verified_input(commitment):
    with pytest.raises(ValueError, match="recorded lowercase SHA-256"):
        audit_feasibility_vector(
            REFERENCE / "primary273-vector.json", expected_sha256=commitment
        )


@pytest.mark.parametrize(
    "cases,labels",
    [
        ([], {}),
        ("abc", {"a": "rain", "b": "dry", "c": "abstain"}),
        (["a", "a"], {"a": "rain"}),
        (["a", "b"], {"a": "rain"}),
        (["a"], {"a": "rain", "b": "abstain"}),
        ([""], {"": "rain"}),
        ([1], {1: "rain"}),
        (["a"], {"a": None}),
        (["a"], {"a": True}),
        (["a"], {"a": "unknown"}),
        (["a"], ["rain"]),
    ],
)
def test_incomplete_duplicate_or_unknown_inputs_do_not_get_a_feasibility_claim(
    cases, labels
):
    with pytest.raises(ValueError):
        attainable_binary_skill_bound(cases, labels)
