"""Independent complete-table and printed-chart checks, retaining disagreements."""

from typing import Any

from fatebridge.core.fengshui.models import XuankongRequest
from fatebridge.core.fengshui.xuankong import _star_trace, natal_rules, xuankong_natal


def audit_replacement_reference(
    original: dict[str, Any], printed: dict[str, Any]
) -> dict[str, Any]:
    rules = natal_rules()
    mountains = {m["name"]: m for m in rules["mountains"]}
    entries = [
        (name, group["star"])
        for group in original["groups"]
        for name in group["mountains"]
    ]
    if (
        len(entries) != 24
        or {m for m, _ in entries} != set(mountains)
        or any(type(n) is not int or n not in (1, 2, 6, 7, 9) for _, n in entries)
    ):
        raise ValueError("All24 unique original replacement entries must be retained")
    clauses = original["same_yuan_examples"]
    if len(clauses) != 4 or {(c["physical_mountain"], c["seed"]) for c in clauses} != {
        ("丁", 3),
        ("甲", 1),
        ("子", 8),
        ("丙", 1),
    }:
        raise ValueError("All four distinct original same-yuan clauses are required")
    cases = printed["cases"]
    if len(cases) != 5 or {
        (c["period"], c["representative_facing_degrees"]) for c in cases
    } != {(7, 180), (7, 354), (7, 264), (7, 84), (7, 129)}:
        raise ValueError("All five independently printed full-chart cases are required")
    disagreements = []
    changed = 0
    for name, expected in entries:
        actual = rules["replacement_catalog"][name]
        changed += actual["changes_number"]
        if actual["replacement_star_number"] != expected:
            disagreements.append(
                {
                    "scope": "table",
                    "mountain": name,
                    "expected": expected,
                    "actual": actual,
                }
            )
    for clause in clauses:
        physical = mountains[clause["physical_mountain"]]
        # These are non-five seed-mapping clauses, not newly inferred property
        # dates. Compare all nine contexts to prove their period independence.
        for period in range(1, 10):
            actual = _star_trace(clause["seed"], physical, period, "replacement")
            values = {
                "mapped": actual["mapped_mountain"],
                "replacement": actual["center_star_number"],
                "polarity": actual["polarity"],
            }
            if any(values[k] != clause[k] for k in values):
                disagreements.append(
                    {"scope": "same_yuan_clause", "clause": clause, "actual": values}
                )
                break
    chart_disagreements = []
    for case in cases:
        if case["cell_roles"] != ["mountain", "facing", "period"]:
            raise ValueError(
                "Keep the independently collated left/right/period star order"
            )
        if set(case["palaces"]) != {"N", "NE", "E", "SE", "S", "SW", "W", "NW", "C"}:
            raise ValueError("Every printed chart must retain all nine palaces")
        request = XuankongRequest.model_validate(
            {
                "house": {
                    "facing_degrees": case["representative_facing_degrees"],
                    "north_reference": "magnetic",
                },
                "period": {
                    "basis": "expert_confirmed",
                    "period_number": case["period"],
                    "evidence": "Independent printed numeric example; not a real property",
                },
            }
        )
        chart = xuankong_natal(request)["chart"]
        if chart["chart_mode"] != case["chart_mode"]:
            chart_disagreements.append(
                {"case": case["label"], "scope": "mode", "actual": chart["chart_mode"]}
            )
        for direction, row in case["palaces"].items():
            if len(row) != 3 or any(type(n) is not int or not 1 <= n <= 9 for n in row):
                raise ValueError(
                    "Every printed palace must retain all three integer stars"
                )
            for role, expected in zip(case["cell_roles"], row):
                actual = chart[f"{role}_chart"][direction]
                if actual != expected:
                    chart_disagreements.append(
                        {
                            "case": case["label"],
                            "direction": direction,
                            "role": role,
                            "expected": expected,
                            "actual": actual,
                        }
                    )
    return {
        "complete_table_entries": 24,
        "changed_number_entries": changed,
        "same_number_entries": 24 - changed,
        "same_yuan_clauses": 4,
        "same_yuan_scope": "non_five_seed_mapping_invariant_across_all_nine_period_contexts_not_new_event_charts",
        "printed_charts": 5,
        "printed_numeric_components": 135,
        "table_and_clause_disagreements": disagreements,
        "printed_chart_disagreements": chart_disagreements,
        "scoped_acceptance_passed": not disagreements and not chart_disagreements,
        "whole_book_conformity_established": False,
        "real_world_prediction": "not_tested",
    }
