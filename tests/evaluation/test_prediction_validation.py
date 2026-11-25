"""Hand-computed metrics, leakage counterexamples, and same-run quotations."""

import json
import subprocess
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.utils.json_digest import digest
from tests.unit_test.fixtures.prediction_study import AS_OF, forecast, outcome, plan
from validation.claims import CalculationClaim, verify_calculation_claims
from validation.predictions import evaluate_study


def test_empty_study_cannot_report_perfect_performance_or_authority() -> None:
    r = evaluate_study(plan(), [], [], as_of=AS_OF)
    assert r["metrics"]["accuracy"] is None
    assert r["metrics"]["brier_score"] is None
    assert r["coverage"] == 0
    assert r["real_world_efficacy"] == "not_tested"
    assert not r["authority_certified"] and not r["preregistered_performance_gate_met"]


@pytest.mark.parametrize(
    "input_name,key,replacement,diagnostic",
    [
        ("forecasts", None, "{}", "Input should be a valid list"),
        ("outcomes", None, "{}", "Input should be a valid list"),
        (
            "plan",
            '"baseline_probability": 0.5',
            '"baseline_probability": 0.4',
            "Duplicate JSON member: baseline_probability",
        ),
        (
            "forecasts",
            '"probability": 1.0',
            '"probability": 0.0',
            "Duplicate JSON member: probability",
        ),
        (
            "outcomes",
            '"occurred": true',
            '"occurred": false',
            "Duplicate JSON member: occurred",
        ),
    ],
)
def test_study_cli_rejects_ambiguous_json(
    tmp_path: Path, input_name: str, key: str | None, replacement: str, diagnostic: str
) -> None:
    root = Path(__file__).resolve().parents[2]
    registered = plan()
    inputs = {
        "plan": registered.model_dump(mode="json"),
        "forecasts": [forecast(0, 1.0, registered=registered).model_dump(mode="json")],
        "outcomes": [outcome(0, True, registered=registered).model_dump(mode="json")],
    }
    command = [sys.executable, "-m", "scripts.evaluation.audit_prediction_study"]
    for name, document in inputs.items():
        content = json.dumps(document)
        if name == input_name:
            if key is None:
                content = replacement
            else:
                assert key in content
                content = content.replace(key, f"{replacement}, {key}", 1)
        path = tmp_path / f"{name}.json"
        path.write_text(content, encoding="utf-8")
        command.extend([f"--{name}", str(path)])
    output = tmp_path / "report.json"
    command.extend(["--as-of", AS_OF.isoformat(), "--output", str(output)])

    result = subprocess.run(
        command, capture_output=True, cwd=root, text=True, timeout=30
    )
    assert result.returncode != 0
    assert diagnostic in result.stderr
    assert not output.exists()


def test_metrics_match_hand_calculation_and_frozen_baseline() -> None:
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


def test_perfect_small_sample_is_never_universal_perfect_prediction() -> None:
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


def test_near_one_confidence_does_not_round_quantile_to_infinity() -> None:
    r = evaluate_study(
        plan(confidence_level=0.9999999999999999),
        [forecast(0, 1.0), forecast(1, 0.0)],
        [outcome(0, True), outcome(1, False)],
        as_of=AS_OF,
    )
    lower, upper = r["metrics"]["accuracy_interval"]
    assert 0 < lower < 0.1
    assert 0.99 < upper <= 1


def test_missing_predictions_abstentions_and_outcomes_remain_in_coverage() -> None:
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
def test_leaked_or_unregistered_forecasts_fail_loudly(change) -> None:
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


def test_duplicate_predictions_and_correlated_subject_rows_are_rejected() -> None:
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
def test_outcome_window_and_complete_followup_are_required(changes) -> None:
    with pytest.raises(ValueError):
        evaluate_study(
            plan(), [forecast(0, 0.9)], [outcome(0, True, **changes)], as_of=AS_OF
        )


def test_future_recorded_outcome_cannot_leak_into_an_earlier_report() -> None:
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
def test_nonprobability_values_are_rejected(probability) -> None:
    with pytest.raises(ValidationError):
        forecast(0, probability)


def test_a_perfect_zero_variance_baseline_cannot_be_divided_by_zero() -> None:
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
        },
    }


def claim(payload, path="dayun.pillar", value="乙酉", **changes):
    return CalculationClaim.model_validate(
        {
            "path": path,
            "value": value,
            "run_id": payload["run_metadata"]["run_id"],
            **changes,
        }
    )


def test_same_run_exact_fact_is_verified_without_certifying_prose() -> None:
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
def test_false_values_types_and_uncalculated_predictions_are_rejected(
    path: str, value: float | int | str
) -> None:
    p = calculation()
    assert verify_calculation_claims(p, [claim(p, path, value)])["status"] == "rejected"


def test_edited_projected_and_different_run_payloads_fail_closed() -> None:
    p = calculation()
    c = claim(p)
    for changed in (
        {"run_metadata": p["run_metadata"], "dayun": p["dayun"]},
        {**deepcopy(p), "score": 100},
    ):
        assert (
            verify_calculation_claims(changed, [c], trusted_payload=p)["status"]
            == "rejected"
        )
    assert (
        verify_calculation_claims(p, [claim(p, run_id="other-run")])["status"]
        == "rejected"
    )
    assert verify_calculation_claims(p, [])["status"] == "rejected"
