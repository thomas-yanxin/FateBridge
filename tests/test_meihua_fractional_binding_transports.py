"""Use the real three transports; replace only the domain packet producer."""

import asyncio
from copy import deepcopy
from dataclasses import replace

import pytest

from fatebridge.application import execution
from tests.meihua_fractional_binding_reference import load
from tests.test_agentic_nested_outputs import SPECS, call_cli, native, rest

PACKETS, _ = load()
SPEC = SPECS["meihua_analysis"]


@pytest.mark.parametrize("row", PACKETS, ids=lambda r: r["id"])
def test_fractional_clock_validation_precedes_projection_on_every_transport(
    row, rest, monkeypatch, tmp_path, capsys
):
    original = execution.execute_spec

    def injected(actual, request):
        if actual.key == "meihua_analysis":
            actual = replace(
                actual, bind=lambda _: (lambda: deepcopy(row["packet"]), (), {})
            )
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", injected)
    response = rest.post(
        SPEC.rest_path,
        json=row["request"],
        params={
            "fields": "analysis_type",
            "strict_fields": "true",
            "trace_id": "fractional-clock",
        },
    )
    mcp = asyncio.run(
        native(
            SPEC,
            row["request"],
            fields=["analysis_type"],
            strict_fields=True,
            trace_id="fractional-clock",
        )
    )
    code, cli = call_cli(
        SPEC,
        row["request"],
        tmp_path,
        capsys,
        flags=[
            "--fields",
            "analysis_type",
            "--strict-fields",
            "true",
            "--trace-id",
            "fractional-clock",
        ],
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
