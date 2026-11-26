"""Degree12 WMM potential gradient in the local WGS84 north/east/down frame.

The Schmidt recurrence follows DLMF14.10.3 after normalization; its latitude
derivative is propagated analytically. For every positive order we carry P/cos
instead of dividing at the poles. The NOAA model, coefficients and surface
uncertainties are separate from floating-point evaluation accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from mpmath import mp  # type: ignore[import-untyped]

WmmCoefficient = tuple[int, int, Decimal, Decimal, Decimal, Decimal]
IMPLEMENTATION_ID = "fatebridge_wmm2025_wgs84_v1"


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
    """Evaluate validated WMM2025 inputs, including geographic-pole limits.

    A private 50-digit context preserves the literal model coefficients and
    WGS84 inverse flattening until the final binary64 output. It also isolates
    concurrent calls from the process-global mpmath precision. The supplied
    longitude fixes local axes at a pole, not a usable compass heading.
    """
    context = mp.clone()
    context.dps = 50
    phi = context.mpf(latitude) * context.pi / 180
    lam = context.mpf(longitude) * context.pi / 180
    sin_phi, cos_phi = context.sin(phi), context.cos(phi)
    if abs(latitude) == 90:
        sin_phi, cos_phi = context.mpf(1 if latitude > 0 else -1), context.zero
    semimajor_axis = context.mpf("6378.137")
    flattening = 1 / context.mpf("298.257223563")
    e2 = flattening * (2 - flattening)
    curvature = semimajor_axis / context.sqrt(1 - e2 * sin_phi**2)
    height = context.mpf(height_km)
    p = (curvature + height) * cos_phi
    z = (curvature * (1 - e2) + height) * sin_phi
    radius = context.hypot(p, z)
    s, c = z / radius, p / radius
    # m=0: q=P; m>=1: q=P/c. This factorization avoids both division by
    # cos(latitude) and cancellation in sqrt(1-sin(latitude)**2) near a pole.
    q = [[context.zero] * 13 for _ in range(13)]
    dq = [[context.zero] * 13 for _ in range(13)]
    q[0][0] = context.one
    for n in range(1, 13):
        for m in range(n + 1):
            if n == m == 1:
                q[n][m] = context.one
            elif n == m:
                a = context.sqrt(context.mpf(2 * n - 1) / (2 * n))
                previous = q[n - 1][m - 1]
                q[n][m] = a * c * previous
                dq[n][m] = a * (c * dq[n - 1][m - 1] - s * previous)
            elif m == n - 1:
                a = context.sqrt(2 * n - 1)
                previous = q[n - 1][m]
                q[n][m] = a * s * previous
                dq[n][m] = a * (s * dq[n - 1][m] + c * previous)
            else:
                denominator = n * n - m * m
                a = (2 * n - 1) / context.sqrt(denominator)
                b = context.sqrt(context.mpf((n - 1) ** 2 - m * m) / denominator)
                previous = q[n - 1][m]
                q[n][m] = a * s * previous - b * q[n - 2][m]
                dq[n][m] = a * (s * dq[n - 1][m] + c * previous) - b * dq[n - 2][m]
    north_terms, east_terms, down_terms = [], [], []
    elapsed = context.mpf(decimal_year) - 2025
    cos_m = [context.cos(m * lam) for m in range(13)]
    sin_m = [context.sin(m * lam) for m in range(13)]
    radial_powers = [(context.mpf("6371.2") / radius) ** (n + 2) for n in range(13)]
    for n, m, g0, h0, dg, dh in coefficients:
        g = context.mpf(str(g0)) + elapsed * context.mpf(str(dg))
        h = context.mpf(str(h0)) + elapsed * context.mpf(str(dh))
        cosine, sine = cos_m[m], sin_m[m]
        harmonic = g * cosine + h * sine
        radial = radial_powers[n]
        p_nm = c * q[n][m] if m else q[n][m]
        dp_nm = c * dq[n][m] - s * q[n][m] if m else dq[n][m]
        north_terms.append(-radial * harmonic * dp_nm)
        east_terms.append(radial * m * (g * sine - h * cosine) * q[n][m])
        down_terms.append(-radial * (n + 1) * harmonic * p_nm)
    north, east, down = map(context.fsum, (north_terms, east_terms, down_terms))
    # Rotate by geocentric minus geodetic latitude, using the sine/cosine
    # pairs directly rather than recovering and subtracting two angles.
    sin_rotation = s * cos_phi - c * sin_phi
    cos_rotation = c * cos_phi + s * sin_phi
    x = north * cos_rotation - down * sin_rotation
    z = north * sin_rotation + down * cos_rotation
    horizontal = context.hypot(x, east)
    return MagneticField(
        x=float(x),
        y=float(east),
        z=float(z),
        h=float(horizontal),
        f=float(context.hypot(horizontal, z)),
        i=float(context.atan2(z, horizontal) * 180 / context.pi),
        d=float(context.atan2(east, x) * 180 / context.pi),
    )
