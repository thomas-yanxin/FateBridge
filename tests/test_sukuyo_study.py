"""Prospective workflow tests; synthetic cases are never efficacy evidence."""

import hashlib
import json
import subprocess
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.validation.predictions import Forecast, Outcome, digest
from fatebridge.validation.sukuyo_study import (
    REQUIRED_ARTIFACTS,
    SukuyoProtocol,
    blind_outcome_sheet,
    evaluate,
    protocol_context_digest,
    read_registration,
    register,
    seal_forecasts,
)

MODEL = b"synthetic test model; not an astrological probability mapping"
MODEL_HASH = hashlib.sha256(MODEL).hexdigest()
ARTIFACTS = {name: ("synthetic actual " + name).encode() for name in REQUIRED_ARTIFACTS}
EVIDENCE = {str(i): f"synthetic calculation evidence {i}".encode() for i in range(2)}
OUTCOME_SOURCES = {str(i): f"synthetic outcome record {i}".encode() for i in range(2)}
REGISTER_AT = datetime(2027, 1, 2, tzinfo=timezone.utc)
SEAL_AT = datetime(2027, 1, 3, tzinfo=timezone.utc)
EVALUATE_AT = datetime(2028, 2, 2, tzinfo=timezone.utc)


def protocol(**changes):
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


def forecasts():
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


def outcomes():
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


def registered():
    return register(protocol(), MODEL, at=REGISTER_AT, artifacts=ARTIFACTS)


def test_registered_sealed_and_revealed_pipeline_preserves_synthetic_boundary():
    reg = registered()
    sealed = seal_forecasts(reg, forecasts(), at=SEAL_AT, evidence=EVIDENCE)
    report = evaluate(
        reg, sealed, outcomes(), at=EVALUATE_AT, outcome_sources=OUTCOME_SOURCES
    )
    assert report["pair_count"] == 2 and report["independent_participant_count"] == 4
    assert report["metrics"]["accuracy"] == 1.0
    assert report["metrics"]["brier_score"] == pytest.approx(0.01)
    assert report["real_world_efficacy"] == "not_established_by_synthetic_data"
    assert not report["authority_certified"]
    assert report["paired_brier_gain_interval"] == [-1.0, 1.0]
    assert not report["confidence_bound_gate_met"]


def test_one_subject_cannot_inflate_sample_count_through_several_pairs():
    pairs = protocol().model_dump(mode="json")["pairs"]
    pairs[1]["person1_subject_id"] = pairs[0]["person2_subject_id"]
    with pytest.raises(ValidationError, match="同一人"):
        protocol(pairs=pairs)


def test_fixed_sample_study_refuses_unadjusted_repeated_looks():
    values = protocol().model_dump(mode="json")
    values["blind_protocol"]["plan"]["planned_evaluations"] = 2
    with pytest.raises(ValidationError, match="一次到期评价"):
        SukuyoProtocol.model_validate(values)


def test_pair_participants_are_checked_against_training_not_just_pair_ids():
    data = protocol().model_dump(mode="json")
    data["blind_protocol"]["training_subject_ids"] = ["fictional-0-a"]
    data["blind_protocol"]["plan"]["training_subject_ids"] = ["fictional-0-a"]
    with pytest.raises(ValidationError, match="训练主体"):
        SukuyoProtocol.model_validate(data)


def test_actual_source_files_are_required_at_registration():
    with pytest.raises(ValueError, match="实际规则"):
        register(
            protocol(),
            MODEL,
            at=REGISTER_AT,
            artifacts={**ARTIFACTS, "forecast_policy": b"changed"},
        )
    data = protocol().model_dump(mode="json")
    data["blind_protocol"]["artifact_sha256"].pop("classical_sources")
    with pytest.raises(ValidationError, match="四类实际文件"):
        SukuyoProtocol.model_validate(data)


def test_pair_list_cannot_be_replaced_after_registration():
    reg = registered()
    reg["protocol"]["pairs"][0]["person1_subject_id"] = "replacement"
    with pytest.raises(ValueError, match="注册文件已改变"):
        read_registration(reg)


def test_declared_interpretation_cannot_differ_from_the_actual_frozen_artifact():
    data = protocol().model_dump(mode="json")
    data["blind_protocol"]["plan"]["interpretation_policy_sha256"] = hashlib.sha256(
        b"a different interpretation policy, absent from the submitted files"
    ).hexdigest()
    with pytest.raises(ValidationError, match="实际interpretation_policy文件"):
        SukuyoProtocol.model_validate(data)


def test_actual_interpretation_is_bound_through_registration_forecast_and_reveal():
    data = protocol().model_dump(mode="json")
    policy_sha = hashlib.sha256(ARTIFACTS["interpretation_policy"]).hexdigest()
    data["blind_protocol"]["plan"].update(
        interpretation_policy_sha256=policy_sha,
        baseline_frozen_at="2026-12-31T00:00:00Z",
        registration_reference="synthetic registration receipt; not an actual registry",
    )
    data["blind_protocol"]["plan"]["protocol_context_sha256"] = protocol_context_digest(
        SukuyoProtocol.model_validate(data)
    )
    reg = register(
        SukuyoProtocol.model_validate(data), MODEL, at=REGISTER_AT, artifacts=ARTIFACTS
    )
    # Even valid probabilities and evidence cannot substitute another policy.
    with pytest.raises(ValueError, match="解释政策"):
        seal_forecasts(reg, forecasts(), at=SEAL_AT, evidence=EVIDENCE)
    fixed_forecasts = [
        Forecast.model_validate(
            {
                **f.model_dump(mode="json"),
                "interpretation_policy_sha256": policy_sha,
                "study_plan_sha256": digest(data["blind_protocol"]["plan"]),
            }
        )
        for f in forecasts()
    ]
    sealed = seal_forecasts(reg, fixed_forecasts, at=SEAL_AT, evidence=EVIDENCE)
    report = evaluate(
        reg,
        sealed,
        [
            o.model_copy(
                update={"study_plan_sha256": digest(data["blind_protocol"]["plan"])}
            )
            for o in outcomes()
        ],
        at=EVALUATE_AT,
        outcome_sources=OUTCOME_SOURCES,
    )
    assert report["preregistered_performance_gate_met"]
    assert report["real_world_efficacy"] == "not_established_by_synthetic_data"
    assert not report["authority_certified"]


def test_even_rehashed_pair_scheme_cannot_reuse_old_forecast_commitment():
    reg = registered()
    sealed = seal_forecasts(reg, forecasts(), at=SEAL_AT, evidence=EVIDENCE)
    changed = deepcopy(reg)
    changed["protocol"]["pairs"][0]["person1_subject_id"] = "replacement"
    changed["registration_sha256"] = digest(
        {k: v for k, v in changed.items() if k != "registration_sha256"}
    )
    with pytest.raises(ValueError, match="注册方案不一致"):
        evaluate(
            changed, sealed, outcomes(), at=EVALUATE_AT, outcome_sources=OUTCOME_SOURCES
        )


def test_early_issuance_reveal_duplicate_or_omitted_predictions_fail():
    reg = registered()
    with pytest.raises(ValueError):
        seal_forecasts(reg, forecasts()[:1], at=SEAL_AT, evidence=EVIDENCE)
    with pytest.raises(ValueError):
        seal_forecasts(reg, [forecasts()[0]] * 2, at=SEAL_AT, evidence=EVIDENCE)
    with pytest.raises(ValueError):
        seal_forecasts(
            reg,
            forecasts(),
            at=datetime(2027, 2, 1, tzinfo=timezone.utc),
            evidence=EVIDENCE,
        )
    sealed = seal_forecasts(reg, forecasts(), at=SEAL_AT, evidence=EVIDENCE)
    with pytest.raises(ValueError, match="尚未结束"):
        evaluate(reg, sealed, [], at=SEAL_AT, outcome_sources={})


def test_missing_observation_is_not_dropped_from_registered_coverage():
    reg = registered()
    sealed = seal_forecasts(reg, forecasts(), at=SEAL_AT, evidence=EVIDENCE)
    report = evaluate(
        reg,
        sealed,
        outcomes()[:1],
        at=EVALUATE_AT,
        outcome_sources={"0": OUTCOME_SOURCES["0"]},
    )
    assert (
        report["coverage"] == 0.5 and not report["preregistered_performance_gate_met"]
    )
    assert report["paired_brier_gain_interval"] is None


def test_fingerprints_require_actual_forecast_and_outcome_evidence():
    reg = registered()
    with pytest.raises(ValueError, match="实际计算"):
        seal_forecasts(reg, forecasts(), at=SEAL_AT, evidence={})
    with pytest.raises(ValueError, match="实际计算"):
        seal_forecasts(
            reg, forecasts(), at=SEAL_AT, evidence={**EVIDENCE, "0": b"changed"}
        )
    sealed = seal_forecasts(reg, forecasts(), at=SEAL_AT, evidence=EVIDENCE)
    with pytest.raises(ValueError, match="实际来源"):
        evaluate(reg, sealed, outcomes(), at=EVALUATE_AT, outcome_sources={})
    with pytest.raises(ValueError, match="实际来源"):
        evaluate(
            reg,
            sealed,
            outcomes(),
            at=EVALUATE_AT,
            outcome_sources={**OUTCOME_SOURCES, "1": b"changed"},
        )


def test_adjudicator_sheet_excludes_births_pair_labels_and_predictions():
    registration = registered()
    sheet = blind_outcome_sheet(registration)
    assert sheet["case_ids"] == ["0", "1"]
    assert set(sheet) == {
        "format",
        "study_id",
        "study_plan_sha256",
        "protocol_context_sha256",
        "target_definition",
        "window_start",
        "window_end",
        "case_ids",
        "adjudication",
        "scope",
    }
    assert "fictional-0-a" not in json.dumps(sheet)
    assert sheet["study_plan_sha256"] == digest(
        read_registration(registration).blind_protocol.plan.model_dump(mode="json")
    )


def test_draft_cli_has_no_real_subjects_and_cannot_overwrite_a_commitment(tmp_path):
    root = Path(__file__).resolve().parents[1]
    import sys

    output = tmp_path / "draft.json"
    command = [
        sys.executable,
        str(root / "scripts/sukuyo_blind_study.py"),
        "draft",
        "--output",
        str(output),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    report = json.loads(output.read_text())
    assert report["status"] == "draft_not_registered"
    assert report["real_world_sample_count"] == 0 and not report["authority_certified"]
    assert subprocess.run(command, capture_output=True).returncode != 0


def test_cli_register_seal_blind_sheet_and_evaluate_share_frozen_files(
    monkeypatch, tmp_path, capsys
):
    import importlib.util
    import sys

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "sukuyo_cli", root / "scripts/sukuyo_blind_study.py"
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)

    class Clock(datetime):
        instant = REGISTER_AT

        @classmethod
        def now(cls, tz=None):
            return cls.instant

    monkeypatch.setattr(cli, "datetime", Clock)

    def write(name, value):
        p = tmp_path / name
        p.write_text(json.dumps(value))
        return str(p)

    def call(action, *args):
        monkeypatch.setattr(
            sys, "argv", ["sukuyo_blind_study", action, *map(str, args)]
        )
        cli.main()
        capsys.readouterr()

    model = tmp_path / "model"
    model.write_bytes(MODEL)
    artifact_args = []
    for name, raw in ARTIFACTS.items():
        p = tmp_path / name
        p.write_bytes(raw)
        artifact_args += ["--artifact", f"{name}={p}"]
    registration = tmp_path / "registration.json"
    call(
        "register",
        "--protocol",
        write("protocol.json", protocol().model_dump(mode="json")),
        "--model",
        model,
        *artifact_args,
        "--output",
        registration,
    )
    Clock.instant = SEAL_AT
    sealed = tmp_path / "sealed.json"
    evidence_args = []
    outcome_args = []
    for option, data, args_list in (
        ("--evidence", EVIDENCE, evidence_args),
        ("--outcome-source", OUTCOME_SOURCES, outcome_args),
    ):
        for case, raw in data.items():
            path = tmp_path / (option + case)
            path.write_bytes(raw)
            args_list += [option, f"{case}={path}"]
    call(
        "seal",
        "--registration",
        registration,
        "--forecasts",
        write("forecasts.json", [f.model_dump(mode="json") for f in forecasts()]),
        *evidence_args,
        "--output",
        sealed,
    )
    sheet = tmp_path / "blind.json"
    call("blind-sheet", "--registration", registration, "--output", sheet)
    assert "forecasts" not in json.loads(sheet.read_text())
    Clock.instant = EVALUATE_AT
    report = tmp_path / "report.json"
    call(
        "evaluate",
        "--registration",
        registration,
        "--sealed",
        sealed,
        "--outcomes",
        write("outcomes.json", [o.model_dump(mode="json") for o in outcomes()]),
        *outcome_args,
        "--output",
        report,
    )
    assert (
        json.loads(report.read_text())["real_world_efficacy"]
        == "not_established_by_synthetic_data"
    )
