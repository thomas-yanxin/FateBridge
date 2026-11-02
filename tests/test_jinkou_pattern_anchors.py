"""An internally coherent pattern ledger must still describe its own course."""

import asyncio
import copy
import hashlib
import json
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.metaphysics.jinkou_patterns import CATALOG
from fatebridge.core.output_chinese import Jinkou
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/jinkou_pattern_anchors_v1"
PIN = "6ead46d3c4e5f242e15a490eede9fd6bd1a8f86d7d265fa6b0df53293481ebc9"
SPEC = SPECS["jinkou"]


def reference():
    assert hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest() == PIN
    freeze = json.loads((CORPUS / "freeze.json").read_text())
    assert set(p.name for p in CORPUS.iterdir()) == set(freeze["files"]) | {
        "freeze.json"
    }
    assert all(
        hashlib.sha256((CORPUS / n).read_bytes()).hexdigest() == h
        for n, h in freeze["files"].items()
    )
    return json.loads((CORPUS / "protocol.json").read_text())


REF = reference()
PAYLOAD = REF["payload"]
ANNUAL_PAYLOAD = dict(PAYLOAD, birth_year_ganzhi="甲午", year_fate_age=20, gender="男")


@lru_cache(maxsize=4)
def valid(annual=False, other=False):
    payload = dict(ANNUAL_PAYLOAD if annual else PAYLOAD)
    if other:
        payload["di_fen"] = "子"
    fn, args, kw = SPEC.bind(SPEC.request_model.model_validate(payload))
    result = fn(*args, **kw)
    execution.validate_output(SPEC, result)
    return result


def set_verdict(patterns, pid, value):
    row = next(v for v in patterns["evaluations"] if v["id"] == pid)
    row.update(matched=value, status="matched" if value else "not_matched")
    patterns["matched"] = [v for v in patterns["matched"] if v["id"] != pid]
    patterns["unresolved"] = [v for v in patterns["unresolved"] if v["id"] != pid]
    if value:
        patterns["matched"].append(
            dict(
                id=pid,
                name=row["name"],
                alias=CATALOG[int(pid[1:]) - 1][1],
                original_pdf_page=row["original_pdf_page"],
                reading="按所选结构定义",
                condition=row["condition"],
                basis="协调伪造的四位结构",
            )
        )
    patterns["evaluation_counts"] = dict(
        matched=sum(v["matched"] is True for v in patterns["evaluations"]),
        not_matched=sum(v["matched"] is False for v in patterns["evaluations"]),
        unresolved=sum(v["matched"] is None for v in patterns["evaluations"]),
    )
    patterns["evaluated_rule_count"] = 64 - patterns["evaluation_counts"]["unresolved"]


def corrupt(name, annual=False):
    # The builder shares the pattern object with its trace. Serialization
    # separates those aliases so trace_only really changes only the trace.
    result = json.loads(json.dumps(valid(annual)))
    board = result["jinkou"]["year_fate"]["course"] if annual else result["jinkou"]
    patterns = board["patterns"]
    traces = board["rule_trace"]
    trace = next(t for t in traces if t["rule_id"] == "jinkou.structural_patterns")
    positive = patterns["matched"][0]["id"]
    negative = next(v["id"] for v in patterns["evaluations"] if v["matched"] is False)
    if name == "coordinated_false_positive":
        set_verdict(patterns, negative, True)
    elif name == "coordinated_false_negative":
        set_verdict(patterns, positive, False)
    elif name in {"unknown_to_true", "unknown_to_false"}:
        set_verdict(patterns, "P52", name.endswith("true"))
    elif name == "borrow_other_ground":
        # Both courses have their own internally valid evidence. Use a
        # different main course as the foreign donor even for an annual child.
        board["patterns"] = copy.deepcopy(valid(False, True)["jinkou"]["patterns"])
        assert board["patterns"] != patterns
    elif name == "wrong_day_robbery":
        patterns["day_robbery_branch"] = (
            "子" if patterns["day_robbery_branch"] != "子" else "午"
        )
    elif name in {"coordinated_condition", "coordinated_name", "coordinated_page"}:
        key = {
            "coordinated_condition": "condition",
            "coordinated_name": "name",
            "coordinated_page": "original_pdf_page",
        }[name]
        value = 999 if key == "original_pdf_page" else "协调伪造的原典条件"
        next(v for v in patterns["evaluations"] if v["id"] == positive)[key] = value
        next(v for v in patterns["matched"] if v["id"] == positive)[key] = value
    elif name == "wrong_source_url":
        patterns["source_url"] = "https://example.invalid/forged"
        trace["source_url"] = patterns["source_url"]
    elif name == "wrong_source_hash":
        patterns["source_sha256"] = "0" * 64
    elif name == "trace_only":
        set_verdict(trace["result"], negative, True)
        return result
    elif name == "missing_patterns":
        del board["patterns"]
        return result
    elif name == "missing_pattern_trace":
        board["rule_trace"] = [
            t for t in traces if t["rule_id"] != "jinkou.structural_patterns"
        ]
        return result
    elif name == "duplicate_pattern_trace":
        traces.append(copy.deepcopy(trace))
        return result
    else:
        raise AssertionError(name)
    trace["result"] = copy.deepcopy(board["patterns"])
    return result


@pytest.mark.parametrize("annual", [False, True])
@pytest.mark.parametrize("fault", REF["faults"])
def test_coordinated_fault_is_rejected_against_this_courses_raw_anchors(fault, annual):
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(SPEC, corrupt(fault, annual))


@pytest.mark.parametrize("annual", [False, True])
def test_valid_complete_main_and_annual_courses_are_accepted(annual):
    result = valid(annual)
    execution.validate_output(SPEC, result)
    assert len(result["jinkou"]["patterns"]["evaluations"]) == 64
    assert result["jinkou"]["patterns"]["complete_classical_conformance"] is False


@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize(
    "fault", ["coordinated_false_positive", "unknown_to_true", "missing_pattern_trace"]
)
def test_anchor_failure_survives_all_three_ports_before_projection(
    fault, project, rest, monkeypatch, tmp_path, capsys
):
    bad = corrupt(fault)
    original = execution.execute_spec

    def broken(spec, request):
        if spec.key == "jinkou":
            spec = replace(spec, bind=lambda _: (lambda: copy.deepcopy(bad), (), {}))
        return original(spec, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    params = {"as_of": AS_OF, "response_char_limit": "0"}
    options, flags = {}, ["--response-char-limit", "0"]
    if project:
        params.update(fields="analysis_type", strict_fields="true")
        options = dict(fields=["analysis_type"], strict_fields=True)
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
    http = rest.post(SPEC.rest_path, json=PAYLOAD, params=params)
    mcp = asyncio.run(native(SPEC, PAYLOAD, **options))
    code, cli = call_cli(SPEC, PAYLOAD, tmp_path, capsys, flags=flags)
    assert http.status_code == 500 and mcp.is_error and code == 1
    for value in (http.json(), mcp.structured_content, cli):
        assert value["error_code"] == "internal_error"
        assert "jinkou" not in value


def test_a_patterns_only_projection_has_no_invented_input_anchors():
    patterns = valid()["jinkou"]["patterns"]
    parsed = Jinkou.model_validate(dict(patterns=patterns))
    assert parsed.rows is None and parsed.calendar_policy is None
    assert (
        parsed.patterns.evaluation_counts.model_dump() == patterns["evaluation_counts"]
    )


@pytest.mark.parametrize("annual", [False, True])
def test_reordered_catalogue_keeps_the_same_id_bound_facts(annual):
    result = json.loads(json.dumps(valid(annual)))
    board = result["jinkou"]["year_fate"]["course"] if annual else result["jinkou"]
    for key in ("evaluations", "matched", "unresolved"):
        board["patterns"][key].reverse()
    trace = next(
        t for t in board["rule_trace"] if t["rule_id"] == "jinkou.structural_patterns"
    )
    trace["result"] = copy.deepcopy(board["patterns"])
    execution.validate_output(SPEC, result)


def test_partial_count_view_uses_available_symbols_without_inventing_omitted_fields():
    source = valid()["jinkou"]
    partial = dict(
        rows=[dict(label=r["label"], content=r["content"]) for r in source["rows"]],
        calendar_policy={
            "effective_day_ganzhi": source["calendar_policy"]["effective_day_ganzhi"]
        },
        patterns={"evaluation_counts": source["patterns"]["evaluation_counts"]},
    )
    parsed = Jinkou.model_validate(partial)
    assert parsed.patterns.evaluations is None
    assert all(row.element is None for row in parsed.rows)
    partial["patterns"]["evaluation_counts"] = dict(
        source["patterns"]["evaluation_counts"],
        matched=source["patterns"]["evaluation_counts"]["matched"] + 1,
    )
    with pytest.raises(ValidationError):
        Jinkou.model_validate(partial)


@pytest.mark.parametrize("position,symbol", [(0, "子"), (1, "甲"), (3, "invalid")])
def test_invalid_raw_symbols_remain_structured_validation_errors(position, symbol):
    result = json.loads(json.dumps(valid()))
    result["jinkou"]["rows"][position]["content"] = symbol
    with pytest.raises(ValidationError):
        SPEC.output_model.model_validate(result)
