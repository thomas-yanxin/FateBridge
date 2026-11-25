#!/usr/bin/env python3
"""FateBridge MCP discovery, calculation and result delivery."""

from __future__ import annotations

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
from fatebridge.application import result_delivery
from fatebridge.application.description import (
    describe_input_spec,
    describe_spec,
)
from fatebridge.application.discovery import discover_specs, select_mcp_specs
from fatebridge.application.execution import (
    execute_tool,
    result_is_error,
)
from fatebridge.application.response_delivery import deliver_response
from fatebridge.application.result_delivery import DEFAULT_MCP_RESPONSE_CHARS
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.core.execution_context import (
    DetailLevel,
    ExecutionOptions,
    correlate_error,
    safe_correlation,
)
from fatebridge.mcp_transport import protocol_result, register_discovery_resources
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.transports.flags import (
    FIELDS_FLAG_DESC,
    RESPONSE_LIMIT_DESC,
    SNAPSHOT_FLAG_DESC,
    STRICT_FIELDS_DESC,
    ResponseCharLimit,
)
from fatebridge.utils.errors import (
    ParameterError,
    error_response_payload,
    handle_calculation_error,
    validation_error_result,
)
from fatebridge.utils.runtime import get_log_level, load_runtime_env

__all__ = ["app", "create_mcp_app", "main"]

app: FastMCP


_MCP_INSTRUCTIONS = (
    "FateBridge 提供本地计算，助手按当前问题选择工具并解释实际结果。"
    "计算前排除生死寿命、灾祸断言、临床诊断治疗和医疗择时。"
    "只用已确认资料，不猜生时、不套默认或示例；必要缺项简短追问，未知后继续已有可答部分。"
    "区分计算、传统解释和现实建议；分数不是成功概率。"
    "已连接且定义清楚时直接调用，不为咨询查仓库或运行诊断。"
    "按当前问题、指定方法和实际时间范围选择公开能力；照片是候选，partial 只限制对应层，动作许可不阻塞普通解释。"
    "精简入口默认返回核心字段，按需用 describe_capability 查看参数和任务视图。"
    "完整导出用 detail=audit、fields=null，再读同一 run 的 result_delivery。"
    "isError 按 error_code 和 issues 的字段与说明修正后再提交；原参数仅在 retryable=true 时重试。"
    "更正资料重建受影响输入并沿用 trace_id/parent_run_id；解释未变结果不重算。"
    "工具不明确时只查所需定义；精简配置可能未公开条件分支，以当前连接和场景 availability 为准。"
    "先答要点、依据及现实建议，详略按请求。"
)


def _render_protocol_error(failure: ServiceResult, operation: str) -> ToolResult:
    return protocol_result(error_response_payload(failure, operation), failed=True)


def _unknown_tool_result(tool_name: str, operation: str) -> ToolResult:
    return _render_protocol_error(
        {
            "error": f"未知工具: {tool_name}",
            "error_code": "unknown_tool",
            "status_code": 404,
            "retryable": False,
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
            else:
                pass
            result = validation_error_result(cause)
            if context.message.name == "run_calculation":
                result = correlate_error(
                    result, safe_correlation(context.message.arguments or {})
                )
            else:
                pass
            return _render_protocol_error(result, context.message.name)


def _register_mcp_tools(server: FastMCP, exposed: list[ToolSpec]) -> None:
    """Register MCP discovery, execution and paging tools for the exposed catalog."""
    server.add_middleware(_ToolValidationFeedback())
    exposed_by_name = {spec.tool_name: spec for spec in exposed}
    allowed_tools = set(exposed_by_name)
    # note (mcp): Wire aliases work across SDK versions with different Python field names.
    meta_annotations = ToolAnnotations.model_validate(
        {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}
    )

    @server.tool(
        name="discover_capabilities",
        description="按 family、关键词或通道发现当前已公开的计算能力摘要。",
        annotations=meta_annotations,
        tags={"meta"},
    )
    def discover_capabilities(
        family: str | None = None,
        q: str | None = None,
        surface: str | None = None,
    ) -> ToolResult:
        try:
            manifest = discover_specs(
                CATALOG,
                family=family,
                q=q,
                surface=surface or "mcp",
                detail="index",
                allowed_names=allowed_tools,
            )
            return protocol_result(manifest, failed=False)
        except ParameterError as exc:
            return _render_protocol_error(exc.as_result(), "discover_capabilities")

    @server.tool(
        name="describe_capability",
        description="读取指定工具的参数 schema、推荐字段、任务视图与可选输出契约。",
        annotations=meta_annotations,
        tags={"meta"},
    )
    def describe_capability(
        tool: str,
        detail: Literal["input", "full"] = "input",
    ) -> ToolResult:
        spec = exposed_by_name.get(tool)
        if spec is None:
            return _unknown_tool_result(tool, "describe_capability")
        else:
            contract = (
                describe_spec(spec) if detail == "full" else describe_input_spec(spec)
            )
            return protocol_result(contract, failed=False)

    @server.tool(
        name="run_calculation",
        description="按工具名与参数执行确定性计算，支持 detail(compact/standard/audit) 与 fields 投影。",
        annotations=meta_annotations,
        tags={"meta"},
    )
    def run_calculation(
        tool: str,
        arguments: dict[str, object] | None = None,
        fields: Annotated[list[str] | None, Field(description=FIELDS_FLAG_DESC)] = None,
        strict_fields: Annotated[bool, Field(description=STRICT_FIELDS_DESC)] = False,
        include_snapshot_text: Annotated[
            bool | None, Field(description=SNAPSHOT_FLAG_DESC)
        ] = None,
        detail: DetailLevel = "compact",
        response_char_limit: Annotated[
            ResponseCharLimit, Field(description=RESPONSE_LIMIT_DESC)
        ] = DEFAULT_MCP_RESPONSE_CHARS,
        as_of: str | None = None,
        trace_id: str | None = None,
        parent_run_id: str | None = None,
    ) -> ToolResult:
        spec = exposed_by_name.get(tool)
        if spec is None:
            return _unknown_tool_result(tool, "run_calculation")
        else:
            pass
        controls = {
            "as_of": as_of,
            "trace_id": trace_id,
            "parent_run_id": parent_run_id,
            "detail": detail,
        }
        try:
            options = ExecutionOptions.model_validate(controls)
            request = spec.request_model.model_validate(arguments or {})
            result = execute_tool(
                spec,
                request,
                options=options,
                fields=fields,
                include_snapshot_text=include_snapshot_text,
            )
            if result_is_error(result):
                return _render_protocol_error(result, spec.operation_label_zh)
            else:
                pass
            payload = deliver_response(
                result,
                spec=spec,
                fields=fields,
                strict_fields=strict_fields,
                include_snapshot_text=include_snapshot_text,
                response_char_limit=response_char_limit,
                detail=options.detail,
            )
            return protocol_result(payload, failed=False)
        except Exception as exc:
            # note (mcp): The shared error boundary logs unexpected failures without exposing request values.
            return _render_protocol_error(
                correlate_error(
                    handle_calculation_error(exc, spec.operation_label_zh),
                    safe_correlation(controls),
                ),
                spec.operation_label_zh,
            )

    @server.tool(
        name="read_result",
        description="读取超预算落盘的同一次结果清单、分页或字段路径；传入 run_id 时执行完整性核验。",
        annotations=meta_annotations,
        tags={"meta"},
    )
    def read_result(
        result_id: str,
        offset: int | None = None,
        path: str | None = None,
        run_id: str | None = None,
    ) -> ToolResult:
        try:
            if run_id is not None:
                payload = result_delivery.RESULT_STORE.verified_page(
                    result_id,
                    run_id,
                    offset or 0,
                    path,
                    allowed_tools=allowed_tools,
                )
            elif offset is not None or path is not None:
                payload = result_delivery.RESULT_STORE.page(
                    result_id,
                    offset or 0,
                    path,
                    allowed_tools=allowed_tools,
                )
            else:
                payload = result_delivery.RESULT_STORE.manifest(
                    result_id, allowed_tools=allowed_tools
                )
            return protocol_result(payload, failed=False)
        except ParameterError as exc:
            return _render_protocol_error(exc.as_result(), "read_result")
        except ValueError as exc:
            return _render_protocol_error(
                {
                    "error": str(exc),
                    "error_code": "validation_error",
                    "status_code": 422,
                    "retryable": False,
                },
                "read_result",
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
    """Expose the four public tools for the selected calculation families."""
    _configure_runtime()
    exposed = select_mcp_specs(CATALOG, family=families)
    if not exposed:
        raise ValueError("未找到所选分类的公开工具")
    else:
        pass
    server = FastMCP(
        name="fatebridge",
        instructions=_MCP_INSTRUCTIONS,
        version=APP_VERSION,
        dereference_schemas=False,
    )
    _register_mcp_tools(server, exposed)
    register_discovery_resources(server, CATALOG, exposed)
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
else:
    pass
