"""Whole-ledger consistency is checked before any output field projection."""

import asyncio
import copy
import importlib.util
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.output_chinese import JinkouPatterns
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    inputs,
    native,
    rest,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "pattern_integrity", ROOT / "scripts/audit_jinkou_pattern_integrity.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
REFERENCE = AUDIT.reference()
FAULTS = REFERENCE["faults"]


def test_complete_source_outputs_survive_and_all_frozen_corruptions_are_rejected():
    result = AUDIT.audit()
    assert result["corruption_probe_count"] == 20
    assert result["rejected_corruption_probes"] == 20
    assert result["unaltered_original_case_outputs"] == 64
    assert result["unaltered_outputs_accepted"] == 64
    assert not result["validation_errors"]
    assert result["selected_integrity_checks_passed"]
    assert not result["classical_acceptance_passed"] and not result["goal_complete"]


@pytest.mark.parametrize("change", ["edit", "missing", "extra"])
def test_integrity_inventory_cannot_hide_a_precommitted_probe(tmp_path, change):
    target = tmp_path / "corpus"
    shutil.copytree(AUDIT.CORPUS, target)
    p = target / "reference.json"
    if change == "edit":
        data = json.loads(p.read_text())
        data["faults"].pop()
        p.write_text(json.dumps(data))
    elif change == "missing":
        p.unlink()
    else:
        (target / "extra.json").write_text("{}")
    with pytest.raises(ValueError, match="Frozen pattern-integrity"):
        AUDIT.reference(target)


@pytest.mark.parametrize("name", FAULTS)
@pytest.mark.parametrize("project", [False, True])
def test_conflicting_ledger_facts_fail_on_all_three_transports_before_projection(
    name, project, rest, monkeypatch, tmp_path, capsys
):
    spec = SPECS["jinkou"]
    # Keep a complete valid business envelope. A patterns-only payload would
    # fail the unrelated required-field gate before reaching this validator.
    # Historical golden receipts predate several mandatory evidence layers.
    # Keep those bytes untouched; obtain a current complete envelope so these
    # frozen corruptions reach the ledger validator, rather than a missing-
    # dependency guard. This does not generate any classical expected label.
    request = spec.request_model.model_validate(inputs(spec))
    fn, args, kwargs = spec.bind(request)
    valid = fn(*args, **kwargs)
    execution.validate_output(spec, valid)
    bad = copy.deepcopy(valid)
    bad["jinkou"]["patterns"] = AUDIT.corrupt(valid["jinkou"]["patterns"], name)
    with pytest.raises(ValidationError):
        spec.output_model.model_validate(bad)
    with pytest.raises(execution.OutputContractError, match="不符合公开契约"):
        execution.validate_output(spec, bad)
    original = execution.execute_spec

    def broken_output(actual, request):
        if actual.key == spec.key:
            actual = replace(
                actual, bind=lambda _: (lambda: copy.deepcopy(bad), (), {})
            )
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", broken_output)
    params = dict(as_of=AS_OF, response_char_limit=0, trace_id="ledger-integrity")
    options = dict(trace_id="ledger-integrity")
    flags = ["--response-char-limit", "0", "--trace-id", "ledger-integrity"]
    if project:
        params.update(fields="analysis_type", strict_fields="true")
        options.update(fields=["analysis_type"], strict_fields=True)
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
    http = rest.post(spec.rest_path, json=inputs(spec), params=params)
    protocol = asyncio.run(native(spec, inputs(spec), **options))
    code, output = call_cli(spec, inputs(spec), tmp_path, capsys, flags=flags)
    assert http.status_code == 500 and protocol.is_error and code == 1
    assert output["error_code"] == "internal_error"
    assert output["status_code"] == 500 and output["trace_id"] == "ledger-integrity"
    assert http.json() == {
        k: v for k, v in output.items() if k not in {"operation", "status_code"}
    }
    assert {
        k: v for k, v in protocol.structured_content.items() if k != "operation"
    } == output
    assert "private-wrong-value" not in json.dumps(output)
    assert json.loads(protocol.content[0].text) == protocol.structured_content


@pytest.mark.parametrize(
    "field",
    [
        "jinkou.patterns",
        "jinkou.patterns.evaluations",
        "jinkou.patterns.evaluation_counts.matched",
        "jinkou.patterns.matched",
        "jinkou.patterns.unresolved",
        "jinkou.patterns.catalog_count",
        "jinkou.patterns.complete_classical_conformance",
    ],
)
def test_actual_sparse_projections_still_agree_across_transports(
    field, rest, tmp_path, capsys
):
    spec = SPECS["jinkou"]
    payload = inputs(spec)
    params = dict(
        fields=field,
        strict_fields="true",
        include_snapshot_text="false",
        response_char_limit=0,
        as_of=AS_OF,
    )
    http = rest.post(spec.rest_path, json=payload, params=params)
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=[field],
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            field,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    bodies = [http.json(), protocol.structured_content, cli]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for body in bodies:
        spec.output_model.model_validate(body)
    pattern = bodies[0]["jinkou"]["patterns"]
    if field.endswith(".matched") and "evaluation_counts" in pattern:
        assert pattern == {
            "evaluation_counts": {"matched": pattern["evaluation_counts"]["matched"]}
        }
    if field.endswith(".evaluations"):
        assert len(pattern["evaluations"]) == 64


@pytest.mark.parametrize("value", [True, 0, 1, "false"])
def test_current_excerpt_cannot_gain_a_full_classical_certificate(value):
    with pytest.raises(ValidationError):
        JinkouPatterns.model_validate({"complete_classical_conformance": value})


def test_object_sparsity_preserves_missing_facts_and_extension_fields():
    raw = {"evaluation_counts": {"matched": 3}, "extension": {"reviewed": False}}
    model = JinkouPatterns.model_validate(raw)
    assert model.model_dump(exclude_unset=True) == raw
    assert raw == {
        "evaluation_counts": {"matched": 3},
        "extension": {"reviewed": False},
    }
