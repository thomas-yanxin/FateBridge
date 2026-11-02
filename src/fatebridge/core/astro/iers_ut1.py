"""Explicit IERS C04 UT1 time source, pinned for one calculation context.

Only UT1 is applied here. Polar motion, CIP offsets and subdaily tidal terms
are separate corrections. Published formal errors are not physical bounds.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from bisect import bisect_right
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date, datetime, timezone
from functools import lru_cache
from importlib.resources import files
from typing import Any, Iterator

ASSET = "iers-c04-ut1-v1.json.gz"
ASSET_SHA = "756a854e7c01770ad87f0956aedab4aa4d071fc7a3008067363a389b075e7b7c"
SOURCE_SHA = "2f451f2b9faf42dc32f7368888980c92c3e773957019963c5d22df9ac20c8c82"
METHOD = "iers20_c04_ut1_tai_linear_tt_v1"


@dataclass(frozen=True)
class C04Sample:
    mjd: int
    dut1: float
    sigma: float
    tai_offset: float
    tt: float
    ut1: float

    @property
    def ut1_tai(self) -> float:
        return self.dut1 - self.tai_offset


class C04Table:
    def __init__(self, data: dict[str, Any]) -> None:
        from fatebridge.core.astro.historical_utc import historical_tai_minus_utc
        from fatebridge.core.astro.utc_policy import leap_table

        if data.get("format_version") != 1 or data.get("source_sha256") != SOURCE_SHA:
            raise ValueError("IERS C04 asset identity mismatch")
        entries = leap_table()["entries"]
        samples = []
        for mjd, dut1_text, sigma_text in data["records"]:
            if type(mjd) is not int:
                raise ValueError("IERS C04 MJD must be an integer")
            day = date.fromordinal(mjd + 678576)
            stamp = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
            if stamp >= datetime.fromisoformat(leap_table()["expires_at"]):
                raise ValueError("C04 dates exceed the frozen UTC leap policy")
            offset = (
                historical_tai_minus_utc(stamp)
                if day.year < 1972
                else next(
                    r["tai_minus_utc_seconds"]
                    for r in reversed(entries)
                    if r["effective_date"] <= day.isoformat()
                )
            )
            if offset is None:
                raise ValueError("C04 sample lacks a supported TAI-UTC definition")
            dut1, sigma = float(dut1_text), float(sigma_text)
            if (
                not all(math.isfinite(x) for x in (dut1, sigma, offset))
                or abs(dut1) > 2
                or not 0 <= sigma < 1
            ):
                raise ValueError("Invalid IERS C04 value or formal error")
            civil = mjd + 2400000.5
            samples.append(
                C04Sample(
                    mjd,
                    dut1,
                    sigma,
                    float(offset),
                    civil + (offset + 32.184) / 86400,
                    civil + dut1 / 86400,
                )
            )
        if len(samples) != 23638 or samples[0].mjd != 37665 or samples[-1].mjd != 61302:
            raise ValueError("Unexpected IERS C04 coverage")
        if any(
            b.mjd - a.mjd != 1 or b.tt <= a.tt or b.ut1 <= a.ut1
            for a, b in zip(samples, samples[1:])
        ):
            raise ValueError("IERS C04 time series is incomplete or nonmonotonic")
        self.samples = tuple(samples)
        self.tt = tuple(s.tt for s in samples)
        self.ut1 = tuple(s.ut1 for s in samples)
        self.mirror = dict(data["mirror"])

    def _bracket(self, value: float, axis: tuple[float, ...]) -> tuple[int, int]:
        if not math.isfinite(value):
            raise ValueError("IERS C04 query epoch must be finite")
        if not axis[0] <= value <= axis[-1]:
            raise ValueError(
                "IERS C04 UT1 source is unavailable outside 1962-01-01T00:00UTC through 2026-09-19T00:00UTC; no prediction, extrapolation or Swiss fallback was applied"
            )
        i = bisect_right(axis, value) - 1
        return (i, i) if value == axis[i] else (i, i + 1)

    def evaluate(self, tt: float) -> tuple[float, tuple[int, int], float, float]:
        i, j = self._bracket(tt, self.tt)
        a, b = self.samples[i], self.samples[j]
        weight = 0.0 if i == j else (tt - a.tt) / (b.tt - a.tt)
        ut1_tai = a.ut1_tai + (b.ut1_tai - a.ut1_tai) * weight
        # Reproduce a published sample directly, avoiding cancellation of a
        # large JD against the small TT/UT1 offset at the exact anchor.
        ut1 = a.ut1 if i == j else tt + (ut1_tai - 32.184) / 86400
        return ut1, (i, j), weight, ut1_tai

    def ut1_from_tt(self, tt: float) -> float:
        return self.evaluate(tt)[0]

    def tt_from_ut1(self, ut1: float) -> float:
        i, j = self._bracket(ut1, self.ut1)
        a, b = self.samples[i], self.samples[j]
        if i == j:
            return a.tt
        tt = a.tt + (ut1 - a.ut1) * (b.tt - a.tt) / (b.ut1 - a.ut1)
        for _ in range(4):
            updated = tt + (ut1 - self.ut1_from_tt(tt))
            if updated == tt:
                break
            tt = updated
        if abs(self.ut1_from_tt(tt) - ut1) * 86400 > 0.0002:
            raise ValueError("IERS C04 inverse failed its physical UT1 guard")
        return tt

    def receipt(self, tt: float, ut1: float) -> dict[str, Any]:
        value, (i, j), weight, continuous = self.evaluate(tt)
        if abs(value - ut1) * 86400 > 0.0002:
            raise ValueError("Chart UT1 and selected IERS C04 source disagree")
        a, b = self.samples[i], self.samples[j]
        return {
            "method_id": METHOD,
            "source_series": "IERS20_C04_final_smoothed_daily_0hUTC_ITRF2020",
            "source_sha256": SOURCE_SHA,
            "asset_sha256": ASSET_SHA,
            "source_url": self.mirror["canonical_origin"],
            "mirror_url": self.mirror["mirror_url"],
            "mirror_commit": self.mirror["commit"]["sha"],
            "coverage_start_utc": "1962-01-01T00:00:00+00:00",
            "coverage_end_utc": "2026-09-19T00:00:00+00:00",
            "published_daily_records": len(self.samples),
            "query_julian_day_tt": tt,
            "query_julian_day_ut1": ut1,
            "numerical_jd_resolution_seconds": max(math.ulp(tt), math.ulp(ut1)) * 86400,
            "source_mjd": [a.mjd, b.mjd],
            "source_ut1_minus_utc_seconds": [a.dut1, b.dut1],
            "source_formal_sigma_seconds": [a.sigma, b.sigma],
            "interpolation_weight": weight,
            "instant_value_kind": (
                "published_daily_sample"
                if i == j
                else "interpolated_between_final_daily_samples"
            ),
            "ut1_minus_tai_seconds": continuous,
            "delta_t_seconds": 32.184 - continuous,
            "measured_ut1_series_applied": True,
            "polar_motion_applied": False,
            "celestial_pole_offsets_applied": False,
            "subdaily_tides_applied": False,
            "interpolation_error_bound_seconds": None,
            "absolute_accuracy_certified": False,
            "epoch_scope": "UT1-dependent epochs require source coverage without extrapolation or model fallback; geocentric TT positions and longitude events do not require UT1 at their trial epochs",
            "scope": "Published combined/smoothed daily UT1 series and declared interpolation, not an independent instantaneous observation, complete EOP transformation, physical error bound, source-clock identification or event prediction. UTC steps are removed through actual TAI-UTC, including pre1972 drift/adjustments. Formal errors are reported, not promoted to confidence bounds.",
        }


@lru_cache(maxsize=1)
def c04_table() -> C04Table:
    raw = files("fatebridge.data").joinpath("knowledge/" + ASSET).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ASSET_SHA:
        raise ValueError("IERS C04 packaged asset checksum mismatch")
    return C04Table(json.loads(gzip.decompress(raw)))


active_ut1: ContextVar[C04Table | None] = ContextVar(
    "fatebridge_ut1_source", default=None
)


@contextmanager
def use_ut1_source(source: str) -> Iterator[None]:
    if source not in {"swiss_delta_t", "iers_c04"}:
        raise ValueError("UT1 source must be swiss_delta_t or iers_c04")
    token = active_ut1.set(c04_table() if source == "iers_c04" else None)
    try:
        yield
    finally:
        active_ut1.reset(token)


def ut1_reference(tt: float | None, ut1: float | None) -> dict[str, Any] | None:
    selected = active_ut1.get()
    if selected is None or tt is None or ut1 is None:
        return None
    return selected.receipt(tt, ut1)
