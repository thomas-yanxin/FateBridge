"""Full geocentric ERFA Fairhead TDB-TT series, independent of orbit files.

The 787 original terms and mass corrections implement eraDtdb with zero
observer coordinates. ERFA/SOFA conditions are in data/astronomy/erfa-license.txt.
The author's 1950-2050 comparison does not certify arbitrary civil epochs.
"""

from __future__ import annotations

import json
import math
from fractions import Fraction
from functools import lru_cache
from importlib.resources import files
from typing import NamedTuple, Sequence, TypedDict


class Parameters(TypedDict):
    fairhead_terms: list[list[float]]


class TimeOffset(NamedTuple):
    seconds: float
    rate_seconds_per_TT_day: float


@lru_cache(maxsize=1)
def _parameters() -> Parameters:
    raw = (
        files("fatebridge")
        .joinpath("data/astronomy/geocentric-tdb-v1.json")
        .read_bytes()
    )
    data: Parameters = json.loads(raw)
    return data


def fairhead_state(
    days_from_j2000: float | Fraction, rows: Sequence[Sequence[float]]
) -> TimeOffset:
    """Original geocentric seconds and analytic rate per TT argument day."""
    t = float(Fraction(days_from_j2000) / 365250)
    sums, rates = [], []
    sin, cos = math.sin, math.cos
    for low, high in ((0, 474), (474, 679), (679, 764), (764, 784), (784, 787)):
        value = rate = 0.0
        for a, f, phase in reversed(rows[low:high]):
            angle = f * t + phase
            value += a * sin(angle)
            rate += a * f * cos(angle)
        sums.append(value)
        rates.append(rate)
    w0, w1, w2, w3, w4 = sums
    fairhead = t * (t * (t * (t * w4 + w3) + w2) + w1) + w0
    value, derivative = sums[-1], rates[-1]
    for w, wd in reversed(list(zip(sums[:-1], rates[:-1]))):
        derivative = derivative * t + value + wd
        value = value * t + w
    masses = (
        0.00065e-6 * sin(6069.776754 * t + 4.021194)
        + 0.00033e-6 * sin(213.299095 * t + 5.543132)
        - 0.00196e-6 * sin(6208.294251 * t + 5.696701)
        - 0.00173e-6 * sin(74.781599 * t + 2.435900)
        + 0.03638e-6 * t * t
    )
    mass_rate = (
        0.00065e-6 * 6069.776754 * cos(6069.776754 * t + 4.021194)
        + 0.00033e-6 * 213.299095 * cos(213.299095 * t + 5.543132)
        - 0.00196e-6 * 6208.294251 * cos(6208.294251 * t + 5.696701)
        - 0.00173e-6 * 74.781599 * cos(74.781599 * t + 2.435900)
        + 2 * 0.03638e-6 * t
    )
    return TimeOffset(fairhead + masses, (derivative + mass_rate) / 365250.0)


def geocentric_tdb_state(
    days_from_j2000: float | Fraction, *, need_rate: bool = True
) -> TimeOffset:
    """Geocentric TDB-TT and its TT derivative, without loading any orbits."""
    if not math.isfinite(days_from_j2000):
        raise ValueError("TT relative epoch must be finite")
    rows = _parameters()["fairhead_terms"]
    if not need_rate:
        t = float(Fraction(days_from_j2000) / 365250)
        return TimeOffset(_fairhead_seconds(t, rows), 0.0)
    return fairhead_state(days_from_j2000, rows)


def fairhead_seconds(
    days_from_j2000: float | Fraction, rows: Sequence[Sequence[float]]
) -> float:
    """Original geocentric seconds without rate terms."""
    return _fairhead_seconds(float(Fraction(days_from_j2000) / 365250), rows)


def _fairhead_seconds(t: float, rows: Sequence[Sequence[float]]) -> float:
    sin = math.sin
    sums = []
    for low, high in ((0, 474), (474, 679), (679, 764), (764, 784), (784, 787)):
        value = 0.0
        for a, f, phase in reversed(rows[low:high]):
            value += a * sin(f * t + phase)
        sums.append(value)
    w0, w1, w2, w3, w4 = sums
    fairhead = t * (t * (t * (t * w4 + w3) + w2) + w1) + w0
    masses = (
        0.00065e-6 * sin(6069.776754 * t + 4.021194)
        + 0.00033e-6 * sin(213.299095 * t + 5.543132)
        - 0.00196e-6 * sin(6208.294251 * t + 5.696701)
        - 0.00173e-6 * sin(74.781599 * t + 2.435900)
        + 0.03638e-6 * t * t
    )
    return fairhead + masses
