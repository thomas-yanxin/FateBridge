"""Topic-specific source facts, strict projections and same-run paging on all surfaces."""

import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from fatebridge.application.examples import suggested_fields
from fatebridge.core.public_output import same_public_value
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from tests.fixtures.mcp_result_delivery import read_full_result
from tests.support.transports import SPECS, business, call_cli, rest, surface_calls

FIELD = "interpretation.topic_reading"
GROUPS = {
    "households": [
        (
            "meihua_cast",
            {
                "casting": {
                    "method": "existing",
                    "hexagram_code": "000000",
                    "moving_line": 1,
                },
                "interpretation_topic": "household",
            },
        ),
        (
            "meihua_cast",
            {
                "casting": {
                    "method": "sound_groups",
                    "first_count": 10,
                    "second_count": 3,
                    "hour_branch": "子",
                },
                "interpretation_topic": "household",
                "season_month_branch": "辰",
            },
        ),
        (
            "meihua_cast",
            {
                "casting": {
                    "method": "sound_groups",
                    "first_count": 10,
                    "second_count": 3,
                    "hour_branch": "子",
                    "line_sum_basis": "trigram_numbers",
                },
                "interpretation_topic": "dwelling",
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
                "interpretation_topic": "dwelling",
            },
        ),
    ],
    "marriage": [
        (
            "meihua_cast",
            {
                "casting": {
                    "method": "existing",
                    "hexagram_code": "000000",
                    "moving_line": 1,
                },
                "interpretation_topic": "marriage",
            },
        ),
        (
            "meihua_cast",
            {
                "casting": {
                    "method": "sound_groups",
                    "first_count": 10,
                    "second_count": 3,
                    "hour_branch": "子",
                },
                "interpretation_topic": "marriage",
                "season_month_branch": "辰",
            },
        ),
        (
            "meihua_cast",
            {
                "casting": {
                    "method": "sound_groups",
                    "first_count": 10,
                    "second_count": 3,
                    "hour_branch": "子",
                    "line_sum_basis": "trigram_numbers",
                },
                "interpretation_topic": "marriage",
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
                "interpretation_topic": "marriage",
            },
        ),
    ],
    "dining": [
        (
            "meihua_cast",
            {
                "casting": {
                    "method": "existing",
                    "hexagram_code": "000000",
                    "moving_line": 1,
                },
                "interpretation_topic": "dining",
            },
        ),
        (
            "meihua_cast",
            {
                "casting": {
                    "method": "sound_groups",
                    "first_count": 1,
                    "second_count": 9,
                    "hour_branch": "丑",
                },
                "interpretation_topic": "dining",
                "season_month_branch": "辰",
            },
        ),
        (
            "meihua_cast",
            {
                "casting": {
                    "method": "sound_groups",
                    "first_count": 1,
                    "second_count": 9,
                    "hour_branch": "丑",
                    "line_sum_basis": "trigram_numbers",
                },
                "interpretation_topic": "dining",
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
                "interpretation_topic": "dining",
            },
        ),
    ],
    "qi_days": [
        (
            "meihua_cast",
            {
                "casting": {
                    "method": "existing",
                    "hexagram_code": "000111",
                    "moving_line": 1,
                },
                "interpretation_topic": "wealth",
                "day_qi_context": {"label": "合成未日标签", "day_branch": "未"},
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
                "interpretation_topic": "wealth",
                "day_qi_context": {"label": "合成申日标签", "day_branch": "申"},
            },
        ),
        (
            "meihua_cast",
            {
                "casting": {
                    "method": "existing",
                    "hexagram_code": "111111",
                    "moving_line": 1,
                },
                "interpretation_topic": "reputation",
                "day_qi_context": {"label": "合成戌日标签", "day_branch": "戌"},
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
                "day_qi_context": {"label": "合成午日标签", "day_branch": "午"},
                "reputation_context": {
                    "label": "合成非原典在任声明",
                    "currently_in_office": False,
                },
            },
        ),
        (
            "meihua_analysis",
            {
                "analysis_year": 2026,
                "analysis_month": 10,
                "analysis_day": 27,
                "analysis_hour": 23,
                "analysis_timezone": "Asia/Shanghai",
                "interpretation_topic": "wealth",
            },
        ),
    ],
    "qi_branches": [
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
                "reputation_context": {
                    "label": "合成非在任",
                    "currently_in_office": False,
                },
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
                "reputation_context": {
                    "label": "合成在任",
                    "currently_in_office": True,
                },
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
    ],
}

QUALIFICATIONS = {
    "households": ["chapter_qualifications", "real_residential_safety_verdict"],
    "marriage": ["chapter_qualifications", "real_marriage_or_consent_verdict"],
    "dining": ["chapter_qualifications", "real_outcome"],
    "qi_days": ["qi_day_timing_reference", "event_time"],
    "qi_branches": ["qi_branch_timing_reference", "event_time"],
}

CASES = [
    pytest.param(group, tool, arguments, id=f"{group}-{index}-{tool}")
    for group, cases in GROUPS.items()
    for index, (tool, arguments) in enumerate(cases)
]
PAGING_CASES = [
    pytest.param(tool, arguments, id=f"{group}-{index}-{tool}")
    for group, cases in GROUPS.items()
    for index, (tool, arguments) in enumerate([cases[0], cases[1], cases[-1]])
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
            "PYTHONPATH": str(root / "src"),
        },
        log_file=tmp_path / "stdio.log",
    )


@pytest.mark.parametrize(
    "tool,arguments", [GROUPS["marriage"][0], GROUPS["marriage"][-1]]
)
@pytest.mark.parametrize(
    "view,topic",
    [("general", "general"), ("weather", "weather"), ("topic", "marriage")],
)
def test_first_response_views_match_full_values_on_three_transports(
    tool, arguments, view, topic, surface_calls
):
    spec = SPECS[tool]
    payload = {**arguments, "interpretation_topic": topic}
    fields = suggested_fields(spec, view=view)
    response, protocol, code, local = surface_calls(
        spec,
        payload,
        projection={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
            "response_char_limit": 0,
        },
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(response.json())
        == business(local)
        == business(protocol.structured_content)
    )

    full_response, full_protocol, full_code, full_cli = surface_calls(
        spec,
        payload,
        params={"response_char_limit": 0},
        options={"fields": None},
        flags=["--response-char-limit", "0"],
    )
    assert (
        full_response.status_code == 200
        and full_code == 0
        and not full_protocol.is_error
    )
    full = full_response.json()
    assert (
        business(full)
        == business(full_cli)
        == business(full_protocol.structured_content)
    )
    assert "projection_warnings" not in local
    assert local["interpretation"]["interpretation_topic"] == topic
    assert {"interpretation.interpretation_topic", "summary"} <= set(fields)
    for field in fields:
        projected_value, full_value = local, full
        for part in field.split("."):
            projected_value, full_value = projected_value[part], full_value[part]
        if view == "general":
            assert projected_value is not None, field
        assert same_public_value(projected_value, full_value), field

    interpretation = local["interpretation"]
    if view == "general":
        assert fields == suggested_fields(spec)
        assert set(interpretation) == {
            "interpretation_topic",
            "classical_text_reference",
        }
        assert "seasonal_strength" not in local["meihua"]
        assert full["interpretation"]["topic_reading"] is None
        if tool == "meihua_analysis":
            assert local["analysis_context"]["civil_utc_offset"] == "+08:00"
            assert local["analysis_context"]["civil_instant_utc"]
    elif view == "weather":
        weather = interpretation["weather"]
        assert weather["context"]["season"] is None
        assert weather["pending_rule_ids"]
        assert any(
            type(count) is int and count == 0
            for count in weather["trigram_counts"].values()
        )
        assert interpretation["evidence_scope"]["body_use_applied"] is False
        assert "topic_reading" not in interpretation
        assert full["interpretation"]["weather"]["single_forecast"] is None
    else:
        topic_reading = interpretation["topic_reading"]
        assert topic_reading["ruleset_id"] == "meihua_marriage_clauses_nlc1925_v1"
        assert interpretation["classical_text_reference"]["moving_yaoci"]
        assert local["meihua"]["changed_hexagram"]["binary_code"]
        assert (
            topic_reading["chapter_qualifications"]["real_marriage_or_consent_verdict"]
            is None
        )
        assert "weather" not in interpretation


@pytest.mark.parametrize(
    "view,topic,evidence_path",
    [
        ("weather", "weather", "weather.selected_readings"),
        ("topic", "marriage", "topic_reading"),
    ],
)
@pytest.mark.asyncio
async def test_first_response_cards_preserve_evidence_at_default_mcp_budget(
    view, topic, evidence_path
):
    tool, arguments = GROUPS["marriage"][1]
    arguments = {**arguments, "interpretation_topic": topic}
    fields = suggested_fields(SPECS[tool], view=view)
    expected = calculate(tool, arguments)["interpretation"]
    async with Client(create_mcp_app()) as client:
        reply = await client.call_tool(
            tool,
            {
                **arguments,
                "fields": fields,
                "strict_fields": True,
                "include_snapshot_text": False,
            },
            raise_on_error=False,
        )
        assert not reply.is_error
        inline = reply.structured_content
        output = await read_full_result(client, inline)
        assert output["run_metadata"]["run_id"] == inline["run_metadata"]["run_id"]
        actual = output["interpretation"]
        for part in evidence_path.split("."):
            actual, expected = actual[part], expected[part]
        assert same_public_value(actual, expected)


@pytest.mark.parametrize("group,tool,arguments", CASES)
@pytest.mark.asyncio
async def test_topic_facts_and_candidates_agree_on_three_transports(
    group, tool, arguments, rest, capsys, tmp_path
):
    domain = calculate(tool, arguments)
    fields = [
        FIELD,
        "interpretation.casting_readings",
        "interpretation.day_qi",
        "summary",
    ]
    parent, field = QUALIFICATIONS[group]
    assert domain["interpretation"]["topic_reading"][parent][field] is None
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
            assert same_public_value(
                output["interpretation"][field], domain["interpretation"][field]
            )
        assert output["summary"] == domain["summary"]


@pytest.mark.parametrize("group", GROUPS)
@pytest.mark.asyncio
async def test_fresh_stdio_schemas_and_published_topic_cards(group, tmp_path):
    cases = GROUPS[group]
    async with Client(stdio(tmp_path)) as client:
        available = {tool.name: tool for tool in await client.list_tools()}
        for name in ["meihua_cast", "meihua_analysis"]:
            schema = available[name].model_dump(by_alias=True)["inputSchema"]
            assert {args["interpretation_topic"] for _, args in cases} <= set(
                schema["properties"]["interpretation_topic"]["enum"]
            )
        for tool, arguments in [cases[0], cases[-1]]:
            for view in ["topic", "topic_audit"]:
                fields = suggested_fields(SPECS[tool], view=view)
                assert FIELD in fields and "interpretation.day_qi" in fields
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
                assert same_public_value(
                    reply.structured_content["interpretation"]["topic_reading"],
                    calculate(tool, arguments)["interpretation"]["topic_reading"],
                )


@pytest.mark.parametrize("tool,arguments", PAGING_CASES)
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
        assert "result_delivery" in output
        restored = await read_full_result(client, output)
        for field in [
            FIELD,
            "interpretation.casting_readings",
            "interpretation.day_qi",
        ]:
            assert same_public_value(
                restored["interpretation"][field.split(".")[1]],
                expected["interpretation"][field.split(".")[1]],
            )
