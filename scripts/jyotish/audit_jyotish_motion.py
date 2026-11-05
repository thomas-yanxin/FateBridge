"""Read-only primary motion-table audit; contradictions deliberately exit1.

No FateBridge or Swiss imports. Decimal table facts stay literal. A consistency
relation identifies a contradiction, not which member should be corrected.
"""

from __future__ import annotations

import argparse
import cmath
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path


def quantum(text: str) -> Fraction:
    return Fraction(1, 10 ** len(text.partition(".")[2]))


def audit_tables(primary: dict) -> dict:
    comparisons, skipped, conflicts = 0, [], []
    for body, table in primary["tables"].items():
        for col, days in enumerate(table["columns_days"]):
            for lower in range(1, 10):
                for higher in range(lower * 2, 10, lower):
                    a, b = table["rows"][lower - 1][col], table["rows"][higher - 1][col]
                    label = {"body": body, "column_days": days, "rows": [lower, higher]}
                    if a is None or b is None:
                        skipped.append(label)
                        continue
                    comparisons += 1
                    multiplier = higher // lower
                    difference = (Fraction(b) - multiplier * Fraction(a)) % 360
                    error = min(difference, 360 - difference)
                    envelope = quantum(b) + multiplier * quantum(a)
                    if error > envelope:
                        conflicts.append(
                            {
                                **label,
                                "literal_cells": [a, b],
                                "multiplier": multiplier,
                                "residual_degrees": float(error),
                                "rounding_truncation_envelope_degrees": float(envelope),
                                "material_over_0_1_degree": error > Fraction(1, 10),
                                "meaning": "Inconsistent pair, not a choice of the correct cell",
                            }
                        )
    return {
        "evaluated_relations": comparisons,
        "skipped_unclear_relations": skipped,
        "conflicts": conflicts,
    }


def primary_angular_reference(case: dict) -> float:
    # Independent vector midpoint + cosine angular separation, rather than
    # the production rational/modulo formulation. Not used for table fitting.
    a, b, apogee = (
        math.radians(float(case[k])) for k in ("mean", "true", "seeghrochcha")
    )
    vector = cmath.exp(1j * a) + cmath.exp(1j * b)
    if abs(vector) < 1e-12:
        raise ValueError("Opposed mean/true midpoint is ambiguous")
    cosine = math.cos(apogee - cmath.phase(vector))
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine)))) / 3


def compare_oracle_tables(primary: dict, oracle: dict) -> dict:
    differences = []
    checked = 0
    for name, table in primary["tables"].items():
        index = oracle["internal_names"].index(name)
        reference = oracle["upstream_literal_tables"][index]
        for row, cells in enumerate(table["rows"], 1):
            for col, literal in enumerate(cells):
                if literal is None:
                    continue
                checked += 1
                actual = reference[str(row)][col]
                if Fraction(literal) != Fraction(str(actual)):
                    differences.append(
                        {
                            "body": name,
                            "row": row,
                            "column_days": table["columns_days"][col],
                            "printed": literal,
                            "software": actual,
                            "scope": "Disagreement only; neither value certified by this comparison",
                        }
                    )
    return {"compared_clear_cells": checked, "differences": differences}


def build_report(primary: dict) -> dict:
    tables = audit_tables(primary)
    exact_interval = (
        Fraction(6862)
        + Fraction(14 * 3600 + 6 * 60 + 16, 86400)
        + (Fraction(76) - Fraction(77 * 60 + 35, 60)) / 360
    )
    venus_listed_total = sum(
        map(Fraction, ("252.88", "201.72", "96.13", "0.92", "328.51", "-5.01"))
    )
    return {
        "source": primary["source"],
        "status": (
            "source_table_not_consistent"
            if tables["conflicts"]
            else "no_detected_table_relation_conflict"
        ),
        "table_checks": tables,
        "angular_worked_cases": [
            {
                **row,
                "independent_vector_virupa": primary_angular_reference(row),
                "printed_virupa_error": abs(
                    primary_angular_reference(row) - float(row["printed_virupa"])
                ),
            }
            for row in primary["worked_angular_cases"]
        ],
        "interval_arithmetic": {
            "exact_1918_Ujjain_interval_days": str(exact_interval),
            "float_days": float(exact_interval),
            "printed14h_as_days": "0.581",
            "14h_minus_printed_seconds": float(
                (Fraction(7, 12) - Fraction("0.581")) * 86400
            ),
            "scope": "Source LMT arithmetic, not an observed UTC/UT1 conversion or future leap assumption",
        },
        "venus_example48": {
            "listed_total": float(venus_listed_total),
            "printed_total": 878.35,
            "unexplained_gap": float(Fraction("878.35") - venus_listed_total),
        },
        "source_conflicts": primary["worked_source_conflicts"],
        "native_activation_eligible": False,
        "remaining": [
            "Adjudicate conflicting source cells and coefficients",
            "Verify historical mean and Seeghrochcha frame mapping to native Lahiri true positions",
            "Independently validate a dated mean model across epochs, including negative intervals and wrap",
        ],
        "authority_certified": False,
        "independent_real_event_cases": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument(
        "--oracle", type=Path, help="Optional frozen reference; never query or patch it"
    )
    args = parser.parse_args()
    source = (
        Path(__file__).resolve().parents[2]
        / "tests/fixtures/jyotish-motion-primary.json"
    )
    protected = [source, *([args.oracle] if args.oracle else [])]
    if args.report.resolve() in {path.resolve() for path in protected}:
        parser.error("report must not overwrite a primary or oracle reference input")
    primary = json.loads(source.read_text())
    report = build_report(primary)
    if args.oracle:
        oracle = json.loads(args.oracle.read_text())
        report["oracle_table_comparison"] = compare_oracle_tables(primary, oracle)
        report["oracle_fixture_sha256"] = hashlib.sha256(
            args.oracle.read_bytes()
        ).hexdigest()
    report["primary_fixture_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "evaluated_relations": report["table_checks"]["evaluated_relations"],
                "conflicts": len(report["table_checks"]["conflicts"]),
                "native_activation_eligible": False,
            }
        )
    )
    return int(bool(report["table_checks"]["conflicts"]))


if __name__ == "__main__":
    raise SystemExit(main())
