"""Continuous full Moshier Moon geometry with stable secular arguments.

The coefficient packet records the default mathematical series published in
swemmoon.c, including its zeroed fifth latitude harmonic. This evaluator sums
the Fourier terms directly; Decimal reduces large secular angles before they
enter binary64 trigonometry. It is an auxiliary source-arithmetic model, not a
new physical ephemeris or a change to displayed native positions.
"""

from __future__ import annotations

import hashlib
import json
import math
from decimal import ROUND_FLOOR, Decimal, localcontext
from functools import lru_cache
from importlib.resources import files
from typing import TypedDict

from fatebridge.core.astro import reference_frames

METHOD_ID = "moshier_full_lunar_secular_argument_precision_v1"
COEFFICIENT_SHA256 = "e2c93a63e58243949792e2ed3f600635e8934ce945df1e2b04981f23404efcda"
SOURCE_URL = "https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/swemmoon.c"


class MeanElement(TypedDict):
    before_modulo: list[str]
    fractional_century_frequency: str
    secular: list[str]


class FourierTerm(TypedDict):
    axis: int
    kind: str
    factors: list[int]
    phase_arcsec: float
    coefficients: list[float]


class LunarCoefficients(TypedDict):
    angle_names: list[str]
    mean_elements: dict[str, MeanElement]
    terms: list[FourierTerm]
    STR: float
    AU: float
    radius_constant_km: float


_RAW = (
    files("fatebridge.data")
    .joinpath("astro/moshier-lunar-coefficients-v1.json")
    .read_bytes()
)
if hashlib.sha256(_RAW).hexdigest() != COEFFICIENT_SHA256:
    raise RuntimeError("Moshier lunar coefficients differ from the declared source")
_DATA: LunarCoefficients = json.loads(_RAW)


def _coefficient(value: str) -> Decimal:
    numerator, _, denominator = value.partition("/")
    return Decimal(numerator) / Decimal(denominator or "1")


with localcontext() as _context:
    _context.prec = 50
    _MEAN = {
        name: (
            _coefficient(element["fractional_century_frequency"]),
            tuple(_coefficient(v) for v in element["before_modulo"]),
            tuple(_coefficient(v) for v in element["secular"]),
        )
        for name, element in _DATA["mean_elements"].items()
    }


@lru_cache(maxsize=4096)
def polar(epoch: float) -> tuple[float, float, float]:
    """Mean ecliptic/equinox of date: longitude/latitude radians and AU."""
    with localcontext() as context:
        context.prec = 50
        t = (Decimal.from_float(epoch) - 2451545) / 36525
        fraction = t - int(t)
        cycle = Decimal(1296000)
        angles = []
        for name in _DATA["angle_names"]:
            frequency, base, secular = _MEAN[name]
            parts = []
            for coefficients in (base, secular):
                value = Decimal(0)
                for coefficient in reversed(coefficients):
                    value = value * t + coefficient
                parts.append(value)
            value = parts[0] + frequency * fraction
            value -= cycle * (value / cycle).to_integral_value(rounding=ROUND_FLOOR)
            angles.append(float(value + parts[1]))
    century = float(t)
    sums: list[list[float]] = [[], [], []]
    for term in _DATA["terms"]:
        argument = _DATA["STR"] * math.fsum(
            [term["phase_arcsec"]]
            + [factor * angle for factor, angle in zip(term["factors"], angles)]
        )
        amplitude = 0.0
        for series_coefficient in reversed(term["coefficients"]):
            amplitude = amplitude * century + series_coefficient
        sums[term["axis"]].append(
            amplitude
            * (math.sin(argument) if term["kind"] == "sin" else math.cos(argument))
        )
    longitude = (angles[-1] + math.fsum(sums[0])) % 1296000 * _DATA["STR"]
    latitude = math.fsum(sums[1]) * _DATA["STR"]
    radius = (_DATA["radius_constant_km"] + math.fsum(sums[2])) * 1000 / _DATA["AU"]
    return longitude, latitude, radius


def equatorial(epoch: float, reception: float) -> list[Decimal]:
    """Source equatorial J2000 vector with the reception obliquity retained.

    swi_moshmoon fixes that obliquity while its three-point source-speed
    operator changes the lunar epoch and precession. Reuse the checked common
    Vondrak frame, including the original exact-J2000 identity shortcut.
    """
    longitude, latitude, radius = polar(epoch)
    ecliptic = (
        radius * math.cos(latitude) * math.cos(longitude),
        radius * math.cos(latitude) * math.sin(longitude),
        radius * math.sin(latitude),
    )
    epsilon = reference_frames.pair(reception, "pepol", "peper")[0][1]
    to_equator = reference_frames.transpose(
        reference_frames.ecliptic_rotation(epsilon)[0]
    )
    date_equator = reference_frames.mv(to_equator, ecliptic)
    fixed = reference_frames.mv(
        reference_frames.transpose(reference_frames.native_precession_frame(epoch)),
        date_equator,
    )
    return [Decimal.from_float(value) for value in fixed]
