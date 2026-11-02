"""False v9 resolution is rejected before projection on every entrance."""

import asyncio
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

import fatebridge.application.execution as execution
from fatebridge.core.execution_context import call_clock
from tests.test_agentic_nested_outputs import AS_OF, SPECS, call_cli, native
from tests.test_agentic_nested_outputs import rest as shared_rest

rest = shared_rest
ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads(
    (
        ROOT / "tests/fixtures/bazi_punishment_resolution_v1/protocol-cases-first.json"
    ).read_text()
)
CASES = DATA["cases"][:12]


def evidence(payload, tool):
    if tool == "analyze_destiny":
        return payload["structure_profile"]["evidence_chain"]
    if tool == "bazi_birth":
        return payload["bazi_birth"]["structure_profile"]["evidence_chain"]
    return payload[tool.removeprefix("bazi_") + "_analysis"]["evidence_chain"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
@pytest.mark.parametrize(
    "fault",
    [
        "false_resolution",
        "without_inventory",
        "without_strength_context_or_wrong_policy",
    ],
)
def test_false_resolution_cannot_hide_behind_unrelated_projection(
    case, fault, rest, monkeypatch, tmp_path, capsys
):
    tool, spec = case["tool"], SPECS[case["tool"]]
    with call_clock(AS_OF):
        payload = execution.execute_spec(
            spec, spec.request_model.model_validate(case["arguments"])
        )
    if tool == "bazi_source_compare":
        current = payload["current_calculation"]
        assert current["method_id"] == "season_root_revelation_relations_v10"
        target = current["assessment"]["relations"]
        if fault == "without_inventory":
            current.pop("branch_combination_candidates")
        if fault == "without_strength_context_or_wrong_policy":
            current["assessment"][
                "punishment_resolution_policy"
            ] = "initial_candidate_protection_v1"
        path = "input_context.input_kind"
    else:
        chain = evidence(payload, tool)
        assert (
            chain["strength_context"]["method_id"]
            == "season_root_revelation_relations_v10"
        )
        target = [e["receipt"] for e in chain["classical_passage_relations"]["events"]]
        if fault == "without_inventory":
            chain["classical_passage_relations"].pop("branch_combination_candidates")
        if fault == "without_strength_context_or_wrong_policy":
            chain.pop("strength_context")
        path = (
            "day_master.stem"
            if tool == "analyze_destiny"
            else (
                "bazi_birth.four_pillars.day.stem"
                if tool == "bazi_birth"
                else tool.removeprefix("bazi_") + "_analysis.evidence_chain.method_id"
            )
        )
    punishment = next(e for e in target if e["kind"] == "刑")
    assert punishment["status"] == "active"
    punishment["status"] = "resolved_by_combination"
    original = execution.execute_spec

    def broken(actual, request):
        if actual.key == tool:
            actual = replace(actual, bind=lambda _: (lambda: deepcopy(payload), (), {}))
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
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
    assert all(v["error_code"] == "internal_error" for v in actual.values())
    assert all(
        len(json.dumps(v, ensure_ascii=False, separators=(",", ":"))) <= 8192
        for v in actual.values()
    )
