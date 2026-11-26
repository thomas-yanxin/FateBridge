"""Shared result field projection and invalid-path reporting."""

from collections.abc import Iterable
from typing import Literal

from pydantic import JsonValue

from fatebridge.application.tool_spec import ServiceResult
from fatebridge.utils.errors import ParameterError

SelectionTree = dict[str, "Literal[True] | SelectionTree"]


def project_fields(
    result: dict[str, JsonValue],
    fields: Iterable[str] | None,
    *,
    strict_fields: bool = False,
    validate_against: ServiceResult | None = None,
) -> ServiceResult:
    """Select dotted object paths and keep the run receipt whole.

    A whole parent takes precedence. For shaped child results, callers may
    validate a path against the original facts before detail and text omission.
    """
    if fields is None:
        return result
    fields = list(fields)
    if not fields:
        return result
    issues = projection_issues(
        result if validate_against is None else validate_against, fields
    )
    if issues and strict_fields:
        raise ParameterError("输出字段投影无效", [{**issue} for issue in issues])
    tree = build_selection_tree(fields)
    tree["run_metadata"] = True
    projected: dict[str, JsonValue] = {
        name: apply_selection(result[name], child)
        for name, child in tree.items()
        if name in result
    }
    if issues:
        projected["projection_warnings"] = [{**issue} for issue in issues]
    return projected


def merge_projected_fields(
    base: dict[str, JsonValue], selected: dict[str, JsonValue]
) -> dict[str, JsonValue]:
    """Add explicit facts to an existing view without mutating either projection."""
    merged = dict(base)
    for name, value in selected.items():
        current = merged.get(name)
        merged[name] = (
            merge_projected_fields(current, value)
            if isinstance(current, dict) and isinstance(value, dict)
            else value
        )
    return merged


def projection_issues(
    result: dict[str, JsonValue], fields: list[str]
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for path in dict.fromkeys(fields):
        parts = path.split(".")
        code = ""
        if any(not part or part.strip() != part for part in parts):
            code = "invalid_projection_path"
        else:
            value: JsonValue = result
            for part in parts:
                if not isinstance(value, dict):
                    code = "non_object_projection_path"
                    break
                if part not in value:
                    code = "unknown_projection_path"
                    break
                value = value[part]
        if code:
            issues.append({"path": path, "code": code})
    return issues


def build_selection_tree(fields: Iterable[str]) -> SelectionTree:
    root: SelectionTree = {}
    for field in fields:
        node = root
        parts = field.split(".")
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                node[part] = True
                break
            child = node.get(part)
            if child is True:
                break
            if child is None:
                child = {}
                node[part] = child
            node = child
    return root


def apply_selection(value: JsonValue, node: Literal[True] | SelectionTree) -> JsonValue:
    if node is True or not isinstance(value, dict):
        return value
    return {
        name: apply_selection(value[name], child)
        for name, child in node.items()
        if name in value
    }
