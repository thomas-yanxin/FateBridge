"""Historical UTC rate/offset changes, separate from UT1/Delta-T.

SOFA supplies 1960; the separately preserved IERS table supplies 1961-1971.
Earlier calendar labels are outside this scope. No Earth rotation is inferred.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from functools import lru_cache
from importlib.resources import files
from typing import Any, cast

from fatebridge.core.astro.julian_day import _datetime_from_julian_day
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.utc_policy import leap_table
from fatebridge.utils.civil_time import CivilPoint


class HistoricalUTCAdjustment(ValueError):
    """TT has no unique supported ordinary historical datetime label."""


@dataclass(frozen=True)
class UTCDriftInterval:
    start: datetime
    start_day: Fraction
    stop_day: Fraction
    offset_at_start: Fraction
    rate: Fraction
    start_tt: Fraction
    stop_tt: Fraction


@lru_cache(maxsize=1)
def historical_utc_table() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            files("fatebridge.data")
            .joinpath("knowledge/western-historical-utc.json")
            .read_text(encoding="utf-8")
        ),
    )


@lru_cache(maxsize=1)
def utc1960_table() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            files("fatebridge.data")
            .joinpath("knowledge/western-utc1960.json")
            .read_text(encoding="utf-8")
        ),
    )


def historical_utc_source(moment: datetime) -> dict[str, Any]:
    """Select the historical coefficient source by the UTC calendar year."""
    if moment.utcoffset() is None:
        raise ValueError("Historical UTC requires an aware datetime")
    return (
        utc1960_table()
        if moment.astimezone(timezone.utc).year == 1960
        else historical_utc_table()
    )


def _utc_intervals() -> tuple[UTCDriftInterval, ...]:
    table = historical_utc_table()
    rows = tuple(
        (
            row["effective_date"],
            str(row["offset_seconds"]),
            str(row["reference_mjd"]),
            str(row["rate_seconds_per_day"]),
        )
        for row in [*utc1960_table()["entries"], *table["entries"]]
    )
    return _utc_intervals_cached(
        rows,
        table["valid_until"],
        Fraction(leap_table()["entries"][0]["tai_minus_utc_seconds"]),
    )


@lru_cache(maxsize=1)
def _utc_intervals_cached(
    source_rows: tuple[tuple[str, str, str, str], ...],
    valid_until: str,
    modern_offset: Fraction,
) -> tuple[UTCDriftInterval, ...]:
    """Ordinary UTC source domains, including removed negative-step tails."""
    rows = [
        (
            _date(effective_date),
            Fraction(offset),
            Fraction(4800001, 2) + Fraction(reference_mjd),
            Fraction(rate),
        )
        for effective_date, offset, reference_mjd, rate in source_rows
    ]
    intervals = []
    for index, (start, offset, reference, rate) in enumerate(rows):
        start_day = Fraction(start.toordinal()) + Fraction(3442849, 2)
        stop = rows[index + 1][0] if index + 1 < len(rows) else _date(valid_until)
        stop_day = Fraction(stop.toordinal()) + Fraction(3442849, 2)
        if index + 1 < len(rows):
            _, next_offset, next_reference, next_rate = rows[index + 1]
            next_offset += (stop_day - next_reference) * next_rate
        else:
            next_offset = modern_offset
        end_offset = offset + (stop_day - reference) * rate
        # SOFA dtf2d: remove the daily frequency drift before measuring the
        # jump. A negative jump removes the final fraction of the UTC day.
        stop_day += min(Fraction(0), next_offset - end_offset) / 86400
        offset_at_start = offset + (start_day - reference) * rate
        intervals.append(
            UTCDriftInterval(
                start,
                start_day,
                stop_day,
                offset_at_start,
                rate,
                start_day + (offset_at_start + Fraction(4023, 125)) / 86400,
                stop_day
                + (
                    offset_at_start
                    + (stop_day - start_day) * rate
                    + Fraction(4023, 125)
                )
                / 86400,
            )
        )
    return tuple(intervals)


def _date(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def historical_tai_minus_utc(moment: datetime) -> float | None:
    """Round the published affine offset once, after exact UTC evaluation."""
    offset = historical_tai_minus_utc_exact(moment)
    return None if offset is None else float(offset)


def historical_tai_minus_utc_exact(moment: datetime) -> Fraction | None:
    """One published-decimal offset for scalar and exact-point consumers."""
    if moment.utcoffset() is None:
        raise ValueError("Historical UTC requires an aware datetime")
    moment = moment.astimezone(timezone.utc)
    intervals = _utc_intervals()
    if not (
        intervals[0].start <= moment < _date(historical_utc_table()["valid_until"])
    ):
        return None
    interval = next(row for row in reversed(intervals) if row.start <= moment)
    micros = (
        moment.hour * 3600 + moment.minute * 60 + moment.second
    ) * 1_000_000 + moment.microsecond
    day = (
        Fraction(moment.toordinal())
        + Fraction(3442849, 2)
        + Fraction(micros, 86_400_000_000)
    )
    if day >= interval.stop_day:
        raise ValueError(
            "UTC clock label was removed by a historical negative adjustment"
        )
    return interval.offset_at_start + (day - interval.start_day) * interval.rate


def historical_utc_to_tt_point(moment: datetime) -> TTInstant | None:
    """Encode a covered UTC label with the same exact published offset."""
    offset = historical_tai_minus_utc_exact(moment)
    return (
        None
        if offset is None
        else TTInstant.from_utc(moment, tai_minus_utc_seconds=offset)
    )


def historical_utc_from_tt(
    jd_tt: float | TTInstant, *, nominal_boundaries: bool = False
) -> datetime | None:
    """Use one point inverse; nominal encoded midnights are explicit policy."""
    point = historical_utc_point_from_tt(jd_tt, nominal_boundaries=nominal_boundaries)
    return (
        None
        if point is None
        else _datetime_from_julian_day(point.day, before=point.excluded_before)
    )


def historical_utc_point_from_tt(
    julian_day_tt: float | TTInstant, *, nominal_boundaries: bool = False
) -> CivilPoint | None:
    """Invert the same published affine coefficients without large-JD loss.

    Removed negative-step labels are outside the ordinary UTC source domain.
    Inserted fractional labels remain unsupported by datetime; tiny gaps in
    the declared source equations are not filled with an invented label.
    """
    intervals = _utc_intervals()
    if isinstance(julian_day_tt, TTInstant):
        if nominal_boundaries:
            raise ValueError("TTInstant cannot request nominal scalar boundary labels")
        point = julian_day_tt
    else:
        point = TTInstant.from_float(julian_day_tt)
        if nominal_boundaries:
            for interval in intervals:
                if julian_day_tt == float(interval.start_tt):
                    return CivilPoint(interval.start_day, interval.stop_day)
    modern = Fraction(_date(historical_utc_table()["valid_until"]).toordinal())
    modern += (
        Fraction(3442849, 2)
        + (
            Fraction(leap_table()["entries"][0]["tai_minus_utc_seconds"])
            + Fraction(4023, 125)
        )
        / 86400
    )
    if not intervals[0].start_tt <= point.days < modern:
        return None
    candidates = [
        (
            interval.start_day
            + (point.days - interval.start_tt) / (1 + interval.rate / 86400),
            interval.stop_day,
        )
        for interval in intervals
        if interval.start_tt <= point.days < interval.stop_tt
    ]
    if len(candidates) != 1:
        raise HistoricalUTCAdjustment(
            "TT lies in a historical UTC adjustment without a unique ordinary datetime label"
        )
    civil, stop = candidates[0]
    return CivilPoint(civil, stop)
