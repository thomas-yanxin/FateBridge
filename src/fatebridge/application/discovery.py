"""Progressive catalog discovery shared by REST, CLI and MCP."""

import difflib
from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from fatebridge.application.description import (
    describe_input_spec,
    describe_spec,
    resolve_spec,
    summarize_spec,
)
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.utils.errors import ParameterError, validation_error_result

ToolSurface = Literal["rest", "mcp", "cli"]


class DiscoveryQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    family: str | None = None
    q: str | None = None
    tool: str | None = None
    surface: ToolSurface | None = None
    detail: Literal["summary", "full"] = "summary"


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
            issue: dict[str, Any] = {"path": "tool", "code": "unknown_tool"}
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
    allowed_names: set[str] | None = None,
) -> dict[str, Any]:
    try:
        query = DiscoveryQuery.model_validate(
            dict(
                family=family,
                q=q,
                tool=tool,
                surface=surface,
                detail=detail,
            )
        )
    except ValidationError as exc:
        failure = validation_error_result(exc)
        raise ParameterError(failure["error"], failure["issues"]) from None

    pool = (
        [spec for spec in specs if spec.name in allowed_names]
        if allowed_names is not None
        else specs
    )
    selected = select_specs(
        specs,
        **query.model_dump(exclude={"detail"}),
        allowed_names=allowed_names,
    )
    if query.tool is not None:
        describe = describe_spec if query.detail == "full" else describe_input_spec
    else:
        describe = describe_spec if query.detail == "full" else summarize_spec
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
