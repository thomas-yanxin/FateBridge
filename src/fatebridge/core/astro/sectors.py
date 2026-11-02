"""FateBridge's 13 equal ascendant-relative sectors, not IAU constellations."""

import math
from fractions import Fraction
from typing import Any, Dict, List

from fatebridge.core.astro.geometry import _sign_name


def _display_degree(value: Fraction) -> float:
    # Keep the displayed value in the same sign as the exact geometric edge.
    display = float(value)
    return math.nextafter(display, -math.inf) if Fraction(display) > value else display


def thirteen_sectors(ascendant: float) -> List[Dict[str, Any]]:
    anchor = Fraction(ascendant) % 360
    width = Fraction(360, 13)
    return [
        {
            "sector": number + 1,
            "cusp_longitude": _display_degree((anchor + number * width) % 360),
            "end_longitude": _display_degree((anchor + (number + 1) * width) % 360),
            "width_degrees": float(width),
            "sign": _sign_name(_display_degree((anchor + number * width) % 360)),
        }
        for number in range(13)
    ]


def sector_profile(ascendant: float) -> Dict[str, Any]:
    return {
        "ruleset_id": "fatebridge_equal13_v1",
        "author": "FateBridge",
        "version": "1",
        "anchor": "ascendant",
        "anchor_longitude": ascendant,
        "sector_count": 13,
        "width_degrees": float(Fraction(360, 13)),
        "interval_convention": "[start,end) along the zodiac; exact rational partition of input floats",
        "boundary_display": "edge floats are approximations; exact boundaries are ascendant + n*360/13",
        "coordinate_system": "same longitude frame as chart_profile; independent of the selected 12-house division",
        "astronomical_constellations": False,
        "original_text_conformance": "not_applicable_to_custom_partition",
        "real_world_efficacy": "not_tested",
        "sources": [
            {
                "id": "iau_constellations",
                "author": "International Astronomical Union",
                "url": "https://iauarchive.eso.org/public/faq/",
                "scope": "Constellation boundaries have unequal widths; this custom partition does not implement them",
            }
        ],
    }
