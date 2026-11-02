"""Adversarial same-ZoneInfo wall labels must never admit future outcomes."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from fatebridge.validation.predictions import (
    Forecast,
    Outcome,
    StudyPlan,
    evaluate_study,
)

ZONE = ZoneInfo("America/New_York")


def at(minute, fold):
    return datetime(2026, 11, 1, 1, minute, tzinfo=ZONE, fold=fold)


def plan(**changes):
    return StudyPlan.model_validate(
        {
            "study_id": "synthetic-fold-order",
            "data_kind": "synthetic",
            "preregistered_at": "2026-10-31T00:00:00Z",
            "registration_reference": "synthetic clock regression, not real registration",
            "window_start": datetime(2026, 11, 1, 0, tzinfo=ZONE),
            "window_end": at(15, 1),
            "target_definition": "Synthetic binary clock test",
            "model_sha256": "a" * 64,
            "interpretation_policy_sha256": "b" * 64,
            "baseline_frozen_at": "2026-10-31T00:00:00Z",
            "baseline_probability": 0.5,
            "minimum_evaluable": 1,
            "training_subject_ids": [],
            "cohort": [{"case_id": "a", "subject_id": "synthetic-a"}],
            **changes,
        }
    )


def forecast(issued_at="2026-10-31T01:00:00Z"):
    return Forecast(
        case_id="a",
        issued_at=issued_at,
        model_sha256="a" * 64,
        interpretation_policy_sha256="b" * 64,
        evidence_sha256="c" * 64,
        probability=0.1,
    )


def outcome(recorded_at=None, event_at=None):
    return Outcome(
        case_id="a",
        occurred=event_at is not None,
        event_at=event_at,
        recorded_at=recorded_at or at(20, 1),
        source_sha256="d" * 64,
        source_reference="synthetic clock regression, not real evidence",
    )


def test_future_window_and_outcome_cannot_leak_through_repeated_hour():
    p, o = plan(), outcome()
    # Wall 01:45 fold=0 is physically earlier than 01:15/01:20 fold=1.
    assert at(45, 0).astimezone(timezone.utc) < p.window_end.astimezone(timezone.utc)
    before = p.model_dump(mode="json"), o.model_dump(mode="json")
    report = evaluate_study(p, [forecast()], [o], as_of=at(45, 0))
    assert report["evaluable_count"] == 0 and report["coverage"] == 0
    assert report["rows"][0]["status"] == "window_pending"
    assert report["metrics"]["brier_score"] is None
    assert (p.model_dump(mode="json"), o.model_dump(mode="json")) == before
    assert p.window_end.fold == 1 and o.recorded_at.fold == 1


def test_folded_future_record_remains_pending_after_window_end():
    p = plan(window_end=at(20, 0))
    report = evaluate_study(
        p, [forecast()], [outcome(recorded_at=at(10, 1))], as_of=at(50, 0)
    )
    assert report["evaluable_count"] == 0
    assert report["rows"][0]["status"] == "outcome_pending"


def test_physically_ordered_window_can_reverse_wall_labels():
    p = plan(window_start=at(50, 0), window_end=at(10, 1))
    report = evaluate_study(
        p, [forecast()], [outcome(event_at=at(1, 1))], as_of=at(25, 1)
    )
    assert report["evaluable_count"] == 1
    assert not report["universal_perfect_prediction_established"]
    assert not report["authority_certified"]


def test_wall_order_cannot_make_a_physically_reversed_window_valid():
    with pytest.raises(ValidationError, match="窗口"):
        plan(window_start=at(10, 1), window_end=at(50, 0))


def test_baseline_cannot_be_frozen_after_registration_in_the_other_fold():
    with pytest.raises(ValidationError, match="基线"):
        plan(
            preregistered_at=at(50, 0),
            baseline_frozen_at=at(10, 1),
            window_start=at(15, 1),
            window_end=at(30, 1),
        )


def test_forecast_in_later_fold_cannot_precede_earlier_fold_window():
    p = plan(window_start=at(50, 0), window_end=at(30, 1))
    with pytest.raises(ValueError, match="窗口开始前"):
        evaluate_study(p, [forecast(at(10, 1))], [], as_of=at(40, 1))


def test_early_negative_record_in_first_fold_is_rejected():
    with pytest.raises(ValueError, match="完整目标窗口"):
        evaluate_study(
            plan(), [forecast()], [outcome(recorded_at=at(50, 0))], as_of=at(40, 1)
        )


def test_record_in_second_fold_is_accepted_even_with_smaller_wall_label():
    p = plan(window_end=at(50, 0))
    report = evaluate_study(
        p, [forecast()], [outcome(recorded_at=at(10, 1))], as_of=at(40, 1)
    )
    assert report["evaluable_count"] == 1
