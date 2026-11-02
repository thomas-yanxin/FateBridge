"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

from typing import Any

TEXT_FIELDS = frozenset({"basis", "scope", "note", "source_url", "source_section"})


def compare_present(actual: Any, expected: Any, path: str = "") -> None:
    """Preserve projections and free prose, reject incompatible computed facts."""
    if isinstance(actual, dict) and isinstance(expected, dict):
        if path.endswith("powers") and set(actual) - set(expected):
            raise ValueError("课内旺衰不能添加不存在的位置")
        for key in actual.keys() & expected.keys():
            if key not in TEXT_FIELDS:
                compare_present(actual[key], expected[key], path + "." + key)
    elif isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError("金口诀旺衰或取用条件的完整队列不一致")
        for a, b in zip(actual, expected):
            compare_present(a, b, path)
    elif type(actual) is not type(expected) or actual != expected:
        raise ValueError("金口诀旺衰、得气或用位条件与本次四位不一致")
