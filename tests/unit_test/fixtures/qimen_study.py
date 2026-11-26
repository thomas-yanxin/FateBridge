"""Synthetic Qimen study witnesses for replay and commitment tests."""

from datetime import datetime, timezone

import pytest

from validation.predictions import Outcome
from validation.qimen_study import (
    FrozenQimenPolicy,
    QimenCommitment,
    StudyInput,
    engine_fingerprint,
    policy_fingerprint,
    seal_forecasts,
)

ISSUED = datetime(2026, 12, 31, tzinfo=timezone.utc)
AS_OF = datetime(2027, 3, 1, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def frozen_study() -> QimenCommitment:
    policy = FrozenQimenPolicy(
        policy_id="synthetic-adversarial-fixture-not-a-predictor",
        target_definition="Synthetic binary event, never an empirical sample",
        ju_method="chaibu",
        god_profile="yanyi_text",
        season_profile="yanyi_vol1_verse",
        use_true_solar_time=False,
        source_disagreement_action="use_declared_rules",
        rules=[
            {
                "rule_id": "test-only-not-calibrated",
                "all_of": [
                    {
                        "feature": "pattern_present",
                        "pattern": "hidden_day_stem",
                        "equals": False,
                    }
                ],
                "probability": 0.8,
            }
        ],
        fallback_probability=0.2,
    )
    casts = [
        {
            "case_id": "literal",
            "subject_id": "synthetic-1",
            "casting_at": "2026-01-15T16:00:00+08:00",
            "timezone_name": "Asia/Hong_Kong",
            "longitude": 114.17,
        },
        {
            "case_id": "jia",
            "subject_id": "synthetic-2",
            "casting_at": "2026-01-20T16:00:00+08:00",
            "timezone_name": "Asia/Hong_Kong",
            "longitude": 114.17,
        },
        {
            "case_id": "fold",
            "subject_id": "synthetic-3",
            "casting_at": "2026-11-01T05:30:00Z",
            "timezone_name": "America/New_York",
            "longitude": -74.0,
        },
    ]
    for c in casts:
        c.update(
            {
                "recorded_at": "2026-12-30T00:00:00Z",
                "question_record_sha256": "a" * 64,
                "question_record_reference": "synthetic question only",
            }
        )
    study = StudyInput.model_validate(
        {
            "plan": {
                "study_id": "synthetic-qimen-replay",
                "data_kind": "synthetic",
                "preregistered_at": "2025-01-01T00:00:00Z",
                "registration_reference": "synthetic-registration-not-a-real-registry",
                "window_start": "2027-01-01T00:00:00Z",
                "window_end": "2027-02-01T00:00:00Z",
                "target_definition": policy.target_definition,
                "model_sha256": engine_fingerprint(),
                "interpretation_policy_sha256": policy_fingerprint(policy),
                "baseline_frozen_at": "2025-01-01T00:00:00Z",
                "baseline_probability": 0.5,
                "minimum_evaluable": 1,
                "training_subject_ids": [],
                "cohort": [
                    {"case_id": c["case_id"], "subject_id": c["subject_id"]}
                    for c in casts
                ],
            },
            "policy": policy.model_dump(mode="json"),
            "castings": casts,
        }
    )
    return seal_forecasts(study, at=ISSUED)


@pytest.fixture
def packet(frozen_study: QimenCommitment) -> QimenCommitment:
    return QimenCommitment.model_validate(frozen_study.model_dump(mode="json"))


def outcomes() -> list[Outcome]:
    return [
        Outcome(
            case_id=c,
            occurred=False,
            recorded_at="2027-02-02T00:00:00Z",
            source_sha256="f" * 64,
            source_reference="synthetic outcome only",
        )
        for c in ("literal", "jia", "fold")
    ]
