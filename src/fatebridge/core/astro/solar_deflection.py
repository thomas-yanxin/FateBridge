"""Finite-source solar bending under an explicitly transparent-Sun convention.

The mass profile, nominal angular radius and GM are the pinned Swiss2.10.03
source values. ERFA2.0.1 eraLd supplies the stable finite-source vector form.
Its positive 1e-11 denominator limiter extends the formal centre convention;
this is not identical to native 0/0 at the centre or to an opaque-Sun model.
Inside-disk coordinates do not describe observable transmitted sunlight.
"""

from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from importlib.resources import files
from typing import Sequence, TypedDict

from fatebridge.core.astro.aberration_math import dot
from fatebridge.core.astro.cartesian import CartesianMotion, CartesianState, Vector3

SOURCE_URL = "https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/sweph.c"
FORMULA_URL = "https://github.com/liberfa/erfa/blob/v2.0.1/src/ld.c"
PROFILE_SHA256 = "8f3f8e90fc756df0e3ba0b4ade05cfc98ecf49d4476c1f868c80c9cc9f3790ab"
DEFLECTION_LIMITER = 1e-11
MODEL_ID = (
    "finite_source_swiss_transparent_solar_profile_stable_unit_sum_erfa_limiter_v2"
)


class Parameters(TypedDict):
    solar_radius_at_one_au_arcsec: float
    solar_GM_m3_s2: float
    mass_profile_radius_fraction_and_effective_mass: list[list[float]]


@lru_cache(maxsize=1)
def _parameters() -> Parameters:
    raw = (
        files("fatebridge")
        .joinpath("data/astronomy/swiss-solar-deflection-2.10.json")
        .read_bytes()
    )
    if hashlib.sha256(raw).hexdigest() != PROFILE_SHA256:
        raise RuntimeError(
            "Solar deflection parameters differ from the declared source"
        )
    data: Parameters = json.loads(raw)
    return data


def effective_solar_mass(radius_fraction: float) -> tuple[float, float | None]:
    """Mass and local slope; unequal adjacent slopes have no unique derivative."""
    if radius_fraction <= 0:
        return 0.0, None if radius_fraction == 0 else 0.0
    if radius_fraction >= 1:
        return 1.0, None if radius_fraction == 1 else 0.0
    profile = _parameters()["mass_profile_radius_fraction_and_effective_mass"]
    index = 1
    while profile[index][0] > radius_fraction:
        index += 1
    r0, m0 = profile[index - 1]
    r1, m1 = profile[index]
    slope: float | None = (m1 - m0) / (r1 - r0)
    if radius_fraction == r1:
        r2, m2 = profile[index + 1]
        if slope != (m2 - m1) / (r2 - r1):
            slope = None
    return m0 + (radius_fraction - r0) / (r1 - r0) * (m1 - m0), slope


def _cross(a: Sequence[float], b: Sequence[float]) -> Vector3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def finite_source_solar_deflection(
    ray: CartesianState,
    observer: CartesianState,
    sun_at_reception: CartesianState,
    target_at_emission: CartesianState,
    sun_at_emission: CartesianState,
) -> CartesianMotion:
    """Bend a ray and differentiate every supplied geometric input in TT.

    The deflector is at reception for observer geometry, at emission for the
    target geometry, following the declared native Swiss convention. This is
    not ERFA's suggested closest-approach deflector epoch or retarded gravity.
    A crossing of a mass/limiter corner retains the position without an
    invented unique rate. At the disk centre the correction is quadratic,
    so its first derivative is zero despite the radial norm's corner.
    """
    data = _parameters()
    geometry = []
    for a, b in (
        (ray, CartesianState((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))),
        (observer, sun_at_reception),
        (target_at_emission, sun_at_emission),
    ):
        x, y, z = (av - bv for av, bv in zip(a.position, b.position))
        vx, vy, vz = (av - bv for av, bv in zip(a.velocity, b.velocity))
        length = math.hypot(x, y, z)
        unit = (x / length, y / length, z / length)
        radial = dot(unit, (vx, vy, vz))
        ux, uy, uz = ((v - u * radial) / length for v, u in zip((vx, vy, vz), unit))
        geometry.append((length, radial, unit, (ux, uy, uz)))
    radius, radius_d, p, pd = geometry[0]
    em, em_d, e, ed = geometry[1]
    _, _, q, qd = geometry[2]
    solar_radius = math.radians(data["solar_radius_at_one_au_arcsec"] / 3600)
    impact = _cross(p, e)
    impact_d = tuple(a + b for a, b in zip(_cross(pd, e), _cross(p, ed)))
    impact_length = math.hypot(*impact)
    if impact_length == 0:
        mass = mass_d = 0.0
        mass_corner = False
    else:
        mass, slope = effective_solar_mass(impact_length * em / solar_radius)
        radial_d = (
            dot(impact, impact_d) / impact_length * em + impact_length * em_d
        ) / solar_radius
        mass_corner = slope is None and radial_d != 0
        mass_d = 0.0 if slope is None else slope * radial_d
    # For unit q,e, q.(q+e) = ||q+e||²/2. The unit-sum form preserves
    # relative precision near opposition instead of subtracting nearly
    # equal unit components before accumulating the small denominator.
    unit_sum = tuple(a + b for a, b in zip(q, e))
    denominator = dot(unit_sum, unit_sum) / 2
    denominator_d = dot(unit_sum, tuple(a + b for a, b in zip(qd, ed)))
    limiter_corner = denominator == DEFLECTION_LIMITER and denominator_d != 0
    limited = max(denominator, DEFLECTION_LIMITER)
    limited_d = denominator_d if denominator > DEFLECTION_LIMITER else 0.0
    srs = 2 * data["solar_GM_m3_s2"] / (299792458.0**2 * 149597870700.0)
    weight = mass * srs / em / limited
    direction = _cross(p, _cross(e, q))
    x, y, z = (radius * (a + weight * b) for a, b in zip(p, direction))
    if any(direction) and (mass_corner or (mass != 0 and limiter_corner)):
        return CartesianMotion((x, y, z), None)
    weight_d = (
        srs / em / limited * (mass_d - mass * em_d / em - mass * limited_d / limited)
    )
    direction_d = tuple(
        a + b + c
        for a, b, c in zip(
            _cross(pd, _cross(e, q)),
            _cross(p, _cross(ed, q)),
            _cross(p, _cross(e, qd)),
        )
    )
    vx, vy, vz = (
        radius_d * (pv + weight * dv) + radius * (pvd + weight_d * dv + weight * dvd)
        for pv, pvd, dv, dvd in zip(p, pd, direction, direction_d)
    )
    return CartesianMotion((x, y, z), (vx, vy, vz))
