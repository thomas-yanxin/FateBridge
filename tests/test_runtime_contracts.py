"""Runtime imports and native protocol responses keep their contracts."""

import asyncio
import json
import subprocess
import sys

import pytest
from fastmcp import Client

import fatebridge.mcp_server as mcp


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
