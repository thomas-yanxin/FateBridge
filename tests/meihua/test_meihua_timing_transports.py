"""Three transports and bounded same-run delivery of the exact timing reference."""

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
from tests.support.transports import SPECS, call_cli, rest

FIELD = "interpretation.motion_context"
CASES = [
    (
        "meihua_cast",
        {
            "casting": {
                "method": "observed_trigrams",
                "upper_trigram": "乾",
                "lower_trigram": "巽",
                "hour_branch": "卯",
            },
            "observer_activity": "walking",
        },
        "5",
    ),
    (
        "meihua_cast",
        {
            "casting": {
                "method": "observed_trigrams",
                "upper_trigram": "乾",
                "lower_trigram": "乾",
                "hour_branch": "子",
            },
            "observer_activity": "walking",
        },
        "3/2",
    ),
    (
        "meihua_cast",
        {
            "casting": {
                "method": "observed_categories",
                "subject_category": "elder_person",
                "subject_description": "虚构类别算术核对，非实际观测",
                "single_subject_confirmed": True,
                "direction": "southeast",
                "direction_role": "toward",
                "hour_branch": "卯",
            },
            "observer_activity": "seated",
        },
        "20",
    ),
    (
        "meihua_analysis",
        {
            "analysis_year": 2026,
            "analysis_month": 10,
            "analysis_day": 27,
            "analysis_hour": 12,
            "analysis_timezone": "Asia/Shanghai",
            "observer_activity": "walking",
        },
        None,
    ),
]


def calculate(tool, arguments):
    return (
        calculate_meihua_cast if tool == "meihua_cast" else calculate_meihua_analysis
    )(**arguments)


def stdio(tmp_path):
    root = Path(__file__).resolve().parents[2]
    return StdioTransport(
        command=sys.executable,
        args=["-m", "fatebridge.mcp_server"],
        cwd=str(root),
        env={
            "PYTHONPATH": os.environ.get(
                "MEIHUA_V54_EXPECTED_PACKAGE_ROOT", str(root / "src")
            ),
        },
        log_file=tmp_path / "stdio.log",
    )


@pytest.mark.parametrize("tool,arguments,nominal", CASES)
@pytest.mark.asyncio
async def test_exact_fraction_source_context_agrees_on_three_transports(
    tool, arguments, nominal, rest, capsys, tmp_path
):
    domain = calculate(tool, arguments)
    expected = domain["interpretation"]["motion_context"]
    if nominal is None:
        assert "postheaven_count_reference" not in expected
    else:
        assert (
            expected["postheaven_count_reference"]["nominal_scaled_count"][
                "exact_rational"
            ]
            == nominal
        )
    fields = [FIELD, "meihua.seed", "summary"]
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
    for out in [response.json(), reply.structured_content, cli]:
        assert out["interpretation"]["motion_context"] == expected
        assert out["meihua"]["seed"] == domain["meihua"]["seed"]
        assert out["summary"] == domain["summary"]
    assert FIELD in suggested_fields(SPECS[tool], view="motion")


@pytest.mark.asyncio
async def test_fresh_stdio_existing_request_schema_and_motion_card_deliver_component(
    tmp_path,
):
    async with Client(stdio(tmp_path)) as client:
        tools = {t.name: t for t in await client.list_tools()}
        for tool, args, nominal in [CASES[0], CASES[3]]:
            schema = tools[tool].inputSchema
            assert "observer_activity" in schema["properties"]
            reply = await client.call_tool(
                tool,
                {
                    **args,
                    "fields": suggested_fields(SPECS[tool], view="motion"),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
                raise_on_error=False,
            )
            assert not reply.is_error
            context = reply.structured_content["interpretation"]["motion_context"]
            assert context == calculate(tool, args)["interpretation"]["motion_context"]
            if nominal is not None:
                assert context["postheaven_count_reference"]["time_unit"] is None


@pytest.mark.parametrize("tool,arguments,nominal", CASES)
@pytest.mark.asyncio
async def test_4096_delivery_restores_same_run_complete_source_and_exact_count(
    tool, arguments, nominal, tmp_path
):
    expected = calculate(tool, arguments)["interpretation"]["motion_context"]
    async with Client(stdio(tmp_path)) as client:
        reply = await client.call_tool(
            tool,
            {
                **arguments,
                "fields": [FIELD],
                "strict_fields": True,
                "include_snapshot_text": False,
                "response_char_limit": 4096,
            },
            raise_on_error=False,
        )
        assert not reply.is_error
        output = reply.structured_content
        if "result_delivery" not in output:
            assert nominal is None
            assert output["interpretation"]["motion_context"] == expected
            return
        delivery = output["result_delivery"]
        run = output["run_metadata"]["run_id"]
        uri = f"fatebridge://results/{delivery['result_id']}/verified/{run}/{delivery['sha256']}/fields/{FIELD}/0"
        pieces = []
        checksum = None
        offset = 0
        while uri:
            page = json.loads((await client.read_resource(uri))[0].text)
            assert page["offset"] == offset and page["path"] == FIELD
            assert page["verification"]["run_id"] == run
            assert page["verification"]["payload_sha256"] == delivery["sha256"]
            assert page["verification"]["calculation_repeated"] is False
            checksum = page["sha256"] if checksum is None else checksum
            assert page["sha256"] == checksum
            pieces.append(page["text"])
            offset += len(page["text"])
            following = page["next_offset"]
            assert following is None or following == offset
            uri = (
                uri.rsplit("/", 1)[0] + "/" + str(following)
                if following is not None
                else None
            )
        raw = "".join(pieces)
        assert hashlib.sha256(raw.encode()).hexdigest() == checksum
        assert json.loads(raw) == expected
