"""Independent original-clause audit for all periods and both fifth-period halves."""

from typing import Any

from fatebridge.core.fengshui.lingzheng import analyze_fixed_lingzheng
from fatebridge.core.fengshui.lingzheng_inputs import FixedLingzhengRequest


def audit_lingzheng_reference(reference: dict[str, Any]) -> dict[str, Any]:
    rows = reference["cases"]
    keys = {(r["period"], r.get("half")) for r in rows}
    expected = {(n, None) for n in (1, 2, 3, 4, 6, 7, 8, 9)} | {
        (5, "first_decade"),
        (5, "second_decade"),
    }
    if len(rows) != 10 or keys != expected:
        raise ValueError("须完整保留八个非五运案例及五运两个分段")
    disagreements = []
    for row in rows:
        args = (
            {"five_period_half": row["half"], "half_evidence": "原书前后十年逐条核对"}
            if "half" in row
            else {}
        )
        actual = analyze_fixed_lingzheng(
            FixedLingzhengRequest.model_validate(args), row["period"], {}
        )["candidates"][0]
        if any(
            actual[k] != row[k]
            for k in (
                "zheng_number",
                "zheng_direction",
                "ling_number",
                "ling_direction",
            )
        ):
            disagreements.append(
                {
                    "source_case": row,
                    "actual": {
                        k: actual[k]
                        for k in (
                            "zheng_number",
                            "zheng_direction",
                            "ling_number",
                            "ling_direction",
                        )
                    },
                }
            )
    return {
        "checked_numeric_cases": 10,
        "matched_numeric_cases": 10 - len(disagreements),
        "disagreements": disagreements,
        "scoped_acceptance_passed": not disagreements,
        "scope": reference["scope"],
        "transcription_actor": reference["transcription_actor"],
        "whole_book_conformity_established": False,
        "real_world_prediction": "not_tested",
    }
