"""Protocol replay counterexamples; all records are explicitly synthetic."""

import hashlib
import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from fatebridge.validation import jyotish_study_binding as api
from tests.jyotish import test_jyotish_study_binding as f

FIELDS = [
    "baseline_derivation",
    "outcome_adjudication",
    "recruitment_and_exclusions",
    "probability_mapping",
    "sample_size_justification",
    "analysis_plan",
    "classical_source_bytes",
    "extra_material",
]


def canonical(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def bound_protocol():
    data = f.protocol_data()
    data["plan"]["protocol_context_sha256"] = expected_context()
    return api.JyotishProtocol.model_validate(data)


def records(protocol, factory):
    plan_hash = canonical(protocol.plan.model_dump(mode="json"))
    return [x.model_copy(update={"study_plan_sha256": plan_hash}) for x in factory()]


def changed_data(field):
    data = bound_protocol().model_dump(mode="json")
    artifacts = dict(f.ARTIFACTS)
    if field == "classical_source_bytes":
        artifacts["classical_sources"] = b"another synthetic source"
        data["artifact_sha256"]["classical_sources"] = f.sha(
            artifacts["classical_sources"]
        )
    elif field == "extra_material":
        artifacts["additional_material"] = b"another synthetic instruction"
        data["artifact_sha256"]["additional_material"] = f.sha(
            artifacts["additional_material"]
        )
    else:
        data[field] += "; changed synthetic condition"
    return data, artifacts


def expected_context():
    details = f.protocol_data()
    details.pop("plan")
    return canonical(
        {"format": "jyotish_protocol_context_v1", "blind_protocol_details": details}
    )


def test_context_commits_declared_outer_details_and_plan_explicitly_includes_binding():
    protocol = f.protocol()
    assert api.protocol_context_digest(protocol) == expected_context()
    assert protocol.plan.model_dump(mode="json")["protocol_context_sha256"] is None
    bound = bound_protocol()
    assert (
        bound.plan.model_dump(mode="json")["protocol_context_sha256"]
        == expected_context()
    )
    assert api.protocol_context_digest(bound) == api.protocol_context_digest(protocol)
    # Plan details and context have separate commitments; neither can hide changes.
    changed = bound.plan.model_copy(
        update={"target_definition": "another synthetic target"}
    )
    assert canonical(changed.model_dump(mode="json")) != canonical(
        bound.plan.model_dump(mode="json")
    )


@pytest.mark.parametrize("field", FIELDS)
def test_supplied_context_rejects_a_changed_wrapper_before_registration(field):
    data, _ = changed_data(field)
    with pytest.raises(ValidationError, match="完整协议上下文指纹"):
        api.JyotishProtocol.model_validate(data)


def test_mutated_protocol_and_fully_rehashed_packet_cannot_keep_stale_context():
    protocol = bound_protocol()
    protocol.outcome_adjudication += "; changed"
    with pytest.raises(ValidationError, match="完整协议上下文指纹"):
        api.register(protocol, f.MODEL, at=f.REGISTERED, artifacts=f.ARTIFACTS)
    registration = api.register(
        bound_protocol(), f.MODEL, at=f.REGISTERED, artifacts=f.ARTIFACTS
    )
    changed = deepcopy(registration)
    inner = changed["commitment"]
    inner["protocol"]["analysis_plan"] += "; changed"
    inner["registration_sha256"] = canonical(
        {k: v for k, v in inner.items() if k != "registration_sha256"}
    )
    changed["registration_sha256"] = canonical(
        {k: v for k, v in changed.items() if k != "registration_sha256"}
    )
    with pytest.raises(ValidationError, match="完整协议上下文指纹"):
        api.read_registration(changed)


@pytest.mark.parametrize("field", FIELDS)
def test_original_forecasts_and_outcomes_cannot_move_to_a_new_bound_protocol(field):
    original = bound_protocol()
    old_forecasts = records(original, f.forecasts)
    old_outcomes = records(original, f.outcomes)
    data, artifacts = changed_data(field)
    # A legitimately new prospective protocol must bind its newly changed
    # details. It cannot reuse the original record commitments afterwards.
    data["plan"]["protocol_context_sha256"] = None
    draft = api.JyotishProtocol.model_validate(data)
    data["plan"]["protocol_context_sha256"] = api.protocol_context_digest(draft)
    other = api.JyotishProtocol.model_validate(data)
    registration = api.register(other, f.MODEL, at=f.REGISTERED, artifacts=artifacts)
    with pytest.raises(ValueError, match="完整研究方案指纹"):
        api.seal_forecasts(
            registration, old_forecasts, at=f.ISSUED, evidence=f.EVIDENCE
        )
    sealed = api.seal_forecasts(
        registration,
        records(other, f.forecasts),
        at=f.ISSUED,
        evidence=f.EVIDENCE,
    )
    with pytest.raises(ValueError, match="完整研究方案指纹"):
        api.reveal_and_evaluate(
            registration, sealed, old_outcomes, at=f.AFTER, outcome_sources=f.SOURCES
        )


def test_complete_original_binding_allows_only_the_existing_limited_gates():
    protocol = bound_protocol()
    registration = api.register(
        protocol, f.MODEL, at=f.REGISTERED, artifacts=f.ARTIFACTS
    )
    sealed = api.seal_forecasts(
        registration, records(protocol, f.forecasts), at=f.ISSUED, evidence=f.EVIDENCE
    )
    report = api.reveal_and_evaluate(
        registration,
        sealed,
        records(protocol, f.outcomes),
        at=f.AFTER,
        outcome_sources=f.SOURCES,
    )
    assert report["protocol_blockers"] == []
    assert report["preregistered_performance_gate_met"]
    assert report["protocol_context_binding"]["status"] == "bound"
    assert not report["statistical_evidence_gate_met"]  # two synthetic rows
    assert not report["authority_certified"]
    assert report["real_world_efficacy"] == "not_established_by_synthetic_data"
    assert (
        report["external_timestamp_and_blinding"] == "requires_independent_verification"
    )
    assert api.blind_outcome_sheet(registration)["study_plan_sha256"] == canonical(
        protocol.plan.model_dump(mode="json")
    )


def test_missing_context_blocks_protocol_gate_without_silent_rebinding():
    protocol = f.protocol()
    registration = api.register(
        protocol, f.MODEL, at=f.REGISTERED, artifacts=f.ARTIFACTS
    )
    before = canonical(registration)
    assert api.read_registration(registration).plan.protocol_context_sha256 is None
    assert canonical(registration) == before
    sealed = api.seal_forecasts(
        registration, records(protocol, f.forecasts), at=f.ISSUED, evidence=f.EVIDENCE
    )
    report = api.reveal_and_evaluate(
        registration,
        sealed,
        records(protocol, f.outcomes),
        at=f.AFTER,
        outcome_sources=f.SOURCES,
    )
    assert report["metrics"]["brier_skill_score"] == pytest.approx(0.96)
    assert report["registered_numeric_gate_met"]
    assert not report["preregistered_performance_gate_met"]
    assert "missing_jyotish_protocol_context_commitment" in report["protocol_blockers"]
    assert report["protocol_context_binding"]["committed_context_sha256"] is None
    assert api.read_registration(registration).plan.protocol_context_sha256 is None
    assert canonical(registration) == before


def test_context_cannot_retroactively_supply_missing_original_record_commitments():
    protocol = bound_protocol()
    registration = api.register(
        protocol, f.MODEL, at=f.REGISTERED, artifacts=f.ARTIFACTS
    )
    forecasts = f.forecasts()
    sealed = api.seal_forecasts(
        registration, forecasts, at=f.ISSUED, evidence=f.EVIDENCE
    )
    report = api.reveal_and_evaluate(
        registration, sealed, f.outcomes(), at=f.AFTER, outcome_sources=f.SOURCES
    )
    assert report["protocol_context_binding"]["status"] == "bound"
    assert not report["preregistered_performance_gate_met"]
    assert set(report["protocol_blockers"]) == {
        "missing_forecast_plan_commitment",
        "missing_outcome_plan_commitment",
    }
    assert all(x.study_plan_sha256 is None for x in forecasts)


def test_actual_cli_preserves_original_context_and_record_bindings(
    tmp_path, monkeypatch
):
    protocol = bound_protocol()
    data = protocol.model_dump(mode="json")
    original_forecasts, original_outcomes = f.forecasts, f.outcomes
    monkeypatch.setattr(f, "protocol_data", lambda: deepcopy(data))
    monkeypatch.setattr(f, "forecasts", lambda: records(protocol, original_forecasts))
    monkeypatch.setattr(f, "outcomes", lambda: records(protocol, original_outcomes))
    # Reuse the real argument parsing/file I/O flow, including duplicate input
    # rejection and exclusive output creation, with the new original bindings.
    f.test_cli_full_synthetic_flow_uses_actual_files_and_duplicate_bindings_fail(
        tmp_path, monkeypatch
    )
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["protocol_context_binding"]["status"] == "bound"
    assert report["preregistered_performance_gate_met"]
    assert report["record_plan_binding"]["registered_cohort_fully_bound"]
    assert not report["authority_certified"]
