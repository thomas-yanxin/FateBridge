#!/usr/bin/env python3
"""FateBridge MCP discovery and deterministic calculation."""

from __future__ import annotations

import difflib
import logging
import os
from functools import cache
from typing import Annotated, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ValidationError as MCPValidationError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools import ToolResult
from mcp.types import CallToolRequestParams, ToolAnnotations
from pydantic import Field, ValidationError

from fatebridge import __version__ as APP_VERSION
from fatebridge.application.discovery import discover_specs, select_mcp_specs
from fatebridge.application.execution import execute_with_receipt, result_is_error
from fatebridge.application.response_delivery import deliver_response
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.core.execution_context import DetailLevel, ExecutionOptions
from fatebridge.mcp_transport import protocol_result
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.transports.flags import FIELDS_FLAG_DESC
from fatebridge.utils.errors import (
    ParameterError,
    error_response_payload,
    handle_calculation_error,
    validation_error_result,
)
from fatebridge.utils.runtime import get_log_level, load_runtime_env

__all__ = ["app", "create_mcp_app", "main"]

app: FastMCP


MCP_INSTRUCTIONS = (
    "FateBridge 提供本地确定性计算，公开 discover_tools 与 run_calculation 两个入口。"
    "计算前排除生死寿命、灾祸断言、临床诊断治疗和医疗择时。"
    "只用已确认资料，不猜生时、不套默认或示例；必要缺项简短追问，未知后继续已有可答部分。"
    "区分计算事实、传统解释与现实建议；分数不是成功概率。"
    "已知工具定义时直接调用 run_calculation；未知工具或参数时调用 discover_tools(q=...) 或 discover_tools(tool=...)。"
    "run_calculation 默认 detail=compact 返回核心业务字段；需要指定子字段传 fields（严格校验路径，错误时附可用字段）；需要完整输出与方法依据传 detail=audit。"
    "isError=true 时按 error_code 和 issues[].path / constraints 修正参数后重调，仅 retryable=true 才按原参数重试。"
)


def _render_protocol_error(failure: ServiceResult, operation: str) -> ToolResult:
    return protocol_result(error_response_payload(failure, operation), failed=True)


def _unknown_tool_result(
    tool_name: str, operation: str, allowed_tools: set[str]
) -> ToolResult:
    suggestions = difflib.get_close_matches(
        tool_name, sorted(allowed_tools), n=5, cutoff=0.4
    )
    issue: dict[str, object] = {"path": "tool", "code": "unknown_tool"}
    if suggestions:
        issue["constraints"] = {"suggestions": suggestions}
    return _render_protocol_error(
        {
            "error": f"未知工具: {tool_name}",
            "error_code": "unknown_tool",
            "status_code": 404,
            "retryable": False,
            "issues": [issue],
        },
        operation,
    )


class _ToolValidationFeedback(Middleware):
    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: CallNext[CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        try:
            return await call_next(context)
        except (MCPValidationError, ValidationError) as exc:
            cause = exc if isinstance(exc, ValidationError) else exc.__cause__
            if not isinstance(cause, ValidationError):
                raise
            return _render_protocol_error(
                validation_error_result(cause), context.message.name
            )


def _register_mcp_tools(server: FastMCP, exposed: list[ToolSpec]) -> None:
    """Register MCP discovery and calculation tools for the exposed catalog."""
    server.add_middleware(_ToolValidationFeedback())
    exposed_by_name = {spec.name: spec for spec in exposed}
    allowed_tools = set(exposed_by_name)
    # note (mcp): Wire aliases work across SDK versions with different Python field names.
    meta_annotations = ToolAnnotations.model_validate(
        {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}
    )

    @server.tool(
        name="discover_tools",
        description=(
            "按 family、关键词 q 或精确 tool 发现当前公开的计算能力与调用契约。"
            "无参数调用返回全部分类计数与工具摘要；指定 tool 返回输入参数 schema、示例与推荐字段；"
            "detail=full 返回 output_fields，需完整 output_schema 时传 include_output_schema=True。"
        ),
        annotations=meta_annotations,
        tags={"meta"},
    )
    def discover_tools(
        family: str | None = None,
        q: str | None = None,
        tool: str | None = None,
        detail: Literal["summary", "full"] = "summary",
        include_output_schema: bool = False,
    ) -> ToolResult:
        try:
            manifest = discover_specs(
                CATALOG,
                family=family,
                q=q,
                tool=tool,
                surface="mcp",
                detail=detail,
                include_output_schema=include_output_schema,
                allowed_names=allowed_tools,
            )
            return protocol_result(manifest, failed=False)
        except ParameterError as exc:
            return _render_protocol_error(exc.as_result(), "discover_tools")

    @server.tool(
        name="run_calculation",
        description=(
            "按工具名与参数执行确定性计算。"
            "支持 detail（compact 默认精简事实 / audit 完整结果与取证）、fields（严格字段投影）与 as_of（冻结当前时刻）。"
        ),
        annotations=meta_annotations,
        tags={"meta"},
    )
    def run_calculation(
        tool: str,
        arguments: dict[str, object] | None = None,
        detail: DetailLevel = "compact",
        fields: Annotated[list[str] | None, Field(description=FIELDS_FLAG_DESC)] = None,
        as_of: str | None = None,
    ) -> ToolResult:
        spec = exposed_by_name.get(tool)
        if spec is None:
            return _unknown_tool_result(tool, "run_calculation", allowed_tools)
        try:
            options = ExecutionOptions.model_validate(
                {"as_of": as_of, "detail": detail}
            )
            request = spec.request_model.model_validate(arguments or {})
            result = execute_with_receipt(
                spec,
                request,
                options=options,
            )
            if result_is_error(result):
                return _render_protocol_error(result, spec.operation_label_zh)
            payload = deliver_response(
                result,
                spec=spec,
                fields=fields,
                detail=options.detail,
            )
            return protocol_result(payload, failed=False)
        except Exception as exc:
            # note (mcp): The shared error boundary logs unexpected failures without exposing request values.
            return _render_protocol_error(
                handle_calculation_error(exc, spec.operation_label_zh),
                spec.operation_label_zh,
            )


@cache
def _configure_runtime() -> None:
    load_runtime_env()
    log_level = logging.getLevelName(get_log_level())
    logging.basicConfig(
        level=log_level if isinstance(log_level, int) else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def create_mcp_app(families: str | None = None) -> FastMCP:
    """Expose the two public tools for the selected calculation families."""
    _configure_runtime()
    exposed = select_mcp_specs(CATALOG, family=families)
    if not exposed:
        raise ValueError("未找到所选分类的公开工具")
    server = FastMCP(
        name="fatebridge",
        instructions=MCP_INSTRUCTIONS,
        version=APP_VERSION,
        dereference_schemas=False,
    )
    _register_mcp_tools(server, exposed)
    return server


@cache
def _default_mcp_app() -> FastMCP:
    _configure_runtime()
    return create_mcp_app(os.getenv("FATEBRIDGE_MCP_FAMILIES") or None)


def __getattr__(name: str) -> FastMCP:
    """Expose the default server when a host resolves the app entry point."""
    if name == "app":
        return _default_mcp_app()
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def main() -> None:
    _default_mcp_app().run(show_banner=False)


if __name__ == "__main__":
    main()
