"""Classical numeric comparisons keep reference plates and textual scopes distinct."""

from typing import Any, Dict

from .directions import rule_data
from .opposite import opposite_star_comparison

PARENTAL_GROUPS = ((1, 4, 7), (2, 5, 8), (3, 6, 9))


def numeric_patterns(chart: Dict[str, Any]) -> Dict[str, Any]:
    ground = {d: p["palace_number"] for d, p in rule_data("directions").items()}
    ground["C"] = 5
    directions = chart["flight_path"]
    if len(directions) != 9 or set(directions) != set(ground):
        raise ValueError("Numeric pattern comparison requires all nine unique palaces")
    for role in ("period", "mountain", "facing"):
        values = chart[f"{role}_chart"]
        if (
            set(values) != set(ground)
            or any(type(v) is not int for v in values.values())
            or sorted(values.values()) != list(range(1, 10))
        ):
            raise ValueError(
                "Every pattern plate must retain the complete integer stars1-9"
            )
    parental_palaces = {}
    for direction in directions:
        values = [
            chart[f"{role}_chart"][direction]
            for role in ("period", "mountain", "facing")
        ]
        group = next((g for g in PARENTAL_GROUPS if sorted(values) == list(g)), None)
        parental_palaces[direction] = {
            "ordered_period_mountain_facing": values,
            "matched_group": list(group) if group is not None else None,
        }
    comparisons = {}
    for role in ("mountain", "facing"):
        values = chart[f"{role}_chart"]
        comparisons[role] = {
            "same_ground_directions": [d for d in directions if values[d] == ground[d]],
            "opposite_ground_directions": [
                d for d in directions if d != "C" and values[d] == 10 - ground[d]
            ],
            "whole_ground_repeat": all(values[d] == ground[d] for d in directions),
            "whole_ground_reverse": all(
                values[d] == 10 - ground[d] for d in directions
            ),
            "period_plate_same_directions": [
                d for d in directions if values[d] == chart["period_chart"][d]
            ],
            "whole_period_plate_same": values == chart["period_chart"],
        }
    sitting, facing = chart["sitting"]["direction"], chart["facing"]["direction"]
    own_endpoints = {
        "mountain_at_sitting": {
            "direction": sitting,
            "star_number": chart["mountain_chart"][sitting],
            "ground_number": ground[sitting],
        },
        "facing_at_facing": {
            "direction": facing,
            "star_number": chart["facing_chart"][facing],
            "ground_number": ground[facing],
        },
    }
    opposite_endpoints = all(
        v["star_number"] + v["ground_number"] == 10 for v in own_endpoints.values()
    )
    full_repeat = any(v["whole_ground_repeat"] for v in comparisons.values())
    return {
        "rule_id": "xuankong_zhongzhou_v1.classical_numeric_patterns",
        "source_ids": ["X10", "X11", "X12"],
        "opposite_star_comparison": opposite_star_comparison(chart),
        "parental_triples": {
            "source_ids": ["X11"],
            "groups": [list(g) for g in PARENTAL_GROUPS],
            "palaces": parental_palaces,
            "all_nine_match": all(
                v["matched_group"] is not None for v in parental_palaces.values()
            ),
            "scope": "three_distinct_period_mountain_facing_stars_in_every_palace_not_ordinary_consecutive_triples",
        },
        "ground_comparison": {
            "source_ids": ["X10"],
            "reference_numbers": ground,
            "opposite_reference_numbers": {d: 10 - n for d, n in ground.items()},
            "roles": comparisons,
            "scope": "fixed_Luo_Shu_ground_plate_separate_from_historical_period_plate",
            "period_overlap_is_separate_from_ground_label": True,
        },
        "volume_two_named_refrain": {
            "applicable": chart["chart_mode"] == "lower",
            "numeric_match": (
                (full_repeat or opposite_endpoints)
                if chart["chart_mode"] == "lower"
                else None
            ),
            "whole_ground_repeat_present": full_repeat,
            "own_role_sitting_facing_both_opposite_ground": opposite_endpoints,
            "endpoint_evidence": own_endpoints,
            "scope": "numeric_correspondence_to_the_volume2_named_lower_chart_list_not_all_uses_of_fan_fu_terms",
        },
        "interpretation_scope": "numeric_relations_and_limited_textual_correspondence_not_auspiciousness_event_prediction_or_action_permission",
    }
