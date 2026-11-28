"""Standard Western Predictive Solar Arc Directions (distinct from core/astro/solar_arc.py)."""

from __future__ import annotations

from typing import Any

from fatebridge.core.astro.geometry import longitude_float
from fatebridge.core.predictive._common import (
    collect_aspect_hits,
    extract_reference_longitudes,
    longitude_to_point_dict,
    point_absolute_position,
    source_arc_positions,
)
from fatebridge.core.predictive.native_chart import NativeSubject
from fatebridge.core.predictive.progressions import ProgressionCalculationOptions


def build_solar_arc_payload(
    natal_subject: NativeSubject,
    progressed_subject: NativeSubject,
    *,
    orb_limit: float = 1.5,
    max_hits: int | None = None,
    progression_options: ProgressionCalculationOptions | None = None,
) -> dict[str, Any]:
    natal_longitudes = extract_reference_longitudes(natal_subject)
    arc_degrees, directed_points = source_arc_positions(
        natal_longitudes,
        point_absolute_position(natal_subject, "Sun"),
        point_absolute_position(progressed_subject, "Sun"),
    )
    hits = collect_aspect_hits(
        source_longitudes=directed_points,
        target_longitudes=natal_longitudes,
        orb_limit=orb_limit,
    )
    hits_total_count = len(hits)
    selected_hits = hits[:max_hits] if max_hits is not None else hits
    calculation_options: dict[str, object] = {
        "arc_method": "true_progressed_Sun_ecliptic_longitude",
        "angle_method": "rigid_natal_longitude_rotation",
    }
    if progression_options is not None:
        calculation_options["progression"] = progression_options
    return {
        "calculation_options": calculation_options,
        "arc_degrees": round(float(arc_degrees), 4),
        "sun": longitude_to_point_dict("Sun", longitude_float(directed_points["Sun"])),
        "moon": longitude_to_point_dict(
            "Moon", longitude_float(directed_points["Moon"])
        ),
        "ascendant": (
            longitude_to_point_dict(
                "Ascendant", longitude_float(directed_points["Ascendant"])
            )
            if "Ascendant" in directed_points
            else None
        ),
        "medium_coeli": longitude_to_point_dict(
            "Medium_Coeli",
            longitude_float(directed_points["Medium_Coeli"]),
        ),
        "hits": selected_hits,
        "hits_total_count": hits_total_count,
    }
