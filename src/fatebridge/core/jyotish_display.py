"""Derive an optional India solar label from the retained physical instant.

Prebuilt SDK display fields are derived values, not recorded birth facts.
They must not carry a parent's old native state into an isolated calculation.
The same forward UT1/TT convention also serves explicit solar-clock inputs.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import Any

from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.birth_clock import solar_clock_components
from fatebridge.core.astro.julian_day import _julian_day
from fatebridge.core.astro.source_session import current_source_session
from fatebridge.core.jyotish_clock import require_recorded_instant


def normalize_solar_display(
    birth: AstroBirthInfo, ephemeris_policy: str, *, requested: bool | None = None
) -> tuple[AstroBirthInfo, dict[str, Any] | None]:
    """Recompute a derived label, never a recorded clock or physical epoch."""
    enabled = birth.applied_true_solar if requested is None else requested
    if not enabled:
        if (
            birth.applied_true_solar
            or birth.solar_datetime is not None
            or birth.solar_correction_minutes != 0
        ):
            return (
                replace(
                    birth,
                    applied_true_solar=False,
                    solar_datetime=None,
                    solar_correction_minutes=0.0,
                ),
                None,
            )
        return birth, None
    require_recorded_instant(birth)
    session = current_source_session()
    if session is None:
        raise RuntimeError(
            "India solar display requires the calculation source session"
        )
    recorded = birth.recorded_datetime or birth.local_datetime
    key = (
        "india_physical_solar_display",
        birth.require_utc_datetime,
        recorded.isoformat(),
        birth.timezone,
        birth.clock_conversion is not None,
        birth.longitude,
        ephemeris_policy,
    )
    if key not in session.memo:
        parts = solar_clock_components(
            birth.require_utc_datetime,
            birth.longitude,
            "local_apparent_solar",
            ephemeris_policy=ephemeris_policy,
        )
        solar_jd = parts["julian_day_solar"]
        try:
            label = datetime(1970, 1, 1) + timedelta(
                days=float(solar_jd - Fraction(4881175, 2))
            )
        except OverflowError:
            label = None
        offset = recorded.utcoffset()
        assert offset is not None
        # Compare with the recorded wall's UTC-named carrier, including its
        # civil offset. Before1960 that carrier follows the declared UT1 input
        # assumption. It is not a claim that historical clocks realised UTC.
        correction = (
            float(
                (solar_jd - Fraction(_julian_day(recorded.astimezone(timezone.utc))))
                * 1440
            )
            - offset.total_seconds() / 60
        )
        sun = parts["sun"]
        context = {
            "method_id": "jyotish.physical_apparent_solar_display.v1",
            "representation_status": (
                "available" if label is not None else "outside_datetime_range"
            ),
            "time_scale_method": parts["time_scale_method"],
            "julian_day_ut1": parts["julian_day_ut1"],
            "julian_day_tt": parts["julian_day_tt"],
            "sun_julian_day_tt": sun["_julian_day_tt"],
            "equation_of_time_seconds": sun["equation_of_time_seconds"],
            "solar_reference": sun["solar_reference"],
            "solar_ephemeris_model": sun["solar_ephemeris_model"],
            "earth_rotation_policy_id": sun["earth_rotation_policy_id"],
            "sidereal_time_model": sun["sidereal_time_model"],
            "physical_sun_source": sun["_physical_source"],
            "derived_from": "recorded_instant_in_current_calculation_session",
            "supplied_derived_display_used": False,
            "physical_instant_shifted": False,
            "correction_reference": (
                "recorded_civil_wall"
                if birth.clock_conversion is None
                else "resolved_carrier_wall_not_original_solar_input"
            ),
            "scope": "Geocentric apparent solar wall label on shared model UT1/TT; not another timestamp or a birth-time correction. JD and display precision do not certify the birth clock, measured EOP, source accuracy or prediction validity.",
        }
        session.memo[key] = (label, round(correction, 4), context)
    label, correction, context = session.memo[key]
    return (
        replace(
            birth,
            applied_true_solar=True,
            solar_datetime=label,
            solar_correction_minutes=correction,
        ),
        context,
    )
