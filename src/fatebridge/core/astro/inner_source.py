"""Analytic continuous DE441 Mercury/Venus source reduction.

The inspected two linearized light-time delays, finite-Sun profile and
aberration are differentiated as one formula. Raw source clocks, physical
observational error and the derivative of native binary rounding are separate.
"""

from __future__ import annotations

import math
from decimal import Decimal as N
from decimal import localcontext
from fractions import Fraction
from typing import Any, Dict, List, Sequence, Tuple

from fatebridge.core.astro.jpl_records import SourceRecords
from fatebridge.core.astro.solar_decimal import (
    PROFILE_SHA256,
    mass_profile,
    stable_interpolation_cell,
)

METHOD_ID = "continuous_de441_inner_apparent_source_jvp_v1"
PRECISION = 70


class SourceDerivativeUnavailable(ValueError):
    pass


def number(value: Any) -> N:
    return N.from_float(value) if isinstance(value, float) else N(value)


class Dual:
    def __init__(self, value: Any, derivative: Any = 0) -> None:
        self.v, self.d = number(value), number(derivative)
        if not self.v.is_finite() or not self.d.is_finite():
            raise SourceDerivativeUnavailable("nonfinite_source_scalar")

    @staticmethod
    def cast(value: Any) -> Dual:
        return value if isinstance(value, Dual) else Dual(value)

    def __add__(self, other: Any) -> Dual:
        other = self.cast(other)
        return Dual(self.v + other.v, self.d + other.d)

    __radd__ = __add__

    def __neg__(self) -> Dual:
        return Dual(-self.v, -self.d)

    def __sub__(self, other: Any) -> Dual:
        return self + -self.cast(other)

    def __rsub__(self, other: Any) -> Dual:
        return self.cast(other) + -self

    def __mul__(self, other: Any) -> Dual:
        other = self.cast(other)
        return Dual(self.v * other.v, self.d * other.v + self.v * other.d)

    __rmul__ = __mul__

    def __truediv__(self, other: Any) -> Dual:
        other = self.cast(other)
        if not other.v:
            raise SourceDerivativeUnavailable("zero_source_denominator")
        return Dual(
            self.v / other.v,
            (self.d * other.v - self.v * other.d) / (other.v * other.v),
        )

    def __rtruediv__(self, other: Any) -> Dual:
        return self.cast(other) / self

    def sqrt(self) -> Dual:
        if self.v <= 0:
            raise SourceDerivativeUnavailable("singular_source_norm")
        root = self.v.sqrt()
        return Dual(root, self.d / (2 * root))


Vector = Sequence[Dual]


def dot(a: Vector, b: Vector) -> Dual:
    return sum((x * y for x, y in zip(a, b)), Dual(0))


def add(a: Vector, b: Vector) -> List[Dual]:
    return [x + y for x, y in zip(a, b)]


def sub(a: Vector, b: Vector) -> List[Dual]:
    return [x - y for x, y in zip(a, b)]


def scale(a: Vector, c: Any) -> List[Dual]:
    return [x * c for x in a]


def norm(a: Vector) -> Dual:
    squared = dot(a, a)
    return Dual(0) if squared.v == 0 and all(x.d == 0 for x in a) else squared.sqrt()


def unit(a: Vector) -> List[Dual]:
    return scale(a, 1 / norm(a))


def cross(a: Vector, b: Vector) -> List[Dual]:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def chebyshev(coefficients: Sequence[float], x: Dual) -> Tuple[Dual, Dual]:
    b1 = b2 = g1 = g2 = Dual(0)
    for coefficient in reversed(coefficients[1:]):
        b = coefficient + 2 * x * b1 - b2
        g = 2 * b1 + 2 * x * g1 - g2
        b2, b1, g2, g1 = b1, b, g1, g
    return coefficients[0] + x * b1 - b2, b1 + x * g1 - g2


def group(reader: SourceRecords, epoch: Dual, index: int) -> List[Dual]:
    values = reader.record(Fraction(epoch.v))
    offset, count, parts = reader.pointer(index)
    start, end = N.from_float(values[0]), N.from_float(values[1])
    width = (end - start) / parts
    part = min(int((epoch.v - start) // width), parts - 1)
    if not 0 <= part < parts:
        raise SourceDerivativeUnavailable("source_subcell_unavailable")
    reader.cells.add((index, values[0], part, count))
    if epoch.v == start + part * width or epoch.v == end:
        raise SourceDerivativeUnavailable("source_polynomial_boundary_unqualified")
    x = 2 * (epoch - start - part * width) / width - 1
    positions = []
    velocities = []
    for axis in range(3):
        first = offset - 1 + (3 * part + axis) * count
        p, v = chebyshev(values[first : first + count], x)
        positions.append(p / reader.au)
        velocities.append(v * 2 / width / reader.au)
    return positions + velocities


def state(reader: SourceRecords, epoch: Dual, body: str) -> List[Dual]:
    if body == "Earth":
        emb, moon = group(reader, epoch, 2), group(reader, epoch, 9)
        return sub(emb, scale(moon, 1 / (Dual(reader.emrat) + 1)))
    return group(reader, epoch, {"Mercury": 0, "Venus": 1, "Sun": 10}[body])


def apparent_source(reader: SourceRecords, body: str, epoch: float) -> Dict[str, Any]:
    if body not in {"Mercury", "Venus"}:
        raise SourceDerivativeUnavailable("unsupported_source_body")
    with localcontext() as context:
        context.prec = PRECISION
        t = Dual(epoch, 1)
        planet, earth, sun = [state(reader, t, b) for b in (body, "Earth", "Sun")]
        au, light, day = Dual(149597870700), Dual(299792458), Dual(86400)
        rough = planet[:3]
        history = []
        delay = Dual(0)
        for _ in range(2):
            delay = norm(sub(rough, earth[:3])) * au / light / day
            rough = sub(planet[:3], scale(planet[3:], delay))
            history.append({"days": str(delay.v), "derivative": str(delay.d)})
        emitted = state(reader, t - delay, body)
        ray = sub(emitted[:3], earth[:3])
        radius = norm(ray)
        u = unit(ray)
        eh = sub(earth[:3], sun[:3])
        re = norm(eh)
        e = unit(eh)
        q = unit(sub(emitted[:3], sub(sun[:3], scale(sun[3:], delay))))
        angular_radius = Dual((959.63 / 3600) * (math.pi / 180)) / re
        impact = norm(cross(u, e)) / angular_radius
        branch = stable_interpolation_cell(impact.v, angular_radius.v, (re / radius).v)
        if impact.v <= 0 or branch["cell"] is None:
            raise SourceDerivativeUnavailable("solar_axis_or_mass_knot_unqualified")
        if impact.v >= 1:
            mass = Dual(1)
        else:
            profile = [(number(float(r)), number(float(m))) for r, m in mass_profile()]
            for (r0, m0), (r1, m1) in zip(profile, profile[1:]):
                if r1 < impact.v < r0:
                    mass = m0 + (impact - r0) * (m1 - m0) / (r1 - r0)
                    break
            else:
                raise SourceDerivativeUnavailable("solar_mass_cell_unqualified")
        strength = 2 * Dual(1.32712440017987e20) * mass / light / light / au / re
        denominator = dot(add(q, e), add(q, e)) / 2
        deflected = scale(
            add(u, scale(cross(u, cross(e, q)), strength / denominator)), radius
        )
        beta = scale(earth[3:], au / light / day)
        r = norm(deflected)
        inverse_gamma = (1 - dot(beta, beta)).sqrt()
        f = dot(deflected, beta) / r
        apparent = unit(
            scale(
                add(
                    scale(deflected, inverse_gamma),
                    scale(beta, (1 + f / (1 + inverse_gamma)) * r),
                ),
                1 / (1 + f),
            )
        )
        return {
            "method_id": METHOD_ID,
            "direction_icrf": [str(v.v) for v in apparent],
            "derivative_per_native_argument_day": [str(v.d) for v in apparent],
            "earth_state": [str(v.v) for v in earth],
            "earth_acceleration": [str(v.d) for v in earth[3:]],
            "light_time_history": history,
            "retarded_argument": str((t - delay).v),
            "solar_interpolation_branch": branch,
            "solar_mass_profile_sha256": PROFILE_SHA256,
            "source_records": reader.evidence(),
            "precision": PRECISION,
            "unrounded_retarded_argument": True,
            "light_time_model": "legacy_two_linearized_delays",
            "physical_TT_TDB_conversion_applied": False,
            "native_binary_function_derivative_certified": False,
            "observational_accuracy_certified": False,
        }
