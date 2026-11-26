"""Native MCP calls and catalog records for residential tools."""

from fastmcp import Client

import fatebridge.mcp_server as mcp
from fatebridge.services.tool_catalog import CATALOG
from tests.support.transports import call_calculation

SPECS = {s.name.removeprefix("fengshui_"): s for s in CATALOG if s.family == "fengshui"}
# Support xuankong_natal alias used by existing fixture helpers.
if "xuankong_house_chart" in SPECS:
    SPECS["xuankong_natal"] = SPECS["xuankong_house_chart"]

_PUBLIC_NAMES = {key: spec.name for key, spec in SPECS.items()}


async def mcp_call(name, inputs):
    async with Client(mcp.app) as client:
        return await call_calculation(
            client,
            _PUBLIC_NAMES.get(name, "fengshui_" + name),
            {"detail": "audit", **inputs},
            raise_on_error=False,
        )
