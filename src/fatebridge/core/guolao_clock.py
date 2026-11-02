"""Apparent solar hour from this chart's Sun RA and modeled UT1 rotation.

USNO: apparent solar time = 12h + the apparent Sun's local hour angle.
No UTC-as-UT1 equation-of-time call, timezone rebasing, or new physical instant.
Exact Fraction arithmetic preserves supplied doubles at hour boundaries; it
does not make the astronomical model or birth coordinates exact observations.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from fractions import Fraction
from typing import Any

from fatebridge.core.guolao_classical import BRANCHES

METHOD_ID = "guolao_same_sky_apparent_solar_hour_v1"
SOURCE_URL = "https://aa.usno.navy.mil/faq/eqtime"
_MICROSECONDS_PER_DAY = 86_400_000_000


def apparent_solar_clock(
    *,
    julian_day_ut1: float,
    sun_right_ascension: float,
    greenwich_apparent_sidereal_degrees: float,
    longitude: float,
    civil_datetime: datetime,
) -> dict[str, Any]:
    """Use the declared geocentric apparent Sun; display has no civil offset.

    The day label uses UT1 + east longitude + signed equation of time. The
    hour branch uses the exact circular phase before microsecond truncation.
    Unrepresentable year labels stay null without substituting a civil hour.
    """
    for value in (
        julian_day_ut1,
        sun_right_ascension,
        greenwich_apparent_sidereal_degrees,
        longitude,
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("太阳钟面须使用明确的有限天文数值")
        if not math.isfinite(value):
            raise ValueError("太阳钟面天文输入须有限")
    if not 0 <= sun_right_ascension < 360:
        raise ValueError("视太阳赤经须在[0,360)")
    if not 0 <= greenwich_apparent_sidereal_degrees < 360:
        raise ValueError("格林尼治视恒星角须在[0,360)")
    if not -180 <= longitude <= 180:
        raise ValueError("经度须在[-180,180]，东经为正")
    if civil_datetime.utcoffset() is None:
        raise ValueError("须明确提供记录的带时区民用时刻")

    ut1 = Fraction(julian_day_ut1)
    ra = Fraction(sun_right_ascension)
    gast = Fraction(greenwich_apparent_sidereal_degrees)
    east = Fraction(longitude)
    mean_day_fraction = (ut1 + Fraction(1, 2)) % 1
    eot_degrees = (gast - ra - 360 * mean_day_fraction) % 360 - 180
    solar_jd = ut1 + (east + eot_degrees) / 360
    solar_day = (solar_jd + Fraction(1, 2)) // 1
    day_fraction = (solar_jd + Fraction(1, 2)) % 1
    # The same phase written directly as 12h + (GAST + east - RA)/15.
    assert day_fraction == ((gast + east - ra + 180) % 360) / 360
    hour_index = int((day_fraction * 24 + 1) // 2) % 12
    boundary_phase_hours = (day_fraction * 24 + 1) % 2
    boundary_distance = min(boundary_phase_hours, 2 - boundary_phase_hours) * 3600
    ordinal = int(solar_day) - 1721425
    display = None
    if 1 <= ordinal <= datetime.max.toordinal():
        microseconds = int(day_fraction * _MICROSECONDS_PER_DAY)
        display = (
            datetime.fromordinal(ordinal) + timedelta(microseconds=microseconds)
        ).isoformat()
    local = civil_datetime.replace(tzinfo=None)
    civil_jd = (
        local.toordinal()
        + Fraction(3442849, 2)
        + Fraction(
            ((local.hour * 60 + local.minute) * 60 + local.second) * 1_000_000
            + local.microsecond,
            _MICROSECONDS_PER_DAY,
        )
    )
    return {
        "method_id": METHOD_ID,
        "source_url": SOURCE_URL,
        "display": display,
        "display_status": "available" if display else "outside_datetime_year_range",
        "display_basis": "naive_local_solar_label_not_a_civil_timezone",
        "display_precision": "microsecond_truncated_not_physical_accuracy",
        "birth_hour_branch": BRANCHES[hour_index],
        "apparent_day_fraction_exact": str(day_fraction),
        "hour_boundary_distance_seconds_exact": str(boundary_distance),
        "solar_day_offset_from_civil": ordinal - local.toordinal(),
        "equation_of_time_seconds": float(eot_degrees * 240),
        "total_correction_seconds": float((solar_jd - civil_jd) * 86400),
        "julian_day_ut1": julian_day_ut1,
        "sun_apparent_right_ascension": sun_right_ascension,
        "greenwich_apparent_sidereal_degrees": greenwich_apparent_sidereal_degrees,
        "longitude": longitude,
        "solar_reference": "geocentric_apparent_sun_true_equator_equinox_of_date",
        "earth_rotation_basis": "shared_estimated_ut1_not_measured_dut1",
        "physical_time_accuracy_certified": False,
        "changes_physical_instant": False,
        "classical_clock_mapping_accepted": False,
    }
