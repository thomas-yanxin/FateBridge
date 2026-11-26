"""Degree-12 WMM potential gradient in the local WGS84 north/east/down frame.

The Schmidt recurrence follows DLMF 14.10.3 after normalization; its latitude
derivative is propagated analytically. For every positive order we carry P/cos
instead of dividing at the poles. Evaluation uses IEEE-754 binary64 spherical
harmonics (matches 50-digit arithmetic to ~1e-13°; WMM2025 surface 1-sigma is >=0.26°).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

WmmCoefficient = tuple[int, int, Decimal, Decimal, Decimal, Decimal]
IMPLEMENTATION_ID = "fatebridge_wmm2025_wgs84_v1"

_WGS84_A = 6378.137
_WGS84_F = 1.0 / 298.257223563
_WGS84_E2 = _WGS84_F * (2.0 - _WGS84_F)
_WMM_REF_RADIUS = 6371.2

_DIAG_A = [0.0] * 13
_SUBDIAG_A = [0.0] * 13
_REC_A: list[list[float]] = [[0.0] * 13 for _ in range(13)]
_REC_B: list[list[float]] = [[0.0] * 13 for _ in range(13)]
for _n in range(1, 13):
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


def wmm2025_field(
    latitude: float,
    longitude: float,
    height_km: float,
    decimal_year: float,
    coefficients: tuple[WmmCoefficient, ...],
) -> MagneticField:
    """Evaluate validated WMM2025 inputs in pure binary64, including pole limits."""
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
    q = [[0.0] * 13 for _ in range(13)]
    dq = [[0.0] * 13 for _ in range(13)]
    q[0][0] = 1.0
    for n in range(1, 13):
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

    elapsed = float(decimal_year) - 2025.0
    cos_m = [math.cos(m * lam) for m in range(13)]
    sin_m = [math.sin(m * lam) for m in range(13)]
    ratio = _WMM_REF_RADIUS / radius
    radial_powers = [ratio ** (n + 2) for n in range(13)]

    north = 0.0
    east = 0.0
    down = 0.0
    for n, m, g0, h0, dg, dh in coefficients:
        g = float(g0) + elapsed * float(dg)
        h = float(h0) + elapsed * float(dh)
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
