"""Cartesian source states and fixed vector rotations, independent of theory."""

from __future__ import annotations

import math
from typing import NamedTuple, Sequence

Vector3 = tuple[float, float, float]


class CartesianState(NamedTuple):
    position: Vector3
    velocity: Vector3


class CartesianMotion(NamedTuple):
    """A position and its local directional rate, absent at a genuine corner."""

    position: Vector3
    velocity: Vector3 | None


def rotate_vector(vector: Vector3, matrix: Sequence[Sequence[float]]) -> Vector3:
    x, y, z = (math.fsum(a * b for a, b in zip(row, vector)) for row in matrix)
    return x, y, z
