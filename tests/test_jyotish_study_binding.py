"""Adversarial synthetic commitments; none are real forecasts or observations."""

import hashlib
import importlib.util
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.validation import jyotish_study as primitive
from fatebridge.validation.jyotish_study_binding import (
    REQUIRED_ARTIFACTS,
    JyotishProtocol,
    blind_outcome_sheet,
    read_registration,
    register,
    reveal_and_evaluate,
    seal_forecasts,
)
from fatebridge.validation.predictions import Forecast, Outcome, digest

MODEL = b"synthetic frozen policy; no claimed forecasting ability"
ARTIFACTS = {name: f"synthetic {name}".encode() for name in REQUIRED_ARTIFACTS}
EVIDENCE = {str(i): f"synthetic original calculation {i}".encode() for i in range(2)}
SOURCES = {str(i): f"synthetic original observation {i}".encode() for i in range(2)}
REGISTERED = datetime(2027, 1, 2, tzinfo=timezone.utc)
ISSUED = datetime(2027, 1, 3, tzinfo=timezone.utc)
AFTER = datetime(2028, 2, 2, tzinfo=timezone.utc)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def protocol_data():
    return {
        "plan": {
            "study_id": "synthetic-binding-test",
            "data_kind": "synthetic",
            "preregistered_at": "2027-01-01T00:00:00Z",
            "registration_reference": "synthetic:external-registration-not-actually-made",
            "window_start": "2027-02-01T00:00:00Z",
            "window_end": "2028-02-01T00:00:00Z",
            "target_definition": "Synthetic binary event only",
            "model_sha256": sha(MODEL),
            "interpretation_policy_sha256": sha(ARTIFACTS["interpretation_policy"]),
            "baseline_probability": 0.5,
            "baseline_frozen_at": "2026-12-31T00:00:00Z",
            "training_subject_ids": ["synthetic-training-person"],
            "minimum_evaluable": 2,
            "cohort": [
                {"case_id": str(i), "subject_id": f"synthetic-held-out-person-{i}"}
                for i in range(2)
            ],
        },
        "training_subject_ids": ["synthetic-training-person"],
        "baseline_derivation": "Frozen synthetic reference, not calibrated event data",
        "outcome_adjudication": "Synthetic test labels with full follow-up",
        "recruitment_and_exclusions": "Two complete fictional rows",
        "probability_mapping": "Synthetic test probabilities, not strength scores",
        "sample_size_justification": "Two rows for code checks, not efficacy",
        "analysis_plan": "Frozen Brier endpoint, retain missing rows",
        "artifact_sha256": {name: sha(data) for name, data in ARTIFACTS.items()},
    }


def protocol():
    return JyotishProtocol.model_validate(protocol_data())


def registered():
    return register(protocol(), MODEL, at=REGISTERED, artifacts=ARTIFACTS)


def test_schema_declares_required_plan_fields_and_named_materials():
    from jsonschema import Draft202012Validator

    schema = JyotishProtocol.model_json_schema()
    validator = Draft202012Validator(schema)
    validator.validate(protocol_data())
    for field in (
        "interpretation_policy_sha256",
        "baseline_frozen_at",
        "training_subject_ids",
    ):
        data = protocol_data()
        data["plan"].pop(field)
        assert list(validator.iter_errors(data)), field
    data = protocol_data()
    data["artifact_sha256"].pop("classical_sources")
    data["artifact_sha256"]["unrelated_material"] = "a" * 64
    assert list(validator.iter_errors(data))


def forecasts():
    return [
        Forecast(
            case_id=str(i),
            issued_at=ISSUED,
            model_sha256=sha(MODEL),
            interpretation_policy_sha256=sha(ARTIFACTS["interpretation_policy"]),
            evidence_sha256=sha(EVIDENCE[str(i)]),
            probability=p,
        )
        for i, p in enumerate([0.9, 0.1])
    ]


def outcomes():
    return [
        Outcome(
            case_id=str(i),
            occurred=not bool(i),
            event_at="2027-07-01T00:00:00Z" if i == 0 else None,
            recorded_at=AFTER,
            source_sha256=sha(SOURCES[str(i)]),
            source_reference="synthetic fixture only",
        )
        for i in range(2)
    ]


@pytest.mark.parametrize(
    "change",
    [
        "missing_training",
        "different_training",
        "duplicate_training",
        "missing_baseline",
        "missing_policy",
        "different_policy",
        "missing_artifact",
    ],
)
def test_strict_protocol_rejects_unbound_or_conflicting_declarations(change):
    data = protocol_data()
    if change == "missing_training":
        data["plan"].pop("training_subject_ids")
    elif change == "different_training":
        data["plan"]["training_subject_ids"] = ["another-synthetic-training-person"]
    elif change == "duplicate_training":
        data["plan"]["training_subject_ids"] *= 2
    elif change == "missing_baseline":
        data["plan"].pop("baseline_frozen_at")
    elif change == "missing_policy":
        data["plan"].pop("interpretation_policy_sha256")
    elif change == "different_policy":
        data["plan"]["interpretation_policy_sha256"] = "f" * 64
    else:
        data["artifact_sha256"].pop("classical_sources")
    with pytest.raises(ValidationError):
        JyotishProtocol.model_validate(data)


def test_registration_requires_actual_policy_bytes_and_revalidates_mutated_models():
    with pytest.raises(ValueError, match="实际规则"):
        register(
            protocol(),
            MODEL,
            at=REGISTERED,
            artifacts={**ARTIFACTS, "interpretation_policy": b"changed"},
        )
    mutated = protocol()
    mutated.plan.training_subject_ids = ["different-training"]
    with pytest.raises(ValidationError, match="一致"):
        register(mutated, MODEL, at=REGISTERED, artifacts=ARTIFACTS)


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"0": EVIDENCE["0"]},
        {**EVIDENCE, "0": EVIDENCE["1"]},
        {**EVIDENCE, "extra": b"unregistered"},
    ],
)
def test_all_forecast_materials_must_match_exact_case_bytes(bad):
    with pytest.raises(ValueError, match="实际文件"):
        seal_forecasts(registered(), forecasts(), at=ISSUED, evidence=bad)


def test_abstention_requires_material_and_never_acquires_full_coverage():
    reg = registered()
    fs = forecasts()
    fs[1].probability = None
    with pytest.raises(ValueError, match="弃权"):
        seal_forecasts(reg, fs, at=ISSUED, evidence={"0": EVIDENCE["0"]})
    sealed = seal_forecasts(reg, fs, at=ISSUED, evidence=EVIDENCE)
    report = reveal_and_evaluate(
        reg, sealed, outcomes(), at=AFTER, outcome_sources=SOURCES
    )
    assert report["coverage"] == 0.5
    assert not report["preregistered_performance_gate_met"]


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"0": SOURCES["0"]},
        {**SOURCES, "0": SOURCES["1"]},
        {**SOURCES, "extra": b"unregistered"},
    ],
)
def test_every_submitted_outcome_requires_exact_source_bytes(bad):
    reg = registered()
    sealed = seal_forecasts(reg, forecasts(), at=ISSUED, evidence=EVIDENCE)
    with pytest.raises(ValueError, match="结局来源"):
        reveal_and_evaluate(reg, sealed, outcomes(), at=AFTER, outcome_sources=bad)


def test_missing_follow_up_is_retained_without_inventing_sources_or_negative_labels():
    reg = registered()
    sealed = seal_forecasts(reg, forecasts(), at=ISSUED, evidence=EVIDENCE)
    report = reveal_and_evaluate(
        reg, sealed, outcomes()[:1], at=AFTER, outcome_sources={"0": SOURCES["0"]}
    )
    assert report["evaluable_count"] == 1 and report["registered_count"] == 2
    assert report["rows"][1]["status"] == "outcome_pending"
    assert report["material_binding"]["outcome_source_files_checked_at_evaluation"] == 1
    assert not report["statistical_evidence_gate_met"]
    empty = reveal_and_evaluate(reg, sealed, [], at=AFTER, outcome_sources={})
    assert empty["real_world_efficacy"] == "not_tested"
    assert empty["metrics"]["brier_score"] is None


def test_material_binding_preserves_hand_computed_metrics_without_certification():
    reg = registered()
    sealed = seal_forecasts(reg, forecasts(), at=ISSUED, evidence=EVIDENCE)
    report = reveal_and_evaluate(
        reg, sealed, outcomes(), at=AFTER, outcome_sources=SOURCES
    )
    assert report["metrics"]["brier_score"] == pytest.approx(0.01)
    assert report["metrics"]["baseline_brier_score"] == 0.25
    assert report["metrics"]["brier_skill_score"] == pytest.approx(0.96)
    assert report["material_binding"]["forecast_evidence_files_checked_at_seal"] == 2
    assert (
        report["external_timestamp_and_blinding"] == "requires_independent_verification"
    )
    assert not report["statistical_evidence_gate_met"]
    assert not report["authority_certified"]
    assert report["real_world_efficacy"] == "not_established_by_synthetic_data"


def test_rehashed_outer_forecast_cannot_replace_its_registered_inner_commitment():
    reg = registered()
    sealed = seal_forecasts(reg, forecasts(), at=ISSUED, evidence=EVIDENCE)
    other = protocol()
    other.plan.study_id = "another-synthetic-study"
    reg2 = register(other, MODEL, at=REGISTERED, artifacts=ARTIFACTS)
    changed = deepcopy(sealed)
    changed["registration_sha256"] = reg2["registration_sha256"]
    changed["forecast_commitment_sha256"] = digest(
        {k: v for k, v in changed.items() if k != "forecast_commitment_sha256"}
    )
    with pytest.raises(ValueError, match="不属于"):
        reveal_and_evaluate(
            reg2, changed, outcomes(), at=AFTER, outcome_sources=SOURCES
        )


def test_tampered_or_legacy_packets_are_not_upgraded_to_material_verified():
    reg = registered()
    changed = deepcopy(reg)
    changed["commitment"]["protocol"]["plan"]["baseline_probability"] = 0.8
    with pytest.raises(ValueError, match="已改变"):
        read_registration(changed)
    legacy = primitive.register(protocol(), MODEL, at=REGISTERED, artifacts=ARTIFACTS)
    with pytest.raises(ValueError, match="旧版"):
        read_registration(legacy)


def test_seal_rejects_mutation_and_uncommitted_interpretation_policy():
    reg = registered()
    fs = forecasts()
    fs[0].probability = True
    with pytest.raises(ValidationError):
        seal_forecasts(reg, fs, at=ISSUED, evidence=EVIDENCE)
    fs = forecasts()
    fs[0].interpretation_policy_sha256 = "f" * 64
    with pytest.raises(ValueError, match="政策指纹"):
        seal_forecasts(reg, fs, at=ISSUED, evidence=EVIDENCE)


def test_adjudicator_sheet_exposes_only_predeclared_outcome_task():
    registration = registered()
    sheet = blind_outcome_sheet(registration)
    assert set(sheet) == {
        "format",
        "registration_sha256",
        "study_plan_sha256",
        "study_id",
        "target_definition",
        "window_start",
        "window_end",
        "case_ids",
        "adjudication",
        "scope",
    }
    assert sheet["case_ids"] == ["0", "1"]
    assert sheet["study_plan_sha256"] == digest(
        read_registration(registration).plan.model_dump(mode="json")
    )
    assert "synthetic-held-out-person" not in json.dumps(sheet)


def test_cli_full_synthetic_flow_uses_actual_files_and_duplicate_bindings_fail(
    tmp_path, monkeypatch
):
    spec = importlib.util.spec_from_file_location(
        "jyotish_material_cli",
        Path(__file__).resolve().parents[1] / "scripts/jyotish_blind_study.py",
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)

    class SyntheticClock(datetime):
        current = REGISTERED

        @classmethod
        def now(cls, tz=None):
            return (
                cls.current.astimezone(tz) if tz else cls.current.replace(tzinfo=None)
            )

    monkeypatch.setattr(cli, "datetime", SyntheticClock)

    def write(name, value):
        path = tmp_path / name
        path.write_bytes(
            value if isinstance(value, bytes) else json.dumps(value).encode()
        )
        return str(path)

    def run(action, *args):
        monkeypatch.setattr(sys, "argv", ["jyotish_blind_study.py", action, *args])
        cli.main()

    reg_path = str(tmp_path / "registered.json")
    args = [
        "--protocol",
        write("protocol.json", protocol_data()),
        "--model",
        write("model.bin", MODEL),
        "--output",
        reg_path,
    ]
    for name, data in ARTIFACTS.items():
        args += ["--artifact", f"{name}={write(name, data)}"]
    run("register", *args)
    seal_path = str(tmp_path / "sealed.json")
    SyntheticClock.current = ISSUED
    args = [
        "--registration",
        reg_path,
        "--forecasts",
        write("forecasts.json", [f.model_dump(mode="json") for f in forecasts()]),
        "--output",
        seal_path,
    ]
    for case, data in EVIDENCE.items():
        args += ["--evidence", f"{case}={write('evidence-'+case, data)}"]
    with pytest.raises(SystemExit):
        run("seal", *args, "--evidence", f"0={tmp_path/'evidence-0'}")
    assert not Path(seal_path).exists()
    run("seal", *args)
    sheet_path = str(tmp_path / "sheet.json")
    run("blind-sheet", "--registration", reg_path, "--output", sheet_path)
    assert json.loads(Path(sheet_path).read_text())["case_ids"] == ["0", "1"]
    SyntheticClock.current = AFTER
    report_path = str(tmp_path / "report.json")
    args = [
        "--registration",
        reg_path,
        "--sealed",
        seal_path,
        "--outcomes",
        write("outcomes.json", [o.model_dump(mode="json") for o in outcomes()]),
        "--output",
        report_path,
    ]
    with pytest.raises(ValueError, match="实际文件"):
        run("evaluate", *args)
    assert not Path(report_path).exists()
    for case, data in SOURCES.items():
        args += ["--outcome-source", f"{case}={write('source-'+case, data)}"]
    run("evaluate", *args)
    report = json.loads(Path(report_path).read_text())
    assert report["evaluable_count"] == 2 and not report["authority_certified"]
    with pytest.raises(FileExistsError):
        run("evaluate", *args)
