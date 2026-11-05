"""Reuse the MCP boundary's validated request with original field presence."""

from contextvars import ContextVar

from pydantic import BaseModel

MCP_REQUEST: ContextVar[tuple[str, BaseModel] | None] = ContextVar(
    "fatebridge_mcp_request", default=None
)
