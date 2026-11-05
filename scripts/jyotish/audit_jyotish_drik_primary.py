"""Audit literal Raman Drik tables; contradictions are evidence and exit1.

No FateBridge, Swiss or reference-software imports. This checks source internal
arithmetic; it does not choose which printed operand to amend.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path


def build_report(primary: dict) -> dict:
    names = primary["planet_order"]
    headings = [
        Fraction(d) + Fraction(m, 60)
        for d, m in primary["example53_header_degrees_minutes"]
    ]
    angles = []
    relations = []

    def check(label: str, target: str, calculated: Decimal, printed: str) -> None:
        literal = Decimal(printed)
        relations.append(
            {
                "relation": label,
                "target": target,
                "calculated_from_literal_inputs": str(calculated),
                "printed": printed,
                "difference": str(literal - calculated),
                "equal": calculated == literal,
            }
        )

    for i, aspector in enumerate(names):
        for j, target in enumerate(names):
            if i == j:
                continue
            d, m = primary["example53_directed_degrees_minutes"][i][j]
            literal = Fraction(d) + Fraction(m, 60)
            expected = (headings[j] - headings[i]) % 360
            gap = (literal - expected + 180) % 360 - 180
            if gap:
                angles.append(
                    {
                        "aspector": aspector,
                        "target": target,
                        "literal_angle_degrees": str(literal),
                        "header_difference_degrees": str(expected),
                        "difference_arcminutes": str(gap * 60),
                        "exceeds_three_display_quanta": abs(gap * 60) > 3,
                    }
                )
    for sign in ("positive", "negative"):
        for j, target in enumerate(names):
            value = sum(
                (
                    Decimal(row[j])
                    for row in primary[f"example54_{sign}_contributions"].values()
                ),
                Decimal(0),
            )
            check(
                f"example54_{sign}_subtotal",
                target,
                value,
                primary[f"example54_{sign}_subtotals"][j],
            )
    for j, target in enumerate(names):
        calculated = Decimal(primary["example54_positive_subtotals"][j]) - Decimal(
            primary["example54_negative_subtotals"][j]
        )
        check(
            "example54_net_from_printed_subtotals",
            target,
            calculated,
            primary["example54_signed_net"][j],
        )
        check(
            "example54_to_example55_net",
            target,
            Decimal(primary["example54_signed_net"][j]),
            primary["example55_signed_net"][j],
        )
        quarter = (Decimal(primary["example55_signed_net"][j]) / 4).quantize(
            Decimal(".01"), rounding=ROUND_HALF_UP
        )
        check(
            "example55_net_to_drik_half_up",
            target,
            quarter,
            primary["example55_signed_drik"][j],
        )
    conflicts = [r for r in relations if not r["equal"]]
    return {
        "source": primary["source"],
        "status": (
            "source_internal_conflicts"
            if conflicts or angles
            else "no_detected_literal_conflict"
        ),
        "angle_relations": 42,
        "literal_angle_disagreements": angles,
        "angle_precision_scope": "Exact displayed-minute arithmetic is reported without correction. A separate conservative three-quantum envelope covers two header quanta plus the displayed angle quantum; it does not adjudicate their rounding or select the correct cell.",
        "decimal_relations": relations,
        "decimal_conflicts": conflicts,
        "drik_rounding_scope": "Half-up at displayed0.01 is an explicit arithmetic comparison, not an author-adjudicated global rounding rule.",
        "nature_witness": primary["nature_witness"],
        "complete_single_original_accepted": False,
        "real_event_cases": 0,
        "scope": "Primary source arithmetic only; neither native calculation accuracy nor prediction evidence. Counts are relations, not independent erroneous cells.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    source = (
        Path(__file__).resolve().parents[2] / "tests/fixtures/jyotish-drik-primary.json"
    )
    if args.report.resolve() == source.resolve():
        parser.error("report must not overwrite the primary source fixture")
    raw = source.read_bytes()
    report = build_report(json.loads(raw))
    report["primary_fixture_sha256"] = hashlib.sha256(raw).hexdigest()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "angle_disagreements": len(report["literal_angle_disagreements"]),
                "decimal_conflicts": len(report["decimal_conflicts"]),
                "complete_single_original_accepted": False,
            }
        )
    )
    return int(
        bool(report["literal_angle_disagreements"] or report["decimal_conflicts"])
    )


if __name__ == "__main__":
    raise SystemExit(main())
