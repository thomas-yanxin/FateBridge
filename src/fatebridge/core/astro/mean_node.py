"""Moshier mean lunar node with the published DE431 secular correction.

This theoretical point is defined by adjusted mean elements and smoothing;
JPL does not supply an observed mean-node record. Parameters are transcribed
from the cited model, not fitted to FateBridge's comparison residuals.
"""

from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path
from typing import TypedDict

from fatebridge.core.astro.nutation import nutation
from fatebridge.core.astro.reference_frames import (
    pair,
)
from fatebridge.core.astro.tt_epoch import TTInstant


class SecularCorrection(TypedDict):
    epoch_jd_tt: str
    step_days: str
    model_start_jd_tt: str
    model_end_jd_tt: str
    values_degrees: list[str]


class MeanNodeParameters(TypedDict):
    model_id: str
    source_native_version: str
    node_polynomial_arcseconds: list[str]
    correction: SecularCorrection


RAW = (
    Path(__file__).resolve().parents[2] / "data/astronomy/mean-lunar-node-v1.json"
).read_bytes()
DATA: MeanNodeParameters = json.loads(RAW)
MODEL_ID = DATA["model_id"]
SOURCE_NATIVE_VERSION = DATA["source_native_version"]
COEFFICIENTS = tuple(map(float, DATA["node_polynomial_arcseconds"]))
CORRECTION = DATA["correction"]
ORIGIN = Fraction(CORRECTION["epoch_jd_tt"])
STEP = Fraction(CORRECTION["step_days"])
VALUES = tuple(map(Fraction, CORRECTION["values_degrees"]))
START = float(CORRECTION["model_start_jd_tt"])
END = float(CORRECTION["model_end_jd_tt"])


def mean_lunar_node(
    julian_day_tt: float | TTInstant, *, include_nutation: bool = True
) -> dict[str, float]:
    point = TTInstant.from_value(julian_day_tt)
    if not START <= point.days <= END:
        raise ValueError("Mean lunar node TT is outside the sourced model range")
    t = float((point.days - 2451545) / 36525)
    longitude = COEFFICIENTS[-1]
    derivative = 0.0
    for coefficient in reversed(COEFFICIENTS[:-1]):
        derivative = derivative * t + longitude
        longitude = longitude * t + coefficient
    # Exact segment membership also distinguishes immediately adjacent floats
    # at the published rational knots. The source's float quotient can round
    # those distinct epochs onto a knot and misidentify its derivative.
    index, remainder = divmod(point.days - ORIGIN, STEP)
    difference = VALUES[index + 1] - VALUES[index]
    correction = VALUES[index] + remainder / STEP * difference
    longitude = longitude / 3600.0 - float(correction)
    rate = derivative / (3600.0 * 36525.0) - float(difference / STEP)
    obliquity = pair(point, "pepol", "peper")[0][1]
    if include_nutation:
        psi, deps, psi_rate, _ = nutation(point)
        longitude += psi
        rate += psi_rate
        obliquity += math.radians(deps)
    longitude %= 360.0
    state = {
        "longitude": longitude,
        "latitude": 0.0,
        "declination": math.degrees(
            math.asin(math.sin(obliquity) * math.sin(math.radians(longitude)))
        ),
    }
    if remainder or difference == VALUES[index] - VALUES[index - 1]:
        state["longitude_speed"] = rate
    # At a genuine correction-slope corner there is no unique instantaneous
    # derivative. The coordinate stays defined; motion remains unavailable.
    return state
