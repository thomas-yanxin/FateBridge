"""太阳弧度推运法（Solar Arc Directions）。"""

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
        orb_limit=1.5,
    )
    calculation_options: dict[str, object] = {
        "arc_method": "true_progressed_Sun_ecliptic_longitude",
        "angle_method": "rigid_natal_longitude_rotation",
    }
    if progression_options is not None:
        calculation_options["progression"] = progression_options
    else:
        pass
    return {
        "calculation_options": calculation_options,
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
