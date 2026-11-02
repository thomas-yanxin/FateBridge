"""A complete216-chart comparison with original named lists, never an efficacy score."""

from typing import Any

from fatebridge.core.fengshui.xuankong import _chart, natal_rules


def audit_classical_patterns(reference: dict[str, Any]) -> dict[str, Any]:
    def cases(key: str, count: int) -> set[tuple[int, str]]:
        rows = [
            (period, facing)
            for family in reference[key]["families"]
            for period in family["periods"]
            for facing in family["facing_mountains"]
        ]
        if len(rows) != count or len(set(rows)) != count:
            raise ValueError(
                f"All{count} unique independently transcribed {key} cases required"
            )
        return set(rows)

    expected_parent = cases("parental_triples", 16)
    expected_named = cases("named_refrain_examples", 28)
    if reference["parental_triples"]["groups"] != [[1, 4, 7], [2, 5, 8], [3, 6, 9]]:
        raise ValueError(
            "Retain all three literal parental groups and their distinct stars"
        )
    known_mountains = {m["name"] for m in natal_rules()["mountains"]}
    for expected in (expected_parent, expected_named):
        if any(
            type(p) is not int or not 1 <= p <= 9 or f not in known_mountains
            for p, f in expected
        ):
            raise ValueError("Original list contains an invalid period or mountain")
    actual_parent = set()
    actual_named = set()
    for period in range(1, 10):
        for index in range(24):
            chart = _chart(period, (index, "lower", "independent_source_list_audit"))
            patterns = chart["structure"]["classical_patterns"]
            key = (period, chart["facing"]["name"])
            if patterns["parental_triples"]["all_nine_match"]:
                actual_parent.add(key)
            if patterns["volume_two_named_refrain"]["numeric_match"]:
                actual_named.add(key)
    parent_diff = sorted(expected_parent ^ actual_parent)
    named_diff = sorted(expected_named ^ actual_named)
    return {
        "lower_chart_domain_checked": 216,
        "parental": {
            "expected_positive_cases": 16,
            "actual_positive_cases": len(actual_parent),
            "negative_cases_checked": 200,
            "symmetric_differences": parent_diff,
        },
        "named_refrain": {
            "expected_positive_cases": 28,
            "actual_positive_cases": len(actual_named),
            "negative_cases_checked": 188,
            "symmetric_differences": named_diff,
        },
        "scoped_acceptance_passed": not parent_diff and not named_diff,
        "scope": "volume1_parental_whole_chart_list_and_volume2_named_lower_charts_only_not_all_traditional_refrain_usage",
        "whole_book_conformity_established": False,
        "real_world_prediction": "not_tested",
    }
