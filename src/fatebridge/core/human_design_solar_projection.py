"""Nominal solar-disk projection in supplied apparent ecliptic coordinates.

The nominal radius is a conversion constant. This geometry cannot establish
actual occultation, visibility, an opaque solar limb or an error bound.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

NOMINAL_SOLAR_RADIUS_M = 695700000
ASTRONOMICAL_UNIT_M = 149597870700
ARITHMETIC_RESOLUTION_RADIANS = 1e-12
RADIUS_SOURCE = "https://www.iau.org/common/Uploaded%20files/IAUGA2015-Resolution-B3-recommended-nominal-conversion.pdf"
AU_SOURCE = "https://ssd.jpl.nasa.gov/planets/eph_export.html"
DEFLECTION_SOURCE = "https://www.astro.com/swisseph/swisseph.htm"


def _coordinates(values: Sequence[float]) -> tuple[float, float, float]:
    if (
        not isinstance(values, (tuple, list))
        or len(values) != 3
        or any(type(x) not in (float, int) or not math.isfinite(x) for x in values)
    ):
        raise ValueError("Projection requires three finite numerical coordinates")
    longitude, latitude, distance = map(float, values)
    if not 0 <= longitude < 360 or not -90 <= latitude <= 90 or distance <= 0:
        raise ValueError("Invalid ecliptic coordinates or distance")
    return longitude, latitude, distance


def nominal_solar_projection(
    sun: Sequence[float], target: Sequence[float]
) -> dict[str, Any]:
    """Portable interval geometry, independently rounded for each scalar."""
    from fatebridge.core.human_design_interval_geometry import (
        portable_projection_scalars,
    )

    solar, other = _coordinates(sun), _coordinates(target)
    return {
        **portable_projection_scalars(
            solar,
            other,
            NOMINAL_SOLAR_RADIUS_M,
            ASTRONOMICAL_UNIT_M,
            ARITHMETIC_RESOLUTION_RADIANS,
        ),
        "more_distant_than_sun_in_supplied_coordinates": other[2] > solar[2],
        "same_reported_distance_as_sun": other[2] == solar[2],
        "arithmetic_comparison_resolution_radians": ARITHMETIC_RESOLUTION_RADIANS,
        "physical_occultation_certified": False,
        "visibility_certified": False,
        "physical_accuracy_certified": False,
    }
