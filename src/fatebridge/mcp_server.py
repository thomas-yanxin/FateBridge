#!/usr/bin/env python3
"""FateBridge MCP discovery and deterministic calculation."""

import logging
from functools import cache
from typing import TYPE_CHECKING, Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ValidationError as MCPValidationError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools import ToolResult
from mcp.types import CallToolRequestParams, ToolAnnotations
from pydantic import Field, ValidationError

from fatebridge import __version__ as APP_VERSION
from fatebridge.application.delivery_flags import (
    FIELDS_FLAG_DESC,
    INCLUDE_FLAG_DESC,
)
from fatebridge.utils.errors import error_response_payload
from fatebridge.utils.runtime import get_log_level, get_mcp_families, load_runtime_env

if TYPE_CHECKING:
    from fatebridge.application.tool_spec import ServiceResult, ToolSpec

__all__ = ["app", "create_mcp_app", "main"]

app: FastMCP


MCP_INSTRUCTIONS = (
    "FateBridge 提供本地确定性计算，公开 discover_tools、run_calculation 与 run_batch 三个入口。"
    "计算前排除生死寿命、灾祸断言、临床诊断治疗和医疗择时。"
    "只用已确认资料，不猜生时、不套默认或示例；必要缺项简短追问，未知后继续已有可答部分。"
    "区分计算事实、传统解释与现实建议。"
    "已知工具定义时直接调用 run_calculation；未知工具或参数时调用 discover_tools(q=...) 或 discover_tools(tool=...)。"
    "同一对象跨多体系计算或多人合盘时优先调用 run_batch，通过 subjects、context（共享问事/分析时刻与地点）、defaults 与 calls 一次性执行并共享同一冻结时刻 as_of，避免重复出生与地点参数。"
    "run_calculation 与 run_batch 默认返回核心业务字段，省略项见 run_metadata.omitted_fields；可用 include 追加路径、evidence_views 名称或 ['*'] 获取无损全量，或用 fields 仅返回指定路径（include 与 fields 互斥，无效路径报错并附可用字段）。"
    "isError=true 时按 error_code 和 issues[].path / constraints 修正参数后重调，仅 retryable=true 才按原参数重试。"
)


def protocol_result(payload: "ServiceResult", *, failed: bool) -> ToolResult:
    """Carry structured content and native MCP error status together."""
    return ToolResult(
        content=payload["error"] if failed else [],
        structured_content=payload,
        is_error=failed,
    )


def _render_protocol_error(failure: "ServiceResult", operation: str) -> ToolResult:
    return protocol_result(error_response_payload(failure, operation), failed=True)


class _ToolValidationFeedback(Middleware):
    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: CallNext[CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        try:
            return await call_next(context)
        except (MCPValidationError, ValidationError) as exc:
            from pydantic_core import ErrorDetails

            from fatebridge.application.batch import BatchRequest
            from fatebridge.utils.errors import validation_issues_result

            cause = exc if isinstance(exc, ValidationError) else exc.__cause__
            if not isinstance(cause, ValidationError):
                raise
            tool_name = context.message.name
            root_model = BatchRequest if tool_name == "run_batch" else None
            allowed_fields = (
                ("tool", "arguments", "include", "fields", "as_of")
                if tool_name == "run_calculation"
                else (
                    BatchRequest.model_fields.keys()
                    if tool_name == "run_batch"
                    else (
                        (
                            "family",
                            "q",
                            "tool",
                            "tools",
                            "detail",
                            "include_output_schema",
                        )
                        if tool_name == "discover_tools"
                        else None
                    )
                )
            )
            entries: list[ErrorDetails] = [
                (
                    {
                        **item,
                        "type": "extra_forbidden",
                        "msg": "Extra inputs are not permitted",
                    }
                    if item["type"] == "unexpected_keyword_argument"
                    else item
                )
                for item in cause.errors(include_input=False, include_url=False)
            ]
            return _render_protocol_error(
                validation_issues_result(
                    entries,
                    allowed_fields=allowed_fields,
                    root_model=root_model,
                ),
                tool_name,
            )


def _register_mcp_tools(server: FastMCP, exposed: "list[ToolSpec]") -> None:
    """Register MCP discovery and calculation tools for the exposed catalog."""
    from fatebridge.application.batch import (
        AnalysisContext,
        BatchCall,
        BatchRequest,
        SubjectProfile,
        execute_batch,
    )
    from fatebridge.application.discovery import DiscoveryDetail, discover_specs
    from fatebridge.application.execution import (
        run_guarded_operation,
        run_tool,
    )
    from fatebridge.utils.errors import ParameterError, unknown_tool_error

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
            "按 family/q/tool/tools 发现计算能力与契约。无参返回摘要；单 tool 直接返回契约；"
            "detail=brief|summary|full，full 加 include_output_schema=True 含输出 schema。"
        ),
        annotations=meta_annotations,
        tags={"meta"},
    )
    def discover_tools(
        family: str | None = None,
        q: str | None = None,
        tool: str | None = None,
        tools: str | list[str] | None = None,
        detail: DiscoveryDetail = "summary",
        include_output_schema: bool = False,
    ) -> ToolResult:
        try:
            manifest = discover_specs(
                exposed,
                family=family,
                q=q,
                tool=tool,
                tools=tools,
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
            "支持 include（追加路径/视图名/'*'）、fields（严格投影，与 include 互斥）与 as_of（冻结时刻）。"
        ),
        annotations=meta_annotations,
        tags={"meta"},
    )
    def run_calculation(
        tool: str,
        arguments: dict[str, object] | None = None,
        include: Annotated[
            list[str] | None, Field(description=INCLUDE_FLAG_DESC)
        ] = None,
        fields: Annotated[list[str] | None, Field(description=FIELDS_FLAG_DESC)] = None,
        as_of: str | None = None,
    ) -> ToolResult:
        spec = exposed_by_name.get(tool)
        if spec is None:
            err = unknown_tool_error(tool, allowed_tools).as_result()
            err["error_code"] = "unknown_tool"
            return _render_protocol_error(err, "run_calculation")
        outcome = run_tool(
            spec,
            arguments,
            include=include,
            fields=fields,
            as_of=as_of,
        )
        if outcome.failed:
            return _render_protocol_error(outcome.payload, outcome.operation)
        return protocol_result(outcome.payload, failed=False)

    @server.tool(
        name="run_batch",
        description=(
            "单次无状态批量执行（1-32 calls），自动映射 subjects、context、defaults 与 arguments，"
            "共享 as_of。支持单条 include/fields 与 stop_on_error。"
        ),
        annotations=meta_annotations,
        tags={"meta"},
    )
    def run_batch(
        calls: Annotated[
            list[BatchCall],
            Field(
                min_length=1,
                max_length=32,
                description="计算调用列表",
            ),
        ],
        subjects: Annotated[
            dict[str, SubjectProfile] | None,
            Field(description="共享对象档案字典"),
        ] = None,
        context: Annotated[
            AnalysisContext | None,
            Field(description="共享分析时刻与地点上下文"),
        ] = None,
        defaults: Annotated[
            dict[str, object] | None,
            Field(description="共享默认参数"),
        ] = None,
        as_of: str | None = None,
        stop_on_error: bool = False,
    ) -> ToolResult:
        outcome = run_guarded_operation(
            "run_batch",
            lambda: execute_batch(
                exposed_by_name,
                BatchRequest.model_validate(
                    {
                        "subjects": {} if subjects is None else subjects,
                        "context": context,
                        "defaults": {} if defaults is None else defaults,
                        "calls": calls,
                        "as_of": as_of,
                        "stop_on_error": stop_on_error,
                    }
                ),
            ),
            allowed_fields=BatchRequest.model_fields.keys(),
            root_model=BatchRequest,
        )
        if outcome.failed:
            return _render_protocol_error(outcome.payload, outcome.operation)
        return protocol_result(outcome.payload, failed=False)


@cache
def _configure_runtime() -> None:
    load_runtime_env()
    log_level = logging.getLevelName(get_log_level())
    logging.basicConfig(
        level=log_level if isinstance(log_level, int) else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def create_mcp_app(families: str | None = None) -> FastMCP:
    """Expose the three public meta tools for the selected calculation families."""
    from fatebridge.application.discovery import select_mcp_specs
    from fatebridge.services.tool_catalog import all_catalog

    _configure_runtime()
    exposed = select_mcp_specs(all_catalog(), family=families)
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
    return create_mcp_app(get_mcp_families())


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
