"""Geometric horizon independent of astrological house division.

Swiss Ephemeris programmer documentation 8.14: azalt()[1] is the true
(unrefracted) altitude. The fallback rotates tropical ecliptic coordinates
to the equator, then uses local mean sidereal time; it is approximate.
The convention is geocentric disc centre, zero altitude counts as day.
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

from fatebridge.core.astro import runtime
from fatebridge.core.astro.geometry import _gmst
from fatebridge.core.astro.native_coordinates import require_altitude
from fatebridge.utils.errors import EphemerisSourceError


def horizon_altitude(
    julian_day: float,
    longitude: float,
    latitude: float,
    ecliptic_longitude: float,
    ecliptic_latitude: float = 0.0,
) -> Tuple[float, str]:
    if (
        not all(
            math.isfinite(v)
            for v in (
                julian_day,
                longitude,
                latitude,
                ecliptic_longitude,
                ecliptic_latitude,
            )
        )
        or not -90 <= latitude <= 90
        or not -90 <= ecliptic_latitude <= 90
    ):
        raise EphemerisSourceError("coordinate_values_unavailable")
    if runtime.swe is not None:
        try:
            result = runtime.ephemeris_call(
                "azalt",
                julian_day,
                runtime.swe.ECL2HOR,
                (longitude, latitude, 0.0),
                0.0,
                0.0,
                (ecliptic_longitude, ecliptic_latitude, 1.0),
            )
        except EphemerisSourceError:
            raise
        except Exception as error:
            runtime._log_swe_runtime_failure("azalt", error)
        else:
            try:
                altitude = float(result[1])
            except (IndexError, TypeError, ValueError, OverflowError) as error:
                raise EphemerisSourceError("coordinate_values_unavailable") from error
            return require_altitude(altitude), "swisseph_true_altitude"
    lam, beta, phi = map(
        math.radians, (ecliptic_longitude, ecliptic_latitude, latitude)
    )
    eps = math.radians(23.439291 - 0.0130042 * ((julian_day - 2451545.0) / 36525.0))
    x = math.cos(beta) * math.cos(lam)
    y = math.cos(beta) * math.sin(lam) * math.cos(eps) - math.sin(beta) * math.sin(eps)
    z = math.cos(beta) * math.sin(lam) * math.sin(eps) + math.sin(beta) * math.cos(eps)
    hour_angle = math.radians(_gmst(julian_day) + longitude) - math.atan2(y, x)
    dec = math.asin(max(-1.0, min(1.0, z)))
    sin_alt = math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(
        hour_angle
    )
    return (
        math.degrees(math.asin(max(-1.0, min(1.0, sin_alt)))),
        "approximate_geometric_altitude",
    )


def populate_horizon(
    states: Dict[str, Dict[str, float]],
    julian_day: float,
    longitude: float,
    latitude: float,
) -> str:
    methods = set()
    for state in states.values():
        state["altitude"], method = horizon_altitude(
            julian_day, longitude, latitude, state["longitude"], state["latitude"]
        )
        methods.add(method)
    return next(iter(methods)) if len(methods) == 1 else "mixed_horizon_methods"
