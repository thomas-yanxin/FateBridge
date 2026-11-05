"""Casewise prospective references keep their identity and the original gates."""

import math

import pytest

from fatebridge.validation.sukuyo_study import (
    GAIN_METHOD,
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
)


def prepared(casewise=True, reverse=False):
    raw = protocol().model_dump(mode="json")
    plan = raw["blind_protocol"]["plan"]
    plan["confidence_level"] = 0.95
    # Enough pairs to expose the interval arithmetic without clipping both ends.
    n = 64
    plan["cohort"] = [
        {"case_id": str(i), "subject_id": f"synthetic-pair-{i}"} for i in range(n)
    ]
    raw["pairs"] = [
        {
            "case_id": str(i),
            "person1_subject_id": f"fictional-{i}-a",
            "person2_subject_id": f"fictional-{i}-b",
        }
        for i in range(n)
    ]
    plan["baseline_frozen_at"] = "2026-12-31T00:00:00Z"
    if casewise:
        plan["baseline_probability"] = None
        plan["baseline_forecasts"] = [
            {
                "case_id": str(i),
                "probability": 0.99 if i % 2 == 0 else 0.01,
                "issued_at": "2026-12-30T00:00:00Z",
                "target_definition": plan["target_definition"],
                "window_start": plan["window_start"],
                "window_end": plan["window_end"],
                "source_sha256": "e" * 64,
                "source_reference": "SYNTHETIC frozen reference; no real evidence",
            }
            for i in range(n)
        ]
        if reverse:
            plan["baseline_forecasts"].reverse()
    p = SukuyoProtocol.model_validate(raw)
    submitted = [
        f.model_copy(update={"case_id": str(i)})
        for i in range(n)
        for f in [forecasts()[i % 2]]
    ]
    observed = [
        o.model_copy(update={"case_id": str(i)})
        for i in range(n)
        for o in [outcomes()[i % 2]]
    ]
    evidence = {str(i): EVIDENCE[str(i % 2)] for i in range(n)}
    sources = {str(i): OUTCOME_SOURCES[str(i % 2)] for i in range(n)}
    return p, submitted, observed, evidence, sources


def report(casewise=True, reverse=False, missing=False, abstained=False):
    p, submitted, observed, evidence, sources = prepared(casewise, reverse)
    if abstained:
        submitted[0] = submitted[0].model_copy(update={"probability": None})
    if reverse:
        submitted.reverse()
        observed.reverse()
    if missing:
        missing_id = observed.pop().case_id
        sources.pop(missing_id)
    registration = register(p, MODEL, at=REGISTER_AT, artifacts=ARTIFACTS)
    sealed = seal_forecasts(registration, submitted, at=SEAL_AT, evidence=evidence)
    return evaluate(
        registration, sealed, observed, at=EVALUATE_AT, outcome_sources=sources
    )


def test_sukuyo_casewise_reference_uses_the_registered_case_not_a_constant_fallback():
    result = report()
    assert result["metrics"]["baseline_brier_score"] == pytest.approx(0.0001)
    assert result["metrics"]["brier_score"] == pytest.approx(0.01)
    assert result["metrics"]["brier_skill_score"] == pytest.approx(-99.0)
    radius = math.sqrt(2 * math.log(2 / 0.05) / 64)
    assert result["paired_brier_gain_interval"] == pytest.approx(
        [-0.0099 - radius, -0.0099 + radius]
    )
    assert result["paired_gain_interval_method"] == GAIN_METHOD
    assert result["pair_count"] == 64 and result["coverage"] == 1.0
    assert not result["confidence_bound_gate_met"]
    assert not result["preregistered_performance_gate_met"]
    assert result["real_world_efficacy"] == "not_established_by_synthetic_data"


def test_sukuyo_strong_reference_can_reverse_skill_without_changing_forecasts():
    constant, strong = report(False), report(True)
    assert constant["forecast_records_sha256"] == strong["forecast_records_sha256"]
    assert constant["outcome_records_sha256"] == strong["outcome_records_sha256"]
    assert constant["metrics"]["brier_skill_score"] == pytest.approx(0.96)
    assert strong["metrics"]["brier_skill_score"] == pytest.approx(-99.0)
    assert not strong["authority_certified"] and not constant["authority_certified"]


def test_sukuyo_reference_order_cannot_change_case_alignment():
    first, shuffled = report(), report(reverse=True)
    assert first["metrics"] == shuffled["metrics"]
    assert first["paired_brier_gain_interval"] == shuffled["paired_brier_gain_interval"]


@pytest.mark.parametrize("missing,abstained", [(True, False), (False, True)])
def test_sukuyo_casewise_reference_keeps_missing_and_abstained_pairs(
    missing, abstained
):
    result = report(missing=missing, abstained=abstained)
    assert result["pair_count"] == 64
    assert result["coverage"] == 63 / 64
    assert result["paired_brier_gain_interval"] is None
    assert not result["confidence_bound_gate_met"]
