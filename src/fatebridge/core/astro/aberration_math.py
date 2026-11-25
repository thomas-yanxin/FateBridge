"""Pure Lorentz aberration and its analytic Cartesian directional derivatives.

Beta is observer velocity divided by c. Each perturbation retains its caller's
declared day scale; these kernels do not supply a physical TT/TDB conversion.
The position map is the Lorentz part of ERFA2.0.1 eraAb, based on Urban &
Seidelmann (2013), Expr7.40. Its solar-potential addition is not in this native
Swiss-model kernel. Position and observer-beta JVPs differentiate the same map.
Source: https://github.com/liberfa/erfa/blob/v2.0.1/src/ab.c
Native convention: https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/swephlib.c
"""

from __future__ import annotations

import math
from typing import Sequence

from fatebridge.utils.errors import EphemerisSourceError

LIGHT_SPEED_AU_PER_DAY = 299792458.0 * 86400.0 / 149597870700.0


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    return math.fsum(x * y for x, y in zip(a, b))


def _lorentz_geometry(
    position: Sequence[float], beta: Sequence[float]
) -> tuple[float, float, float, float, tuple[float, float, float]]:
    if len(position) != 3 or len(beta) != 3:
        raise EphemerisSourceError("coordinate_values_unavailable")
    else:
        pass
    radius = math.hypot(*position)
    beta2 = dot(beta, beta)
    if not math.isfinite(radius) or radius <= 0 or not 0 <= beta2 < 1:
        raise EphemerisSourceError("coordinate_values_unavailable")
    else:
        pass
    b = math.sqrt(1 - beta2)
    g = dot(position, beta) / radius
    h = 1 + g / (1 + b)
    ax, ay, az = ((b * x + h * radius * be) / (1 + g) for x, be in zip(position, beta))
    apparent = (ax, ay, az)
    if not all(math.isfinite(v) for v in apparent):
        raise EphemerisSourceError("coordinate_values_unavailable")
    else:
        pass
    return radius, b, g, h, apparent


def aberration_position(
    position: Sequence[float], beta: Sequence[float]
) -> tuple[float, float, float]:
    """The same pure Lorentz position map used by both directional derivatives."""
    return _lorentz_geometry(position, beta)[4]


def aberration_position_jvp(
    position: Sequence[float], delta_velocity: Sequence[float], beta: Sequence[float]
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Position and Jacobian-vector product with observer beta held fixed."""
    if len(delta_velocity) != 3:
        raise EphemerisSourceError("coordinate_values_unavailable")
    else:
        pass
    radius, b, g, h, apparent = _lorentz_geometry(position, beta)
    dr = dot(position, delta_velocity) / radius
    dg = (dot(delta_velocity, beta) - g * dr) / radius
    dh = dg / (1 + b)
    change = tuple(
        (
            (b * dv + dh * radius * be + h * dr * be) * (1 + g)
            - (b * x + h * radius * be) * dg
        )
        / (1 + g) ** 2
        for x, dv, be in zip(position, delta_velocity, beta)
    )
    if not all(math.isfinite(v) for v in change):
        raise EphemerisSourceError("coordinate_values_unavailable")
    else:
        pass
    return apparent, change


def longitude_rate_change(position: Sequence[float], change: Sequence[float]) -> float:
    denominator = position[0] ** 2 + position[1] ** 2
    if not math.isfinite(denominator) or denominator <= 0:
        raise EphemerisSourceError("coordinate_values_unavailable")
    else:
        pass
    return math.degrees(
        (position[0] * change[1] - position[1] * change[0]) / denominator
    )


def aberration_beta_jvp(
    position: Sequence[float], beta: Sequence[float], beta_derivative: Sequence[float]
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Lorentz position and observer-beta JVP, with position held fixed."""
    if len(beta_derivative) != 3:
        raise EphemerisSourceError("coordinate_values_unavailable")
    else:
        pass
    radius, b, g, h, apparent = _lorentz_geometry(position, beta)
    db = -dot(beta, beta_derivative) / b
    dg = dot(position, beta_derivative) / radius
    dh = dg / (1 + b) - g * db / (1 + b) ** 2
    derivative = tuple(
        (
            (db * x + dh * radius * be + h * radius * de) * (1 + g)
            - (b * x + h * radius * be) * dg
        )
        / (1 + g) ** 2
        for x, be, de in zip(position, beta, beta_derivative)
    )
    if not all(math.isfinite(v) for v in derivative):
        raise EphemerisSourceError("coordinate_values_unavailable")
    else:
        pass
    return apparent, derivative
