"""Four source-bound Variable arrows derived from actual activation Tones.

These are Human Design notation, not a cognitive, dietary or clinical finding.
An inconsistent or missing opposition pair must not acquire an invented code.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core.human_design_personality_color import personality_colors

VARIABLE_SOURCES = [
    "https://jovianarchive.com/blogs/deeper-mechanics-system-theory/a-simple-guide-to-variable",
    "https://jovianarchive.com/pages/the-basics-of-substructure-in-human-design",
    "https://jovianarchive.com/pages/get-your-human-design-chart",
]
COMPONENTS = (
    ("design_sun_earth", "design", ("Sun", "Earth"), "top_left"),
    ("design_nodes", "design", ("NorthNode", "SouthNode"), "bottom_left"),
    ("personality_sun_earth", "personality", ("Sun", "Earth"), "top_right"),
    ("personality_nodes", "personality", ("NorthNode", "SouthNode"), "bottom_right"),
)
NOTATION_ORDER = [
    "personality_sun_earth",
    "personality_nodes",
    "design_sun_earth",
    "design_nodes",
]


def variables_from_activations(activations: dict[str, Any]) -> dict[str, Any]:
    arrows: list[dict[str, Any]] = []
    for component, side, pair, position in COMPONENTS:
        items = activations.get(side, [])
        matches = [
            [(i, a) for i, a in enumerate(items) if a.get("body") == body]
            for body in pair
        ]
        valid = all(
            len(found) == 1
            and type(found[0][1].get("tone")) is int
            and 1 <= found[0][1]["tone"] <= 6
            for found in matches
        )
        basis = (
            [
                {
                    "path": f"activations.{side}.{found[0][0]}.tone",
                    "value": found[0][1]["tone"],
                }
                for found in matches
            ]
            if valid
            else []
        )
        consistent = valid and basis[0]["value"] == basis[1]["value"]
        tone = basis[0]["value"] if consistent else None
        orientation = ("left" if tone <= 3 else "right") if tone is not None else None
        arrows.append(
            {
                "component": component,
                "side": side,
                "body_pair": list(pair),
                "position": position,
                "status": (
                    "computed"
                    if consistent
                    else "inconsistent_pair" if valid else "missing_or_invalid_pair"
                ),
                "tone": tone,
                "orientation": orientation,
                "letter": orientation[0].upper() if orientation else None,
                "pair_tones_consistent": bool(consistent),
                "basis": basis,
                "ephemeris_models": sorted(
                    {
                        found[0][1]["ephemeris_model"]
                        for found in matches
                        if len(found) == 1 and found[0][1].get("ephemeris_model")
                    }
                ),
            }
        )
    computed = all(a["status"] == "computed" for a in arrows)
    by_id = {a["component"]: a for a in arrows}
    letters = "".join(by_id[c]["letter"] for c in NOTATION_ORDER) if computed else None
    return {
        "status": "computed" if computed else "incomplete_or_inconsistent",
        "code": f"P{letters[:2]} D{letters[2:]}" if letters else None,
        "arrows": arrows,
        "personality_colors": personality_colors(activations),
        "notation_order": list(NOTATION_ORDER),
        "source_urls": list(VARIABLE_SOURCES),
        "subdivision_accuracy_certified": False,
        "scope": "所选名义盘的四组Tone数值汇总：1至3向左，4至6向右；P、D均先日地后交点。不同生时或后端的箭头不可拼接。数值可受生时、交点约定和星历影响；不认证认知、健康、饮食或学习能力。",
    }
