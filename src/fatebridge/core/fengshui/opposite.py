"""Directed mountain/facing comparisons across eight spatial opposite palaces.

The central palace has a numeric pair, never a spatial opposite. This is a
numeric relation illustrated by a printed example, not a complete fan-yin rule.
"""

from typing import Any

DIRECTIONS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
OPPOSITE = {
    direction: DIRECTIONS[(index + 4) % 8] for index, direction in enumerate(DIRECTIONS)
}


def opposite_star_comparison(chart: dict[str, Any]) -> dict[str, Any]:
    palaces = {*DIRECTIONS, "C"}
    if (
        len(chart["flight_path"]) != 9
        or set(chart["flight_path"]) != palaces
        or chart["chart_mode"] not in {"lower", "replacement"}
    ):
        raise ValueError("对宫比较须有九个不同宫位及已知宅盘模式")
    for role in ("mountain", "facing"):
        values = chart[role + "_chart"]
        if (
            set(values) != palaces
            or any(type(n) is not int for n in values.values())
            or sorted(values.values()) != list(range(1, 10))
        ):
            raise ValueError("对宫比较须保留两盘各自完整的一至九星")
    pairs = {}
    for direction in chart["flight_path"]:
        if direction == "C":
            continue
        opposite = OPPOSITE[direction]
        mountain = chart["mountain_chart"][direction]
        facing = chart["facing_chart"][opposite]
        total = mountain + facing
        pairs[direction] = {
            "mountain_direction": direction,
            "facing_direction": opposite,
            "mountain_star_number": mountain,
            "facing_star_number": facing,
            "sum": total,
            "matches_sum_to_ten": total == 10,
        }
    center_mountain = chart["mountain_chart"]["C"]
    center_facing = chart["facing_chart"]["C"]
    return {
        "rule_id": "xuankong_zhongzhou_v1.opposite_star_comparison",
        "source_ids": ["X12"],
        "pairs": pairs,
        "spatial_pair_count": 8,
        "all_eight_sum_to_ten": all(
            row["matches_sum_to_ten"] for row in pairs.values()
        ),
        "center_numeric_pair": {
            "mountain_star_number": center_mountain,
            "facing_star_number": center_facing,
            "sum": center_mountain + center_facing,
            "matches_sum_to_ten": center_mountain + center_facing == 10,
            "spatial_opposite_exists": False,
            "included_in_spatial_conjunction": False,
        },
        "scope": "directed_eight_palace_mountain_at_d_plus_facing_at_opposite_d_not_same_palace_or_complete_refrain_verdict",
        "replacement_scope": "numeric_relation_only_not_inheritance_of_printed_lower_example_or_fortune",
    }
