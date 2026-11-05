"""Invalid duty facts cannot hide behind an unrelated projection on any entry."""

import asyncio
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

import fatebridge.application.execution as execution
from tests.support.bazi_month_command_faults import (
    perturb,
)
from tests.support.transports import AS_OF, SPECS, call_cli, native
from tests.support.transports import rest as rest_fixture

rest = rest_fixture
ROOT = Path(__file__).resolve().parents[2]
DATA = {
    "cases": json.loads(
        (ROOT / "tests/data/bazi/month-command-transport-inputs.json").read_text()
    )
}


def evidence(payload, tool):
    if tool == "analyze_destiny":
        return payload["structure_profile"]["evidence_chain"]
    if tool == "bazi_birth":
        return payload["bazi_birth"]["structure_profile"]["evidence_chain"]
    return payload[tool.removeprefix("bazi_") + "_analysis"]["evidence_chain"]


@pytest.mark.parametrize("case", DATA["cases"], ids=lambda c: c["tool"])
@pytest.mark.parametrize(
    "fault", ["invented_duty", "false_duration_sum", "mixed_witness_month"]
)
def test_wrong_full_month_facts_fail_before_unrelated_projection(
    case, fault, rest, monkeypatch, tmp_path, capsys
):
    tool = case["tool"]
    spec = SPECS[tool]
    from fatebridge.core.execution_context import ExecutionOptions

    payload = execution.execute_tool(
        spec,
        spec.request_model(**case["arguments"]),
        options=ExecutionOptions(as_of=AS_OF),
        include_metadata=False,
    )
    chain = evidence(payload, tool)
    changed = perturb(chain, fault)
    chain.clear()
    chain.update(changed)
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
        json.dumps(actual, ensure_ascii=False, indent=2) + "\n"
    )
    assert all(
        len(json.dumps(value, ensure_ascii=False, separators=(",", ":"))) <= 8192
        for value in actual.values()
    )
    assert (
        (response is None or response.status_code == 500)
        and protocol.is_error
        and code == 1
    )
    assert (
        protocol.structured_content["error_code"]
        == cli["error_code"]
        == "internal_error"
    )
    if response is not None:
        assert response.json()["error_code"] == "internal_error"
