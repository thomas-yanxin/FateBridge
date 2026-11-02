"""Continuous scalar-obliquity Lahiri frame and analytic TT derivatives.

The complete state transform is R @ (gamma*v) + Rprime @ x. Its frame term
uses TT regardless of the separately declared vector-velocity scale. Native
orbital/aberration speeds and physical TT/TDB conversion need their own
qualification. No isolated J2000 identity shortcut is used here.
"""

from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Sequence, Tuple

Vector = Tuple[float, ...]
Matrix = Tuple[Vector, ...]
METHOD_ID = "fatebridge_continuous_scalar_lahiri_frame_v1"
COEFFICIENT_SHA256 = "577c38bf4db44728523e126ac8a50b899fe761d666a1253c0c6e9788bbf68791"
_COEFFICIENT_BYTES = (
    Path(__file__).resolve().parents[2] / "data/astronomy/lahiri-frame-v1.json"
).read_bytes()
if hashlib.sha256(_COEFFICIENT_BYTES).hexdigest() != COEFFICIENT_SHA256:
    raise RuntimeError("Lahiri frame coefficients differ from the declared source")
DATA = json.loads(_COEFFICIENT_BYTES)
AS2R = math.pi / 648000.0
DEG = 180.0 / math.pi


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    return math.fsum(x * y for x, y in zip(a, b))


def cross(a: Sequence[float], b: Sequence[float]) -> Vector:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def add(a: Sequence[float], b: Sequence[float]) -> Vector:
    return tuple(x + y for x, y in zip(a, b))


def transpose(a: Sequence[Sequence[float]]) -> Matrix:
    return tuple(zip(*a))


def mv(a: Sequence[Sequence[float]], v: Sequence[float]) -> Vector:
    return tuple(dot(row, v) for row in a)


def mm(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> Matrix:
    columns = transpose(b)
    return tuple(tuple(dot(row, column) for column in columns) for row in a)


def madd(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> Matrix:
    return tuple(add(x, y) for x, y in zip(a, b))


def pair(tt: float, polynomial: str, periodic: str) -> Tuple[Vector, Vector]:
    century = (tt - 2451545.0) / 36525.0
    poly = DATA["native_tables"][polynomial]
    terms = DATA["native_tables"][periodic]
    values = []
    derivatives = []
    for axis in range(2):
        value_terms = [
            float(row[axis]) * century**power for power, row in enumerate(poly)
        ]
        derivative_terms = [
            power * float(row[axis]) * century ** (power - 1)
            for power, row in enumerate(poly)
            if power
        ]
        for period, cosine, sine in zip(terms[0], terms[1 + axis], terms[3 + axis]):
            frequency = 2.0 * math.pi / float(period)
            angle = frequency * century
            c, s = math.cos(angle), math.sin(angle)
            cv, sv = float(cosine), float(sine)
            value_terms.append(cv * c + sv * s)
            derivative_terms.append(frequency * (-cv * s + sv * c))
        values.append(math.fsum(value_terms) * AS2R)
        derivatives.append(math.fsum(derivative_terms) * AS2R / 36525.0)
    return tuple(values), tuple(derivatives)


def precession(tt: float) -> Tuple[Matrix, Matrix]:
    (p, q), (pd, qd) = pair(tt, "pqpol", "pqper")
    eps0 = 84381.406 * AS2R
    ce, se = math.cos(eps0), math.sin(eps0)
    z = math.sqrt(1.0 - p * p - q * q)
    zd = -(p * pd + q * qd) / z
    ecliptic = (p, -q * ce - z * se, -q * se + z * ce)
    ecliptic_d = (pd, -qd * ce - zd * se, -qd * se + zd * ce)
    (x, y), (xd, yd) = pair(tt, "xypol", "xyper")
    z = math.sqrt(1.0 - x * x - y * y)
    zd = -(x * xd + y * yd) / z
    equator = (x, y, z)
    equator_d = (xd, yd, zd)
    raw = cross(equator, ecliptic)
    raw_d = add(cross(equator_d, ecliptic), cross(equator, ecliptic_d))
    radius = math.sqrt(dot(raw, raw))
    equinox = tuple(v / radius for v in raw)
    radial = dot(equinox, raw_d)
    equinox_d = tuple((d - v * radial) / radius for d, v in zip(raw_d, equinox))
    middle = cross(equator, equinox)
    middle_d = add(cross(equator_d, equinox), cross(equator, equinox_d))
    return (equinox, middle, equator), (equinox_d, middle_d, equator_d)


def ecliptic_rotation(epsilon: float, epsilon_d: float = 0.0) -> Tuple[Matrix, Matrix]:
    c, s = math.cos(epsilon), math.sin(epsilon)
    return (
        ((1.0, 0.0, 0.0), (0.0, c, s), (0.0, -s, c)),
        (
            (0.0, 0.0, 0.0),
            (0.0, -s * epsilon_d, c * epsilon_d),
            (0.0, -c * epsilon_d, -s * epsilon_d),
        ),
    )


def pmat76(tt: float) -> Matrix:
    century = (tt - 2451545.0) / 36525.0
    angles = {
        name: math.fsum(float(c) * century**i for i, c in enumerate(terms)) * AS2R
        for name, terms in DATA["IAU1976_angles_arcsec_coefficients"].items()
    }
    Z, z, theta = angles["zeta"], angles["z"], angles["theta"]
    cZ, sZ, cz, sz, cT, sT = (
        math.cos(Z),
        math.sin(Z),
        math.cos(z),
        math.sin(z),
        math.cos(theta),
        math.sin(theta),
    )
    return (
        (cZ * cT * cz - sZ * sz, -sZ * cT * cz - cZ * sz, -sT * cz),
        (cZ * cT * sz + sZ * cz, -sZ * cT * sz + cZ * cz, -sT * sz),
        (cZ * sT, -sZ * sT, cT),
    )


@lru_cache(maxsize=1)
def anchor() -> Tuple[Matrix, float]:
    tt = float(DATA["anchor_tt"])
    matrix, _ = precession(tt)
    values, _ = pair(tt, "pepol", "peper")
    rotation, _ = ecliptic_rotation(values[1])
    correction = mv(mm(mm(rotation, pmat76(tt)), transpose(matrix)), (1.0, 0.0, 0.0))
    initial = math.fsum(float(x) for x in DATA["anchor_origin_degrees_terms"]) / DEG
    return mm(rotation, matrix), initial - math.atan2(correction[1], correction[0])


def frame_state(tt: float) -> Dict[str, Any]:
    if (
        isinstance(tt, bool)
        or not math.isfinite(tt)
        or not 1721425.5 <= tt <= 5373485.5
    ):
        raise ValueError("TT epoch outside the declared continuous-frame domain")
    matrix, matrix_d = precession(tt)
    values, derivatives = pair(tt, "pepol", "peper")
    rotation, rotation_d = ecliptic_rotation(values[1], derivatives[1])
    mean = mm(rotation, matrix)
    mean_d = madd(mm(rotation_d, matrix), mm(rotation, matrix_d))
    anchor_matrix, constant = anchor()
    # P.T @ e1 is the first row of P. Anchor terms are fixed in TT.
    basis = mv(anchor_matrix, matrix[0])
    basis_d = mv(anchor_matrix, matrix_d[0])
    x, y = basis[:2]
    xd, yd = basis_d[:2]
    origin = constant - math.atan2(y, x)
    origin_d = -(x * yd - y * xd) / (x * x + y * y)
    c, s = math.cos(origin), math.sin(origin)
    sidereal = ((c, s, 0.0), (-s, c, 0.0), (0.0, 0.0, 1.0))
    sidereal_d = (
        (-s * origin_d, c * origin_d, 0.0),
        (-c * origin_d, -s * origin_d, 0.0),
        (0.0, 0.0, 0.0),
    )
    frame = mm(sidereal, mean)
    frame_d = madd(mm(sidereal_d, mean), mm(sidereal, mean_d))
    return {
        "epoch_jd_tt": tt,
        "mean_frame": mean,
        "mean_frame_derivative_per_TT_day": mean_d,
        "frame": frame,
        "frame_derivative_per_TT_day": frame_d,
        "mean_omega": mm(mean_d, transpose(mean)),
        "omega": mm(frame_d, transpose(frame)),
        "origin_degrees": origin * DEG,
        "origin_rate_degrees_per_TT_day": origin_d * DEG,
        "model_id": METHOD_ID,
        "coefficient_sha256": COEFFICIENT_SHA256,
    }


def longitude_frame_rate(omega: Matrix, longitude: float, latitude: float) -> float:
    if (
        not math.isfinite(longitude)
        or not math.isfinite(latitude)
        or not -90.0 < latitude < 90.0
    ):
        raise ValueError("Finite direction away from a longitude singularity required")
    longitude = math.radians(math.remainder(longitude, 360.0))
    latitude = math.radians(latitude)
    c = math.cos(latitude)
    q = (c * math.cos(longitude), c * math.sin(longitude), math.sin(latitude))
    v = mv(omega, q)
    return (q[0] * v[1] - q[1] * v[0]) / (q[0] * q[0] + q[1] * q[1]) * DEG


def _vector(values: Sequence[float]) -> Vector:
    if len(values) != 3 or any(isinstance(v, bool) for v in values):
        raise ValueError("A finite Cartesian three-vector is required")
    result = tuple(float(v) for v in values)
    if not all(math.isfinite(v) for v in result):
        raise ValueError("A finite Cartesian three-vector is required")
    return result


def spherical_state(
    position: Sequence[float], velocity: Sequence[float]
) -> Dict[str, Any]:
    """Spherical position and derivative in the supplied distance/day units.

    Longitude is undefined at a pole. Latitude has no two-sided derivative
    there for a generic transverse velocity, so neither rate is fabricated.
    """
    p, v = _vector(position), _vector(velocity)
    rho = math.hypot(p[0], p[1])
    radius = math.hypot(*p)
    if radius == 0:
        raise ValueError("The zero vector has no spherical direction")
    radial = dot(p, v) / radius
    if rho == 0:
        return {
            "longitude_degrees": None,
            "latitude_degrees": math.copysign(90.0, p[2]),
            "radius": radius,
            "longitude_rate_degrees_per_day": None,
            "latitude_rate_degrees_per_day": None,
            "radial_rate_per_day": radial,
        }
    rho_d = (p[0] * v[0] + p[1] * v[1]) / rho
    return {
        "longitude_degrees": math.degrees(math.atan2(p[1], p[0])) % 360.0,
        "latitude_degrees": math.degrees(math.atan2(p[2], rho)),
        "radius": radius,
        "longitude_rate_degrees_per_day": math.degrees(
            (p[0] * v[1] - p[1] * v[0]) / rho**2
        ),
        "latitude_rate_degrees_per_day": math.degrees(
            (rho * v[2] - p[2] * rho_d) / radius**2
        ),
        "radial_rate_per_day": radial,
    }


def project_state(
    julian_day_tt: float,
    position: Sequence[float],
    velocity: Sequence[float],
    *,
    vector_rate_scale: float,
) -> Dict[str, Any]:
    """Reframe a state with an explicitly supplied input-velocity scale.

    The caller owns the meaning and provenance of the input velocity and
    scale. This function supplies the continuous TT frame derivative only.
    """
    if (
        isinstance(vector_rate_scale, bool)
        or not math.isfinite(vector_rate_scale)
        or vector_rate_scale <= 0
    ):
        raise ValueError("A finite positive input-velocity scale is required")
    p, v = _vector(position), _vector(velocity)
    frame = frame_state(julian_day_tt)
    matrix, derivative = frame["frame"], frame["frame_derivative_per_TT_day"]
    q = mv(matrix, p)
    vector_term = mv(matrix, tuple(vector_rate_scale * x for x in v))
    frame_term = mv(derivative, p)
    dq = add(vector_term, frame_term)
    return {
        "model_id": METHOD_ID,
        "coefficient_sha256": COEFFICIENT_SHA256,
        "epoch_jd_tt": julian_day_tt,
        "vector_rate_scale": vector_rate_scale,
        "position": list(q),
        "velocity_per_TT_day": list(dq),
        "frame_motion_per_TT_day": list(frame_term),
        "scaled_input_velocity_term_per_TT_day": list(vector_term),
        "spherical": spherical_state(q, dq),
    }


def decode_native_fixed_reception_state(
    julian_day_tt: float, position: Sequence[float], velocity: Sequence[float]
) -> Dict[str, Any]:
    """Decode a held native reception basis; do not differentiate its epoch.

    The inspected swi_trop_ra2sid_lon skips precession at exactly J2000.
    Reconstruct that input representation only. The output frame and its
    derivative in project_state remain continuous, including at J2000.
    """
    p, v = _vector(position), _vector(velocity)
    basis = frame_state(julian_day_tt)["mean_frame"]
    if julian_day_tt == 2451545.0:
        epsilon = pair(julian_day_tt, "pepol", "peper")[0][1]
        basis = ecliptic_rotation(epsilon)[0]
    inverse = transpose(basis)
    return {
        "position": list(mv(inverse, p)),
        "velocity_per_native_argument_day": list(mv(inverse, v)),
        "input_frame_held_fixed": True,
        "native_input_precession_identity_shortcut": julian_day_tt == 2451545.0,
    }
