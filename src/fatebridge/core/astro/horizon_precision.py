"""Resolve antipodal horizon endpoints using the supplied angle model.

USNO's altitude equation gives A*cos(lambda)+B*sin(lambda)=0. The two
solutions must be distinguished by their eastern component, not by a rounded
ASC/MC subtraction. Near polar tangencies that subtraction can lose the sign.
Scalar equations here are checked against frozen independent vector geometry.
This is numerical model consistency, not an observational error certificate.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from mpmath import mp  # type: ignore[import-untyped]

METHOD_ID = "eastern_horizon_scalar_precision_v1"
WORKING_DIGITS = (80, 120, 160, 200)
CONVERGENCE_DEGREES = "1e-50"
SELECTOR_WORK_GATE = math.sqrt(sys.float_info.epsilon)
NATIVE_COORDINATE_GUARD_DEGREES = 128 * sys.float_info.epsilon * 360


@dataclass(frozen=True)
class HorizonGeometry:
    working_digits: tuple[int, int]
    tropical_ascendant: float
    tropical_midheaven: float
    ascendant_phase_from_midheaven: float
    regiomontanus_phases: tuple[float, ...]
    campanus_phases: tuple[float, ...]
    eastern_selector: str
    intersection_norm: float


def _solve(
    latitude: float, armc: float, obliquity: float, digits: int
) -> dict[str, Any]:
    # Contexts are private to this call; mpmath's global precision is untouched.
    ctx = mp.clone()
    ctx.dps = digits
    phi, theta, eps = [ctx.mpf(v) * ctx.pi / 180 for v in (latitude, armc, obliquity)]
    sp, cp = ctx.sin(phi), ctx.cos(phi)
    st, ct = ctx.sin(theta), ctx.cos(theta)
    se, ce = ctx.sin(eps), ctx.cos(eps)
    a, b = cp * ct, cp * st * ce + sp * se
    norm = ctx.sqrt(a * a + b * b)
    selector = cp * ce + sp * se * st
    if norm == 0 or abs(selector) <= ctx.mpf(10) ** (-digits + 10):
        raise ArithmeticError(
            "Horizon endpoint sign is not resolved at working precision"
        )

    def projected(lam: Any) -> tuple[Any, Any]:
        x, y = ctx.cos(lam), ctx.sin(lam)
        return -st * x + ct * ce * y, a * x + b * y

    point = ctx.atan2(-a, b)
    if projected(point)[0] < 0:
        point += ctx.pi
    asc = point * 180 / ctx.pi % 360
    mc = ctx.atan2(st / ce, ct) * 180 / ctx.pi % 360
    cusps = {}
    for code in ("R", "C"):
        values = []
        for house in range(1, 13):
            if code == "C":
                alpha = ctx.mpf(1 - house) * ctx.pi / 6
                x, y = ctx.cos(alpha), ctx.sin(alpha)
            else:
                beta = ctx.mpf((house - 10) % 12) * ctx.pi / 6
                x, y = ctx.sin(beta), cp * ctx.cos(beta)
            lower, upper = y * (-st) - x * a, y * ct * ce - x * b
            lam = ctx.atan2(-lower, upper)
            east, up = projected(lam)
            if x * east + y * up < 0:
                lam += ctx.pi
            values.append(lam * 180 / ctx.pi % 360)
        cusps[code] = values
    return {
        "ctx": ctx,
        "asc": asc,
        "mc": mc,
        "cusps": cusps,
        "selector": selector,
        "norm": norm,
    }


def horizon_geometry(latitude: float, armc: float, obliquity: float) -> HorizonGeometry:
    """Two-precision scalar solution over exact supplied finite doubles."""
    if not all(math.isfinite(v) for v in (latitude, armc, obliquity)):
        raise ValueError("Horizon precision requires finite angle inputs")
    previous = None
    for digits in WORKING_DIGITS:
        try:
            high = _solve(latitude, armc, obliquity, digits)
        except ArithmeticError:
            previous = None
            continue
        if previous is None:
            previous = (digits, high)
            continue
        low_digits, low = previous
        ctx = high["ctx"]
        line = ctx.mpf(CONVERGENCE_DEGREES)

        def difference(a: Any, b: Any) -> Any:
            return abs((ctx.mpf(a) - ctx.mpf(b) + 180) % 360 - 180)

        values = [difference(low[k], high[k]) for k in ("asc", "mc")]
        for code in ("R", "C"):
            values.extend(
                difference(a, b)
                for a, b in zip(low["cusps"][code], high["cusps"][code])
            )
        if (
            ctx.sign(low["selector"]) == ctx.sign(high["selector"])
            and max(values) <= line
        ):
            break
        previous = (digits, high)
    else:
        raise ArithmeticError("Horizon/spatial cusp solution did not converge")
    return HorizonGeometry(
        working_digits=(low_digits, digits),
        tropical_ascendant=float(high["asc"]) % 360,
        tropical_midheaven=float(high["mc"]) % 360,
        ascendant_phase_from_midheaven=float((high["asc"] - high["mc"]) % 360),
        regiomontanus_phases=tuple(
            float((v - high["mc"]) % 360) for v in high["cusps"]["R"]
        ),
        campanus_phases=tuple(
            float((v - high["mc"]) % 360) for v in high["cusps"]["C"]
        ),
        eastern_selector=ctx.nstr(high["selector"], 100),
        intersection_norm=float(high["norm"]),
    )


def aligned_longitude(
    native: float, native_mc: float, phase: float
) -> tuple[float, str]:
    """Retain a correct native coordinate; repair its endpoint or intersection.

    Phase relative to the unchanged common MC removes a traditional sidereal
    origin without estimating that origin from an ASC. The tiny coordinate
    guard is an arithmetic work rule, not the independent1arcsecond criterion.
    """
    residual = (Fraction(native) - Fraction(native_mc) - Fraction(phase)) % 360
    opposite = 90 < residual < 270
    candidate = (Fraction(native) + (180 if opposite else 0)) % 360
    error = (candidate - Fraction(native_mc) - Fraction(phase)) % 360
    error = min(error, 360 - error)
    if error > Fraction(NATIVE_COORDINATE_GUARD_DEGREES):
        candidate = (Fraction(native_mc) + Fraction(phase)) % 360
        action = "high_precision_intersection"
    else:
        action = "antipodal_endpoint" if opposite else "native_coordinate_retained"
    value = float(candidate)
    if value == 360:
        value = math.nextafter(360.0, 0.0)
    return value, action
