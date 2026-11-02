"""The actual REST/MCP/CLI paths keep every full packet's declared outcome."""

import asyncio
from copy import deepcopy
from dataclasses import replace

import pytest

from fatebridge.application import execution
from tests.meihua_iso_clock_reference import load, load_supplement
from tests.test_agentic_nested_outputs import SPECS, call_cli, native, rest

_, PACKETS = load()
PACKETS += load_supplement()
SPEC = SPECS["meihua_analysis"]


@pytest.mark.parametrize("row", PACKETS, ids=lambda r: r["id"])
def test_iso_clock_validation_precedes_projection_across_transports(
    row, rest, monkeypatch, tmp_path, capsys
):
    original = execution.execute_spec

    def inject(spec, request):
        if spec.key == "meihua_analysis":
            spec = replace(
                spec, bind=lambda _: (lambda: deepcopy(row["packet"]), (), {})
            )
        return original(spec, request)

    monkeypatch.setattr(execution, "execute_spec", inject)
    response = rest.post(
        SPEC.rest_path,
        json=row["request"],
        params={
            "fields": "analysis_type",
            "strict_fields": "true",
            "trace_id": "iso-clock",
        },
    )
    reply = asyncio.run(
        native(
            SPEC,
            row["request"],
            fields=["analysis_type"],
            strict_fields=True,
            trace_id="iso-clock",
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
            "iso-clock",
        ],
    )
    if row["should_succeed"]:
        assert response.status_code == 200 and not reply.is_error and code == 0
        for result in [response.json(), reply.structured_content, cli]:
            assert (
                result["analysis_type"] == row["packet"]["analysis_type"]
                and "error" not in result
            )
    else:
        assert response.status_code == 500 and reply.is_error and code == 1
        for result in [response.json(), reply.structured_content, cli]:
            assert (
                result["error_code"] == "internal_error"
                and result["retryable"] is True
                and result["trace_id"] == "iso-clock"
            )
