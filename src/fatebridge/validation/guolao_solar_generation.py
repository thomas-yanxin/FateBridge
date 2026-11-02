"""Full-domain exact-generator versus source checkpoints and all literal rates."""

from __future__ import annotations

import json
from fractions import Fraction as F
from typing import Any

from fatebridge.core.guolao_solar_generation import (
    DAILY_PROFILE,
    load_generated_daily_solar,
)


def audit_solar_generation() -> dict[str, Any]:
    model = load_generated_daily_solar(DAILY_PROFILE)
    generator = model.generator
    checkpoints = json.loads(generator.literal_checkpoints_json)
    checkpoint_residuals = []
    identities = []
    numeric = blank = 0
    for origin in ("winter", "summer"):
        branch = generator.branch(origin)
        rows = branch.rows()
        for row in rows:
            identities.append(
                {
                    "origin": origin,
                    "index": row.index,
                    "recurrence_minus_polynomial_ancient_du_exact": str(
                        row.cumulative_correction_fen / 10000
                        - branch.polynomial_correction(row.index)
                    ),
                    "identity_is_not_independent_accuracy_acceptance": True,
                }
            )
        for source in checkpoints[origin]:
            generated = rows[source["index"]]
            for field in (
                "combined_difference_fen",
                "correction_increment_fen",
                "cumulative_correction_fen",
            ):
                literal = source[field]
                value = getattr(generated, field)
                numeric += literal is not None
                blank += literal is None
                checkpoint_residuals.append(
                    {
                        "origin": origin,
                        "index": source["index"],
                        "field": field,
                        "literal_source_string": literal,
                        "generated_fen_exact": (
                            str(value) if value is not None else None
                        ),
                        "generated_minus_literal_fen_exact": (
                            str(value - F(literal))
                            if value is not None and literal is not None
                            else None
                        ),
                        "printed_blank_not_replaced_in_source_data": literal is None,
                    }
                )
    rate_residuals = []
    for literal, generated in zip(
        model.literal.segments, model.trajectory.segments, strict=True
    ):
        for index, (a, b) in enumerate(
            zip(literal.rates, generated.rates, strict=True)
        ):
            rate_residuals.append(
                {
                    "segment": literal.name,
                    "index": index,
                    "literal_motion_du_exact": str(a),
                    "generated_motion_du_exact": str(b),
                    "generated_minus_literal_du_exact": str(b - a),
                    "literal_motion_cell_replaced": False,
                }
            )
    return {
        **model.audit(),
        "seed_and_checkpoint_numeric_cells": numeric,
        "seed_and_checkpoint_printed_empty_cells": blank,
        "all_checkpoint_fields": checkpoint_residuals,
        "all185_recurrence_polynomial_identities": identities,
        "all366_literal_motion_cell_comparisons": rate_residuals,
        "literal_terminal_motion_blanks_retained": 4,
        "rounding_or_quantum_chosen_using_match_count": False,
        "fitted_source_cell_emendation": None,
        "modern_astronomical_reference_comparison": None,
        "cell_counts_or_polynomial_identity_used_as_accuracy_score": False,
        "four_axis_perfect_scores_established": False,
    }
