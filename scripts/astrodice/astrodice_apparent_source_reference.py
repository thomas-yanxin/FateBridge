"""Differentiate a declared continuous native-source apparent-position model.

Maintenance reference only: original DE441 coefficients, two light-time
iterations, the pinned extended-Sun table and relativistic stellar aberration.
No FateBridge or Swiss import. This is a shared source-model/TDB study, not an
independent observation or a physical TT/TDB conversion.
"""

import math
import struct
from decimal import Decimal as N
from decimal import localcontext
from fractions import Fraction

from scripts.astrodice.astrodice_de441_records import header


def number(value):
    if isinstance(value, float):
        return N.from_float(value)
    if isinstance(value, Fraction):
        return N(value.numerator) / N(value.denominator)
    return N(value)


class D:
    """First-order forward derivative with respect to reception TDB days."""

    __slots__ = ("v", "d")

    def __init__(self, value, derivative=0):
        self.v, self.d = number(value), number(derivative)
        if not self.v.is_finite() or not self.d.is_finite():
            raise ValueError("Nonfinite source-model scalar")

    @staticmethod
    def cast(value):
        return value if isinstance(value, D) else D(value)

    def __add__(self, other):
        other = D.cast(other)
        return D(self.v + other.v, self.d + other.d)

    __radd__ = __add__

    def __neg__(self):
        return D(-self.v, -self.d)

    def __sub__(self, other):
        return self + -D.cast(other)

    def __rsub__(self, other):
        return D.cast(other) - self

    def __mul__(self, other):
        other = D.cast(other)
        return D(self.v * other.v, self.d * other.v + self.v * other.d)

    __rmul__ = __mul__

    def __truediv__(self, other):
        other = D.cast(other)
        if not other.v:
            raise ValueError("Zero source-model denominator")
        return D(self.v / other.v, (self.d * other.v - self.v * other.d) / other.v**2)

    def __rtruediv__(self, other):
        return D.cast(other) / self

    def sqrt(self):
        if self.v <= 0:
            raise ValueError("Source-model square root outside differentiable domain")
        root = self.v.sqrt()
        return D(root, self.d / (2 * root))


def dot(a, b):
    return sum((x * y for x, y in zip(a, b)), D(0))


def add(a, b):
    return [x + y for x, y in zip(a, b)]


def sub(a, b):
    return [x - y for x, y in zip(a, b)]


def scale(a, b):
    return [x * b for x in a]


def cross(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def norm(a):
    square = dot(a, a)
    if square.v == 0 and all(x.d == 0 for x in a):
        return D(0)
    return square.sqrt()


def unit(a):
    return scale(a, 1 / norm(a))


def clenshaw(coefficients, x):
    b1 = b2 = g1 = g2 = D(0)
    for coefficient in reversed(coefficients[1:]):
        b = coefficient + 2 * x * b1 - b2
        g = 2 * b1 + 2 * x * g1 - g2
        b2, b1, g2, g1 = b1, b, g1, g
    return coefficients[0] + x * b1 - b2, b1 + x * g1 - g2


class Reader:
    def __init__(self, fixture, window_index):
        self.metadata = header((fixture / "header.bin").read_bytes())
        raw = (fixture / f"record-responses/case-{window_index:02}.bin").read_bytes()
        if len(raw) != 3 * 8144:
            raise ValueError("Incomplete frozen original record window")
        self.records = [
            struct.unpack("<1018d", raw[i : i + 8144]) for i in range(0, len(raw), 8144)
        ]
        self.cells = set()

    def group(self, epoch, group):
        record = next(
            (v for v in self.records if number(v[0]) <= epoch.v < number(v[1])), None
        )
        if record is None:
            raise ValueError("Reference epoch outside frozen original records")
        offset, count, parts = self.metadata["pointers"][group]
        width = (number(record[1]) - number(record[0])) / parts
        part = int((epoch.v - number(record[0])) // width)
        self.cells.add((group, record[0], part))
        x = 2 * (epoch - number(record[0]) - part * width) / width - 1
        first = offset - 1 + part * count * 3
        position, velocity = [], []
        for axis in range(3):
            coefficients = [
                D(v) for v in record[first + axis * count : first + (axis + 1) * count]
            ]
            p, v = clenshaw(coefficients, x)
            position.append(p)
            velocity.append(v * 2 / width)
        return position + velocity

    def states(self, epoch, body):
        if body not in {"Mercury", "Venus"}:
            raise ValueError("Unplanned original source body")
        emb, moon = self.group(epoch, 2), self.group(epoch, 9)
        earth = sub(
            emb, scale(moon, 1 / (D(self.metadata["earth_moon_mass_ratio"]) + 1))
        )
        result = {
            "Earth": earth,
            "Sun": self.group(epoch, 10),
            body: self.group(epoch, 0 if body == "Mercury" else 1),
        }
        return {
            name: scale(state, 1 / D(self.metadata["au_km"]))
            for name, state in result.items()
        }

    def body_state(self, epoch, body):
        if body not in {"Mercury", "Venus"}:
            raise ValueError("Unplanned original source body")
        return scale(
            self.group(epoch, 0 if body == "Mercury" else 1),
            1 / D(self.metadata["au_km"]),
        )


def enclosed_mass(impact, profile, *, allow_knot_value=False):
    if impact.v <= 0:
        if allow_knot_value and impact.v == 0:
            return D(0), {"cell": "axis_value", "minimum_knot_distance": "0"}
        raise ValueError("Solar-axis derivative is unqualified")
    if impact.v >= 1:
        if impact.v - 1 < N("1e-30") and not allow_knot_value:
            raise ValueError("Solar interpolation boundary is unqualified")
        return D(1), {"cell": "outside", "minimum_knot_distance": str(impact.v - 1)}
    values = [(number(float(r)), number(float(m))) for r, m in profile]
    distance = min(abs(impact.v - r) for r, _ in values)
    if distance < N("1e-30"):
        if not allow_knot_value:
            raise ValueError("Solar interpolation knot derivative is unqualified")
        for r, mass in values:
            if impact.v == r:
                return D(mass), {"cell": "boundary_value", "minimum_knot_distance": "0"}
    for index, ((r0, m0), (r1, m1)) in enumerate(zip(values, values[1:])):
        if r1 < impact.v < r0:
            mass = m0 + (impact - r0) * ((m1 - m0) / (r1 - r0))
            return mass, {"cell": index, "minimum_knot_distance": str(distance)}
    raise ValueError("Unqualified finite-Sun profile cell")


def aberration(ray, beta):
    radius = norm(ray)
    lorentz = (1 - dot(beta, beta)).sqrt()
    projection = dot(ray, beta) / radius
    return scale(
        add(
            scale(ray, lorentz), scale(beta, (1 + projection / (1 + lorentz)) * radius)
        ),
        1 / (1 + projection),
    )


def sample(reader, body, epoch, profile, *, precision=70, seed=1):
    if body not in {"Mercury", "Venus"}:
        raise ValueError("Unplanned source-reference body")
    with localcontext() as context:
        context.prec = precision
        reader.cells = set()
        t = D(epoch, seed)
        now = reader.states(t, body)
        planet, earth, sun = now[body], now["Earth"], now["Sun"]
        au, light, day = D(149597870700), D(299792458), D(86400)
        delay = D(0)
        rough = planet[:3]
        history = []
        for _ in range(2):
            delay = norm(sub(rough, earth[:3])) * au / light / day
            rough = sub(planet[:3], scale(planet[3:], delay))
            history.append({"days": str(delay.v), "derivative": str(delay.d)})
        retarded = reader.body_state(t - delay, body)
        ray = sub(retarded[:3], earth[:3])
        radius = norm(ray)
        u = unit(ray)
        eh = sub(earth[:3], sun[:3])
        re, e = norm(eh), unit(eh)
        q = unit(sub(retarded[:3], sub(sun[:3], scale(sun[3:], delay))))
        source_radius = D((959.63 / 3600) * (math.pi / 180))
        impact = norm(cross(u, e)) * re / source_radius
        mass, cell = enclosed_mass(impact, profile, allow_knot_value=seed == 0)
        strength = 2 * D(1.32712440017987e20) * mass / light / light / au / re
        denominator = dot(add(q, e), add(q, e)) / 2
        if denominator.v <= 0:
            raise ValueError("Solar deflection geometry is singular")
        deflected = scale(
            add(u, scale(cross(u, cross(e, q)), strength / denominator)), radius
        )
        beta = scale(earth[3:], au / light / day)
        apparent = unit(aberration(deflected, beta))
        return {
            "direction_icrf": [str(x.v) for x in apparent],
            "derivative_per_day": [str(x.d) for x in apparent],
            "light_time_history": history,
            "retarded_epoch": str((t - delay).v),
            "solar_impact_fraction": str(impact.v),
            "solar_impact_derivative_per_day": str(impact.d),
            "solar_mass_fraction": str(mass.v),
            "solar_mass_derivative_per_day": str(mass.d),
            "solar_profile_cell": cell,
            "precision": precision,
            "original_polynomial_cells": sorted(reader.cells),
            "continuous_unrounded_source_epoch_model": True,
            "light_time_model": "legacy_two_linearized_delays",
            "light_time_convergence_certified": False,
            "Horizons_emission_epoch_mapping_certified": False,
            "exact_TT_conversion": False,
        }
