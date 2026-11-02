"""Literal source-study interface; never reconstruct a person's birth record."""

from typing import Any, Dict

from fatebridge.core.branch_candidates import build_branch_combination_candidates
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.energy_provenance import build_energy_provenance
from fatebridge.core.source_annotations import (
    annotation_comparison_summary,
    compare_registered_annotations,
)
from fatebridge.utils.data import STEM_ELEMENTS
from fatebridge.utils.errors import calculation_guard
from fatebridge.utils.formatting import create_pillar_dict
from fatebridge.validation.bazi_source_corpus import input_consistency, pillar_values


@calculation_guard("原典四柱核对")
def calculate_bazi_source_compare(
    year_pillar: str, month_pillar: str, day_pillar: str, hour_pillar: str
) -> Dict[str, Any]:
    values = pillar_values(
        {"pillars": [year_pillar, month_pillar, day_pillar, hour_pillar]}
    )
    pillars = {
        p: (s[0], s[1]) for p, s in zip(("year", "month", "day", "hour"), values)
    }
    current = ElementAnalysis.analyze_day_master_strength(pillars)
    comparison = compare_registered_annotations(pillars, current["strength_level"])
    return {
        "analysis_type": "原典字面四柱与当前模型核对",
        "four_pillars": create_pillar_dict(pillars),
        "input_context": {
            **input_consistency(values),
            "input_kind": "literal_four_pillars",
            "birth_datetime_reconstructed": False,
            "calendar_accuracy_assessed": False,
        },
        "current_calculation": {
            "strength_level": current["strength_level"],
            "method_id": current["assessment"]["method_id"],
            "assessment": current["assessment"],
            "energy_provenance": build_energy_provenance(
                current["assessment"], STEM_ELEMENTS[pillars["day"][0]][0].value
            ),
            "branch_combination_candidates": build_branch_combination_candidates(
                pillars, current["assessment"]
            ),
            "calculation_overridden": False,
        },
        "source_comparison": comparison,
        "summary": annotation_comparison_summary(comparison),
    }
