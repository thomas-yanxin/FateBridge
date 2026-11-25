"""Moshier mean lunar node with the published DE431 secular correction.

This theoretical point is defined by adjusted mean elements and smoothing;
JPL does not supply an observed mean-node record. Parameters are transcribed
from the cited model, not fitted to FateBridge's comparison residuals.
"""

from __future__ import annotations

import hashlib
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
    source_url: str
    source_native_version: str
    method_reference_url: str
    node_polynomial_arcseconds: list[str]
    correction: SecularCorrection


COEFFICIENT_SHA256 = "e8101129bb78d737f8845169974d40cfb1b49e2a33c70657903ce5aca2625497"
_RAW = (
    Path(__file__).resolve().parents[2] / "data/astronomy/mean-lunar-node-v1.json"
).read_bytes()
if hashlib.sha256(_RAW).hexdigest() != COEFFICIENT_SHA256:
    raise RuntimeError("Mean-node parameters differ from the declared source")
_DATA: MeanNodeParameters = json.loads(_RAW)
MODEL_ID = _DATA["model_id"]
SOURCE_URL = _DATA["method_reference_url"]
SOURCE_CODE_URL = _DATA["source_url"]
SOURCE_NATIVE_VERSION = _DATA["source_native_version"]
_COEFFICIENTS = tuple(map(float, _DATA["node_polynomial_arcseconds"]))
_CORRECTION = _DATA["correction"]
_ORIGIN = Fraction(_CORRECTION["epoch_jd_tt"])
_STEP = Fraction(_CORRECTION["step_days"])
_VALUES = tuple(map(Fraction, _CORRECTION["values_degrees"]))
_START = float(_CORRECTION["model_start_jd_tt"])
_END = float(_CORRECTION["model_end_jd_tt"])


def mean_lunar_node(
    julian_day_tt: float | TTInstant, *, include_nutation: bool = True
) -> dict[str, float]:
    point = TTInstant.from_value(julian_day_tt)
    if not _START <= point.days <= _END:
        raise ValueError("Mean lunar node TT is outside the sourced model range")
    t = float((point.days - 2451545) / 36525)
    longitude = _COEFFICIENTS[-1]
    derivative = 0.0
    for coefficient in reversed(_COEFFICIENTS[:-1]):
        derivative = derivative * t + longitude
        longitude = longitude * t + coefficient
    # Exact segment membership also distinguishes immediately adjacent floats
    # at the published rational knots. The source's float quotient can round
    # those distinct epochs onto a knot and misidentify its derivative.
    index, remainder = divmod(point.days - _ORIGIN, _STEP)
    difference = _VALUES[index + 1] - _VALUES[index]
    correction = _VALUES[index] + remainder / _STEP * difference
    longitude = longitude / 3600.0 - float(correction)
    rate = derivative / (3600.0 * 36525.0) - float(difference / _STEP)
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
    if remainder or difference == _VALUES[index] - _VALUES[index - 1]:
        state["longitude_speed"] = rate
    # At a genuine correction-slope corner there is no unique instantaneous
    # derivative. The coordinate stays defined; motion remains unavailable.
    return state
