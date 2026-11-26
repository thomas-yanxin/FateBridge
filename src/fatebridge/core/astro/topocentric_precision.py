"""Unclipped T position lines in the declared physical quadrant.

The native inverse's horizon/meridian reflection policy is retained. Its
89.999-degree latitude clip, rotated-latitude stopping rule, and longitude
cusp snap are replaced by a bounded phase solve over the supplied model.
The geometric phase is unshifted and determines the half-open house;
binary64 delivery preserves that ownership. This is the Swiss-style position
profile, not whole-book Polich/Page acceptance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from mpmath import mp  # type: ignore[import-untyped]
from mpmath.libmp import to_rational  # type: ignore[import-untyped]

from fatebridge.core.astro.horizon_precision import (
    CONVERGENCE_DEGREES,
    WORKING_DIGITS,
)

TOPOCENTRIC_PROJECTION_METHOD = "fatebridge_topocentric_zero_ecliptic_latitude_v2"
TOPOCENTRIC_BRANCH_POLICY = "physical_quadrant_positive_to_negative_position_line_v1"
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
    phase_degrees_working: Fraction


def _solve(
    latitude: float,
    armc: float,
    obliquity: float,
    longitude: float | Fraction,
    digits: int,
    scale_bits: int,
) -> dict[str, Any]:
    ctx = mp.clone()
    ctx.dps = digits
    p_exact, t_exact, e_exact, lam_exact = (
        Fraction(value) for value in (latitude, armc, obliquity, longitude)
    )
    # Reduce exact angles before a finite-precision conversion can discard a
    # small nonzero cardinal offset.
    p, t, e, lam = [
        ctx.mpf(value.numerator) / value.denominator
        for value in (p_exact, t_exact % 360, e_exact % 360, lam_exact % 360)
    ]
    exact_equatorial = lam_exact % 180 == 0 or (
        p_exact == 0 and lam_exact % 180 == 90 and abs((e_exact + 180) % 360 - 180) < 90
    )
    if exact_equatorial:
        # Here z=0, or sp=0 with a positive equatorial amplitude. The
        # residual is a positive multiple of sin(alpha-theta-90*y).
        delta = (lam_exact - t_exact) % 360
        above = delta <= 90 or delta >= 270
        if not above:
            delta = (delta + 180) % 360
        western = delta > 180
        root = 360 - delta if western else delta
        kind = (
            "meridian_endpoint"
            if root == 0
            else "horizon_endpoint" if root == 90 else "positive_to_negative_interior"
        )
        return dict(
            ctx=ctx,
            phase=_phase(root, above, western),
            root=root,
            candidates=[root],
            candidate_phases=[_phase(root, above, western)],
            above=above,
            western=western,
            kind=kind,
            bracket_width=Fraction(0),
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
    end = -abs(height) / scale

    def residual(y: Fraction) -> Any:
        if y == 0:
            return a
        if y == 1:
            return end
        value = ctx.mpf(y.numerator) / y.denominator
        return a * ctx.cospi(value / 2) - b * ctx.sinpi(value / 2) - c * value

    def derivative(y: Fraction) -> Any:
        value = ctx.mpf(y.numerator) / y.denominator
        return -(ctx.pi / 2) * (a * ctx.sinpi(value / 2) + b * ctx.cospi(value / 2)) - c

    alternatives = []
    if a == 0:
        alternatives.append(Fraction(0))
    if end == 0:
        alternatives.append(Fraction(1))
    budget = 1024 + scale_bits
    # This numerical sign bracket is checked across private contexts; it is
    # not an outward-rounded transcendental interval certificate.
    radius = Fraction(1, 10 ** (60 + (scale_bits * 30103 + 99999) // 100000))

    def resolved(lower: Fraction, upper: Fraction) -> bool:
        if 90 * (upper - lower) > radius:
            return False
        first, last = sorted(
            (_phase(90 * lower, above, western), _phase(90 * upper, above, western))
        )
        # A short bracket crossing the circular seam must continue refining.
        if last - first > 180:
            return False
        return (
            first // 30 == last // 30
            and float(first) == float(last)
            and _position(first) == _position(last)
            and float(90 * lower) == float(90 * upper)
        )

    if a == 0 and end == 0:
        selected = Fraction(1) if residual(Fraction(1, 2)) > 0 else Fraction(0)
        lower = upper = selected
        kind = "endpoint_limit"
    elif a == 0 and derivative(Fraction(0)) <= 0:
        selected = lower = upper = Fraction(0)
        kind = "meridian_endpoint"
    elif end == 0 and derivative(Fraction(1)) <= 0:
        selected = lower = upper = Fraction(1)
        kind = "horizon_endpoint"
    else:
        lower, upper = Fraction(0), Fraction(1)
        if a == 0:
            lower = Fraction(1, 2)
            for _ in range(budget):
                if residual(lower) > 0:
                    break
                lower /= 2
            else:
                raise ArithmeticError(
                    "No positive side of the interior T position line"
                )
        if end == 0:
            delta = Fraction(1, 2)
            for _ in range(budget):
                upper = 1 - delta
                if residual(upper) < 0:
                    break
                delta /= 2
            else:
                raise ArithmeticError(
                    "No negative side of the interior T position line"
                )
        x = (lower + upper) / 2
        for iteration in range(budget):
            value = residual(x)
            if abs(value) < ctx.mpf("1e-40"):
                probe_radius = min(radius / 180, (upper - lower) / 4)
                left, right = max(lower, x - probe_radius), min(upper, x + probe_radius)
                if residual(left) > 0 and residual(right) < 0:
                    lower, upper = left, right
                    if resolved(lower, upper):
                        break
                    if value == 0:
                        # Numerical zero is not a proved singleton root.
                        x = (2 * lower + upper) / 3
                        continue
                elif value == 0:
                    raise ArithmeticError("T root sign bracket needs more precision")
            if value > 0:
                lower = x
            else:
                upper = x
            if resolved(lower, upper):
                break
            slope = derivative(x)
            if slope:
                working_x = ctx.mpf(x.numerator) / x.denominator
                proposal = Fraction(*to_rational((working_x - value / slope)._mpf_))
            else:
                proposal = (lower + upper) / 2
            if iteration % 3 == 2 or not lower < proposal < upper:
                proposal = (lower + upper) / 2
            x = proposal
        else:
            raise ArithmeticError("Bounded T position solve did not converge")
        selected = (lower + upper) / 2
        alternatives.append(selected)
        kind = "positive_to_negative_interior"
    roots = [90 * value for value in sorted(alternatives)]

    return dict(
        ctx=ctx,
        phase=_phase(90 * selected, above, western),
        root=90 * selected,
        candidates=roots,
        candidate_phases=[_phase(root, above, western) for root in roots],
        above=above,
        western=western,
        kind=kind,
        bracket_width=90 * (upper - lower),
    )


def _phase(root: Fraction, above: bool, western: bool) -> Fraction:
    return ((-root if western else root) + (0 if above else 180) - 90) % 360


def _position(phase: Fraction) -> tuple[float, int]:
    house = phase // 30 + 1
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
    scale_bits = 0
    for angle in (latitude, armc, obliquity, longitude):
        offset = Fraction(angle) % 90
        offset = min(offset, 90 - offset)
        if 0 < offset < 1:
            numerator, denominator = offset.numerator, offset.denominator
            bits = max(0, denominator.bit_length() - numerator.bit_length())
            scale_bits = max(scale_bits, bits + int(numerator << bits < denominator))
    extra_digits = (scale_bits * 30103 + 99999) // 100000
    for digits in (value + extra_digits for value in WORKING_DIGITS):
        try:
            high = _solve(latitude, armc, obliquity, longitude, digits, scale_bits)
        except ArithmeticError:
            previous = None
            continue
        if previous is not None:
            low_digits, low = previous
            line = Fraction(CONVERGENCE_DEGREES)
            equal_branch = (
                low["above"] == high["above"]
                and low["western"] == high["western"]
                and low["kind"] == high["kind"]
                and len(low["candidates"]) == len(high["candidates"])
            )
            distance = abs((low["phase"] - high["phase"] + 180) % 360 - 180)
            candidates_agree = all(
                abs(a - b) <= line and float(a) == float(b)
                for a, b in zip(low["candidates"], high["candidates"])
            )
            deliveries_agree = (
                _position(low["phase"]) == _position(high["phase"])
                and float(low["phase"]) == float(high["phase"])
                and all(
                    _position(a) == _position(b) and float(a) == float(b)
                    for a, b in zip(low["candidate_phases"], high["candidate_phases"])
                )
            )
            if (
                equal_branch
                and distance <= line
                and candidates_agree
                and deliveries_agree
            ):
                break
        previous = digits, high
    else:
        raise ArithmeticError(
            "T inverse or its branch did not converge across precisions"
        )
    ctx = high["ctx"]
    value, house = _position(high["phase"])
    action = (
        "native_coordinate_retained"
        if native_position == value
        else "topocentric_scalar_inverse_recomputed"
    )
    phase = float(high["phase"])
    if phase == 360:
        phase = math.nextafter(360.0, 0.0)
    branch = dict(
        above_horizon=high["above"],
        reflected_western=high["western"],
        candidate_scope="all_admissible_roots_in_the_declared_physical_quadrant",
        root_selection=high["kind"],
        selected_root_degrees=float(high["root"]),
        candidate_root_degrees=[float(x) for x in high["candidates"]],
        candidate_positions=[_position(x)[0] for x in high["candidate_phases"]],
        computed_root_bracket_width_degrees=ctx.nstr(
            ctx.mpf(high["bracket_width"].numerator)
            / high["bracket_width"].denominator,
            100,
        ),
        geographic_latitude_used=latitude,
        latitude_clamped=False,
    )
    return TopocentricPosition(
        value,
        house,
        phase,
        ctx.nstr(
            ctx.mpf(high["phase"].numerator) / high["phase"].denominator,
            max(100, digits),
        ),
        (low_digits, digits),
        action,
        branch,
        high["phase"],
    )
