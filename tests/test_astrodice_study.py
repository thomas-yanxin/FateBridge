"""Synthetic adversarial workflow tests, never real-world efficacy evidence."""

import importlib.util
import json
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.astrodice import METHOD_ID, PLANETS
from fatebridge.core.astrology_tables import SIGNS
from fatebridge.validation.astrodice_study import (
    DiceObservation,
    FrozenDicePolicy,
    audit_study,
    engine_fingerprint,
    make_forecasts,
    policy_fingerprint,
)
from fatebridge.validation.predictions import Outcome, StudyPlan

ISSUED = datetime(2027, 1, 2, tzinfo=timezone.utc)
AS_OF = datetime(2027, 3, 1, tzinfo=timezone.utc)


@pytest.fixture
def study():
    cells = {f"{p}|{s}|{h}": 0.2 for p, s, h in product(PLANETS, SIGNS, range(12))}
    cells["Mercury|Virgo|0"] = 0.8
    policy = FrozenDicePolicy(
        policy_id="synthetic-test-only",
        method_id=METHOD_ID,
        symbolic_engine_sha256=engine_fingerprint(),
        target_definition="Synthetic event within the registered window",
        probabilities=cells,
    )
    plan = StudyPlan(
        study_id="synthetic-dice",
        data_kind="synthetic",
        preregistered_at="2027-01-01T00:00:00Z",
        window_start="2027-01-03T00:00:00Z",
        window_end="2027-02-01T00:00:00Z",
        target_definition=policy.target_definition,
        model_sha256=policy_fingerprint(policy),
        baseline_probability=0.5,
        minimum_evaluable=2,
        training_subject_ids=[],
        cohort=[{"case_id": str(i), "subject_id": f"synthetic-{i}"} for i in range(2)],
    )
    records = [
        DiceObservation(
            case_id=str(i),
            subject_id=f"synthetic-{i}",
            recorded_at="2027-01-01T12:00:00Z",
            roll={"planet": "Mercury", "sign": "Virgo", "house": i},
            physical_record_sha256=str(i) * 64,
            physical_record_reference=f"synthetic row {i}",
        )
        for i in range(2)
    ]
    forecasts = make_forecasts(plan, policy, records, at=ISSUED)
    outcomes = [
        Outcome(
            case_id=str(i),
            occurred=i == 0,
            event_at="2027-01-10T00:00:00Z" if i == 0 else None,
            recorded_at="2027-02-02T00:00:00Z",
            source_sha256="a" * 64,
            source_reference="synthetic outcome",
        )
        for i in range(2)
    ]
    return plan, policy, records, forecasts, outcomes


def test_dice_evidence_and_metrics_are_recomputed_but_not_certified(study):
    plan, policy, records, forecasts, outcomes = study
    report = audit_study(plan, policy, records, forecasts, outcomes, as_of=AS_OF)
    assert report["metrics"]["brier_score"] == pytest.approx(0.04)
    assert report["metrics"]["brier_skill_score"] == pytest.approx(0.84)
    assert report["metrics"]["accuracy"] == 1
    assert report["metrics"]["accuracy_interval"][0] < 0.35
    assert report["coverage"] == 1
    assert (
        report["dice_evidence_binding"]
        == "all_registered_rolls_and_policy_outputs_recomputed"
    )
    assert report["real_world_efficacy"] == "not_established_by_synthetic_data"
    assert (
        not report["authority_certified"]
        and not report["universal_perfect_prediction_established"]
    )


@pytest.mark.parametrize(
    "change",
    [
        {"probability": 0.9},
        {"probability": None},
        {"evidence_sha256": "f" * 64},
        {"issued_at": datetime(2027, 1, 1, tzinfo=timezone.utc)},
    ],
)
def test_hindsight_probability_abstention_hash_and_late_roll_are_rejected(
    study, change
):
    plan, policy, records, forecasts, outcomes = study
    forecasts[0] = forecasts[0].model_copy(update=change)
    with pytest.raises(ValueError):
        audit_study(plan, policy, records, forecasts, outcomes, as_of=AS_OF)


@pytest.mark.parametrize(
    "change",
    [
        {"subject_id": "someone-else"},
        {"physical_record_sha256": "f" * 64},
        {"recorded_at": datetime(2027, 1, 4, tzinfo=timezone.utc)},
    ],
)
def test_changed_identity_physical_evidence_and_outcome_window_records_are_rejected(
    study, change
):
    plan, policy, records, forecasts, outcomes = study
    records[0] = records[0].model_copy(update=change)
    with pytest.raises(ValueError):
        audit_study(plan, policy, records, forecasts, outcomes, as_of=AS_OF)


def test_changed_roll_is_rejected_even_if_probability_is_unchanged(study):
    plan, policy, records, forecasts, outcomes = study
    changed = records[1].model_dump(mode="json")
    changed["roll"]["house"] = 2  # Both policy cells are 0.2.
    records[1] = DiceObservation.model_validate(changed)
    with pytest.raises(ValueError, match="绑定"):
        audit_study(plan, policy, records, forecasts, outcomes, as_of=AS_OF)


@pytest.mark.parametrize("which", ["observations", "forecasts"])
@pytest.mark.parametrize("operation", ["drop", "duplicate", "add"])
def test_no_subset_selection_or_duplicated_cases(study, which, operation):
    plan, policy, records, forecasts, outcomes = study
    rows = records if which == "observations" else forecasts
    if operation == "drop":
        rows.pop()
    elif operation == "duplicate":
        rows.append(rows[0])
    else:
        rows.append(rows[0].model_copy(update={"case_id": "unregistered"}))
    with pytest.raises(ValueError):
        audit_study(plan, policy, records, forecasts, outcomes, as_of=AS_OF)


@pytest.mark.parametrize(
    "field,value",
    [
        ("method_id", "different-engine"),
        ("symbolic_engine_sha256", "f" * 64),
        ("target_definition", "A redefined success event"),
    ],
)
def test_version_code_and_event_definition_cannot_drift(study, field, value):
    plan, policy, records, forecasts, outcomes = study
    policy = policy.model_copy(update={field: value})
    with pytest.raises(ValueError):
        audit_study(plan, policy, records, forecasts, outcomes, as_of=AS_OF)


def test_policy_must_cover_full_space_without_defaults(study):
    _, policy, *_ = study
    data = policy.model_dump(mode="json")
    data["probabilities"].pop("Mercury|Virgo|0")
    with pytest.raises(ValidationError):
        FrozenDicePolicy.model_validate(data)
    data["probabilities"]["Mercury|Virgo|12"] = 0.8
    with pytest.raises(ValidationError):
        FrozenDicePolicy.model_validate(data)


def test_reordered_json_has_same_semantic_policy_commitment(study):
    _, policy, *_ = study
    data = policy.model_dump(mode="json")
    data["probabilities"] = dict(reversed(list(data["probabilities"].items())))
    assert policy_fingerprint(
        FrozenDicePolicy.model_validate(data)
    ) == policy_fingerprint(policy)


def test_missing_outcome_and_abstention_remain_in_registered_denominator(study):
    plan, policy, records, forecasts, outcomes = study
    policy.probabilities["Mercury|Virgo|1"] = None
    plan.model_sha256 = policy_fingerprint(policy)
    forecasts = make_forecasts(plan, policy, records, at=ISSUED)
    report = audit_study(plan, policy, records, forecasts, outcomes, as_of=AS_OF)
    assert report["coverage"] == 0.5 and report["registered_count"] == 2
    assert report["rows"][1]["status"] == "abstained"
    assert not report["preregistered_performance_gate_met"]
    report = audit_study(plan, policy, records, forecasts, outcomes[:1], as_of=AS_OF)
    assert report["rows"][1]["status"] == "outcome_pending"


def test_cli_writes_auditable_files_without_overwriting(
    study, tmp_path, monkeypatch, capsys
):
    plan, policy, records, _, outcomes = study
    script = Path(__file__).resolve().parents[1] / "scripts/audit_astrodice_study.py"
    spec = importlib.util.spec_from_file_location("dice_study_cli", script)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    for name, value in {
        "plan": plan.model_dump(mode="json"),
        "policy": policy.model_dump(mode="json"),
        "observations": [r.model_dump(mode="json") for r in records],
        "outcomes": [o.model_dump(mode="json") for o in outcomes],
    }.items():
        (tmp_path / f"{name}.json").write_text(json.dumps(value))
    flags = [
        flag
        for name in ("plan", "policy", "observations")
        for flag in ("--" + name, str(tmp_path / f"{name}.json"))
    ]
    forecasts = tmp_path / "forecasts.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            str(script),
            "forecast",
            *flags,
            "--at",
            ISSUED.isoformat(),
            "--output",
            str(forecasts),
        ],
    )
    assert cli.main() == 0
    with pytest.raises(FileExistsError):
        cli.main()
    report = tmp_path / "report.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            str(script),
            "audit",
            *flags,
            "--at",
            AS_OF.isoformat(),
            "--forecasts",
            str(forecasts),
            "--outcomes",
            str(tmp_path / "outcomes.json"),
            "--output",
            str(report),
        ],
    )
    assert cli.main() == 0
    assert json.loads(report.read_text())["metrics"]["brier_score"] == pytest.approx(
        0.04
    )
    assert not json.loads(capsys.readouterr().out.splitlines()[-1])[
        "predictive_validity_certified"
    ]
