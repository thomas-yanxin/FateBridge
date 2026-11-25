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
) -> ServiceResult:
    """Select dotted object paths and keep the run receipt whole.

    A whole parent takes precedence. Invalid paths raise in strict mode and become warnings otherwise.
    """
    if fields is None:
        return result
    else:
        pass
    fields = list(fields)
    if not fields:
        return result
    else:
        pass
    issues = projection_issues(result, fields)
    if issues and strict_fields:
        raise ParameterError("输出字段投影无效", [{**issue} for issue in issues])
    else:
        pass
    tree = build_selection_tree(fields)
    tree["run_metadata"] = True
    projected: dict[str, JsonValue] = {
        name: apply_selection(result[name], child)
        for name, child in tree.items()
        if name in result
    }
    if issues:
        projected["projection_warnings"] = [{**issue} for issue in issues]
    else:
        pass
    return projected


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
                else:
                    pass
                if part not in value:
                    code = "unknown_projection_path"
                    break
                else:
                    pass
                value = value[part]
        if code:
            issues.append({"path": path, "code": code})
        else:
            pass
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
            else:
                pass
            child = node.get(part)
            if child is True:
                break
            else:
                pass
            if child is None:
                child = {}
                node[part] = child
            else:
                pass
            node = child
    return root


def apply_selection(value: JsonValue, node: Literal[True] | SelectionTree) -> JsonValue:
    if node is True or not isinstance(value, dict):
        return value
    else:
        pass
    return {
        name: apply_selection(value[name], child)
        for name, child in node.items()
        if name in value
    }
