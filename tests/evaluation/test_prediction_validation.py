"""Hand-computed metrics, leakage counterexamples, and same-run quotations."""

from copy import deepcopy
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from fatebridge.services.replay_metadata import digest
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from fatebridge.validation.predictions import (
    Forecast,
    Outcome,
    StudyPlan,
    evaluate_study,
)

MODEL = "a" * 64
AS_OF = datetime(2028, 2, 1, tzinfo=timezone.utc)


def plan(n=2, **changes):
    data = dict(
        study_id="synthetic-test",
        data_kind="synthetic",
        preregistered_at="2026-10-22T00:00:00Z",
        registration_reference="synthetic-test:registration-not-real-evidence",
        window_start="2027-01-01T00:00:00Z",
        window_end="2028-01-01T00:00:00Z",
        target_definition="Explicit test event in the registered window",
        model_sha256=MODEL,
        interpretation_policy_sha256="d" * 64,
        baseline_frozen_at="2026-10-20T00:00:00Z",
        training_subject_ids=[],
        baseline_probability=0.5,
        minimum_evaluable=2,
        cohort=[{"case_id": str(i), "subject_id": f"fictional-{i}"} for i in range(n)],
    )
    return StudyPlan.model_validate({**data, **changes})


def forecast(i, p, *, registered=None, **changes):
    data = dict(
        case_id=str(i),
        study_plan_sha256=(
            digest(registered.model_dump(mode="json")) if registered else None
        ),
        issued_at="2026-12-01T00:00:00Z",
        model_sha256=MODEL,
        interpretation_policy_sha256="d" * 64,
        evidence_sha256="b" * 64,
        probability=p,
    )
    return Forecast.model_validate({**data, **changes})


def outcome(i, occurred, *, registered=None, **changes):
    data = dict(
        case_id=str(i),
        study_plan_sha256=(
            digest(registered.model_dump(mode="json")) if registered else None
        ),
        occurred=occurred,
        event_at="2027-06-01T00:00:00Z" if occurred else None,
        recorded_at="2028-01-02T00:00:00Z",
        source_sha256="c" * 64,
        source_reference="synthetic fixture",
    )
    return Outcome.model_validate({**data, **changes})


def test_empty_study_cannot_report_perfect_performance_or_authority():
    r = evaluate_study(plan(), [], [], as_of=AS_OF)
    assert r["metrics"]["accuracy"] is None
    assert r["metrics"]["brier_score"] is None
    assert r["coverage"] == 0
    assert r["real_world_efficacy"] == "not_tested"
    assert not r["authority_certified"] and not r["preregistered_performance_gate_met"]


def test_metrics_match_hand_calculation_and_frozen_baseline():
    r = evaluate_study(
        plan(),
        [forecast(0, 0.9), forecast(1, 0.8)],
        [outcome(0, True), outcome(1, False)],
        as_of=AS_OF,
    )
    assert r["metrics"]["accuracy"] == 0.5
    assert r["metrics"]["brier_score"] == pytest.approx(0.325)
    assert r["metrics"]["baseline_brier_score"] == 0.25
    assert r["metrics"]["brier_skill_score"] == pytest.approx(-0.3)
    assert not r["preregistered_performance_gate_met"]


def test_perfect_small_sample_is_never_universal_perfect_prediction():
    p = plan(10)
    r = evaluate_study(
        p,
        [forecast(i, 1.0, registered=p) for i in range(10)],
        [outcome(i, True, registered=p) for i in range(10)],
        as_of=AS_OF,
    )
    assert r["metrics"]["accuracy"] == 1
    assert r["metrics"]["accuracy_interval"][0] == pytest.approx(0.7224672)
    assert r["preregistered_performance_gate_met"]
    assert not r["universal_perfect_prediction_established"]
    assert r["real_world_efficacy"] == "not_established_by_synthetic_data"


def test_near_one_confidence_does_not_round_quantile_to_infinity():
    r = evaluate_study(
        plan(confidence_level=0.9999999999999999),
        [forecast(0, 1.0), forecast(1, 0.0)],
        [outcome(0, True), outcome(1, False)],
        as_of=AS_OF,
    )
    lower, upper = r["metrics"]["accuracy_interval"]
    assert 0 < lower < 0.1
    assert 0.99 < upper <= 1


def test_missing_predictions_abstentions_and_outcomes_remain_in_coverage():
    p = plan(4)
    r = evaluate_study(
        p,
        [forecast(0, 1.0), forecast(1, None), forecast(2, 0.8)],
        [outcome(0, True), outcome(1, False)],
        as_of=AS_OF,
    )
    assert r["coverage"] == 0.25
    assert {row["status"] for row in r["rows"]} == {
        "evaluable",
        "abstained",
        "outcome_pending",
        "missing_forecast",
    }
    assert not r["preregistered_performance_gate_met"]


@pytest.mark.parametrize(
    "change",
    [
        {"issued_at": "2027-01-01T00:00:00Z"},
        {"issued_at": "2026-10-21T00:00:00Z"},
        {"model_sha256": "d" * 64},
        {"case_id": "not-in-cohort"},
    ],
)
def test_leaked_or_unregistered_forecasts_fail_loudly(change):
    f = forecast(0, 0.5).model_copy(
        update={
            k: (
                datetime.fromisoformat(v.replace("Z", "+00:00"))
                if k == "issued_at"
                else v
            )
            for k, v in change.items()
        }
    )
    with pytest.raises(ValueError):
        evaluate_study(plan(), [f], [], as_of=AS_OF)


def test_duplicate_predictions_and_correlated_subject_rows_are_rejected():
    with pytest.raises(ValueError, match="重复case_id"):
        evaluate_study(plan(), [forecast(0, 0.5), forecast(0, 0.9)], [], as_of=AS_OF)
    with pytest.raises(ValidationError, match="独立样本"):
        plan(
            cohort=[
                {"case_id": "a", "subject_id": "same"},
                {"case_id": "b", "subject_id": "same"},
            ]
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"event_at": "2028-01-01T00:00:00Z"},
        {"recorded_at": "2027-06-01T00:00:00Z"},
        {"event_at": None},
    ],
)
def test_outcome_window_and_complete_followup_are_required(changes):
    with pytest.raises(ValueError):
        evaluate_study(
            plan(), [forecast(0, 0.9)], [outcome(0, True, **changes)], as_of=AS_OF
        )


def test_future_recorded_outcome_cannot_leak_into_an_earlier_report():
    r = evaluate_study(
        plan(),
        [forecast(0, 0.9)],
        [outcome(0, True, recorded_at="2028-03-01T00:00:00Z")],
        as_of=AS_OF,
    )
    assert r["evaluable_count"] == 0
    assert r["rows"][0]["status"] == "outcome_pending"


@pytest.mark.parametrize(
    "probability", [float("nan"), float("inf"), -0.1, 1.1, "0.8", True]
)
def test_nonprobability_values_are_rejected(probability):
    with pytest.raises(ValidationError):
        forecast(0, probability)


def test_a_perfect_zero_variance_baseline_cannot_be_divided_by_zero():
    r = evaluate_study(
        plan(baseline_probability=0.0),
        [forecast(0, 0.0), forecast(1, 0.0)],
        [outcome(0, False), outcome(1, False)],
        as_of=AS_OF,
    )
    assert r["metrics"]["brier_skill_score"] is None
    assert not r["preregistered_performance_gate_met"]


def calculation():
    body = {
        "analysis_at": "2028-01-20T12:00:00+08:00",
        "dayun": {"pillar": "乙酉"},
        "relations": [{"transformation": "not_assessed"}],
        "score": None,
        "flag": True,
    }
    return {
        **body,
        "run_metadata": {
            "run_id": "original-run",
            "business_output_sha256": digest(body),
        },
    }


def claim(payload, path="dayun.pillar", value="乙酉", **changes):
    return CalculationClaim.model_validate(
        {
            "path": path,
            "value": value,
            "run_id": payload["run_metadata"]["run_id"],
            "business_output_sha256": payload["run_metadata"]["business_output_sha256"],
            **changes,
        }
    )


def test_same_run_exact_fact_is_verified_without_certifying_prose():
    p = calculation()
    report = verify_calculation_claims(
        p, [claim(p), claim(p, "relations.0.transformation", "not_assessed")]
    )
    assert report["status"] == "verified_structured_facts"
    assert "自由文本" in report["scope"]


@pytest.mark.parametrize(
    "path,value",
    [
        ("dayun.pillar", "甲申"),
        ("score", 0),
        ("flag", 1),
        ("future.success_probability", 1.0),
        ("relations.0.transformation", "complete"),
    ],
)
def test_false_values_types_and_uncalculated_predictions_are_rejected(path, value):
    p = calculation()
    assert verify_calculation_claims(p, [claim(p, path, value)])["status"] == "rejected"


def test_edited_projected_and_different_run_payloads_fail_closed():
    p = calculation()
    c = claim(p)
    for changed in (
        {"run_metadata": p["run_metadata"], "dayun": p["dayun"]},
        {**deepcopy(p), "score": 100},
    ):
        assert verify_calculation_claims(changed, [c])["status"] == "rejected"
    assert (
        verify_calculation_claims(p, [claim(p, run_id="other-run")])["status"]
        == "rejected"
    )
    assert verify_calculation_claims(p, [])["status"] == "rejected"
