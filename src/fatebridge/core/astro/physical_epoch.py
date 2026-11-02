"""Physical TT/UT1 axes with an optional Python civil-time representation.

An inserted UTC second has a valid UTC label and physical epoch, but cannot
be carried by datetime. Never substitute the following midnight for it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.clock_observation import observe_clock
from fatebridge.core.astro.historical_utc import HistoricalUTCAdjustment
from fatebridge.core.astro.iers_ut1 import active_ut1
from fatebridge.core.astro.julian_day import _julian_day
from fatebridge.core.astro.time_scales import (
    EphemerisTime,
    datetime_from_tt,
    ephemeris_time,
    tt_from_ut1,
    ut1_from_tt,
)
from fatebridge.core.astro.utc_policy import leap_table
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.utils.civil_time import UTCCalendar
from fatebridge.utils.errors import EphemerisSourceError


def _calendar_from_jd(day: Fraction) -> UTCCalendar:
    serial = day + Fraction(1, 2) - 1721425
    ordinal = serial // 1
    micros = round((serial - ordinal) * 86_400_000_000)
    carry, micros = divmod(micros, 86_400_000_000)
    return UTCCalendar(int(ordinal + carry), micros)


def _extended_utc_label(jd_tt: float) -> str | None:
    """Prove an out-of-datetime label using the established time policy.

    Errors at ordinary dates are not converted to range failures. Before
    1960 the UTC-named historical label is modeled UT1; future UTC retains
    the frozen final atomic offset, rather than inventing leap seconds.
    """
    last = leap_table()["entries"][-1]
    effective = datetime.fromisoformat(last["effective_date"]).replace(
        tzinfo=timezone.utc
    )
    offset = Fraction(last["tai_minus_utc_seconds"]) + Fraction(4023, 125)
    if Fraction(jd_tt) >= Fraction(_julian_day(effective)) + offset / 86400:
        candidate = _calendar_from_jd(Fraction(jd_tt) - offset / 86400)
        return candidate.isoformat() if candidate.as_datetime() is None else None
    candidate = _calendar_from_jd(Fraction(ut1_from_tt(jd_tt)))
    return candidate.isoformat() if candidate.date_parts[0] < 1 else None


def utc_from_tt(jd_tt: float) -> tuple[str | None, datetime | None, bool]:
    """Frozen UTC policy, retaining second60 and historical nonunique labels.

    The label's microseconds express numerical formatting, not observed clock
    accuracy. Its fractional part is limited by the input double JD.
    """
    if not math.isfinite(jd_tt):
        raise ValueError("TT Julian day must be finite")
    entries = leap_table()["entries"]
    for previous, current in zip(entries, entries[1:]):
        delta = current["tai_minus_utc_seconds"] - previous["tai_minus_utc_seconds"]
        if delta <= 0:
            continue
        effective = datetime.fromisoformat(current["effective_date"]).replace(
            tzinfo=timezone.utc
        )
        midnight = _julian_day(effective)
        start = midnight + (previous["tai_minus_utc_seconds"] + 32.184) / 86400
        stop = midnight + (current["tai_minus_utc_seconds"] + 32.184) / 86400
        if start <= jd_tt < stop:
            if delta != 1:
                raise RuntimeError("未支持连续插入多个 UTC 闰秒的表示")
            fraction = min(int((jd_tt - start) * 86400 * 1e6), 999999)
            prior_day = effective - timedelta(days=1)
            label = prior_day.strftime("%Y-%m-%dT23:59:60") + f".{fraction:06d}+00:00"
            observe_clock(
                "tt_to_utc_display",
                jd_tt=jd_tt,
                utc_label=label,
                utc_is_leap_second=True,
            )
            return label, None, True
    try:
        moment = datetime_from_tt(jd_tt)
    except EphemerisSourceError:
        raise
    except HistoricalUTCAdjustment:
        observe_clock(
            "tt_to_utc_display", jd_tt=jd_tt, utc_label=None, utc_is_leap_second=False
        )
        return None, None, False
    except (ValueError, OverflowError):
        extended_label = _extended_utc_label(jd_tt)
        if extended_label is None:
            raise
        observe_clock(
            "tt_to_utc_display",
            jd_tt=jd_tt,
            utc_label=extended_label,
            utc_is_leap_second=False,
        )
        return extended_label, None, False
    observe_clock(
        "tt_to_utc_display",
        jd_tt=jd_tt,
        utc_label=moment.isoformat(),
        utc_is_leap_second=False,
    )
    return moment.isoformat(), moment, False


def utc_representation(
    utc_label: str | None, utc_datetime: datetime | None, utc_is_leap_second: bool
) -> dict[str, Any]:
    """Describe a UTC label independently of a Python datetime carrier."""
    return {
        "utc_label": utc_label,
        "utc_is_leap_second": utc_is_leap_second,
        "datetime_representable": utc_datetime is not None,
        "label_status": (
            "inserted_UTC_leap_second"
            if utc_is_leap_second
            else (
                "unique_civil_label"
                if utc_datetime is not None
                else (
                    "unique_extended_calendar_label_outside_datetime_range"
                    if utc_label is not None
                    else "unrepresentable_historical_fractional_UTC_adjustment"
                )
            )
        ),
        "primary_axis": "TT_for_positions_UT1_for_rotation",
        "scope": "UTC is a display label; no leap second is moved, smeared or converted to a uniform UTC JD. Before1960 the UTC-named historical carrier denotes modeled UT1. Numerical formatting does not establish input precision or measured EOP.",
    }


@dataclass(frozen=True)
class PhysicalEpoch:
    time: EphemerisTime
    utc_label: str | None
    utc_datetime: datetime | None
    utc_is_leap_second: bool

    def __post_init__(self) -> None:
        if self.time.jd_tt is None or not all(
            math.isfinite(x) for x in (self.time.jd_ut1, self.time.jd_tt)
        ):
            raise ValueError("Physical epoch requires finite TT and UT1")
        if self.utc_is_leap_second and (
            self.utc_datetime is not None or self.time.jd_utc is not None
        ):
            raise ValueError("UTC second60 cannot have a datetime or uniform UTC JD")

    @classmethod
    @runtime.preserve_ephemeris_path()
    def from_ut1(cls, jd_ut1: float) -> PhysicalEpoch:
        if runtime.swe is None:
            raise ImportError("Swiss Ephemeris is required for UT1 conversion")
        runtime.swe.set_ephe_path(configured_ephemeris_path() or "")
        tt = tt_from_ut1(jd_ut1)
        label, moment, leap = utc_from_tt(tt)
        # Preserve the established representable civil forward path, including
        # its final double-JD rounding. No carrier is fabricated when absent.
        if moment is not None:
            scales = ephemeris_time(moment)
        else:
            scales = EphemerisTime(
                None,
                jd_ut1,
                tt,
                (
                    "primary_UT1_IERS20_C04_to_TT_frozen_UTC_display"
                    if active_ut1.get() is not None
                    else "primary_UT1_swiss_delta_t_to_TT_frozen_UTC_display"
                ),
                tt
                >= float(
                    Fraction(
                        _julian_day(datetime.fromisoformat(leap_table()["expires_at"]))
                    )
                    + (
                        Fraction(leap_table()["entries"][-1]["tai_minus_utc_seconds"])
                        + Fraction(4023, 125)
                    )
                    / 86400
                ),
            )
        if abs(scales.jd_ut1 - jd_ut1) * 86400 > 0.0002:
            raise ValueError("Physical clock inversion did not preserve UT1")
        return cls(scales, label, moment, leap)

    def require_datetime(self) -> datetime:
        if self.utc_datetime is None:
            raise ValueError(
                "Solved event lies in a UTC leap second not representable by datetime"
                if self.utc_is_leap_second
                else (
                    "Solved UTC calendar label is outside datetime range"
                    if self.utc_label is not None
                    else "Solved physical event has no unique supported UTC datetime"
                )
            )
        return self.utc_datetime

    def representation(self) -> dict[str, Any]:
        return utc_representation(
            self.utc_label, self.utc_datetime, self.utc_is_leap_second
        )
