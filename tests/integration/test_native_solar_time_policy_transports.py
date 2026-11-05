"""Actual native civil policy on REST, CLI, stdio MCP and strict projection."""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from tests.support.transports import SPECS, business, call_cli

pytest_plugins = ["tests.evaluation.test_agentic_nested_outputs"]

ROOT = Path(
    os.environ.get("FATEBRIDGE_TEST_SOURCE_ROOT", Path(__file__).resolve().parents[2])
)


async def stdio(payload, options, log):
    transport = StdioTransport(
        command=sys.executable,
        args=["-X", "utf8", "-m", "fatebridge.mcp_server"],
        cwd=str(ROOT),
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT / "src"),
            "FATEBRIDGE_MCP_TOOL_SCOPE": "complete",
            "FATEBRIDGE_MCP_FAMILIES": "",
            "FATEBRIDGE_MCP_SCENARIOS": "",
        },
        log_file=log,
    )
    async with Client(transport) as client:
        return await client.call_tool(
            SPECS["sixyao"].tool_name, {**payload, **options}, raise_on_error=False
        )


@pytest.mark.parametrize(
    "year,historical,future",
    [(1700, True, False), (1972, False, False), (2300, False, True)],
)
@pytest.mark.parametrize("project", [False, True])
def test_actual_three_protocol_native_policy(
    year, historical, future, project, monkeypatch, rest, tmp_path, capsys
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    spec = SPECS["sixyao"]
    payload = dict(
        date=f"{year}-06-01",
        time="12:00:00",
        zone="UTC",
        gua_code="111111",
        timing_days=0,
    )
    options = dict(response_char_limit=0, include_snapshot_text=False)
    flags = ["--response-char-limit", "0", "--include-snapshot-text", "false"]
    if project:
        options.update(fields=["calendar_context"], strict_fields=True)
        flags += ["--fields", "calendar_context", "--strict-fields", "true"]
    response = rest.post(spec.rest_path, json=payload, params=options)
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(stdio(payload, options, tmp_path / "native-policy-mcp.log"))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), cli, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        spec.output_model.model_validate(output)
        calendar = output["calendar_context"]
        for term in [
            calendar["current_solar_term"],
            calendar["next_solar_term"],
            calendar["bazi_month_boundary"]["start_term"],
            calendar["bazi_month_boundary"]["next_term"],
        ]:
            details = term["solar_model_details"]
            assert term["ephemeris_model"] == details["ephemeris_model"] == "moshier"
            assert details["historical_ut1_convention"] is historical
            assert details["future_leap_seconds_assumed_unchanged"] is future
            assert details["accuracy_certified"] is False
    evidence = os.environ.get("FATEBRIDGE_TEST_EVIDENCE")
    if evidence:
        target = Path(evidence)
        target.mkdir(exist_ok=True)
        (target / f"native-{year}-{project}.json").write_text(
            json.dumps(outputs, ensure_ascii=False, indent=2) + "\n"
        )
