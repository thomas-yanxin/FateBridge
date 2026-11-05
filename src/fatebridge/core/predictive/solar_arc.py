"""太阳弧度推运法（Solar Arc Directions）。"""

from __future__ import annotations

from fractions import Fraction

from fatebridge.core.astro.geometry import longitude_float

from ._common import (
    Any,
    Dict,
    collect_aspect_hits,
    extract_reference_longitudes,
    longitude_to_point_dict,
    point_absolute_position,
)


def build_solar_arc_payload(
    natal_subject: Any,
    progressed_subject: Any,
) -> Dict[str, Any]:
    natal_longitudes = extract_reference_longitudes(natal_subject)
    arc_degrees = (
        Fraction(point_absolute_position(progressed_subject, "Sun"))
        - Fraction(point_absolute_position(natal_subject, "Sun"))
    ) % 360
    directed_points: Dict[str, Fraction] = {}
    for point_name, longitude in natal_longitudes.items():
        directed_points[point_name] = (Fraction(longitude) + arc_degrees) % 360
    hits = collect_aspect_hits(
        source_longitudes=directed_points,
        target_longitudes=natal_longitudes,
        orb_limit=1.5,
    )
    return {
        "arc_degrees": round(float(arc_degrees), 4),
        "sun": longitude_to_point_dict("Sun", longitude_float(directed_points["Sun"])),
        "moon": longitude_to_point_dict(
            "Moon", longitude_float(directed_points["Moon"])
        ),
        "ascendant": longitude_to_point_dict(
            "Ascendant",
            longitude_float(directed_points["Ascendant"]),
        ),
        "medium_coeli": longitude_to_point_dict(
            "Medium_Coeli",
            longitude_float(directed_points["Medium_Coeli"]),
        ),
        "hits": hits[:8],
    }
