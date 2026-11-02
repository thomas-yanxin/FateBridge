"""Outward Taylor coefficients of a fixed, continuous DE441 source model.

Coefficient k encloses f^(k)/k! over the entire supplied base interval.
This is a maintenance reference, with no candidate or Swiss imports. It
does not establish Horizons equivalence or a physical TT/TDB conversion.
"""

import math
from fractions import Fraction as Q

from scripts.astrodice_clock_interval import I
from scripts.astrodice_clock_interval import Reader as BaseReader
from scripts.astrodice_source_slope_bounds import pi_bounds


class J:
    def __init__(self, value=0, derivative=0, *, degree=7):
        if type(degree) is not int or degree < 0:
            raise ValueError("Invalid source Taylor degree")
        self.c = [I.cast(value)] + [I() for _ in range(degree)]
        if degree:
            self.c[1] = I.cast(derivative)

    @classmethod
    def coefficients(cls, values):
        if not values:
            raise ValueError("Empty Taylor coefficient sequence")
        result = cls.__new__(cls)
        result.c = list(map(I.cast, values))
        return result

    @property
    def degree(self):
        return len(self.c) - 1

    @property
    def v(self):
        return self.c[0]

    def pair(self, other):
        if not isinstance(other, J):
            other = J(other, degree=self.degree)
        return other, min(self.degree, other.degree)

    def __neg__(self):
        return J.coefficients([-c for c in self.c])

    def __add__(self, other):
        other, degree = self.pair(other)
        return J.coefficients([self.c[k] + other.c[k] for k in range(degree + 1)])

    __radd__ = __add__

    def __sub__(self, other):
        other, _ = self.pair(other)
        return self + -other

    def __rsub__(self, other):
        return -self + other

    def __mul__(self, other):
        other, degree = self.pair(other)
        return J.coefficients(
            [
                sum((self.c[i] * other.c[k - i] for i in range(k + 1)), I())
                for k in range(degree + 1)
            ]
        )

    __rmul__ = __mul__

    def reciprocal(self):
        result = [1 / self.c[0]]
        for k in range(1, self.degree + 1):
            result.append(
                -result[0]
                * sum((self.c[i] * result[k - i] for i in range(1, k + 1)), I())
            )
        return J.coefficients(result)

    def __truediv__(self, other):
        other, _ = self.pair(other)
        return self * other.reciprocal()

    def __rtruediv__(self, other):
        return self.reciprocal() * other

    def sqrt(self):
        root = self.c[0].sqrt()
        if root.lo <= 0:
            raise ValueError("Taylor square root is not analytic on support")
        result = [root]
        for k in range(1, self.degree + 1):
            result.append(
                (self.c[k] - sum((result[i] * result[k - i] for i in range(1, k)), I()))
                / (2 * root)
            )
        return J.coefficients(result)

    def derivative(self):
        if not self.degree:
            raise ValueError("Derivative of an unknown higher coefficient")
        return J.coefficients([(k + 1) * self.c[k + 1] for k in range(self.degree)])


def add(a, b):
    return [x + y for x, y in zip(a, b)]


def sub(a, b):
    return [x - y for x, y in zip(a, b)]


def scale(a, b):
    return [x * b for x in a]


def dot(a, b):
    return sum((x * y for x, y in zip(a, b)), J(0, degree=min(v.degree for v in a + b)))


def norm(a):
    return dot(a, a).sqrt()


def unit(a):
    return scale(a, 1 / norm(a))


def cross(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


class Reader(BaseReader):
    def group(self, epoch, group):
        lo, hi = epoch.v.bounds()
        record = next((v for v in self.records if Q(v[0]) <= lo and hi < Q(v[1])), None)
        if record is None:
            raise ValueError("Taylor support crosses source record")
        offset, count, parts = self.pointers[group]
        width = (Q(record[1]) - Q(record[0])) / parts
        part = (lo - Q(record[0])) // width
        if not 0 <= part < parts or not hi < Q(record[0]) + (part + 1) * width:
            raise ValueError("Taylor support crosses source polynomial cell")
        self.cells.add((group, record[0], part))
        x = 2 * (epoch - Q(record[0]) - part * width) / width - 1

        def constant(value):
            return J(value, degree=epoch.degree)

        basis, derivative = [constant(1), x], [constant(0), constant(1)]
        for _ in range(2, count):
            derivative.append(2 * basis[-1] + 2 * x * derivative[-1] - derivative[-2])
            basis.append(2 * x * basis[-1] - basis[-2])
        position, velocity = [], []
        for axis in range(3):
            first = offset - 1 + (part * 3 + axis) * count
            coefficients = list(map(Q, record[first : first + count]))
            position.append(
                sum((c * b for c, b in zip(coefficients, basis)), constant(0)) / self.au
            )
            velocity.append(
                sum((c * b for c, b in zip(coefficients, derivative)), constant(0))
                * 2
                / width
                / self.au
            )
        return position + velocity


def mass(impact, profile):
    lo, hi = impact.v.bounds()
    if lo > 1:
        return J(1, degree=impact.degree), "outside"
    pairs = [(Q(float(r)), Q(float(m))) for r, m in profile]
    for i, ((r0, m0), (r1, m1)) in enumerate(zip(pairs, pairs[1:])):
        if r1 < lo <= hi < r0:
            return m0 + (impact - r0) * ((m1 - m0) / (r1 - r0)), i
    raise ValueError("Taylor support crosses source solar mass knot")


def apparent(reader, body, epoch, profile):
    reader.cells = set()
    t = J(epoch, 1)
    planet, earth, sun = [reader.state(t, n) for n in (body, "Earth", "Sun")]
    rough = planet[:3]
    for _ in range(2):
        delay = norm(sub(rough, earth[:3])) * Q(149597870700, 299792458 * 86400)
        rough = sub(planet[:3], scale(planet[3:], delay))
    emitted = reader.state(t - delay, body)
    ray = sub(emitted[:3], earth[:3])
    distance, u = norm(ray), unit(ray)
    e_ray = sub(earth[:3], sun[:3])
    re, e = norm(e_ray), unit(e_ray)
    q = unit(sub(emitted[:3], sub(sun[:3], scale(sun[3:], delay))))
    impact = norm(cross(u, e)) * re / Q((959.63 / 3600) * (math.pi / 180))
    effective, cell = mass(impact, profile)
    strength = (
        2 * Q(1.32712440017987e20) * effective / Q(299792458**2 * 149597870700) / re
    )
    denominator = dot(add(q, e), add(q, e)) / 2
    deflected = scale(
        add(u, scale(cross(u, cross(e, q)), strength / denominator)), distance
    )
    beta = scale(earth[3:], Q(149597870700, 299792458 * 86400))
    radius = norm(deflected)
    gamma = (1 - dot(beta, beta)).sqrt()
    projection = dot(deflected, beta) / radius
    result = unit(
        scale(
            add(
                scale(deflected, gamma),
                scale(beta, (1 + projection / (1 + gamma)) * radius),
            ),
            1 / (1 + projection),
        )
    )
    return result, {"polynomial_cells": sorted(reader.cells), "mass_cell": cell}


def angular_coefficients(direction):
    x, y, z = direction
    dx, dy, dz = [v.derivative() for v in direction]
    rho2 = x * x + y * y
    rho = rho2.sqrt()
    alpha = (x * dy - y * dx) / rho2
    drho = (x * dx + y * dy) / rho
    delta = (rho * dz - z * drho) / (rho2 + z * z)
    lo, hi = pi_bounds()
    factor = Q(648000) / I(lo, hi)
    # Integrating the rate series gives f^(k)/k! for k>=1. The
    # missing angular constant is intentionally never approximated here.
    return [
        [rate.c[k - 1] * factor / k for k in range(1, 8)] for rate in (alpha, delta)
    ]
