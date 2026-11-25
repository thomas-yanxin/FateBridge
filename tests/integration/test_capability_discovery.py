"""Agent-facing capability-discovery contracts.

Guards the surface an LLM uses to find and call tools without scraping prose
docs: the ``GET /api/tools`` manifest, cross-surface (REST↔MCP) parity, and the
self-describing MCP transport flags.
"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from fastmcp import Client

from fatebridge.api import app
from fatebridge.application.description import describe_spec
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG, mcp_specs, rest_specs


def _tools_payload() -> dict:
    return TestClient(app).get("/api/tools").json()


def test_tools_endpoint_counts_match_catalog() -> None:
    payload = _tools_payload()
    assert payload["counts"]["rest"] == len(rest_specs())
    assert payload["counts"]["mcp"] == len(mcp_specs())
    assert payload["counts"]["total"] == len(CATALOG)
    assert len(payload["tools"]) == len(CATALOG)


def test_tools_endpoint_records_are_well_formed() -> None:
    payload = _tools_payload()
    assert {t["tool"] for t in payload["tools"]} == {s.tool_name for s in CATALOG}
    for record in payload["tools"]:
        assert record["summary"]
        assert record["family"]
        assert {"cli", "rest_path", "mcp_name"} <= record["surfaces"].keys()
        for param in record["parameters"]:
            assert {"name", "type", "required", "description"} <= param.keys()


def test_every_tool_declares_the_same_public_name_across_surfaces() -> None:
    for spec in CATALOG:
        surfaces = describe_spec(spec)["surfaces"]
        assert surfaces["rest_path"]
        assert surfaces["mcp_name"] == spec.tool_name
        assert surfaces["cli"]


def test_mcp_transport_flags_are_self_describing() -> None:
    async def fetch():
        async with Client(create_mcp_app()) as client:
            tool = next(
                t for t in await client.list_tools() if t.name == "run_calculation"
            )
            return tool.input_schema["properties"]

    properties = asyncio.run(fetch())
    assert "compact" not in properties
    assert properties["detail"]["default"] == "compact"
    assert properties["detail"]["enum"] == ["compact", "standard", "audit"]
    for flag in (
        "include_snapshot_text",
        "fields",
        "strict_fields",
        "response_char_limit",
    ):
        assert properties[flag]["description"]
