"""Continuous scalar-obliquity Lahiri frame and analytic TT derivatives.

The complete state transform is R @ (gamma*v) + Rprime @ x. Its frame term
uses TT regardless of the separately declared vector-velocity scale. Native
orbital/aberration speeds and physical TT/TDB conversion need their own
qualification. No isolated J2000 identity shortcut is used here.

The pole coefficients use Vondrak, Capitaine & Wallace (2011/2012), as in
ERFA2.0.1 ltp/ltpecl/ltpequ. The separate scalar obliquity and Lahiri anchor
follow the inspected Swiss2.10.03 convention; scalar and coupled-vector
ecliptics are distinct approximations, not interchangeable reference frames.
Sources: https://doi.org/10.1051/0004-6361/201117274
https://doi.org/10.1051/0004-6361/201117274e
https://github.com/liberfa/erfa/tree/v2.0.1/src
https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/swephlib.c
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Sequence, Tuple, TypedDict

from fatebridge.core.astro.nutation import nutation
from fatebridge.core.astro.reference_frames import (
    COEFFICIENT_SHA256,
    DATA,
    Matrix,
    Vector,
    add,
    dot,
    ecliptic_rotation,
    madd,
    mean_ecliptic_frame,
    mm,
    mv,
    pair,
    pmat76,
    precession,
    transpose,
)


class FrameState(TypedDict):
    epoch_jd_tt: float
    mean_frame: Matrix
    mean_frame_derivative_per_TT_day: Matrix
    frame: Matrix
    frame_derivative_per_TT_day: Matrix
    mean_omega: Matrix
    omega: Matrix
    origin_degrees: float
    origin_rate_degrees_per_TT_day: float
    model_id: str
    coefficient_sha256: str


class SphericalState(TypedDict):
    longitude_degrees: float | None
    latitude_degrees: float
    radius: float
    longitude_rate_degrees_per_day: float | None
    latitude_rate_degrees_per_day: float | None
    radial_rate_per_day: float


class ProjectedState(TypedDict):
    model_id: str
    coefficient_sha256: str
    epoch_jd_tt: float
    vector_rate_scale: float
    position: list[float]
    velocity_per_TT_day: list[float]
    frame_motion_per_TT_day: list[float]
    scaled_input_velocity_term_per_TT_day: list[float]
    spherical: SphericalState


class FixedReceptionState(TypedDict):
    position: list[float]
    velocity_per_native_argument_day: list[float]
    input_frame_held_fixed: bool
    native_input_precession_identity_shortcut: bool


METHOD_ID = "fatebridge_continuous_scalar_lahiri_frame_v1"
DEG = 180.0 / math.pi


@lru_cache(maxsize=1)
def anchor() -> Tuple[Matrix, float]:
    tt = float(DATA["anchor_tt"])
    matrix, _ = precession(tt)
    values, _ = pair(tt, "pepol", "peper")
    rotation, _ = ecliptic_rotation(values[1])
    correction = mv(mm(mm(rotation, pmat76(tt)), transpose(matrix)), (1.0, 0.0, 0.0))
    initial = math.fsum(float(x) for x in DATA["anchor_origin_degrees_terms"]) / DEG
    return mm(rotation, matrix), initial - math.atan2(correction[1], correction[0])


def _mean_origin(matrix: Matrix, matrix_d: Matrix) -> Tuple[float, float]:
    anchor_matrix, constant = anchor()
    # P.T @ e1 is the first row of P. Anchor terms are fixed in TT.
    basis = mv(anchor_matrix, matrix[0])
    basis_d = mv(anchor_matrix, matrix_d[0])
    x, y = basis[:2]
    xd, yd = basis_d[:2]
    origin = constant - math.atan2(y, x)
    origin_d = -(x * yd - y * xd) / (x * x + y * y)
    return origin, origin_d


def apparent_lahiri_origin(tt: float) -> Tuple[float, float]:
    """Complete apparent offset and analytic rate, in degrees and degrees/TT day.

    Reuse the continuous mean origin, then add the complete 77-term nutation.
    Unlike the qualified auxiliary frame's input domain, evaluation also
    accepts the adjacent TT years required by civil-date and rate stencils.
    This is the declared parameter model, not physical clock certification.
    """
    origin, origin_d = _mean_origin(*precession(tt))
    dpsi, _, dpsi_d, _ = nutation(tt)
    return (origin * DEG + dpsi) % 360.0, origin_d * DEG + dpsi_d


def frame_state(tt: float) -> FrameState:
    if (
        isinstance(tt, bool)
        or not math.isfinite(tt)
        or not 1721425.5 <= tt <= 5373485.5
    ):
        raise ValueError("TT epoch outside the declared continuous-frame domain")
    matrix, matrix_d = precession(tt)
    mean, mean_d = mean_ecliptic_frame(tt)
    origin, origin_d = _mean_origin(matrix, matrix_d)
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


def _vector(values: Sequence[float]) -> Vector:
    if len(values) != 3 or any(isinstance(v, bool) for v in values):
        raise ValueError("A finite Cartesian three-vector is required")
    result = tuple(float(v) for v in values)
    if not all(math.isfinite(v) for v in result):
        raise ValueError("A finite Cartesian three-vector is required")
    return result


def spherical_state(
    position: Sequence[float], velocity: Sequence[float]
) -> SphericalState:
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
) -> ProjectedState:
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
) -> FixedReceptionState:
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
