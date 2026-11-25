"""Fixed reference frame; no inferred floor-plan centre or north conversion."""

import json
from bisect import bisect_right
from copy import deepcopy
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, cast


@lru_cache(maxsize=1)
def _bundle() -> dict[str, Any]:
    path = Path(__file__).parents[2] / "data" / "fengshui" / "rules-v1.json"
    return cast(Dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def rule_data(key: str) -> Any:
    """Never expose the cached mutable registry to a caller."""
    return deepcopy(_bundle()[key])


def provenance(ruleset_id: str) -> dict[str, Any]:
    rules = rule_data("rulesets")
    selected = {"ruleset_id": ruleset_id, **rules[ruleset_id]}
    sources = rule_data("sources")
    selected["sources"] = [
        dict(source_id=s, **sources[s]) for s in selected["source_ids"]
    ]
    selected["bundle_version"] = _bundle()["bundle_version"]
    return selected


def wrap9(number: int) -> int:
    return (number - 1) % 9 + 1


def bearing_context(degrees: float | Fraction, north_reference: str) -> dict[str, Any]:
    angle = degrees % 360
    index = bisect_right([22.5 + 45 * i for i in range(8)], angle) % 8
    direction = list(_bundle()["directions"])[index]
    mountain_index = bisect_right([7.5 + 15 * i for i in range(24)], angle) % 24
    return {
        "bearing_degrees": float(angle) % 360,
        "north_reference": north_reference,
        "direction": direction,
        "trigram": _bundle()["directions"][direction]["trigram"],
        "mountain": _bundle()["mountains"][mountain_index],
        "boundary_policy": "left_closed_right_open",
        "rule_id": "houtian_directions_v1.angular_sectors",
        "source_ids": ["S4"],
    }


def sitting_from_facing(degrees: float, north_reference: str) -> dict[str, Any]:
    # Derive opposite sectors before adding 180, which can erase the final ULP
    # of a precise facing bearing close to a dividing line.
    facing = bearing_context(degrees, north_reference)
    directions = list(_bundle()["directions"])
    direction = directions[(directions.index(facing["direction"]) + 4) % 8]
    mountains = _bundle()["mountains"]
    index = mountains.index(facing["mountain"])
    return {
        **facing,
        "bearing_degrees": (degrees + 180) % 360,
        "direction": direction,
        "trigram": _bundle()["directions"][direction]["trigram"],
        "mountain": deepcopy(mountains[(index + 12) % 24]),
    }
