"""Outward dyadic intervals for conditional, complete apparent clock budgets.

No candidate or Decimal reference import. Every elementary operation rounds
outwards on a fixed binary grid; source states use direct Chebyshev bases.
This encloses a declared source model, not an observed TT/TDB relation.
"""

import math
import re
import struct
from fractions import Fraction as Q

BITS = 256
SCALE = 1 << BITS
FB_SHA256 = "228bd7c7c1c88dda44c29a076f289c968f64d77a2dc389138b03ab5d1d442105"


def ceil_div(a, b):
    return -((-a) // b)


class I:
    __slots__ = ("lo", "hi")

    def __init__(self, value=0, upper=None):
        lower, upper = Q(value), Q(value if upper is None else upper)
        if lower > upper:
            raise ValueError("Reversed interval")
        self.lo = lower.numerator * SCALE // lower.denominator
        self.hi = ceil_div(upper.numerator * SCALE, upper.denominator)

    @classmethod
    def scaled(cls, lo, hi):
        if type(lo) is not int or type(hi) is not int or lo > hi:
            raise ValueError("Invalid outward dyadic endpoints")
        result = cls.__new__(cls)
        result.lo, result.hi = lo, hi
        return result

    @staticmethod
    def cast(value):
        return value if isinstance(value, I) else I(value)

    def __neg__(self):
        return I.scaled(-self.hi, -self.lo)

    def __add__(self, other):
        other = I.cast(other)
        return I.scaled(self.lo + other.lo, self.hi + other.hi)

    __radd__ = __add__

    def __sub__(self, other):
        return self + -I.cast(other)

    def __rsub__(self, other):
        return I.cast(other) - self

    def __mul__(self, other):
        other = I.cast(other)
        if self is other:
            return self.square()
        values = [a * b for a in (self.lo, self.hi) for b in (other.lo, other.hi)]
        return I.scaled(min(values) // SCALE, ceil_div(max(values), SCALE))

    __rmul__ = __mul__

    def square(self):
        low = 0 if self.lo <= 0 <= self.hi else min(self.lo**2, self.hi**2)
        return I.scaled(low // SCALE, ceil_div(max(self.lo**2, self.hi**2), SCALE))

    def reciprocal(self):
        if self.lo <= 0 <= self.hi:
            raise ValueError("Interval denominator contains zero")
        return I.scaled(SCALE**2 // self.hi, ceil_div(SCALE**2, self.lo))

    def __truediv__(self, other):
        return self * I.cast(other).reciprocal()

    def __rtruediv__(self, other):
        return I.cast(other) / self

    def sqrt(self):
        if self.lo < 0:
            raise ValueError("Negative interval square root")
        lo, hi = math.isqrt(self.lo * SCALE), math.isqrt(self.hi * SCALE)
        return I.scaled(lo, hi + (hi * hi < self.hi * SCALE))

    def bounds(self):
        return Q(self.lo, SCALE), Q(self.hi, SCALE)

    def contains(self, value):
        value = Q(value) * SCALE
        return self.lo <= value <= self.hi

    def absolute_upper(self):
        return Q(max(abs(self.lo), abs(self.hi)), SCALE)

    def record(self):
        return {
            "lower_numerator": str(self.lo),
            "upper_numerator": str(self.hi),
            "denominator_power_two": BITS,
        }


class A:
    __slots__ = ("v", "d")

    def __init__(self, value=0, derivative=0):
        self.v, self.d = I.cast(value), I.cast(derivative)

    @staticmethod
    def cast(value):
        return value if isinstance(value, A) else A(value)

    def __neg__(self):
        return A(-self.v, -self.d)

    def __add__(self, other):
        other = A.cast(other)
        return A(self.v + other.v, self.d + other.d)

    __radd__ = __add__

    def __sub__(self, other):
        return self + -A.cast(other)

    def __rsub__(self, other):
        return A.cast(other) - self

    def __mul__(self, other):
        other = A.cast(other)
        return A(self.v * other.v, self.d * other.v + self.v * other.d)

    __rmul__ = __mul__

    def __truediv__(self, other):
        other = A.cast(other)
        return A(
            self.v / other.v, (self.d * other.v - self.v * other.d) / other.v.square()
        )

    def __rtruediv__(self, other):
        return A.cast(other) / self

    def sqrt(self):
        root = self.v.sqrt()
        if root.lo <= 0:
            raise ValueError("Nondifferentiable interval square root")
        return A(root, self.d / (2 * root))


def dot(a, b):
    return sum((x * y for x, y in zip(a, b)), A())


def sub(a, b):
    return [x - y for x, y in zip(a, b)]


def add(a, b):
    return [x + y for x, y in zip(a, b)]


def scale(a, b):
    return [x * b for x in a]


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


class Reader:
    def __init__(self, fixture, window):
        header = (fixture / "header.bin").read_bytes()
        if len(header) != 8144 or struct.unpack_from("<i", header, 2840)[0] != 441:
            raise ValueError("Unplanned source header")
        self.au, self.emrat = map(Q, struct.unpack_from("<2d", header, 2680))
        self.pointers = [
            struct.unpack_from("<3i", header, 2696 + 12 * g) for g in range(12)
        ]
        raw = (fixture / f"record-responses/case-{window:02}.bin").read_bytes()
        if len(raw) != 3 * 8144:
            raise ValueError("Incomplete original source window")
        self.records = [
            struct.unpack("<1018d", raw[i : i + 8144]) for i in range(0, len(raw), 8144)
        ]
        self.cells = set()

    def group(self, epoch, group):
        lower, upper = epoch.v.bounds()
        record = next(
            (v for v in self.records if Q(v[0]) <= lower and upper < Q(v[1])), None
        )
        if record is None:
            raise ValueError("Clock interval crosses a source record boundary")
        offset, count, parts = self.pointers[group]
        width = (Q(record[1]) - Q(record[0])) / parts
        piece = (lower - Q(record[0])) // width
        if not 0 <= piece < parts or not upper < Q(record[0]) + (piece + 1) * width:
            raise ValueError("Clock interval crosses a polynomial cell")
        self.cells.add((group, record[0], piece))
        x = 2 * (epoch - Q(record[0]) - piece * width) / width - 1
        basis, derivative = [A(1), x], [A(), A(1)]
        for _ in range(2, count):
            derivative.append(2 * basis[-1] + 2 * x * derivative[-1] - derivative[-2])
            basis.append(2 * x * basis[-1] - basis[-2])
        position, velocity = [], []
        for axis in range(3):
            first = offset - 1 + (piece * 3 + axis) * count
            coefficients = list(map(Q, record[first : first + count]))
            position.append(
                sum((v * b for v, b in zip(coefficients, basis)), A()) / self.au
            )
            velocity.append(
                sum((v * b for v, b in zip(coefficients, derivative)), A())
                * 2
                / width
                / self.au
            )
        return position + velocity

    def state(self, epoch, body):
        if body == "Earth":
            return sub(
                self.group(epoch, 2),
                scale(self.group(epoch, 9), Q(1) / (1 + self.emrat)),
            )
        if body not in {"Sun", "Mercury", "Venus"}:
            raise ValueError("Unsupported source body")
        return self.group(epoch, {"Sun": 10, "Mercury": 0, "Venus": 1}[body])


def mass(impact, profile):
    lo, hi = impact.v.bounds()
    if lo > 1:
        return A(1), "outside"
    rows = [(Q(float(r)), Q(float(m))) for r, m in profile]
    for index, ((r0, m0), (r1, m1)) in enumerate(zip(rows, rows[1:])):
        if r1 < lo <= hi < r0:
            return m0 + (impact - r0) * ((m1 - m0) / (r1 - r0)), index
    raise ValueError("Clock interval crosses a mass-profile knot or solar axis")


def apparent(reader, body, epoch, profile):
    if body not in {"Mercury", "Venus"}:
        raise ValueError("Unsupported apparent body")
    reader.cells = set()
    t = A(epoch, 1)
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


def clock_envelope(source, epoch):
    """Exact triangle bounds of the named analytic model; no validity extrapolation."""
    table = re.search(r"fairhd\[787\]\[3\] = \{(.*?)\n\s*\};", source, re.S)
    if table is None:
        raise ValueError("Missing full author clock table")
    values = [
        tuple(Q(float(value)) for value in v)
        for v in re.findall(
            r"\{\s*([\d.e+-]+),\s*([\d.e+-]+),\s*([\d.e+-]+)\s*\}", table.group(1)
        )
    ]
    if len(values) != 787:
        raise ValueError("Incomplete author clock terms")
    # The integer domain also encloses the small implicit TDB-TT offset.
    bound = math.ceil(abs((Q(epoch) - 2451545) / 365250)) + 1
    amplitude, derivative = Q(), Q()
    for power, (lo, hi) in enumerate(
        [(0, 474), (474, 679), (679, 764), (764, 784), (784, 787)]
    ):
        for a, b, _ in values[lo:hi]:
            amplitude += abs(a) * bound**power
            derivative += abs(a) * (
                abs(b) * bound**power + (power * bound ** (power - 1) if power else 0)
            )
    adjustments = [
        (Q("0.00065e-6"), Q("6069.776754")),
        (Q("0.00033e-6"), Q("213.299095")),
        (Q("-0.00196e-6"), Q("6208.294251")),
        (Q("-0.00173e-6"), Q("74.781599")),
    ]
    adjustments = [(Q(float(a)), Q(float(b))) for a, b in adjustments]
    if not re.search(r"0\.03638e-6\s*\* t \* t", source):
        raise ValueError("Missing author quadratic mass correction")
    quadratic = Q(float("0.03638e-6"))
    amplitude += sum((abs(a) for a, _ in adjustments), Q()) + quadratic * bound**2
    derivative += sum((abs(a * b) for a, b in adjustments), Q()) + 2 * quadratic * bound
    rho = derivative / (365250 * 86400)
    if not rho < 1 or not amplitude / (86400 * 365250) < bound - abs(
        (Q(epoch) - 2451545) / 365250
    ):
        raise ValueError("Unqualified implicit clock domain")
    factor = 1 / I(1 - rho, 1 + rho)
    return {
        "maximum_offset_seconds": amplitude,
        "delta_derivative_per_second": rho,
        "tdb_per_tt_rate_factor": factor,
        "millennium_absolute_bound": bound,
    }
