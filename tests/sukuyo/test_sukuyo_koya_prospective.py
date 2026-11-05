"""New collation cannot be retrofitted into sealed synthetic forecasts."""

import hashlib

import pytest

from fatebridge.core.sukuyo_koya import SOURCE
from fatebridge.validation.sukuyo_study import (
    SukuyoProtocol,
    evaluate,
    register,
    seal_forecasts,
)
from tests.sukuyo.test_sukuyo_study import (
    ARTIFACTS,
    EVALUATE_AT,
    EVIDENCE,
    MODEL,
    OUTCOME_SOURCES,
    REGISTER_AT,
    SEAL_AT,
    forecasts,
    outcomes,
    protocol,
    registered,
)


def updated_source_artifacts():
    return {**ARTIFACTS, "classical_sources": SOURCE.read_bytes()}


def test_new_actual_printed_source_requires_its_own_registered_digest():
    with pytest.raises(ValueError, match="实际规则"):
        register(
            protocol(), MODEL, at=REGISTER_AT, artifacts=updated_source_artifacts()
        )


def test_new_source_cannot_inherit_old_sealed_forecasts_or_efficacy():
    old = registered()
    sealed = seal_forecasts(old, forecasts(), at=SEAL_AT, evidence=EVIDENCE)
    artifacts = updated_source_artifacts()
    data = protocol().model_dump(mode="json")
    data["blind_protocol"]["artifact_sha256"]["classical_sources"] = hashlib.sha256(
        artifacts["classical_sources"]
    ).hexdigest()
    new = register(
        SukuyoProtocol.model_validate(data), MODEL, at=REGISTER_AT, artifacts=artifacts
    )
    with pytest.raises(ValueError, match="注册方案不一致"):
        evaluate(
            new, sealed, outcomes(), at=EVALUATE_AT, outcome_sources=OUTCOME_SOURCES
        )
    own_sealed = seal_forecasts(new, forecasts(), at=SEAL_AT, evidence=EVIDENCE)
    result = evaluate(
        new, own_sealed, outcomes(), at=EVALUATE_AT, outcome_sources=OUTCOME_SOURCES
    )
    assert result["real_world_efficacy"] == "not_established_by_synthetic_data"
    assert not result["authority_certified"]
    assert not result["confidence_bound_gate_met"]
