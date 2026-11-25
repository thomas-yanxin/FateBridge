"""Versioned IERS 2010 printed-table corrections at explicit TT/UT1 points.

Chapter 5 (served revision 2012-08-10), Tables 5.1a/b, Eqs. 5.32/5.43;
Chapter 8, Tables 8.1/8.2/8.3. These are the published table coefficients,
not the different single-MJD/REAL*4 INTERP 2007 numerical operator.
https://iers-conventions.obspm.fr/content/chapter5/icc5.pdf
https://iers-conventions.obspm.fr/content/chapter8/icc8.pdf
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from importlib.resources import files
from typing import Literal

from pydantic import FiniteFloat, TypeAdapter
from typing_extensions import TypedDict

from fatebridge.core.astro.earth_rotation import _era_turn
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant

ASSET = "iers2010-eop-tides-v1.json"
ASSET_SHA = "b7e0dbfbee28ab3928671ba01e2d25247f04c04a187353e5aeed6457c543861a"
MODEL = "iers2010_printed_tables_20120810_tt_ut1_v1"

_Five = tuple[int, int, int, int, int]
_Six = tuple[int, int, int, int, int, int]
_Pair = tuple[FiniteFloat, FiniteFloat]
_Pole = tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]


class _OceanTerm(TypedDict):
    multipliers: _Six
    pole_microarcseconds: _Pole
    ut1_microseconds: _Pair
    lod_microseconds: _Pair
    doodson: str
    period_days: str


class _PolarTerm(TypedDict):
    multipliers: _Six
    pole_microarcseconds: _Pole
    doodson: str
    period_days: str


class _UT1Term(TypedDict):
    multipliers: _Six
    ut1_microseconds: _Pair
    lod_microseconds: _Pair
    doodson: str
    period_days: str


class _ZonalTerm(TypedDict):
    multipliers: _Five
    ut1_1e_minus4_seconds: _Pair
    lod_1e_minus5_seconds: _Pair
    omega_1e_minus14_rad_per_second: _Pair
    period_days: str


class _TideData(TypedDict):
    format_version: Literal[1]
    model_id: str
    source_documents: dict[str, str]
    fundamental_arcseconds: tuple[tuple[str, str, str, str, str], ...]
    gmst_arcseconds: tuple[str, str, str, str, str, str]
    ocean: tuple[_OceanTerm, ...]
    polar_libration: tuple[_PolarTerm, ...]
    ut1_libration: tuple[_UT1Term, ...]
    zonal: tuple[_ZonalTerm, ...]
    scope: str


@lru_cache(maxsize=1)
def _coefficients() -> _TideData:
    """Validate unknown resource bytes once, at their owning boundary."""
    raw = files("fatebridge.data").joinpath("knowledge/" + ASSET).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ASSET_SHA:
        raise ValueError("IERS 2010 coefficient asset identity mismatch")
    return TypeAdapter(_TideData).validate_json(raw)


def _fundamental_angles(tt: TTInstant) -> tuple[float, ...]:
    t = (tt.days - 2451545) / 36525
    angles = []
    for coefficients in _coefficients()["fundamental_arcseconds"]:
        value = Fraction(0)
        for coefficient in reversed(coefficients):
            value = value * t + Fraction(coefficient)
        angles.append(float((value % 1296000) / 1296000) * math.tau)
    return tuple(angles)


@dataclass(frozen=True)
class SubdailyEOP:
    """Corrections only; no daily base, zonal term or duplicate clock."""

    x_arcsec: float
    y_arcsec: float
    ut1_seconds: float


@lru_cache(maxsize=512)
def zonal_ut1(tt: TTInstant) -> float:
    """Table 8.1's 62 zonal UT1 terms, in seconds, at TT.

    Memoization reuses immutable daily source-node corrections. LOD and
    angular-velocity columns remain source data and are not evaluated.
    """
    angles = _fundamental_angles(tt)
    terms = []
    for term in _coefficients()["zonal"]:
        phase = math.fsum(m * a for m, a in zip(term["multipliers"], angles))
        sine, cosine = term["ut1_1e_minus4_seconds"]
        terms.append(sine * math.sin(phase) + cosine * math.cos(phase))
    return math.fsum(terms) * 1e-4


def subdaily_eop(tt: TTInstant, ut1: UT1Instant) -> SubdailyEOP:
    """Ocean71 + polar quasi10 + UT1 libration11, each exactly once.

    Theoretical lunisolar arguments use the permitted TT substitution for
    TDB. Gamma is modern GMST + pi: ERA(UT1) + precession(TT), not GAST.
    """
    data = _coefficients()
    t = (tt.days - 2451545) / 36525
    precession = Fraction(0)
    for coefficient in reversed(data["gmst_arcseconds"]):
        precession = precession * t + Fraction(coefficient)
    gamma_turn = (_era_turn(ut1) + precession / 1296000 + Fraction(1, 2)) % 1
    gamma = float(gamma_turn) * math.tau
    angles = (gamma, *_fundamental_angles(tt))
    x_terms: list[float] = []
    y_terms: list[float] = []
    ut1_terms: list[float] = []
    for ocean in data["ocean"]:
        phase = math.fsum(m * a for m, a in zip(ocean["multipliers"], angles))
        sine, cosine = math.sin(phase), math.cos(phase)
        xs, xc, ys, yc = ocean["pole_microarcseconds"]
        us, uc = ocean["ut1_microseconds"]
        x_terms.append(xs * sine + xc * cosine)
        y_terms.append(ys * sine + yc * cosine)
        ut1_terms.append(us * sine + uc * cosine)
    for polar in data["polar_libration"]:
        phase = math.fsum(m * a for m, a in zip(polar["multipliers"], angles))
        sine, cosine = math.sin(phase), math.cos(phase)
        xs, xc, ys, yc = polar["pole_microarcseconds"]
        x_terms.append(xs * sine + xc * cosine)
        y_terms.append(ys * sine + yc * cosine)
    for libration in data["ut1_libration"]:
        phase = math.fsum(m * a for m, a in zip(libration["multipliers"], angles))
        us, uc = libration["ut1_microseconds"]
        ut1_terms.append(us * math.sin(phase) + uc * math.cos(phase))
    return SubdailyEOP(
        math.fsum(x_terms) * 1e-6,
        math.fsum(y_terms) * 1e-6,
        math.fsum(ut1_terms) * 1e-6,
    )
