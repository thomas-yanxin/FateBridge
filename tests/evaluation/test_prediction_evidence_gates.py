"""Predeclared paired-loss bounds cannot be replaced by perfect toy accuracy."""

import math

import pytest

from fatebridge.validation.predictions import evaluate_study
from tests.evaluation.test_prediction_validation import AS_OF, forecast, outcome, plan


def perfect_study(n, **changes):
    registered = plan(n, **{"minimum_evaluable": 2, **changes})
    forecasts = [forecast(i, 1.0, registered=registered) for i in range(n)]
    outcomes = [outcome(i, True, registered=registered) for i in range(n)]
    return evaluate_study(registered, forecasts, outcomes, as_of=AS_OF)


def test_perfect_small_sample_keeps_point_gate_separate_from_statistical_evidence():
    result = perfect_study(10)
    assert result["preregistered_performance_gate_met"] is True
    assert result["statistical_evidence_gate_met"] is False
    evidence = result["statistical_evidence"]
    assert evidence["mean_paired_brier_improvement"] == 0.25
    assert evidence["lower_bound_excess_over_registered_threshold"] == pytest.approx(
        0.25 - math.sqrt(2 * math.log(20) / 10)
    )
    assert result["real_world_efficacy"] == "not_established_by_synthetic_data"
    assert result["authority_certified"] is False


def test_registered_multiple_looks_do_not_get_the_single_look_threshold():
    single = perfect_study(100)
    repeated = perfect_study(100, planned_evaluations=2)
    assert single["statistical_evidence_gate_met"] is True
    assert repeated["statistical_evidence_gate_met"] is False
    assert repeated["statistical_evidence"]["per_evaluation_alpha"] == pytest.approx(
        0.025
    )
    assert (
        repeated["statistical_evidence"]["lower_bound_excess_over_registered_threshold"]
        < single["statistical_evidence"]["lower_bound_excess_over_registered_threshold"]
    )


def test_bound_tests_the_registered_skill_threshold_not_merely_positive_gain():
    result = perfect_study(100, minimum_brier_skill=0.2)
    evidence = result["statistical_evidence"]
    assert evidence["mean_excess_over_registered_threshold"] == 0.2
    assert evidence["lower_bound_excess_over_registered_threshold"] == pytest.approx(
        0.2 - 1.8 * math.sqrt(math.log(20) / 200)
    )
    assert not result["statistical_evidence_gate_met"]


def test_confident_bound_does_not_bypass_coverage_or_registered_sample_size():
    p = plan(101, minimum_evaluable=100)
    result = evaluate_study(
        p,
        [forecast(i, 1.0) for i in range(100)],
        [outcome(i, True) for i in range(100)],
        as_of=AS_OF,
    )
    assert (
        result["statistical_evidence"]["lower_bound_excess_over_registered_threshold"]
        > 0
    )
    assert result["coverage"] < 1
    assert not result["statistical_evidence_gate_met"]
    small = perfect_study(100, minimum_evaluable=200)
    assert not small["statistical_evidence_gate_met"]


def test_no_records_never_produce_a_positive_evidence_bound():
    result = evaluate_study(plan(), [], [], as_of=AS_OF)
    assert result["statistical_evidence"]["mean_paired_brier_improvement"] is None
    assert (
        result["statistical_evidence"]["lower_bound_excess_over_registered_threshold"]
        is None
    )
    assert not result["statistical_evidence_gate_met"]
    assert result["real_world_efficacy"] == "not_tested"


@pytest.mark.parametrize(
    "field,blocker",
    [
        ("registration_reference", "missing_external_registration_reference"),
        ("interpretation_policy_sha256", "missing_interpretation_policy_commitment"),
        ("baseline_frozen_at", "missing_baseline_freeze_time"),
        ("training_subject_ids", "missing_training_subject_declaration"),
    ],
)
def test_positive_bound_cannot_bypass_incomplete_preregistration(field, blocker):
    registered = plan(100, **{field: None})
    forecasts = [forecast(i, 1.0) for i in range(100)]
    if field == "interpretation_policy_sha256":
        forecasts = [
            f.model_copy(update={"interpretation_policy_sha256": None})
            for f in forecasts
        ]
    result = evaluate_study(
        registered,
        forecasts,
        [outcome(i, True) for i in range(100)],
        as_of=AS_OF,
    )
    assert result["registered_numeric_gate_met"]
    assert (
        result["statistical_evidence"]["lower_bound_excess_over_registered_threshold"]
        > 0
    )
    assert blocker in result["protocol_blockers"]
    assert result["protocol_status"] == "incomplete"
    assert not result["preregistered_performance_gate_met"]
    assert not result["statistical_evidence_gate_met"]


def test_baseline_and_interpretation_policy_cannot_be_changed_after_commitment():
    with pytest.raises(ValueError, match="基线"):
        plan(baseline_frozen_at="2026-10-23T00:00:00Z")
    changed = forecast(0, 0.8).model_copy(
        update={"interpretation_policy_sha256": "e" * 64}
    )
    with pytest.raises(ValueError, match="解释政策"):
        evaluate_study(plan(), [changed], [], as_of=AS_OF)
