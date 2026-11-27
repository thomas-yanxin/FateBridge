"""Literal classical-source index comparison; never reconstruct a birth datetime."""

from __future__ import annotations

from typing import Any

from fatebridge.core.bazi.sources import (
    compare_registered_annotations,
    input_consistency,
    pillar_values,
)
from fatebridge.core.bazi.strength import analyze_elements_and_structure
from fatebridge.utils.errors import calculation_guard
from fatebridge.utils.formatting import create_pillar_dict


@calculation_guard("原典四柱核对")
def calculate_bazi_source_compare(
    year_pillar: str, month_pillar: str, day_pillar: str, hour_pillar: str
) -> dict[str, Any]:
    values = pillar_values(
        {"pillars": [year_pillar, month_pillar, day_pillar, hour_pillar]}
    )
    pillars = {
        p: (s[0], s[1]) for p, s in zip(("year", "month", "day", "hour"), values)
    }
    analysis = analyze_elements_and_structure(pillars)
    strength_level = analysis["day_master"]["strength"]
    comparison = compare_registered_annotations(pillars, strength_level)
    return {
        "analysis_type": "原典字面四柱与当前模型核对",
        "four_pillars": create_pillar_dict(pillars),
        "analysis_context": {
            **input_consistency(values),
            "input_kind": "literal_four_pillars",
            "birth_datetime_reconstructed": False,
        },
        "current_calculation": {
            "strength_level": strength_level,
            "day_master": analysis["day_master"],
            "favorable_elements": analysis["favorable_elements"],
            "dominant_structure": analysis["structure_profile"]["dominant_structure"],
        },
        "source_comparison": comparison,
    }
