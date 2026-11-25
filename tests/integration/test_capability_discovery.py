"""Agent-facing capability-discovery contracts.

Guards the surface an LLM uses to find and call tools without scraping prose
docs: the ``GET /api/tools`` manifest, cross-surface (REST↔MCP) parity, and the
self-describing MCP transport flags.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from fatebridge.api import app
from fatebridge.application.description import describe_spec
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG, mcp_specs, rest_specs
from tests.support.transports import cached_mcp_app, discover_capabilities, rest

__all__ = ["rest"]


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


def test_reference_discovery_uses_public_names_and_resources(
    rest: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    names = {"export_formats", "export_parse", "knowledge_catalog", "knowledge_read"}
    records = {}
    for name in sorted(names):
        response = rest.get(
            "/api/tools", params={"tool": name, "surface": "mcp", "detail": "summary"}
        )
        assert response.status_code == 200, response.text
        (record,) = response.json()["tools"]
        assert record["tool"] == record["surfaces"]["mcp_name"] == name
        assert (
            run(["discover", "--tool", name, "--surface", "mcp", "--detail", "summary"])
            == 0
        )
        assert json.loads(capsys.readouterr().out)["tools"] == [record]
        records[name] = record["surfaces"]

    retired = {"export_registry", "knowledge_registry", "calculate_knowledge_read"}
    for name in sorted(retired):
        assert rest.get("/api/tools", params={"tool": name}).status_code == 422
        assert run(["discover", "--tool", name]) == 1
        assert json.loads(capsys.readouterr().out)["issues"] == [
            {"path": "tool", "code": "unknown_tool"}
        ]

    async def read_resources() -> None:
        async with Client(cached_mcp_app(families="export,knowledge")) as client:
            assert set(await discover_capabilities(client)) == names
            for name in sorted(names):
                manifest = json.loads(
                    (await client.read_resource(f"fatebridge://tools/{name}"))[0].text
                )
                (contract,) = manifest["tools"]
                assert contract["tool"] == name
                assert contract["surfaces"] == records[name]
            for name in sorted(retired):
                result = await client.call_tool(
                    "run_calculation",
                    {"tool": name, "arguments": {}},
                    raise_on_error=False,
                )
                assert result.is_error
                assert result.structured_content["error_code"] == "unknown_tool"

    asyncio.run(read_resources())
