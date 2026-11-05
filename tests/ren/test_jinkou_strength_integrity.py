"""Strength, qi, use conditions and traces describe one calculation."""

import asyncio
import copy
import importlib.util
import itertools
import json
import shutil
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.metaphysics.jinkou_strength import internal_strength
from fatebridge.core.output_chinese import Jinkou
from tests.evaluation.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

ROOT = Path(__file__).resolve().parents[2]
MOD = importlib.util.spec_from_file_location(
    "strength_integrity", ROOT / "scripts/ren/audit_jinkou_strength_integrity.py"
)
assert MOD and MOD.loader
AUDIT = importlib.util.module_from_spec(MOD)
MOD.loader.exec_module(AUDIT)
REFERENCE = AUDIT.reference()
PAYLOAD = REFERENCE["protocol"]["payload"]
SPEC = SPECS["jinkou"]


@lru_cache(maxsize=1)
def raw():
    fn, args, kw = SPEC.bind(SPEC.request_model.model_validate(PAYLOAD))
    return fn(*args, **kw)


def test_new_witness_is_corroboration_and_does_not_erase_the_original_failure():
    report = AUDIT.audit()
    assert report["synthetic_fault_count"] == report["synthetic_rejected_count"] == 37
    assert report["new_witness_case_count"] == report["new_witness_matched_count"] == 12
    assert (
        report["older_scan_case_count"] == 12
        and report["older_scan_matched_count"] == 11
    )
    assert report["older_scan_failures"][0]["id"] == "S01"
    assert report["older_scan_failures"][0]["raw_diagram_elements"] == list("土土火木")
    assert report["engineering_rejection_gate_passed"]
    assert not report["original_classical_gate_passed"]
    assert not report["daily_five_states_adjudicated"]
    assert not report["comprehensive_use_adjudicated"] and not report["goal_complete"]
    assert report["new_unique_historical_or_empirical_events"] == 0
    assert report["implementation_unchanged"]


@pytest.mark.parametrize(
    "change", ["reference", "faults", "manifest", "extra", "missing"]
)
def test_source_and_fault_cohort_cannot_be_relabelled_or_pruned(tmp_path, change):
    target = tmp_path / "source"
    shutil.copytree(AUDIT.CORPUS, target)
    if change == "extra":
        (target / "extra.json").write_text("{}")
    elif change == "missing":
        (target / "source-pages.pdf").unlink()
    else:
        path = (
            target
            / {
                "reference": "reference.json",
                "faults": "faults.json",
                "manifest": "freeze.json",
            }[change]
        )
        path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="Frozen strength-integrity"):
        AUDIT.reference(target)


@pytest.mark.parametrize("fault", REFERENCE["faults"], ids=lambda f: f["id"])
@pytest.mark.parametrize("project", [False, True])
def test_each_predeclared_fault_is_rejected_before_projection_on_all_ports(
    fault, project, rest, monkeypatch, tmp_path, capsys
):
    bad = AUDIT.corrupt(raw(), fault)
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(SPEC, bad)
    original = execution.execute_spec

    def broken(spec, request):
        if spec.key == "jinkou":
            spec = replace(spec, bind=lambda _: (lambda: copy.deepcopy(bad), (), {}))
        return original(spec, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    params = {"as_of": AS_OF, "response_char_limit": 0}
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        params.update(fields="analysis_type", strict_fields="true")
        options.update(fields=["analysis_type"], strict_fields=True)
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
    http = rest.post(SPEC.rest_path, json=PAYLOAD, params=params)
    protocol = asyncio.run(native(SPEC, PAYLOAD, **options))
    code, cli = call_cli(SPEC, PAYLOAD, tmp_path, capsys, flags=flags)
    assert http.status_code == 500 and protocol.is_error and code == 1
    assert cli["error_code"] == "internal_error"


@pytest.mark.parametrize("project", [False, True])
def test_valid_result_and_nullable_unknowns_are_faithful_on_all_ports(
    project, rest, tmp_path, capsys
):
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        fields = [
            "jinkou.rows",
            "jinkou.internal_strength",
            "jinkou.qi_evidence",
            "jinkou.use_evidence",
            "jinkou.rule_trace",
        ]
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        options.update(fields=fields, strict_fields=True, include_snapshot_text=False)
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
    http = rest.post(SPEC.rest_path, json=PAYLOAD, params=params)
    protocol = asyncio.run(native(SPEC, PAYLOAD, **options))
    code, cli = call_cli(SPEC, PAYLOAD, tmp_path, capsys, flags=flags)
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    for data in [http.json(), protocol.structured_content, cli]:
        SPEC.output_model.model_validate(data)
        board = data["jinkou"]
        assert board["internal_strength"]["status"] == "ambiguous_excerpt"
        assert board["internal_strength"]["anchor_element"] is None
        assert all(r["internal_power"] is None for r in board["rows"])
        assert board["use_evidence"]["comprehensive_position"] is None
        if not project:
            assert "位内旺神：未定" in data["snapshot_text"]
            assert (
                "综合取用状态：no_control_strength_priority_unresolved"
                in data["snapshot_text"]
            )


def test_all_625_phase_boards_accept_actual_unknowns_and_reject_a_changed_power():
    count = 0
    for phases in itertools.product("木火土金水", repeat=4):
        rows = [dict(label=p, element=e) for p, e in zip(AUDIT.POSITIONS, phases)]
        strength = internal_strength(rows)
        for row in rows:
            row["internal_power"] = strength["powers"][row["label"]]
        value = dict(rows=rows, internal_strength=strength)
        Jinkou.model_validate(value)
        wrong = copy.deepcopy(value)
        wrong["rows"][0]["internal_power"] = AUDIT.changed(
            rows[0]["internal_power"], "power"
        )
        with pytest.raises(ValidationError):
            Jinkou.model_validate(wrong)
        count += 1
    assert count == 625  # Synthetic boards; not 625 new classical examples.


@pytest.mark.parametrize(
    "route", ["internal_strength", "use_evidence", "qi_evidence", "rule_trace"]
)
def test_public_sparse_views_keep_omitted_anchors_omitted(route):
    value = {route: raw()["jinkou"][route]}
    assert Jinkou.model_validate(value).model_dump(exclude_unset=True) == value
    sparse = {
        "rows": [
            {"internal_power": r["internal_power"]} for r in raw()["jinkou"]["rows"]
        ]
    }
    assert Jinkou.model_validate(sparse).model_dump(exclude_unset=True) == sparse


@pytest.mark.parametrize(
    "claim", ["complete_classical_acceptance", "daily_five_states_adjudicated"]
)
def test_trace_cannot_turn_unknown_classical_scope_into_certification(claim):
    bad = json.loads(json.dumps(raw()))
    trace = next(
        t
        for t in bad["jinkou"]["rule_trace"]
        if t["rule_id"] == "jinkou.internal_strength"
    )
    trace["result"]["source_evidence"][claim] = True
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(SPEC, bad)


def test_invalid_raw_symbol_is_a_validation_error_and_boolean_trace_is_strict():
    bad = json.loads(json.dumps(raw()))
    bad["jinkou"]["rows"][0]["content"] = "子"
    with pytest.raises(ValidationError):
        SPEC.output_model.model_validate(bad)
    bad = json.loads(json.dumps(raw()))
    trace = next(
        t
        for t in bad["jinkou"]["rule_trace"]
        if t["rule_id"] == "jinkou.internal_strength"
    )
    trace["result"]["has_control"] = 0
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(SPEC, bad)


@pytest.mark.parametrize(
    "target", ["null_basis", "empty_trace_basis", "null_source_note"]
)
def test_complete_explanation_dependencies_cannot_be_replaced_with_empty_values(target):
    bad = json.loads(json.dumps(raw()))
    if target == "null_basis":
        bad["jinkou"]["internal_strength"]["basis"] = None
    elif target == "empty_trace_basis":
        trace = next(
            t
            for t in bad["jinkou"]["rule_trace"]
            if t["rule_id"] == "jinkou.use_conditions"
        )
        trace["result"]["basis"] = ""
    else:
        bad["jinkou"]["internal_strength"]["source_evidence"]["note"] = None
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(SPEC, bad)
