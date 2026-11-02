"""Actual unequal planetary hour for a supplied native horary instant."""

from __future__ import annotations

import math
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.classical import _planetary_hours
from fatebridge.core.astro.physical_sources import assert_physical_configuration
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path


@runtime.preserve_ephemeris_path()
def collect_radicality_hour(
    subject: Any, *, clock_basis: str = "civil"
) -> dict[str, Any]:
    """Reuse the same UT1 sunrise interval engine, never civil-hour modulo24.

    rise_trans does not expose a physical backend flag. Keep its horizon and
    backend-verification limits explicit rather than calling it a source match.
    """
    result: dict[str, Any] = {
        "status": "not_computed",
        "unavailable_reason": "native_epoch_or_location_unavailable",
        "hour": None,
        "horizon_policy": "Shared apparent solar-center unequal hours; sea level,1013.25hPa,0C; not a reconstructed1647 table",
        "actual_solar_backend_verified": False,
        "source_method_acceptance": False,
        "geometric_chart_sect": (
            "day"
            if getattr(subject, "is_diurnal", None) is True
            else "night" if getattr(subject, "is_diurnal", None) is False else None
        ),
        "hour_and_geometric_sect_differ": None,
        "sect_comparison_policy": "Unequal-hour day uses the apparent sunrise convention; chart sect uses geometric solar center. Their boundaries can differ; neither is silently replaced to force agreement.",
    }
    at = getattr(subject, "julian_day", None)
    lng, lat, tz = (
        getattr(subject, "lng", None),
        getattr(subject, "lat", None),
        getattr(subject, "tz_str", None),
    )
    if at is None or lng is None or lat is None or tz is None or runtime.swe is None:
        return result
    if not all(math.isfinite(v) for v in (at, lng, lat)):
        raise ValueError("Planetary hour epoch and location must be finite")
    if not -180 <= lng <= 180 or not -90 < lat < 90:
        raise ValueError("Invalid planetary-hour location")
    selected = configured_ephemeris_path()
    hour = (
        _planetary_hours(at, lng, lat, tz)
        if clock_basis == "civil"
        else _planetary_hours(at, lng, lat, tz, weekday_clock_basis=clock_basis)
    )
    assert_physical_configuration(selected)
    result.update(
        status="computed" if hour is not None else "unavailable",
        unavailable_reason=(
            None if hour is not None else "sunrise_sunset_interval_unavailable"
        ),
        hour=hour,
        epoch_jd_ut1=at,
        hour_and_geometric_sect_differ=(
            None
            if hour is None or result["geometric_chart_sect"] is None
            else hour["is_day"] != (result["geometric_chart_sect"] == "day")
        ),
    )
    return result
