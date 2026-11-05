"""Frozen case-wise references; synthetic values never count as real skill."""

import hashlib
import importlib.util
import json
import math
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.validation.predictions import StudyPlan, evaluate_study
from fatebridge.validation.qimen_study import (
    QimenCommitment,
    StudyInput,
    audit_study,
    commitment_fingerprint,
    seal_forecasts,
)
from tests.evaluation.test_prediction_validation import AS_OF, forecast, outcome, plan
from tests.qimen.test_qimen_study import AS_OF as QIMEN_AS_OF  # noqa: F401
from tests.qimen.test_qimen_study import ISSUED, frozen_study, outcomes, packet


def records(ids, probabilities):
    return [
        dict(
            case_id=str(i),
            probability=p,
            issued_at="2026-10-19T00:00:00Z",
            target_definition="Explicit test event in the registered window",
            window_start="2027-01-01T00:00:00Z",
            window_end="2028-01-01T00:00:00Z",
            source_sha256="e" * 64,
            source_reference="SYNTHETIC reference only",
        )
        for i, p in zip(ids, probabilities)
    ]


def casewise(probabilities):
    raw = plan(len(probabilities)).model_dump(mode="json")
    raw["baseline_probability"] = None
    raw["baseline_forecasts"] = records(range(len(probabilities)), probabilities)
    return StudyPlan.model_validate(raw)


def test_scores_use_the_corresponding_reference_probability_for_each_same_case():
    r = evaluate_study(
        casewise([0.7, 0.1]),
        [forecast(0, 0.9), forecast(1, 0.6)],
        [outcome(0, True), outcome(1, False)],
        as_of=AS_OF,
    )
    assert r["metrics"]["brier_score"] == pytest.approx(0.185)
    assert r["metrics"]["baseline_brier_score"] == pytest.approx(0.05)
    assert r["metrics"]["brier_skill_score"] == pytest.approx(-2.7)
    assert r["metrics"]["baseline_accuracy"] == 1.0
    assert r["statistical_evidence"]["mean_paired_brier_improvement"] == pytest.approx(
        -0.135
    )
    assert r["baseline_comparison"]["mode"] == "frozen_per_case"
    assert not r["baseline_comparison"]["reference_strength_certified"]
    assert not r["baseline_comparison"]["source_provenance_authenticated"]
    assert [x["baseline_probability"] for x in r["rows"]] == [0.7, 0.1]
    assert all(x["baseline_record_sha256"] for x in r["rows"])


def test_shuffling_reference_forecast_and_outcome_records_cannot_swap_case_alignment():
    p = casewise([0.1, 0.8, 0.3])
    forecasts = [forecast(0, 0.2), forecast(1, 0.7), forecast(2, 0.4)]
    labels = [outcome(0, False), outcome(1, True), outcome(2, True)]
    a = evaluate_study(p, forecasts, labels, as_of=AS_OF)
    raw = p.model_dump(mode="json")
    raw["baseline_forecasts"].reverse()
    b = evaluate_study(
        StudyPlan.model_validate(raw),
        list(reversed(forecasts)),
        list(reversed(labels)),
        as_of=AS_OF,
    )
    assert (
        a["metrics"] == b["metrics"]
        and a["statistical_evidence"] == b["statistical_evidence"]
    )


def test_a_strong_reference_can_reverse_the_result_without_changing_any_prediction():
    n = 1000
    submitted = [forecast(i, 0.75 if i % 2 else 0.25) for i in range(n)]
    labels = [outcome(i, bool(i % 2)) for i in range(n)]
    weak = evaluate_study(plan(n), submitted, labels, as_of=AS_OF)
    strong = evaluate_study(
        casewise([0.95 if i % 2 else 0.05 for i in range(n)]),
        submitted,
        labels,
        as_of=AS_OF,
    )
    assert weak["forecast_records_sha256"] == strong["forecast_records_sha256"]
    assert weak["outcome_records_sha256"] == strong["outcome_records_sha256"]
    assert weak["metrics"]["brier_skill_score"] == pytest.approx(0.75)
    # Legacy records retain the numerical counterfactual comparison, but cannot
    # certify either plan without the originally issued plan commitments.
    assert not weak["statistical_evidence_gate_met"]
    assert "missing_forecast_plan_commitment" in weak["protocol_blockers"]
    weak_plan = plan(n)
    bound_weak = evaluate_study(
        weak_plan,
        [forecast(i, 0.75 if i % 2 else 0.25, registered=weak_plan) for i in range(n)],
        [outcome(i, bool(i % 2), registered=weak_plan) for i in range(n)],
        as_of=AS_OF,
    )
    assert bound_weak["statistical_evidence_gate_met"]
    assert strong["metrics"]["brier_skill_score"] == pytest.approx(-24)
    assert not strong["statistical_evidence_gate_met"]
    assert not strong["preregistered_performance_gate_met"]
    assert not strong["authority_certified"] and not weak["authority_certified"]
    assert strong["data_kind"] == "synthetic"


def test_identical_casewise_references_preserve_constant_baseline_statistics():
    submitted = [forecast(0, 0.9), forecast(1, 0.8)]
    labels = [outcome(0, True), outcome(1, False)]
    a = evaluate_study(plan(), submitted, labels, as_of=AS_OF)
    b = evaluate_study(casewise([0.5, 0.5]), submitted, labels, as_of=AS_OF)
    assert (
        a["metrics"] == b["metrics"]
        and a["statistical_evidence"] == b["statistical_evidence"]
    )


def test_heterogeneous_references_keep_the_registered_hoeffding_bound():
    p = casewise([0.7, 0.1])
    p.minimum_brier_skill = 0.4
    p.planned_evaluations = 3
    r = evaluate_study(
        p,
        [forecast(0, 0.9), forecast(1, 0.6)],
        [outcome(0, True), outcome(1, False)],
        as_of=AS_OF,
    )
    mean = 0.6 * 0.05 - 0.185
    lower = mean - 1.6 * math.sqrt(math.log(3 / 0.05) / 4)
    assert r["statistical_evidence"][
        "mean_excess_over_registered_threshold"
    ] == pytest.approx(mean)
    assert r["statistical_evidence"][
        "lower_bound_excess_over_registered_threshold"
    ] == pytest.approx(lower)


def test_abstentions_and_missing_forecasts_stay_in_coverage_without_reference_fallback():
    p = casewise([0.2, 0.8, 0.9])
    r = evaluate_study(
        p,
        [forecast(0, 0.7), forecast(1, None)],
        [outcome(i, True) for i in range(3)],
        as_of=AS_OF,
    )
    assert r["coverage"] == pytest.approx(1 / 3)
    assert [x["status"] for x in r["rows"]] == [
        "evaluable",
        "abstained",
        "missing_forecast",
    ]
    assert r["metrics"]["baseline_brier_score"] == pytest.approx(0.64)
    assert r["baseline_comparison"]["per_case_record_count"] == 3
    assert not r["preregistered_performance_gate_met"]


def test_perfect_reference_is_not_divided_by_zero_or_called_model_skill():
    r = evaluate_study(
        casewise([1.0, 0.0]),
        [forecast(0, 1.0), forecast(1, 0.0)],
        [outcome(0, True), outcome(1, False)],
        as_of=AS_OF,
    )
    assert r["metrics"]["baseline_brier_score"] == 0
    assert r["metrics"]["brier_skill_score"] is None
    assert not r["preregistered_performance_gate_met"]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "extra",
        "duplicate",
        "late_issue",
        "missing_freeze",
        "late_freeze",
        "bad_source_hash",
        "blank_source",
        "null_probability",
        "string_probability",
        "bool_probability",
        "nan_probability",
        "infinite_probability",
        "both_modes",
        "neither_mode",
        "target_mismatch",
        "window_start_mismatch",
        "window_end_mismatch",
    ],
)
def test_incomplete_or_post_registration_reference_information_is_rejected(mutation):
    raw = casewise([0.7, 0.1]).model_dump(mode="json")
    if mutation == "missing":
        raw["baseline_forecasts"].pop()
    elif mutation == "extra":
        raw["baseline_forecasts"].append(records(["unknown"], [0.5])[0])
    elif mutation == "duplicate":
        raw["baseline_forecasts"].append(deepcopy(raw["baseline_forecasts"][0]))
    elif mutation == "late_issue":
        raw["baseline_forecasts"][0]["issued_at"] = "2026-10-21T00:00:00Z"
    elif mutation == "missing_freeze":
        raw["baseline_frozen_at"] = None
    elif mutation == "late_freeze":
        raw["baseline_frozen_at"] = "2026-10-23T00:00:00Z"
    elif mutation == "bad_source_hash":
        raw["baseline_forecasts"][0]["source_sha256"] = "bad"
    elif mutation == "blank_source":
        raw["baseline_forecasts"][0]["source_reference"] = "   "
    elif mutation.endswith("_probability"):
        raw["baseline_forecasts"][0]["probability"] = {
            "null_probability": None,
            "string_probability": "0.7",
            "bool_probability": True,
            "nan_probability": float("nan"),
            "infinite_probability": float("inf"),
        }[mutation]
    elif mutation == "both_modes":
        raw["baseline_probability"] = 0.5
    elif mutation == "target_mismatch":
        raw["baseline_forecasts"][0]["target_definition"] = "A different outcome"
    elif mutation == "window_start_mismatch":
        raw["baseline_forecasts"][0]["window_start"] = "2027-01-02T00:00:00Z"
    elif mutation == "window_end_mismatch":
        raw["baseline_forecasts"][0]["window_end"] = "2028-01-02T00:00:00Z"
    else:
        raw["baseline_forecasts"] = None
    with pytest.raises(ValueError):
        StudyPlan.model_validate(raw)


def test_mutated_model_copy_is_validated_again_before_generic_scoring():
    p = casewise([0.7, 0.1])
    p.baseline_forecasts.pop()
    with pytest.raises(ValueError, match="覆盖注册队列"):
        evaluate_study(p, [forecast(0, 0.9)], [outcome(0, True)], as_of=AS_OF)


def qimen_casewise(packet):
    study = packet.study.model_dump(mode="json")
    study["plan"]["baseline_probability"] = None
    study["plan"]["baseline_forecasts"] = [
        {
            **r,
            "issued_at": "2024-12-31T00:00:00Z",
            "target_definition": study["plan"]["target_definition"],
            "window_start": study["plan"]["window_start"],
            "window_end": study["plan"]["window_end"],
        }
        for r in records([c["case_id"] for c in study["castings"]], [0.7, 0.4, 0.2])
    ]
    return seal_forecasts(StudyInput.model_validate(study), at=ISSUED)


def test_actual_qimen_replay_scores_against_the_frozen_same_case_reference(packet):
    sealed = qimen_casewise(packet)
    r = audit_study(
        sealed,
        outcomes(),
        as_of=QIMEN_AS_OF,
        expected_commitment_sha256=commitment_fingerprint(sealed),
    )
    assert sealed.format == "qimen_forecast_commitment_v3"
    assert r["metrics"]["baseline_brier_score"] == pytest.approx(0.265)
    assert r["baseline_comparison"]["mode"] == "frozen_per_case"
    assert r["registered_count"] == 3 and r["evaluable_count"] == 2
    assert not r["validated_qimen_predictor"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("probability", 0.99),
        ("source_reference", "replacement-reference"),
        ("source_sha256", "f" * 64),
        ("issued_at", "2024-12-30T00:00:00Z"),
    ],
)
def test_reference_value_and_source_edits_are_bound_to_the_same_qimen_receipts(
    packet, field, value
):
    sealed = qimen_casewise(packet)
    raw = sealed.model_dump(mode="json")
    raw["study"]["plan"]["baseline_forecasts"][0][field] = value
    with pytest.raises(ValueError, match="研究输入"):
        audit_study(QimenCommitment.model_validate(raw), outcomes(), as_of=QIMEN_AS_OF)


def test_whole_reference_reseal_cannot_replace_the_independently_anchored_packet(
    packet,
):
    sealed = qimen_casewise(packet)
    expected = commitment_fingerprint(sealed)
    study = sealed.study.model_copy(deep=True)
    study.plan.baseline_forecasts[0].probability = 0.99
    replacement = seal_forecasts(study, at=ISSUED)
    with pytest.raises(ValueError, match="事前独立保存"):
        audit_study(
            replacement,
            outcomes(),
            as_of=QIMEN_AS_OF,
            expected_commitment_sha256=expected,
        )


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_old_qimen_packets_are_not_silently_upgraded_for_new_baseline_semantics(
    packet, version
):
    raw = packet.model_dump(mode="json")
    raw["format"] = "qimen_forecast_commitment_" + version
    with pytest.raises(ValueError, match="原固定环境"):
        QimenCommitment.model_validate(raw)


def test_cli_roundtrip_keeps_frozen_casewise_baseline_artifacts(
    packet, tmp_path, capsys
):
    sealed = qimen_casewise(packet)
    spec = importlib.util.spec_from_file_location(
        "qimen_casewise_cli",
        Path(__file__).parents[2] / "scripts/qimen/audit_qimen_study.py",
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    source = tmp_path / "study.json"
    target = tmp_path / "packet.json"
    labels = tmp_path / "labels.json"
    report = tmp_path / "report.json"
    source.write_text(sealed.study.model_dump_json())
    labels.write_text(json.dumps([r.model_dump(mode="json") for r in outcomes()]))
    assert (
        cli.main(
            [
                "seal",
                "--study",
                str(source),
                "--synthetic-at",
                ISSUED.isoformat(),
                "--output",
                str(target),
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert (
        cli.main(
            [
                "evaluate",
                "--commitment",
                str(target),
                "--outcomes",
                str(labels),
                "--as-of",
                QIMEN_AS_OF.isoformat(),
                "--expected-commitment-sha256",
                summary["commitment_sha256"],
                "--output",
                str(report),
            ]
        )
        == 0
    )
    assert json.loads(report.read_text())["metrics"][
        "baseline_brier_score"
    ] == pytest.approx(0.265)


def test_synthetic_demo_writes_reference_artifacts_matching_frozen_hashes(
    tmp_path, monkeypatch, capsys
):
    spec = importlib.util.spec_from_file_location(
        "qimen_casewise_demo",
        Path(__file__).parents[2] / "scripts/qimen/demo_qimen_study.py",
    )
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    folder = tmp_path / "synthetic"
    monkeypatch.setattr(
        sys,
        "argv",
        ["demo", "--output-dir", str(folder), "--baseline-kind", "per-case"],
    )
    assert demo.main() == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["evaluable_count"] == 0 and not summary["authority_certified"]
    packet = QimenCommitment.model_validate_json(
        (folder / "commitment.json").read_text()
    )
    assert packet.format == "qimen_forecast_commitment_v3"
    assert packet.study.plan.baseline_probability is None
    for b in packet.study.plan.baseline_forecasts:
        artifact = folder / b.source_reference.split(": ", 1)[1]
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == b.source_sha256
        assert json.loads(artifact.read_text())["data_kind"] == "synthetic"
