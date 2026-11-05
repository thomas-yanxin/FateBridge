"""Unclipped T position lines in the declared physical quadrant.

The native inverse's horizon/meridian reflection policy is retained. Its
89.999-degree latitude clip, rotated-latitude stopping rule, and longitude
cusp snap are replaced by a bounded phase solve over the supplied model.
This is the Swiss-style position profile, not whole-book Polich/Page acceptance.
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

TOPOCENTRIC_PROJECTION_METHOD = "fatebridge_topocentric_zero_ecliptic_latitude_v1"
TOPOCENTRIC_BRANCH_POLICY = "physical_quadrant_positive_to_negative_position_line_v1"
PHASE_FORWARD_OFFSET_ARCSECONDS = 0.001
NATIVE_INVERSE_LATITUDE_LIMIT = 89.999


@dataclass(frozen=True)
class TopocentricPosition:
    position: float
    house: int
    phase_degrees: float
    phase_degrees_decimal: str
    working_digits: tuple[int, int]
    action: str
    branch: dict[str, Any]


def _solve(
    latitude: float,
    armc: float,
    obliquity: float,
    longitude: float | Fraction,
    digits: int,
) -> dict[str, Any]:
    ctx = mp.clone()
    ctx.dps = digits
    p, t, e = [ctx.mpf(x) for x in (latitude, armc, obliquity)]
    lam = (
        ctx.mpf(longitude.numerator) / longitude.denominator
        if isinstance(longitude, Fraction)
        else ctx.mpf(longitude)
    )
    cp, sp = ctx.cospi(p / 180), ctx.sinpi(p / 180)
    ct, st = ctx.cospi(t / 180), ctx.sinpi(t / 180)
    ce, se = ctx.cospi(e / 180), ctx.sinpi(e / 180)
    cl, sl = ctx.cospi(lam / 180), ctx.sinpi(lam / 180)
    meridian = ct * cl + st * ce * sl
    east = -st * cl + ct * ce * sl
    z = se * sl
    if t % 360 == 90:
        height = cp * ct * cl + ctx.cospi((p - e) / 180) * sl
    elif t % 360 == 270:
        height = cp * ct * cl - ctx.cospi((p + e) / 180) * sl
    else:
        height = cp * meridian + sp * z
    above = height >= 0
    if not above:
        meridian, east, z = -meridian, -east, -z
    western = east < 0
    east = abs(east)
    scale = max(abs(cp * east), abs(cp * meridian), abs(sp * z))
    if not scale:
        raise ArithmeticError("Topocentric position line has no resolved direction")
    a, b, c = cp * east / scale, cp * meridian / scale, sp * z / scale
    half = ctx.pi / 2
    end = -abs(height) / scale

    def residual(x: Any) -> Any:
        if x == 0:
            return a
        if x == half:
            return end
        return a * ctx.cos(x) - b * ctx.sin(x) - c * x / half

    def derivative(x: Any) -> Any:
        return -a * ctx.sin(x) - b * ctx.cos(x) - c / half

    alternatives = []
    if a == 0:
        alternatives.append(ctx.mpf(0))
    if end == 0:
        alternatives.append(half)
    radius = ctx.mpf("1e-60")
    if a == 0 and end == 0:
        selected = half if residual(half / 2) > 0 else ctx.mpf(0)
        lower = upper = selected
        kind = "endpoint_limit"
    elif a == 0 and derivative(0) <= 0:
        selected = lower = upper = ctx.mpf(0)
        kind = "meridian_endpoint"
    elif end == 0 and derivative(half) <= 0:
        selected = lower = upper = half
        kind = "horizon_endpoint"
    else:
        lower, upper = ctx.mpf(0), half
        if a == 0:
            lower = half / 2
            for _ in range(1024):
                if residual(lower) > 0:
                    break
                lower /= 2
            else:
                raise ArithmeticError(
                    "No positive side of the interior T position line"
                )
        if end == 0:
            delta = half / 2
            for _ in range(1024):
                upper = half - delta
                if residual(upper) < 0:
                    break
                delta /= 2
            else:
                raise ArithmeticError(
                    "No negative side of the interior T position line"
                )
        x = (lower + upper) / 2
        for iteration in range(1024):
            value = residual(x)
            # A small rotated latitude is not a phase-error bound. Check a
            # bracket in the position parameter before accepting convergence.
            if abs(value) < ctx.mpf("1e-40"):
                left, right = max(lower, x - radius), min(upper, x + radius)
                if residual(left) > 0 and residual(right) < 0:
                    lower, upper = left, right
                    break
                if value == 0:
                    raise ArithmeticError("T root sign bracket needs more precision")
            if value > 0:
                lower = x
            else:
                upper = x
            if upper - lower <= radius:
                break
            slope = derivative(x)
            proposal = x - value / slope if slope else (lower + upper) / 2
            if iteration % 3 == 2 or not lower < proposal < upper:
                proposal = (lower + upper) / 2
            x = proposal
        else:
            raise ArithmeticError("Bounded T position solve did not converge")
        selected = (lower + upper) / 2
        alternatives.append(selected)
        kind = "positive_to_negative_interior"

    def phase(root: Any) -> Any:
        if western:
            root = -root
        if not above:
            root += ctx.pi
        return (root * 180 / ctx.pi - 90 + ctx.mpf(1) / 3600000) % 360

    return dict(
        ctx=ctx,
        phase=phase(selected),
        root=selected,
        candidates=sorted(alternatives),
        candidate_phases=[phase(x) for x in sorted(alternatives)],
        above=above,
        western=western,
        kind=kind,
        bracket_width=(upper - lower) * 180 / ctx.pi,
    )


def _position(ctx: Any, phase: Any) -> tuple[float, int]:
    house = int(ctx.floor(phase / 30)) + 1
    position = float(phase / 30 + 1)
    if math.floor(position) > house:
        position = math.nextafter(position, -math.inf)
    if not 1 <= position < 13 or math.floor(position) != house:
        raise ArithmeticError("T position cannot represent its half-open house")
    return position, house


def checked_topocentric_position(
    *,
    latitude: float,
    armc: float,
    obliquity: float,
    longitude: float | Fraction,
    native_position: float,
) -> TopocentricPosition:
    if not all(math.isfinite(x) for x in (latitude, armc, obliquity, longitude)):
        raise ValueError("Topocentric precision requires finite model inputs")
    if abs(latitude) >= 90:
        raise ArithmeticError(
            "An exact geographic pole requires an explicit limit convention"
        )
    previous = None
    for digits in WORKING_DIGITS:
        try:
            high = _solve(latitude, armc, obliquity, longitude, digits)
        except ArithmeticError:
            previous = None
            continue
        if previous is not None:
            low_digits, low = previous
            ctx = high["ctx"]
            line = ctx.mpf(CONVERGENCE_DEGREES)
            equal_branch = (
                low["above"] == high["above"]
                and low["western"] == high["western"]
                and low["kind"] == high["kind"]
                and len(low["candidates"]) == len(high["candidates"])
            )
            distance = abs((ctx.mpf(low["phase"]) - high["phase"] + 180) % 360 - 180)
            candidates_agree = all(
                abs(ctx.mpf(a) - b) * 180 / ctx.pi <= line
                for a, b in zip(low["candidates"], high["candidates"])
            )
            if equal_branch and distance <= line and candidates_agree:
                break
        previous = digits, high
    else:
        raise ArithmeticError(
            "T inverse or its branch did not converge across precisions"
        )
    ctx = high["ctx"]
    value, house = _position(ctx, high["phase"])
    action = "topocentric_scalar_inverse_recomputed"
    if (
        math.isfinite(native_position)
        and 1 <= native_position < 13
        and int(native_position) == house
    ):
        error = abs(
            ((ctx.mpf(native_position) - 1) * 30 - high["phase"] + 180) % 360 - 180
        )
        if error <= ctx.mpf(NATIVE_COORDINATE_GUARD_DEGREES):
            value = native_position
            action = "native_coordinate_retained"
    phase = float(high["phase"])
    if phase == 360:
        phase = math.nextafter(360.0, 0.0)
    branch = dict(
        above_horizon=high["above"],
        reflected_western=high["western"],
        candidate_scope="all_admissible_roots_in_the_declared_physical_quadrant",
        root_selection=high["kind"],
        selected_root_degrees=float(high["root"] * 180 / ctx.pi),
        candidate_root_degrees=[float(x * 180 / ctx.pi) for x in high["candidates"]],
        candidate_positions=[_position(ctx, x)[0] for x in high["candidate_phases"]],
        computed_root_bracket_width_degrees=ctx.nstr(high["bracket_width"], 100),
        geographic_latitude_used=latitude,
        latitude_clamped=False,
    )
    return TopocentricPosition(
        value,
        house,
        phase,
        ctx.nstr(high["phase"], 100),
        (low_digits, digits),
        action,
        branch,
    )
