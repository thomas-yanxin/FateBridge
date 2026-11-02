"""Check derived numeric assertions against raw stars, independently of builders.

Only the existing selected numeric profile is checked. This is not an oracle
for its historical interpretation, author terminology or real-world efficacy.
"""

from itertools import combinations
from typing import Any

from fatebridge.utils.errors import FengshuiCalculationError

from .integrity import FLIGHT_PATH, PALACE_NUMBERS, ROLES

OUTER = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
PARENTAL = ([1, 4, 7], [2, 5, 8], [3, 6, 9])


def _require(condition: bool) -> None:
    if not condition:
        raise FengshuiCalculationError("natal_structure_inconsistent")


def _record(actual: Any, expected: Any) -> None:
    """Strict JSON types; metadata outside selected numeric fields is retained."""
    _require(type(actual) is type(expected))
    if isinstance(expected, dict):
        _require(set(expected).issubset(actual))
        for key, value in expected.items():
            _record(actual[key], value)
    elif isinstance(expected, list):
        _require(len(actual) == len(expected))
        for a, b in zip(actual, expected):
            _record(a, b)
    else:
        _require(actual == expected)


def validate_natal_structure(
    chart: dict[str, Any], *, include_opposite: bool = True
) -> None:
    """No calls to natal_structure, numeric_patterns or opposite_star_comparison.

    Version 1.1 fixed readings predate the opposite-palace branch; only that
    branch may be omitted by their archival verifier. Runtime checks it fully.
    """
    try:
        plates = {role: chart[role + "_chart"] for role in ROLES}
        for plate in plates.values():
            _require(set(plate) == set(FLIGHT_PATH))
            _require(all(type(v) is int for v in plate.values()))
            _require(sorted(plate.values()) == list(range(1, 10)))
        period = chart["period_number"]
        _require(type(period) is int and 1 <= period <= 9)
        _require(chart["chart_mode"] in {"lower", "replacement"})
        sitting, facing = chart["sitting"]["direction"], chart["facing"]["direction"]
        mountain_at = next(d for d in FLIGHT_PATH if plates["mountain"][d] == period)
        facing_at = next(d for d in FLIGHT_PATH if plates["facing"][d] == period)
        labels = {
            (sitting, facing): ("at_sitting_and_facing", "到山到向"),
            (facing, sitting): ("reversed_sitting_and_facing", "上山下水"),
            (sitting, sitting): ("both_at_sitting", "双星到坐"),
            (facing, facing): ("both_at_facing", "双星到向"),
        }
        code, label = labels.get((mountain_at, facing_at), ("other", "其他星位结构"))
        structure = chart["structure"]
        _record(
            structure,
            {
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
            },
        )
        sums = []
        for left, right in combinations(ROLES, 2):
            values = {d: plates[left][d] + plates[right][d] for d in FLIGHT_PATH}
            sums.append(
                {
                    "left_role": left,
                    "right_role": right,
                    "palace_sums": values,
                    "all_nine_sum_to_ten": all(v == 10 for v in values.values()),
                }
            )
        _record(structure["combination_of_ten"], sums)
        for pair in structure["combination_of_ten"]:
            _require(set(pair["palace_sums"]) == set(FLIGHT_PATH))
        patterns = structure["classical_patterns"]
        parental = {}
        for direction in FLIGHT_PATH:
            numbers = [plates[role][direction] for role in ROLES]
            group = next((g for g in PARENTAL if sorted(numbers) == g), None)
            parental[direction] = {
                "ordered_period_mountain_facing": numbers,
                "matched_group": group,
            }
        _record(
            patterns["parental_triples"],
            {
                "groups": list(PARENTAL),
                "palaces": parental,
                "all_nine_match": all(
                    v["matched_group"] is not None for v in parental.values()
                ),
            },
        )
        _require(set(patterns["parental_triples"]["palaces"]) == set(FLIGHT_PATH))
        comparisons = {}
        for role in ("mountain", "facing"):
            values = plates[role]
            comparisons[role] = {
                "same_ground_directions": [
                    d for d in FLIGHT_PATH if values[d] == PALACE_NUMBERS[d]
                ],
                "opposite_ground_directions": [
                    d
                    for d in FLIGHT_PATH
                    if d != "C" and values[d] + PALACE_NUMBERS[d] == 10
                ],
                "whole_ground_repeat": all(
                    values[d] == PALACE_NUMBERS[d] for d in FLIGHT_PATH
                ),
                "whole_ground_reverse": all(
                    values[d] + PALACE_NUMBERS[d] == 10 for d in FLIGHT_PATH
                ),
                "period_plate_same_directions": [
                    d for d in FLIGHT_PATH if values[d] == plates["period"][d]
                ],
                "whole_period_plate_same": values == plates["period"],
            }
        ground = patterns["ground_comparison"]
        _record(
            ground,
            {
                "reference_numbers": PALACE_NUMBERS,
                "opposite_reference_numbers": {
                    d: 10 - v for d, v in PALACE_NUMBERS.items()
                },
                "roles": comparisons,
                "period_overlap_is_separate_from_ground_label": True,
            },
        )
        for key in ("reference_numbers", "opposite_reference_numbers"):
            _require(set(ground[key]) == set(FLIGHT_PATH))
        _require(set(ground["roles"]) == {"mountain", "facing"})
        endpoints = {
            key: {
                "direction": d,
                "star_number": plates[role][d],
                "ground_number": PALACE_NUMBERS[d],
            }
            for key, role, d in (
                ("mountain_at_sitting", "mountain", sitting),
                ("facing_at_facing", "facing", facing),
            )
        }
        endpoint_opposite = all(
            v["star_number"] + v["ground_number"] == 10 for v in endpoints.values()
        )
        repeat = any(v["whole_ground_repeat"] for v in comparisons.values())
        lower = chart["chart_mode"] == "lower"
        named = patterns["volume_two_named_refrain"]
        _record(
            named,
            {
                "applicable": lower,
                "numeric_match": (repeat or endpoint_opposite) if lower else None,
                "whole_ground_repeat_present": repeat,
                "own_role_sitting_facing_both_opposite_ground": endpoint_opposite,
                "endpoint_evidence": endpoints,
            },
        )
        _require(set(named["endpoint_evidence"]) == set(endpoints))
        if include_opposite:
            pairs = {}
            for index, direction in enumerate(OUTER):
                opposite = OUTER[(index + 4) % 8]
                a, b = plates["mountain"][direction], plates["facing"][opposite]
                pairs[direction] = {
                    "mountain_direction": direction,
                    "facing_direction": opposite,
                    "mountain_star_number": a,
                    "facing_star_number": b,
                    "sum": a + b,
                    "matches_sum_to_ten": a + b == 10,
                }
            a, b = plates["mountain"]["C"], plates["facing"]["C"]
            comparison = patterns["opposite_star_comparison"]
            _record(
                comparison,
                {
                    "pairs": pairs,
                    "spatial_pair_count": 8,
                    "all_eight_sum_to_ten": all(
                        v["matches_sum_to_ten"] for v in pairs.values()
                    ),
                    "center_numeric_pair": {
                        "mountain_star_number": a,
                        "facing_star_number": b,
                        "sum": a + b,
                        "matches_sum_to_ten": a + b == 10,
                        "spatial_opposite_exists": False,
                        "included_in_spatial_conjunction": False,
                    },
                },
            )
            _require(set(comparison["pairs"]) == set(OUTER))
    except (KeyError, TypeError, AttributeError, StopIteration) as exc:
        raise FengshuiCalculationError("natal_structure_inconsistent") from exc
