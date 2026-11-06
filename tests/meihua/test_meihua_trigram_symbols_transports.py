"""Actual shared REST/MCP/CLI evidence and a fresh stdio server, no models."""

import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from tests.support.transports import SPECS, call_cli, rest

CASES = [
    (
        "meihua_cast",
        {
            "casting": {
                "method": "existing",
                "hexagram_code": "010111",
                "moving_line": 4,
            }
        },
    ),
    (
        "meihua_cast",
        {
            "casting": {
                "method": "existing",
                "hexagram_code": "010110",
                "moving_line": 4,
            },
            "interpretation_topic": "wealth",
            "season_month_branch": "申",
        },
    ),
    (
        "meihua_cast",
        {
            "casting": {
                "method": "existing",
                "hexagram_code": "000011",
                "moving_line": 4,
            }
        },
    ),
    (
        "meihua_cast",
        {
            "casting": {
                "method": "sound_groups",
                "first_count": 11,
                "second_count": 1,
                "hour_branch": "子",
            },
            "season_month_branch": "申",
        },
    ),
    (
        "meihua_cast",
        {
            "casting": {
                "method": "existing",
                "hexagram_code": "111111",
                "moving_line": 3,
            },
            "interpretation_topic": "travel",
        },
    ),
    (
        "meihua_cast",
        {
            "casting": {
                "method": "existing",
                "hexagram_code": "001010",
                "moving_line": 4,
            },
            "interpretation_topic": "weather",
        },
    ),
    (
        "meihua_analysis",
        {
            "analysis_year": 2026,
            "analysis_month": 2,
            "analysis_day": 5,
            "analysis_hour": 12,
            "analysis_timezone": "Asia/Shanghai",
        },
    ),
    (
        "meihua_analysis",
        {
            "analysis_year": 2026,
            "analysis_month": 10,
            "analysis_day": 26,
            "analysis_hour": 23,
            "analysis_timezone": "Asia/Shanghai",
            "interpretation_topic": "reputation",
        },
    ),
]
FIELD = "interpretation.trigram_relation_symbols"


@pytest.mark.parametrize("tool,arguments", CASES)
@pytest.mark.asyncio
async def test_shared_projection_matches_domain_for_all_three_transports(
    tool, arguments, rest, capsys, tmp_path
):
    expected = (
        calculate_meihua_cast if tool == "meihua_cast" else calculate_meihua_analysis
    )(**arguments)["interpretation"]["trigram_relation_symbols"]
    request = {
        **arguments,
        "fields": [FIELD],
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    spec = SPECS[tool]
    response = rest.post(
        spec.rest_path,
        json=arguments,
        params=[
            ("fields", FIELD),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    assert response.status_code == 200, response.text
    assert response.json()["interpretation"]["trigram_relation_symbols"] == expected
    async with Client(create_mcp_app()) as client:
        reply = await client.call_tool(tool, request, raise_on_error=False)
        assert not reply.is_error
        assert (
            reply.structured_content["interpretation"]["trigram_relation_symbols"]
            == expected
        )
    code, actual = call_cli(
        spec,
        arguments,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            FIELD,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert code == 0
    assert actual["interpretation"]["trigram_relation_symbols"] == expected


@pytest.mark.asyncio
async def test_fresh_stdio_advertises_and_projects_the_new_evidence_card(tmp_path):
    root = Path(__file__).resolve().parents[2]
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "fatebridge.mcp_server"],
        cwd=str(root),
        env={
            "PYTHONPATH": str(root / "src"),
        },
        log_file=tmp_path / "stdio.log",
    )
    async with Client(transport) as client:
        tools = {t.name: t for t in await client.list_tools()}
        assert "meihua_cast" in tools and "meihua_analysis" in tools
        for tool, arguments in [CASES[0], CASES[6]]:
            reply = await client.call_tool(
                tool,
                {
                    **arguments,
                    "fields": [FIELD],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
                raise_on_error=False,
            )
            assert not reply.is_error
            payload = reply.structured_content
            assert (
                payload["interpretation"]["trigram_relation_symbols"]["ruleset_id"]
                == "meihua_trigram_relation_symbols_nlc1925_v1"
            )
            assert payload["run_metadata"]["run_id"]
