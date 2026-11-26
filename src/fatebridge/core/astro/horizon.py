"""Geometric horizon independent of astrological house division.

Swiss Ephemeris programmer documentation 8.14: azalt()[1] is the true
(unrefracted) altitude. The fallback shares the analytic ray's true ecliptic,
equator and matching GAST; source-frame consistency is not physical certification.
The convention is geocentric disc centre, zero altitude counts as day.
"""

from __future__ import annotations

import math

from fatebridge.core.astro import runtime
from fatebridge.core.astro.earth_attitude import analytic_earth_attitude
from fatebridge.core.astro.ephemeris import fast_swe_call
from fatebridge.core.astro.native_coordinates import require_altitude
from fatebridge.core.astro.time_scales import fallback_julian_day_tt
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.utils.errors import EphemerisSourceError


def horizon_altitude(
    julian_day: float | UT1Instant,
    longitude: float,
    latitude: float,
    ecliptic_longitude: float,
    ecliptic_latitude: float = 0.0,
    *,
    julian_day_tt: float | TTInstant | None = None,
) -> tuple[float, str]:
    if (
        not all(
            math.isfinite(v)
            for v in (
                (
                    julian_day.as_float()
                    if isinstance(julian_day, UT1Instant)
                    else julian_day
                ),
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
            result = fast_swe_call(
                "azalt",
                julian_day,
                runtime.swe.ECL2HOR,
                (longitude, latitude, 0.0),
                0.0,
                0.0,
                (ecliptic_longitude, ecliptic_latitude, 1.0),
                _julian_day_tt=julian_day_tt,
            )
        except EphemerisSourceError:
            raise
        except runtime.native_ephemeris_errors() as error:
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
    attitude = analytic_earth_attitude(
        julian_day, fallback_julian_day_tt(julian_day, julian_day_tt)
    )
    eps = math.radians(attitude.true_obliquity)
    x = math.cos(beta) * math.cos(lam)
    y = math.cos(beta) * math.sin(lam) * math.cos(eps) - math.sin(beta) * math.sin(eps)
    z = math.cos(beta) * math.sin(lam) * math.sin(eps) + math.sin(beta) * math.cos(eps)
    hour_angle = math.radians(
        attitude.equator.greenwich_sidereal_degrees + longitude
    ) - math.atan2(y, x)
    dec = math.asin(max(-1.0, min(1.0, z)))
    sin_alt = math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(
        hour_angle
    )
    return (
        math.degrees(math.asin(max(-1.0, min(1.0, sin_alt)))),
        "approximate_geometric_altitude",
    )


def populate_horizon(
    states: dict[str, dict[str, float]],
    julian_day: float | UT1Instant,
    longitude: float,
    latitude: float,
    *,
    julian_day_tt: float | TTInstant | None = None,
) -> str:
    methods = set()
    for state in states.values():
        state["altitude"], method = horizon_altitude(
            julian_day,
            longitude,
            latitude,
            state["longitude"],
            state["latitude"],
            julian_day_tt=julian_day_tt,
        )
        methods.add(method)
    return next(iter(methods)) if len(methods) == 1 else "mixed_horizon_methods"
