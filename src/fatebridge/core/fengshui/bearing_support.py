"""Propagate a supplied closed bearing interval without inventing probabilities."""

from fractions import Fraction
from typing import Any, Dict, List

from .directions import rule_data, sitting_from_facing


def sitting_support(
    degrees: float, radius: float, north_reference: str
) -> List[Dict[str, Any]]:
    """Enumerate every intersecting eight-sector cell using exact input values.

    A zero radius retains the existing left-closed/right-open point convention.
    Positive radii use closed intersections, including a touched endpoint. This
    is an engineering interval policy, not a classical measurement theorem or
    a conversion of WMM standard deviations into guaranteed error bounds.
    """
    directions = list(rule_data("directions"))
    if radius == 0:
        sitting = sitting_from_facing(degrees, north_reference)
        return [
            {
                "sitting_direction": sitting["direction"],
                "sitting_trigram": sitting["trigram"],
                "regions": [],
            }
        ]
    center = Fraction(degrees) % 360
    lower, upper = center - Fraction(radius), center + Fraction(radius)
    found: Dict[str, Dict[str, Any]] = {}
    for index in range(-4, 13):
        start = max(lower, index * 45 - Fraction(45, 2))
        end = min(upper, index * 45 + Fraction(45, 2))
        if start > end:
            continue
        direction = directions[(index + 4) % 8]
        candidate = found.setdefault(
            direction,
            {
                "sitting_direction": direction,
                "sitting_trigram": rule_data("directions")[direction]["trigram"],
                "regions": [],
            },
        )
        candidate["regions"].append(
            {
                "from_facing_degrees_exact": str(start),
                "until_facing_degrees_exact": str(end),
                "endpoints_included": True,
            }
        )
    return list(found.values())
