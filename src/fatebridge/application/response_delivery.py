"""Prepare shared output before transport-specific JSON serialization."""

from collections.abc import Iterable

from pydantic import JsonValue

from fatebridge.application.examples import evidence_views
from fatebridge.application.projection import (
    include_issues,
    project_fields,
    prune_omitted_paths,
)
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.utils.errors import ParameterError


def validate_delivery_controls(
    include: Iterable[str] | None,
    fields: Iterable[str] | None,
) -> None:
    """Reject mutually exclusive include and fields delivery controls."""
    if include is not None and fields is not None:
        raise ParameterError(
            "include 与 fields 不能同时指定",
            [
                {
                    "path": "fields",
                    "code": "conflicting_delivery_controls",
                    "message": "include 与 fields 互斥，请仅指定其一",
                    "constraints": {
                        "available": ["include", "fields"],
                        "mutually_exclusive_with": ["include"],
                    },
                }
            ],
        )


def _without_omitted_fields(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    metadata = payload.get("run_metadata")
    if isinstance(metadata, dict) and "omitted_fields" in metadata:
        return {
            **payload,
            "run_metadata": {
                key: value for key, value in metadata.items() if key != "omitted_fields"
            },
        }
    return payload


def deliver_response(
    payload: dict[str, JsonValue],
    *,
    spec: ToolSpec | None = None,
    include: list[str] | None = None,
    fields: list[str] | None = None,
    failed: bool = False,
) -> dict[str, JsonValue]:
    """Deliver isomorphic canonical output with default_omit pruning, include, or strict fields projection."""
    validate_delivery_controls(include, fields)
    if failed:
        return _without_omitted_fields(payload)

    if fields:
        return _without_omitted_fields(project_fields(payload, fields))

    include_items = list(dict.fromkeys(include)) if include else []
    omit_patterns = spec.default_omit if spec is not None else ()
    unomit_patterns: list[str] = []

    if include_items:
        views = evidence_views(spec) if spec is not None else None
        issues = include_issues(
            payload,
            include_items,
            views=views,
            default_omit=omit_patterns,
        )
        if issues:
            raise ParameterError("输出包含字段无效", issues)
        if "*" in include_items:
            return _without_omitted_fields(payload)
        for item in include_items:
            if views is not None and item in views:
                unomit_patterns.extend(views[item]["fields"])
                if item in payload:
                    unomit_patterns.append(item)
            else:
                unomit_patterns.append(item)

    if not omit_patterns:
        return _without_omitted_fields(payload)

    pruned, omitted = prune_omitted_paths(payload, omit_patterns, unomit_patterns)
    metadata = pruned.get("run_metadata")
    if omitted and isinstance(metadata, dict):
        omitted_json: list[JsonValue] = list(omitted)
        return {
            **pruned,
            "run_metadata": {
                **metadata,
                "omitted_fields": omitted_json,
            },
        }
    return _without_omitted_fields(pruned)
