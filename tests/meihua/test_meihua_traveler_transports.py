"""Selected traveler chapter across REST, MCP and CLI; no model executions."""

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from mcp.shared.exceptions import MCPError

from fatebridge.application.examples import suggested_fields
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from tests.support.transports import SPECS, call_cli, rest

FIELD = "interpretation.topic_reading"
CASES = [
    (
        "meihua_cast",
        {
            "casting": {
                "method": "existing",
                "hexagram_code": "111111",
                "moving_line": 1,
            }
        },
    ),
    (
        "meihua_cast",
        {
            "casting": {
                "method": "existing",
                "hexagram_code": "111111",
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
            }
        },
    ),
    (
        "meihua_analysis",
        {
            "analysis_year": 2026,
            "analysis_month": 10,
            "analysis_day": 26,
            "analysis_hour": 12,
            "analysis_timezone": "Asia/Shanghai",
        },
    ),
]


@pytest.mark.parametrize("tool,arguments", CASES)
@pytest.mark.asyncio
async def test_new_branch_domain_and_three_transports_agree(
    tool, arguments, rest, capsys, tmp_path
):
    arguments = {**arguments, "interpretation_topic": "traveler"}
    domain = (
        calculate_meihua_cast if tool == "meihua_cast" else calculate_meihua_analysis
    )(**arguments)
    expected = domain["interpretation"]["topic_reading"]
    fields = [
        FIELD,
        "interpretation.casting_readings",
        "interpretation.casting_comparison",
    ]
    spec = SPECS[tool]
    request = {
        **arguments,
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    params = [("fields", f) for f in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", "0"),
    ]
    response = rest.post(spec.rest_path, json=arguments, params=params)
    assert response.status_code == 200, response.text
    async with Client(create_mcp_app()) as client:
        reply = await client.call_tool(tool, request, raise_on_error=False)
    assert not reply.is_error
    code, local = call_cli(
        spec,
        arguments,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert code == 0
    for output in [response.json(), reply.structured_content, local]:
        assert output["interpretation"]["topic_reading"] == expected
        assert (
            output["interpretation"]["casting_readings"]
            == domain["interpretation"]["casting_readings"]
        )
        assert (
            output["interpretation"]["casting_comparison"]
            == domain["interpretation"]["casting_comparison"]
        )
    for view in [None, "reading", "topic", "topic_audit"]:
        assert FIELD in suggested_fields(spec, view=view)


@pytest.mark.asyncio
async def test_fresh_stdio_schema_and_actual_default_fields_accept_the_new_enum(
    tmp_path,
):
    root = Path(__file__).resolve().parents[2]
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "fatebridge.mcp_server"],
        cwd=str(root),
        env={
            "PYTHONPATH": os.environ.get(
                "MEIHUA_V53_EXPECTED_PACKAGE_ROOT", str(root / "src")
            ),
            "FATEBRIDGE_MCP_SCENARIOS": "onda-zhanbu",
            "FATEBRIDGE_MCP_TOOL_SCOPE": "topic",
        },
        log_file=tmp_path / "stdio.log",
    )
    async with Client(transport) as client:
        tools = {t.name: t for t in await client.list_tools()}
        for name, args in [CASES[0], CASES[3]]:
            schema = tools[name].inputSchema
            assert "traveler" in schema["properties"]["interpretation_topic"]["enum"]
            reply = await client.call_tool(
                name,
                {
                    **args,
                    "interpretation_topic": "traveler",
                    "fields": suggested_fields(SPECS[name]),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
                raise_on_error=False,
            )
            assert not reply.is_error
            payload = reply.structured_content
            assert (
                payload["interpretation"]["topic_reading"]["ruleset_id"]
                == "meihua_traveler_nlc1925_v1"
            )
            assert payload["run_metadata"]["run_id"]
            assert (
                payload["interpretation"]["topic_reading"]["chapter_qualifications"][
                    "real_location"
                ]
                is None
            )


@pytest.mark.parametrize("tool,arguments", [CASES[0], CASES[2], CASES[3]])
@pytest.mark.asyncio
async def test_bounded_default_projection_restores_same_run_complete_evidence(
    tool, arguments, tmp_path
):
    root = Path(__file__).resolve().parents[2]
    package = os.environ.get("MEIHUA_V53_EXPECTED_PACKAGE_ROOT", str(root / "src"))
    arguments = {**arguments, "interpretation_topic": "traveler"}
    expected = (
        calculate_meihua_cast if tool == "meihua_cast" else calculate_meihua_analysis
    )(**arguments)
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "fatebridge.mcp_server"],
        cwd=str(root),
        env={
            "PYTHONPATH": package,
            "FATEBRIDGE_MCP_SCENARIOS": "onda-zhanbu",
            "FATEBRIDGE_MCP_TOOL_SCOPE": "topic",
        },
        log_file=tmp_path / "stdio.log",
    )
    async with Client(transport) as client:
        reply = await client.call_tool(
            tool,
            {
                **arguments,
                "fields": suggested_fields(SPECS[tool]),
                "strict_fields": True,
                "include_snapshot_text": False,
                "response_char_limit": 4096,
            },
            raise_on_error=False,
        )
        assert not reply.is_error
        payload = reply.structured_content
        delivery = payload["result_delivery"]
        run = payload["run_metadata"]["run_id"]
        fields_to_restore = [FIELD]
        if "interpretation.casting_readings" in suggested_fields(SPECS[tool]):
            fields_to_restore.append("interpretation.casting_readings")
        else:
            # Delivery retains the requested projection. Time casts have no
            # count alternatives, and their default card omits this empty list.
            assert tool == "meihua_analysis"
            assert expected["interpretation"]["casting_readings"] == []
            uri = f"fatebridge://results/{delivery['result_id']}/verified/{run}/{delivery['sha256']}/fields/interpretation.casting_readings/0"
            with pytest.raises(MCPError, match="结果字段路径不存在"):
                await client.read_resource(uri)
        for field in fields_to_restore:
            uri = f"fatebridge://results/{delivery['result_id']}/verified/{run}/{delivery['sha256']}/fields/{field}/0"
            fragments = []
            checksum = None
            offset = 0
            while uri:
                page = json.loads((await client.read_resource(uri))[0].text)
                assert page["offset"] == offset and page["path"] == field
                assert page["result_id"] == delivery["result_id"]
                assert page["verification"]["run_id"] == run
                assert page["verification"]["payload_sha256"] == delivery["sha256"]
                assert page["verification"]["calculation_repeated"] is False
                checksum = page["sha256"] if checksum is None else checksum
                assert checksum == page["sha256"]
                fragments.append(page["text"])
                offset += len(page["text"])
                following = page["next_offset"]
                assert following is None or following == offset
                uri = (
                    uri.rsplit("/", 1)[0] + "/" + str(following)
                    if following is not None
                    else None
                )
            restored = "".join(fragments)
            assert hashlib.sha256(restored.encode()).hexdigest() == checksum
            assert (
                json.loads(restored) == expected["interpretation"][field.split(".")[1]]
            )
