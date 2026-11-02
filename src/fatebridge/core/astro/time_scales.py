"""Explicit civil UTC, dynamical TT and estimated Earth-rotation UT1.

Post-1972: TT = UTC + (TAI-UTC) + 32.184 seconds (IERS Bulletin C).
Beyond the frozen leap table's expiry the last offset is an assumption,
reported on every chart. No future leap second or measured DUT1 is invented.
1960 uses SOFA; 1961-1971 uses IERS' historical UTC rate/offset table.
Earlier inputs retain Swiss Ephemeris' historical UT1/Delta-T convention.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import Optional

from fatebridge.core.astro import runtime, utc_policy
from fatebridge.core.astro.clock_observation import observe_clock, observer
from fatebridge.core.astro.historical_utc import (
    HistoricalUTCAdjustment,
    historical_tai_minus_utc,
    historical_utc_from_tt,
    historical_utc_from_tt_point,
)
from fatebridge.core.astro.iers_ut1 import active_ut1
from fatebridge.core.astro.julian_day import _julian_day
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.utc_policy import default_delta_t_flag, leap_table
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.utils.civil_time import utc_calendar


@dataclass(frozen=True)
class EphemerisTime:
    jd_utc: Optional[float]
    jd_ut1: float
    jd_tt: Optional[float]
    method: str
    future_leap_seconds_assumed_unchanged: bool


def _delta_t_for_ut1(
    julian_day_ut1: float, steps: Optional[list[list[float | int]]] = None
) -> float:
    # Before the SOFA/IERS UTC era, our forward path uses Swiss utc_to_jd,
    # which explicitly calls deltat_ex(..., -1). A SWIEPH flag selects a
    # different automatic tidal acceleration and is not its inverse (about
    # 30 seconds apart in AD400). Keep both directions on the declared path.
    # From 1960 the explicit UTC-offset path uses FLG_SWIEPH instead.
    assert runtime.swe is not None
    flag = default_delta_t_flag(julian_day_ut1, runtime.swe.FLG_SWIEPH)
    delta = float(runtime.ephemeris_call("deltat_ex", julian_day_ut1, flag))
    if steps is not None:
        steps.append([julian_day_ut1, flag, delta])
    return delta


def tt_from_ut1(julian_day_ut1: float) -> float:
    """Convert UT1 under the selected C04 or default Delta T policy."""
    if not math.isfinite(julian_day_ut1):
        raise ValueError("UT1 Julian day must be finite")
    selected = active_ut1.get()
    if selected is not None:
        return selected.tt_from_ut1(julian_day_ut1)
    if runtime.swe is None:
        raise ImportError("Swiss Ephemeris is required for UT1 conversion")
    delta = _delta_t_for_ut1(julian_day_ut1)
    return float(julian_day_ut1 + delta)


def ut1_from_tt(julian_day_tt: float) -> float:
    """Selected C04 interpolation, or inverse default modeled Delta T."""
    if not math.isfinite(julian_day_tt):
        raise ValueError("TT Julian day must be finite")
    selected = active_ut1.get()
    if selected is not None:
        result = selected.ut1_from_tt(julian_day_tt)
        observe_clock(
            "tt_to_ut1",
            jd_tt=julian_day_tt,
            jd_ut1=result,
            steps=[],
            ut1_source="iers_c04",
        )
        return result
    if runtime.swe is None:
        raise ImportError("Swiss Ephemeris is required for TT conversion")
    result = julian_day_tt
    steps: Optional[list[list[float | int]]] = [] if observer.get() else None
    for _ in range(4):
        result = julian_day_tt - _delta_t_for_ut1(result, steps)
    observe_clock("tt_to_ut1", jd_tt=julian_day_tt, jd_ut1=float(result), steps=steps)
    return float(result)


def datetime_from_ut1(julian_day_ut1: float) -> datetime:
    """UT1 event to civil UTC through TT and the frozen civil-time policy."""
    return datetime_from_tt(tt_from_ut1(julian_day_ut1))


def ephemeris_time(moment: datetime) -> EphemerisTime:
    if moment.utcoffset() is None:
        raise ValueError("Ephemeris time requires a timezone-aware civil instant")
    calendar = utc_calendar(moment)
    normalized = calendar.as_datetime()
    if normalized is not None:
        moment = normalized
    year, month, day = calendar.date_parts
    hour, minute, second, microsecond = calendar.time_parts
    civil = _julian_day(moment)
    assumed = moment >= datetime.fromisoformat(utc_policy.leap_table()["expires_at"])
    selected = active_ut1.get()
    if runtime.swe is None:
        if selected is not None:
            raise ImportError(
                "Selected IERS/native clock path requires Swiss Ephemeris"
            )
        return EphemerisTime(civil, civil, None, "UTC_as_UT1_approximation", assumed)
    # Swiss state can be thread-local and may have been released by a prior
    # catalogue calculation. Initialize this worker before Delta-T calls.
    with runtime.preserve_ephemeris_path():
        runtime.swe.set_ephe_path(configured_ephemeris_path() or "")
        historical_offset = (
            historical_tai_minus_utc(moment) if 1960 <= year < 1972 else None
        )
        if year < 1972 and historical_offset is None:
            if selected is not None:
                raise ValueError(
                    "IERS C04 UT1 source has no records before 1962; no modeled fallback applied"
                )
            tt, ut1 = runtime.ephemeris_call(
                "utc_to_jd",
                year,
                month,
                day,
                hour,
                minute,
                second + microsecond / 1e6,
                runtime.swe.GREG_CAL,
            )
            observe_clock(
                "civil_to_tt_ut1",
                utc_label=calendar.isoformat(),
                jd_civil=civil,
                jd_tt=float(tt),
                jd_ut1=float(ut1),
                steps=[],
                native_utc_to_jd=[
                    year,
                    month,
                    day,
                    hour,
                    minute,
                    second + microsecond / 1e6,
                    runtime.swe.GREG_CAL,
                ],
            )
            return EphemerisTime(
                civil, float(ut1), float(tt), "pre_1972_swiss_UT1_delta_t", False
            )
        offset = (
            historical_offset
            if historical_offset is not None
            else next(
                entry["tai_minus_utc_seconds"]
                for entry in reversed(utc_policy.leap_table()["entries"])
                if tuple(map(int, entry["effective_date"].split("-")))
                <= (year, month, day)
            )
        )
        tt = civil + (offset + 32.184) / 86400.0
        # Invert TT = UT1 + Delta T. UT1 is a model estimate, not measured EOP.
        ut1 = civil
        steps: Optional[list[list[float | int]]] = [] if observer.get() else None
        if selected is not None:
            ut1 = selected.ut1_from_tt(tt)
        else:
            for _ in range(4):
                delta = runtime.ephemeris_call("deltat_ex", ut1, runtime.swe.FLG_SWIEPH)
                if steps is not None:
                    steps.append([ut1, runtime.swe.FLG_SWIEPH, float(delta)])
                ut1 = tt - delta
        observe_clock(
            "civil_to_tt_ut1",
            utc_label=calendar.isoformat(),
            jd_civil=civil,
            jd_tt=tt,
            jd_ut1=float(ut1),
            steps=steps,
            native_utc_to_jd=None,
            **({"ut1_source": "iers_c04"} if selected is not None else {}),
        )
        if historical_offset is None:
            method = "IERS_UTC_to_TT_swiss_delta_t_to_UT1"
        elif year == 1960:
            method = "SOFA_1960_UTC_drift_to_TT_swiss_delta_t_to_UT1"
        else:
            method = "IERS_1961_1971_UTC_drift_to_TT_swiss_delta_t_to_UT1"
        if selected is not None:
            method = "frozen_UTC_offsets_to_TT_IERS20_C04_UT1_TAI_interpolation"
        return EphemerisTime(civil, float(ut1), tt, method, assumed)


def datetime_from_tt(
    julian_day_tt: float | TTInstant, *, exact_epoch: Optional[bool] = None
) -> datetime:
    """Invert atomic offsets without a second large-JD rounding.

    The established scalar convention preserves nominal leap-boundary labels
    encoded as a rounded double JD. ``exact_epoch=True`` explicitly interprets
    the supplied IEEE value as an exact point instead. These interpretations
    differ at transition aliases; neither proves physical clock precision.
    TTInstant retains an explicit exact point (including two-part TT or a
    losslessly encoded UTC label); it never enables nominal scalar aliases.
    """
    if isinstance(julian_day_tt, TTInstant):
        if exact_epoch is False:
            raise ValueError("TTInstant cannot request nominal scalar boundary labels")
        exact_tt = julian_day_tt.days
        julian_day_tt = julian_day_tt.as_float()
        exact_epoch = True
    else:
        exact_tt = Fraction(julian_day_tt)
    entries = utc_policy.leap_table()["entries"]
    if not exact_epoch:
        for previous, current in zip(entries, entries[1:]):
            if current["tai_minus_utc_seconds"] <= previous["tai_minus_utc_seconds"]:
                continue
            effective = datetime.fromisoformat(current["effective_date"]).replace(
                tzinfo=timezone.utc
            )
            nominal_start = (
                _julian_day(effective)
                + (previous["tai_minus_utc_seconds"] + 32.184) / 86400
            )
            if julian_day_tt == nominal_start:
                raise ValueError(
                    "Solved event lies in a UTC leap second not representable by datetime"
                )
    for entry in reversed(entries):
        effective = datetime.fromisoformat(entry["effective_date"]).replace(
            tzinfo=timezone.utc
        )
        offset = Fraction(entry["tai_minus_utc_seconds"]) + Fraction(32184, 1000)
        nominal_boundary = (
            _julian_day(effective) + (entry["tai_minus_utc_seconds"] + 32.184) / 86400
        )
        encoded_boundary = not exact_epoch and julian_day_tt == nominal_boundary
        if (
            encoded_boundary
            or exact_tt >= Fraction(_julian_day(effective)) + offset / 86400
        ):
            elapsed_microseconds = round(
                ((exact_tt - Fraction(4881175, 2)) * 86400 - offset) * 1_000_000
            )
            moment = (
                effective
                if encoded_boundary
                else datetime(1970, 1, 1, tzinfo=timezone.utc)
                + timedelta(microseconds=elapsed_microseconds)
            )
            resolved = (
                _utc_tt_without_rotation(moment)
                if active_ut1.get() is not None
                else ephemeris_time(moment).jd_tt
            )
            if resolved is None or abs(resolved - julian_day_tt) * 86400 > 0.0002:
                raise ValueError(
                    "Solved event lies in a UTC leap second not representable by datetime"
                )
            return moment
    if exact_tt != Fraction(julian_day_tt):
        raise HistoricalUTCAdjustment(
            "Historical UTC inversion cannot retain this exact two-part TT point"
        )
    historical = historical_utc_from_tt(julian_day_tt)
    if historical is not None:
        resolved = (
            _utc_tt_without_rotation(historical)
            if active_ut1.get() is not None
            else ephemeris_time(historical).jd_tt
        )
        if resolved is None or abs(resolved - julian_day_tt) * 86400 > 0.0002:
            raise HistoricalUTCAdjustment(
                "Historical UTC inversion did not preserve TT"
            )
        return historical
    if runtime.swe is None:
        raise ImportError("Swiss Ephemeris is required for historical TT conversion")
    year, month, day, hour, minute, seconds = runtime.ephemeris_call(
        "jdet_to_utc", julian_day_tt, runtime.swe.GREG_CAL
    )
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc) + timedelta(
        seconds=seconds
    )


def datetime_from_tt_point(point: TTInstant) -> datetime:
    """Explicit point inversion for a split-root consumer across all eras.

    Modern UTC uses frozen integer offsets; 1960–1971 uses the published
    affine UTC segments. Before UTC, the existing Swiss UT1/Delta-T convention
    is retained, with the small TT remainder kept outside the native float.
    None of these numerical conversions measures historical physical UTC.
    """
    if not isinstance(point, TTInstant):
        raise TypeError("Point inversion requires explicit TTInstant")
    resolved: Optional[float]
    first_modern = datetime(1972, 1, 1, tzinfo=timezone.utc)
    if point.days >= TTInstant.from_utc(first_modern, tai_minus_utc_seconds=10).days:
        return datetime_from_tt(point)
    historical = historical_utc_from_tt_point(point)
    if historical is not None:
        resolved = _utc_tt_without_rotation(historical)
        if abs(resolved - point.as_float()) * 86400 > 0.0002:
            raise HistoricalUTCAdjustment(
                "Rounded historical UTC label cannot preserve the supplied TT point"
            )
        return historical
    if active_ut1.get() is not None:
        raise ValueError("Selected IERS C04 has no pre-1960 UTC/UT1 inversion")
    if runtime.swe is None:
        raise ImportError("Swiss Ephemeris is required for pre-UTC TT conversion")
    with runtime.preserve_ephemeris_path():
        runtime.swe.set_ephe_path(configured_ephemeris_path() or "")
        ut1 = point.days
        for _ in range(4):
            ut1 = point.days - Fraction(_delta_t_for_ut1(float(ut1)))
        micros = round((ut1 - Fraction(4881175, 2)) * 86_400_000_000)
        moment = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
            microseconds=micros
        )
        # Do not silently cross into a civil era whose affine clock policy
        # did not accept this TT point.
        if moment.year >= 1960:
            raise HistoricalUTCAdjustment(
                "TT point has no consistent label across the start of UTC"
            )
        resolved = ephemeris_time(moment).jd_tt
        if resolved is None or abs(resolved - point.as_float()) * 86400 > 0.0002:
            raise HistoricalUTCAdjustment(
                "Modeled pre-UTC inversion did not preserve TT"
            )
        return moment


def _utc_tt_without_rotation(moment: datetime) -> float:
    """Validate a UTC label through atomic offsets, without querying UT1.

    UTC display of a TT-only event remains available after a selected C04
    series ends. This is not a modeled fallback for an unavailable UT1.
    """
    moment = moment.astimezone(timezone.utc)
    if moment.year < 1972:
        offset = historical_tai_minus_utc(moment)
        if offset is None:
            raise ValueError("No atomic UTC offset for this historical label")
    else:
        label = moment.date().isoformat()
        offset = next(
            r["tai_minus_utc_seconds"]
            for r in reversed(utc_policy.leap_table()["entries"])
            if r["effective_date"] <= label
        )
    return _julian_day(moment) + (offset + 32.184) / 86400
