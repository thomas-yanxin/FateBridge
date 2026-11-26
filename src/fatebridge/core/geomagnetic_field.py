"""Spherical-harmonic geomagnetic field evaluation in the local WGS84 NED frame.

The Schmidt recurrence follows DLMF 14.10.3 after normalization; its latitude
derivative is propagated analytically. For every positive order we carry P/cos
instead of dividing at the poles. Evaluation uses IEEE-754 binary64 spherical
harmonics for both WMM2025 (degree 12, 2025.0-2030.0) and IGRF-14 (degree 13,
1900.0-2030.0).
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

WmmCoefficient = tuple[int, int, Decimal, Decimal, Decimal, Decimal]
IgrfCoefficient = tuple[int, int, tuple[float, ...], tuple[float, ...], float, float]
IMPLEMENTATION_ID = "fatebridge_wmm2025_wgs84_v1"
IGRF14_IMPLEMENTATION_ID = "fatebridge_igrf14_wgs84_v1"

_MAX_DEGREE = 13
_WGS84_A = 6378.137
_WGS84_F = 1.0 / 298.257223563
_WGS84_E2 = _WGS84_F * (2.0 - _WGS84_F)
_REF_RADIUS = 6371.2

_DIAG_A = [0.0] * (_MAX_DEGREE + 1)
_SUBDIAG_A = [0.0] * (_MAX_DEGREE + 1)
_REC_A: list[list[float]] = [[0.0] * (_MAX_DEGREE + 1) for _ in range(_MAX_DEGREE + 1)]
_REC_B: list[list[float]] = [[0.0] * (_MAX_DEGREE + 1) for _ in range(_MAX_DEGREE + 1)]
for _n in range(1, _MAX_DEGREE + 1):
    _DIAG_A[_n] = math.sqrt((2 * _n - 1) / (2 * _n))
    _SUBDIAG_A[_n] = math.sqrt(2 * _n - 1)
    for _m in range(_n - 1):
        _denom = _n * _n - _m * _m
        _REC_A[_n][_m] = (2 * _n - 1) / math.sqrt(_denom)
        _REC_B[_n][_m] = math.sqrt(((_n - 1) ** 2 - _m * _m) / _denom)


@dataclass(frozen=True)
class MagneticField:
    """North/east/down and intensities in nT; inclination/declination in degrees."""

    x: float
    y: float
    z: float
    h: float
    f: float
    i: float
    d: float


def _evaluate_field(
    latitude: float,
    longitude: float,
    height_km: float,
    max_degree: int,
    terms: Iterable[tuple[int, int, float, float]],
) -> MagneticField:
    """Evaluate validated geodetic inputs for any Schmidt spherical-harmonic expansion."""
    phi = math.radians(latitude)
    lam = math.radians(longitude)
    if abs(latitude) == 90:
        sin_phi = 1.0 if latitude > 0 else -1.0
        cos_phi = 0.0
    else:
        sin_phi = math.sin(phi)
        cos_phi = math.cos(phi)
    curvature = _WGS84_A / math.sqrt(1.0 - _WGS84_E2 * sin_phi * sin_phi)
    p = (curvature + height_km) * cos_phi
    z = (curvature * (1.0 - _WGS84_E2) + height_km) * sin_phi
    radius = math.hypot(p, z)
    s = z / radius
    c = p / radius

    # m=0: q=P; m>=1: q=P/c. Avoids division by cos(latitude) near poles.
    size = max_degree + 1
    q = [[0.0] * size for _ in range(size)]
    dq = [[0.0] * size for _ in range(size)]
    q[0][0] = 1.0
    for n in range(1, size):
        qn = q[n]
        dqn = dq[n]
        qn1 = q[n - 1]
        dqn1 = dq[n - 1]
        for m in range(n + 1):
            if n == m == 1:
                qn[m] = 1.0
            elif n == m:
                a = _DIAG_A[n]
                prev = qn1[m - 1]
                qn[m] = a * c * prev
                dqn[m] = a * (c * dqn1[m - 1] - s * prev)
            elif m == n - 1:
                a = _SUBDIAG_A[n]
                prev = qn1[m]
                qn[m] = a * s * prev
                dqn[m] = a * (s * dqn1[m] + c * prev)
            else:
                a = _REC_A[n][m]
                b = _REC_B[n][m]
                prev = qn1[m]
                qn[m] = a * s * prev - b * q[n - 2][m]
                dqn[m] = a * (s * dqn1[m] + c * prev) - b * dq[n - 2][m]

    cos_m = [math.cos(m * lam) for m in range(size)]
    sin_m = [math.sin(m * lam) for m in range(size)]
    ratio = _REF_RADIUS / radius
    radial_powers = [ratio ** (n + 2) for n in range(size)]

    north = 0.0
    east = 0.0
    down = 0.0
    for n, m, g, h in terms:
        cosine = cos_m[m]
        sine = sin_m[m]
        harmonic = g * cosine + h * sine
        radial = radial_powers[n]
        q_nm = q[n][m]
        dq_nm = dq[n][m]
        if m:
            p_nm = c * q_nm
            dp_nm = c * dq_nm - s * q_nm
            east += radial * m * (g * sine - h * cosine) * q_nm
        else:
            p_nm = q_nm
            dp_nm = dq_nm
        north -= radial * harmonic * dp_nm
        down -= radial * (n + 1) * harmonic * p_nm

    sin_rotation = s * cos_phi - c * sin_phi
    cos_rotation = c * cos_phi + s * sin_phi
    x = north * cos_rotation - down * sin_rotation
    z_out = north * sin_rotation + down * cos_rotation
    horizontal = math.hypot(x, east)
    return MagneticField(
        x=x,
        y=east,
        z=z_out,
        h=horizontal,
        f=math.hypot(horizontal, z_out),
        i=math.degrees(math.atan2(z_out, horizontal)),
        d=math.degrees(math.atan2(east, x)),
    )


def wmm2025_field(
    latitude: float,
    longitude: float,
    height_km: float,
    decimal_year: float,
    coefficients: tuple[WmmCoefficient, ...],
) -> MagneticField:
    """Evaluate validated WMM2025 inputs (2025.0-2030.0) in pure binary64."""
    elapsed = float(decimal_year) - 2025.0
    terms = (
        (n, m, float(g0) + elapsed * float(dg), float(h0) + elapsed * float(dh))
        for n, m, g0, h0, dg, dh in coefficients
    )
    return _evaluate_field(latitude, longitude, height_km, 12, terms)


def igrf14_field(
    latitude: float,
    longitude: float,
    height_km: float,
    decimal_year: float,
    coefficients: tuple[IgrfCoefficient, ...],
) -> MagneticField:
    """Evaluate validated IGRF-14 inputs (1900.0-2030.0) in pure binary64."""
    year = float(decimal_year)
    if year < 1900.0 or year > 2030.0:
        raise ValueError("IGRF-14 supports decimal_year in [1900.0, 2030.0]")
    if year >= 2025.0:
        elapsed = year - 2025.0
        terms = (
            (n, m, g_arr[25] + elapsed * dg, h_arr[25] + elapsed * dh)
            for n, m, g_arr, h_arr, dg, dh in coefficients
        )
    else:
        idx = min(int((year - 1900.0) // 5.0), 24)
        frac = (year - (1900.0 + 5.0 * idx)) / 5.0
        terms = (
            (
                n,
                m,
                g_arr[idx] + frac * (g_arr[idx + 1] - g_arr[idx]),
                h_arr[idx] + frac * (h_arr[idx + 1] - h_arr[idx]),
            )
            for n, m, g_arr, h_arr, _, _ in coefficients
        )
    return _evaluate_field(latitude, longitude, height_km, 13, terms)
