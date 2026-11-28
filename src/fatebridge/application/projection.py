"""Shared strict result field projection, include validation, and default_omit pruning."""

from __future__ import annotations

import difflib
from collections.abc import Iterable, Mapping
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


def _apply_projection(result: dict[str, JsonValue], fields: list[str]) -> ServiceResult:
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
                    keys = sorted(value.keys())
                    constraints = {"available": keys[:30]}
                    suggestions = difflib.get_close_matches(part, keys, n=5, cutoff=0.6)
                    if suggestions:
                        constraints["suggestions"] = suggestions
                    break
                value = value[part]
        if code:
            issue: dict[str, object] = {"path": path, "code": code}
            if constraints is not None:
                issue["constraints"] = constraints
            issues.append(issue)
    return issues


def _validate_include_segments(
    node: JsonValue,
    parts: list[str],
    *,
    is_root: bool,
    views: Mapping[str, object] | None,
    full_pattern: str,
    default_omit_set: set[str],
    depth: int = 0,
) -> tuple[str, dict[str, object] | None, int]:
    part = parts[0]
    rest = parts[1:]

    if part != "*":
        if not isinstance(node, dict):
            return ("non_object_projection_path", None, depth)
        if part not in node:
            candidates = (
                sorted(set(node.keys()) | set(views.keys()))
                if is_root and views
                else sorted(node.keys())
            )
            limit = 60 if is_root else 30
            constraints: dict[str, object] = {"available": candidates[:limit]}
            suggestions = difflib.get_close_matches(part, candidates, n=5, cutoff=0.6)
            if suggestions:
                constraints["suggestions"] = suggestions
            return ("unknown_projection_path", constraints, depth)
        if not rest:
            return ("", None, depth)
        return _validate_include_segments(
            node[part],
            rest,
            is_root=False,
            views=None,
            full_pattern=full_pattern,
            default_omit_set=default_omit_set,
            depth=depth + 1,
        )

    if not isinstance(node, (dict, list)):
        return ("non_object_projection_path", None, depth)
    children = list(node.values()) if isinstance(node, dict) else node
    if not children:
        if full_pattern in default_omit_set:
            return ("", None, depth)
        return ("unknown_projection_path", {"available": []}, depth)
    if not rest:
        return ("", None, depth)

    failures: list[tuple[str, dict[str, object] | None, int]] = []
    for child in children:
        code, child_constraints, fail_depth = _validate_include_segments(
            child,
            rest,
            is_root=False,
            views=None,
            full_pattern=full_pattern,
            default_omit_set=default_omit_set,
            depth=depth + 1,
        )
        if not code:
            return ("", None, depth)
        failures.append((code, child_constraints, fail_depth))

    unknown_failures = [
        item for item in failures if item[0] == "unknown_projection_path"
    ]
    if unknown_failures:
        max_depth = max(item[2] for item in unknown_failures)
        if max_depth == depth + 1:
            merged_keys = sorted(
                {
                    key
                    for child in children
                    if isinstance(child, dict)
                    for key in child.keys()
                }
            )
            merged_constraints: dict[str, object] = {"available": merged_keys[:30]}
            suggestions = difflib.get_close_matches(
                rest[0], merged_keys, n=5, cutoff=0.6
            )
            if suggestions:
                merged_constraints["suggestions"] = suggestions
            return ("unknown_projection_path", merged_constraints, max_depth)
        deepest = next(item for item in unknown_failures if item[2] == max_depth)
        return deepest

    return failures[0]


def include_issues(
    result: dict[str, JsonValue],
    includes: list[str],
    *,
    views: Mapping[str, Mapping[str, object]] | None = None,
    default_omit: Iterable[str] = (),
) -> list[dict[str, object]]:
    """Validate include entries against '*' wildcard, evidence_views names, and dotted paths."""
    issues: list[dict[str, object]] = []
    default_omit_set = set(default_omit)
    for item in dict.fromkeys(includes):
        if item == "*":
            continue
        if views is not None and item in views:
            continue
        parts = item.split(".")
        if any(not part or part.strip() != part for part in parts):
            issues.append({"path": item, "code": "invalid_projection_path"})
            continue
        code, constraints, _ = _validate_include_segments(
            result,
            parts,
            is_root=True,
            views=views,
            full_pattern=item,
            default_omit_set=default_omit_set,
        )
        if code:
            issue: dict[str, object] = {"path": item, "code": code}
            if constraints is not None:
                issue["constraints"] = constraints
            issues.append(issue)
    return issues


def _project_descendants(
    value: JsonValue,
    include_rules: list[tuple[str, ...]],
) -> tuple[JsonValue, bool, bool]:
    """Keep only descendants matching include_rules inside an omitted container."""
    if () in include_rules:
        return value, True, False
    if isinstance(value, dict):
        out: dict[str, JsonValue] = {}
        any_matched = False
        any_omitted = False
        for key, child in value.items():
            child_rules = [
                rule[1:] for rule in include_rules if rule and rule[0] in (key, "*")
            ]
            if not child_rules:
                any_omitted = True
                continue
            projected, matched, omitted = _project_descendants(child, child_rules)
            if matched:
                out[key] = projected
                any_matched = True
                if omitted:
                    any_omitted = True
            else:
                any_omitted = True
        return out, any_matched, any_omitted
    if isinstance(value, list):
        star_rules = [rule[1:] for rule in include_rules if rule and rule[0] == "*"]
        if not star_rules:
            return value, False, bool(value)
        out_list: list[JsonValue] = []
        any_matched = False
        any_omitted = False
        for elem in value:
            projected, matched, omitted = _project_descendants(elem, star_rules)
            if matched:
                out_list.append(projected)
                any_matched = True
                if omitted:
                    any_omitted = True
            else:
                any_omitted = True
        return out_list, any_matched, any_omitted
    return value, False, True


def _omit_node(
    node: JsonValue,
    active_omit: list[tuple[str, tuple[str, ...]]],
    active_include: list[tuple[str, ...]],
) -> tuple[JsonValue, set[str]]:
    if () in active_include or not active_omit:
        return node, set()

    if isinstance(node, dict):
        changed = False
        out: dict[str, JsonValue] = {}
        omitted: set[str] = set()
        for key, child in node.items():
            next_omit = [
                (pat, segs[1:])
                for pat, segs in active_omit
                if segs and segs[0] in (key, "*")
            ]
            next_inc = [
                segs[1:] for segs in active_include if segs and segs[0] in (key, "*")
            ]
            terminating = [pat for pat, segs in next_omit if not segs]
            if terminating:
                if () in next_inc:
                    out[key] = child
                elif next_inc:
                    projected, matched, sub_omitted = _project_descendants(
                        child, next_inc
                    )
                    if matched:
                        out[key] = projected if sub_omitted else child
                        if sub_omitted:
                            changed = True
                            omitted.update(terminating)
                    else:
                        changed = True
                        omitted.update(terminating)
                else:
                    changed = True
                    omitted.update(terminating)
            else:
                deeper = [(pat, segs) for pat, segs in next_omit if segs]
                if deeper:
                    new_child, child_omitted = _omit_node(child, deeper, next_inc)
                    if new_child is not child:
                        changed = True
                    out[key] = new_child
                    omitted.update(child_omitted)
                else:
                    out[key] = child
        return (out if changed else node), omitted

    if isinstance(node, list):
        next_omit = [
            (pat, segs[1:]) for pat, segs in active_omit if segs and segs[0] == "*"
        ]
        if not next_omit:
            return node, set()
        next_inc = [segs[1:] for segs in active_include if segs and segs[0] == "*"]
        terminating = [pat for pat, segs in next_omit if not segs]
        if terminating:
            if () in next_inc:
                return node, set()
            if next_inc:
                projected, matched, sub_omitted = _project_descendants(
                    node, [("*", *rule) for rule in next_inc]
                )
                if matched:
                    return (
                        (projected if sub_omitted else node),
                        set(terminating) if sub_omitted else set(),
                    )
            if node:
                return [], set(terminating)
            return node, set()
        deeper = [(pat, segs) for pat, segs in next_omit if segs]
        changed = False
        out_list: list[JsonValue] = []
        omitted = set()
        for elem in node:
            new_elem, elem_omitted = _omit_node(elem, deeper, next_inc)
            if new_elem is not elem:
                changed = True
            out_list.append(new_elem)
            omitted.update(elem_omitted)
        return (out_list if changed else node), omitted

    return node, set()


def prune_omitted_paths(
    result: dict[str, JsonValue],
    default_omit: Iterable[str],
    include_paths: Iterable[str] = (),
) -> tuple[dict[str, JsonValue], list[str]]:
    """Copy-on-write removal of default_omit paths not un-omitted by include_paths."""
    omit_patterns = tuple(dict.fromkeys(pattern for pattern in default_omit if pattern))
    if not omit_patterns:
        return result, []
    omit_rules = [(pattern, tuple(pattern.split("."))) for pattern in omit_patterns]
    inc_rules = [
        tuple(path.split(".")) for path in dict.fromkeys(include_paths) if path
    ]
    pruned, omitted_set = _omit_node(result, omit_rules, inc_rules)
    assert isinstance(pruned, dict)
    ordered_omitted = [pattern for pattern in omit_patterns if pattern in omitted_set]
    return pruned, ordered_omitted


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
