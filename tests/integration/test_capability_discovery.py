"""Agent-facing capability-discovery contracts.

Guards the surface an LLM uses to find and call tools without scraping prose
docs: the ``GET /api/tools`` manifest, cross-surface (REST↔MCP) parity, and the
self-describing MCP transport flags.
"""

from __future__ import annotations

import inspect
from typing import get_args

from fastapi.testclient import TestClient

from fatebridge.api import app
from fatebridge.application.description import describe_spec
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
