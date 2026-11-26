"""Isolate solar altitude extrema in a closed UT1 interval."""

import math
from typing import Protocol


class SolarAltitudeAtUt1(Protocol):
    def __call__(self, julian_day_ut1: float, /) -> float: ...


def _solar_extremum(
    value: SolarAltitudeAtUt1, lower: float, upper: float, *, maximum: bool
) -> float:
    """Refine a bracketed solar-height extremum without clipping latitude."""
    ratio = (math.sqrt(5) - 1) / 2
    left = upper - ratio * (upper - lower)
    right = lower + ratio * (upper - lower)
    sign = -1 if maximum else 1
    left_value, right_value = sign * value(left), sign * value(right)
    for _ in range(96):
        if left == right or left == lower or right == upper:
            break
        if left_value < right_value:
            upper, right, right_value = right, left, left_value
            left = upper - ratio * (upper - lower)
            left_value = sign * value(left)
        else:
            lower, left, left_value = left, right, right_value
            right = lower + ratio * (upper - lower)
            right_value = sign * value(right)
    else:
        raise RuntimeError("Solar altitude extremum did not converge")
    return min((lower, left, right, upper), key=lambda point: sign * value(point))


def _chebyshev_value(coefficients: list[float], x: float) -> float:
    """Clenshaw evaluation, including close roots without a power-basis change."""
    first = second = 0.0
    for coefficient in reversed(coefficients[1:]):
        first, second = math.fsum((coefficient, 2 * x * first, -second)), first
    return math.fsum((coefficients[0], x * first, -second))


def _chebyshev_derivative(coefficients: list[float]) -> list[float]:
    degree = len(coefficients) - 1
    if degree == 0:
        return [0.0]
    derivative = [0.0] * degree
    for index in range(degree - 1, -1, -1):
        derivative[index] = 2 * (index + 1) * coefficients[index + 1]
        if index + 2 < degree:
            derivative[index] += derivative[index + 2]
    derivative[0] /= 2
    return derivative


def _chebyshev_roots(coefficients: list[float]) -> list[float]:
    """Isolate real roots on [-1,1] by the derivative's monotone intervals.

    Rolle's theorem supplies the partitions recursively. The interpolant only
    proposes height extrema; physical observations decide every event bracket.
    """
    if len(coefficients) == 1:
        return []
    stationary = _chebyshev_roots(_chebyshev_derivative(coefficients))
    nodes = [-1.0, *stationary, 1.0]
    values = [_chebyshev_value(coefficients, point) for point in nodes]
    roots = [point for point, value in zip(nodes, values) if value == 0]
    for lower, upper, low_value, high_value in zip(
        nodes, nodes[1:], values, values[1:]
    ):
        if not (low_value < 0 < high_value or high_value < 0 < low_value):
            continue
        for _ in range(64):
            middle = lower + (upper - lower) / 2
            if middle == lower or middle == upper:
                break
            score = _chebyshev_value(coefficients, middle)
            if score == 0:
                lower = upper = middle
                break
            if (score < 0) == (low_value < 0):
                lower, low_value = middle, score
            else:
                upper = middle
        roots.append(lower + (upper - lower) / 2)
    return sorted(set(roots))


def solar_altitude_nodes(
    value: SolarAltitudeAtUt1, lower: float, upper: float
) -> list[float]:
    """Resolve the smooth vertical component, allowing clustered extrema.

    Chebyshev interpolation avoids assuming one extremum per sampling interval.
    Its high-order tail controls subdivision; the tolerance includes rounding
    the absolute UT1 date to binary64. This is a numerical resolution check,
    not an interval-arithmetic proof for arbitrarily small tangent arcs.
    """
    degree = 12
    pending = [(lower, upper, 0)]
    nodes: set[float] = set()
    while pending:
        lower, upper, depth = pending.pop()
        # Rounded Lobatto nodes can skip dates even when every representable
        # date fits in the existing sampling budget.
        words = [lower]
        for _ in range(degree):
            words.append(math.nextafter(words[-1], upper))
            if words[-1] == upper:
                break
        if words[-1] == upper:
            nodes.update(words)
            continue
        middle = lower + (upper - lower) / 2
        radius = (upper - lower) / 2

        def to_ut1(x: float) -> float:
            # Across a JD binade, the rounded midpoint can displace an
            # interior projection past its closed segment endpoint.
            return min(upper, max(lower, middle + radius * x))

        points = [
            (
                upper
                if index == 0
                else (
                    lower
                    if index == degree
                    else to_ut1(math.cos(index * math.pi / degree))
                )
            )
            for index in range(degree + 1)
        ]
        scores = [value(point) for point in points]
        coefficients = [
            math.fsum(
                (0.5 if index in (0, degree) else 1.0)
                * score
                * math.cos(index * order * math.pi / degree)
                for index, score in enumerate(scores)
            )
            * 2
            / degree
            * (0.5 if order in (0, degree) else 1.0)
            for order in range(degree + 1)
        ]
        uncertainty = 32 * math.ulp(1.0) + 32 * (max(scores) - min(scores)) * math.ulp(
            middle
        ) / (upper - lower)
        tail = math.fsum(abs(c) for c in coefficients[-4:])
        nodes.update(points)
        # |T_k(x)| <= 1 gives the interpolant's complete range. A band
        # separated from zero needs no extremum localization. In particular,
        # do not subdivide coordinate roundoff at a polar solstice tens of
        # degrees from the horizon. The tail is a numerical estimate, not a
        # certified enclosure of an arbitrary underlying ephemeris function.
        if abs(coefficients[0]) - math.fsum(abs(c) for c in coefficients[1:]) > (
            8 * tail + uncertainty
        ):
            continue
        if tail > uncertainty:
            if depth == 20 or middle in (lower, upper):
                raise RuntimeError("Solar altitude interpolation did not converge")
            pending.extend(((lower, middle, depth + 1), (middle, upper, depth + 1)))
            continue
        while len(coefficients) > 1 and abs(coefficients[-1]) <= uncertainty:
            coefficients.pop()
        derivative = _chebyshev_derivative(coefficients)
        extrema = [x for x in _chebyshev_roots(derivative) if -1 < x < 1]
        partitions = [-1.0, *extrema, 1.0]
        for index, estimate in enumerate(extrema, start=1):
            left = (partitions[index - 1] + estimate) / 2
            right = (estimate + partitions[index + 1]) / 2
            before = _chebyshev_value(derivative, left)
            after = _chebyshev_value(derivative, right)
            if before * after < 0:
                nodes.add(
                    _solar_extremum(
                        value,
                        to_ut1(left),
                        to_ut1(right),
                        maximum=before > 0,
                    )
                )
    return sorted(nodes)
