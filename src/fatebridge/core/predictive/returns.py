"""Bracketed solar/lunar returns in TT; governing event never lies in future."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from fatebridge.core.astro.geometry import native_lahiri_ayanamsha
from fatebridge.core.astro.time_scales import datetime_from_tt, ephemeris_time
from fatebridge.core.ephemeris_runtime import (
    ephemeris_call,
    preserve_ephemeris_path,
    swe,
)

from ._common import build_subject, point_to_dict


def _longitude_tt(
    body_id: int, julian_day_tt: float, *, sidereal: bool = False
) -> float:
    coordinates, flag = ephemeris_call("calc", julian_day_tt, body_id, swe.FLG_SWIEPH)
    if flag < 0:
        raise ValueError("Return search ephemeris failed")
    longitude = float(coordinates[0])
    if sidereal:
        longitude -= native_lahiri_ayanamsha(julian_day_tt=julian_day_tt)
    return longitude % 360


def _signed_offset(longitude: float, target: float) -> float:
    offset = math.remainder(longitude - target, 360.0)
    return offset - 360.0 if offset == 180.0 else offset


def governing_return_tt(
    body_id: int, target_longitude: float, analysis_tt: float, *, sidereal: bool = False
) -> float:
    """Latest positive-motion zero crossing at or before analysis_tt.

    Solar 10-day / lunar 1-day steps remain below half a revolution; reject the
    antipodal discontinuity. Bisection keeps the final root inside its bracket.
    The wider windows include at least one complete solar or lunar revolution.
    """
    if body_id not in {swe.SUN, swe.MOON}:
        raise ValueError("This return solver supports Sun and Moon only")
    lookback, step = (370.0, 10.0) if body_id == swe.SUN else (32.0, 1.0)
    left = analysis_tt - lookback
    previous = _signed_offset(
        _longitude_tt(body_id, left, sidereal=sidereal), target_longitude
    )
    bracket = None
    while left < analysis_tt:
        right = min(left + step, analysis_tt)
        current = _signed_offset(
            _longitude_tt(body_id, right, sidereal=sidereal), target_longitude
        )
        if previous <= 0 <= current and current - previous < 180:
            bracket = (left, right)
        left, previous = right, current
    if bracket is None:
        raise ValueError(
            "No governing return was bracketed before the analysis instant"
        )
    low, high = bracket
    for _ in range(64):
        middle = (low + high) / 2
        if middle in {low, high} or high - low <= 1e-9:
            break
        value = _signed_offset(
            _longitude_tt(body_id, middle, sidereal=sidereal), target_longitude
        )
        if value < 0:
            low = middle
        else:
            high = middle
    return min(
        (low, high),
        key=lambda jd: abs(
            _signed_offset(
                _longitude_tt(body_id, jd, sidereal=sidereal), target_longitude
            )
        ),
    )


@preserve_ephemeris_path()
def build_return_payload(
    natal_subject: Any,
    *,
    analysis_datetime: datetime,
    return_longitude: float,
    return_latitude: float,
    return_timezone: str,
    include: Optional[List[str]] = None,
) -> Dict[str, Any]:
    times = ephemeris_time(analysis_datetime)
    if times.jd_tt is None:
        raise ImportError("Swiss Ephemeris is required for planetary returns")
    payload: Dict[str, Any] = {}
    for key, planet, body_id in [
        ("solar_return", "sun", swe.SUN),
        ("lunar_return", "moon", swe.MOON),
    ]:
        if key not in (include or ["solar_return", "lunar_return"]):
            continue
        target = float(getattr(natal_subject, planet).abs_pos)
        sidereal = natal_subject.zodiac_type == "Sidereal"
        solved = governing_return_tt(body_id, target, times.jd_tt, sidereal=sidereal)
        moment = datetime_from_tt(solved)
        chart = build_subject(
            name=f"{natal_subject.name}-{key}",
            local_datetime=moment,
            longitude=return_longitude,
            latitude=return_latitude,
            timezone_name=return_timezone,
            house_system=natal_subject.houses_system_identifier,
            zodiac_type=natal_subject.zodiac_type,
        )
        actual = float(getattr(chart, planet).abs_pos)
        payload[key] = {
            "return_datetime": chart.iso_formatted_local_datetime,
            "return_datetime_utc": moment.isoformat(),
            "sun": point_to_dict("Sun", chart.sun),
            "moon": point_to_dict("Moon", chart.moon),
            "ascendant": point_to_dict("Ascendant", chart.ascendant),
            "medium_coeli": point_to_dict("Medium_Coeli", chart.medium_coeli),
            "solver": {
                "method_id": "bracketed_tt_longitude_return_v1",
                "julian_day_tt": solved,
                "target_longitude": target,
                "solved_longitude": actual,
                "residual_arcseconds": abs(_signed_offset(actual, target)) * 3600,
                "event_not_after_analysis": solved <= times.jd_tt,
            },
            "calculation_basis": chart.calculation_basis,
        }
    return payload
