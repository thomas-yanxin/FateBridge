"""Progressive catalog discovery shared by REST, CLI and MCP."""

import difflib
from collections import Counter
from collections.abc import Callable
from functools import partial
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from fatebridge.application.description import (
    describe_input_spec,
    describe_spec,
    resolve_spec,
    summarize_spec,
)
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.utils.errors import ParameterError, validation_error_result

ToolSurface = Literal["rest", "mcp", "cli"]


class DiscoveryQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    family: str | None = None
    q: str | None = None
    tool: str | None = None
    surface: ToolSurface | None = None
    detail: Literal["summary", "full"] = "summary"
    include_output_schema: bool = False


def select_mcp_specs(
    specs: list[ToolSpec],
    *,
    family: str | None = None,
) -> list[ToolSpec]:
    """Select an explicit MCP loading profile without changing domain contracts."""
    return select_specs(specs, family=family, surface="mcp")


def select_specs(
    specs: list[ToolSpec],
    *,
    family: str | None = None,
    q: str | None = None,
    tool: str | None = None,
    surface: ToolSurface | None = None,
    allowed_names: set[str] | None = None,
) -> list[ToolSpec]:
    """Filter declarations before materializing any expensive schemas."""
    selected = specs
    if allowed_names is not None:
        selected = [spec for spec in selected if spec.name in allowed_names]
    if family is not None:
        families = [part.strip() for part in family.split(",")]
        known = {spec.family for spec in specs}
        if any(not name or name not in known for name in families):
            raise ParameterError(
                "工具分类无效",
                [
                    {
                        "path": "family",
                        "code": "unknown_family",
                        "constraints": {"allowed": sorted(known)},
                    }
                ],
            )
        selected = [spec for spec in selected if spec.family in families]
    if surface:
        available = {
            "rest": lambda spec: bool(spec.rest_path),
            "mcp": lambda spec: spec.expose_mcp,
            "cli": lambda _spec: True,
        }
        selected = [spec for spec in selected if available[surface](spec)]
    if tool is not None:
        resolved = resolve_spec(selected, tool)
        if resolved is None:
            candidates = sorted(spec.name for spec in selected)
            suggestions = difflib.get_close_matches(tool, candidates, n=5, cutoff=0.4)
            issue: dict[str, object] = {"path": "tool", "code": "unknown_tool"}
            if suggestions:
                issue["constraints"] = {"suggestions": suggestions}
            raise ParameterError(f"未知工具: {tool}", [issue], status_code=404)
        selected = [resolved]
    if q:
        needle = q.strip().casefold()
        selected = [
            spec
            for spec in selected
            if needle
            in " ".join(
                (
                    spec.name,
                    spec.summary,
                    spec.operation_label_zh,
                    spec.family,
                )
            ).casefold()
        ]
    return selected


def discover_specs(
    specs: list[ToolSpec],
    *,
    family: str | None = None,
    q: str | None = None,
    tool: str | None = None,
    surface: str | None = None,
    detail: str = "summary",
    include_output_schema: bool = False,
    allowed_names: set[str] | None = None,
) -> ServiceResult:
    try:
        query = DiscoveryQuery.model_validate(
            dict(
                family=family,
                q=q,
                tool=tool,
                surface=surface,
                detail=detail,
                include_output_schema=include_output_schema,
            )
        )
    except ValidationError as exc:
        failure = validation_error_result(exc)
        raise ParameterError(failure["error"], failure["issues"]) from None

    if (
        query.detail == "full"
        and query.tool is None
        and query.family is None
        and query.q is None
    ):
        raise ParameterError(
            "detail=full 需配合 tool、family 或 q 过滤，避免全量输出超出上下文预算",
            [
                {
                    "path": "detail",
                    "code": "filter_required_for_full_detail",
                    "constraints": {"require_one_of": ["tool", "family", "q"]},
                }
            ],
        )

    pool = (
        [spec for spec in specs if spec.name in allowed_names]
        if allowed_names is not None
        else specs
    )
    selected = select_specs(
        specs,
        **query.model_dump(exclude={"detail", "include_output_schema"}),
        allowed_names=allowed_names,
    )
    describe: Callable[[ToolSpec], dict[str, Any]]
    if query.detail == "full":
        describe = partial(
            describe_spec, include_output_schema=query.include_output_schema
        )
    elif query.tool is not None:
        describe = describe_input_spec
    else:
        describe = summarize_spec
    tools = [describe(spec) for spec in selected]
    families = dict(sorted(Counter(spec.family for spec in pool).items()))
    return {
        "counts": {
            "rest": sum(bool(spec.rest_path) for spec in pool),
            "mcp": sum(spec.expose_mcp for spec in pool),
            "total": len(pool),
        },
        "families": families,
        "matched_count": len(selected),
        "detail": query.detail,
        "tools": tools,
    }


def describe_batch_interface() -> ServiceResult:
    """Return the shared self-description contract for batch execution across CLI, REST, and MCP."""
    from fatebridge.application.batch import MAX_BATCH_CALLS, BatchRequest

    example_input: dict[str, Any] = {
        "subjects": {
            "demo": {
                "name": "演示甲",
                "gender": "male",
                "birth_date": "1990-05-15",
                "birth_time": "10:30:00",
                "birth_place": "北京",
                "timezone": "Asia/Shanghai",
            }
        },
        "calls": [
            {
                "id": "bazi_chart",
                "tool": "bazi_birth_chart",
                "subject": "demo",
                "fields": ["bazi_birth.day_master"],
            },
            {
                "id": "minggua",
                "tool": "fengshui_minggua",
                "subject": "demo",
            },
        ],
        "detail": "compact",
    }
    BatchRequest.model_validate(example_input)
    return {
        "tool": "batch",
        "summary": "在单次无状态调用中对一个或多个对象（subjects）批量执行多个计算工具（calls），共享冻结时刻 as_of 并按调用隔离错误。",
        "surface": ["cli", "rest", "mcp"],
        "rest_path": "/api/batch",
        "mcp_tool": "run_batch",
        "limits": {"max_calls": MAX_BATCH_CALLS},
        "input_schema": BatchRequest.model_json_schema(),
        "example_input": example_input,
        "cli_example": "fatebridge batch --request-file batch.json",
    }
