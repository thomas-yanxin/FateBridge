"""JinSuo YuGuan 8-palace and 24-mountain sand/water polarity classification."""

from __future__ import annotations

from typing import Any

from fatebridge.core.fengshui.directions import MOUNTAINS_24, raw_rule_data
from fatebridge.core.fengshui.models import JinsuoRequest


def _palace_preference(palace_number: int) -> str:
    return "sand" if palace_number in {1, 2, 3, 4} else "water"


def jinsuo_24_mountains() -> dict[str, Any]:
    """Build the 24-mountain sand/water polarity table anchored to Houtian palaces."""
    directions = raw_rule_data("directions")
    table: dict[str, Any] = {}
    for m in MOUNTAINS_24:
        palace = directions[m["direction"]]
        pref = _palace_preference(palace["palace_number"])
        table[m["name"]] = {
            "mountain": m["name"],
            "direction": m["direction"],
            "palace_number": palace["palace_number"],
            "trigram": palace["trigram"],
            "yuan": m["yuan"],
            "polarity": m["polarity"],
            "preferred_classification": pref,
            "avoid_classification": "water" if pref == "sand" else "sand",
        }
    return table


def jinsuo(req: JinsuoRequest) -> dict[str, Any]:
    directions = raw_rule_data("directions")
    preferences = {
        d: {
            "direction": d,
            "trigram": info["trigram"],
            "palace_number": info["palace_number"],
            "element": info["element"],
            "preferred_classification": _palace_preference(info["palace_number"]),
        }
        for d, info in directions.items()
    }
    mountains_24 = jinsuo_24_mountains()
    missing = [] if req.features else ["confirmed_environment_features"]
    findings = []
    for feature in req.features:
        known = feature.classification in {"sand", "water"}
        if not known:
            missing.append(
                f"features.{feature.object_id}.single_confirmed_classification"
            )
        assert feature.direction is not None
        if feature.mountain is not None:
            preference = mountains_24[feature.mountain]["preferred_classification"]
        else:
            preference = preferences[feature.direction]["preferred_classification"]
        findings.append(
            {
                **feature.model_dump(),
                "method": "jinsuo",
                "preferred_classification": preference,
                "finding": (
                    (
                        "matches_preference"
                        if feature.classification == preference
                        else "opposes_preference"
                    )
                    if known
                    else "undetermined"
                ),
            }
        )
    return {
        "status": "partial" if missing else "complete",
        "preferences": preferences,
        "twenty_four_mountains": {
            name: {
                "direction": row["direction"],
                "preferred_classification": row["preferred_classification"],
                "polarity": row["polarity"],
            }
            for name, row in mountains_24.items()
        },
        "feature_findings": findings,
        "missing_inputs": missing,
    }
