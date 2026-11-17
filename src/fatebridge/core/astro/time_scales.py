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

import astronomy

from fatebridge.core.astro import runtime, utc_policy
from fatebridge.core.astro.clock_observation import observe_clock, observer
from fatebridge.core.astro.historical_utc import (
    HistoricalUTCAdjustment,
    historical_tai_minus_utc,
    historical_utc_from_tt,
    historical_utc_from_tt_point,
)
from fatebridge.core.astro.iers_ut1 import active_ut1
from fatebridge.core.astro.julian_day import (
    _julian_day,
    _julian_day_from_calendar,
    _utc_calendar_from_julian_day,
)
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.utc_policy import default_delta_t_flag
from fatebridge.core.astro.utc_policy import leap_table as leap_table
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.utils.civil_time import UTCCalendar, gregorian_ordinal, utc_calendar


@dataclass(frozen=True)
class EphemerisTime:
    jd_utc: Optional[float]
    jd_ut1: float
    jd_tt: Optional[float]
    method: str
    future_leap_seconds_assumed_unchanged: bool


def fallback_julian_day_tt(julian_day_ut1: float, julian_day_tt: float | None) -> float:
    """Preserve explicit TT, otherwise use the declared Espenak–Meeus estimate."""
    return (
        julian_day_tt
        if julian_day_tt is not None
        else astronomy.Time(julian_day_ut1 - 2451545.0).tt + 2451545.0
    )


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


@dataclass(frozen=True)
class UTCClock:
    calendar: UTCCalendar
    civil_jd: float
    jd_tt: float | None
    method: str
    future_leap_seconds_assumed_unchanged: bool


def utc_clock(moment: datetime | UTCCalendar) -> UTCClock:
    """Resolve the civil/atomic clock without selecting an Earth-rotation source.

    Before an atomic UTC offset exists, TT remains unassigned here. The full
    ephemeris clock owns that era's explicit UT1/Delta-T convention.
    """
    calendar = moment if isinstance(moment, UTCCalendar) else utc_calendar(moment)
    year, month, day = calendar.date_parts
    hour, minute, second, microsecond = calendar.time_parts
    civil = _julian_day_from_calendar(calendar)
    expiry = utc_calendar(datetime.fromisoformat(utc_policy.leap_table()["expires_at"]))
    assumed = (calendar.ordinal, calendar.microseconds_of_day) >= (
        expiry.ordinal,
        expiry.microseconds_of_day,
    )
    historical_offset = (
        historical_tai_minus_utc(
            datetime(
                year, month, day, hour, minute, second, microsecond, tzinfo=timezone.utc
            )
        )
        if 1960 <= year < 1972
        else None
    )
    offset: float | None
    if historical_offset is not None:
        offset = historical_offset
    elif year >= 1972:
        offset = float(
            next(
                entry["tai_minus_utc_seconds"]
                for entry in reversed(utc_policy.leap_table()["entries"])
                if tuple(map(int, entry["effective_date"].split("-")))
                <= (year, month, day)
            )
        )
    else:
        offset = None
    tt = None if offset is None else civil + (offset + 32.184) / 86400.0
    if tt is None:
        method = "no_atomic_UTC_offset"
    elif historical_offset is None:
        method = "IERS_UTC_to_TT"
    elif year == 1960:
        method = "SOFA_1960_UTC_drift_to_TT"
    else:
        method = "IERS_1961_1971_UTC_drift_to_TT"
    return UTCClock(calendar, civil, tt, method, assumed)


def ephemeris_time(moment: datetime | UTCCalendar) -> EphemerisTime:
    atomic = utc_clock(moment)
    calendar = atomic.calendar
    year, month, day = calendar.date_parts
    hour, minute, second, microsecond = calendar.time_parts
    civil = atomic.civil_jd
    tt = atomic.jd_tt
    assumed = atomic.future_leap_seconds_assumed_unchanged
    selected = active_ut1.get()
    if tt is None:
        if selected is not None:
            raise ValueError(
                "IERS C04 UT1 source has no records before 1962; no modeled fallback applied"
            )
        if runtime.swe is None:
            return EphemerisTime(
                civil, civil, None, "UTC_as_UT1_approximation", assumed
            )
        with runtime.preserve_ephemeris_path():
            runtime.swe.set_ephe_path(configured_ephemeris_path() or "")
            native_tt, native_ut1 = runtime.ephemeris_call(
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
                jd_tt=float(native_tt),
                jd_ut1=float(native_ut1),
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
                civil,
                float(native_ut1),
                float(native_tt),
                "pre_1972_swiss_UT1_delta_t",
                False,
            )
    ut1 = civil
    steps: Optional[list[list[float | int]]] = [] if observer.get() else None
    if selected is not None:
        ut1 = selected.ut1_from_tt(tt)
    elif runtime.swe is not None:
        # Only the default UT1/DeltaT provider needs native ephemeris state.
        # Frozen UTC offsets and the C04 table are independent clock sources.
        with runtime.preserve_ephemeris_path():
            runtime.swe.set_ephe_path(configured_ephemeris_path() or "")
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
    if selected is not None:
        method = "frozen_UTC_offsets_to_TT_IERS20_C04_UT1_TAI_interpolation"
    elif runtime.swe is None:
        method = "frozen_UTC_offsets_to_TT_UTC_as_UT1_approximation"
    else:
        method = atomic.method + "_swiss_delta_t_to_UT1"
    return EphemerisTime(civil, float(ut1), tt, method, assumed)


def utc_calendar_from_tt(
    julian_day_tt: float | TTInstant, *, exact_epoch: Optional[bool] = None
) -> UTCCalendar:
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
    for index in range(len(entries) - 1, -1, -1):
        entry = entries[index]
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
            ordinary_stop = None
            if index + 1 < len(entries):
                following = entries[index + 1]
                next_midnight = datetime.fromisoformat(
                    following["effective_date"]
                ).replace(tzinfo=timezone.utc)
                next_offset = Fraction(following["tai_minus_utc_seconds"]) + Fraction(
                    32184, 1000
                )
                ordinary_stop = (
                    Fraction(_julian_day(next_midnight))
                    + min(Fraction(0), next_offset - offset) / 86400
                )
                if exact_tt >= ordinary_stop + offset / 86400:
                    raise ValueError(
                        "Solved event lies in a UTC leap second not representable by datetime"
                    )
            moment = (
                utc_calendar(effective)
                if encoded_boundary
                else _utc_calendar_from_julian_day(
                    exact_tt - offset / 86400, before=ordinary_stop
                )
            )
            resolved = _utc_tt_without_rotation(moment)
            if abs(resolved - julian_day_tt) * 86400 > 0.0002:
                raise ValueError(
                    "Solved event lies in a UTC leap second not representable by datetime"
                )
            return moment
    historical = (
        historical_utc_from_tt_point(TTInstant(exact_tt))
        if exact_epoch
        else historical_utc_from_tt(julian_day_tt, nominal_boundaries=True)
    )
    if historical is not None:
        resolved = _utc_tt_without_rotation(historical)
        if abs(resolved - julian_day_tt) * 86400 > 0.0002:
            raise HistoricalUTCAdjustment(
                "Historical UTC inversion did not preserve TT"
            )
        return utc_calendar(historical)
    if active_ut1.get() is not None:
        raise ValueError("Selected IERS C04 has no pre-1960 UTC/UT1 inversion")
    if runtime.swe is None:
        raise ImportError("Swiss Ephemeris is required for pre-UTC TT conversion")
    if not exact_epoch:
        year, month, day, hour, minute, seconds = runtime.ephemeris_call(
            "jdet_to_utc", julian_day_tt, runtime.swe.GREG_CAL
        )
        elapsed = timedelta(hours=hour, minutes=minute, seconds=seconds)
        return UTCCalendar(
            gregorian_ordinal(year, month, day) + elapsed.days,
            elapsed.seconds * 1000000 + elapsed.microseconds,
        )
    with runtime.preserve_ephemeris_path():
        runtime.swe.set_ephe_path(configured_ephemeris_path() or "")
        ut1 = exact_tt
        for _ in range(4):
            ut1 = exact_tt - Fraction(_delta_t_for_ut1(float(ut1)))
        moment = _utc_calendar_from_julian_day(ut1)
        # Do not silently cross into a civil era whose affine clock policy
        # did not accept this TT point.
        if moment.date_parts[0] >= 1960:
            raise HistoricalUTCAdjustment(
                "TT point has no consistent label across the start of UTC"
            )
        roundtrip_tt = ephemeris_time(moment).jd_tt
        if roundtrip_tt is None or abs(roundtrip_tt - julian_day_tt) * 86400 > 0.0002:
            raise HistoricalUTCAdjustment(
                "Modeled pre-UTC inversion did not preserve TT"
            )
        return moment


def datetime_from_tt(
    julian_day_tt: float | TTInstant, *, exact_epoch: Optional[bool] = None
) -> datetime:
    """Use the shared clock inversion, requiring a Python-representable UTC label."""
    calendar = utc_calendar_from_tt(julian_day_tt, exact_epoch=exact_epoch)
    moment = calendar.as_datetime()
    if moment is None:
        raise ValueError("UTC calendar label is outside Python datetime's year range")
    return moment


def _utc_tt_without_rotation(moment: datetime | UTCCalendar) -> float:
    """Validate a UTC label through atomic offsets, without querying UT1.

    UTC display of a TT-only event remains available after a selected C04
    series ends. This is not a modeled fallback for an unavailable UT1.
    """
    resolved = utc_clock(moment).jd_tt
    if resolved is None:
        raise ValueError("No atomic UTC offset for this historical label")
    return resolved
