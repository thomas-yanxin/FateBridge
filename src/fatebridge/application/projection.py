"""Shared strict result field projection and actionable invalid-path reporting."""

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
    validate_against: ServiceResult | None = None,
) -> ServiceResult:
    """Select dotted object paths strictly and keep the run receipt whole."""
    if fields is None:
        return result
    field_list = list(fields)
    if not field_list:
        return result
    issues = projection_issues(
        result if validate_against is None else validate_against, field_list
    )
    if issues:
        raise ParameterError("输出字段投影无效", issues)
    return _apply_projection(result, field_list)


def project_present_fields(
    result: dict[str, JsonValue],
    fields: Iterable[str] | None,
) -> ServiceResult:
    """Project existing paths for internal compact views without failing on absent variant keys."""
    if fields is None:
        return result
    field_list = [
        path for path in fields if not projection_issues(result, [path])
    ]
    if not field_list:
        return result
    return _apply_projection(result, field_list)


def _apply_projection(
    result: dict[str, JsonValue], fields: list[str]
) -> ServiceResult:
    tree = build_selection_tree(fields)
    tree["run_metadata"] = True
    return {
        name: apply_selection(result[name], child)
        for name, child in tree.items()
        if name in result
    }


def projection_issues(
    result: dict[str, JsonValue], fields: list[str]
) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for path in dict.fromkeys(fields):
        parts = path.split(".")
        code = ""
        constraints: dict[str, object] | None = None
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
                    constraints = {"available": sorted(value.keys())[:30]}
                    break
                value = value[part]
        if code:
            issue: dict[str, object] = {"path": path, "code": code}
            if constraints is not None:
                issue["constraints"] = constraints
            issues.append(issue)
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
