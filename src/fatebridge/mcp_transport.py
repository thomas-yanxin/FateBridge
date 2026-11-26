"""MCP protocol envelope helper around shared catalog execution."""

from fastmcp.tools import ToolResult

from fatebridge.application.tool_spec import ServiceResult


def protocol_result(payload: ServiceResult, *, failed: bool) -> ToolResult:
    """Carry structured content and native MCP error status together."""
    return ToolResult(
        content=payload["error"] if failed else [],
        structured_content=payload,
        is_error=failed,
    )
