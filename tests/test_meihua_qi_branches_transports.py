"""Chapter-selected time-unit atoms across REST, MCP, CLI and same-run paging."""

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from fatebridge.application.examples import suggested_fields
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from tests.test_agentic_nested_outputs import SPECS, call_cli, rest  # noqa: F401

FIELD = "interpretation.topic_reading"
CASES = [
    (
        "meihua_cast",
        {
            "casting": {
                "method": "existing",
                "hexagram_code": "000111",
                "moving_line": 1,
            },
            "interpretation_topic": "wealth",
        },
    ),
    (
        "meihua_cast",
        {
            "casting": {
                "method": "sound_groups",
                "first_count": 11,
                "second_count": 1,
                "hour_branch": "申",
            },
            "interpretation_topic": "wealth",
            "season_month_branch": "辰",
            "day_qi_context": {"label": "合成未日", "day_branch": "未"},
        },
    ),
    (
        "meihua_cast",
        {
            "casting": {
                "method": "lunar_time_added_count",
                "year_branch": "巳",
                "lunar_month": 12,
                "lunar_day": 29,
                "hour_branch": "子",
                "added_count": 1,
            },
            "interpretation_topic": "reputation",
            "reputation_context": {"label": "合成非在任", "currently_in_office": False},
        },
    ),
    (
        "meihua_cast",
        {
            "casting": {
                "method": "existing",
                "hexagram_code": "101111",
                "moving_line": 1,
            },
            "interpretation_topic": "reputation",
            "season_month_branch": "申",
            "day_qi_context": {"label": "合成辰日", "day_branch": "辰"},
            "reputation_context": {"label": "合成在任", "currently_in_office": True},
        },
    ),
    (
        "meihua_analysis",
        {
            "analysis_year": 2026,
            "analysis_month": 2,
            "analysis_day": 16,
            "analysis_hour": 23,
            "analysis_timezone": "Asia/Shanghai",
            "interpretation_topic": "wealth",
        },
    ),
]


def calculate(tool, args):
    return (
        calculate_meihua_cast if tool == "meihua_cast" else calculate_meihua_analysis
    )(**args)


def stdio(tmp_path):
    root = Path(__file__).resolve().parents[1]
    return StdioTransport(
        command=sys.executable,
        args=["-m", "fatebridge.mcp_server"],
        cwd=str(root),
        env={
            "PYTHONPATH": os.environ.get(
                "MEIHUA_V57_EXPECTED_PACKAGE_ROOT", str(root / "src")
            ),
            "FATEBRIDGE_MCP_SCENARIOS": "onda-zhanbu",
            "FATEBRIDGE_MCP_TOOL_SCOPE": "topic",
        },
        log_file=tmp_path / "stdio.log",
    )


@pytest.mark.parametrize("tool,arguments", CASES)
@pytest.mark.asyncio
async def test_own_time_unit_labels_role_conditions_and_candidates_agree_on_three_transports(
    tool, arguments, rest, capsys, tmp_path
):
    domain = calculate(tool, arguments)
    fields = [
        FIELD,
        "interpretation.casting_readings",
        "interpretation.day_qi",
        "summary",
    ]
    assert (
        domain["interpretation"]["topic_reading"]["qi_branch_timing_reference"][
            "event_time"
        ]
        is None
    )
    params = [("fields", f) for f in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", "0"),
    ]
    response = rest.post(SPECS[tool].rest_path, json=arguments, params=params)
    assert response.status_code == 200, response.text
    async with Client(create_mcp_app()) as client:
        reply = await client.call_tool(
            tool,
            {
                **arguments,
                "fields": fields,
                "strict_fields": True,
                "include_snapshot_text": False,
                "response_char_limit": 0,
            },
            raise_on_error=False,
        )
    assert not reply.is_error
    code, cli = call_cli(
        SPECS[tool],
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
    for output in [response.json(), reply.structured_content, cli]:
        for field in ["topic_reading", "casting_readings", "day_qi"]:
            assert output["interpretation"][field] == domain["interpretation"][field]
        assert output["summary"] == domain["summary"]


@pytest.mark.asyncio
async def test_fresh_stdio_published_topic_cards_include_complete_new_parent_and_day_evidence(
    tmp_path,
):
    async with Client(stdio(tmp_path)) as client:
        for tool, args in [CASES[0], CASES[-1]]:
            for view in ["topic", "topic_audit"]:
                fields = suggested_fields(SPECS[tool], view=view)
                assert FIELD in fields and "interpretation.day_qi" in fields
                reply = await client.call_tool(
                    tool,
                    {
                        **args,
                        "fields": fields,
                        "strict_fields": True,
                        "include_snapshot_text": False,
                        "response_char_limit": 0,
                    },
                    raise_on_error=False,
                )
                assert not reply.is_error
                assert (
                    reply.structured_content["interpretation"]["topic_reading"]
                    == calculate(tool, args)["interpretation"]["topic_reading"]
                )


@pytest.mark.parametrize("tool,arguments", [CASES[0], CASES[1], CASES[-1]])
@pytest.mark.asyncio
async def test_4096_topic_projection_restores_full_field_and_same_run_candidates(
    tool, arguments, tmp_path
):
    expected = calculate(tool, arguments)
    async with Client(stdio(tmp_path)) as client:
        reply = await client.call_tool(
            tool,
            {
                **arguments,
                "fields": [
                    FIELD,
                    "interpretation.casting_readings",
                    "interpretation.day_qi",
                ],
                "strict_fields": True,
                "include_snapshot_text": False,
                "response_char_limit": 4096,
            },
            raise_on_error=False,
        )
        assert not reply.is_error
        output = reply.structured_content
        delivery = output["result_delivery"]
        run = output["run_metadata"]["run_id"]
        for field in [
            FIELD,
            "interpretation.casting_readings",
            "interpretation.day_qi",
        ]:
            uri = f"fatebridge://results/{delivery['result_id']}/verified/{run}/{delivery['sha256']}/fields/{field}/0"
            chunks = []
            checksum = None
            offset = 0
            while uri:
                page = json.loads((await client.read_resource(uri))[0].text)
                assert page["path"] == field and page["offset"] == offset
                assert (
                    page["verification"]["run_id"] == run
                    and page["verification"]["payload_sha256"] == delivery["sha256"]
                )
                assert page["verification"]["calculation_repeated"] is False
                checksum = page["sha256"] if checksum is None else checksum
                assert checksum == page["sha256"]
                chunks.append(page["text"])
                offset += len(page["text"])
                following = page["next_offset"]
                assert following is None or following == offset
                uri = (
                    uri.rsplit("/", 1)[0] + "/" + str(following)
                    if following is not None
                    else None
                )
            raw = "".join(chunks)
            assert hashlib.sha256(raw.encode()).hexdigest() == checksum
            assert json.loads(raw) == expected["interpretation"][field.split(".")[1]]
