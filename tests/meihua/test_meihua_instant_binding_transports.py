"""Corrupt clock facts cannot be hidden by selecting unrelated output fields."""

from copy import deepcopy
from dataclasses import replace

import pytest

from fatebridge.application import execution
from tests.meihua.test_meihua_instant_binding import original
from tests.support.meihua_instant_binding_reference import load, mutate
from tests.support.transports import SPECS, rest, surface_calls

CASES, PROTOCOL = load()
SPEC = SPECS["meihua_analysis"]
BY_ID = {r["id"]: r for r in CASES}


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_valid_declared_moments_keep_one_cross_transport_business_receipt(
    case, surface_calls
):
    from tests.support.transports import business

    fields = [
        "analysis_context",
        "calendar_context.bazi_month_boundary",
        "meihua.calendar_policy.civil_clock_resolution",
        "summary",
    ]
    response, mcp, code, cli = surface_calls(
        SPEC,
        case["arguments"],
        projection={
            **{"fields": fields, "strict_fields": True},
            "response_char_limit": 0,
        },
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
    fault, monkeypatch, surface_calls
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
    response, mcp, code, cli = surface_calls(
        SPEC,
        args,
        params={
            "fields": "analysis_type",
            "strict_fields": "true",
            "trace_id": "instant-fault",
        },
        options={
            "fields": ["analysis_type"],
            "strict_fields": True,
            "trace_id": "instant-fault",
        },
        flags=[
            "--fields",
            "analysis_type",
            "--strict-fields",
            "true",
            "--trace-id",
            "instant-fault",
        ],
        cli_first=False,
    )
    assert response.status_code == 500 and mcp.is_error and code == 1
    for result in [response.json(), mcp.structured_content, cli]:
        assert result["error_code"] == "internal_error" and result["retryable"] is True
        assert result["trace_id"] == "instant-fault"
