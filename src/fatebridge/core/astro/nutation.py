"""Shared 77-term nutation and analytic TT derivatives.

The pinned variant uses full Simon polynomial arguments, as documented in its
parameter file. This is the native 2.10.03 model, not a new physical error bound.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import TypedDict

from fatebridge.core.astro.tt_epoch import TTInstant


class NutationParameters(TypedDict):
    terms: list[list[str]]
    fundamental_arcseconds: list[list[str]]


RAW = (
    Path(__file__).resolve().parents[2] / "data/astronomy/swiss-nutation77-v1.json"
).read_bytes()
DATA: NutationParameters = json.loads(RAW)
TERMS = tuple(tuple(map(float, row)) for row in DATA["terms"])
FUNDAMENTAL = tuple(tuple(map(float, row)) for row in DATA["fundamental_arcseconds"])
AS2R = math.pi / 648000.0


def nutation(epoch: float | TTInstant) -> tuple[float, float, float, float]:
    """dpsi,deps in degrees and analytic derivatives per TT argument day."""
    t = float((TTInstant.from_value(epoch).days - 2451545) / 36525)
    phases = []
    rates = []
    for polynomial in FUNDAMENTAL:
        angle = polynomial[-1]
        derivative = 0.0
        for coefficient in reversed(polynomial[:-1]):
            derivative = derivative * t + angle
            angle = angle * t + coefficient
        phases.append(math.remainder(angle, 1296000.0) * AS2R)
        rates.append(derivative * AS2R / 36525.0)
    values: list[list[float]] = [[], [], [], []]
    for row in reversed(TERMS):
        phase = math.remainder(
            math.fsum(n * a for n, a in zip(row[:5], phases)), math.tau
        )
        rate = math.fsum(n * a for n, a in zip(row[:5], rates))
        s, c = math.sin(phase), math.cos(phase)
        ps, pst, pc, ec, ect, es = row[5:]
        values[0].append((ps + pst * t) * s + pc * c)
        values[1].append((ec + ect * t) * c + es * s)
        values[2].append(pst / 36525.0 * s + ((ps + pst * t) * c - pc * s) * rate)
        values[3].append(ect / 36525.0 * c + (-(ec + ect * t) * s + es * c) * rate)
    factor = 10000000.0 * 3600.0
    return (
        math.fsum(values[0]) / factor,
        math.fsum(values[1]) / factor,
        math.fsum(values[2]) / factor,
        math.fsum(values[3]) / factor,
    )
