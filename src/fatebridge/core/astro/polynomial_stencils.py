"""Exact polynomial linear-functional weights for the actual sample geometry."""

from __future__ import annotations

from fractions import Fraction
from functools import lru_cache
from typing import Tuple


@lru_cache(maxsize=128)
def polynomial_weights(
    nodes: Tuple[Fraction, ...], moments: Tuple[Fraction, ...]
) -> Tuple[Fraction, ...]:
    """Apply a linear functional to the least-squares polynomial on these nodes.

    moments[i] is the desired value of that functional on x**i. The normal
    equations are solved over exact rationals; neither measured values nor
    expected rates enter their construction. Callers supply distinct nodes
    spanning the requested polynomial degree.
    """
    powers = range(len(moments))
    matrix = [
        [sum((x ** (i + j) for x in nodes), Fraction(0)) for j in powers] + [moments[i]]
        for i in powers
    ]
    for column in powers:
        pivot = matrix[column][column]
        matrix[column] = [value / pivot for value in matrix[column]]
        for row in powers:
            if row != column:
                factor = matrix[row][column]
                matrix[row] = [
                    a - factor * b for a, b in zip(matrix[row], matrix[column])
                ]
    coefficients = [row[-1] for row in matrix]
    return tuple(
        sum((c * x**i for i, c in enumerate(coefficients)), Fraction(0)) for x in nodes
    )
