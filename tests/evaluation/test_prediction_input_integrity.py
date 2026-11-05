"""Scoring must not trust mutable records that bypass their declared schema.

Every person, event and probability here is synthetic, including the deliberately
invalid nonbinary attack. No result is a real-world forecasting observation.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from fatebridge.validation.predictions import (
    Forecast,
    Outcome,
    StudyPlan,
    digest,
    evaluate_study,
)

AS_OF = datetime(2028, 2, 1, tzinfo=timezone.utc)


def study(n=100):
    plan = StudyPlan(
        study_id="synthetic-admission-only",
        data_kind="synthetic",
        preregistered_at="2026-01-01T00:00:00Z",
        registration_reference="synthetic:not-actually-registered",
        window_start="2027-01-01T00:00:00Z",
        window_end="2028-01-01T00:00:00Z",
        target_definition="Synthetic binary event",
        model_sha256="a" * 64,
        interpretation_policy_sha256="b" * 64,
        baseline_frozen_at="2025-12-31T00:00:00Z",
        training_subject_ids=[],
        baseline_probability=0.5,
        minimum_evaluable=100,
        cohort=[{"case_id": str(i), "subject_id": f"fictional-{i}"} for i in range(n)],
    )
    forecasts = [
        Forecast(
            case_id=str(i),
            study_plan_sha256=digest(plan.model_dump(mode="json")),
            issued_at="2026-12-01T00:00:00Z",
            model_sha256="a" * 64,
            interpretation_policy_sha256="b" * 64,
            evidence_sha256="c" * 64,
            probability=1.0,
        )
        for i in range(n)
    ]
    outcomes = [
        Outcome(
            case_id=str(i),
            study_plan_sha256=digest(plan.model_dump(mode="json")),
            occurred=True,
            event_at="2027-06-01T00:00:00Z",
            recorded_at="2028-01-02T00:00:00Z",
            source_sha256="d" * 64,
            source_reference="synthetic fixture",
        )
        for i in range(n)
    ]
    return plan, forecasts, outcomes


def corrupt(record, field, value, mode):
    if mode == "copy":
        return record.model_copy(update={field: value})
    if mode == "construct":
        return type(record).model_construct(**{**record.__dict__, field: value})
    setattr(record, field, value)
    return record


@pytest.mark.parametrize("mode", ["copy", "construct", "assign"])
@pytest.mark.parametrize(
    "target,field,value",
    [
        ("forecast", "probability", True),
        ("forecast", "probability", 2.0),
        ("outcome", "occurred", 2),
        ("outcome", "occurred", 1),
        ("plan", "baseline_probability", True),
        ("plan", "minimum_evaluable", True),
    ],
)
def test_invalid_mutable_models_are_rejected_before_any_scoring(
    mode, target, field, value
):
    plan, forecasts, outcomes = study()
    if target == "plan":
        plan = corrupt(plan, field, value, mode)
    elif target == "forecast":
        forecasts[0] = corrupt(forecasts[0], field, value, mode)
    else:
        outcomes[0] = corrupt(outcomes[0], field, value, mode)
    with pytest.raises(ValidationError):
        evaluate_study(plan, forecasts, outcomes, as_of=AS_OF)


def test_nonbinary_attack_cannot_enter_the_bounded_binary_loss_gate():
    plan, forecasts, outcomes = study()
    outcomes = [o.model_copy(update={"occurred": 2}) for o in outcomes]
    with pytest.raises(ValidationError):
        evaluate_study(plan, forecasts, outcomes, as_of=AS_OF)


def test_valid_copies_retain_the_same_full_report_without_weakening_the_gate():
    plan, forecasts, outcomes = study()
    expected = evaluate_study(plan, forecasts, outcomes, as_of=AS_OF)
    actual = evaluate_study(
        plan.model_copy(deep=True),
        [f.model_copy(deep=True) for f in forecasts],
        [o.model_copy(deep=True) for o in outcomes],
        as_of=AS_OF,
    )
    assert actual == expected
    assert actual["metrics"]["brier_score"] == 0.0
    assert actual["metrics"]["baseline_brier_score"] == 0.25
    assert actual["statistical_evidence_gate_met"] is True
    assert actual["authority_certified"] is False
    assert actual["real_world_efficacy"] == "not_established_by_synthetic_data"
