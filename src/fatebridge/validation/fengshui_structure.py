"""Compare separately transcribed printed numbers and scoped headings, never prose efficacy."""

from typing import Any

from fatebridge.core.fengshui.xuankong import _chart, natal_rules


def audit_printed_structures(reference: dict[str, Any]) -> dict[str, Any]:
    directions = reference["row_order"]
    roles = reference["column_order"]
    mountains = [m["name"] for m in natal_rules()["mountains"]]
    examples = reference["charts"]
    if (
        len(examples) != 6
        or len({r["id"] for r in examples}) != 6
        or len({(r["period"], r["facing"]) for r in examples}) != 6
        or set(directions) != {"C", "N", "NE", "E", "SE", "S", "SW", "W", "NW"}
        or len(directions) != 9
        or roles != ["mountain", "facing", "period"]
    ):
        raise ValueError("Retain six complete unique printed examples and their frames")
    differences = []
    headings = 0
    for example in examples:
        if type(example["period"]) is not int or example["period"] not in range(1, 10):
            raise ValueError("Printed periods must be integers1-9")
        rows = example["rows"]
        if len(rows) != 9 or any(len(row) != 3 for row in rows):
            raise ValueError(
                "Every printed chart requires27 independently read numbers"
            )
        for column in range(3):
            values = [row[column] for row in rows]
            if any(type(n) is not int for n in values) or sorted(values) != list(
                range(1, 10)
            ):
                raise ValueError("Printed plates must each retain integer stars1-9")
        chart = _chart(
            example["period"],
            (mountains.index(example["facing"]), "lower", "printed_audit"),
        )
        if chart["sitting"]["name"] != example["sitting"]:
            raise ValueError("Printed sitting and facing must be opposite mountains")
        for direction, row in zip(directions, rows):
            for role, expected in zip(roles, row):
                actual = chart[role + "_chart"][direction]
                if actual != expected:
                    differences.append(
                        dict(
                            example=example["id"],
                            palace=direction,
                            role=role,
                            expected=expected,
                            actual=actual,
                        )
                    )
        structure = chart["structure"]
        checks = []
        if "expected_sum_ten_pair" in example:
            pair = example["expected_sum_ten_pair"]
            checks.append(
                (
                    "same_palace_sum_ten",
                    True,
                    next(
                        row
                        for row in structure["combination_of_ten"]
                        if [row["left_role"], row["right_role"]] == pair
                    )["all_nine_sum_to_ten"],
                )
            )
        if "expected_ground_role" in example:
            checks.append(
                (
                    example["expected_ground_pattern"],
                    True,
                    structure["classical_patterns"]["ground_comparison"]["roles"][
                        example["expected_ground_role"]
                    ][example["expected_ground_pattern"]],
                )
            )
        if "expected_all_nine_parental_groups" in example:
            checks.append(
                (
                    "all_nine_parental_groups",
                    example["expected_all_nine_parental_groups"],
                    structure["classical_patterns"]["parental_triples"][
                        "all_nine_match"
                    ],
                )
            )
        if "shen_volume_two_named_list_correspondence" in example:
            checks.append(
                (
                    "separate_Shen_list_correspondence",
                    example["shen_volume_two_named_list_correspondence"],
                    structure["classical_patterns"]["volume_two_named_refrain"][
                        "numeric_match"
                    ],
                )
            )
        for name, expected, actual in checks:
            headings += 1
            if type(expected) is not bool or type(actual) is not bool:
                raise ValueError("Scoped headings require explicit boolean evidence")
            if actual is not expected:
                differences.append(
                    dict(
                        example=example["id"],
                        heading=name,
                        expected=expected,
                        actual=actual,
                    )
                )
    if headings != 7:
        raise ValueError(
            "Retain all seven scoped positive and countervailing heading checks"
        )
    return {
        "printed_charts": len(examples),
        "numeric_cells_checked": len(examples) * 27,
        "scoped_heading_checks": headings,
        "differences": differences,
        "scoped_acceptance_passed": not differences,
        "source": reference["source"],
        "scope": "printed_numeric_examples_and_separate_finite_list_correspondence_only",
        "independent_human_expert_review": False,
        "whole_book_conformity_established": False,
        "real_world_prediction_established": False,
    }
