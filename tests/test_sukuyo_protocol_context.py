"""Current paired-protocol context commitments; synthetic workflow only."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.validation.predictions import StudyPlan, digest
from fatebridge.validation.sukuyo_study import (
    SukuyoProtocol,
    blind_outcome_sheet,
    evaluate,
    protocol_context_digest,
    read_registration,
    register,
    seal_forecasts,
)
from tests.test_sukuyo_study import (
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

ROOT = Path(__file__).resolve().parents[1]


def prepared():
    raw = protocol().model_dump(mode="json")
    plan = raw["blind_protocol"]["plan"]
    plan.update(
        interpretation_policy_sha256=hashlib.sha256(
            ARTIFACTS["interpretation_policy"]
        ).hexdigest(),
        baseline_frozen_at="2026-12-31T00:00:00Z",
        registration_reference="SYNTHETIC context-binding receipt; no real registry",
    )
    plan["protocol_context_sha256"] = protocol_context_digest(
        SukuyoProtocol.model_validate(raw)
    )
    p = SukuyoProtocol.model_validate(raw)
    binding = digest(p.blind_protocol.plan.model_dump(mode="json"))
    submitted = [
        f.model_copy(
            update={
                "study_plan_sha256": binding,
                "interpretation_policy_sha256": plan["interpretation_policy_sha256"],
            }
        )
        for f in forecasts()
    ]
    observed = [o.model_copy(update={"study_plan_sha256": binding}) for o in outcomes()]
    return p, submitted, observed


def result(p, submitted, observed):
    reg = register(p, MODEL, at=REGISTER_AT, artifacts=ARTIFACTS)
    sealed = seal_forecasts(reg, submitted, at=SEAL_AT, evidence=EVIDENCE)
    return evaluate(
        reg, sealed, observed, at=EVALUATE_AT, outcome_sources=OUTCOME_SOURCES
    )


@pytest.mark.parametrize("mode", ["omitted", "null"])
def test_empty_context_is_serialized_as_current_explicit_null(mode):
    raw = protocol().blind_protocol.plan.model_dump(mode="json")
    if mode == "omitted":
        raw.pop("protocol_context_sha256", None)
    else:
        raw["protocol_context_sha256"] = None
    validated = StudyPlan.model_validate(raw)
    for serialization in ("json", "python"):
        assert (
            validated.model_dump(mode=serialization)["protocol_context_sha256"] is None
        )


def test_complete_context_remains_part_of_original_plan_record_commitment():
    p, submitted, observed = prepared()
    r = result(p, submitted, observed)
    assert r["protocol_context_binding"]["status"] == "bound"
    assert r["protocol_context_binding"]["committed_context_sha256"] == (
        protocol_context_digest(p)
    )
    assert r["preregistered_performance_gate_met"]
    assert r["coverage"] == 1.0 and r["registered_count"] == 2
    assert r["metrics"]["brier_score"] == pytest.approx(0.01)
    assert r["real_world_efficacy"] == "not_established_by_synthetic_data"
    assert not r["authority_certified"]
    sheet = blind_outcome_sheet(register(p, MODEL, at=REGISTER_AT, artifacts=ARTIFACTS))
    assert (
        sheet["protocol_context_sha256"]
        == p.blind_protocol.plan.protocol_context_sha256
    )
    assert "fictional-0-a" not in json.dumps(sheet)


CONTEXT_CHANGES = [
    "pair_member",
    "pair_assignment",
    "relationship_context",
    "hypothesis",
    "training_subject_ids",
    "baseline_derivation",
    "outcome_adjudication",
    "recruitment_and_exclusions",
    "probability_mapping",
    "sample_size_justification",
    "analysis_plan",
    "calendar_rules",
    "classical_sources",
    "forecast_policy",
]


def change_context(raw, kind):
    if kind == "pair_member":
        raw["pairs"][0]["person1_subject_id"] = "SYNTHETIC replacement person"
    elif kind == "pair_assignment":
        raw["pairs"][0]["person1_subject_id"], raw["pairs"][1]["person1_subject_id"] = (
            raw["pairs"][1]["person1_subject_id"],
            raw["pairs"][0]["person1_subject_id"],
        )
    elif kind in ("relationship_context", "hypothesis"):
        raw[kind] += " changed"
    elif kind == "training_subject_ids":
        raw["blind_protocol"][kind].append("SYNTHETIC declared training person")
        raw["blind_protocol"]["plan"][kind].append("SYNTHETIC declared training person")
    elif kind in ("calendar_rules", "classical_sources", "forecast_policy"):
        raw["blind_protocol"]["artifact_sha256"][kind] = "f" * 64
    else:
        raw["blind_protocol"][kind] += " changed"


@pytest.mark.parametrize("kind", CONTEXT_CHANGES)
def test_changed_wrapper_cannot_keep_original_plan_context_commitment(kind):
    p, _, _ = prepared()
    raw = p.model_dump(mode="json")
    change_context(raw, kind)
    with pytest.raises(ValidationError, match="完整协议上下文指纹"):
        SukuyoProtocol.model_validate(raw)


@pytest.mark.parametrize("record", ["forecast", "outcome"])
def test_new_registered_context_cannot_reseal_original_record_from_other_pairing(
    record,
):
    p, submitted, observed = prepared()
    raw = p.model_dump(mode="json")
    raw["blind_protocol"]["plan"].pop("protocol_context_sha256")
    change_context(raw, "pair_member")
    raw["blind_protocol"]["plan"]["protocol_context_sha256"] = protocol_context_digest(
        SukuyoProtocol.model_validate(raw)
    )
    changed = SukuyoProtocol.model_validate(raw)
    new_binding = digest(changed.blind_protocol.plan.model_dump(mode="json"))
    if record == "outcome":
        submitted = [
            f.model_copy(update={"study_plan_sha256": new_binding}) for f in submitted
        ]
    with pytest.raises(ValueError, match="完整研究方案指纹不一致"):
        result(changed, submitted, observed)


def test_register_revalidates_mutated_protocol_and_never_fills_missing_binding():
    p, _, _ = prepared()
    p.pairs[0].person1_subject_id = "SYNTHETIC mutable replacement"
    with pytest.raises(ValidationError, match="完整协议上下文指纹"):
        register(p, MODEL, at=REGISTER_AT, artifacts=ARTIFACTS)
    legacy = protocol()
    reg = register(legacy, MODEL, at=REGISTER_AT, artifacts=ARTIFACTS)
    assert read_registration(reg).blind_protocol.plan.protocol_context_sha256 is None
    assert legacy.blind_protocol.plan.protocol_context_sha256 is None


def test_plan_context_cannot_be_invalidated_with_unvalidated_mutable_copy():
    p, submitted, observed = prepared()
    p.blind_protocol.plan.protocol_context_sha256 = True
    with pytest.raises(ValidationError, match="protocol_context_sha256"):
        result(p, submitted, observed)


def test_actual_context_cli_is_exclusive_and_does_not_edit_or_register_protocol(
    tmp_path,
):
    p, _, _ = prepared()
    raw = p.model_dump(mode="json")
    raw["blind_protocol"]["plan"].pop("protocol_context_sha256")
    path, output = tmp_path / "protocol.json", tmp_path / "context.json"
    path.write_text(json.dumps(raw))
    original = path.read_bytes()
    argv = [
        sys.executable,
        str(ROOT / "scripts/sukuyo_blind_study.py"),
        "context",
        "--protocol",
        str(path),
        "--output",
        str(output),
    ]
    completed = subprocess.run(argv, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    r = json.loads(output.read_bytes())
    assert r["status"] == "context_digest_only_not_registered"
    assert r["protocol_context_sha256"] == protocol_context_digest(p)
    assert path.read_bytes() == original
    receipt = output.read_bytes()
    repeated = subprocess.run(argv, capture_output=True, text=True)
    assert repeated.returncode != 0
    assert output.read_bytes() == receipt
    assert path.read_bytes() == original
