"""Use the real three transports; replace only the domain packet producer."""

from copy import deepcopy
from dataclasses import replace

import pytest

from fatebridge.application import execution
from tests.support.meihua_fractional_binding_reference import load
from tests.support.transports import SPECS, rest, surface_calls

PACKETS, _ = load()
SPEC = SPECS["meihua_analysis"]


@pytest.mark.parametrize("row", PACKETS, ids=lambda r: r["id"])
def test_fractional_clock_validation_precedes_projection_on_every_transport(
    row, monkeypatch, surface_calls
):
    original = execution.execute_spec

    def injected(actual, request):
        if actual.key == "meihua_analysis":
            actual = replace(
                actual, bind=lambda _: (lambda: deepcopy(row["packet"]), (), {})
            )
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", injected)
    response, mcp, code, cli = surface_calls(
        SPEC,
        row["request"],
        params={
            "fields": "analysis_type",
            "strict_fields": "true",
            "trace_id": "fractional-clock",
        },
        options={
            "fields": ["analysis_type"],
            "strict_fields": True,
            "trace_id": "fractional-clock",
        },
        flags=[
            "--fields",
            "analysis_type",
            "--strict-fields",
            "true",
            "--trace-id",
            "fractional-clock",
        ],
        cli_first=False,
    )
    if row["should_succeed"]:
        assert response.status_code == 200 and code == 0 and not mcp.is_error
        for value in [response.json(), mcp.structured_content, cli]:
            assert value["analysis_type"] == row["packet"]["analysis_type"]
            assert "error" not in value
    else:
        assert response.status_code == 500 and code == 1 and mcp.is_error
        for value in [response.json(), mcp.structured_content, cli]:
            assert (
                value["error_code"] == "internal_error" and value["retryable"] is True
            )
            assert value["trace_id"] == "fractional-clock"
