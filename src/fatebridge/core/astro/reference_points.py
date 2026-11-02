"""Describe the point actually represented by standard native coordinates.

Swiss general documentation 2.4 distinguishes planetary system barycenters
from centers of body. No CENTER_BODY flag is requested by the sky engine.
Approximate or unidentified models must not inherit a native point claim.
"""

from typing import Any, Dict, List

from fatebridge.core.astro.profiles import ANALYTICAL_MEAN_NODE_MODEL

BODY_CENTERS = frozenset({"Sun", "Moon", "Mercury", "Venus"})
SYSTEM_BARYCENTERS = frozenset(
    {"Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"}
)
NATIVE_MODELS = frozenset({"swieph", "moshier", "jpl"})


def ephemeris_reference_points(
    planetary_models: Dict[str, str], derived_points: List[str]
) -> Dict[str, Any]:
    groups: Dict[str, List[str]] = {
        "body_centers": [],
        "system_barycenters": [],
        "theoretical_points": [],
        "approximate_points": [],
        "unresolved_points": [],
    }
    for name, model in planetary_models.items():
        if model == "fatebridge_approximate_orbital_model":
            key = "approximate_points"
        elif name == "North Node" and model == ANALYTICAL_MEAN_NODE_MODEL:
            key = "theoretical_points"
        elif model not in NATIVE_MODELS:
            key = "unresolved_points"
        elif name in BODY_CENTERS:
            key = "body_centers"
        elif name in SYSTEM_BARYCENTERS:
            key = "system_barycenters"
        elif name == "North Node":
            key = "theoretical_points"
        else:
            key = "unresolved_points"
        groups[key].append(name)
    notes = []
    if groups["system_barycenters"]:
        notes.append(
            "原生系统质心："
            + "、".join(groups["system_barycenters"])
            + "；未应用这些行星的本体中心修正。"
        )
    if groups["body_centers"]:
        notes.append("原生本体中心：" + "、".join(groups["body_centers"]) + "。")
    if groups["approximate_points"]:
        notes.append(
            "近似参考点："
            + "、".join(groups["approximate_points"])
            + "；该近似不解析本体中心与系统质心的差异。"
        )
    if groups["unresolved_points"]:
        notes.append("参考点未确认：" + "、".join(groups["unresolved_points"]) + "。")
    return {
        "policy_id": "fatebridge_ephemeris_reference_points_v1",
        **groups,
        "derived_points": list(derived_points),
        "center_body_correction_applied": False,
        "source_url": "https://www.astro.com/swisseph/swisseph.htm",
        "source_section": "2.4",
        "note_zh": "".join(notes),
        "scope": "Geocentric reference-point identity; not absolute accuracy certification. Derived points inherit their source-coordinate limitations.",
    }
