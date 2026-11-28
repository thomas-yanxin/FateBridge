"""Shared pytest fixtures for FateBridge opaque-box E2E tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from fastmcp import Client

from tests.e2e._surfaces import DEFAULT_AS_OF, get_all_full_specs


@pytest.fixture(scope="session")
def e2e_as_of() -> str:
    """Canonical frozen UTC timestamp used across cross-surface E2E checks."""
    return DEFAULT_AS_OF


@pytest.fixture(scope="session")
def all_tool_specs() -> dict[str, dict[str, Any]]:
    """All public tool discovery records (detail='full', include_output_schema=True)."""
    return get_all_full_specs()


@pytest.fixture
def rest_client() -> Iterator[TestClient]:
    """Isolated FastAPI TestClient with runtime state reset and API key disabled."""
    import fatebridge.api as api

    original_auth = api.API_KEY_AUTHENTICATOR
    api._reset_runtime_state_for_tests()
    api.API_KEY_AUTHENTICATOR = api.ApiKeyAuthenticator(
        header_name="X-API-Key",
        api_keys={},
    )
    try:
        with TestClient(api.app) as client:
            yield client
    finally:
        api.API_KEY_AUTHENTICATOR = original_auth
        api._reset_runtime_state_for_tests()


@pytest_asyncio.fixture
async def mcp_client() -> AsyncIterator[Client]:
    """In-process FastMCP client connected to the public FateBridge MCP server."""
    from fatebridge.mcp_server import create_mcp_app

    async with Client(create_mcp_app()) as client:
        yield client
