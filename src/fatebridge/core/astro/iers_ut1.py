"""Pinned IERS20 C04 with the versioned IERS 2010 printed-table model.

The clock interpolates regularized UT1-TAI on continuous TT. Orientation
uses the supplied TT/UT1 pair; it does not establish another time source.
Published formal errors and numerical residuals are not physical bounds.
"""

from __future__ import annotations

import gzip
import math
from bisect import bisect_right
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date, datetime, timezone
from fractions import Fraction
from functools import lru_cache
from importlib.resources import files
from typing import Iterator, Literal, Protocol

from pydantic import TypeAdapter
from typing_extensions import TypedDict

from fatebridge.core.astro.historical_utc import historical_tai_minus_utc_exact
from fatebridge.core.astro.iers_tides2010 import MODEL as TIDAL_MODEL
from fatebridge.core.astro.iers_tides2010 import subdaily_eop, zonal_ut1
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.core.astro.utc_policy import leap_table

ASSET = "iers-c04-ut1-v1.json.gz"
ORIENTATION_ASSET = "iers-c04-orientation-v1.json.gz"
METHOD = "iers20_c04_lagrange4_zonal62_subdaily2010_tt_ut1_v2"
TT_MINUS_TAI = Fraction(4023, 125)
SOLVER_SECONDS = Fraction(1, 10**13)
TT_GRID = 2**64
_Indices = tuple[int, int, int, int]
_Weights = tuple[Fraction, Fraction, Fraction, Fraction]


class _Commit(TypedDict):
    sha: str
    date: str


class _Mirror(TypedDict):
    commit: _Commit


class _UT1Data(TypedDict):
    format_version: Literal[1]
    source_kind: str
    mirror: _Mirror
    records: tuple[tuple[int, str, str], ...]


class _OrientationData(TypedDict):
    format_version: Literal[1]
    columns: tuple[str, str, str, str, str]
    reference_model: str
    cpo_application_policy: str
    records: tuple[tuple[int, str, str, str, str], ...]


class C04Receipt(TypedDict):
    method_id: str
    source_series: str
    tidal_model_id: str
    mirror_commit: str
    coverage_start_utc: str
    coverage_end_utc: str
    published_daily_records: int
    query_julian_day_tt: float
    query_julian_day_ut1: float
    numerical_jd_resolution_seconds: float
    source_mjd: list[int]
    source_ut1_minus_utc_seconds: list[float]
    source_formal_sigma_seconds: list[float]
    interpolation_weights: list[float]
    interpolation_axis: str
    instant_value_kind: str
    ut1_minus_tai_seconds: float
    base_ut1_minus_tai_seconds: float
    zonal_ut1_seconds: float
    subdaily_ut1_seconds: float
    delta_t_seconds: float
    solver_residual_seconds: float
    solver_tolerance_seconds: float
    solver_iterations: int
    measured_ut1_series_applied: bool
    polar_motion_applied: bool
    celestial_pole_offsets_applied: bool
    subdaily_tides_applied: bool
    interpolation_error_bound_seconds: None
    absolute_accuracy_certified: bool
    epoch_scope: str
    scope: str


@dataclass(frozen=True)
class C04Sample:
    mjd: int
    dut1: Fraction
    sigma: float
    tai_offset: Fraction
    tt: TTInstant
    ut1: Fraction
    x_arcsec: Fraction
    y_arcsec: Fraction
    dx_arcsec: Fraction
    dy_arcsec: Fraction

    @property
    def ut1_tai(self) -> Fraction:
        return self.dut1 - self.tai_offset


class C04OrientationComponent(Protocol):
    def __call__(self, sample: C04Sample, /) -> Fraction: ...


@dataclass(frozen=True)
class C04Evaluation:
    tt: TTInstant
    ut1: Fraction
    indices: _Indices
    weights: _Weights
    ut1_tai: Fraction
    base_ut1_tai: Fraction
    zonal_ut1_seconds: float
    subdaily_ut1_seconds: float
    residual_seconds: Fraction
    iterations: int


@dataclass(frozen=True)
class C04Orientation:
    """Nonclock EOP; CPO is a qualified pair, never a value-based flag."""

    x_arcsec: float
    y_arcsec: float
    cpo_arcsec: tuple[float, float] | None


class C04Table:
    def __init__(self, data: _UT1Data, orientation: _OrientationData) -> None:
        policy = leap_table()
        entries = policy["entries"]
        samples: list[C04Sample] = []
        for record, pole in zip(data["records"], orientation["records"], strict=True):
            mjd, dut1_text, sigma_text = record
            pole_mjd, x, y, dx, dy = pole
            if pole_mjd != mjd:
                raise ValueError("IERS C04 orientation and clock rows disagree")
            day = date.fromordinal(mjd + 678576)
            stamp = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
            if stamp >= datetime.fromisoformat(policy["expires_at"]):
                raise ValueError("C04 dates exceed the frozen UTC leap policy")
            offset = (
                historical_tai_minus_utc_exact(stamp)
                if day.year < 1972
                else Fraction(
                    next(
                        row["tai_minus_utc_seconds"]
                        for row in reversed(entries)
                        if row["effective_date"] <= day.isoformat()
                    )
                )
            )
            if offset is None:
                raise ValueError("C04 sample lacks a supported TAI-UTC definition")
            dut1, sigma = Fraction(dut1_text), float(sigma_text)
            if not math.isfinite(sigma) or abs(dut1) > 2 or not 0 <= sigma < 1:
                raise ValueError("Invalid IERS C04 value or formal error")
            civil = Fraction(mjd) + Fraction(4800001, 2)
            samples.append(
                C04Sample(
                    mjd=mjd,
                    dut1=dut1,
                    sigma=sigma,
                    tai_offset=offset,
                    tt=TTInstant(civil + (offset + TT_MINUS_TAI) / 86400),
                    ut1=civil + dut1 / 86400,
                    x_arcsec=Fraction(x),
                    y_arcsec=Fraction(y),
                    dx_arcsec=Fraction(dx),
                    dy_arcsec=Fraction(dy),
                )
            )
        if len(samples) != 23638 or samples[0].mjd != 37665 or samples[-1].mjd != 61302:
            raise ValueError("Unexpected IERS C04 coverage")
        if any(
            b.mjd - a.mjd != 1 or b.tt.days <= a.tt.days or b.ut1 <= a.ut1
            for a, b in zip(samples, samples[1:])
        ):
            raise ValueError("IERS C04 time series is incomplete or nonmonotonic")
        self.samples = tuple(samples)
        self.tt = tuple(sample.tt.days for sample in samples)
        # Published UT1 locates an inverse bracket; it is not the modern axis.
        self.ut1 = tuple(sample.ut1 for sample in samples)
        self.mirror = data["mirror"]
        qualified_mjd = date(1984, 1, 1).toordinal() - 678576
        self.cpo_start = bisect_right(tuple(s.mjd for s in samples), qualified_mjd - 1)
        self.ut1_bounds = (
            self.evaluate(samples[0].tt).ut1,
            self.evaluate(samples[-1].tt).ut1,
        )

    def _window(self, value: Fraction, minimum: int = 0) -> tuple[_Indices, _Weights]:
        if not self.tt[minimum] <= value <= self.tt[-1]:
            raise ValueError(
                "IERS C04 source is unavailable outside its qualified TT support; "
                "no prediction, extrapolation or Swiss fallback was applied"
            )
        start = min(max(bisect_right(self.tt, value) - 2, minimum), len(self.tt) - 4)
        indices = (start, start + 1, start + 2, start + 3)
        weights: list[Fraction] = []
        for i in indices:
            weight = Fraction(1)
            for j in indices:
                if j != i:
                    weight *= (value - self.tt[j]) / (self.tt[i] - self.tt[j])
            weights.append(weight)
        return indices, (weights[0], weights[1], weights[2], weights[3])

    def _daily_base(
        self, point: TTInstant
    ) -> tuple[_Indices, _Weights, Fraction, float]:
        """Shared regularized Lagrange base with the same zonal model restored."""
        indices, weights = self._window(point.days)
        regularized = sum(
            (
                (self.samples[i].ut1_tai - Fraction(zonal_ut1(self.samples[i].tt))) * w
                for i, w in zip(indices, weights)
            ),
            Fraction(0),
        )
        zonal = zonal_ut1(point)
        return indices, weights, regularized + Fraction(zonal), zonal

    def evaluate(self, tt: float | TTInstant) -> C04Evaluation:
        point = TTInstant.from_value(tt)
        indices, weights, base_ut1_tai, zonal = self._daily_base(point)
        base = point.days + (base_ut1_tai - TT_MINUS_TAI) / 86400
        value = base
        for iteration in range(1, 9):
            subdaily = subdaily_eop(point, UT1Instant(value)).ut1_seconds
            updated = base + Fraction(subdaily) / 86400
            residual = abs(updated - value) * 86400
            if residual <= SOLVER_SECONDS:
                return C04Evaluation(
                    tt=point,
                    ut1=value,
                    indices=indices,
                    weights=weights,
                    ut1_tai=(value - point.days) * 86400 + TT_MINUS_TAI,
                    base_ut1_tai=base_ut1_tai,
                    zonal_ut1_seconds=zonal,
                    subdaily_ut1_seconds=subdaily,
                    residual_seconds=residual,
                    iterations=iteration,
                )
            value = updated
        raise ValueError("IERS C04 subdaily UT1 fixed point did not converge")

    def ut1_from_tt(self, tt: float | TTInstant) -> float:
        return float(self.evaluate(tt).ut1)

    def tt_from_ut1(self, ut1: float | Fraction | UT1Instant) -> TTInstant:
        """Solve the original pair equation at the exact supplied UT1.

        Bounds are the forward solver's numerical source endpoints, not a
        claim of exact physical endpoints or additional source coverage.
        """
        if isinstance(ut1, UT1Instant):
            value = ut1.days
        elif isinstance(ut1, Fraction):
            value = ut1
        else:
            value = UT1Instant.from_float(ut1).days
        lower, upper = self.ut1_bounds
        if not lower <= value <= upper:
            raise ValueError("IERS C04 UT1 is outside the modern forward source bounds")
        if value == lower:
            return self.samples[0].tt
        if value == upper:
            return self.samples[-1].tt
        given = UT1Instant(value)

        def residual(tt: Fraction) -> Fraction:
            point = TTInstant(tt)
            _, _, base_ut1_tai, _ = self._daily_base(point)
            subdaily = Fraction(subdaily_eop(point, given).ut1_seconds)
            return (tt - value) * 86400 + base_ut1_tai - TT_MINUS_TAI + subdaily

        index = min(max(bisect_right(self.ut1, value) - 1, 0), len(self.tt) - 1)
        lo = self.tt[max(index - 1, 0)]
        hi = self.tt[min(index + 2, len(self.tt) - 1)]
        r_lo, r_hi = residual(lo), residual(hi)
        if not r_lo <= 0 <= r_hi:
            lo, hi = self.tt[0], self.tt[-1]
            r_lo, r_hi = residual(lo), residual(hi)
        if abs(r_lo) <= SOLVER_SECONDS:
            return TTInstant(lo)
        if abs(r_hi) <= SOLVER_SECONDS:
            return TTInstant(hi)
        if not r_lo <= 0 <= r_hi:
            raise ValueError("IERS C04 inverse could not bracket its pair equation")
        for _ in range(32):
            trial = lo - r_lo * (hi - lo) / (r_hi - r_lo)
            trial = min(max(Fraction(round(trial * TT_GRID), TT_GRID), lo), hi)
            if trial == lo or trial == hi:
                midpoint = Fraction(round((lo + hi) * TT_GRID / 2), TT_GRID)
                trial = min(max(midpoint, lo), hi)
            error = residual(trial)
            if abs(error) <= SOLVER_SECONDS:
                return TTInstant(trial)
            if error < 0:
                lo, r_lo = trial, error
            else:
                hi, r_hi = trial, error
        raise ValueError("IERS C04 inverse TT solver did not converge")

    def orientation(
        self, tt: float | TTInstant, ut1: float | UT1Instant
    ) -> C04Orientation:
        """Interpolate nonclock EOP at the supplied canonical pair.

        CPO application begins with source-qualified year1984 nodes. This
        policy does not identify each zero as measured, nor interpret the
        unqualified semantics of pre1984 CPO columns. Every window encloses TT.
        """
        point = TTInstant.from_value(tt)
        pole_window = self._window(point.days)
        subdaily = subdaily_eop(point, UT1Instant.from_value(ut1))

        def interpolate(
            window: tuple[_Indices, _Weights],
            component: C04OrientationComponent,
        ) -> float:
            indices, weights = window
            return float(
                sum(
                    (component(self.samples[i]) * w for i, w in zip(indices, weights)),
                    Fraction(0),
                )
            )

        x = interpolate(pole_window, lambda sample: sample.x_arcsec)
        y = interpolate(pole_window, lambda sample: sample.y_arcsec)
        cpo: tuple[float, float] | None = None
        if point.days >= self.tt[self.cpo_start]:
            cpo_window = self._window(point.days, self.cpo_start)
            cpo = (
                interpolate(cpo_window, lambda sample: sample.dx_arcsec),
                interpolate(cpo_window, lambda sample: sample.dy_arcsec),
            )
        return C04Orientation(x + subdaily.x_arcsec, y + subdaily.y_arcsec, cpo)

    def receipt(self, tt: float | TTInstant, ut1: float | UT1Instant) -> C04Receipt:
        evaluation = self.evaluate(tt)
        point = UT1Instant.from_value(ut1)
        if abs(evaluation.ut1 - point.days) * 86400 > Fraction(1, 5000):
            raise ValueError("Chart UT1 and selected IERS C04 source disagree")
        if point.days == evaluation.ut1:
            ut1_tai = evaluation.ut1_tai
            subdaily = evaluation.subdaily_ut1_seconds
            residual = evaluation.residual_seconds
        else:
            ut1_tai = (point.days - evaluation.tt.days) * 86400 + TT_MINUS_TAI
            subdaily = subdaily_eop(evaluation.tt, point).ut1_seconds
            residual = abs(ut1_tai - evaluation.base_ut1_tai - Fraction(subdaily))
        nodes = [self.samples[i] for i in evaluation.indices]
        scalar_tt, scalar_ut1 = evaluation.tt.as_float(), point.as_float()
        return {
            "method_id": METHOD,
            "source_series": "IERS20_C04_final_smoothed_daily_0hUTC_ITRF2020",
            "tidal_model_id": TIDAL_MODEL,
            "mirror_commit": self.mirror["commit"]["sha"],
            "coverage_start_utc": "1962-01-01T00:00:00+00:00",
            "coverage_end_utc": "2026-09-19T00:00:00+00:00",
            "published_daily_records": len(self.samples),
            "query_julian_day_tt": scalar_tt,
            "query_julian_day_ut1": scalar_ut1,
            "numerical_jd_resolution_seconds": (
                max(math.ulp(scalar_tt), math.ulp(scalar_ut1)) * 86400
            ),
            "source_mjd": [node.mjd for node in nodes],
            "source_ut1_minus_utc_seconds": [float(node.dut1) for node in nodes],
            "source_formal_sigma_seconds": [node.sigma for node in nodes],
            "interpolation_weights": [float(w) for w in evaluation.weights],
            "interpolation_axis": "continuous_TT_regularized_UT1_minus_TAI_Lagrange4",
            "instant_value_kind": "daily_regularized_base_plus_instantaneous_model_terms",
            "ut1_minus_tai_seconds": float(ut1_tai),
            "base_ut1_minus_tai_seconds": float(evaluation.base_ut1_tai),
            "zonal_ut1_seconds": evaluation.zonal_ut1_seconds,
            "subdaily_ut1_seconds": subdaily,
            "delta_t_seconds": float(TT_MINUS_TAI - ut1_tai),
            "solver_residual_seconds": float(residual),
            "solver_tolerance_seconds": float(SOLVER_SECONDS),
            "solver_iterations": evaluation.iterations,
            "measured_ut1_series_applied": True,
            "polar_motion_applied": False,
            "celestial_pole_offsets_applied": False,
            "subdaily_tides_applied": True,
            "interpolation_error_bound_seconds": None,
            "absolute_accuracy_certified": False,
            "epoch_scope": (
                "UT1-dependent epochs require source coverage without extrapolation or fallback; "
                "geocentric TT positions and longitude-event trials do not require UT1."
            ),
            "scope": (
                "Published daily UT1-TAI with four-point TT interpolation after removing "
                "the 62-term zonal model, then restoring it and adding ocean71 and UT1 "
                "libration11 once. The base already includes restored Z62; do not add "
                "the explanatory zonal field again. UT1-TAI, delta T and the reported "
                "equation residual use the retained exact TT/UT1 pair and its subdaily "
                "correction, before display rounding. Tolerance and iterations describe "
                "the forward solve used to check source agreement. A separately supplied "
                "UT1 can give a residual above that tolerance. "
                "Numerical residuals and formal errors are not physical "
                "error bounds. This time receipt does not claim polar motion or CPO was "
                "consumed by geometry. UTC steps/drift use the frozen atomic-offset policy. "
                "Scalar JD fields are native/display projections of retained exact points."
            ),
        }


@lru_cache(maxsize=1)
def c04_table() -> C04Table:
    resource = files("fatebridge.data").joinpath("knowledge")
    raw = resource.joinpath(ASSET).read_bytes()
    orientation = resource.joinpath(ORIENTATION_ASSET).read_bytes()
    return C04Table(
        TypeAdapter(_UT1Data).validate_json(gzip.decompress(raw)),
        TypeAdapter(_OrientationData).validate_json(gzip.decompress(orientation)),
    )


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


def ut1_reference(
    tt: float | TTInstant | None, ut1: float | UT1Instant | None
) -> C04Receipt | None:
    selected = active_ut1.get()
    if selected is None or tt is None or ut1 is None:
        return None
    return selected.receipt(tt, ut1)
