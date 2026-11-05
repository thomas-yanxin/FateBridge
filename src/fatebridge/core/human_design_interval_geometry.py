"""Portable outward-rounded integer intervals for nominal angular geometry.

All interval endpoints are integers scaled by2**bits. No platform transcendental
function, decimal context, numerical tolerance or empirical error estimate is
used. Series tails are bounded analytically. Precision increases until both
endpoints round to one binary64 value and prove the unchanged classification.
This says nothing about the physical accuracy of supplied native coordinates.
"""

from fractions import Fraction
from functools import lru_cache
from math import factorial, isqrt

METHOD = "integer_interval_nominal_projection_v2"
Interval = tuple[int, int]


class ProjectionRoundingUnresolved(ValueError):
    """Valid supplied coordinates exceeded the finite arithmetic budget."""


class _MorePrecision(Exception):
    pass


def _ceil(n: int, d: int) -> int:
    return -(-n // d)


def _add(a: Interval, b: Interval) -> Interval:
    return a[0] + b[0], a[1] + b[1]


def _neg(a: Interval) -> Interval:
    return -a[1], -a[0]


def _sub(a: Interval, b: Interval) -> Interval:
    return _add(a, _neg(b))


def _scale(a: Interval, n: int) -> Interval:
    return (a[0] * n, a[1] * n) if n >= 0 else (a[1] * n, a[0] * n)


def _divide_integer(a: Interval, n: int) -> Interval:
    if n <= 0:
        raise ValueError("Positive interval divisor required")
    return a[0] // n, _ceil(a[1], n)


class _Arithmetic:
    def __init__(self, bits: int):
        self.bits = bits
        self.s = 1 << bits
        self.one = (self.s, self.s)

    def rational(self, n: int, d: int) -> Interval:
        if d <= 0:
            raise ValueError("Positive rational denominator required")
        return n * self.s // d, _ceil(n * self.s, d)

    def multiply(self, a: Interval, b: Interval) -> Interval:
        products = [x * y for x in a for y in b]
        return min(products) // self.s, _ceil(max(products), self.s)

    def square(self, a: Interval) -> Interval:
        low = 0 if a[0] <= 0 <= a[1] else min(a[0] ** 2, a[1] ** 2)
        return low // self.s, _ceil(max(a[0] ** 2, a[1] ** 2), self.s)

    def divide(self, a: Interval, b: Interval) -> Interval:
        if b[0] <= 0:
            raise _MorePrecision
        return min(x * self.s // y for x in a for y in b), max(
            _ceil(x * self.s, y) for x in a for y in b
        )

    def sqrt(self, a: Interval) -> Interval:
        # Every caller has an independently known nonnegative radicand.
        if a[1] < 0:
            raise ValueError("Negative radicand enclosure")
        lo, hi = isqrt(max(0, a[0]) * self.s), isqrt(a[1] * self.s)
        return lo, hi + (hi * hi != a[1] * self.s)

    def sincos_degrees(self, angle: Fraction) -> tuple[Interval, Interval]:
        quadrant = (angle + 45) // 90
        residual = angle - 90 * quadrant
        if residual == 0:
            sine, cosine = (0, 0), self.one
        else:
            x = _divide_integer(
                _scale(_pi(self.bits), residual.numerator),
                residual.denominator * 180,
            )
            # |residual|<=45degrees and pi<4, hence |x|<1.
            if max(abs(x[0]), abs(x[1])) >= self.s:
                raise _MorePrecision
            square = self.square(x)
            sine = sine_term = x
            cosine = cosine_term = self.one
            count = self.bits // 4 + 8
            for k in range(1, count):
                sine_term = _divide_integer(
                    _neg(self.multiply(sine_term, square)), 2 * k * (2 * k + 1)
                )
                cosine_term = _divide_integer(
                    _neg(self.multiply(cosine_term, square)), (2 * k - 1) * 2 * k
                )
                sine, cosine = _add(sine, sine_term), _add(cosine, cosine_term)
            # Alternating real-series remainder <=1/(2count)! for both sums.
            error = _ceil(self.s, factorial(2 * count))
            sine = sine[0] - error, sine[1] + error
            cosine = cosine[0] - error, cosine[1] + error
        return (
            (sine, cosine),
            (cosine, _neg(sine)),
            (_neg(sine), _neg(cosine)),
            (_neg(cosine), sine),
        )[quadrant % 4]

    def atan_nonnegative(self, value: Interval) -> Interval:
        if value == (0, 0):
            return 0, 0
        if value[0] < 0:
            raise _MorePrecision
        x = value
        for _ in range(3):
            x = self.divide(
                x, _add(self.one, self.sqrt(_add(self.one, self.square(x))))
            )
        if x[1] > self.s // 8:
            raise _MorePrecision
        square, power, total = self.square(x), x, x
        count = self.bits // 4 + 8
        for k in range(1, count):
            power = _neg(self.multiply(power, square))
            total = _add(total, _divide_integer(power, 2 * k + 1))
        # |x|<=1/8: first omitted term <=(1/8)**(2count+1).
        error = _ceil(self.s, 8 ** (2 * count + 1))
        return max(0, (total[0] - error) * 8), (total[1] + error) * 8

    def atan2_nonnegative_y(self, y: Interval, x: Interval) -> Interval:
        if y[0] < 0:
            raise ValueError("Nonnegative ordinate required")
        if y == (0, 0):
            if x[0] > 0:
                return 0, 0
            if x[1] < 0:
                return _pi(self.bits)
            raise _MorePrecision
        norm = self.sqrt(_add(self.square(x), self.square(y)))
        # Both formulas are valid on either side of x=0. Choose the stable one.
        if x[0] + x[1] >= 0:
            t = self.divide(y, _add(norm, x))
            return _scale(self.atan_nonnegative(t), 2)
        t = self.divide(y, _sub(norm, x))
        return _sub(_pi(self.bits), _scale(self.atan_nonnegative(t), 2))

    def rounded(self, value: Interval) -> float:
        lo, hi = (float(Fraction(endpoint, self.s)) for endpoint in value)
        if lo != hi:
            raise _MorePrecision
        # Canonical positive zero avoids a platform/serialization sign choice.
        return lo if lo else 0.0


@lru_cache(maxsize=8)
def _pi(bits: int) -> Interval:
    a = _Arithmetic(bits)

    def atan_inverse(q: int) -> Interval:
        total, power, k = (0, 0), q, 0
        while True:
            term = a.rational(1, (2 * k + 1) * power)
            total = _add(total, term if k % 2 == 0 else _neg(term))
            power *= q * q
            k += 1
            denominator = (2 * k + 1) * power
            if denominator > a.s * 4096:
                # Alternating remainder bounded by the next exact term.
                error = _ceil(a.s, denominator)
                return total[0] - error, total[1] + error

    return _sub(_scale(atan_inverse(5), 16), _scale(atan_inverse(239), 4))


@lru_cache(maxsize=512)
def _vector(lon: float, lat: float, bits: int) -> tuple[Interval, ...]:
    a = _Arithmetic(bits)
    sl, cl = a.sincos_degrees(Fraction(lon))
    sb, cb = a.sincos_degrees(Fraction(lat))
    return a.multiply(cb, cl), a.multiply(cb, sl), sb


def _separation(
    sun: tuple[float, ...], target: tuple[float, ...], a: _Arithmetic
) -> Interval:
    if sun[:2] == target[:2] or (sun[1] == target[1] and abs(sun[1]) == 90):
        return 0, 0
    if sun[1] == -target[1] and (
        abs(sun[1]) == 90 or abs(Fraction(sun[0]) - Fraction(target[0])) == 180
    ):
        return _pi(a.bits)
    u, v = _vector(*sun[:2], a.bits), _vector(*target[:2], a.bits)
    cross = (
        _sub(a.multiply(u[1], v[2]), a.multiply(u[2], v[1])),
        _sub(a.multiply(u[2], v[0]), a.multiply(u[0], v[2])),
        _sub(a.multiply(u[0], v[1]), a.multiply(u[1], v[0])),
    )
    norm, dot = (0, 0), (0, 0)
    for i in range(3):
        norm = _add(norm, a.square(cross[i]))
        dot = _add(dot, a.multiply(u[i], v[i]))
    return a.atan2_nonnegative_y(a.sqrt(norm), dot)


def portable_projection_scalars(
    sun: tuple[float, ...],
    target: tuple[float, ...],
    radius_m: int,
    au_m: int,
    resolution: float,
    *,
    include_enclosures: bool = False,
) -> dict:
    distance = Fraction(sun[2])
    ratio = Fraction(radius_m, au_m) / distance
    if not 0 < ratio < 1:
        raise ValueError("Observer is not outside the nominal solar sphere")
    threshold = Fraction(resolution)
    for bits in (128, 256, 512, 1024, 2048, 4096, 8192):
        a = _Arithmetic(bits)
        try:
            separation = _separation(sun, target, a)
            q = a.rational(ratio.numerator, ratio.denominator)
            radius = a.atan2_nonnegative_y(q, a.sqrt(_sub(a.one, a.square(q))))
            margin = _sub(separation, radius)
            lo, hi = (Fraction(endpoint, a.s) for endpoint in margin)
            if lo > threshold:
                relation = "outside_nominal_disk"
            elif hi < -threshold:
                relation = "inside_nominal_disk"
            elif lo >= -threshold and hi <= threshold:
                relation = "numerical_boundary_undetermined"
            else:
                raise _MorePrecision
            return {
                "separation_radians": a.rounded(separation),
                "nominal_solar_radius_radians": a.rounded(radius),
                "projection_margin_radians": a.rounded(margin),
                "projection_relation": relation,
                "inside_nominal_solar_disk_projection": (
                    None
                    if relation == "numerical_boundary_undetermined"
                    else relation == "inside_nominal_disk"
                ),
                "arithmetic_method": METHOD,
                "arithmetic_interval_bits": bits,
                "arithmetic_rounding_status": "enclosure_endpoints_round_to_same_binary64",
                "zero_sign_policy": "canonical_positive_zero",
                **(
                    {
                        "arithmetic_enclosures_exact": {
                            key: [str(Fraction(v, a.s)) for v in bounds]
                            for key, bounds in (
                                ("separation_radians", separation),
                                ("nominal_solar_radius_radians", radius),
                                ("projection_margin_radians", margin),
                            )
                        }
                    }
                    if include_enclosures
                    else {}
                ),
            }
        except _MorePrecision:
            continue
    raise ProjectionRoundingUnresolved(
        "Nominal geometry rounding not resolved within precision budget"
    )
