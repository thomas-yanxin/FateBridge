"""Traveler and lost-property chapters across REST, MCP, CLI and same-run paging."""

import json
import os
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from mcp.shared.exceptions import MCPError

from fatebridge.application.examples import suggested_fields
from fatebridge.core.public_output import same_public_value
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from tests.fixtures.mcp_result_delivery import read_full_result
from tests.support.transports import SPECS, call_cli, rest

TOPICS = [
    ("traveler", "MEIHUA_V53_EXPECTED_PACKAGE_ROOT"),
    ("lost_property", "MEIHUA_V48_EXPECTED_PACKAGE_ROOT"),
]

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
@pytest.mark.parametrize("topic,package_env", TOPICS)
@pytest.mark.asyncio
async def test_new_branch_domain_and_three_transports_agree(
    topic, package_env, tool, arguments, rest, capsys, tmp_path
):
    arguments = {**arguments, "interpretation_topic": topic}
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
        assert same_public_value(output["interpretation"]["topic_reading"], expected)
        assert same_public_value(
            output["interpretation"]["casting_readings"],
            domain["interpretation"]["casting_readings"],
        )
        assert same_public_value(
            output["interpretation"]["casting_comparison"],
            domain["interpretation"]["casting_comparison"],
        )
    assert FIELD not in suggested_fields(spec)
    for view in ["reading", "topic", "topic_audit"]:
        assert FIELD in suggested_fields(spec, view=view)


@pytest.mark.parametrize("topic,package_env", TOPICS)
@pytest.mark.asyncio
async def test_fresh_stdio_schema_and_topic_fields_accept_the_new_enum(
    topic,
    package_env,
    tmp_path,
):
    root = Path(__file__).resolve().parents[2]
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "fatebridge.mcp_server"],
        cwd=str(root),
        env={
            "PYTHONPATH": os.environ.get(package_env, str(root / "src")),
        },
        log_file=tmp_path / "stdio.log",
    )
    async with Client(transport) as client:
        tools = {t.name: t for t in await client.list_tools()}
        for name, args in [CASES[0], CASES[3]]:
            schema = tools[name].inputSchema
            assert topic in schema["properties"]["interpretation_topic"]["enum"]
            reply = await client.call_tool(
                name,
                {
                    **args,
                    "interpretation_topic": topic,
                    "fields": suggested_fields(SPECS[name], view="topic"),
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
                == f"meihua_{topic}_nlc1925_v1"
            )
            assert payload["run_metadata"]["run_id"]
            assert (
                payload["interpretation"]["topic_reading"]["chapter_qualifications"][
                    "real_location"
                ]
                is None
            )


@pytest.mark.parametrize("tool,arguments", [CASES[0], CASES[2], CASES[3]])
@pytest.mark.parametrize("topic,package_env", TOPICS)
@pytest.mark.asyncio
async def test_bounded_topic_projection_restores_same_run_complete_evidence(
    topic, package_env, tool, arguments, tmp_path
):
    root = Path(__file__).resolve().parents[2]
    package = os.environ.get(package_env, str(root / "src"))
    arguments = {**arguments, "interpretation_topic": topic}
    expected = (
        calculate_meihua_cast if tool == "meihua_cast" else calculate_meihua_analysis
    )(**arguments)
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "fatebridge.mcp_server"],
        cwd=str(root),
        env={
            "PYTHONPATH": package,
        },
        log_file=tmp_path / "stdio.log",
    )
    async with Client(transport) as client:
        reply = await client.call_tool(
            tool,
            {
                **arguments,
                "fields": suggested_fields(SPECS[tool], view="topic"),
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
        restored = await read_full_result(client, payload)
        if tool == "meihua_analysis":
            assert expected["interpretation"]["casting_readings"] == []
            field_uri = f"fatebridge://results/{delivery['result_id']}/verified/{run}/fields/interpretation.casting_readings"
            page = json.loads((await client.read_resource(f"{field_uri}/0"))[0].text)
            assert json.loads(page["text"]) == []
            with pytest.raises(MCPError, match="结果字段路径不存在"):
                await client.read_resource(f"{field_uri}.0/0")
        for field in [FIELD, "interpretation.casting_readings"]:
            assert same_public_value(
                restored["interpretation"][field.split(".")[1]],
                expected["interpretation"][field.split(".")[1]],
            )
