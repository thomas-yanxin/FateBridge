"""Conditional arithmetic on literal manuscript cells, without repairing them.

A small side cell need not be an intercalary month. Compatibility here tests
the explicitly requested consecutive-month hypothesis; it never authenticates
that hypothesis, the transcription, a historical calendar or its day boundary.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Mapping, Sequence

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
DAY_CYCLE = tuple(STEMS[i % 10] + BRANCHES[i % 12] for i in range(60))
WEEKDAYS = tuple("日月火水木金土")
MONTH_LENGTHS = {"大": 30, "小": 29}


def _cell(value: Any, *, required: bool) -> None:
    if value is None and not required:
        return
    if not isinstance(value, dict):
        raise ValueError("月格须为原读字典；允许未读邻格为null")
    for field in ("size", "sexagenary", "weekday"):
        if field not in value or (
            value[field] is not None and not isinstance(value[field], str)
        ):
            raise ValueError(f"月格{field}须保留原读字符串或null，不接受数值替位")


def audit_month_start_insertions(
    records: Sequence[Mapping[str, Any]],
    *,
    evaluate_conditional_adjacency: bool = False,
) -> dict[str, Any]:
    """Retain every record and test two conditional edges for each candidate.

    Candidate readings, month numbers, annotations and geometry pass through
    unchanged. Unknown/invalid tokens stay unassessed. Alternative readings
    are never selected by their arithmetic fit.
    """
    if type(evaluate_conditional_adjacency) is not bool:
        raise ValueError("条件检查开关须为明确布尔值")
    if not isinstance(records, (list, tuple)) or not records:
        raise ValueError("须提供非空原读记录列表")
    seen: set[str] = set()
    edges: list[dict[str, Any]] = []
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("原读记录须为字典")
        identifier = row.get("id")
        if (
            not isinstance(identifier, str)
            or not identifier.strip()
            or identifier in seen
        ):
            raise ValueError("原读记录须有唯一非空id")
        seen.add(identifier)
        if any(k not in row for k in ("before", "marked_cell", "after")):
            raise ValueError("前／插／后月格须明示，未读不能省略为已知")
        for field in ("before", "marked_cell", "after", "next_year_column_first_cell"):
            _cell(row.get(field), required=field == "marked_cell")
        after = row["after"]
        cross_year = (
            after is None and row.get("next_year_column_first_cell") is not None
        )
        if cross_year:
            after = row["next_year_column_first_cell"]
        for label, first, last in (
            ("before_to_marked", row["before"], row["marked_cell"]),
            ("marked_to_after", row["marked_cell"], after),
        ):
            edge: dict[str, Any] = {
                "id": identifier,
                "edge": label,
                "first_literal": deepcopy(first),
                "last_literal": deepcopy(last),
                "cross_year_column": cross_year and label == "marked_to_after",
                "hypothesis_confirmed": False,
                "checks": {},
            }
            if not evaluate_conditional_adjacency:
                edge["status"] = "not_assessed_adjacency_not_evaluated"
            elif first is None or last is None:
                edge["status"] = "not_assessed_missing_literal"
            else:
                length = MONTH_LENGTHS.get(first["size"])
                for name, cycle in (("sexagenary", DAY_CYCLE), ("weekday", WEEKDAYS)):
                    a, b = first[name], last[name]
                    check: dict[str, Any]
                    if length is None or a not in cycle or b not in cycle:
                        check = {"status": "not_assessed_unread_or_invalid_literal"}
                    else:
                        expected = cycle[(cycle.index(a) + length) % len(cycle)]
                        check = {
                            "status": (
                                "compatible_under_hypothesis"
                                if expected == b
                                else "incompatible_under_hypothesis"
                            ),
                            "length_assumption": length,
                            "first_literal": a,
                            "next_literal": b,
                            "expected_from_literal_length": expected,
                            "observed_modular_delta": (cycle.index(b) - cycle.index(a))
                            % len(cycle),
                        }
                    edge["checks"][name] = check
                statuses = [v["status"] for v in edge["checks"].values()]
                edge["status"] = (
                    "incompatible_under_hypothesis"
                    if "incompatible_under_hypothesis" in statuses
                    else (
                        "not_fully_assessed"
                        if any(s.startswith("not_assessed") for s in statuses)
                        else "compatible_under_hypothesis"
                    )
                )
            edges.append(edge)
    return {
        "format": "sukuyo_literal_month_adjacency_v1",
        "source_records": deepcopy(list(records)),
        "candidate_count": len(records),
        "edge_count": len(edges),
        "evaluate_conditional_adjacency": evaluate_conditional_adjacency,
        "edges": edges,
        "totals": dict(sorted(Counter(e["status"] for e in edges).items())),
        "historical_calendar_truth": "not_assessed",
        "source_adoption": "not_assessed",
        "scope": (
            "仅在所列月格依次为连续月首、大小指该月长度的假设下检查模60／模7算术。"
            "不校定插格为闰月，不补月号或疑字，不转换纪年／公历，不认证古代日界、"
            "半日、补配优先、原典定本或现实效力。"
        ),
    }


def audit_exit_code(report: Mapping[str, Any]) -> int:
    """0 compatible conditional edges, 1 conflict, 3 unassessed; never authority."""
    totals = report["totals"]
    if totals.get("incompatible_under_hypothesis", 0):
        return 1
    if any(k.startswith("not_") and n for k, n in totals.items()):
        return 3
    return 0
