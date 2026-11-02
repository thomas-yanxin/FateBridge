"""Source-bounded numeric structures of a natal chart, without fortune verdicts.

The reference period is the chart's historical period. A current period, annual
star or observed external form must never alter these geometric facts.
"""

from itertools import combinations
from typing import Any, Dict

from .numeric_patterns import numeric_patterns


def natal_structure(chart: Dict[str, Any]) -> Dict[str, Any]:
    period = chart["period_number"]
    sitting = chart["sitting"]["direction"]
    facing = chart["facing"]["direction"]
    mountain_at = next(d for d, n in chart["mountain_chart"].items() if n == period)
    facing_at = next(d for d, n in chart["facing_chart"].items() if n == period)
    labels = {
        (sitting, facing): ("at_sitting_and_facing", "到山到向"),
        (facing, sitting): ("reversed_sitting_and_facing", "上山下水"),
        (sitting, sitting): ("both_at_sitting", "双星到坐"),
        (facing, facing): ("both_at_facing", "双星到向"),
    }
    code, label = labels.get((mountain_at, facing_at), ("other", "其他星位结构"))
    ten = []
    for left, right in combinations(("period", "mountain", "facing"), 2):
        sums = {
            d: chart[f"{left}_chart"][d] + chart[f"{right}_chart"][d]
            for d in chart["flight_path"]
        }
        ten.append(
            {
                "left_role": left,
                "right_role": right,
                "palace_sums": sums,
                "all_nine_sum_to_ten": all(n == 10 for n in sums.values()),
            }
        )
    return {
        "rule_id": "xuankong_zhongzhou_v1.natal_numeric_structure",
        "source_ids": ["X1", "X10", "X11", "X12"],
        "reference_period_number": period,
        "period_scope": "historical_natal_period_not_current_timeliness",
        "distribution": {
            "code": code,
            "traditional_label": label,
            "sitting_direction": sitting,
            "facing_direction": facing,
            "mountain_period_star_direction": mountain_at,
            "facing_period_star_direction": facing_at,
        },
        "combination_of_ten": ten,
        "classical_patterns": numeric_patterns(chart),
        "interpretation_scope": "numeric_structure_only_not_external_form_or_fortune",
    }
