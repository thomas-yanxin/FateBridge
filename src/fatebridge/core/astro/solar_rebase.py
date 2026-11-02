"""Resolve the optional western clock rebase on its recorded instant's UT1."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fatebridge.core.astro.birth_clock import _sun_clock
from fatebridge.core.astro.source_session import coherent_ephemeris_sources
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.utils.civil_time import utc_calendar
from fatebridge.utils.solar_time import (
    SOLAR_TIME_STRATEGY_LONGITUDE_ONLY,
    calculate_solar_time_adjustment,
)


def rebase_solar_datetime(recorded: datetime, correction_minutes: float) -> datetime:
    """Carry a shifted solar label at the confirmed record's fixed offset.

    A solar label is not a second civil-time input. Applying named-zone rules
    again can cross a gap/fold and add an unintended offset change. Retain a
    fixed-offset carrier so UTC receives exactly the stated correction, also
    when that UTC label lies outside datetime's representable year range.
    """
    offset = recorded.utcoffset()
    if offset is None:
        raise ValueError("Solar rebasing requires a confirmed aware record")
    return recorded.replace(tzinfo=timezone(offset), fold=0) + timedelta(
        minutes=correction_minutes
    )


@coherent_ephemeris_sources
def solar_rebase_adjustment(
    recorded: datetime, timezone_name: str, longitude: float
) -> tuple[dict[str, float], dict[str, Any]]:
    """Retain the existing longitude/DST/rebase convention, resolve EOT in UT1.

    This is the explicitly selected legacy rebase, not conversion of a known
    LMT/LAT birth label or a claim about future Earth rotation/leap seconds.
    """
    scales = ephemeris_time(recorded)
    if scales.jd_tt is None:
        raise ImportError("Western solar-clock rebasing requires a native clock")
    # time_equ(UT1) internally chooses calc_ut's TT and native sidereal time.
    # Use the already resolved TT and the chart's adopted GAST instead, as in
    # the existing explicit LAT/LMT clock path. The source session also covers
    # the clock mapping and the actual Sun call, not only its returned number.
    sun = _sun_clock(scales.jd_ut1, _julian_day_tt=scales.jd_tt)
    adjustment = calculate_solar_time_adjustment(
        recorded,
        timezone_name,
        longitude,
        strategy=SOLAR_TIME_STRATEGY_LONGITUDE_ONLY,
    )
    eot_minutes = sun["equation_of_time_seconds"] / 60
    adjustment["equation_of_time_minutes"] = eot_minutes
    adjustment["total_correction_minutes"] += eot_minutes
    rebased = rebase_solar_datetime(recorded, adjustment["total_correction_minutes"])
    frozen_offset = rebased.utcoffset()
    assert frozen_offset is not None
    return adjustment, {
        "method_id": "western_solar_rebase_coherent_tt_ut1_v2",
        "recorded_utc": utc_calendar(recorded).isoformat(),
        "recorded_julian_day_tt": scales.jd_tt,
        "equation_of_time_julian_day_ut1": scales.jd_ut1,
        "equation_of_time_seconds": adjustment["equation_of_time_minutes"] * 60,
        "sun_apparent_right_ascension_degrees": sun[
            "sun_apparent_right_ascension_degrees"
        ],
        "greenwich_apparent_sidereal_degrees": sun[
            "greenwich_apparent_sidereal_degrees"
        ],
        "solar_ephemeris_model": sun["solar_ephemeris_model"],
        "solar_ephemeris_source": sun["_physical_source"],
        "sidereal_time_model": sun["sidereal_time_model"],
        "earth_rotation_policy_id": sun["earth_rotation_policy_id"],
        "rebase_arithmetic": "frozen_recorded_utc_offset_v1",
        "recorded_local_datetime": recorded.isoformat(),
        "recorded_utc_offset_seconds": frozen_offset.total_seconds(),
        "rebased_solar_clock_datetime": rebased.isoformat(),
        "rebased_utc": utc_calendar(rebased).isoformat(),
        "rebase_utc_shift_seconds": timedelta(
            minutes=adjustment["total_correction_minutes"]
        ).total_seconds(),
        "time_scale_method": scales.method,
        "future_leap_seconds_assumed_unchanged": scales.future_leap_seconds_assumed_unchanged,
        "scope": "Apparent Sun at the recorded primary TT and adopted GAST at its selected/modelled UT1. Actual Sun source is separate from the effective rebased chart. Existing longitude/DST correction is applied with the record's UTC offset frozen; the shifted solar label is not a legal clock assertion in the named civil zone. Not historical-clock identification, complete EOP, future clock accuracy or a physical-error bound.",
    }
