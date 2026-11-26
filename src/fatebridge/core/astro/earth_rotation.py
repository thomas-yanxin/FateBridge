"""Earth rotation and same-equator origins on explicitly supplied TT/UT1.

Published IERS 2010 expressions and ERFA S06/equation-of-origins arithmetic.
No native configuration, geographic geometry or physical ray is selected here.
"""

from __future__ import annotations

import math
from fractions import Fraction

import erfa

from fatebridge.core.astro.reference_frames import Matrix
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.core.iers2010_series import EECT_TERMS

MODERN_REFERENCE_JD_TT = 2451545


_ERA_ORIGIN = Fraction("0.7790572732640")


_ERA_RATE = Fraction("1.00273781191135448")


MODERN_HALF_WINDOW_DAYS = 2 * 36525.0


def selected_sidereal_model(julian_day_tt: float | TTInstant) -> int:
    point = TTInstant.from_value(julian_day_tt)
    return (
        3 if abs(point.days - MODERN_REFERENCE_JD_TT) <= MODERN_HALF_WINDOW_DAYS else 4
    )


_LUNAR = (
    (485868.249036, 1717915923.2178, 31.8792, 0.051635, -0.00024470),
    (1287104.793048, 129596581.0481, -0.5532, 0.000136, -0.00001149),
    (335779.526232, 1739527262.8478, -12.7512, -0.001037, 0.00000417),
    (1072260.703692, 1602961601.2090, -6.3706, 0.006593, -0.00003169),
    (450160.398036, -6962890.5431, 7.4722, 0.007702, -0.00005939),
)


def _fundamental_arguments(t: float) -> tuple[float, ...]:
    values = []
    for coefficients in _LUNAR:
        value = 0.0
        for coefficient in reversed(coefficients):
            value = value * t + coefficient
        values.append(math.radians((value % 1296000.0) / 3600))
    values.extend(
        (
            (3.176146697 + 1021.3285546211 * t) % math.tau,
            (1.753470314 + 628.3075849991 * t) % math.tau,
            (0.024381750 + 0.00000538691 * t) * t,
        )
    )
    return tuple(values)


def _era_turn(jd_ut1: float | UT1Instant) -> Fraction:
    point = UT1Instant.from_value(jd_ut1)
    return (_ERA_ORIGIN + _ERA_RATE * (point.days - 2451545)) % 1


def iers2010_gast(
    jd_ut1: float | UT1Instant,
    jd_tt: float | TTInstant,
    nutation_longitude: float,
    mean_obliquity: float,
) -> float:
    """IERS Table 5.2e; degrees, UT1 for ERA and TT for polynomial/series."""
    ut1 = UT1Instant.from_value(jd_ut1)
    if not all(math.isfinite(x) for x in (nutation_longitude, mean_obliquity)):
        raise ValueError("Rotation inputs must be finite")
    # Keep the published affine rotation and the supplied UT1 point exact
    # until the final angular sum. A scalar still denotes only its IEEE point.
    era_turn = _era_turn(ut1)
    t = float((TTInstant.from_value(jd_tt).days - MODERN_REFERENCE_JD_TT) / 36525)
    polynomial = 0.014506 + t * (
        4612.156534
        + t * (1.3915817 + t * (-0.00000044 + t * (-0.000029956 + t * (-0.0000000368))))
    )
    arguments = _fundamental_arguments(t)
    series = math.fsum(
        (
            sine * math.sin(math.fsum(m * a for m, a in zip(multipliers, arguments)))
            + cosine
            * math.cos(math.fsum(m * a for m, a in zip(multipliers, arguments)))
        )
        * (t**power)
        for power, sine, cosine, multipliers in EECT_TERMS
    )
    correction_arcseconds = math.fsum(
        (
            polynomial,
            nutation_longitude * 3600 * math.cos(math.radians(mean_obliquity)),
            series / 1_000_000,
        )
    )
    return float((era_turn * 360 + Fraction(correction_arcseconds) / 3600) % 360) % 360


def frame_gast(
    jd_ut1: float | UT1Instant, jd_tt: float | TTInstant, matrix: Matrix
) -> float:
    """GAST from the same equinox NPB, S06 CIO locator and precise ERA.

    ERFA gst06 permits a supplied NPB model. The native matrix need not be
    full IAU 2006/2000A; observed pole offsets and polar motion are separate.
    """
    ut1 = UT1Instant.from_value(jd_ut1)
    point = TTInstant.from_value(jd_tt)
    locator = float(erfa.s06(*point.as_parts(), matrix[2][0], matrix[2][1]))
    origins = float(erfa.eors(matrix, locator))
    return float((_era_turn(ut1) * 360 - Fraction(math.degrees(origins))) % 360) % 360
