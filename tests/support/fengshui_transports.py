"""Native MCP calls and catalog records for residential tools."""

from fastmcp import Client

import fatebridge.mcp_server as mcp
from fatebridge.services.tool_catalog import CATALOG

SPECS = {s.key.removeprefix("fengshui_"): s for s in CATALOG if s.family == "fengshui"}


async def mcp_call(name, inputs):
    async with Client(mcp.app) as client:
        return await client.call_tool(
            "fengshui_" + name,
            {"response_char_limit": 0, **inputs},
            raise_on_error=False,
        )
