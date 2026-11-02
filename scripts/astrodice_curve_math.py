"""Exact source polynomials, fixed Bernstein subdivision and outward metrics."""

import math
from fractions import Fraction as Q
from functools import lru_cache

from scripts.astrodice_clock_interval import I


def trim(p):
    p = list(p)
    while len(p) > 1 and not p[-1]:
        p.pop()
    return p


def add(*polynomials):
    p = [Q()] * max(map(len, polynomials))
    for other in polynomials:
        for i, c in enumerate(other):
            p[i] += c
    return trim(p)


def scale(p, c):
    return trim([x * c for x in p])


def affine(p, a, b):
    out = [Q()]
    for c in reversed(p):
        out = add([c], scale(out, a), [Q(), *scale(out, b)])
    return trim(out)


def cheb_power(coefficients, half_constant=False):
    coefficients = list(map(Q, coefficients))
    out, t0, t1 = [Q()], [Q(1)], [Q(), Q(1)]
    for k, c in enumerate(coefficients):
        if k == 0:
            basis = t0
            c /= 2 if half_constant else 1
        elif k == 1:
            basis = t1
        else:
            t0, t1 = t1, add([Q(), *scale(t1, 2)], scale(t0, -1))
            basis = t1
        out = add(out, scale(basis, c))
    return trim(out)


def derivative(p, width):
    return trim([i * c / width for i, c in enumerate(p)][1:] or [Q()])


def evaluate(p, x):
    out = Q()
    for c in reversed(p):
        out = out * x + c
    return out


def bernstein(p):
    n = len(p) - 1
    return [
        sum(
            (c * Q(math.comb(i, k), math.comb(n, k)) for k, c in enumerate(p[: i + 1])),
            Q(),
        )
        for i in range(n + 1)
    ]


def split(b):
    left, right, row = [b[0]], [b[-1]], list(b)
    while len(row) > 1:
        row = [(a + c) / 2 for a, c in zip(row, row[1:])]
        left.append(row[0])
        right.append(row[-1])
    return left, right[::-1]


def leaves(b, depth):
    nodes = [b]
    for _ in range(depth):
        nodes = [child for node in nodes for child in split(node)]
    return nodes


def bernstein_derivative(b, width):
    n = len(b) - 1
    return [n * (y - x) / width for x, y in zip(b, b[1:])] or [Q()]


@lru_cache(maxsize=1)
def pi():
    def atan(n, count):
        a = sum(
            (Q((-1) ** k, (2 * k + 1) * n ** (2 * k + 1)) for k in range(count)), Q()
        )
        b = a + Q((-1) ** count, (2 * count + 1) * n ** (2 * count + 1))
        return I(min(a, b), max(a, b))

    return 16 * atan(5, 80) - 4 * atan(239, 32)


def dot(a, b):
    return sum((x * y for x, y in zip(a, b)), I())


def length(a, audit_scales=None):
    magnitude = max(x.absolute_upper() for x in a) or Q(1)
    if audit_scales is not None:
        audit_scales.append(str(magnitude))
    scaled = [x / magnitude for x in a]
    return sum((x.square() for x in scaled), I()).sqrt() * magnitude


def metrics(q, w, e, f, audit_scales=None):
    p = [x + y for x, y in zip(q, e)]
    radius, reference_radius = length(p, audit_scales), length(q, audit_scales)
    invp, invq = 1 / radius, 1 / reference_radius
    delta_radius = (2 * dot(q, e) + dot(e, e)) / (radius + reference_radius)
    delta_inverse = -delta_radius / (radius * reference_radius)
    delta_cube = delta_inverse * (invp.square() + invp * invq + invq.square())
    a = dot(q, w)
    da = dot(q, f) + dot(e, w) + dot(e, f)
    cube = invp.square() * invp
    direction = [ee * invp + qq * delta_inverse for qq, ee in zip(q, e)]
    rate = [
        ff * invp
        + ww * delta_inverse
        - ee * (a + da) * cube
        - qq * (da * cube + a * delta_cube)
        for qq, ww, ee, ff in zip(q, w, e, f)
    ]
    factor = 648000 / pi()
    return length(direction, audit_scales) * factor, length(rate, audit_scales) * factor


def interval_record(pair):
    return [list(map(str, value.bounds())) for value in pair]
