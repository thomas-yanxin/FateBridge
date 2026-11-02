"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

import math
from typing import Sequence, Tuple

from fatebridge.utils.errors import EphemerisSourceError

LIGHT_SPEED_AU_PER_DAY = 299792458.0 * 86400.0 / 149597870700.0


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    return math.fsum(x * y for x, y in zip(a, b))


def aberration_position_jvp(
    position: Sequence[float], delta_velocity: Sequence[float], beta: Sequence[float]
) -> Tuple[Tuple[float, ...], Tuple[float, ...]]:
    """Position and Jacobian-vector product with observer beta held fixed."""
    if any(len(v) != 3 for v in (position, delta_velocity, beta)):
        raise EphemerisSourceError("coordinate_values_unavailable")
    radius = math.hypot(*position)
    beta2 = dot(beta, beta)
    if not math.isfinite(radius) or radius <= 0 or not 0 <= beta2 < 1:
        raise EphemerisSourceError("coordinate_values_unavailable")
    dr = dot(position, delta_velocity) / radius
    b = math.sqrt(1 - beta2)
    g = dot(position, beta) / radius
    dg = (dot(delta_velocity, beta) - g * dr) / radius
    h, dh = 1 + g / (1 + b), dg / (1 + b)
    apparent = tuple(
        (b * x + h * radius * be) / (1 + g) for x, be in zip(position, beta)
    )
    change = tuple(
        (
            (b * dv + dh * radius * be + h * dr * be) * (1 + g)
            - (b * x + h * radius * be) * dg
        )
        / (1 + g) ** 2
        for x, dv, be in zip(position, delta_velocity, beta)
    )
    if not all(math.isfinite(v) for v in (*apparent, *change)):
        raise EphemerisSourceError("coordinate_values_unavailable")
    return apparent, change


def longitude_rate_change(position: Sequence[float], change: Sequence[float]) -> float:
    denominator = position[0] ** 2 + position[1] ** 2
    if not math.isfinite(denominator) or denominator <= 0:
        raise EphemerisSourceError("coordinate_values_unavailable")
    return math.degrees(
        (position[0] * change[1] - position[1] * change[0]) / denominator
    )


def aberration_beta_jvp(
    position: Sequence[float], beta: Sequence[float], beta_derivative: Sequence[float]
) -> Tuple[Tuple[float, ...], Tuple[float, ...]]:
    """Lorentz position and observer-beta JVP, with position held fixed."""
    if any(len(v) != 3 for v in (position, beta, beta_derivative)):
        raise EphemerisSourceError("coordinate_values_unavailable")
    radius = math.hypot(*position)
    beta2 = dot(beta, beta)
    if not math.isfinite(radius) or radius <= 0 or not 0 <= beta2 < 1:
        raise EphemerisSourceError("coordinate_values_unavailable")
    b = math.sqrt(1 - beta2)
    db = -dot(beta, beta_derivative) / b
    g = dot(position, beta) / radius
    dg = dot(position, beta_derivative) / radius
    h = 1 + g / (1 + b)
    dh = dg / (1 + b) - g * db / (1 + b) ** 2
    apparent = tuple(
        (b * x + h * radius * be) / (1 + g) for x, be in zip(position, beta)
    )
    derivative = tuple(
        (
            (db * x + dh * radius * be + h * radius * de) * (1 + g)
            - (b * x + h * radius * be) * dg
        )
        / (1 + g) ** 2
        for x, be, de in zip(position, beta, beta_derivative)
    )
    if not all(math.isfinite(v) for v in (*apparent, *derivative)):
        raise EphemerisSourceError("coordinate_values_unavailable")
    return apparent, derivative
