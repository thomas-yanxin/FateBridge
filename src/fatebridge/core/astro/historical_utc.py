"""Historical UTC rate/offset changes, separate from UT1/Delta-T.

SOFA supplies 1960; the separately preserved IERS table supplies 1961-1971.
Earlier calendar labels are outside this scope. No Earth rotation is inferred.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from functools import lru_cache
from importlib.resources import files
from typing import Any, Optional, cast

from fatebridge.core.astro.julian_day import _julian_day
from fatebridge.core.astro.tt_epoch import TTInstant


class HistoricalUTCAdjustment(ValueError):
    """TT occurs in a fractional UTC adjustment with no unique civil label."""


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


def _entries() -> list[dict[str, Any]]:
    return [*utc1960_table()["entries"], *historical_utc_table()["entries"]]


def _date(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def historical_tai_minus_utc(moment: datetime) -> Optional[float]:
    """Use the full fractional UTC day, not just midnight's TAI-UTC value."""
    if moment.utcoffset() is None:
        raise ValueError("Historical UTC requires an aware datetime")
    moment = moment.astimezone(timezone.utc)
    entries = _entries()
    if (
        not _date(entries[0]["effective_date"])
        <= moment
        < _date(historical_utc_table()["valid_until"])
    ):
        return None
    entry = next(
        row
        for row in reversed(entries)
        if row["effective_date"] <= moment.date().isoformat()
    )
    return float(
        entry["offset_seconds"]
        + (_julian_day(moment) - 2400000.5 - entry["reference_mjd"])
        * entry["rate_seconds_per_day"]
    )


def historical_utc_to_tt_point(moment: datetime) -> Optional[TTInstant]:
    """Encode a covered UTC label using the exact published affine decimals.

    This is a separate point contract. The established float forward and
    inverse functions retain their existing arithmetic and results. It does
    not infer Earth rotation, authenticate a clock, or extend table coverage.
    """
    if moment.utcoffset() is None:
        raise ValueError("Historical UTC requires an aware datetime")
    moment = moment.astimezone(timezone.utc)
    entries = _entries()
    if not (
        _date(entries[0]["effective_date"])
        <= moment
        < _date(historical_utc_table()["valid_until"])
    ):
        return None
    row = next(
        entry
        for entry in reversed(entries)
        if entry["effective_date"] <= moment.date().isoformat()
    )
    micros = (
        moment.hour * 3600 + moment.minute * 60 + moment.second
    ) * 1_000_000 + moment.microsecond
    day = (
        Fraction(moment.toordinal())
        + Fraction(3442849, 2)
        + Fraction(micros, 86_400_000_000)
    )
    offset = Fraction(str(row["offset_seconds"])) + (
        day - Fraction(4800001, 2) - Fraction(str(row["reference_mjd"]))
    ) * Fraction(str(row["rate_seconds_per_day"]))
    return TTInstant.from_utc(moment, tai_minus_utc_seconds=offset)


def historical_utc_from_tt(jd_tt: float) -> Optional[datetime]:
    """Invert each affine segment; refuse a gap or multiple civil candidates.

    datetime cannot encode the fractional UTC clock-adjustment intervals. The
    caller may retain TT and report that a unique normalized label is missing.
    """
    table = historical_utc_table()
    entries = _entries()
    first = _date(entries[0]["effective_date"])
    first_offset = historical_tai_minus_utc(first)
    if first_offset is None:
        raise ValueError("Historical UTC table does not cover its first epoch")
    first_tt = _julian_day(first) + (first_offset + 32.184) / 86400
    # Modern UTC conversion handles the upper endpoint and later epochs.
    stop_tt = _julian_day(_date(table["valid_until"])) + (10 + 32.184) / 86400
    if not first_tt <= jd_tt < stop_tt:
        return None
    candidates = []
    for index, row in enumerate(entries):
        start = _julian_day(_date(row["effective_date"]))
        stop = _julian_day(
            _date(
                entries[index + 1]["effective_date"]
                if index + 1 < len(entries)
                else table["valid_until"]
            )
        )
        rate = row["rate_seconds_per_day"]
        offset = (
            row["offset_seconds"] + (start - 2400000.5 - row["reference_mjd"]) * rate
        )
        start_tt = start + (offset + 32.184) / 86400
        # Evaluate both endpoints directly. Accumulating a multi-year segment
        # from start_tt can create a one-ULP false overlap at a continuous
        # coefficient change (for example 1962-01-01).
        stop_offset = (
            row["offset_seconds"] + (stop - 2400000.5 - row["reference_mjd"]) * rate
        )
        stop_tt = stop + (stop_offset + 32.184) / 86400
        if start_tt <= jd_tt < stop_tt:
            civil = start + (jd_tt - start_tt) / (1 + rate / 86400)
            candidates.append(
                datetime(1970, 1, 1, tzinfo=timezone.utc)
                + timedelta(days=civil - 2440587.5)
            )
    if len(candidates) != 1:
        raise HistoricalUTCAdjustment(
            "TT lies in a historical fractional UTC adjustment without a unique datetime label"
        )
    return candidates[0]


def historical_utc_from_tt_point(point: TTInstant) -> Optional[datetime]:
    """Invert the same published affine coefficients without large-JD loss.

    Decimal coefficients denote their published decimal values. Positive
    steps have no civil candidate; negative steps may have two. Keep those
    conditions explicit instead of choosing an offset from a rounded label.
    """
    entries = _entries()
    intervals = []
    for index, row in enumerate(entries):
        start_date = _date(row["effective_date"])
        stop_date = _date(
            entries[index + 1]["effective_date"]
            if index + 1 < len(entries)
            else historical_utc_table()["valid_until"]
        )
        start = Fraction(start_date.toordinal()) + Fraction(3442849, 2)
        stop = Fraction(stop_date.toordinal()) + Fraction(3442849, 2)
        rate = Fraction(str(row["rate_seconds_per_day"]))
        offset = Fraction(str(row["offset_seconds"]))
        reference = Fraction(str(row["reference_mjd"])) + Fraction(4800001, 2)
        base = Fraction(4023, 125) + offset
        start_tt = start + (base + (start - reference) * rate) / 86400
        stop_tt = stop + (base + (stop - reference) * rate) / 86400
        intervals.append((start, stop, start_tt, stop_tt, rate))
    modern = Fraction(_date(historical_utc_table()["valid_until"]).toordinal())
    modern += Fraction(3442849, 2) + Fraction(5273, 125) / 86400
    if not intervals[0][2] <= point.days < modern:
        return None
    candidates = [
        start + (point.days - first) / (1 + rate / 86400)
        for start, stop, first, last, rate in intervals
        if first <= point.days < last
    ]
    if len(candidates) != 1:
        raise HistoricalUTCAdjustment(
            "TT lies in a historical fractional UTC adjustment without a unique datetime label"
        )
    micros = round((candidates[0] - Fraction(4881175, 2)) * 86_400_000_000)
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=micros)
