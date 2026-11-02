"""Compare every literal source interval with the previously declared rates."""

from __future__ import annotations

from fractions import Fraction as F
from typing import Any

from fatebridge.core.guolao_ruler_calendar import ruler_calendar_scale
from fatebridge.core.guolao_ruler_printed_table import (
    GROUPS,
    PALACES,
    PROFILE,
    load_printed_limit_table,
)


def audit_printed_limit_table() -> dict[str, Any]:
    table = load_printed_limit_table(PROFILE)
    literal = table.audit()
    comparisons = []
    for group, palaces in zip(GROUPS, PALACES):
        scale = ruler_calendar_scale(palaces[0])
        for cell in table.rows[group]:
            formula = scale.cell_interval(cell.column)
            start_difference = cell.start.elapsed_days - F(
                formula["interval_start_nominal_days_exact"]
            )
            end_difference = cell.end_exclusive_days - F(
                formula["interval_end_nominal_days_exact"]
            )
            comparisons.append(
                {
                    "group": group,
                    "column": cell.column,
                    "literal": cell.as_dict(),
                    "existing_declared_rate_formula": formula,
                    "literal_minus_formula_start_nominal_days_exact": str(
                        start_difference
                    ),
                    "literal_minus_formula_end_exclusive_nominal_days_exact": str(
                        end_difference
                    ),
                    "endpoints_agree": start_difference == end_difference == 0,
                    "formula_or_literal_changed_to_obtain_agreement": False,
                }
            )
    return {
        "profile_id": PROFILE,
        "source": literal["source"],
        "reference_data_sha256": table.fingerprint,
        "literal_table": literal,
        "complete_comparisons": len(comparisons),
        "equal_endpoint_cells": sum(c["endpoints_agree"] for c in comparisons),
        "different_endpoint_cells": sum(not c["endpoints_agree"] for c in comparisons),
        "all_literal_ranges_retained": True,
        "rate_formula_replaced_by_table": False,
        "full_birth_limit_schedule_accepted": False,
        "modern_calendar_mapping_accepted": False,
        "real_world_predictive_efficacy_established": False,
        "comparisons": comparisons,
    }
