"""Descriptive audit of literal Gujin daily rates and worked cumulative values."""

from __future__ import annotations

import json
from fractions import Fraction as F
from typing import Any

from fatebridge.core.guolao_daily_solar import DATA, PROFILE, load_daily_solar


def audit_daily_solar() -> dict[str, Any]:
    model = load_daily_solar(PROFILE)
    raw = json.loads(DATA.read_bytes())
    reverse = []
    for forward_index, reverse_index in [(0, 3), (2, 1)]:
        a, b = model.segments[forward_index], model.segments[reverse_index]
        for i, (expected, literal) in enumerate(
            zip(reversed(a.rates), b.rates, strict=True)
        ):
            if expected != literal:
                reverse.append(
                    {
                        "forward_table": a.name,
                        "forward_index": len(a.rates) - 1 - i,
                        "reverse_table": b.name,
                        "reverse_index": i,
                        "forward_literal_du_exact": str(expected),
                        "reverse_literal_du_exact": str(literal),
                        "reverse_minus_forward_du_exact": str(literal - expected),
                        "reverse_value_replaced": False,
                    }
                )
    nodes = []
    witness = raw["worked_cumulative_comparison_witness"]
    for s in model.segments:
        for index, printed in witness["nodes"][s.name].items():
            calculated = s.cumulative(int(index))
            nodes.append(
                {
                    "segment": s.name,
                    "day_offset": int(index),
                    "literal_rate_sum_du_exact": str(calculated),
                    "separately_printed_worked_cumulative_du_exact": str(F(printed)),
                    "rate_sum_minus_worked_cumulative_du_exact": str(
                        calculated - F(printed)
                    ),
                }
            )
    return {
        **model.audit(),
        "forward_reverse_literal_differences": reverse,
        "worked_cumulative_comparison": {**witness, "residuals": nodes},
        "source_witness_differences": raw["source_witness_differences"],
        "source_subtraction_components": raw["source_subtraction_components"],
        "midnight_anchor_policy": raw["midnight_anchor_policy"],
        "earlier_autumn_midnight_short_value_du_exact": str(
            F(raw["printed_earlier_autumn_midnight_du"])
        ),
        "source_rate_repair_or_fitted_tolerance": None,
        "modern_astronomical_comparison": None,
        "four_axis_perfect_scores_established": False,
    }
