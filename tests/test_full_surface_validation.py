import asyncio
import json

from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api_module
import fatebridge.mcp_server as mcp_module
from tests.fixtures.surface_payloads import (
    MCP_CASES,
    REST_GET_CASES,
    REST_POST_CASES,
)


def _build_client(monkeypatch) -> TestClient:
    api_module._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api_module,
        "API_KEY_AUTHENTICATOR",
        api_module.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    return TestClient(api_module.app)


def _assert_run_metadata(payload: dict) -> None:
    metadata = payload.get("run_metadata")
    assert isinstance(metadata, dict)
    assert metadata["tool_name"]
    assert metadata["engine"]
    assert metadata["run_id"]
    assert metadata["trace_id"]
    assert metadata["generated_at"]


def test_rest_case_map_covers_all_business_routes():
    actual_paths = {
        route.path
        for route in api_module.app.routes
        if getattr(route, "path", None)
        and not route.path.startswith("/openapi")
        and not route.path.startswith("/docs")
        and not route.path.startswith("/redoc")
    }
    # Result readers take opaque IDs from a prior calculation, so their live
    # success/auth/error cases are in test_result_delivery, not static GETs.
    result_reader_paths = {
        "/api/results/{result_id}",
        "/api/results/{result_id}/pages",
    }
    expected_paths = set(REST_GET_CASES) | set(REST_POST_CASES) | result_reader_paths

    assert expected_paths == actual_paths


def test_fastmcp_version_supports_list_tools_api():
    """The declared runtime supports discovery and native error results."""
    import inspect
    from importlib.metadata import version

    from fastmcp.tools import ToolResult
    from packaging.version import Version

    assert Version(version("fastmcp")) >= Version("3.4.2")
    assert "is_error" in inspect.signature(ToolResult).parameters

    list_tools = getattr(type(mcp_module.app), "list_tools", None)
    assert list_tools is not None, "FastMCP app is missing list_tools()"
    assert "run_middleware" in inspect.signature(list_tools).parameters


def test_mcp_case_map_covers_all_registered_tools():
    actual_names = {
        tool.name
        for tool in asyncio.run(mcp_module.app.list_tools(run_middleware=False))
    }

    assert set(MCP_CASES) == actual_names


def test_rest_health_endpoints_return_expected_contract(monkeypatch):
    client = _build_client(monkeypatch)

    for path, assertion in REST_GET_CASES.items():
        response = client.get(path)
        assert response.status_code == 200
        if path == "/metrics":
            assert "fatebridge_http_requests_total" in response.text
            continue
        assertion(response.json())


def test_rest_post_endpoints_all_accept_representative_payloads(monkeypatch):
    client = _build_client(monkeypatch)

    for path, payload_factory in REST_POST_CASES.items():
        response = client.post(path, json=payload_factory())
        assert response.status_code == 200, path
        body = response.json()
        assert "error" not in body, path
        _assert_run_metadata(body)


def test_shared_execution_accepts_all_mcp_representative_payloads():
    from fatebridge.application.execution import execute_tool
    from fatebridge.services.tool_catalog import CATALOG

    by_name = {spec.tool_name: spec for spec in CATALOG}
    for name, (_, kwargs_factory) in MCP_CASES.items():
        spec = by_name[name]
        body = execute_tool(spec, spec.request_model.model_validate(kwargs_factory()))
        assert "error" not in body, name
        _assert_run_metadata(body)


def test_fastmcp_client_accepts_all_representative_payloads():
    """Exercise protocol validation and defaults, which direct .fn skips."""

    async def run():
        async with Client(mcp_module.app) as client:
            schemas = {
                tool.name: tool.model_dump(by_alias=True)["outputSchema"]
                for tool in await client.list_tools()
            }
            for name, (_, kwargs_factory) in MCP_CASES.items():
                result = await client.call_tool(name, kwargs_factory())
                body = json.loads(result.content[0].text)
                assert "error" not in body, name
                _assert_run_metadata(body)
                assert result.structured_content == body
                Draft202012Validator(schemas[name]).validate(body)

    asyncio.run(run())
