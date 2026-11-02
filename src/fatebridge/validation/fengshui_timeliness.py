"""Compare all printed Wang period columns, retaining source disagreements."""

from typing import Any

from fatebridge.core.fengshui.timeliness import classify_timeliness


def audit_timeliness_reference(reference: dict[str, Any]) -> dict[str, Any]:
    rows = reference["basic_phase_rows"]
    mutual = reference["mutual_use_rows"]
    if (
        len(rows) != 9
        or {r["period"] for r in rows} != set(range(1, 10))
        or len(mutual) != 9
        or {r[0] for r in mutual} != set(range(1, 10))
    ):
        raise ValueError("All nine unique printed period columns are required")
    for row in rows:
        flattened = [n for label in "旺生衰死" for n in row[label]]
        if (
            len(flattened) != 9
            or set(flattened) != set(range(1, 10))
            or [len(row[label]) for label in "旺生衰死"] != [1, 2, 2, 4]
        ):
            raise ValueError("Every column must include all nine stars exactly once")
    if any(
        len(row) != 4
        or row[1] != row[0]
        or len(set(row[1:])) != 3
        or any(type(n) is not int or n not in range(1, 10) for n in row)
        for row in mutual
    ):
        raise ValueError("All three distinct printed mutual-use numbers are required")
    disagreements = []
    for row in rows:
        for label in "旺生衰死":
            for number in row[label]:
                actual = classify_timeliness(number, row["period"])
                if actual["traditional_label"] != label:
                    disagreements.append(
                        {
                            "period": row["period"],
                            "number": number,
                            "expected": label,
                            "actual": actual,
                        }
                    )
    for period, *numbers in mutual:
        for number in range(1, 10):
            actual = classify_timeliness(number, period)["mutual_use_reference"]
            if actual["period_numbers"] != numbers or actual[
                "numeric_membership"
            ] is not (number in numbers):
                disagreements.append(
                    {
                        "period": period,
                        "number": number,
                        "expected_mutual_use": numbers,
                        "actual": actual,
                    }
                )
    return {
        "checked": 162,
        "matched": 162 - len(disagreements),
        "basic_phase_cells": 81,
        "mutual_use_memberships": 81,
        "disagreements": disagreements,
        "scoped_acceptance_passed": not disagreements,
        "primary_source_disagreements": reference["primary_source_disagreements"],
        "chapter_consistency_established": not reference[
            "primary_source_disagreements"
        ],
        "scope": reference["acceptance_scope"],
        "secondary_source_discrepancies": reference["secondary_source_discrepancies"],
        "whole_book_conformity_established": False,
        "real_world_prediction": "not_tested",
    }
