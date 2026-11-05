"""Hand-derived score ratios must survive floating-point loss underflow."""

import json
import math
from decimal import Decimal, localcontext

import pytest

from fatebridge.validation.predictions import evaluate_study
from tests.evaluation.test_prediction_validation import AS_OF, forecast, outcome, plan


def evaluate(baseline, probability):
    return evaluate_study(
        plan(baseline_probability=baseline),
        [forecast(i, probability) for i in range(2)],
        [outcome(i, False) for i in range(2)],
        as_of=AS_OF,
    )


@pytest.mark.parametrize(
    "baseline,probability,expected",
    [(1e-200, 0.0, 1.0), (1e-200, 5e-201, 0.75), (1e-160, 5e-161, 0.75)],
)
def test_squared_loss_underflow_does_not_erase_an_identifiable_skill_ratio(
    baseline, probability, expected
):
    result = evaluate(baseline, probability)
    with localcontext() as context:
        context.prec = 80
        b, p = Decimal.from_float(baseline), Decimal.from_float(probability)
        oracle = float(1 - p * p / (b * b))
    assert oracle == expected
    assert result["metrics"]["brier_skill_score"] == pytest.approx(
        oracle, rel=0, abs=1e-14
    )
    assert result["metrics"]["brier_skill_score_status"] == "defined_with_scaled_losses"
    assert not result["statistical_evidence_gate_met"]
    assert not result["authority_certified"]
    assert result["real_world_efficacy"] == "not_established_by_synthetic_data"
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("baseline", [1e-160, 1e-200])
def test_unrepresentably_bad_skill_is_explicit_and_never_passes_a_gate(baseline):
    result = evaluate(baseline, 1.0)
    metric = result["metrics"]
    assert metric["brier_skill_score"] is None
    assert metric["brier_skill_score_status"] == "negative_overflow"
    assert metric["brier_score"] == 1.0
    assert not result["registered_numeric_gate_met"]
    assert not result["preregistered_performance_gate_met"]
    assert not result["statistical_evidence_gate_met"]
    json.dumps(result, allow_nan=False)


def test_zero_baseline_error_and_positive_underflow_remain_distinct():
    zero = evaluate(0.0, 0.0)["metrics"]
    tiny = evaluate(1e-200, 0.0)["metrics"]
    assert zero["brier_skill_score_status"] == "undefined_zero_baseline_loss"
    assert zero["baseline_brier_score_status"] == "finite"
    assert tiny["baseline_brier_score_status"] == "positive_loss_underflow"
    assert tiny["brier_score_status"] == "finite"
    assert (
        evaluate(1e-200, 5e-201)["metrics"]["brier_score_status"]
        == "positive_loss_underflow"
    )


def test_ordinary_brier_ratio_keeps_its_existing_arithmetic_and_fixed_thresholds():
    result = evaluate(0.5, 0.8)
    assert result["metrics"]["brier_skill_score"] == 1 - (0.8**2) / (0.5**2)
    assert result["metrics"]["brier_skill_score_status"] == "defined"
    assert math.isfinite(
        result["statistical_evidence"]["lower_bound_excess_over_registered_threshold"]
    )
    assert result["statistical_evidence"]["registered_minimum_brier_skill"] == 0
