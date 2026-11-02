"""Candidate omissions and invented effects fail before unrelated projection."""

import asyncio
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

import fatebridge.application.execution as execution
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.passage_relations import build_passage_relation_context
from tests.test_agentic_nested_outputs import AS_OF, SPECS, call_cli, native
from tests.test_agentic_nested_outputs import rest as shared_rest

rest = shared_rest
ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads(
    (
        ROOT
        / "tests/fixtures/bazi_same_target_bureau_v1/protocol-cases-affiliation-first.json"
    ).read_text()
)


def chain_for(payload, tool):
    if tool == "analyze_destiny":
        return payload["structure_profile"]["evidence_chain"]
    if tool == "bazi_birth":
        return payload["bazi_birth"]["structure_profile"]["evidence_chain"]
    return payload[tool.removeprefix("bazi_") + "_analysis"]["evidence_chain"]


@pytest.mark.parametrize("case", DATA["cases"], ids=lambda c: c["tool"])
@pytest.mark.parametrize(
    "fault", ["missing_candidate", "false_carrier_refs", "invented_event"]
)
def test_inventory_faults_cannot_hide_behind_unrelated_fields(
    case, fault, rest, monkeypatch, tmp_path, capsys
):
    tool, spec = case["tool"], SPECS[case["tool"]]
    payload = {
        k: v
        for k, v in execution.execute_tool(
            spec, spec.request_model.model_validate(case["arguments"])
        ).items()
        if k != "run_metadata"
    }
    assert "error" not in payload, payload
    chart = {p: tuple(pair) for p, pair in DATA["verified_synthetic_pillars"].items()}
    strength = ElementAnalysis.analyze_day_master_strength(chart)
    chain = chain_for(payload, tool)
    context = build_passage_relation_context(
        chain["classical_passage"], strength["assessment"], pillars=chart
    )
    assert chain["classical_passage_relations"] == context
    chain["classical_passage_relations"] = context
    spec.output_model.model_validate(payload)
    inventory = context["branch_combination_candidates"]
    if fault == "missing_candidate":
        inventory["candidates"].pop()
    elif fault == "false_carrier_refs":
        node = next(n for n in context["nodes"] if n["potential_branch_candidate_refs"])
        node["potential_branch_candidate_refs"] = []
    else:
        candidate = next(
            r for r in inventory["candidates"] if not r["actual_event_refs"]
        )
        candidate.update(
            actual_event_refs=["assessment.relations:0"],
            current_statuses=[strength["assessment"]["relations"][0]["status"]],
            screen_decision="recorded_event",
        )
    original = execution.execute_spec

    def broken(actual, request):
        if actual.key == tool:
            actual = replace(actual, bind=lambda _: (lambda: deepcopy(payload), (), {}))
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    path = (
        "day_master.stem"
        if tool == "analyze_destiny"
        else (
            "bazi_birth.four_pillars.day.stem"
            if tool == "bazi_birth"
            else tool.removeprefix("bazi_") + "_analysis.evidence_chain.method_id"
        )
    )
    flags = {
        "fields": [path],
        "strict_fields": True,
        "response_char_limit": 8192,
        "as_of": AS_OF,
    }
    response = (
        rest.post(spec.rest_path, json=case["arguments"], params=flags)
        if spec.rest_path
        else None
    )
    protocol = asyncio.run(
        native(
            spec,
            case["arguments"],
            fields=[path],
            strict_fields=True,
            response_char_limit=8192,
        )
    )
    code, cli = call_cli(
        spec,
        case["arguments"],
        tmp_path,
        capsys,
        ["--fields", path, "--strict-fields", "true", "--response-char-limit", "8192"],
    )
    actual = {"mcp": protocol.structured_content, "cli": cli}
    if response is not None:
        actual["rest"] = response.json()
    (tmp_path / "actual-responses.json").write_text(
        json.dumps(actual, ensure_ascii=False) + "\n"
    )
    assert (
        (response is None or response.status_code == 500)
        and protocol.is_error
        and code == 1
    )
    assert all(value["error_code"] == "internal_error" for value in actual.values())
    assert all(
        len(json.dumps(v, ensure_ascii=False, separators=(",", ":"))) <= 8192
        for v in actual.values()
    )
