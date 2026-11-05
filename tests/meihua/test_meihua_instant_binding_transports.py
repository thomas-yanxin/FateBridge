"""Corrupt clock facts cannot be hidden by selecting unrelated output fields."""

import asyncio
from copy import deepcopy
from dataclasses import replace

import pytest

from fatebridge.application import execution
from tests.evaluation.test_agentic_nested_outputs import SPECS, call_cli, native, rest
from tests.meihua.test_meihua_instant_binding import original
from tests.support.meihua_instant_binding_reference import load, mutate, new_result

CASES, PROTOCOL = load()
SPEC = SPECS["meihua_analysis"]
BY_ID = {r["id"]: r for r in CASES}


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_valid_declared_moments_keep_one_cross_transport_business_receipt(
    case, rest, tmp_path, capsys
):
    from tests.evaluation.test_agentic_nested_outputs import business

    fields = [
        "analysis_context",
        "calendar_context.bazi_month_boundary",
        "meihua.calendar_policy.civil_clock_resolution",
        "summary",
    ]
    response = rest.post(
        SPEC.rest_path,
        json=case["arguments"],
        params=[
            *(("fields", f) for f in fields),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
        ],
    )
    code, cli = call_cli(
        SPEC,
        case["arguments"],
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
        ],
    )
    mcp = asyncio.run(
        native(SPEC, case["arguments"], fields=fields, strict_fields=True)
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    assert (
        len(
            {
                v["run_metadata"]["input_sha256"]
                for v in [response.json(), cli, mcp.structured_content]
            }
        )
        == 1
    )
    for value in [response.json(), cli, mcp.structured_content]:
        clock = value["meihua"]["calendar_policy"]["civil_clock_resolution"]
        assert (
            clock["instant_utc"] == case["expected_utc"]
            and clock["fold"] == case["expected_fold"]
        )


@pytest.mark.parametrize("fault", PROTOCOL["faults"], ids=lambda c: c["id"])
def test_clock_faults_are_rejected_before_projection_on_all_real_transports(
    fault, rest, monkeypatch, tmp_path, capsys
):
    req, value = original(fault["base_case"])
    bad = mutate(value, fault["id"])
    real = execution.execute_spec

    def injected(actual, request):
        if actual.key == "meihua_analysis":
            actual = replace(actual, bind=lambda _: (lambda: deepcopy(bad), (), {}))
        return real(actual, request)

    monkeypatch.setattr(execution, "execute_spec", injected)
    args = BY_ID[fault["base_case"]]["arguments"]
    response = rest.post(
        SPEC.rest_path,
        json=args,
        params={
            "fields": "analysis_type",
            "strict_fields": "true",
            "trace_id": "instant-fault",
        },
    )
    mcp = asyncio.run(
        native(
            SPEC,
            args,
            fields=["analysis_type"],
            strict_fields=True,
            trace_id="instant-fault",
        )
    )
    code, cli = call_cli(
        SPEC,
        args,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            "analysis_type",
            "--strict-fields",
            "true",
            "--trace-id",
            "instant-fault",
        ],
    )
    assert response.status_code == 500 and mcp.is_error and code == 1
    for result in [response.json(), mcp.structured_content, cli]:
        assert result["error_code"] == "internal_error" and result["retryable"] is True
        assert result["trace_id"] == "instant-fault"
