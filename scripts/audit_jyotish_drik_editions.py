"""Read-only Raman given-input audit; printed conflicts keep the source gate shut.

The default path uses only the standard library. --native compares the selected
calculator only after the independent mathematical/source report is complete.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path

PLANETS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
KNOTS = ((30, 0), (60, 15), (90, 45), (120, 30), (150, 0), (180, 60), (300, 0))


def parts_from_clauses(
    body: str, angle: Fraction, primary: dict
) -> tuple[Fraction, Fraction]:
    """Ordinary clauses as knot interpolation; no special endpoint adjudication."""
    if body not in PLANETS or not 0 <= angle < 360:
        raise ValueError("Seven-graha normalized directed angle required")
    base = Fraction(0)
    for (left, low), (right, high) in zip(KNOTS, KNOTS[1:]):
        if left <= angle <= right:
            base = low + (angle - left) * Fraction(high - low, right - left)
            break
    rules = primary["source_rule_witness"]
    for lo, hi in rules["special_strict_interiors"].get(body, []):
        if angle in {lo, hi}:
            raise ValueError("This witness audit does not adjudicate special endpoints")
        if lo < angle < hi:
            return base, Fraction(rules["special_addition_virupa"][body])
    return base, Fraction(0)


def value_from_clauses(body: str, angle: Fraction, primary: dict) -> Fraction:
    return sum(parts_from_clauses(body, angle, primary), Fraction(0))


def given_inputs(primary: dict) -> list[Fraction]:
    if tuple(primary["planet_order"]) != PLANETS:
        raise ValueError("Literal planet orientation/order must be preserved")
    headings = primary["example53_headers_degrees_minutes"]
    if len(headings) != 7:
        raise ValueError("All seven printed headings are required")
    for d, m in headings:
        if (
            type(d) is not int
            or type(m) is not int
            or not 0 <= d < 360
            or not 0 <= m < 60
        ):
            raise ValueError("Literal degree/minute heading required")
    for name in (
        "example53_angles_target_rows",
        "example54_signed_contributions_target_rows",
    ):
        rows = primary[name]
        if len(rows) != 7 or any(len(row) != 7 for row in rows):
            raise ValueError(
                "All49printed matrix slots, including blanks, are required"
            )
    for name in (
        "example54_signed_net",
        "example55_signed_net",
        "example55_signed_drik",
        "example56_signed_drik",
    ):
        if len(primary[name]) != 7:
            raise ValueError("All seven printed totals are required")
    return [Fraction(d) + Fraction(m, 60) for d, m in headings]


def build_report(primary: dict, later: dict) -> dict:
    headings = given_inputs(primary)
    angles, cells, decimal, terms = [], [], [], []
    natures = primary["nature_witness"]["signed_example_columns"]
    if set(natures) != set(PLANETS) or not set(natures.values()) <= {
        "benefic",
        "malefic",
    }:
        raise ValueError("All seven explicitly given worked-column signs are required")

    def relation(kind: str, target: str, expected: Decimal, printed: str) -> None:
        decimal.append(
            dict(
                relation=kind,
                target=target,
                calculated=str(expected),
                printed=printed,
                difference=str(Decimal(printed) - expected),
                equal=Decimal(printed) == expected,
            )
        )

    for ti, target in enumerate(PLANETS):
        for ai, aspector in enumerate(PLANETS):
            x = (headings[ti] - headings[ai]) % 360
            literal = primary["example53_angles_target_rows"][ti][ai]
            raw = primary["example54_signed_contributions_target_rows"][ti][ai]
            if literal is not None:
                if (
                    len(literal) != 2
                    or any(type(v) is not int for v in literal)
                    or not 0 <= literal[0] < 360
                    or not 0 <= literal[1] < 60
                ):
                    raise ValueError("Literal angle must be degrees/minutes or null")
                printed_angle = Fraction(literal[0]) + Fraction(literal[1], 60)
                gap = (printed_angle - x + 180) % 360 - 180
                angles.append(
                    dict(
                        target=target,
                        aspector=aspector,
                        header_difference=str(x),
                        printed_angle=str(printed_angle),
                        difference_arcminutes=str(gap * 60),
                        equal=not gap,
                    )
                )
            ordinary, special = parts_from_clauses(aspector, x, primary)
            expected = ordinary + special
            sign = 1 if natures[aspector] == "benefic" else -1
            if raw is not None and (
                not raw or any(not isinstance(v, str) for v in raw)
            ):
                raise ValueError("Signed printed terms must remain literal strings")
            combined = (
                sum((Fraction(v) for v in raw), Fraction(0))
                if raw is not None
                else None
            )
            if raw is not None:
                expected_parts = (
                    [sign * special, sign * ordinary]
                    if len(raw) == 2
                    else [sign * expected]
                )
                if len(raw) != len(expected_parts):
                    raise ValueError(
                        "Only the literal single or two-term printed cell is supported"
                    )
                for index, (printed_term, exact_term) in enumerate(
                    zip(raw, expected_parts)
                ):
                    d = Decimal(exact_term.numerator) / Decimal(exact_term.denominator)
                    quantum = Decimal(printed_term).as_tuple().exponent
                    if not isinstance(quantum, int):
                        raise ValueError("Finite printed decimal quantum required")
                    unit = Decimal(1).scaleb(quantum)
                    terms.append(
                        dict(
                            target=target,
                            aspector=aspector,
                            term_index=index,
                            role=(
                                ("special" if index == 0 else "ordinary")
                                if len(raw) == 2
                                else "combined"
                            ),
                            exact_header_formula=str(exact_term),
                            printed=printed_term,
                            exact_equal=Fraction(printed_term) == exact_term,
                            half_up_at_printed_quantum=str(
                                d.quantize(unit, rounding=ROUND_HALF_UP)
                            ),
                            toward_zero_at_printed_quantum=str(
                                d.quantize(unit, rounding=ROUND_DOWN)
                            ),
                        )
                    )
            cells.append(
                dict(
                    target=target,
                    aspector=aspector,
                    directed_angle=str(x),
                    exact_ordinary=str(ordinary),
                    exact_special=str(special),
                    exact_unsigned=str(expected),
                    given_nature=natures[aspector],
                    exact_signed=str(sign * expected),
                    printed_terms=raw,
                    printed_combined=None if combined is None else str(combined),
                    signed_formula_from_printed_angle=(
                        None
                        if literal is None
                        else str(
                            sign * value_from_clauses(aspector, printed_angle, primary)
                        )
                    ),
                    difference=(
                        None if combined is None else str(combined - sign * expected)
                    ),
                    blank_agrees_with_zero=expected == 0 if raw is None else None,
                    angle_blank_domain_ok=(
                        (x < 30 or x >= 300) if literal is None else None
                    ),
                )
            )
        printed_sum = sum(
            (
                sum((Decimal(v) for v in terms), Decimal(0))
                for terms in primary["example54_signed_contributions_target_rows"][ti]
                if terms is not None
            ),
            Decimal(0),
        )
        relation(
            "example54_sum_of_literal_terms",
            target,
            printed_sum,
            primary["example54_signed_net"][ti],
        )
        relation(
            "example54_to55_net",
            target,
            Decimal(primary["example54_signed_net"][ti]),
            primary["example55_signed_net"][ti],
        )
        quarter = Decimal(primary["example55_signed_net"][ti]) / 4
        relation(
            "example55_exact_quarter",
            target,
            quarter,
            primary["example55_signed_drik"][ti],
        )
        for label, rounding in (
            ("half_up", ROUND_HALF_UP),
            ("toward_zero", ROUND_DOWN),
        ):
            relation(
                "example55_quarter_" + label,
                target,
                quarter.quantize(Decimal(".01"), rounding=rounding),
                primary["example55_signed_drik"][ti],
            )
        relation(
            "example55_to56_drik",
            target,
            Decimal(primary["example55_signed_drik"][ti]),
            primary["example56_signed_drik"][ti],
        )
    return dict(
        source=primary["source"],
        status="source_internal_conflicts_not_adjudicated",
        angle_relations=angles,
        angle_conflicts=[x for x in angles if not x["equal"]],
        matrix_slots=cells,
        matrix_slots_count=len(cells),
        literal_angle_cells=len(angles),
        blank_angle_cells=49 - len(angles),
        literal_signed_cells=sum(x["printed_terms"] is not None for x in cells),
        literal_signed_term_relations=terms,
        decimal_relations=decimal,
        decimal_conflicts=[x for x in decimal if not x["equal"]],
        cross_witness=dict(
            earlier_mercury_given_sign=natures["Mercury"],
            later_mercury_given_sign=later["nature_witness"]["standard_example"][
                "Mercury"
            ],
            all_seven_heading_inputs_differ=all(
                a != b
                for a, b in zip(
                    primary["example53_headers_degrees_minutes"],
                    later["example53_header_degrees_minutes"],
                )
            ),
            earlier_orientation="target_rows_aspector_columns",
            later_orientation="aspector_rows_target_columns",
            generic_mercury_association_adjudicated=False,
            witnesses_must_not_be_spliced=True,
        ),
        rounding_scope="Exact differences remain. Half-up and toward-zero display probes are separate comparisons, neither a source correction nor an author-wide rounding policy.",
        complete_single_original_accepted=False,
        production_activation_eligible=False,
        independent_real_event_cases=0,
        independent_model_blind_reviews=0,
        whole_goal_complete=False,
        scope="Given printed operands only, not astronomical validation, independent births or real-world events. Counts are related comparisons, not independent mistakes.",
    )


def compare_native(primary: dict) -> dict:
    # The source/numeric report is built before this optional native import.
    from fatebridge.core import jyotish_balas

    inputs = [float(x) for x in given_inputs(primary)]
    binary = [Fraction(x) for x in inputs]
    body = jyotish_balas.aspect_strength(dict(zip(PLANETS, inputs)))
    natures = primary["nature_witness"]["signed_example_columns"]
    key = f'moon_{natures["Moon"]}__mercury_{natures["Mercury"]}'
    native = body["scenarios"][key]
    scalar, sums, contributions = [], [], []
    for ti, target in enumerate(PLANETS):
        exact_terms = []
        conversion_bound = Fraction(0)
        for ai, aspector in enumerate(PLANETS):
            exact = value_from_clauses(
                aspector, (binary[ti] - binary[ai]) % 360, primary
            )
            value = body["matrix"][aspector][target]
            scalar.append(
                dict(
                    target=target,
                    aspector=aspector,
                    native=value,
                    independent_exact_binary_input_value=str(exact),
                    equal=type(value) is float and value == float(exact),
                )
            )
            sign = 1 if natures[aspector] == "benefic" else -1
            exact_terms.append(sign * exact / 4)
            signed_value = native["contributions"][target][aspector]
            contributions.append(
                dict(
                    target=target,
                    aspector=aspector,
                    independent_exact_signed_quarter=str(sign * exact / 4),
                    native=signed_value,
                    equal=type(signed_value) is float
                    and signed_value == float(sign * exact / 4),
                )
            )
            conversion_bound += Fraction(math.ulp(float(exact))) / 8
        expected = sum(exact_terms, Fraction(0))
        magnitude = sum(map(abs, exact_terms), Fraction(0))
        addition_bound = Fraction(7, 2) * Fraction(math.ulp(float(magnitude)))
        bound = conversion_bound + addition_bound
        value = native["summary"][target]
        error = Fraction(value) - expected
        sums.append(
            dict(
                target=target,
                independent_exact_binary_input_quarter_sum=str(expected),
                native=value,
                difference=str(error),
                fixed_roundoff_bound=str(bound),
                within_roundoff_bound=type(value) is float and abs(error) <= bound,
            )
        )
    return dict(
        native_source_sha256=hashlib.sha256(
            Path(jyotish_balas.__file__).read_bytes()
        ).hexdigest(),
        scalar_relations=scalar,
        scalar_exact_float_conflicts=[x for x in scalar if not x["equal"]],
        given_nature_branch=key,
        given_natures_match=native["natures"] == natures,
        contribution_relations=contributions,
        contribution_exact_float_conflicts=[x for x in contributions if not x["equal"]],
        sum_relations=sums,
        sum_roundoff_conflicts=[x for x in sums if not x["within_roundoff_bound"]],
        arbitrary_mercury_nature_selected=False,
        scope="49given-input formula checks with exact binary operands; seven given-nature sums use the predeclared floating roundoff bound. Neither changes a printed relation or validates astronomical inputs.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--native", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sources = [
        root / "tests/fixtures/jyotish-raman-1942-drik-primary.json",
        root / "tests/fixtures/jyotish-drik-primary.json",
    ]
    if args.report.exists() or args.report.resolve() in {p.resolve() for p in sources}:
        parser.error(
            "Report must be new; frozen references and earlier reports cannot be overwritten"
        )
    raw = [p.read_bytes() for p in sources]
    primary, later = [json.loads(x) for x in raw]
    report = build_report(primary, later)
    report["fixture_sha256s"] = [hashlib.sha256(x).hexdigest() for x in raw]
    if args.native:
        report["native_comparison"] = compare_native(primary)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                status=report["status"],
                matrix_slots=49,
                printed_angles=report["literal_angle_cells"],
                angle_conflicts=len(report["angle_conflicts"]),
                decimal_comparisons=len(report["decimal_relations"]),
                decimal_conflicts=len(report["decimal_conflicts"]),
                complete_single_original_accepted=False,
            )
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
