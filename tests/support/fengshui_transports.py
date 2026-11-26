"""Native MCP calls and catalog records for residential tools."""

from fastmcp import Client

import fatebridge.mcp_server as mcp
from fatebridge.services.tool_catalog import CATALOG
from tests.support.transports import call_calculation

SPECS = {s.key.removeprefix("fengshui_"): s for s in CATALOG if s.family == "fengshui"}
_PUBLIC_NAMES = {
    **{key: spec.tool_name for key, spec in SPECS.items()},
    **{
        spec.tool_name.removeprefix("fengshui_"): spec.tool_name
        for spec in SPECS.values()
    },
}


async def mcp_call(name, inputs):
    async with Client(mcp.app) as client:
        return await call_calculation(
            client,
            _PUBLIC_NAMES.get(name, "fengshui_" + name),
            {"response_char_limit": 0, **inputs},
            raise_on_error=False,
        )
