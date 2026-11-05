"""Synthetic record replay attacks, not evidence of real prediction skill."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.validation.jyotish_study import reveal_and_evaluate, seal_forecasts
from fatebridge.validation.predictions import (
    Forecast,
    Outcome,
    StudyPlan,
    digest,
    evaluate_study,
)
from tests.test_prediction_validation import AS_OF, forecast, outcome, plan

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("bind_forecast", [False, True])
@pytest.mark.parametrize("bind_outcome", [False, True])
def test_both_original_record_commitments_are_needed_for_protocol_gates(
    bind_forecast, bind_outcome
):
    registered = plan(100)
    forecasts = [
        forecast(i, 1.0, registered=registered if bind_forecast else None)
        for i in range(100)
    ]
    outcomes = [
        outcome(i, True, registered=registered if bind_outcome else None)
        for i in range(100)
    ]
    before = [f.model_dump(mode="json") for f in forecasts], [
        o.model_dump(mode="json") for o in outcomes
    ]
    report = evaluate_study(registered, forecasts, outcomes, as_of=AS_OF)
    assert report["registered_numeric_gate_met"]
    assert (
        report["statistical_evidence"]["lower_bound_excess_over_registered_threshold"]
        > 0
    )
    assert report["preregistered_performance_gate_met"] is (
        bind_forecast and bind_outcome
    )
    assert report["statistical_evidence_gate_met"] is (bind_forecast and bind_outcome)
    assert report["record_plan_binding"]["forecast_bound_count"] == 100 * bind_forecast
    assert report["record_plan_binding"]["outcome_bound_count"] == 100 * bind_outcome
    assert report["record_plan_binding"]["registered_cohort_fully_bound"] is (
        bind_forecast and bind_outcome
    )
    assert ("missing_forecast_plan_commitment" in report["protocol_blockers"]) is (
        not bind_forecast
    )
    assert ("missing_outcome_plan_commitment" in report["protocol_blockers"]) is (
        not bind_outcome
    )
    assert (
        [f.model_dump(mode="json") for f in forecasts],
        [o.model_dump(mode="json") for o in outcomes],
    ) == before
    assert not report["authority_certified"]
    assert report["real_world_efficacy"] == "not_established_by_synthetic_data"


@pytest.mark.parametrize("role", ["forecast", "outcome"])
@pytest.mark.parametrize(
    "change",
    [
        {"study_id": "different-study"},
        {"target_definition": "Different fictional endpoint"},
        {"window_start": "2026-12-15T00:00:00Z"},
        {"window_end": "2027-12-15T00:00:00Z"},
        {"baseline_probability": 0.4},
        {"decision_threshold": 0.6},
        {"minimum_evaluable": 1},
        {"confidence_level": 0.9},
        {"minimum_brier_skill": 0.1},
        {"planned_evaluations": 2},
        {"training_subject_ids": ["different-training-declaration"]},
        {
            "cohort": [
                {"case_id": "0", "subject_id": "different-person"},
                {"case_id": "1", "subject_id": "fictional-1"},
            ]
        },
    ],
)
def test_unchanged_bound_records_cannot_be_reused_under_a_changed_plan(role, change):
    registered = plan()
    altered = StudyPlan.model_validate({**registered.model_dump(mode="json"), **change})
    assert digest(registered.model_dump(mode="json")) != digest(
        altered.model_dump(mode="json")
    )
    forecasts = [forecast(0, 1.0, registered=registered)] if role == "forecast" else []
    outcomes = [outcome(0, True, registered=registered)] if role == "outcome" else []
    with pytest.raises(ValueError, match="完整研究方案指纹不一致"):
        evaluate_study(altered, forecasts, outcomes, as_of=AS_OF)


@pytest.mark.parametrize("role", ["forecast", "outcome"])
@pytest.mark.parametrize("probability", [None, 1.0])
def test_mismatched_records_are_checked_even_when_no_score_would_be_used(
    role, probability
):
    registered = plan()
    f = (
        forecast(0, probability, study_plan_sha256="e" * 64)
        if role == "forecast"
        else forecast(0, probability)
    )
    o = (
        outcome(0, True, study_plan_sha256="e" * 64)
        if role == "outcome"
        else outcome(0, True)
    )
    # Forecast scoring is window_pending at this instant; mismatched future
    # outcome records still must not be admitted as belonging to this plan.
    with pytest.raises(ValueError, match="完整研究方案指纹不一致"):
        evaluate_study(registered, [f], [o], as_of=f.issued_at)


@pytest.mark.parametrize("role", ["forecast", "outcome"])
@pytest.mark.parametrize("value", [True, "A" * 64, "a" * 63, "not-a-digest"])
def test_mutable_record_copies_cannot_bypass_commitment_shape_checks(role, value):
    registered = plan()
    f, o = forecast(0, 1.0, registered=registered), outcome(
        0, True, registered=registered
    )
    if role == "forecast":
        f = f.model_copy(update={"study_plan_sha256": value})
    else:
        o = o.model_copy(update={"study_plan_sha256": value})
    with pytest.raises(ValidationError):
        evaluate_study(registered, [f], [o], as_of=AS_OF)


def test_partial_missing_and_abstained_rows_keep_both_binding_and_coverage_facts():
    registered = plan(3)
    report = evaluate_study(
        registered,
        [forecast(0, 1.0, registered=registered), forecast(1, None)],
        [outcome(0, True, registered=registered), outcome(1, False)],
        as_of=AS_OF,
    )
    assert report["evaluable_count"] == 1
    assert [r["status"] for r in report["rows"]] == [
        "evaluable",
        "abstained",
        "missing_forecast",
    ]
    assert [r["forecast_plan_binding"] for r in report["rows"]] == [
        "bound",
        "unbound",
        "missing_record",
    ]
    assert [r["outcome_plan_binding"] for r in report["rows"]] == [
        "bound",
        "unbound",
        "missing_record",
    ]
    assert report["record_plan_binding"]["forecast_unbound_count"] == 1
    assert not report["record_plan_binding"]["registered_cohort_fully_bound"]
    assert not report["statistical_evidence_gate_met"]


def test_fingerprint_is_of_the_validated_plan_not_pretty_json_file_bytes():
    registered = plan()
    pretty = json.dumps(
        registered.model_dump(mode="json"), ensure_ascii=False, indent=4
    )
    reparsed = StudyPlan.model_validate_json(pretty)
    assert digest(reparsed.model_dump(mode="json")) == digest(
        registered.model_dump(mode="json")
    )
    report = evaluate_study(
        reparsed,
        [forecast(0, 1.0, registered=registered)],
        [outcome(0, True, registered=registered)],
        as_of=AS_OF,
    )
    assert report["record_plan_binding"]["forecast_bound_count"] == 1
    assert report["record_plan_binding"]["outcome_bound_count"] == 1


@pytest.mark.parametrize("mode", ["bound", "legacy", "wrong"])
def test_actual_offline_cli_and_api_share_binding_rules_and_preserve_prior_report(
    tmp_path, mode
):
    registered = plan(100)
    kwargs = {"registered": registered} if mode == "bound" else {}
    if mode == "wrong":
        kwargs["study_plan_sha256"] = "e" * 64
    forecasts = [forecast(i, 1.0, **kwargs) for i in range(100)]
    outcomes = [outcome(i, True, **kwargs) for i in range(100)]
    inputs = {
        "plan": registered.model_dump(mode="json"),
        "forecasts": [f.model_dump(mode="json") for f in forecasts],
        "outcomes": [o.model_dump(mode="json") for o in outcomes],
    }
    argv = [sys.executable, str(ROOT / "scripts/audit_prediction_study.py")]
    for key, value in inputs.items():
        path = tmp_path / f"{key}.json"
        path.write_text(json.dumps(value, ensure_ascii=False))
        argv.extend([f"--{key}", str(path)])
    output = tmp_path / "report.json"
    argv.extend(["--as-of", AS_OF.isoformat(), "--output", str(output)])
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    result = subprocess.run(argv, env=env, capture_output=True, text=True)
    (tmp_path / "cli.stdout").write_text(result.stdout)
    (tmp_path / "cli.stderr").write_text(result.stderr)
    (tmp_path / "cli-result.json").write_text(
        json.dumps({"argv": argv, "exit_code": result.returncode})
    )
    if mode == "wrong":
        assert result.returncode != 0
        assert not output.exists()
        assert "完整研究方案指纹不一致" in result.stderr
        return
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text())
    assert report == evaluate_study(registered, forecasts, outcomes, as_of=AS_OF)
    assert report["statistical_evidence_gate_met"] is (mode == "bound")
    original = output.read_bytes()
    repeated = subprocess.run(argv, env=env, capture_output=True, text=True)
    assert repeated.returncode != 0
    assert output.read_bytes() == original
    assert "FileExistsError" in repeated.stderr
