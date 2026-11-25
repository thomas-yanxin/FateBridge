"""MCP protocol contracts around the shared catalog execution functions."""

import json
from typing import Literal

from fastmcp import FastMCP
from fastmcp.tools import ToolResult

from fatebridge.application import result_delivery
from fatebridge.application.description import describe_input_spec, resolve_spec
from fatebridge.application.discovery import discover_specs
from fatebridge.application.tool_spec import ServiceResult, ToolSpec


def register_discovery_resources(
    app: FastMCP, catalog: list[ToolSpec], exposed: list[ToolSpec]
) -> None:
    """Expose summaries and on-demand contracts without extra business tools."""
    allowed_tool_names = {spec.tool_name for spec in exposed}

    def render_catalog(
        *,
        detail: Literal["index", "full"],
        family: str | None = None,
        tool: str | None = None,
    ) -> str:
        manifest = discover_specs(
            catalog,
            family=family,
            tool=tool,
            surface="mcp",
            detail=detail,
            allowed_names=allowed_tool_names,
        )
        return json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))

    @app.resource("fatebridge://catalog/summary", mime_type="application/json")
    def catalog_summary() -> str:
        """Compact summaries for this host's exposed tool set."""
        return render_catalog(detail="index")

    @app.resource("fatebridge://families/{family}", mime_type="application/json")
    def family_summary(family: str) -> str:
        """Compact tool discovery inside one or several known families."""
        return render_catalog(family=family, detail="index")

    @app.resource("fatebridge://tools/{tool}", mime_type="application/json")
    def tool_contract(tool: str) -> str:
        """Full shared contract for one exposed tool; hidden tools stay hidden."""
        if tool not in allowed_tool_names:
            raise ValueError("工具未在当前 MCP 配置中公开")
        else:
            pass
        return render_catalog(tool=tool, detail="full")

    @app.resource("fatebridge://tools/{tool}/input", mime_type="application/json")
    def tool_input_contract(tool: str) -> str:
        """Small call contract and output roots; full schemas remain on demand."""
        spec = resolve_spec(catalog, tool)
        if spec is None or spec.tool_name not in allowed_tool_names:
            raise ValueError("工具未在当前 MCP 配置中公开")
        else:
            pass
        return json.dumps(
            {
                "detail": "input",
                "matched_count": 1,
                "tools": [describe_input_spec(spec)],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @app.resource("fatebridge://results/{result_id}", mime_type="application/json")
    def result_manifest(result_id: str) -> str:
        """Fields and paging references for one retained, unchanged result."""
        return json.dumps(
            result_delivery.RESULT_STORE.manifest(
                result_id, allowed_tools=allowed_tool_names
            ),
            ensure_ascii=False,
        )

    @app.resource(
        "fatebridge://results/{result_id}/pages/{offset}", mime_type="application/json"
    )
    def result_page(result_id: str, offset: int) -> str:
        """A complete JSON page envelope; join text fragments only when needed."""
        return json.dumps(
            result_delivery.RESULT_STORE.page(
                result_id, offset, allowed_tools=allowed_tool_names
            ),
            ensure_ascii=False,
        )

    @app.resource(
        "fatebridge://results/{result_id}/fields/{path}/{offset}",
        mime_type="application/json",
    )
    def result_field_page(result_id: str, path: str, offset: int) -> str:
        """Read a dotted field, including array numeric indices, from the same run."""
        return json.dumps(
            result_delivery.RESULT_STORE.page(
                result_id, offset, path, allowed_tools=allowed_tool_names
            ),
            ensure_ascii=False,
        )

    @app.resource(
        "fatebridge://results/{result_id}/verified/{run_id}/{offset}",
        mime_type="application/json",
    )
    def verified_result_page(result_id: str, run_id: str, offset: int) -> str:
        """Verify the entire original payload before reading one page."""
        return json.dumps(
            result_delivery.RESULT_STORE.verified_page(
                result_id, run_id, offset, allowed_tools=allowed_tool_names
            ),
            ensure_ascii=False,
        )

    @app.resource(
        "fatebridge://results/{result_id}/verified/{run_id}/fields/{path}/{offset}",
        mime_type="application/json",
    )
    def verified_result_field_page(
        result_id: str, run_id: str, path: str, offset: int
    ) -> str:
        """Verify the full payload and select a field from those same bytes."""
        return json.dumps(
            result_delivery.RESULT_STORE.verified_page(
                result_id, run_id, offset, path, allowed_tools=allowed_tool_names
            ),
            ensure_ascii=False,
        )


def protocol_result(payload: ServiceResult, *, failed: bool) -> ToolResult:
    """Carry structured content and native MCP error status together."""
    return ToolResult(
        content=payload["error"] if failed else [],
        structured_content=payload,
        is_error=failed,
    )
