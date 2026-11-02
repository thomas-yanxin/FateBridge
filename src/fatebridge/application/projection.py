"""Shared result field projection and invalid-path reporting."""

from typing import Dict, Iterable, List, Literal, Optional, Union

from fatebridge.application.tool_spec import ServiceResult
from fatebridge.utils.errors import ParameterError

# True keeps a subtree whole; a mapping selects its children.
SelectionTree = Dict[str, Union[Literal[True], "SelectionTree"]]


def project_fields(
    result: ServiceResult,
    fields: Optional[Iterable[str]],
    *,
    strict_fields: bool = False,
) -> ServiceResult:
    """Project a result to a subset of keys for token budgeting.

    Supports two forms, freely mixed:

    - **Top-level**: ``"snapshot_text"`` keeps that whole top-level value.
    - **Dotted sub-path**: ``"bazi_birth.day_master"`` keeps ``bazi_birth`` but
      prunes it to just ``day_master`` (recurses to any depth). This lets an
      agent pull a scalar buried in an otherwise huge block (e.g. the ~50KB
      ``bazi_birth`` payload) without dumping the whole thing.

    Rules: ``run_metadata`` is always preserved whole. Asking for a whole parent
    AND a sub-path of it keeps the whole parent (whole wins, any order). A
    ``None``/empty selection returns the result unchanged. Lenient projection
    retains historical data shaping, with visible ``projection_warnings`` for
    every invalid path. Strict projection rejects them before shaping any data.
    Paths traverse objects only; arrays and scalars must be selected whole.
    """
    if fields is None:
        return result
    fields = list(fields)
    if not fields:
        return result
    issues = _projection_issues(result, fields)
    if issues and strict_fields:
        raise ParameterError("输出字段投影无效", issues)
    tree = _build_selection_tree(fields)
    tree["run_metadata"] = True  # provenance always survives, whole
    projected = {
        key: _apply_selection(result[key], child)
        for key, child in tree.items()
        if key in result
    }
    if issues:
        projected["projection_warnings"] = issues
    return projected


def _projection_issues(
    result: ServiceResult, fields: List[str]
) -> List[Dict[str, str]]:
    issues = []
    for path in dict.fromkeys(fields):
        parts = path.split(".")
        code = ""
        if any(not part or part.strip() != part for part in parts):
            code = "invalid_projection_path"
        else:
            value: object = result
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


def _build_selection_tree(fields: Iterable[str]) -> SelectionTree:
    root: SelectionTree = {}
    for field in fields:
        node = root
        parts = field.split(".")
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                node[part] = True  # whole-keep wins over any partial selection
                break
            child = node.get(part)
            if child is True:
                break  # parent already requested whole; sub-path is subsumed
            if child is None:
                child = {}
                node[part] = child
            node = child
    return root


def _apply_selection(value: object, node: Literal[True] | SelectionTree) -> object:
    if node is True or not isinstance(value, dict):
        return value
    return {
        k: _apply_selection(value[k], child) for k, child in node.items() if k in value
    }
