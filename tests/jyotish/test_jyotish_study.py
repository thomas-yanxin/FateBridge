"""Synthetic workflow tests are never empirical prediction evidence."""

import hashlib
from copy import deepcopy
from datetime import datetime

import pytest
from pydantic import ValidationError

from fatebridge.validation.jyotish_study import (
    BlindProtocol,
    register,
    reveal_and_evaluate,
    seal_forecasts,
)
from fatebridge.validation.predictions import Forecast, Outcome

MODEL = b"frozen synthetic probability policy; not a real prediction model"
MODEL_SHA = hashlib.sha256(MODEL).hexdigest()
ARTIFACTS = {"rules": b"synthetic rules", "source": b"synthetic source"}
AT = datetime.fromisoformat("2026-11-01T00:00:00+00:00")
ISSUED = datetime.fromisoformat("2026-12-01T00:00:00+00:00")
AFTER = datetime.fromisoformat("2028-02-01T00:00:00+00:00")


def protocol(**updates):
    body = {
        "plan": {
            "study_id": "synthetic-workflow-test",
            "data_kind": "synthetic",
            "preregistered_at": "2026-10-22T00:00:00Z",
            "window_start": "2027-01-01T00:00:00Z",
            "window_end": "2028-01-01T00:00:00Z",
            "target_definition": "Fictional binary event; no real subject",
            "model_sha256": MODEL_SHA,
            "baseline_probability": 0.5,
            "minimum_evaluable": 2,
            "cohort": [
                {"case_id": str(i), "subject_id": f"held-out-fictional-{i}"}
                for i in range(2)
            ],
        },
        "training_subject_ids": ["training-fictional-0"],
        "baseline_derivation": "constant synthetic fixture only",
        "outcome_adjudication": "synthetic labels; no human outcome assessment",
        "recruitment_and_exclusions": "two fictional test rows",
        "probability_mapping": "explicit frozen synthetic probabilities, no astrological scores",
        "artifact_sha256": {
            key: hashlib.sha256(content).hexdigest()
            for key, content in ARTIFACTS.items()
        },
        "sample_size_justification": "Two rows exercise code only; no power or efficacy claim",
        "analysis_plan": "Synthetic Brier metric; missing and abstained cases stay in coverage",
    }
    return BlindProtocol.model_validate({**body, **updates})


def forecasts():
    return [
        Forecast(
            case_id=str(i),
            issued_at=ISSUED,
            model_sha256=MODEL_SHA,
            evidence_sha256="c" * 64,
            probability=0.8 if i == 0 else 0.2,
        )
        for i in range(2)
    ]


def outcomes():
    return [
        Outcome(
            case_id=str(i),
            occurred=i == 0,
            event_at=(
                datetime.fromisoformat("2027-06-01T00:00:00+00:00") if i == 0 else None
            ),
            recorded_at=AFTER,
            source_sha256="d" * 64,
            source_reference="synthetic test",
        )
        for i in range(2)
    ]


def test_full_commit_seal_reveal_preserves_metrics_and_no_authority_claim():
    reg = register(protocol(), MODEL, at=AT, artifacts=ARTIFACTS)
    sealed = seal_forecasts(reg, forecasts(), at=ISSUED)
    report = reveal_and_evaluate(reg, sealed, outcomes(), at=AFTER)
    assert report["metrics"]["brier_score"] == pytest.approx(0.04)
    assert report["coverage"] == 1
    assert report["forecast_commitment_sha256"] == sealed["forecast_commitment_sha256"]
    assert report["real_world_efficacy"] == "not_established_by_synthetic_data"
    assert not report["authority_certified"]


def test_no_real_outcomes_remains_unassessed_with_all_pending_rows():
    reg = register(protocol(), MODEL, at=AT, artifacts=ARTIFACTS)
    report = reveal_and_evaluate(
        reg, seal_forecasts(reg, forecasts(), at=ISSUED), [], at=AFTER
    )
    assert report["metrics"]["accuracy"] is None
    assert report["real_world_efficacy"] == "not_tested"
    assert report["coverage"] == 0


def test_training_cohort_overlap_is_rejected():
    with pytest.raises(ValidationError, match="重叠"):
        protocol(training_subject_ids=["held-out-fictional-0"])


def test_wrong_actual_model_file_is_rejected():
    with pytest.raises(ValueError, match="模型文件"):
        register(protocol(), MODEL + b"changed", at=AT, artifacts=ARTIFACTS)


def test_artifact_hashes_are_verified_against_actual_bytes():
    with pytest.raises(ValueError, match="实际规则"):
        register(
            protocol(),
            MODEL,
            at=AT,
            artifacts={"rules": b"changed", "source": ARTIFACTS["source"]},
        )
    with pytest.raises(ValueError, match="实际规则"):
        register(protocol(), MODEL, at=AT, artifacts={})


def test_registration_and_forecast_tampering_are_rejected():
    reg = register(protocol(), MODEL, at=AT, artifacts=ARTIFACTS)
    sealed = seal_forecasts(reg, forecasts(), at=ISSUED)
    changed = deepcopy(reg)
    changed["protocol"]["plan"]["baseline_probability"] = 0.9
    with pytest.raises(ValueError, match="已改变"):
        seal_forecasts(changed, forecasts(), at=ISSUED)
    changed = deepcopy(sealed)
    changed["forecasts"][0]["probability"] = 1.0
    with pytest.raises(ValueError, match="已改变"):
        reveal_and_evaluate(reg, changed, outcomes(), at=AFTER)


def test_incomplete_forecasts_cannot_be_sealed_but_explicit_abstention_can():
    reg = register(protocol(), MODEL, at=AT, artifacts=ARTIFACTS)
    fs = forecasts()
    with pytest.raises(ValueError, match="完整注册队列"):
        seal_forecasts(reg, fs[:1], at=ISSUED)
    fs[1].probability = None
    report = reveal_and_evaluate(
        reg, seal_forecasts(reg, fs, at=ISSUED), outcomes(), at=AFTER
    )
    assert report["coverage"] == 0.5
    assert not report["preregistered_performance_gate_met"]


def test_late_seal_and_early_reveal_are_rejected():
    reg = register(protocol(), MODEL, at=AT, artifacts=ARTIFACTS)
    with pytest.raises(ValueError):
        seal_forecasts(reg, forecasts(), at=AFTER)
    sealed = seal_forecasts(reg, forecasts(), at=ISSUED)
    with pytest.raises(ValueError, match="尚未结束"):
        reveal_and_evaluate(reg, sealed, outcomes(), at=ISSUED)


def test_real_cli_creates_distinct_commitments_and_refuses_overwrite_or_early_reveal(
    tmp_path, monkeypatch, capsys
):
    import importlib.util
    import json
    import sys
    from datetime import timedelta, timezone
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "jyotish_study_cli",
        Path(__file__).resolve().parents[2] / "scripts/jyotish/jyotish_blind_study.py",
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    now = datetime.now(timezone.utc)
    p = protocol().model_dump(mode="json")
    binding_artifacts = {
        name: f"synthetic {name}".encode()
        for name in (
            "calendar_rules",
            "classical_sources",
            "interpretation_policy",
            "forecast_policy",
        )
    }
    p["artifact_sha256"] = {
        name: hashlib.sha256(data).hexdigest()
        for name, data in binding_artifacts.items()
    }
    p["plan"].update(
        preregistered_at=(now - timedelta(minutes=1)).isoformat(),
        window_start=(now + timedelta(days=10)).isoformat(),
        window_end=(now + timedelta(days=20)).isoformat(),
        baseline_frozen_at=(now - timedelta(minutes=2)).isoformat(),
        training_subject_ids=p["training_subject_ids"],
        interpretation_policy_sha256=p["artifact_sha256"]["interpretation_policy"],
    )
    (tmp_path / "protocol.json").write_text(json.dumps(p))
    (tmp_path / "model.bin").write_bytes(MODEL)
    for name, data in binding_artifacts.items():
        (tmp_path / name).write_bytes(data)
    args = [
        "register",
        "--protocol",
        str(tmp_path / "protocol.json"),
        "--model",
        str(tmp_path / "model.bin"),
        "--output",
        str(tmp_path / "registration.json"),
    ]
    for name in binding_artifacts:
        args += ["--artifact", f"{name}={tmp_path / name}"]
    monkeypatch.setattr(sys, "argv", ["jyotish_blind_study.py", *args])
    cli.main()
    with pytest.raises(FileExistsError):
        cli.main()
    evidence = {str(i): f"synthetic evidence {i}".encode() for i in range(2)}
    for name, data in evidence.items():
        (tmp_path / f"evidence-{name}").write_bytes(data)
    fs = [
        f.model_copy(
            update={
                "issued_at": datetime.now(timezone.utc),
                "interpretation_policy_sha256": p["plan"][
                    "interpretation_policy_sha256"
                ],
                "evidence_sha256": hashlib.sha256(evidence[f.case_id]).hexdigest(),
            }
        ).model_dump(mode="json")
        for f in forecasts()
    ]
    (tmp_path / "forecasts.json").write_text(json.dumps(fs))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "jyotish_blind_study.py",
            "seal",
            "--registration",
            str(tmp_path / "registration.json"),
            "--forecasts",
            str(tmp_path / "forecasts.json"),
            "--output",
            str(tmp_path / "sealed.json"),
            "--evidence",
            f"0={tmp_path / 'evidence-0'}",
            "--evidence",
            f"1={tmp_path / 'evidence-1'}",
        ],
    )
    cli.main()
    (tmp_path / "outcomes.json").write_text("[]")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "jyotish_blind_study.py",
            "evaluate",
            "--registration",
            str(tmp_path / "registration.json"),
            "--sealed",
            str(tmp_path / "sealed.json"),
            "--outcomes",
            str(tmp_path / "outcomes.json"),
            "--output",
            str(tmp_path / "report.json"),
        ],
    )
    with pytest.raises(ValueError, match="尚未结束"):
        cli.main()
    assert not (tmp_path / "report.json").exists()
    assert "authority_certified" in capsys.readouterr().out
