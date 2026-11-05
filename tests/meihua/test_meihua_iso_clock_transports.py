"""The actual REST/MCP/CLI paths keep every full packet's declared outcome."""

from copy import deepcopy
from dataclasses import replace

import pytest

from fatebridge.application import execution
from tests.support.meihua_iso_clock_reference import load, load_supplement
from tests.support.transports import SPECS, rest, surface_calls

_, PACKETS = load()
PACKETS += load_supplement()
SPEC = SPECS["meihua_analysis"]


@pytest.mark.parametrize("row", PACKETS, ids=lambda r: r["id"])
def test_iso_clock_validation_precedes_projection_across_transports(
    row, monkeypatch, surface_calls
):
    original = execution.execute_spec

    def inject(spec, request):
        if spec.key == "meihua_analysis":
            spec = replace(
                spec, bind=lambda _: (lambda: deepcopy(row["packet"]), (), {})
            )
        return original(spec, request)

    monkeypatch.setattr(execution, "execute_spec", inject)
    response, reply, code, cli = surface_calls(
        SPEC,
        row["request"],
        params={
            "fields": "analysis_type",
            "strict_fields": "true",
            "trace_id": "iso-clock",
        },
        options={
            "fields": ["analysis_type"],
            "strict_fields": True,
            "trace_id": "iso-clock",
        },
        flags=[
            "--fields",
            "analysis_type",
            "--strict-fields",
            "true",
            "--trace-id",
            "iso-clock",
        ],
        cli_first=False,
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
