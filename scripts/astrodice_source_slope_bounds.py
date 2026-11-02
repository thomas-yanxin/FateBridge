"""Outward angular-rate bounds for a declared Cartesian source direction.

These bounds concern the supplied mathematical model, not Horizons' internal
implementation, actual epoch errors, or physical ephemeris accuracy.
"""

from fractions import Fraction as Q

from scripts.astrodice_clock_interval import I


def arctangent_bounds(inverse, terms):
    if type(inverse) is not int or inverse <= 1 or type(terms) is not int or terms < 1:
        raise ValueError("Invalid alternating arctangent declaration")
    total = sum(
        (Q((-1) ** k, (2 * k + 1) * inverse ** (2 * k + 1)) for k in range(terms)), Q()
    )
    other = total + Q((-1) ** terms, (2 * terms + 1) * inverse ** (2 * terms + 1))
    return min(total, other), max(total, other)


def pi_bounds():
    # Machin identity pi = 16 atan(1/5) - 4 atan(1/239).
    a, b = arctangent_bounds(5, 32), arctangent_bounds(239, 16)
    return 16 * a[0] - 4 * b[1], 16 * a[1] - 4 * b[0]


def angular_rate_bounds(direction):
    if len(direction) != 3:
        raise ValueError("Three source direction/derivative components required")
    x, y, z = direction
    rho2 = x.v.square() + y.v.square()
    rho = rho2.sqrt()
    ra = (x.v * y.d - y.v * x.d) / rho2
    drho = (x.v * x.d + y.v * y.d) / rho
    dec = (rho * z.d - z.v * drho) / (rho2 + z.v.square())
    lo, hi = pi_bounds()
    factor = Q(648000) / I(lo, hi)
    return [(value * factor).absolute_upper() for value in (ra, dec)]
