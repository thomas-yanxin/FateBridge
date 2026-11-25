"""Synthetic records for binary forecast study tests."""

from datetime import datetime, timezone

from pydantic import JsonValue

from fatebridge.utils.json_digest import digest
from validation.predictions import Forecast, Outcome, StudyPlan

MODEL = "a" * 64
AS_OF = datetime(2028, 2, 1, tzinfo=timezone.utc)


def plan(n: int = 2, **changes: JsonValue) -> StudyPlan:
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


def forecast(
    i: int,
    p: float | None,
    *,
    registered: StudyPlan | None = None,
    **changes: JsonValue,
) -> Forecast:
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


def outcome(
    i: int,
    occurred: bool | None,
    *,
    registered: StudyPlan | None = None,
    **changes: JsonValue,
) -> Outcome:
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
