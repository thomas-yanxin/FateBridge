"""Collate two literal Raman witnesses; unresolved source differences exit1.

This never selects cells for production, repairs a source, or regenerates a
reference from FateBridge. The existing Fraction table-relation audit supplies
the same comparison and display-quantum policy for both printing witnesses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

from scripts.jyotish.audit_jyotish_motion import audit_tables

COLUMNS = {
    "Sun": [1, 100, 1000, 10000],
    "Mars": [1, 100, 1000, 10000],
    "Jupiter": [1, 10, 100, 1000, 10000],
    "Saturn": [1, 10, 100, 1000, 10000],
    "Mercury": [1, 10, 100, 1000, 10000],
    "Venus": [1, 10, 100, 1000, 10000],
}


def validate_tables(witness: dict[str, Any]) -> None:
    tables = witness["tables"]
    if set(tables) != set(COLUMNS):
        raise ValueError("Both witnesses must contain all six motion tables")
    for name, columns in COLUMNS.items():
        table = tables[name]
        if table["columns_days"] != columns:
            raise ValueError(f"Unexpected day-column domain for {name}")
        if len(table["rows"]) != 9:
            raise ValueError(f"All nine digit rows are required for {name}")
        for row in table["rows"]:
            if len(row) != len(columns):
                raise ValueError(f"All cells are required for {name}")
            for cell in row:
                if cell is not None and (
                    not isinstance(cell, str)
                    or re.fullmatch(r"\d+\.\d+", cell) is None
                    or not 0 <= Fraction(cell) < 360
                ):
                    raise ValueError("Cells must be literal decimal strings or null")


def build_report(
    older: dict[str, Any],
    earlier: dict[str, Any],
    text: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """`older` is the preexisting fixture, not the earlier publication date."""
    for witness in (older, earlier):
        validate_tables(witness)
    differences, precision, legibility = [], [], []
    compared = 0
    for name, columns in COLUMNS.items():
        for row in range(9):
            for column, days in enumerate(columns):
                a = older["tables"][name]["rows"][row][column]
                b = earlier["tables"][name]["rows"][row][column]
                entry = {
                    "planet": name,
                    "row": row + 1,
                    "column_days": days,
                    "existing_witness_literal": a,
                    "earlier_witness_literal": b,
                }
                if a is None or b is None:
                    legibility.append(entry)
                    continue
                compared += 1
                if Fraction(a) != Fraction(b):
                    differences.append(entry)
                elif a != b:
                    precision.append(entry)
    audits = {
        "existing_witness": audit_tables(older),
        "earlier_witness": audit_tables(earlier),
    }

    def keys(audit: dict[str, Any]) -> set[tuple[Any, ...]]:
        return {(r["body"], r["column_days"], *r["rows"]) for r in audit["conflicts"]}

    old_keys, early_keys = (keys(a) for a in audits.values())
    text_audit = audit_text(text) if text is not None else None
    accepted = (
        not differences
        and not old_keys
        and not early_keys
        and (text_audit is None or not text_audit["source_conflicts"])
    )
    return {
        "status": (
            "no_detected_source_conflict" if accepted else "source_conflicts_retained"
        ),
        "sources": {
            "existing_witness": older["source"],
            "earlier_witness": earlier["source"],
        },
        "table_cells_per_witness": 252,
        "comparable_clear_cells": compared,
        "numeric_differences": differences,
        "equal_value_display_precision_differences": precision,
        "legibility_differences": legibility,
        "relation_audits": audits,
        "earlier_witness_text_arithmetic": text_audit,
        "conflict_relation_key_comparison": {
            "both": sorted(old_keys & early_keys),
            "existing_only": sorted(old_keys - early_keys),
            "earlier_only": sorted(early_keys - old_keys),
            "meaning": "Locations of conflicting relations, not adjudicated cells, corrections or independent errors. Unequal legibility and display quanta remain visible.",
        },
        "numerical_comparison": "Exact rational equality of literal decimal values; display-precision changes listed separately. No looser threshold fitted to the new witness.",
        "historical_mean_model_activation_eligible": False,
        "complete_single_original_accepted": False,
        "blinded": False,
        "real_event_cases": 0,
        "whole_goal_complete": False,
    }


def audit_text(text: dict[str, Any]) -> dict[str, Any]:
    """Keep the earlier input clock and each separate printed operand."""
    clock, mercury, venus = (text[k] for k in ("standard_clock", "Mercury", "Venus"))

    def seconds(hms: list[int]) -> int:
        h, m, s = hms
        return h * 3600 + m * 60 + s

    degrees, minutes = clock["birth_longitude_degrees_minutes"]
    longitude = Fraction(degrees) + Fraction(minutes, 60)
    converted = (
        Fraction(seconds(clock["birth_local_mean_hms"]))
        + (clock["reference_longitude_degrees"] - longitude) * 240
    )
    listed_sum = sum(map(Fraction, venus["example48_signed_terms"]))
    calculated_modulo = listed_sum % 360
    conflicts = []

    def relation(location: str, difference: Fraction) -> None:
        if difference:
            conflicts.append(
                dict(location=location, difference_degrees=str(difference))
            )

    apogee_gap = Fraction(mercury["body_epoch_apogee"]) - Fraction(
        mercury["tableVIII_typeset_adopted_apogee"]
    )
    relation("Mercury section102 versus TableVIII", apogee_gap)
    summary_gap = Fraction(venus["section104_summary_apogee"]) - Fraction(
        venus["example48_printed_modulo360"]
    )
    relation("Venus Example48 versus section104 summary", summary_gap)
    relation(
        "Venus Example48 listed terms versus printed total",
        Fraction(venus["example48_printed_total"]) - listed_sum,
    )
    relation(
        "Venus Example48 listed modulo versus printed modulo",
        Fraction(venus["example48_printed_modulo360"]) - calculated_modulo,
    )
    relation(
        "Mercury section102 versus Example47 year coefficient",
        Fraction(mercury["body_correction_year_coefficient"])
        - Fraction(mercury["example47_year_coefficient"]),
    )
    relation(
        "Venus section103 versus Example48 year coefficient",
        Fraction(venus["body_subtracted_correction_year_coefficient"])
        - Fraction(venus["example48_year_coefficient"]),
    )
    return {
        "edition": text["edition"],
        "source_clock": clock,
        "exact_converted_reference_seconds_after_midnight": str(converted),
        "displayed_reference_time_minus_exact_seconds": str(
            seconds(clock["example38_printed_reference_hms"]) - converted
        ),
        "exact_reference_time_minus_displayed_fractional_day_seconds": str(
            converted - Fraction(clock["example39_printed_fractional_day"]) * 86400
        ),
        "clock_scope": "Arithmetic differences only. The source display/rounding convention is not adjudicated; no UTC or physical-epoch precision claim.",
        "mercury_body_and_example_year_coefficients_equal": Fraction(
            mercury["body_correction_year_coefficient"]
        )
        == Fraction(mercury["example47_year_coefficient"]),
        "venus_listed_sum": str(listed_sum),
        "venus_listed_sum_matches_printed_total": listed_sum
        == Fraction(venus["example48_printed_total"]),
        "venus_listed_modulo_matches_printed_modulo": calculated_modulo
        == Fraction(venus["example48_printed_modulo360"]),
        "source_conflicts": conflicts,
        "scope": "These are selected text witnesses, not an exhaustive audit of the earlier edition or evidence that a particular correction is author-approved.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    paths = [
        root / "tests/fixtures/jyotish-motion-primary.json",
        root / "tests/fixtures/jyotish-raman-1942-motion-primary.json",
        root / "tests/fixtures/jyotish-raman-1942-motion-text.json",
    ]
    if args.report.exists() or args.report.resolve() in {p.resolve() for p in paths}:
        parser.error("report must be a new file and must not overwrite any reference")
    raw = [p.read_bytes() for p in paths]
    report = build_report(*(json.loads(b) for b in raw))
    report["fixture_sha256"] = {
        str(p.relative_to(root)): hashlib.sha256(b).hexdigest()
        for p, b in zip(paths, raw)
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "comparable_clear_cells": report["comparable_clear_cells"],
                "numeric_differences": len(report["numeric_differences"]),
                "conflicts_by_witness": {
                    name: len(a["conflicts"])
                    for name, a in report["relation_audits"].items()
                },
                "historical_mean_model_activation_eligible": False,
            }
        )
    )
    return int(report["status"] != "no_detected_source_conflict")


if __name__ == "__main__":
    raise SystemExit(main())
