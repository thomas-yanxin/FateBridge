"""Integration tests for the public place_lookup tool across CLI, REST, and MCP."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.mcp_server as mcp_module
from fatebridge.cli import run as cli_run
from fatebridge.utils.places import lookup_place as calculate_place_lookup
from tests.support.transports import business, call_calculation, rest

__all__ = ["rest"]


def test_place_lookup_resolved_ambiguous_and_not_found() -> None:
    resolved = calculate_place_lookup(query="北京朝阳", limit=5)
    assert resolved["status"] == "resolved"
    assert resolved["resolved"]["canonical_name"] == "朝阳区"
    assert resolved["resolved"]["admin_path"] == ["北京市", "朝阳区"]
    assert resolved["resolved"]["timezone"] == "Asia/Shanghai"
    assert resolved["resolved"]["country_code"] == "CN"
    assert resolved["resolved"]["precision"] == "county"
    assert resolved["resolved"]["match_source"] == "qualified_match"

    ambiguous = calculate_place_lookup(query="朝阳", limit=5)
    assert ambiguous["status"] == "ambiguous"
    assert ambiguous["resolved"] is None
    assert len(ambiguous["candidates"]) == 3
    admin_paths = [c["admin_path"] for c in ambiguous["candidates"]]
    assert ["北京市", "朝阳区"] in admin_paths
    assert ["辽宁省", "朝阳市"] in admin_paths
    assert ["吉林省", "长春市", "朝阳区"] in admin_paths

    limited = calculate_place_lookup(query="朝阳", limit=2)
    assert limited["status"] == "ambiguous"
    assert len(limited["candidates"]) == 2

    preferred = calculate_place_lookup(query="London", limit=5)
    assert preferred["status"] == "resolved"
    assert preferred["resolved"]["country_code"] == "GB"
    assert preferred["resolved"]["match_source"] == "preferred_alias"

    springfield = calculate_place_lookup(query="Springfield", limit=5)
    assert springfield["status"] == "ambiguous"
    assert len(springfield["candidates"]) == 3
    assert all(len(c["admin_path"]) >= 3 for c in springfield["candidates"])

    fallback = calculate_place_lookup(query="江苏省未收录地点", limit=5)
    assert fallback["status"] == "resolved"
    assert fallback["resolved"]["canonical_name"] == "江苏"
    assert fallback["resolved"]["precision"] == "province"
    assert fallback["resolved"]["match_source"] == "province_fallback"

    missing = calculate_place_lookup(query="不存在的地名xyz", limit=5)
    assert missing["status"] == "not_found"
    assert missing["resolved"] is None
    assert missing["candidates"] == []


def test_place_lookup_three_surface_parity(
    rest: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = {"query": "朝阳", "limit": 5}
    http = rest.post("/api/places/lookup", json=payload)
    assert http.status_code == 200, http.text

    async def mcp_call():
        async with Client(mcp_module.app) as client:
            return await call_calculation(client, "place_lookup", payload)

    mcp_res = asyncio.run(mcp_call())
    assert not mcp_res.is_error

    capsys.readouterr()
    code = cli_run(["place_lookup", "--query", "朝阳", "--limit", "5"])
    assert code == 0
    cli_res = json.loads(capsys.readouterr().out)

    assert (
        business(http.json())
        == business(mcp_res.structured_content)
        == business(cli_res)
    )
    assert cli_res["status"] == "ambiguous"
    assert len(cli_res["candidates"]) == 3


def test_place_lookup_rejects_blank_query(capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()
    code = cli_run(["place_lookup", "--query", "   "])
    assert code == 1
    err = json.loads(capsys.readouterr().out)
    assert err["error_code"] == "validation_error"
    assert err["issues"][0]["path"] == "query"
