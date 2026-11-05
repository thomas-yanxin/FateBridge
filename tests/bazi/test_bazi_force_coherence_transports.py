"""Same-receipt contradictions fail before projection across all BaZi entries."""

import asyncio
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

import fatebridge.application.execution as execution
from tests.evaluation.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
)
from tests.evaluation.test_agentic_nested_outputs import rest as shared_rest_fixture

rest = shared_rest_fixture
ROOT = Path(__file__).resolve().parents[2]
ROWS = json.loads((ROOT / "tests/data/bazi/force-coherence-inputs.json").read_text())


def evidence(result, tool):
    if tool == "analyze_destiny":
        return result["structure_profile"]["evidence_chain"]
    if tool == "bazi_birth":
        return result["bazi_birth"]["structure_profile"]["evidence_chain"]
    return result[tool.removeprefix("bazi_") + "_analysis"]["evidence_chain"]


def projection(tool):
    if tool == "analyze_destiny":
        return "day_master.stem"
    if tool == "bazi_birth":
        return "bazi_birth.four_pillars.day.stem"
    return tool.removeprefix("bazi_") + "_analysis.evidence_chain.method_id"


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["tool"])
@pytest.mark.parametrize("fault", ["wrong_share", "mixed_method"])
def test_inconsistent_full_force_packet_cannot_hide_behind_unrelated_projection(
    row, fault, rest, monkeypatch, tmp_path, capsys
):
    tool = row["tool"]
    spec = SPECS[tool]
    from tests.bazi.test_bazi_complete_anchors import base

    payload = deepcopy(base(tool)["result"])
    force = evidence(payload, tool)["force_components"]["engineering_composition"]
    if fault == "wrong_share":
        force["body_within_support_share"] = (
            0.75 if force["body_within_support_share"] != 0.75 else 0.25
        )
    else:
        force["strength_method_id"] = "stale-other-assessment"
    original = execution.execute_spec

    def broken_output(actual, request):
        if actual.key == tool:
            actual = replace(actual, bind=lambda _: (lambda: deepcopy(payload), (), {}))
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", broken_output)
    path = projection(tool)
    values = row["arguments"]
    response = (
        rest.post(
            spec.rest_path,
            json=values,
            params={
                "as_of": AS_OF,
                "fields": path,
                "strict_fields": True,
                "trace_id": "force-fault",
            },
        )
        if spec.rest_path is not None
        else None
    )
    protocol = asyncio.run(
        native(spec, values, fields=[path], strict_fields=True, trace_id="force-fault")
    )
    code, cli = call_cli(
        spec,
        values,
        tmp_path,
        capsys,
        ["--fields", path, "--strict-fields", "true", "--trace-id", "force-fault"],
    )
    actual = [
        ("mcp", protocol.structured_content),
        ("cli", cli),
    ]
    if response is not None:
        actual.append(("rest", response.json()))
    for name, value in actual:
        (tmp_path / (name + "-actual-response.json")).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n"
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


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["tool"])
def test_healthy_force_and_narrow_partial_readings_survive_all_three_surfaces(
    row, rest, tmp_path, capsys
):
    tool = row["tool"]
    spec = SPECS[tool]
    values = row["arguments"]
    path = projection(tool)
    response = (
        rest.post(
            spec.rest_path,
            json=values,
            params={"as_of": AS_OF, "fields": path, "strict_fields": True},
        )
        if spec.rest_path is not None
        else None
    )
    protocol = asyncio.run(native(spec, values, fields=[path], strict_fields=True))
    code, cli = call_cli(
        spec, values, tmp_path, capsys, ["--fields", path, "--strict-fields", "true"]
    )
    assert (
        (response is None or response.status_code == 200)
        and not protocol.is_error
        and code == 0
    )
    assert business(protocol.structured_content) == business(cli)
    if response is not None:
        assert business(response.json()) == business(cli)
