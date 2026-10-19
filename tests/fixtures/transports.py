"""Test access to mounted REST endpoints and the native MCP protocol."""

import asyncio
import json
from copy import deepcopy
from functools import lru_cache

from fastmcp import Client


def rest_handler(key):
    from fatebridge.api import app

    return next(route.endpoint for route in app.routes if route.name == f"rest_{key}")


async def mcp_text_async(name, /, **arguments):
    from fatebridge.mcp_server import app

    async with Client(app) as client:
        # This helper verifies full-payload parity. Chat delivery defaults and
        # lossless paging are exercised separately in test_result_delivery.
        result = await client.call_tool(
            name, {"response_char_limit": 0, **arguments}, raise_on_error=False
        )
        text = result.content[0].text
        assert json.loads(text) == result.structured_content
        return text


def mcp_text(name, /, **arguments):
    return asyncio.run(mcp_text_async(name, **arguments))


@lru_cache(maxsize=1)
def _mcp_schemas():
    from fatebridge.mcp_server import app

    async def load():
        async with Client(app) as client:
            return {tool.name: tool.input_schema for tool in await client.list_tools()}

    return asyncio.run(load())


def mcp_parameters(name):
    return deepcopy(_mcp_schemas()[name])
