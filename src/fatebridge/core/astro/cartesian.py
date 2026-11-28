"""Cartesian source states, fixed vector/matrix ops, and shared algebraic primitives."""

from __future__ import annotations

import math
from typing import NamedTuple, Protocol, Sequence, TypeVar

from fatebridge.utils.errors import EphemerisSourceError

Vector3 = tuple[float, float, float]
Vector = tuple[float, ...]
Matrix = tuple[Vector, ...]
_Self = TypeVar("_Self")


class _AlgebraicScalar(Protocol):
    def __add__(self: _Self, other: _Self, /) -> _Self: ...

    def __sub__(self: _Self, other: _Self, /) -> _Self: ...

    def __mul__(self: _Self, other: _Self, /) -> _Self: ...


_S = TypeVar("_S", bound=_AlgebraicScalar)


class CartesianState(NamedTuple):
    position: Vector3
    velocity: Vector3


class CartesianMotion(NamedTuple):
    """A position and its local directional rate, absent at a genuine corner."""

    position: Vector3
    velocity: Vector3 | None


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    return math.fsum(x * y for x, y in zip(a, b))


def add(a: Sequence[float], b: Sequence[float]) -> Vector:
    return tuple(x + y for x, y in zip(a, b))


def sub(a: Sequence[float], b: Sequence[float]) -> Vector:
    return tuple(x - y for x, y in zip(a, b))


def scale(a: Sequence[float], value: float) -> Vector:
    return tuple(x * value for x in a)


def cross(a: Sequence[float], b: Sequence[float]) -> Vector3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def norm(a: Sequence[float]) -> float:
    return math.hypot(*a)


def unit(a: Sequence[float]) -> Vector:
    size = norm(a)
    if not math.isfinite(size) or size <= 0:
        raise EphemerisSourceError("coordinate_values_unavailable")
    return tuple(x / size for x in a)


def transpose(a: Sequence[Sequence[float]]) -> Matrix:
    return tuple(zip(*a))


def mv(a: Sequence[Sequence[float]], v: Sequence[float]) -> Vector:
    return tuple(dot(row, v) for row in a)


def mm(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> Matrix:
    columns = transpose(b)
    return tuple(tuple(dot(row, column) for column in columns) for row in a)


def madd(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> Matrix:
    return tuple(add(x, y) for x, y in zip(a, b))


def rotate_vector(vector: Vector3, matrix: Sequence[Sequence[float]]) -> Vector3:
    x, y, z = mv(matrix, vector)
    return x, y, z


def vec_dot(a: Sequence[_S], b: Sequence[_S], zero: _S) -> _S:
    total = zero
    for x, y in zip(a, b):
        total = total + x * y
    return total


def vec_add(a: Sequence[_S], b: Sequence[_S]) -> list[_S]:
    return [x + y for x, y in zip(a, b)]


def vec_sub(a: Sequence[_S], b: Sequence[_S]) -> list[_S]:
    return [x - y for x, y in zip(a, b)]


def vec_scale(a: Sequence[_S], value: _S) -> list[_S]:
    return [x * value for x in a]


def vec_cross(a: Sequence[_S], b: Sequence[_S]) -> list[_S]:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
