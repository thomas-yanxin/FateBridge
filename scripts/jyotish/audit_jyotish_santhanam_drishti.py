"""Read-only selected-witness audit; unresolved source readings deliberately exit1.

The default audit imports no FateBridge or Swiss code. Optional --native reads
the selected Raman calculator only after the independent report is constructed.
Neither source reading is silently substituted for a production algorithm.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any


def ordinary(x: Fraction) -> Fraction:
    if not 0 <= x <= 360:
        raise ValueError("Scalar aspect angle must be in0..360")
    if x < 30 or x >= 300:
        return Fraction(0)
    if x < 60:
        return (x - 30) / 2
    if x < 90:
        return x - 45
    if x < 120:
        return (120 - x) / 2 + 30
    if x < 150:
        return 150 - x
    if x < 180:
        return 2 * (x - 150)
    return (300 - x) / 2


def commentary_values(primary: dict, body: str, x: Fraction) -> list[Fraction]:
    base = ordinary(x)
    rule = primary["commentary_additions"][body]
    extra = Fraction(rule["extra_virupa"])
    for lower, upper in rule["strict_interiors"]:
        lo, hi = Fraction(lower), Fraction(upper)
        if lo < x < hi:
            return [base + extra]
        if x in {lo, hi}:
            return sorted({base, base + extra})
    return [base]


def verse_sector_value(
    body: str, x: Fraction, sector: int, full_mars6_sector: bool
) -> Fraction:
    """One declared quotient-sector reading; ordinary base comes from notes."""
    u = x - sector * 30
    if body == "Saturn":
        if sector in {1, 9}:
            return 2 * u
        if sector == 2:
            return 60 - u / 2
        if sector == 8:
            return 30 + u
    elif body == "Mars":
        if sector in {3, 7}:
            return 60 - u
        if sector == 2:
            return u + u / 2 + 15
        if sector == 6 and full_mars6_sector:
            return Fraction(60)
    elif body == "Jupiter":
        if sector in {3, 7}:
            return u / 2 + 45
        if sector in {4, 8}:
            return 60 - u
    else:
        raise ValueError("Only three explicitly special bodies are in this audit")
    return ordinary(x)


def verse_values(body: str, x: Fraction, full_mars6_sector: bool) -> list[Fraction]:
    if not 0 <= x < 360:
        raise ValueError("Normalized comparison angle required")
    sector = int(x // 30)
    if x % 30:
        return [verse_sector_value(body, x, sector, full_mars6_sector)]
    left_x, left_sector = (Fraction(360), 11) if x == 0 else (x, sector - 1)
    return sorted(
        {
            verse_sector_value(body, left_x, left_sector, full_mars6_sector),
            verse_sector_value(body, x, sector, full_mars6_sector),
        }
    )


def speculum_rows(primary: dict) -> list[dict]:
    rows: list[dict[str, Any]] = []
    nominal_seen: set[Fraction] = set()
    for column in primary["ordinary_speculum"]["columns"]:
        degree, minute = column["start"]
        first = Fraction(degree) + Fraction(minute, 60)
        step = Fraction(column["step_minutes"], 60)
        if step != Fraction(1, 2) or not column["values"]:
            raise ValueError("Every printed half-degree column is required")
        final = first + step * (len(column["values"]) - 1)
        d, m = column["end"]
        if final != Fraction(d) + Fraction(m, 60):
            raise ValueError("Column end disagrees with its literal cell count")
        overrides = {
            item["row_index_zero_based"]: item["literal_degrees_minutes"]
            for item in column.get("angle_overrides", [])
        }
        if any(not 0 <= i < len(column["values"]) for i in overrides):
            raise ValueError(
                "Literal coordinate override is outside its printed column"
            )
        for index, literal in enumerate(column["values"]):
            nominal = first + index * step
            if nominal in nominal_seen or not isinstance(literal, str):
                raise ValueError("Duplicate printed row or nonliteral speculum cell")
            nominal_seen.add(nominal)
            d, m = overrides.get(index, [nominal, 0])
            angle = Fraction(d) + Fraction(m, 60)
            expected = ordinary(angle)
            rows.append(
                dict(
                    angle_degrees=str(angle),
                    sequence_angle_degrees=str(nominal),
                    column_row_zero_based=index,
                    printed=literal,
                    formula_value=str(expected),
                    equal=Fraction(literal) == expected,
                    pdf_page=column["pdf_page"],
                )
            )
    if nominal_seen != {Fraction(i, 2) for i in range(60, 600)}:
        raise ValueError("The complete540printed row slots30..299.5are required")
    return rows


def given_benefic_drik_readings(
    other_signed_sum: Fraction, mercury: Fraction, jupiter: Fraction
) -> dict[str, Fraction]:
    if mercury < 0 or jupiter < 0:
        raise ValueError("Given benefic aspect intensities must be nonnegative")
    combined = mercury + jupiter
    return {
        "quarter_only_raman120": (other_signed_sum + combined) / 4,
        "whole_replaces_quarter": other_signed_sum / 4 + combined,
        "whole_superadded_after_quarter": (other_signed_sum + combined) / 4 + combined,
    }


def build_report(primary: dict) -> dict:
    table = speculum_rows(primary)
    dense: list[dict[str, Any]] = []
    for body in ("Mars", "Jupiter", "Saturn"):
        for half in range(720):
            x = Fraction(half, 2)
            readings = {
                "commentary_printed_additions": commentary_values(primary, body, x),
                "verse_specials_on_commentary_base_mars6_exact_point": verse_values(
                    body, x, False
                ),
                "verse_specials_on_commentary_base_mars6_full_sector": verse_values(
                    body, x, True
                ),
            }
            dense.append(
                dict(
                    body=body,
                    angle_degrees=str(x),
                    reading_candidates={
                        k: [str(v) for v in a] for k, a in readings.items()
                    },
                    any_endpoint_ambiguity=any(len(a) > 1 for a in readings.values()),
                    candidate_sets_differ=len({tuple(a) for a in readings.values()})
                    > 1,
                )
            )
    direction = (Fraction(87) - 12) % 360
    reverse = (-direction) % 360
    return {
        "source": primary["source"],
        "status": "selected_witness_readings_not_uniquely_adjudicated",
        "ordinary_speculum": {
            "printed_cells": len(table),
            "relations": table,
            "conflicts": [r for r in table if not r["equal"]],
            "unique_literal_coordinates": len({r["angle_degrees"] for r in table}),
            "coordinate_labels_preserved": True,
            "terminal300_not_printed": True,
        },
        "dense_comparison": {
            "positions": len(dense),
            "candidate_sets_differ": sum(r["candidate_sets_differ"] for r in dense),
            "positions_with_endpoint_ambiguity": sum(
                r["any_endpoint_ambiguity"] for r in dense
            ),
            "rows": dense,
            "scope": "Declared mathematical readings on all720half-degree positions per body, not2160observed errors, charts or events.",
        },
        "direction_probe": {
            "given_aspector": "12",
            "given_aspected": "87",
            "aspected_minus_aspector_degrees": str(direction),
            "aspector_minus_aspected_degrees": str(reverse),
            "ordinary_values": [str(ordinary(direction)), str(ordinary(reverse))],
            "direction_uniquely_selected": False,
        },
        "drik_given_benefic_mercury60_jupiter30_other_sum0": {
            **{
                k: str(v)
                for k, v in given_benefic_drik_readings(
                    Fraction(0), Fraction(60), Fraction(30)
                ).items()
            },
            "scope": "Algebra with explicitly given benefic nature; no arbitrary natal Mercury/Moon classification or source adjudication.",
        },
        "raw_verse6_8_beyond300_probe": [
            dict(
                angle_degrees=str(x),
                literal_first_clause_reading=str((300 - x) / 2),
                commentary_outside=0,
            )
            for x in (Fraction(315), Fraction(330), Fraction(345))
        ],
        "unresolved": [
            "Subtraction wording versus target-plus360instruction; no unique direction claimed",
            "Translated special clauses versus commentary additions; quotient-sector reading is explicitly conditional",
            "Mars printed249versus selected Raman240; no silent correction",
            "Mars sum6fractional-band coverage; exact-point and full-sector readings retained",
            "Special-rule endpoints represented by algebraic neighbor candidates, not assigned an undocumented scalar",
            "27.19Mercury/Jupiter full-aspect clause is separate from Raman120quarter sum",
        ],
        "production_activation_eligible": False,
        "complete_single_original_accepted": False,
        "independent_real_event_cases": 0,
        "independent_model_blind_reviews": 0,
        "whole_goal_complete": False,
    }


def compare_native(primary: dict, report: dict) -> dict:
    from fatebridge.core import jyotish_balas

    ordinary_differences, commentary_differences = [], []
    for row in report["ordinary_speculum"]["relations"]:
        native_angle = float(Fraction(row["angle_degrees"]))
        value = jyotish_balas.aspect_value("Sun", 0, native_angle)["value"]
        if Fraction(value) != Fraction(row["printed"]):
            ordinary_differences.append(dict(**row, native=value))
    for body in ("Mars", "Jupiter", "Saturn"):
        for half in range(720):
            x = Fraction(half, 2)
            value = jyotish_balas.aspect_value(body, 0, float(x))["value"]
            candidates = commentary_values(primary, body, x)
            if Fraction(value) not in candidates:
                commentary_differences.append(
                    dict(
                        body=body,
                        angle_degrees=str(x),
                        native=value,
                        commentary_candidates=[str(v) for v in candidates],
                    )
                )
    return dict(
        native_source=str(jyotish_balas.__file__),
        native_source_sha256=hashlib.sha256(
            Path(jyotish_balas.__file__).read_bytes()
        ).hexdigest(),
        printed_ordinary_cells_compared=len(report["ordinary_speculum"]["relations"]),
        ordinary_differences=ordinary_differences,
        commentary_positions_compared=2160,
        commentary_differences=commentary_differences,
        scope="Selected Raman implementation compared after pure source audit; not the reference generator or an independent ephemeris.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--native", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    source = root / "tests/fixtures/jyotish-santhanam-drishti-primary.json"
    if args.report.exists() or args.report.resolve() == source.resolve():
        parser.error(
            "report must be a new file; reference and prior evidence cannot be overwritten"
        )
    raw = source.read_bytes()
    primary = json.loads(raw)
    report = build_report(primary)
    report["primary_fixture_sha256"] = hashlib.sha256(raw).hexdigest()
    if args.native:
        report["native_comparison"] = compare_native(primary, report)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                status=report["status"],
                printed_cells=report["ordinary_speculum"]["printed_cells"],
                table_conflicts=len(report["ordinary_speculum"]["conflicts"]),
                dense_positions=2160,
                dense_reading_differences=report["dense_comparison"][
                    "candidate_sets_differ"
                ],
                production_activation_eligible=False,
            )
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
