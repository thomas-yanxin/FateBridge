"""Physical TT/UT1 axes with an optional Python civil-time representation.

An inserted UTC second has a valid UTC label and physical epoch, but cannot
be carried by datetime. Never substitute the following midnight for it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from fractions import Fraction
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.clock_observation import observe_clock
from fatebridge.core.astro.historical_utc import HistoricalUTCAdjustment
from fatebridge.core.astro.iers_ut1 import active_ut1
from fatebridge.core.astro.julian_day import _julian_day
from fatebridge.core.astro.time_scales import (
    EphemerisTime,
    ephemeris_time,
    resolve_tt_from_ut1,
    resolve_ut1_from_tt,
    utc_calendar_from_tt,
)
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.core.astro.utc_policy import leap_table
from fatebridge.utils.civil_time import (
    CivilPoint,
    UTCCalendar,
    ZonedCalendar,
    utc_calendar,
)
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.timezones import is_unspecified_local_time


def _calendar_from_jd(day: Fraction) -> UTCCalendar:
    serial = day + Fraction(1, 2) - 1721425
    ordinal = serial // 1
    micros = round((serial - ordinal) * 86_400_000_000)
    carry, micros = divmod(micros, 86_400_000_000)
    return UTCCalendar(int(ordinal + carry), micros)


def _extended_utc_label(point: TTInstant) -> str | None:
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
    if point.days >= Fraction(_julian_day(effective)) + offset / 86400:
        candidate = _calendar_from_jd(point.days - offset / 86400)
        return candidate.isoformat() if candidate.as_datetime() is None else None
    candidate = _calendar_from_jd(resolve_ut1_from_tt(point).days)
    return candidate.isoformat() if candidate.date_parts[0] < 1 else None


def utc_from_tt(
    jd_tt: float | TTInstant, *, legacy_pre_utc: bool = False
) -> tuple[str | None, datetime | None, bool]:
    """Frozen UTC policy, retaining second60 and historical nonunique labels.

    An explicit point retains its source precision; a scalar retains only
    its represented IEEE value, including at leap boundaries. The
    nominal rounded-midnight aliases belong to datetime_from_tt(float).
    The label's microseconds express numerical formatting, not observed clock
    accuracy. A scalar input's fractional part is limited by its double JD.
    Legacy event displays can retain Swiss's pre-UTC calendar conversion
    while using exact transition membership on the atomic and drift scales.
    """
    point = TTInstant.from_value(jd_tt)
    scalar_tt = point.as_float()
    entries = leap_table()["entries"]
    for previous, current in zip(entries, entries[1:]):
        delta = current["tai_minus_utc_seconds"] - previous["tai_minus_utc_seconds"]
        if delta <= 0:
            continue
        effective = datetime.fromisoformat(current["effective_date"]).replace(
            tzinfo=timezone.utc
        )
        midnight = Fraction(_julian_day(effective))
        start = (
            midnight
            + (Fraction(previous["tai_minus_utc_seconds"]) + Fraction(4023, 125))
            / 86400
        )
        stop = (
            midnight
            + (Fraction(current["tai_minus_utc_seconds"]) + Fraction(4023, 125)) / 86400
        )
        if start <= point.days < stop:
            if delta != 1:
                raise RuntimeError("未支持连续插入多个 UTC 闰秒的表示")
            fraction = int((point.days - start) * 86_400_000_000)
            prior_day = effective - timedelta(days=1)
            label = prior_day.strftime("%Y-%m-%dT23:59:60") + f".{fraction:06d}+00:00"
            observe_clock(
                "tt_to_utc_display",
                jd_tt=scalar_tt,
                utc_label=label,
                utc_is_leap_second=True,
            )
            return label, None, True
    try:
        calendar = utc_calendar_from_tt(point, legacy_pre_utc=legacy_pre_utc)
    except EphemerisSourceError:
        raise
    except HistoricalUTCAdjustment:
        observe_clock(
            "tt_to_utc_display",
            jd_tt=scalar_tt,
            utc_label=None,
            utc_is_leap_second=False,
        )
        return None, None, False
    except (ValueError, OverflowError):
        extended_label = _extended_utc_label(point)
        if extended_label is None:
            raise
        observe_clock(
            "tt_to_utc_display",
            jd_tt=scalar_tt,
            utc_label=extended_label,
            utc_is_leap_second=False,
        )
        return extended_label, None, False
    label, moment = calendar.isoformat(), calendar.as_datetime()
    observe_clock(
        "tt_to_utc_display",
        jd_tt=scalar_tt,
        utc_label=label,
        utc_is_leap_second=False,
    )
    return label, moment, False


def local_leap_second_label(utc_label: str, zone: tzinfo) -> str | None:
    """Apply a defined, integral-minute offset to an inserted UTC second."""
    prior = ZonedCalendar.from_isoformat(utc_label.replace(":60.", ":59.", 1))
    local = ZonedCalendar(prior.utc, zone)
    sample = local.rule_sample()
    if is_unspecified_local_time(sample) or local.offset % timedelta(minutes=1):
        return None
    return sample.isoformat(timespec="microseconds").replace(":59.", ":60.", 1)


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
    source_calendar: CivilPoint | None = None

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
    def from_civil(cls, moment: datetime | UTCCalendar) -> PhysicalEpoch:
        """Retain the calendar that supplies a forward TT/UT1 conversion."""
        calendar = utc_calendar(moment) if isinstance(moment, datetime) else moment
        return cls(
            ephemeris_time(calendar),
            moment.isoformat(),
            moment if isinstance(moment, datetime) else calendar.as_datetime(),
            False,
            CivilPoint(calendar.julian_day_exact()),
        )

    @classmethod
    @runtime.preserve_ephemeris_path()
    def from_tt(cls, jd_tt: float | TTInstant) -> PhysicalEpoch:
        """Retain a solved TT point; its civil label never becomes a new epoch."""
        point = TTInstant.from_value(jd_tt)
        label, moment, leap = utc_from_tt(point)
        last = leap_table()["entries"][-1]
        expiry_tt = (
            Fraction(_julian_day(datetime.fromisoformat(leap_table()["expires_at"])))
            + (Fraction(last["tai_minus_utc_seconds"]) + Fraction(4023, 125)) / 86400
        )
        scales = EphemerisTime(
            _julian_day(moment) if moment is not None else None,
            resolve_ut1_from_tt(point),
            point,
            (
                "primary_TT_IERS20_C04_UT1_frozen_UTC_display"
                if active_ut1.get() is not None
                else "primary_TT_swiss_delta_t_UT1_frozen_UTC_display"
            ),
            point.days >= expiry_tt,
        )
        return cls(scales, label, moment, leap)

    @classmethod
    @runtime.preserve_ephemeris_path()
    def from_ut1(cls, jd_ut1: float | UT1Instant) -> PhysicalEpoch:
        """Retain primary UT1 and its selected TT conversion before formatting."""
        ut1 = UT1Instant.from_value(jd_ut1)
        tt = resolve_tt_from_ut1(ut1)
        label, moment, leap = utc_from_tt(tt)
        # UTC's microsecond display must not become a replacement physical
        # epoch. Before1960, a second native civil conversion can move both
        # primary axes by one JD ulp even though its old tolerance passed.
        scales = EphemerisTime(
            _julian_day(moment) if moment is not None else None,
            ut1,
            tt,
            (
                "primary_UT1_IERS20_C04_to_TT_frozen_UTC_display"
                if active_ut1.get() is not None
                else "primary_UT1_swiss_delta_t_to_TT_frozen_UTC_display"
            ),
            tt.as_float()
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
