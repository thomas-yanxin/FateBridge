"""Scalar R/C house-plane phases over the supplied native angle model.

This checks geometric phases instead of choosing the last rounded cusp within
a longitude band. The independent reference uses vector-plane intersections.
The 0.001 arcsecond forward *phase* offset remains explicit; a longitude cusp
snap is not interchangeable with that offset near a degenerate projection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from mpmath import mp  # type: ignore[import-untyped]

from fatebridge.core.astro.horizon_precision import (
    CONVERGENCE_DEGREES,
    NATIVE_COORDINATE_GUARD_DEGREES,
    WORKING_DIGITS,
)

RC_PLANE_PROJECTION_METHOD = "fatebridge_rc_plane_zero_ecliptic_latitude_v1"
PHASE_FORWARD_OFFSET_ARCSECONDS = 0.001


@dataclass(frozen=True)
class HousePlanePosition:
    position: float
    house: int
    phase_degrees: float
    phase_degrees_decimal: str
    working_digits: tuple[int, int]
    action: str


def _phase(
    latitude: float,
    armc: float,
    obliquity: float,
    longitude: float | Fraction,
    house_code: bytes,
    digits: int,
) -> tuple[Any, Any]:
    ctx = mp.clone()
    ctx.dps = digits
    phi, theta, eps = [ctx.mpf(v) * ctx.pi / 180 for v in (latitude, armc, obliquity)]
    lam = (
        (
            ctx.mpf(longitude.numerator) / longitude.denominator
            if isinstance(longitude, Fraction)
            else ctx.mpf(longitude)
        )
        * ctx.pi
        / 180
    )
    east = -ctx.sin(theta) * ctx.cos(lam) + ctx.cos(theta) * ctx.cos(eps) * ctx.sin(lam)
    up = ctx.cos(phi) * (
        ctx.cos(theta) * ctx.cos(lam) + ctx.sin(theta) * ctx.cos(eps) * ctx.sin(lam)
    ) + ctx.sin(phi) * ctx.sin(eps) * ctx.sin(lam)
    if ctx.hypot(east, up) <= ctx.mpf(10) ** (-digits + 10):
        raise ArithmeticError("House-plane direction unresolved at working precision")
    if house_code == b"C":
        phase = ctx.atan2(-up, east) * 180 / ctx.pi % 360
    else:
        phase = (ctx.atan2(east * ctx.cos(phi), up) * 180 / ctx.pi - 90) % 360
    return ctx, phase


def checked_house_plane_position(
    *,
    latitude: float,
    armc: float,
    obliquity: float,
    longitude: float | Fraction,
    house_code: bytes,
    native_position: float,
) -> HousePlanePosition:
    if house_code not in (b"R", b"C"):
        raise ValueError("House-plane precision supports R/C only")
    if not all(math.isfinite(v) for v in (latitude, armc, obliquity, longitude)):
        raise ValueError("House-plane precision requires finite model inputs")
    if abs(latitude) > 90 or (house_code == b"R" and abs(latitude) == 90):
        raise ArithmeticError(
            "Equatorial house planes are undefined at a geographic pole"
        )
    previous = None
    for digits in WORKING_DIGITS:
        try:
            ctx, phase = _phase(
                latitude, armc, obliquity, longitude, house_code, digits
            )
        except ArithmeticError:
            previous = None
            continue
        if previous is not None:
            low_digits, low = previous
            distance = abs((phase - ctx.mpf(low) + 180) % 360 - 180)
            if distance <= ctx.mpf(CONVERGENCE_DEGREES):
                break
        previous = digits, phase
    else:
        raise ArithmeticError("House-plane phase did not converge")
    shifted = (phase + ctx.mpf(1) / 3600000) % 360
    house = int(ctx.floor(shifted / 30)) + 1
    reported_phase = float(shifted)
    if reported_phase == 360:
        reported_phase = math.nextafter(360.0, 0.0)
    decimal_phase = ctx.nstr(shifted, 100)
    if math.isfinite(native_position) and 1 <= native_position < 13:
        error = abs(((ctx.mpf(native_position) - 1) * 30 - shifted + 180) % 360 - 180)
        if int(native_position) == house and error <= ctx.mpf(
            NATIVE_COORDINATE_GUARD_DEGREES
        ):
            return HousePlanePosition(
                native_position,
                house,
                reported_phase,
                decimal_phase,
                (low_digits, digits),
                "native_coordinate_retained",
            )
    value = float(shifted / 30 + 1)
    # Retain the exact half-open house when binary64 rounds up to its boundary.
    if math.floor(value) > house:
        value = math.nextafter(value, -math.inf)
    if not 1 <= value < 13 or math.floor(value) != house:
        raise ArithmeticError(
            "House-plane position cannot represent its half-open house"
        )
    return HousePlanePosition(
        value,
        house,
        reported_phase,
        decimal_phase,
        (low_digits, digits),
        "scalar_plane_recomputed",
    )
