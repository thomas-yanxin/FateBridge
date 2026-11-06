"""Progressive catalog discovery shared by REST, CLI and MCP resources."""

from typing import Any, Dict, List, Literal, Optional, Set

from pydantic import BaseModel, ConfigDict, ValidationError

from fatebridge.application.description import (
    describe_spec,
    resolve_spec,
    spec_is_cli_safe,
    summarize_spec,
)
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.utils.errors import ParameterError, validation_error_result

ToolSurface = Literal["rest", "mcp", "cli"]


class DiscoveryQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    family: Optional[str] = None
    q: Optional[str] = None
    tool: Optional[str] = None
    surface: Optional[ToolSurface] = None
    detail: Literal["summary", "full"] = "full"


def select_mcp_specs(
    specs: List[ToolSpec],
    *,
    family: Optional[str] = None,
) -> List[ToolSpec]:
    """Select an explicit MCP loading profile without changing domain contracts."""
    return select_specs(specs, family=family, surface="mcp")


def select_specs(
    specs: List[ToolSpec],
    *,
    family: Optional[str] = None,
    q: Optional[str] = None,
    tool: Optional[str] = None,
    surface: Optional[ToolSurface] = None,
    allowed_names: Optional[Set[str]] = None,
) -> List[ToolSpec]:
    """Filter declarations before materializing any expensive schemas."""
    selected = specs
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
    if tool is not None:
        resolved = resolve_spec(specs, tool)
        if resolved is None:
            raise ParameterError(
                "工具名称无效", [{"path": "tool", "code": "unknown_tool"}]
            )
        selected = [spec for spec in selected if spec is resolved]
    if surface:
        available = {
            "rest": lambda spec: bool(spec.rest_path),
            "mcp": lambda spec: bool(spec.mcp_name),
            "cli": spec_is_cli_safe,
        }
        selected = [spec for spec in selected if available[surface](spec)]
    if allowed_names is not None:
        selected = [spec for spec in selected if spec.tool_name in allowed_names]
    if q:
        needle = q.strip().casefold()
        selected = [
            spec
            for spec in selected
            if needle
            in " ".join(
                (
                    spec.key,
                    spec.tool_name,
                    spec.summary,
                    spec.operation_label_zh,
                    spec.family,
                )
            ).casefold()
        ]
    return selected


def discover_specs(
    specs: List[ToolSpec],
    *,
    family: Optional[str] = None,
    q: Optional[str] = None,
    tool: Optional[str] = None,
    surface: Optional[str] = None,
    detail: str = "full",
    allowed_names: Optional[Set[str]] = None,
) -> Dict[str, Any]:
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
    selected = select_specs(
        specs, **query.model_dump(exclude={"detail"}), allowed_names=allowed_names
    )
    describe = summarize_spec if query.detail == "summary" else describe_spec
    return {
        # Counts retain their original global-catalog meaning under filtering.
        "counts": {
            "rest": sum(bool(spec.rest_path) for spec in specs),
            "mcp": sum(bool(spec.mcp_name) for spec in specs),
            "total": len(specs),
        },
        "matched_count": len(selected),
        "detail": query.detail,
        "tools": [describe(spec) for spec in selected],
    }
