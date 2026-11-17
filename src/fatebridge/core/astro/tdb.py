"""Full geocentric ERFA Fairhead TDB-TT series, independent of orbit files.

The 787 original terms and mass corrections implement eraDtdb with zero
observer coordinates. ERFA/SOFA conditions are in data/astronomy/erfa-license.txt.
The author's 1950-2050 comparison does not certify arbitrary civil epochs.
https://github.com/liberfa/erfa/blob/v2.0.1/src/dtdb.c
"""

from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from importlib.resources import files
from typing import NamedTuple, Sequence, TypedDict

SOURCE_URL = "https://github.com/liberfa/erfa/blob/v2.0.1/src/dtdb.c"
COEFFICIENT_SHA256 = "a092d8bd128309277135097c6cd29f2aed2e7abe03d51f9522890d97f49a7c25"


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
    if hashlib.sha256(raw).hexdigest() != COEFFICIENT_SHA256:
        raise RuntimeError("Geocentric TDB parameters differ from the declared source")
    data: Parameters = json.loads(raw)
    return data


def fairhead_state(
    days_from_j2000: float, rows: Sequence[Sequence[float]]
) -> TimeOffset:
    """Original geocentric seconds and analytic rate per TT argument day."""
    t = days_from_j2000 / 365250.0
    sums = []
    rates = []
    for low, high in [(0, 474), (474, 679), (679, 764), (764, 784), (784, 787)]:
        value = rate = 0.0
        for a, f, phase in reversed(rows[low:high]):
            angle = f * t + phase
            value += a * math.sin(angle)
            rate += a * f * math.cos(angle)
        sums.append(value)
        rates.append(rate)
    w0, w1, w2, w3, w4 = sums
    fairhead = t * (t * (t * (t * w4 + w3) + w2) + w1) + w0
    value, derivative = sums[-1], rates[-1]
    for w, wd in reversed(list(zip(sums[:-1], rates[:-1]))):
        derivative = derivative * t + value + wd
        value = value * t + w
    masses = (
        0.00065e-6 * math.sin(6069.776754 * t + 4.021194)
        + 0.00033e-6 * math.sin(213.299095 * t + 5.543132)
        - 0.00196e-6 * math.sin(6208.294251 * t + 5.696701)
        - 0.00173e-6 * math.sin(74.781599 * t + 2.435900)
        + 0.03638e-6 * t * t
    )
    mass_rate = (
        0.00065e-6 * 6069.776754 * math.cos(6069.776754 * t + 4.021194)
        + 0.00033e-6 * 213.299095 * math.cos(213.299095 * t + 5.543132)
        - 0.00196e-6 * 6208.294251 * math.cos(6208.294251 * t + 5.696701)
        - 0.00173e-6 * 74.781599 * math.cos(74.781599 * t + 2.435900)
        + 2 * 0.03638e-6 * t
    )
    return TimeOffset(fairhead + masses, (derivative + mass_rate) / 365250.0)


def geocentric_tdb_state(days_from_j2000: float) -> TimeOffset:
    """Geocentric TDB-TT and its TT derivative, without loading any orbits."""
    if not math.isfinite(days_from_j2000):
        raise ValueError("TT relative epoch must be finite")
    return fairhead_state(days_from_j2000, _parameters()["fairhead_terms"])
