"""Earth rotation and same-equator origins on explicitly supplied TT/UT1.

Published IERS 2010 expressions and ERFA S06/equation-of-origins arithmetic.
No native configuration, geographic geometry or physical ray is selected here.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Tuple

from fatebridge.core.astro.reference_frames import Matrix
from fatebridge.core.iers2010_series import EECT_TERMS

MODERN_REFERENCE_JD_TT = 2451545.0


_ERA_ORIGIN = Fraction("0.7790572732640")


_ERA_RATE = Fraction("1.00273781191135448")


MODERN_HALF_WINDOW_DAYS = 2 * 36525.0


def selected_sidereal_model(julian_day_tt: float) -> int:
    if not math.isfinite(julian_day_tt):
        raise ValueError("Rotation model epoch must be finite")
    return (
        3
        if abs(julian_day_tt - MODERN_REFERENCE_JD_TT) <= MODERN_HALF_WINDOW_DAYS
        else 4
    )


_LUNAR = (
    (485868.249036, 1717915923.2178, 31.8792, 0.051635, -0.00024470),
    (1287104.793048, 129596581.0481, -0.5532, 0.000136, -0.00001149),
    (335779.526232, 1739527262.8478, -12.7512, -0.001037, 0.00000417),
    (1072260.703692, 1602961601.2090, -6.3706, 0.006593, -0.00003169),
    (450160.398036, -6962890.5431, 7.4722, 0.007702, -0.00005939),
)


def _fundamental_arguments(t: float) -> Tuple[float, ...]:
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


def _era_turn(jd_ut1: float) -> Fraction:
    return (_ERA_ORIGIN + _ERA_RATE * (Fraction(jd_ut1) - 2451545)) % 1


def iers2010_gast(
    jd_ut1: float, jd_tt: float, nutation_longitude: float, mean_obliquity: float
) -> float:
    """IERS Table 5.2e; degrees, UT1 for ERA and TT for polynomial/series."""
    if not all(
        math.isfinite(x) for x in (jd_ut1, jd_tt, nutation_longitude, mean_obliquity)
    ):
        raise ValueError("Rotation inputs must be finite")
    # Keep the published decimal affine rotation and the supplied IEEE UT1
    # point exact until the final angular sum and wrap. This does not restore
    # civil-clock precision already lost before this point was supplied.
    era_turn = _era_turn(jd_ut1)
    t = (jd_tt - MODERN_REFERENCE_JD_TT) / 36525
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


def frame_gast(jd_ut1: float, jd_tt: float, matrix: Matrix) -> float:
    """GAST from the same equinox NPB, S06 CIO locator and precise ERA.

    ERFA gst06 permits a supplied NPB model. The native matrix need not be
    full IAU 2006/2000A; observed pole offsets and polar motion are separate.
    """
    import erfa

    if not math.isfinite(jd_ut1) or not math.isfinite(jd_tt):
        raise ValueError("Rotation epochs must be finite")
    locator = float(erfa.s06(jd_tt, 0.0, matrix[2][0], matrix[2][1]))
    origins = float(erfa.eors(matrix, locator))
    return (
        float((_era_turn(jd_ut1) * 360 - Fraction(math.degrees(origins))) % 360) % 360
    )
