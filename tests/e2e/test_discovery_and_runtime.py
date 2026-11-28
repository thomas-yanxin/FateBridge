"""Opaque-box E2E tests for M1 (Progressive Discovery) and M7 (Ephemeris & Runtime)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Literal

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from tests.e2e.conftest import (
    call_cli,
    call_mcp_tool,
    call_rest,
    extract_error_issues,
    find_bloat_keys,
    rest_path_for,
)
from tests.support.transports import cached_mcp_app

EXPECTED_TOOL_COUNT = 91
EXPECTED_FAMILY_COUNT = 12
DISCOVERY_DETAILS: tuple[Literal["brief", "summary", "full"], ...] = (
    "brief",
    "summary",
    "full",
)


# ---------------------------------------------------------------------------
# M1: Progressive Discovery & Surface Schema Parity
# ---------------------------------------------------------------------------


def test_catalog_has_91_tools_12_families_and_clean_output_schemas(
    all_tool_specs: dict[str, dict[str, Any]],
) -> None:
    import fatebridge

    assert len(all_tool_specs) == EXPECTED_TOOL_COUNT
    summary = fatebridge.discover(detail="summary")
    assert summary["counts"]["total"] == EXPECTED_TOOL_COUNT
    assert len(summary["families"]) == EXPECTED_FAMILY_COUNT

    for tool_name, spec in sorted(all_tool_specs.items()):
        output_schema = spec.get("output_schema")
        assert isinstance(output_schema, dict), f"{tool_name} missing output_schema"
        assert find_bloat_keys(output_schema) == [], f"{tool_name} bloat in schema"


@pytest.mark.asyncio
@pytest.mark.parametrize("detail_level", DISCOVERY_DETAILS)
@pytest.mark.parametrize("include_output_schema", (False, True))
async def test_discovery_detail_and_output_schema_toggle_across_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    detail_level: Literal["brief", "summary", "full"],
    include_output_schema: bool,
) -> None:
    import fatebridge

    py_manifest = fatebridge.discover(
        tool="bazi_overview",
        detail=detail_level,
        include_output_schema=include_output_schema,
    )
    mcp_out = await call_mcp_tool(
        mcp_client,
        "discover_tools",
        {
            "tool": "bazi_overview",
            "detail": detail_level,
            "include_output_schema": include_output_schema,
        },
    )
    rest_out = call_rest(
        rest_client,
        "GET",
        "/api/tools",
        params={
            "tool": "bazi_overview",
            "detail": detail_level,
            "include_output_schema": str(include_output_schema).lower(),
        },
    )
    cli_args = ["discover", "bazi_overview", "--detail", detail_level]
    if include_output_schema:
        cli_args.append("--include-output-schema")
    cli_out = call_cli(cli_args)

    assert mcp_out.ok and rest_out.ok and cli_out.ok
    for record in (py_manifest, mcp_out.payload, rest_out.payload, cli_out.payload):
        assert record["tool"] == "bazi_overview"
        assert record["detail"] == detail_level
        if detail_level == "full" and include_output_schema:
            assert isinstance(record.get("output_schema"), dict)
        else:
            assert "output_schema" not in record
        if detail_level == "brief":
            assert "input_schema" not in record
        elif detail_level == "summary":
            assert isinstance(record.get("input_schema"), dict)
        else:
            assert isinstance(record.get("input_schema"), dict)
            assert "example_input" in record


@pytest.mark.asyncio
async def test_discovery_filtering_parity_across_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
) -> None:
    import fatebridge

    # 1. family="knowledge"
    py_fam = fatebridge.discover(family="knowledge", detail="summary")
    mcp_fam = await call_mcp_tool(
        mcp_client, "discover_tools", {"family": "knowledge", "detail": "summary"}
    )
    rest_fam = call_rest(
        rest_client,
        "GET",
        "/api/tools",
        params={"family": "knowledge", "detail": "summary"},
    )
    cli_fam = call_cli(["discover", "--family", "knowledge", "--detail", "summary"])
    assert mcp_fam.ok and rest_fam.ok and cli_fam.ok
    expected_knowledge = {"knowledge_catalog", "knowledge_read", "place_lookup"}
    for payload in (py_fam, mcp_fam.payload, rest_fam.payload, cli_fam.payload):
        assert {item["tool"] for item in payload["tools"]} == expected_knowledge

    # 2. q="法达"
    py_q = fatebridge.discover(q="法达", detail="brief")
    mcp_q = await call_mcp_tool(
        mcp_client, "discover_tools", {"q": "法达", "detail": "brief"}
    )
    rest_q = call_rest(
        rest_client, "GET", "/api/tools", params={"q": "法达", "detail": "brief"}
    )
    cli_q = call_cli(["discover", "--q", "法达", "--detail", "brief"])
    assert mcp_q.ok and rest_q.ok and cli_q.ok
    q_names = {item["tool"] for item in rest_q.payload["tools"]}
    assert "firdaria" in q_names
    for payload in (py_q, mcp_q.payload, cli_q.payload):
        assert {item["tool"] for item in payload["tools"]} == q_names

    # 3. tools (+ surface) filtering across REST, MCP, CLI & Python SDK
    target_tools = ["qimen", "liuren_chart"]
    mcp_tools = await call_mcp_tool(
        mcp_client,
        "discover_tools",
        {"tools": target_tools, "detail": "summary"},
    )
    rest_tools = call_rest(
        rest_client,
        "GET",
        "/api/tools",
        params={"tools": ",".join(target_tools), "surface": "mcp", "detail": "summary"},
    )
    cli_tools = call_cli(
        [
            "discover",
            "--tools",
            ",".join(target_tools),
            "--surface",
            "mcp",
            "--detail",
            "summary",
        ]
    )
    assert mcp_tools.ok and rest_tools.ok and cli_tools.ok
    for payload in (mcp_tools.payload, rest_tools.payload, cli_tools.payload):
        assert [item["tool"] for item in payload["tools"]] == target_tools
        assert all(item["surfaces"]["mcp"] is True for item in payload["tools"])

    py_tools = fatebridge.discover(tools=target_tools, surface="mcp", detail="summary")
    assert [item["tool"] for item in py_tools["tools"]] == target_tools


@pytest.mark.asyncio
@pytest.mark.parametrize("q_val", (None, "", "   "))
async def test_discovery_unfiltered_full_rejected_422_across_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    q_val: str | None,
) -> None:
    import fatebridge

    py_kw: dict[str, Any] = {"detail": "full"}
    mcp_args: dict[str, Any] = {"detail": "full"}
    rest_params: dict[str, str] = {"detail": "full"}
    cli_args = ["discover", "--detail", "full"]
    if q_val is not None:
        py_kw["q"] = q_val
        mcp_args["q"] = q_val
        rest_params["q"] = q_val
        cli_args.extend(["--q", q_val])

    with pytest.raises(ValueError) as exc_info:
        fatebridge.discover(**py_kw)
    assert getattr(exc_info.value, "status_code", None) == 422
    py_issues = getattr(exc_info.value, "issues", [])
    assert py_issues and py_issues[0]["code"] == "filter_required_for_full_detail"

    mcp_out = await call_mcp_tool(mcp_client, "discover_tools", mcp_args)
    rest_out = call_rest(rest_client, "GET", "/api/tools", params=rest_params)
    cli_out = call_cli(cli_args)

    assert not mcp_out.ok and mcp_out.status_code == 422
    assert not rest_out.ok and rest_out.status_code == 422
    assert not cli_out.ok and cli_out.exit_code == 1
    for outcome in (mcp_out, rest_out, cli_out):
        assert outcome.payload.get("error_code") == "validation_error"
        issues = extract_error_issues(outcome.payload)
        assert issues and issues[0]["code"] == "filter_required_for_full_detail"


@pytest.mark.asyncio
async def test_discovery_unknown_tool_returns_404_with_suggestions(
    mcp_client: Client,
    rest_client: TestClient,
) -> None:
    import fatebridge

    typo = "bazi_birth_chrat"
    with pytest.raises(ValueError) as exc_info:
        fatebridge.discover(tool=typo)
    assert getattr(exc_info.value, "status_code", None) == 404
    py_issues = getattr(exc_info.value, "issues", [])
    assert py_issues and py_issues[0]["code"] == "unknown_tool"
    assert "bazi_birth_chart" in py_issues[0]["constraints"]["suggestions"]

    mcp_out = await call_mcp_tool(mcp_client, "discover_tools", {"tool": typo})
    rest_out = call_rest(rest_client, "GET", "/api/tools", params={"tool": typo})
    cli_out = call_cli(["discover", typo])

    assert not mcp_out.ok and mcp_out.status_code == 404
    assert not rest_out.ok and rest_out.status_code == 404
    assert not cli_out.ok and cli_out.exit_code == 2
    for outcome in (mcp_out, rest_out, cli_out):
        issues = extract_error_issues(outcome.payload)
        assert issues and issues[0]["code"] == "unknown_tool"
        assert "bazi_birth_chart" in issues[0]["constraints"]["suggestions"]


def test_cli_discover_batch_and_batch_schema_example() -> None:
    disc_batch = call_cli(["discover", "batch"])
    schema_out = call_cli(["batch", "--schema"])
    example_out = call_cli(["batch", "--example"])

    for out in (disc_batch, schema_out, example_out):
        assert out.ok and out.exit_code == 0, out.raw_stdout or out.raw_stderr

    for contract in (disc_batch.payload, schema_out.payload):
        assert contract["tool"] == "batch"
        assert contract["limits"]["max_calls"] == 32
        assert isinstance(contract.get("input_schema"), dict)
        assert isinstance(contract.get("example_input"), dict)

    assert isinstance(example_out.payload.get("calls"), list)
    assert len(example_out.payload["calls"]) >= 1
    assert "context" in example_out.payload
    assert "defaults" in example_out.payload


@pytest.mark.asyncio
async def test_mcp_and_openapi_schemas_parity(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
) -> None:
    mcp_tools = {tool.name: tool for tool in await mcp_client.list_tools()}
    assert set(mcp_tools) == {"discover_tools", "run_calculation", "run_batch"}

    calc_props = mcp_tools["run_calculation"].input_schema.get("properties", {})
    assert "detail" not in calc_props
    assert {"tool", "arguments", "include", "fields", "as_of"}.issubset(calc_props)

    batch_schema = mcp_tools["run_batch"].input_schema
    batch_props = batch_schema.get("properties", {})
    assert "detail" not in batch_props
    assert "include" not in batch_props
    assert "fields" not in batch_props
    batch_call_props = batch_schema["$defs"]["BatchCall"]["properties"]
    assert "detail" not in batch_call_props
    assert {"include", "fields"}.issubset(batch_call_props)
    assert "detail" in mcp_tools["discover_tools"].input_schema.get("properties", {})

    openapi_out = call_rest(rest_client, "GET", "/openapi.json")
    assert openapi_out.ok
    paths = openapi_out.payload["paths"]

    discovered_rest_paths = {
        rest_path_for(name, all_tool_specs) for name in all_tool_specs
    }
    assert len(discovered_rest_paths) == EXPECTED_TOOL_COUNT
    for path in discovered_rest_paths:
        assert "post" in paths[path]

    sample_post = paths[rest_path_for("bazi_overview", all_tool_specs)]["post"]
    sample_query = {
        p["name"] for p in sample_post.get("parameters", []) if p.get("in") == "query"
    }
    assert "detail" not in sample_query
    assert {"include", "fields", "as_of"}.issubset(sample_query)

    tools_query = {
        p["name"]
        for p in paths["/api/tools"]["get"].get("parameters", [])
        if p.get("in") == "query"
    }
    assert "detail" in tools_query

    schemas = openapi_out.payload["components"]["schemas"]
    batch_req_props = schemas["BatchRequest"]["properties"]
    assert not ({"detail", "include", "fields"} & set(batch_req_props))
    batch_call_rest_props = schemas["BatchCall"]["properties"]
    assert "detail" not in batch_call_rest_props
    assert {"include", "fields"}.issubset(batch_call_rest_props)


# ---------------------------------------------------------------------------
# M7: Ephemeris & Runtime Endpoints
# ---------------------------------------------------------------------------


def test_health_ready_and_metrics_auth_exempt_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fatebridge.api as api

    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(api, "REQUEST_METRICS", api.RuntimeMetrics())
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={"client": "k1"}),
    )
    try:
        with TestClient(api.app) as client:
            health = client.get("/health")
            assert health.status_code == 200
            assert health.json() == {"status": "healthy"}

            ready = client.get("/ready")
            assert ready.status_code == 200
            ready_json = ready.json()
            assert ready_json["status"] == "ready"
            assert ready_json["checks"]["core_api"]["ok"] is True
            assert ready_json["checks"]["offline_astrology"]["ok"] is True

            # Auth-protected calc fails without key; /metrics remains auth-exempt
            unauth = client.post("/api/divination/gua", json={"queries": ["乾"]})
            assert unauth.status_code == 401

            metrics = client.get("/metrics")
            assert metrics.status_code == 200
            assert metrics.headers["content-type"].startswith("text/plain")
            assert (
                'fatebridge_http_requests_total{method="GET",path="/health",status="200"} 1.0'
                in metrics.text
            )
            assert (
                'fatebridge_http_requests_total{method="GET",path="/ready",status="200"} 1.0'
                in metrics.text
            )
            assert (
                'fatebridge_http_requests_total{method="POST",path="/api/divination/gua",status="401"} 1.0'
                in metrics.text
            )
    finally:
        api._reset_runtime_state_for_tests()


def test_ready_503_and_western_timing_dependency_missing_subprocess() -> None:
    """Verify /ready 503 and western_timing 503 dependency_missing without internal imports."""
    script = """
import asyncio, json, os, sys, tempfile
from fastapi.testclient import TestClient
from fastmcp import Client
import fatebridge
import fatebridge.api as api
from fatebridge.mcp_server import create_mcp_app

api._reset_runtime_state_for_tests()
api.API_KEY_AUTHENTICATOR = api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={})
client = TestClient(api.app)
astro_args = {
    "birth_year": 1990, "birth_month": 5, "birth_day": 15,
    "birth_hour": 10, "birth_minute": 30,
    "birth_longitude": 116.4, "birth_latitude": 39.9,
    "birth_timezone": "Asia/Shanghai",
}
# Ensure lazy predictive runtime modules are loaded before disabling native swe
warm = client.post("/api/astrology/timing", json=astro_args)
assert warm.status_code == 200

with tempfile.TemporaryDirectory() as empty_dir:
    os.environ["FATEBRIDGE_DE441_DIR"] = empty_dir
    for name, mod in list(sys.modules.items()):
        if name.startswith("fatebridge.") and mod is not None and hasattr(mod, "swe"):
            setattr(mod, "swe", None)

    ready_resp = client.get("/ready")
    rest_resp = client.post("/api/astrology/timing", json=astro_args)
    py_resp = fatebridge.run("western_timing", astro_args)

    async def call_mcp():
        async with Client(create_mcp_app()) as mcp_c:
            return await mcp_c.call_tool(
                "run_calculation",
                {"tool": "western_timing", "arguments": astro_args},
                raise_on_error=False,
            )

    mcp_resp = asyncio.run(call_mcp())
    print(json.dumps({
        "ready_status": ready_resp.status_code,
        "ready_body": ready_resp.json(),
        "rest_status": rest_resp.status_code,
        "rest_body": rest_resp.json(),
        "py_body": py_resp,
        "mcp_error": mcp_resp.is_error,
        "mcp_body": mcp_resp.structured_content,
    }, ensure_ascii=False))
"""
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60.0,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = json.loads(proc.stdout.strip().splitlines()[-1])

    assert data["ready_status"] == 503
    assert data["ready_body"]["status"] == "not_ready"
    assert data["ready_body"]["checks"]["offline_astrology"]["ok"] is False

    assert data["rest_status"] == 503
    assert data["rest_body"]["error_code"] == "dependency_missing"
    assert data["rest_body"]["retryable"] is False

    assert data["py_body"]["error_code"] == "dependency_missing"
    assert data["py_body"]["status_code"] == 503
    assert data["py_body"]["retryable"] is False

    assert data["mcp_error"] is True
    assert data["mcp_body"]["error_code"] == "dependency_missing"
    assert data["mcp_body"]["status_code"] == 503
    assert data["mcp_body"]["retryable"] is False


def test_astro_and_bazi_approximate_engine_warning_subprocess() -> None:
    """When native .se1 files are absent, astro & bazi degrade with approximate_engine warning."""
    script = """
import json, os, tempfile, fatebridge
with tempfile.TemporaryDirectory() as empty_dir:
    os.environ["SE_EPHE_PATH"] = empty_dir
    os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] = "native"
    bazi_res = fatebridge.run(
        "bazi_birth_chart",
        {
            "birth_year": 1990, "birth_month": 5, "birth_day": 15,
            "birth_hour": 10, "birth_minute": 30, "birth_timezone": "Asia/Shanghai",
        },
        as_of="2026-10-12T02:00:00Z",
    )
    os.environ["FATEBRIDGE_DE441_DIR"] = empty_dir
    astro_res = fatebridge.run(
        "astrology_chart",
        {
            "birth_year": 1990, "birth_month": 5, "birth_day": 15,
            "birth_hour": 10, "birth_minute": 30,
            "birth_longitude": 116.4, "birth_latitude": 39.9,
            "birth_timezone": "Asia/Shanghai",
        },
        as_of="2026-10-12T02:00:00Z",
    )
    print(json.dumps({"bazi": bazi_res["run_metadata"], "astro": astro_res["run_metadata"]}, ensure_ascii=False))
"""
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60.0,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    for key in ("bazi", "astro"):
        assert data[key]["engine_is_approximate"] is True
        assert "approximate_engine" in (data[key].get("warnings") or [])


@pytest.mark.asyncio
async def test_mcp_families_scoping_and_subprocess_cli_boundaries() -> None:
    async with Client(cached_mcp_app(families="knowledge")) as scoped_client:
        disc = await call_mcp_tool(scoped_client, "discover_tools", {"detail": "brief"})
        assert disc.ok
        assert {item["tool"] for item in disc.payload["tools"]} == {
            "knowledge_catalog",
            "knowledge_read",
            "place_lookup",
        }
        blocked = await call_mcp_tool(
            scoped_client,
            "run_calculation",
            {"tool": "bazi_birth_chart", "arguments": {}},
        )
        assert not blocked.ok
        assert blocked.payload.get("error_code") == "unknown_tool"

    # Process-boundary subprocess checks: --help, doctor --mcp, and --family scoping
    help_out = call_cli(["--help"], use_subprocess=True)
    assert help_out.ok and help_out.exit_code == 0

    doctor_full = call_cli(["doctor", "--mcp"], use_subprocess=True)
    assert doctor_full.ok, doctor_full.raw_stdout or doctor_full.raw_stderr
    assert doctor_full.payload.get("mcp", {}).get("ok") is True
    assert doctor_full.payload.get("mcp_tool_count") == 3
    assert doctor_full.payload.get("mcp_capability_count") == EXPECTED_TOOL_COUNT

    doctor_scoped = call_cli(
        ["doctor", "--mcp", "--family", "knowledge"],
        use_subprocess=True,
        env={**os.environ, "FATEBRIDGE_MCP_FAMILIES": "knowledge"},
    )
    assert doctor_scoped.ok, doctor_scoped.raw_stdout or doctor_scoped.raw_stderr
    assert doctor_scoped.payload.get("mcp", {}).get("ok") is True
    assert doctor_scoped.payload.get("mcp_tool_count") == 3
    assert doctor_scoped.payload.get("mcp_capability_count") == 3
