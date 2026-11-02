"""Loading profiles constrain discovery without changing calculation contracts."""

import asyncio
import json

import pytest
from fastmcp import Client

from fatebridge.application.discovery import select_mcp_specs
from fatebridge.application.examples import example_input
from fatebridge.diagnostics import diagnose
from fatebridge.mcp_server import _MCP_INSTRUCTIONS, create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import ParameterError


def test_topic_profile_retains_core_evidence_and_marks_conditional_gaps():
    async def run():
        async with Client(
            create_mcp_app(scenarios="onda-shiye", tool_scope="topic")
        ) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            assert {
                "bazi_career",
                "ziwei_birth",
                "astro_chart",
                "western_timing_analysis",
                "knowledge_read",
            } <= tools.keys()
            complete = select_mcp_specs(CATALOG, scenario="onda-shiye")
            assert len(tools) < len(complete)
            assert "profection" not in tools
            record = json.loads(
                (await client.read_resource("fatebridge://scenarios/onda-shiye"))[
                    0
                ].text
            )["scenarios"][0]
            assert not record["availability"]["complete"]
            assert "profection" in record["availability"]["missing_tool_keys"]
            denied = await client.call_tool("profection", {}, raise_on_error=False)
            assert denied.is_error
            spec = next(s for s in CATALOG if s.key == "bazi_career")
            result = await client.call_tool(
                spec.tool_name,
                {
                    **example_input(spec),
                    "as_of": "2026-10-22T12:00:00+08:00",
                    "fields": ["career_analysis.dominant_ten_gods"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            assert result.structured_content["career_analysis"]["dominant_ten_gods"]
            with pytest.raises(Exception, match="未在当前 MCP 配置中公开"):
                await client.read_resource("fatebridge://tools/profection/input")

    asyncio.run(run())


@pytest.mark.parametrize("scope,scenario", [("unknown", None), ("topic", None)])
def test_invalid_loading_profile_fails_before_publication(scope, scenario):
    with pytest.raises(ParameterError):
        create_mcp_app(scenarios=scenario, tool_scope=scope)
    assert not diagnose(tool_scope=scope, scenario=scenario)["ok"]


def test_default_profile_preserves_every_published_tool():
    assert {s.tool_name for s in select_mcp_specs(CATALOG)} == {
        s.tool_name for s in CATALOG if s.mcp_name
    }


def test_profile_doctor_matches_real_child_and_registration_environment():
    result = diagnose(mcp=True, scenario="onda-shiye", tool_scope="topic")
    assert result["ok"], result
    assert result["mcp_tool_count"] == result["mcp"]["tool_count"]
    assert result["codex"]["config"]["env"]["FATEBRIDGE_MCP_TOOL_SCOPE"] == "topic"


def test_all_published_parameters_explain_their_role():
    async def run():
        async with Client(create_mcp_app()) as client:
            for tool in await client.list_tools():
                schema = tool.model_dump(by_alias=True)["inputSchema"]
                for name, field in schema["properties"].items():
                    assert field.get("description"), (tool.name, name)

    asyncio.run(run())
    # Project budget for a self-contained server introduction, per OpenAI guidance.
    assert len(_MCP_INSTRUCTIONS) <= 512
