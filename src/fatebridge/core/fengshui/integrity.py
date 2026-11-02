"""Reject contradictory natal plates before their numbers inform interpretation.

These are engineering invariants of the selected nine-star flight calculation.
They do not certify source conformity, input selection or predictive efficacy.
"""

from typing import Any, Dict

from fatebridge.utils.errors import FengshuiCalculationError

FLIGHT_PATH = ("C", "NW", "W", "NE", "S", "N", "SW", "E", "SE")
PALACE_NUMBERS = dict(zip(FLIGHT_PATH, (5, 6, 7, 8, 9, 1, 2, 3, 4)))
ROLES = ("period", "mountain", "facing")


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise FengshuiCalculationError(reason)


def validate_natal_chart(
    chart: Dict[str, Any],
    *,
    period: int,
    facing: Dict[str, Any],
    sitting: Dict[str, Any],
    mode: str,
) -> None:
    """Check identity, all representations, flight order and trace agreement.

    The expected identity comes from this call's selector, never from the chart
    under test or a printed diagram. Source differences therefore remain valid
    results, while a numerically contradictory candidate stops the calculation.
    """
    try:
        _require(
            type(chart["period_number"]) is int
            and chart["period_number"] == period
            and chart["facing"] == facing
            and chart["sitting"] == sitting
            and chart["chart_mode"] == mode
            and chart["candidate_id"]
            == f"{period}:{sitting['name']}-{facing['name']}:{mode}",
            "natal_identity_mismatch",
        )
        _require(
            tuple(chart["flight_path"]) == FLIGHT_PATH
            and set(chart["palaces"]) == set(FLIGHT_PATH),
            "natal_plate_inconsistent",
        )
        palaces = chart["palaces"]
        for direction in FLIGHT_PATH:
            _require(
                palaces[direction]["direction"] == direction
                and type(palaces[direction]["palace_number"]) is int
                and palaces[direction]["palace_number"] == PALACE_NUMBERS[direction],
                "natal_plate_inconsistent",
            )
        for role in ROLES:
            numbers = chart[role + "_chart"]
            _require(
                set(numbers) == set(FLIGHT_PATH)
                and all(type(numbers[d]) is int for d in FLIGHT_PATH)
                and sorted(numbers.values()) == list(range(1, 10))
                and all(
                    type(palaces[d][role + "_star_number"]) is int
                    and palaces[d][role + "_star_number"] == numbers[d]
                    for d in FLIGHT_PATH
                ),
                "natal_plate_inconsistent",
            )
            center, step = period, 1
            if role != "period":
                trace = chart["trace"][role]
                center = trace["center_star_number"]
                seed = trace["seed_star_number"]
                physical = sitting if role == "mountain" else facing
                _require(
                    type(seed) is int
                    and seed == chart["period_chart"][physical["direction"]]
                    and type(center) is int
                    and 1 <= center <= 9
                    and trace["polarity"] in ("yang", "yin")
                    and trace["flight"]
                    == ("forward" if trace["polarity"] == "yang" else "reverse")
                    and type(trace["replacement_applied"]) is bool
                    and trace["replacement_applied"] == (center != seed)
                    and (mode != "lower" or center == seed),
                    "natal_trace_inconsistent",
                )
                step = 1 if trace["flight"] == "forward" else -1
            _require(
                all(
                    numbers[direction] == (center - 1 + step * index) % 9 + 1
                    for index, direction in enumerate(FLIGHT_PATH)
                ),
                "natal_plate_inconsistent",
            )
    except (KeyError, TypeError, AttributeError) as exc:
        raise FengshuiCalculationError("natal_plate_inconsistent") from exc
