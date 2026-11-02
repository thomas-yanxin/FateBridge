"""Retired adapters stay removed; canonical transports keep their contracts."""

import asyncio
import importlib.util
import json
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import fatebridge.mcp_server as mcp
from fatebridge.services.tool_catalog import CATALOG

RETIRED_MODULES = (
    "fatebridge.core.tool_spec",
    "fatebridge.core.discovery",
    "fatebridge.core.scenarios",
    "fatebridge.core.request_models",
    "fatebridge.core.astrology",
    "fatebridge.utils.helpers",
)


@pytest.mark.parametrize("module", RETIRED_MODULES)
def test_retired_import_paths_do_not_resolve(module):
    assert importlib.util.find_spec(module) is None


def test_retired_route_and_command_are_absent(monkeypatch):
    assert all(spec.key != "calculate_legacy" for spec in CATALOG)
    assert "/api/calculate" not in api.app.openapi()["paths"]
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as client:
        assert client.post("/api/calculate", json={}).status_code == 404
        assert client.post("/api/cn/bazi/birth", json={}).status_code == 422


def test_adapters_do_not_reexport_models_services_or_text_tools():
    assert not hasattr(api, "FateBridgeRequest")
    assert not hasattr(api, "calculate_astro_chart")
    assert not hasattr(api, "calculate_bazi_birth")
    assert not hasattr(mcp, "gua_meiyi")
    assert not hasattr(mcp, "_render_tool_response")
    assert not hasattr(mcp, "_render_tool_error")
    from fatebridge import mcp_transport
    from fatebridge.core import (
        local_techniques,
        metaphysics,
        predictive,
        response_models,
    )
    from fatebridge.core.local_techniques import chart
    from fatebridge.services import calculation, timing, tool_catalog

    assert not hasattr(tool_catalog, "calculate_bazi_birth")
    assert not hasattr(tool_catalog, "person_invoke")
    assert not hasattr(calculation, "_render_destiny_analysis")
    assert not hasattr(timing, "calculate_nongli_time")
    assert not hasattr(predictive, "build_return_payload")
    assert not hasattr(local_techniques, "build_pseudo_chart")
    assert not hasattr(chart, "build_pseudo_chart")
    assert not hasattr(response_models, "Planet")
    for name in (
        "MetaphysicsSeed",
        "kongwang_for_ganzhi",
        "build_ziwei_chart",
        "build_ziwei_horoscope",
        "build_ziwei_rules",
        "build_liureng_board",
        "build_liureng_runyear",
        "build_qimen_board",
        "build_taiyi_board",
        "build_jinkou_board",
    ):
        assert not hasattr(metaphysics, name), name
    assert not hasattr(mcp_transport, "native_tool_function")


@pytest.mark.parametrize(
    "arguments",
    [
        {"name": ["111", "000"], "compact": False, "include_snapshot_text": False},
        {"name": ["111"], "fields": ["missing"], "strict_fields": True},
    ],
)
def test_native_success_and_error_have_matching_text_and_structured_content(arguments):
    async def run():
        async with Client(mcp.create_mcp_app(families="divination")) as client:
            result = await client.call_tool(
                "gua_meiyi", arguments, raise_on_error=False
            )
            payload = json.loads(result.content[0].text)
            assert payload == result.structured_content
            assert result.is_error is ("error_code" in payload)
            if not arguments.get("strict_fields"):
                assert "\n" in result.content[0].text
                assert "snapshot_text" not in payload

    asyncio.run(run())


def test_mcp_import_inside_running_loop_has_no_coroutine_warning():
    code = """
import asyncio, gc, warnings
warnings.simplefilter('error', RuntimeWarning)
async def load():
    from fastmcp import Client
    import fatebridge.mcp_server as module
    async with Client(module.app) as client:
        assert any(tool.name == 'gua_meiyi' for tool in await client.list_tools())
    gc.collect()
asyncio.run(load())
"""
    proc = subprocess.run(
        [sys.executable, "-W", "error::RuntimeWarning", "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert "never awaited" not in proc.stderr


def test_classical_rules_import_without_predictive_backend():
    code = """
import sys
from fatebridge.core.classical_western import bound_lord
assert bound_lord('Aries', 0.0) == 'Jupiter'
assert 'fatebridge.core.predictive._common' not in sys.modules
assert 'kerykeion' not in sys.modules
"""
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=30
    )
    assert proc.returncode == 0, proc.stderr
