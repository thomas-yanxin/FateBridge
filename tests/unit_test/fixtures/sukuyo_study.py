"""Synthetic protocol, predictions and records for Sukuyo workflow tests."""

import hashlib
from datetime import datetime, timezone

from pydantic import JsonValue

from validation.predictions import Forecast, Outcome
from validation.sukuyo_study import REQUIRED_ARTIFACTS, SukuyoProtocol, register

MODEL = b"synthetic test model; not an astrological probability mapping"
MODEL_HASH = hashlib.sha256(MODEL).hexdigest()
ARTIFACTS = {name: ("synthetic actual " + name).encode() for name in REQUIRED_ARTIFACTS}
EVIDENCE = {str(i): f"synthetic calculation evidence {i}".encode() for i in range(2)}
OUTCOME_SOURCES = {str(i): f"synthetic outcome record {i}".encode() for i in range(2)}
REGISTER_AT = datetime(2027, 1, 2, tzinfo=timezone.utc)
SEAL_AT = datetime(2027, 1, 3, tzinfo=timezone.utc)
EVALUATE_AT = datetime(2028, 2, 2, tzinfo=timezone.utc)


def protocol(**changes: JsonValue) -> SukuyoProtocol:
    base = {
        "blind_protocol": {
            "plan": {
                "study_id": "synthetic-workflow-test",
                "data_kind": "synthetic",
                "preregistered_at": "2027-01-01T00:00:00Z",
                "window_start": "2027-02-01T00:00:00Z",
                "window_end": "2028-02-01T00:00:00Z",
                "target_definition": "Synthetic binary endpoint, not a real relationship observation",
                "model_sha256": MODEL_HASH,
                "baseline_probability": 0.5,
                "minimum_evaluable": 2,
                "training_subject_ids": [],
                "cohort": [
                    {"case_id": str(i), "subject_id": "synthetic-pair-" + str(i)}
                    for i in range(2)
                ],
            },
            "training_subject_ids": [],
            "baseline_derivation": "Frozen synthetic test baseline",
            "outcome_adjudication": "Independent source after complete follow-up; synthetic in this test",
            "recruitment_and_exclusions": "Frozen complete two-pair synthetic cohort",
            "probability_mapping": "Explicit synthetic values; no mapping from traditional labels",
            "sample_size_justification": "Two cases verify arithmetic only, not statistical efficacy",
            "analysis_plan": "Frozen Brier endpoint; no early stopping; keep missing cases in coverage",
            "artifact_sha256": {
                k: hashlib.sha256(v).hexdigest() for k, v in ARTIFACTS.items()
            },
        },
        "pairs": [
            {
                "case_id": str(i),
                "person1_subject_id": f"fictional-{i}-a",
                "person2_subject_id": f"fictional-{i}-b",
            }
            for i in range(2)
        ],
        "relationship_context": "synthetic business pairing test",
        "hypothesis": "Synthetic prediction pipeline validation only",
    }
    base.update(changes)
    return SukuyoProtocol.model_validate(base)


def registered() -> dict[str, JsonValue]:
    return register(protocol(), MODEL, at=REGISTER_AT, artifacts=ARTIFACTS)


def forecasts() -> list[Forecast]:
    return [
        Forecast(
            case_id=str(i),
            issued_at="2027-01-02T12:00:00Z",
            model_sha256=MODEL_HASH,
            evidence_sha256=hashlib.sha256(EVIDENCE[str(i)]).hexdigest(),
            probability=p,
        )
        for i, p in enumerate([0.9, 0.1])
    ]


def outcomes() -> list[Outcome]:
    return [
        Outcome(
            case_id=str(i),
            occurred=bool(v),
            event_at="2027-07-01T00:00:00Z" if v else None,
            recorded_at="2028-02-02T00:00:00Z",
            source_sha256=hashlib.sha256(OUTCOME_SOURCES[str(i)]).hexdigest(),
            source_reference="synthetic independent outcome",
        )
        for i, v in enumerate([1, 0])
    ]
