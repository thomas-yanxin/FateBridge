"""Test access to mounted REST endpoints and the native MCP protocol."""

import asyncio
from copy import deepcopy
from functools import lru_cache

from fastmcp import Client

from tests.support.transports import call_calculation, describe_capability


def rest_handler(key):
    from fatebridge.api import app

    return next(route.endpoint for route in app.routes if route.name == f"rest_{key}")


async def mcp_payload_async(name, /, **arguments):
    from fatebridge.mcp_server import app

    call_args = (
        {"include": ["*"], **arguments}
        if "include" not in arguments and "fields" not in arguments
        else arguments
    )
    async with Client(app) as client:
        result = await call_calculation(client, name, call_args, raise_on_error=False)
        assert result.structured_content is not None
        return result.structured_content


def mcp_payload(name, /, **arguments):
    return asyncio.run(mcp_payload_async(name, **arguments))


@lru_cache(maxsize=None)
def _mcp_schema(name):
    from fatebridge.mcp_server import app

    async def load():
        async with Client(app) as client:
            return (await describe_capability(client, name))["input_schema"]

    return asyncio.run(load())


def mcp_parameters(name):
    return deepcopy(_mcp_schema(name))
