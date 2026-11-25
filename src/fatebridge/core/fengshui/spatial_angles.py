"""Exact periodic phases for spatial decisions; finite components at geometry."""

from __future__ import annotations

from fractions import Fraction
from functools import lru_cache
from math import isqrt, nextafter, sqrt
from typing import Literal

from mpmath import mp  # type: ignore[import-untyped]

Angle = float | Fraction
CompassDirection = Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
DIRECTIONS: tuple[CompassDirection, ...] = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
WORKING_DIGITS = 90


def compose_degrees(*angles: Angle) -> Fraction:
    """Compose original finite phases without rounded or overflowing sums."""
    return sum((Fraction(angle) for angle in angles), Fraction(0)) % 360


@lru_cache(maxsize=4096)
def _sin_cos_degrees(angle: Angle) -> tuple[float, float]:
    phase = Fraction(angle) % 360
    quadrant = int((phase + 45) // 90)
    residual = phase - quadrant * 90
    if residual == 0:
        sine, cosine = 0.0, 1.0
    elif abs(residual) == 45:
        cosine = sqrt(0.5)
        sine = cosine if residual > 0 else -cosine
    else:
        # Reduce exactly before conversion: a tiny displacement from any axis
        # remains a tiny argument, even after large cancelling source phases.
        # A private context leaves other calculations' precision untouched.
        context = mp.clone()
        context.dps = WORKING_DIGITS
        value = (
            context.mpf(residual.numerator) / residual.denominator * context.pi / 180
        )
        sine, cosine = float(context.sin(value)), float(context.cos(value))
    return (
        (sine, cosine),
        (cosine, -sine),
        (-sine, -cosine),
        (-cosine, sine),
    )[quadrant % 4]


@lru_cache(maxsize=4096)
def _atan_degrees(ratio: Fraction) -> Fraction:
    """Retain the small residual before adding an exact axis or diagonal."""
    if ratio == 0:
        return Fraction(0)
    else:
        pass
    context = mp.clone()
    context.dps = WORKING_DIGITS
    value = context.atan(context.mpf(ratio.numerator) / ratio.denominator)
    return Fraction(context.nstr(value * 180 / context.pi, WORKING_DIGITS))


def angular_radius(radius: float, distance_squared: Fraction) -> Fraction:
    """Tangent angle of a closed error disc that does not reach the origin.

    Keep rational tangencies on the same atan path as point headings. Turning
    a separately rounded asin into degrees can otherwise lose a closed edge.
    """
    if radius == 0:
        return Fraction(0)
    else:
        pass
    error = Fraction(radius)
    tangent_squared = distance_squared - error * error
    numerator = isqrt(tangent_squared.numerator)
    denominator = isqrt(tangent_squared.denominator)
    if (
        numerator * numerator == tangent_squared.numerator
        and denominator * denominator == tangent_squared.denominator
    ):
        return _atan_degrees(error / Fraction(numerator, denominator))
    else:
        pass
    context = mp.clone()
    context.dps = WORKING_DIGITS
    ratio = (context.mpf(error.numerator) / error.denominator) / context.sqrt(
        context.mpf(tangent_squared.numerator) / tangent_squared.denominator
    )
    return Fraction(
        context.nstr(context.atan(ratio) * 180 / context.pi, WORKING_DIGITS)
    )


def angular_offset(left: Angle, right: Angle) -> Fraction:
    """Signed working phase for closed angular predicates."""
    return (Fraction(left) - Fraction(right) + 180) % 360 - 180


def angular_delta(left: Angle, right: Angle) -> float:
    angle = float(angular_offset(left, right))
    return nextafter(180.0, 0.0) if angle == 180 else angle


def direction_support(bearing: Angle, radius: Angle) -> list[CompassDirection]:
    """Closed uncertainty interval; an exact point uses left-closed cells."""
    center = Fraction(bearing) % 360
    if radius == 0:
        return [DIRECTIONS[int((center + Fraction(45, 2)) // 45) % 8]]
    else:
        pass
    lower, upper = center - Fraction(radius), center + Fraction(radius)
    return [
        direction
        for i, direction in enumerate(DIRECTIONS)
        if any(
            max(lower, i * 45 - Fraction(45, 2) + turn * 360)
            <= min(upper, i * 45 + Fraction(45, 2) + turn * 360)
            for turn in (-1, 0, 1)
        )
    ]
