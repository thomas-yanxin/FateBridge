"""Compensated source-polynomial evaluation with final unit projection.

Full c0 and analytic derivatives share the same two-component recurrence.
The EFT arithmetic assumes no intermediate overflow or underflow; it is not
an all-input correct-rounding certificate. Source/model uncertainty remains
separate from arithmetic at the supplied coordinate.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import NamedTuple, Sequence

from fatebridge.utils.errors import EphemerisSourceError

DoubleDouble = tuple[float, float]
Vector = tuple[float, float, float]


def _add(*values: DoubleDouble) -> DoubleDouble:
    terms = _flatten_terms(values)
    high = math.fsum(terms)
    return high, math.fsum((*terms, -high))


def _product(a: float, b: float) -> DoubleDouble:
    value = a * b
    split_a = 134217729.0 * a
    high_a = split_a - (split_a - a)
    low_a = a - high_a
    split_b = 134217729.0 * b
    high_b = split_b - (split_b - b)
    low_b = b - high_b
    error = (
        (high_a * high_b - value) + high_a * low_b + low_a * high_b
    ) + low_a * low_b
    return value, error


def _multiply(a: DoubleDouble, b: DoubleDouble) -> DoubleDouble:
    return _add(
        _product(a[0], b[0]),
        (a[0] * b[1], a[1] * b[0]),
        (a[1] * b[1], 0.0),
    )


def _divide(value: DoubleDouble, divisor: float) -> DoubleDouble:
    high = value[0] / divisor
    product, error = _product(high, divisor)
    residual = _add(value, (-product, -error))
    return _add((high, 0.0), (math.fsum(residual) / divisor, 0.0))


class ChebyshevKinematics(NamedTuple):
    """Value and two source derivatives before final float delivery."""

    value: DoubleDouble
    first_derivative: DoubleDouble
    second_derivative: DoubleDouble

    def in_units(
        self, derivative_scale: float = 1.0, divisor: float = 1.0
    ) -> ChebyshevKinematics:
        """Keep source quantities compensated through unit conversion.

        Preserve full source precision when higher derivatives are omitted.
        """
        return ChebyshevKinematics(
            _divide(self.value, divisor),
            _scale_dd(self.first_derivative, derivative_scale, divisor),
            _scale_dd(
                self.second_derivative,
                derivative_scale * derivative_scale,
                divisor,
            ),
        )

    def plus(self, other: ChebyshevKinematics) -> ChebyshevKinematics:
        """Combine quantities already on the same source clock and units."""
        return ChebyshevKinematics(
            _add(self.value, other.value),
            _add_dd(self.first_derivative, other.first_derivative),
            _add_dd(self.second_derivative, other.second_derivative),
        )

    def minus(
        self, other: ChebyshevKinematics, divisor: float = 1.0
    ) -> ChebyshevKinematics:
        """Subtract another source contribution divided by its given ratio."""
        p = _divide(other.value, divisor)
        v = _divide_dd(other.first_derivative, divisor)
        a = _divide_dd(other.second_derivative, divisor)
        return ChebyshevKinematics(
            _add(self.value, (-p[0], -p[1])),
            _add_dd(self.first_derivative, (-v[0], -v[1])),
            _add_dd(self.second_derivative, (-a[0], -a[1])),
        )

    def rounded(self) -> Vector:
        """Project the complete source quantities to their float boundary."""
        return (
            math.fsum(self.value),
            math.fsum(self.first_derivative),
            math.fsum(self.second_derivative),
        )

    def scaled(self, derivative_scale: float = 1.0, divisor: float = 1.0) -> Vector:
        """Convert units and project once when no source combination follows."""
        return self.in_units(derivative_scale, divisor).rounded()


def chebyshev_eval_float(
    coefficients: Sequence[float],
    x: float,
    *,
    need_derivative: bool = True,
) -> tuple[float, float]:
    """Fast IEEE-754 float64 Clenshaw evaluation (value, first_derivative)."""
    if not coefficients or not -1.0 <= x <= 1.0:
        raise EphemerisSourceError("jpl_kinematics_invalid")
    tx = 2.0 * x
    b1 = b2 = 0.0
    if not need_derivative:
        for coefficient in reversed(coefficients[1:]):
            b0 = coefficient + tx * b1 - b2
            b2, b1 = b1, b0
        return coefficients[0] + x * b1 - b2, 0.0
    d1 = d2 = 0.0
    for coefficient in reversed(coefficients[1:]):
        b0 = coefficient + tx * b1 - b2
        d0 = 2.0 * b1 + tx * d1 - d2
        b2, b1 = b1, b0
        d2, d1 = d1, d0
    return coefficients[0] + x * b1 - b2, b1 + x * d1 - d2


def chebyshev_kinematics(
    coefficients: Sequence[float],
    x: float | Fraction,
    *,
    derivatives: int = 2,
) -> ChebyshevKinematics:
    """Full-c0 differentiated Clenshaw with two-component source arithmetic."""
    if (
        not coefficients
        or derivatives not in (0, 1, 2)
        or not -1 <= x <= 1
        or not all(math.isfinite(c) for c in coefficients)
    ):
        raise EphemerisSourceError("jpl_kinematics_invalid")
    if isinstance(x, Fraction):
        high = float(x)
        coord_h, coord_l = high, float(x - Fraction(high))
    else:
        coord_h, coord_l = x, 0.0
    tx_h, tx_l = coord_h * 2, coord_l * 2
    split_tx = 134217729.0 * tx_h
    tx_hi = split_tx - (split_tx - tx_h)
    tx_lo = tx_h - tx_hi
    fsum = math.fsum
    b1h = b1l = b2h = b2l = 0.0
    d1h = d1l = d2h = d2l = 0.0
    a1h = a1l = a2h = a2l = 0.0
    tail = reversed(coefficients[1:])
    if derivatives == 0:
        for coefficient in tail:
            p = tx_h * b1h
            sb = 134217729.0 * b1h
            b_hi = sb - (sb - b1h)
            b_lo = b1h - b_hi
            e = ((tx_hi * b_hi - p) + tx_hi * b_lo + tx_lo * b_hi) + tx_lo * b_lo
            mh = fsum((p, e, tx_h * b1l, tx_l * b1h, tx_l * b1l, 0.0))
            ml = fsum((p, e, tx_h * b1l, tx_l * b1h, tx_l * b1l, 0.0, -mh))
            b0h = fsum((coefficient, 0.0, mh, ml, -b2h, -b2l))
            b0l = fsum((coefficient, 0.0, mh, ml, -b2h, -b2l, -b0h))
            b2h, b2l, b1h, b1l = b1h, b1l, b0h, b0l
    elif derivatives == 1:
        for coefficient in tail:
            p = tx_h * b1h
            sb = 134217729.0 * b1h
            b_hi = sb - (sb - b1h)
            b_lo = b1h - b_hi
            e = ((tx_hi * b_hi - p) + tx_hi * b_lo + tx_lo * b_hi) + tx_lo * b_lo
            mh = fsum((p, e, tx_h * b1l, tx_l * b1h, tx_l * b1l, 0.0))
            ml = fsum((p, e, tx_h * b1l, tx_l * b1h, tx_l * b1l, 0.0, -mh))
            b0h = fsum((coefficient, 0.0, mh, ml, -b2h, -b2l))
            b0l = fsum((coefficient, 0.0, mh, ml, -b2h, -b2l, -b0h))
            p = tx_h * d1h
            sb = 134217729.0 * d1h
            b_hi = sb - (sb - d1h)
            b_lo = d1h - b_hi
            e = ((tx_hi * b_hi - p) + tx_hi * b_lo + tx_lo * b_hi) + tx_lo * b_lo
            mh = fsum((p, e, tx_h * d1l, tx_l * d1h, tx_l * d1l, 0.0))
            ml = fsum((p, e, tx_h * d1l, tx_l * d1h, tx_l * d1l, 0.0, -mh))
            d0h = fsum((2 * b1h, 2 * b1l, mh, ml, -d2h, -d2l))
            d0l = fsum((2 * b1h, 2 * b1l, mh, ml, -d2h, -d2l, -d0h))
            b2h, b2l, b1h, b1l = b1h, b1l, b0h, b0l
            d2h, d2l, d1h, d1l = d1h, d1l, d0h, d0l
    else:
        for coefficient in tail:
            p = tx_h * b1h
            sb = 134217729.0 * b1h
            b_hi = sb - (sb - b1h)
            b_lo = b1h - b_hi
            e = ((tx_hi * b_hi - p) + tx_hi * b_lo + tx_lo * b_hi) + tx_lo * b_lo
            mh = fsum((p, e, tx_h * b1l, tx_l * b1h, tx_l * b1l, 0.0))
            ml = fsum((p, e, tx_h * b1l, tx_l * b1h, tx_l * b1l, 0.0, -mh))
            b0h = fsum((coefficient, 0.0, mh, ml, -b2h, -b2l))
            b0l = fsum((coefficient, 0.0, mh, ml, -b2h, -b2l, -b0h))
            p = tx_h * d1h
            sb = 134217729.0 * d1h
            b_hi = sb - (sb - d1h)
            b_lo = d1h - b_hi
            e = ((tx_hi * b_hi - p) + tx_hi * b_lo + tx_lo * b_hi) + tx_lo * b_lo
            mh = fsum((p, e, tx_h * d1l, tx_l * d1h, tx_l * d1l, 0.0))
            ml = fsum((p, e, tx_h * d1l, tx_l * d1h, tx_l * d1l, 0.0, -mh))
            d0h = fsum((2 * b1h, 2 * b1l, mh, ml, -d2h, -d2l))
            d0l = fsum((2 * b1h, 2 * b1l, mh, ml, -d2h, -d2l, -d0h))
            p = tx_h * a1h
            sb = 134217729.0 * a1h
            b_hi = sb - (sb - a1h)
            b_lo = a1h - b_hi
            e = ((tx_hi * b_hi - p) + tx_hi * b_lo + tx_lo * b_hi) + tx_lo * b_lo
            mh = fsum((p, e, tx_h * a1l, tx_l * a1h, tx_l * a1l, 0.0))
            ml = fsum((p, e, tx_h * a1l, tx_l * a1h, tx_l * a1l, 0.0, -mh))
            a0h = fsum((4 * d1h, 4 * d1l, mh, ml, -a2h, -a2l))
            a0l = fsum((4 * d1h, 4 * d1l, mh, ml, -a2h, -a2l, -a0h))
            b2h, b2l, b1h, b1l = b1h, b1l, b0h, b0l
            d2h, d2l, d1h, d1l = d1h, d1l, d0h, d0l
            a2h, a2l, a1h, a1l = a1h, a1l, a0h, a0l
    coordinate = (coord_h, coord_l)
    value = _add(
        (coefficients[0], 0.0), _multiply(coordinate, (b1h, b1l)), (-b2h, -b2l)
    )
    first = (
        _add((b1h, b1l), _multiply(coordinate, (d1h, d1l)), (-d2h, -d2l))
        if derivatives >= 1
        else (0.0, 0.0)
    )
    second = (
        _add((2 * d1h, 2 * d1l), _multiply(coordinate, (a1h, a1l)), (-a2h, -a2l))
        if derivatives == 2
        else (0.0, 0.0)
    )
    result = ChebyshevKinematics(value, first, second)
    if not all(math.isfinite(part) for part_pair in result for part in part_pair):
        raise EphemerisSourceError("jpl_kinematics_invalid")
    return result


def _flatten_terms(values: Sequence[DoubleDouble]) -> tuple[float, ...]:
    n = len(values)
    if n == 3:
        a, b, c = values
        return (a[0], a[1], b[0], b[1], c[0], c[1])
    if n == 2:
        a, b = values
        return (a[0], a[1], b[0], b[1])
    return tuple(part for value in values for part in value)


def _scale_dd(value: DoubleDouble, scale: float, divisor: float) -> DoubleDouble:
    if (
        value == (0.0, 0.0)
        and math.isfinite(scale)
        and math.isfinite(divisor)
        and divisor != 0.0
    ):
        return (0.0, 0.0)
    return _divide(_multiply(value, (scale, 0.0)), divisor)


def _divide_dd(value: DoubleDouble, divisor: float) -> DoubleDouble:
    if value == (0.0, 0.0) and math.isfinite(divisor) and divisor != 0.0:
        return (0.0, 0.0)
    return _divide(value, divisor)


def _add_dd(a: DoubleDouble, b: DoubleDouble) -> DoubleDouble:
    if a == (0.0, 0.0):
        return b
    if b == (0.0, 0.0):
        return a
    return _add(a, b)
