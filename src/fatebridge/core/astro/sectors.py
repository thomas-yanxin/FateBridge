"""FateBridge's 13 equal ascendant-relative sectors, not IAU constellations."""

import math
from fractions import Fraction
from typing import Any, TypedDict

from fatebridge.core.astro.geometry import _sign_name


class ThirteenSectorRecord(TypedDict):
    sector: int
    cusp_longitude: float
    end_longitude: float
    width_degrees: float
    sign: str


def _display_degree(value: Fraction) -> float:
    # Keep the displayed value in the same sign as the exact geometric edge.
    display = float(value)
    return math.nextafter(display, -math.inf) if Fraction(display) > value else display


def thirteen_sectors(ascendant: float) -> list[ThirteenSectorRecord]:
    anchor_degrees = Fraction(ascendant) % 360
    width_degrees = Fraction(360, 13)
    sectors: list[ThirteenSectorRecord] = []
    for sector_index in range(13):
        cusp_longitude = _display_degree(
            (anchor_degrees + sector_index * width_degrees) % 360
        )
        end_longitude = _display_degree(
            (anchor_degrees + (sector_index + 1) * width_degrees) % 360
        )
        sectors.append(
            {
                "sector": sector_index + 1,
                "cusp_longitude": cusp_longitude,
                "end_longitude": end_longitude,
                "width_degrees": float(width_degrees),
                "sign": _sign_name(cusp_longitude),
            }
        )
    return sectors


def sector_profile(ascendant: float) -> dict[str, Any]:
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
        "sources": [
            {
                "id": "iau_constellations",
                "author": "International Astronomical Union",
                "url": "https://iauarchive.eso.org/public/faq/",
                "scope": "Constellation boundaries have unequal widths; this custom partition does not implement them",
            }
        ],
    }
