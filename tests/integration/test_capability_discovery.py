"""Agent-facing capability-discovery contracts.

Guards the surface an LLM uses to find and call tools without scraping prose
docs: the ``GET /api/tools`` manifest, cross-surface (REST↔MCP) parity, and the
self-describing MCP transport flags.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import get_args

from fastapi.testclient import TestClient
from fastmcp import Client

from fatebridge.api import app
from fatebridge.application.description import describe_spec
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG, mcp_specs, rest_specs
from fatebridge.transports.mcp import _make_mcp_fn

# Intentional single-surface tools — test-locked 口径 aliases: a nested-model REST
# variant + its flat MCP twin, plus the legacy aggregate alias. If this set
# changes, the parity tests below fail on purpose so the change is reviewed.
_REST_ONLY = {"astro_relative"}
_MCP_ONLY = {"analyze_destiny", "astro_relative_chart"}


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


def test_describe_spec_does_not_claim_phantom_mcp_for_rest_only_tools() -> None:
    by_key = {s.key: s for s in CATALOG}
    for key in _REST_ONLY:
        assert describe_spec(by_key[key])["surfaces"]["mcp_name"] is None


def test_every_tool_is_dual_surface_or_documented_single_surface() -> None:
    rest_only = {s.key for s in CATALOG if s.rest_path and not s.mcp_name}
    mcp_only = {s.key for s in CATALOG if s.mcp_name and not s.rest_path}
    assert (
        rest_only == _REST_ONLY
    ), "REST-only tools changed; if intentional, update the documented allow-list"
    assert (
        mcp_only == _MCP_ONLY
    ), "MCP-only tools changed; if intentional, update the documented allow-list"


def test_mcp_transport_flags_are_self_describing() -> None:
    spec = next(s for s in CATALOG if s.mcp_name)
    fn = _make_mcp_fn(
        spec,
        render_response=lambda *a, **k: "",
        render_error=lambda *a, **k: "",
    )
    sig = inspect.signature(fn)
    for flag in ("compact", "include_snapshot_text", "fields"):
        annotation = sig.parameters[flag].annotation
        descriptions = [
            getattr(meta, "description", None) for meta in get_args(annotation)[1:]
        ]
        assert any(descriptions), f"MCP flag {flag!r} has no description"


def test_reference_and_dice_discovery_publish_callable_baseline_names(capsys):
    names = [
        "otherbu",
        "export_registry",
        "export_parse",
        "knowledge_registry",
        "knowledge_read",
    ]
    records = {}
    for name in names:
        response = TestClient(app).get(
            "/api/tools", params={"tool": name, "surface": "mcp", "detail": "summary"}
        )
        assert response.status_code == 200, response.text
        assert response.json()["matched_count"] == 1
        record = response.json()["tools"][0]
        assert record["tool"] == record["surfaces"]["mcp_name"] == name
        capsys.readouterr()
        assert run(["discover", "--tool", name, "--surface", "mcp"]) == 0
        local = json.loads(capsys.readouterr().out)
        assert local["tools"] == [record]
        records[name] = record

    async def native():
        async with Client(
            create_mcp_app(families="divination,export,knowledge")
        ) as client:
            tools = {tool.name for tool in await client.list_tools()}
            assert set(names) <= tools
            for name in names:
                resource = json.loads(
                    (await client.read_resource(f"fatebridge://tools/{name}"))[0].text
                )
                assert resource["matched_count"] == 1
                assert resource["tools"][0]["tool"] == records[name]["tool"]
                assert resource["tools"][0]["surfaces"] == records[name]["surfaces"]

    asyncio.run(native())


def test_discovery_rejects_unpublished_names_instead_of_inventing_aliases(capsys):
    names = ["astrodice", "calculate_export_parse", "calculate_knowledge_read"]
    for name in names:
        response = TestClient(app).get("/api/tools", params={"tool": name})
        assert response.status_code == 422
        assert response.json()["issues"] == [{"path": "tool", "code": "unknown_tool"}]
        capsys.readouterr()
        assert run(["discover", "--tool", name]) == 1
        local = json.loads(capsys.readouterr().out)
        assert local["issues"] == [{"path": "tool", "code": "unknown_tool"}]
        assert run([name]) == 2
        assert json.loads(capsys.readouterr().out)["error_code"] == "usage_error"

    async def native():
        async with Client(
            create_mcp_app(families="divination,export,knowledge")
        ) as client:
            for name in names:
                result = await client.call_tool(name, {}, raise_on_error=False)
                assert result.is_error

    asyncio.run(native())
