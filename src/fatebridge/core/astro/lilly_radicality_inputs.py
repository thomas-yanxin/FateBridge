"""Actual unequal planetary hour for a supplied native horary instant."""

from __future__ import annotations

import math
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.classical import _resolve_planetary_hour
from fatebridge.core.astro.native_chart import NativeSubject
from fatebridge.core.astro.physical_sources import assert_physical_configuration
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path


@runtime.preserve_ephemeris_path()
def collect_radicality_hour(
    subject: Any, *, clock_basis: str = "civil"
) -> dict[str, Any]:
    """Collect the shared unequal planetary hour for the supplied instant.

    The nested hour records the interval's solar source. This collector leaves
    independent backend verification and Lilly's method unassessed.
    """
    result: dict[str, Any] = {
        "status": "not_computed",
        "unavailable_reason": "native_epoch_or_location_unavailable",
        "hour": None,
        "geometric_chart_sect": (
            "day"
            if getattr(subject, "is_diurnal", None) is True
            else "night" if getattr(subject, "is_diurnal", None) is False else None
        ),
        "hour_and_geometric_sect_differ": None,
    }
    at = (
        subject.ut1
        if isinstance(subject, NativeSubject)
        else getattr(subject, "julian_day", None)
    )
    lng, lat, tz = (
        getattr(subject, "lng", None),
        getattr(subject, "lat", None),
        getattr(subject, "tz_str", None),
    )
    if at is None or lng is None or lat is None or tz is None or runtime.swe is None:
        return result
    scalar = at.as_float() if isinstance(at, UT1Instant) else at
    if not all(math.isfinite(v) for v in (scalar, lng, lat)):
        raise ValueError("Planetary hour epoch and location must be finite")
    if not -180 <= lng <= 180 or not -90 < lat < 90:
        raise ValueError("Invalid planetary-hour location")
    selected = configured_ephemeris_path()
    outcome = (
        _resolve_planetary_hour(at, lng, lat, tz)
        if clock_basis == "civil"
        else _resolve_planetary_hour(at, lng, lat, tz, weekday_clock_basis=clock_basis)
    )
    assert_physical_configuration(selected)
    unavailable_reason: str | None
    if isinstance(outcome, str):
        hour = None
        unavailable_reason = outcome
    else:
        hour = outcome
        unavailable_reason = (
            "sunrise_sunset_interval_unavailable" if hour is None else None
        )
    result.update(
        status="computed" if hour is not None else "unavailable",
        unavailable_reason=unavailable_reason,
        hour=hour,
        epoch_jd_ut1=scalar,
        hour_and_geometric_sect_differ=(
            None
            if hour is None or result["geometric_chart_sect"] is None
            else hour["is_day"] != (result["geometric_chart_sect"] == "day")
        ),
    )
    return result
