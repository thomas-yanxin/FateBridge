"""Bind the complete pattern ledger and trace to their course's raw symbols."""

from __future__ import annotations

from typing import Any

from .metaphysics.jinkou_patterns import pattern_metadata, patterns_from_symbols

RULE_ID = "jinkou.structural_patterns"


def expected_patterns(board: dict[str, Any]) -> dict[str, Any] | None:
    rows = board.get("rows")
    policy = board.get("calendar_policy")
    day = policy.get("effective_day_ganzhi") if isinstance(policy, dict) else None
    if not isinstance(day, str) or not day:
        return None
    if not isinstance(rows, list) or len(rows) != 4:
        return None
    if any(not isinstance(row, dict) or row.get("content") is None for row in rows):
        return None
    return patterns_from_symbols(rows, day_ganzhi=day)


def compare_present(actual: Any, expected: Any) -> None:
    """Sparse views may omit fields; present statements must still be true."""
    if isinstance(actual, dict) and isinstance(expected, dict):
        for key in actual.keys() & expected.keys():
            compare_present(actual[key], expected[key])
    elif isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError("课钤判定队列与本课四位不一致")
        # Catalog claims are bound by pattern ID, not incidental list order.
        if actual and all(
            isinstance(row, dict) and isinstance(row.get("id"), str)
            for row in actual + expected
        ):
            observed = {row["id"]: row for row in actual}
            canonical = {row["id"]: row for row in expected}
            if len(observed) != len(actual) or observed.keys() != canonical.keys():
                raise ValueError("课钤判定ID与本课实际结构不一致")
            for pid, row in observed.items():
                compare_present(row, canonical[pid])
            return
        for a, e in zip(actual, expected, strict=True):
            compare_present(a, e)
    elif type(actual) is not type(expected) or actual != expected:
        raise ValueError("课钤判定、条件或原典来源与本课四位及占日不一致")


def validate_pattern_anchors(board: dict[str, Any]) -> None:
    traces = [t for t in board.get("rule_trace") or [] if t.get("rule_id") == RULE_ID]
    if len(traces) > 1:
        raise ValueError("同课六十四课钤规则轨迹不可重复")
    metadata = pattern_metadata()
    from .output_ren_patterns import JinkouPatterns

    for trace in traces:
        if trace.get("result") is not None:
            JinkouPatterns.model_validate(trace["result"])
        for key in ("source_url", "source_section"):
            if key in trace:
                compare_present(trace[key], metadata[key])
    expected = expected_patterns(board)
    if expected is None:
        return
    if "patterns" in board:
        compare_present(board["patterns"], expected)
    for trace in traces:
        if "result" in trace:
            compare_present(trace["result"], expected)
        for key in ("source_url", "source_section"):
            if key in trace:
                compare_present(trace[key], expected[key])


def require_complete(actual: Any, expected: Any) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or expected.keys() - actual.keys():
            raise ValueError("完整金口诀须保留六十四课钤全部可空事实与依据")
        for key, value in expected.items():
            require_complete(actual[key], value)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError("完整金口诀须保留六十四课钤完整队列")
        if actual and all(
            isinstance(row, dict) and isinstance(row.get("id"), str)
            for row in actual + expected
        ):
            observed = {row["id"]: row for row in actual}
            canonical = {row["id"]: row for row in expected}
            if len(observed) != len(actual) or observed.keys() != canonical.keys():
                raise ValueError("完整课钤ID队列与本课四位不一致")
            for pid, row in observed.items():
                require_complete(row, canonical[pid])
            return
        for a, e in zip(actual, expected, strict=True):
            require_complete(a, e)
    else:
        compare_present(actual, expected)


def require_complete_pattern_anchors(board: dict[str, Any]) -> None:
    expected = expected_patterns(board)
    if expected is None:
        raise ValueError("完整金口诀须保留课钤的四位原始符号与占日")
    require_complete(board.get("patterns"), expected)
    traces = [t for t in board.get("rule_trace") or [] if t.get("rule_id") == RULE_ID]
    if len(traces) != 1:
        raise ValueError("完整金口诀须保留唯一的六十四课钤规则轨迹")
    require_complete(traces[0].get("result"), expected)
    for key in ("source_url", "source_section"):
        compare_present(traces[0].get(key), expected[key])
