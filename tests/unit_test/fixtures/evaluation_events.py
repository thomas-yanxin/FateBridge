"""Completed tool-call events for observable evaluation tests."""

from pydantic import JsonValue


def event(
    tool: str, arguments: dict[str, JsonValue] | None = None, server: str = "fatebridge"
) -> dict[str, JsonValue]:
    return {
        "type": "item.completed",
        "item": {
            "type": "mcp_tool_call",
            "server": server,
            "tool": tool,
            "arguments": arguments or {},
            "status": "completed",
        },
    }
