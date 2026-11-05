"""Independent rational replay of the complete raw Witte1925 table.

Expected calculations import no FateBridge computation. Unknown degrees and
the source's unspecified rounding/calendar conventions remain unaccepted;
the default source-completeness audit consequently returns exit1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "src/fatebridge/data/knowledge/witte1925-solar-arc-table.json"
RECORD_SHA256 = "301a22dbc2390ca9b644e4ed87d65cbf67437bf608165f49825e192299608750"


def reference_cells(record: dict) -> dict[tuple[int, int], int | None]:
    """Decode each column independently, retaining its unresolved interval."""
    missing = {(x["row"], x["age_years"]) for x in record["unresolved_degree_marker"]}
    result = {}
    for column, age in enumerate(record["age_columns_years"]):
        degree = None
        for row in record["rows"]:
            tokens = row["raw_age_cells"][column].split()
            if len(tokens) == 2:
                degree = int(tokens[0])
            if (row["row"], age) in missing:
                degree = None
            minute = int(tokens[-1])
            if not 0 <= minute < 60:
                raise ValueError("Printed table minute out of range")
            result[(row["row"], age)] = None if degree is None else degree * 60 + minute
    return result


def reference_interpolate(
    record: dict, day: Fraction, age: Fraction
) -> Fraction | None:
    """Locate bracketing points by search and evaluate their Lagrange weights."""
    days = [r["common_year_day_offset"] for r in record["rows"]]
    ages = record["age_columns_years"]
    if not days[0] <= day <= days[-1] or not ages[0] <= age <= ages[-1]:
        raise ValueError("Outside original table numeric axes")
    cells = reference_cells(record)

    def bracket(nodes, point):
        lo = max(n for n in nodes if n <= point)
        hi = min(n for n in nodes if n >= point)
        if hi == lo:
            return [(lo, Fraction(1))]
        return [(lo, (hi - point) / (hi - lo)), (hi, (point - lo) / (hi - lo))]

    terms = []
    for x, wx in bracket(days, day):
        for y, wy in bracket(ages, age):
            value = cells[(days.index(x), y)]
            if value is None:
                return None
            terms.append(value * wx * wy)
    return sum(terms, Fraction())


def replay(record: dict) -> dict:
    cells = reference_cells(record)
    unknown = [
        {"row": r, "age_years": age}
        for (r, age), value in cells.items()
        if value is None
    ]
    sample = record["printed_worked_example"]
    printed_base = sum(
        v * unit for v, unit in zip(sample["full_year_arc_degrees_minutes"], [60, 1])
    )
    printed_total = sum(
        v * unit for v, unit in zip(sample["printed_total_degrees_minutes"], [60, 1])
    )
    literal_sum = (
        sample["until_january_zero_arcminutes"]
        + printed_base
        + sample["partial_year_printed_arcminutes"]
    )
    base = reference_interpolate(record, Fraction(26), Fraction(54))
    first = reference_interpolate(record, Fraction(26), Fraction(50))
    last = reference_interpolate(record, Fraction(26), Fraction(60))
    assert base is not None and first is not None and last is not None
    zero = (
        Fraction(2, 5) * record["rows"][2]["raw_until_january_zero_arcminutes"]
        + Fraction(3, 5) * record["rows"][3]["raw_until_january_zero_arcminutes"]
    )
    unrounded = base + zero + (last - first) * Fraction(7, 120)
    return {
        "source": record["source"],
        "raw_date_rows": len(record["rows"]),
        "raw_age_cells": len(cells),
        "resolved_age_cells": len(cells) - len(unknown),
        "unresolved_age_cells": unknown,
        "raw_last_column_cells": len(record["rows"]),
        "all_table_degrees_resolved": not unknown,
        "all_printed_raw_cells_retained": True,
        "worked_example": {
            "printed_total_arcminutes": printed_total,
            "literal_components_sum_arcminutes": literal_sum,
            "literal_arithmetic_matches_print": literal_sum == printed_total,
            "exact_bilinear_base_fraction": [base.numerator, base.denominator],
            "hypothetical_unrounded_total_fraction": [
                unrounded.numerator,
                unrounded.denominator,
            ],
            "printed_minus_unrounded_arcminutes": float(printed_total - unrounded),
            "unrounded_extension_adopted_as_original": False,
        },
        "source_calendar_and_rounding_fully_resolved": False,
        "full_original_method_accepted": False,
        "empirical_outcomes": 0,
        "all_four_objectives_validated": False,
        "authority_certified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-record", type=Path, default=RECORD)
    parser.add_argument("--source-pdf", type=Path)
    parser.add_argument("--day-offset", type=Fraction)
    parser.add_argument("--age-years", type=Fraction)
    args = parser.parse_args()
    if (args.day_offset is None) != (args.age_years is None):
        parser.error("A numerical probe requires both --day-offset and --age-years")
    raw = args.source_record.read_bytes()
    if hashlib.sha256(raw).hexdigest() != RECORD_SHA256:
        raise ValueError("Frozen Witte1925 table checksum mismatch")
    record = json.loads(raw)
    if (
        args.source_pdf
        and hashlib.sha256(args.source_pdf.read_bytes()).hexdigest()
        != record["source"]["source_pdf_sha256"]
    ):
        raise ValueError("Witte1925 original PDF checksum mismatch")
    report = replay(record)
    report["source_record_sha256"] = RECORD_SHA256
    report["source_pdf_bytes_checked"] = bool(args.source_pdf)
    if args.day_offset is not None:
        value = reference_interpolate(record, args.day_offset, args.age_years)
        report["numeric_probe"] = {
            "status": "underdetermined" if value is None else "computed",
            "day_offset": str(args.day_offset),
            "age_years": str(args.age_years),
            "arcminutes_fraction": (
                None if value is None else [value.numerator, value.denominator]
            ),
            "scope": "Explicit numerical axes only; not a user birth/target date conversion",
        }
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2, allow_nan=False)
        output.write("\n")
    return 0 if report["all_table_degrees_resolved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
