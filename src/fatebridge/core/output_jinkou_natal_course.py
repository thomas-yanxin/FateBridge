"""Keep a derived natal course separate and bind it to this analysis."""

from __future__ import annotations

from typing import Any

from .metaphysics.jinkou_natal_course import natal_course_metadata, natal_course_trace
from .output_liuren_selection import compare


def shared_compare(a: Any, b: Any) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a.keys() & b.keys():
            shared_compare(a[k], b[k])
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            raise ValueError("本命另课须保留同次分析队列")
        for x, y in zip(a, b):
            shared_compare(x, y)
    elif type(a) is not type(b) or a != b:
        raise ValueError("本命另课与本次占时、本命来源或课盘依据不一致")


def expected_metadata(value: dict[str, Any]) -> dict[str, Any] | None:
    if not {"birth_year_ganzhi", "natal_branch", "natal_branch_source"} <= value.keys():
        return None
    source = value["natal_branch_source"]
    if not isinstance(source, str) or source not in {
        "explicit_natal_branch",
        "explicit_birth_year_ganzhi",
        "missing",
    }:
        raise ValueError("本命另课来源无效")
    return natal_course_metadata(
        value["birth_year_ganzhi"],
        value["natal_branch"] if source == "explicit_natal_branch" else None,
    )


def validate_natal_course(parent: dict[str, Any]) -> None:
    value = parent.get("natal_course")
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError("本命另课须为资料对象")
    expected = expected_metadata(value)
    if expected is not None:
        compare({k: v for k, v in value.items() if k != "course"}, expected)
    child = value.get("course")
    if child is not None and not isinstance(child, dict):
        raise ValueError("本命另课课盘须为对象或未知")
    if (
        "status" in value
        and "course" in value
        and (child is not None) != (value["status"] == "calculated")
    ):
        raise ValueError("本命未知不能生成另课，明确已算不能丢失另课")
    annual = parent.get("year_fate")
    if isinstance(annual, dict):
        shared_compare(
            value,
            {
                k: annual[k]
                for k in ["birth_year_ganzhi", "natal_branch", "natal_branch_source"]
                if k in annual
            },
        )
    boards = [parent] + ([child] if isinstance(child, dict) else [])
    for board in boards:
        natal = ((board.get("relations") or {}).get("si_jue") or {}).get("natal")
        if isinstance(natal, dict):
            if "right_branch" in natal and "natal_branch" in value:
                shared_compare(value["natal_branch"], natal["right_branch"])
            if "input_source" in natal and "natal_branch_source" in value:
                shared_compare(
                    (
                        "not_provided"
                        if value["natal_branch_source"] == "missing"
                        else value["natal_branch_source"]
                    ),
                    natal["input_source"],
                )
    if isinstance(child, dict):
        if any(k in child for k in ["year_fate", "natal_course"]):
            raise ValueError("本命另课不得递归另起年命课")
        overview = child.get("overview")
        if isinstance(overview, dict):
            if "di_fen" in overview and "natal_branch" in value:
                shared_compare(overview["di_fen"], value["natal_branch"])
            if "di_fen_source" in overview:
                compare(overview["di_fen_source"], "natal_branch_derived_course")
            main = parent.get("overview")
            if isinstance(main, dict):
                shared_compare(
                    overview,
                    {
                        k: main[k]
                        for k in [
                            "month_general",
                            "is_diurnal",
                            "diurnal_basis",
                            "diurnal_evidence",
                        ]
                        if k in main
                    },
                )
        if "calendar_policy" in parent and "calendar_policy" in child:
            shared_compare(parent["calendar_policy"], child["calendar_policy"])
    traces = [
        t
        for t in parent.get("rule_trace") or []
        if t.get("rule_id") == "jinkou.natal_branch_course"
    ]
    if len(traces) > 1:
        raise ValueError("本命另课推导轨迹不能重复")
    if expected is not None:
        for trace in traces:
            compare(trace, natal_course_trace(expected))


def require_complete_natal_course(parent: dict[str, Any]) -> None:
    value = parent.get("natal_course")
    if not isinstance(value, dict):
        raise ValueError("完整金口诀须保留可空的本命另课资料")
    expected = expected_metadata(value)
    if expected is None or set(expected) | {"course"} != set(value):
        raise ValueError("完整本命另课缺少输入、来源或范围说明")
    validate_natal_course(parent)
    if value["course"] is not None:
        overview = value["course"].get("overview") or {}
        if not {"di_fen", "di_fen_source"} <= overview.keys():
            raise ValueError("完整本命另课须保留派生地分")
    traces = [
        t
        for t in parent.get("rule_trace") or []
        if t.get("rule_id") == "jinkou.natal_branch_course"
    ]
    if len(traces) != 1 or traces[0] != natal_course_trace(expected):
        raise ValueError("完整本命另课须有唯一完整依据轨迹")
