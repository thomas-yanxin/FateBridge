"""Literal Witte1925 table and exact numerical interpolation of its axes.

Unclear printed degree markers remain unknown. This module does not choose
historical clocks, rounding or a complete date-to-progression key, and does
not replace the selected true-Sun solar arc with a table approximation.
"""

from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

RECORD = (
    Path(__file__).resolve().parents[2]
    / "data/knowledge/witte1925-solar-arc-table.json"
)
RULESET = "witte1925_table_numeric_interpolation_v1"


def load_table() -> dict[str, Any]:
    raw = RECORD.read_bytes()
    return cast(dict[str, Any], json.loads(raw))


def normalized_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Carry legible explicit degrees; an unclear marker invalidates that carry."""
    ages = record["age_columns_years"]
    unclear = {(r["row"], r["age_years"]) for r in record["unresolved_degree_marker"]}
    degrees: list[int | None] = [None] * len(ages)
    result = []
    for row in record["rows"]:
        values = []
        for index, (age, raw) in enumerate(
            zip(ages, row["raw_age_cells"], strict=True)
        ):
            parts = raw.split()
            if len(parts) == 2:
                degrees[index] = int(parts[0])
            if (row["row"], age) in unclear:
                degrees[index] = None
            minute = int(parts[-1])
            if len(parts) not in (1, 2) or not 0 <= minute < 60:
                raise RuntimeError("Invalid source table cell")
            degree = degrees[index]
            values.append(None if degree is None else degree * 60 + minute)
        result.append(
            {
                **row,
                "normalized_arcminutes": values,
                "unresolved_age_columns": [
                    age for age, value in zip(ages, values) if value is None
                ],
            }
        )
    return result


def _coordinate(value: int | float | Fraction) -> Fraction:
    if type(value) not in (int, float, Fraction) or (
        isinstance(value, float) and not math.isfinite(value)
    ):
        raise ValueError("Table coordinates require finite explicit numbers")
    return Fraction(value)


def interpolate(
    record: dict[str, Any],
    day_offset: int | float | Fraction,
    age_years: int | float | Fraction,
) -> dict[str, Any]:
    """Interpolate numeric axes only; preserve positive-weight unknown corners.

    day_offset0 is printed January1; offset370 is the following January6.
    These are common-year grid coordinates, not a chosen calendar/clock epoch.
    The age coordinate is an explicit table axis, not a calculated user age.
    """
    day, age = _coordinate(day_offset), _coordinate(age_years)
    rows = normalized_rows(record)
    ages = record["age_columns_years"]
    if (
        not 0 <= day <= rows[-1]["common_year_day_offset"]
        or not ages[0] <= age <= ages[-1]
    ):
        raise ValueError("Source table axes require day_offset0..370 and age10..90")
    row0 = min(int(day // 10), len(rows) - 2)
    col0 = min(int((age - ages[0]) // 10), len(ages) - 2)
    date_weight = (day - rows[row0]["common_year_day_offset"]) / 10
    age_weight = (age - ages[col0]) / 10
    corners = []
    total = Fraction(0)
    unresolved = False
    for r, rw in ((row0, 1 - date_weight), (row0 + 1, date_weight)):
        for c, cw in ((col0, 1 - age_weight), (col0 + 1, age_weight)):
            weight = rw * cw
            if weight == 0:
                continue
            value = rows[r]["normalized_arcminutes"][c]
            corners.append(
                {
                    "row": r,
                    "age_years": ages[c],
                    "raw_cell": rows[r]["raw_age_cells"][c],
                    "arcminutes": value,
                    "weight_fraction": [weight.numerator, weight.denominator],
                }
            )
            if value is None:
                unresolved = True
            else:
                total += value * weight
    return {
        "status": "underdetermined" if unresolved else "computed",
        "ruleset_id": RULESET,
        "day_offset_fraction": [day.numerator, day.denominator],
        "age_years_fraction": [age.numerator, age.denominator],
        "corners": corners,
        "arcminutes": None if unresolved else float(total),
        "arcminutes_fraction": (
            None if unresolved else [total.numerator, total.denominator]
        ),
        "full_original_method_accepted": False,
        "scope": "Exact numerical table interpolation; no historical date/clock, source rounding or event prediction inferred",
    }


def _fraction(probe: dict[str, Any]) -> Fraction:
    if probe["status"] != "computed":
        raise RuntimeError("Printed worked example has unresolved source corners")
    return Fraction(*probe["arcminutes_fraction"])


def source_table_analysis() -> dict[str, Any]:
    """Retain every raw cell and replay the author's staged worked example."""
    record = load_table()
    rows = normalized_rows(record)
    example = record["printed_worked_example"]
    first = example["fifty_year_date_interpolation"]
    x = Fraction(first["first_row"] * 10) + Fraction(*first["fraction_parts"]) * 10
    probe50, probe60, probe54 = [interpolate(record, x, y) for y in (50, 60, 54)]
    v50, v60, v54 = map(_fraction, (probe50, probe60, probe54))
    row0 = int(x // 10)
    w = (x - row0 * 10) / 10
    until_zero = (
        rows[row0]["raw_until_january_zero_arcminutes"] * (1 - w)
        + rows[row0 + 1]["raw_until_january_zero_arcminutes"] * w
    )
    # This diagnostic deliberately removes intermediate rounding. The source
    # does not fully prescribe that policy, so it is not the original method.
    partial = (v60 - v50) / 10 * Fraction(example["partial_year_months"], 12)
    hypothetical_total = v54 + until_zero + partial
    printed_base = (
        example["full_year_arc_degrees_minutes"][0] * 60
        + example["full_year_arc_degrees_minutes"][1]
    )
    printed_total = (
        example["printed_total_degrees_minutes"][0] * 60
        + example["printed_total_degrees_minutes"][1]
    )
    literal_sum = (
        example["until_january_zero_arcminutes"]
        + printed_base
        + example["partial_year_printed_arcminutes"]
    )
    unresolved = sum(v is None for row in rows for v in row["normalized_arcminutes"])
    source = record["source"]
    return {
        "status": "partially_resolved_source",
        "ruleset_id": RULESET,
        "author": "FateBridge",
        "version": "1",
        "computed_for_current_chart": False,
        "source": {
            "id": source["id"],
            "author": source["author"],
            "title": source["title"] + ", " + source["publication"],
            "sections": [
                "p.87: entire printed table",
                "p.88: interpolation and worked example",
            ],
            "scope": record["scope"],
        },
        "coverage": {
            "date_rows": len(rows),
            "raw_age_cells": len(rows) * len(record["age_columns_years"]),
            "resolved_age_cells": len(rows) * len(record["age_columns_years"])
            - unresolved,
            "unresolved_age_cells": unresolved,
            "last_column_cells": len(rows),
            "all_printed_raw_cells_retained": True,
            "all_degrees_resolved": unresolved == 0,
        },
        "age_columns_years": record["age_columns_years"],
        "rows": rows,
        "worked_example": {
            "birth_date_label": example["birth_date_label"],
            "target_date_label": example["target_date_label"],
            "clock_or_timezone_given": example["clock_or_timezone_given"],
            "printed_components_arcminutes": [
                example["until_january_zero_arcminutes"],
                printed_base,
                example["partial_year_printed_arcminutes"],
            ],
            "literal_components_sum_arcminutes": literal_sum,
            "printed_total_arcminutes": printed_total,
            "literal_arithmetic_matches_print": literal_sum == printed_total,
            "exact_bilinear_base": probe54,
            "exact_fifty_year_arcminutes": float(v50),
            "exact_sixty_year_arcminutes": float(v60),
            "exact_last_column_arcminutes": float(until_zero),
            "hypothetical_unrounded_partial_year_arcminutes": float(partial),
            "hypothetical_unrounded_total_arcminutes": float(hypothetical_total),
            "hypothetical_total_fraction": [
                hypothetical_total.numerator,
                hypothetical_total.denominator,
            ],
            "printed_minus_hypothetical_total_arcminutes": float(
                printed_total - hypothetical_total
            ),
            "hypothetical_unrounded_policy_adopted_as_original": False,
            "source_rounding_policy_fully_specified": False,
        },
        "full_original_method_accepted": False,
    }
