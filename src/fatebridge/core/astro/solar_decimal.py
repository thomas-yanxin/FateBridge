"""Stable auxiliary reduction of the pinned finite-Sun apparent-position model.

Small solar separations make the native binary64 subtraction 1+q.e and
sqrt(1-(u.e)^2) ill-conditioned. This uses equivalent vector identities and
50-digit arithmetic on the observed geometric states. It neither replaces
displayed positions nor supplies an independent physical ephemeris.
"""

from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal, localcontext
from importlib.resources import files
from typing import Any, Dict, List, Sequence, Tuple

from fatebridge.core import ephemeris_runtime
from fatebridge.core.astro import runtime
from fatebridge.core.astro.native_coordinates import COORDINATE_FLAGS
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.compressed_ephemeris import preserve_native_dependency_context
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.utils.errors import EphemerisSourceError

METHOD_ID = "native_geometric_decimal_apparent_reduction_v2"
PRECISION = 50
PROFILE_SHA256 = "ad8dd7126d5e1a4b2e6cbcef6aa13d5a4bbc51778db0c037f430a3fac50e8b36"
SOURCE_URL = "https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/sweph.c"
FRAME_BODIES = ("Mercury", "Mars", "Pluto")
Vector = Sequence[Decimal]


def mass_profile() -> List[Tuple[Decimal, Decimal]]:
    """Check the reviewed source table on every fallback sample, without caching."""
    try:
        raw = (
            files("fatebridge.data")
            .joinpath("astro/native-solar-mass-v1.json")
            .read_bytes()
        )
        if hashlib.sha256(raw).hexdigest() != PROFILE_SHA256:
            raise ValueError("Changed finite-Sun source profile")
        data = json.loads(raw)
        return [(Decimal(r), Decimal(m)) for r, m in data["radius_mass_pairs"]]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise EphemerisSourceError("coordinate_values_unavailable") from error


def dot(a: Vector, b: Vector) -> Decimal:
    return sum((x * y for x, y in zip(a, b)), Decimal(0))


def add(a: Vector, b: Vector) -> List[Decimal]:
    return [x + y for x, y in zip(a, b)]


def sub(a: Vector, b: Vector) -> List[Decimal]:
    return [x - y for x, y in zip(a, b)]


def scale(a: Vector, value: Decimal) -> List[Decimal]:
    return [x * value for x in a]


def cross(a: Vector, b: Vector) -> List[Decimal]:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def norm(a: Vector) -> Decimal:
    return dot(a, a).sqrt()


def unit(a: Vector) -> List[Decimal]:
    size = norm(a)
    if not size.is_finite() or size <= 0:
        raise EphemerisSourceError("coordinate_values_unavailable")
    return scale(a, Decimal(1) / size)


def stable_interpolation_cell(
    impact: Decimal, angular_radius: Decimal, observer_to_target_ratio: Decimal
) -> Dict[str, Any]:
    """Classify the stable reduction's cell, retaining its arithmetic margin.

    The cross product avoids sqrt(1-dot²)'s inverse-radius-squared loss.
    This finite-arithmetic scale is not an observational/source-error bound.
    """
    if (
        not all(
            v.is_finite() for v in (impact, angular_radius, observer_to_target_ratio)
        )
        or impact < 0
        or angular_radius <= 0
        or observer_to_target_ratio <= 0
    ):
        raise EphemerisSourceError("coordinate_values_unavailable")
    pad = (
        64
        * Decimal.from_float(math.ulp(1.0))
        / angular_radius
        * (1 + observer_to_target_ratio)
    )
    cell = min(100, int(impact * 100))
    lower, upper = impact - pad, impact + pad
    interior = lower > Decimal(cell) / 100 and (
        cell == 100 or upper < Decimal(cell + 1) / 100
    )
    return {
        "method_id": "decimal_continuous_source_cross_product_cell_v1",
        "status": "interior_sampled_cell" if interior else "boundary_ambiguous",
        "cell": cell if interior else None,
        "impact_solar_radius_fraction": float(impact),
        "arithmetic_margin_fraction": float(pad),
        "scope": "Stable auxiliary source reduction cell; finite arithmetic scale, not continuous-interval or physical ephemeris accuracy certification.",
    }


def rotate(
    vector: Vector, pairs: Sequence[Tuple[Vector, Vector]]
) -> Tuple[List[Decimal], Decimal]:
    """Recover and check a proper frame rotation from three native basis pairs."""
    a = [unit(p[0][:3]) for p in pairs]
    c = [unit(p[1][:3]) for p in pairs]
    matrix = [
        [a[col][row] for col in range(3)]
        + [Decimal(int(row == col)) for col in range(3)]
        for row in range(3)
    ]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda row: abs(matrix[row][column]))
        if abs(matrix[pivot][column]) < Decimal("1e-12"):
            raise EphemerisSourceError("coordinate_motion_unavailable")
        matrix[column], matrix[pivot] = matrix[pivot], matrix[column]
        divisor = matrix[column][column]
        matrix[column] = [x / divisor for x in matrix[column]]
        for row in range(3):
            if row != column:
                factor = matrix[row][column]
                matrix[row] = [
                    x - factor * y for x, y in zip(matrix[row], matrix[column])
                ]
    inverse = [row[3:] for row in matrix]
    rotation = [
        [sum((c[k][i] * inverse[k][j] for k in range(3)), Decimal(0)) for j in range(3)]
        for i in range(3)
    ]
    orthogonal = max(
        abs(
            sum((rotation[k][i] * rotation[k][j] for k in range(3)), Decimal(0))
            - int(i == j)
        )
        for i in range(3)
        for j in range(3)
    )
    determinant = dot(rotation[0], cross(rotation[1], rotation[2]))
    if orthogonal > Decimal("1e-10") or abs(determinant - 1) > Decimal("1e-10"):
        raise EphemerisSourceError("coordinate_contract_changed")
    return [dot(row, vector) for row in rotation], orthogonal


@runtime.preserve_ephemeris_path()
def reduced_longitude(
    planet: str,
    epoch: float,
    *,
    sidereal: bool,
    trace: PhysicalEphemerisTrace,
    contexts: Dict[str, Any],
    prefix: str,
    center_source: Dict[str, Any],
    model: str = "swieph",
) -> Tuple[float, Dict[str, Any]]:
    """Reduce shared Swiss geometric states, retaining the center file cohort.

    Two source light-time iterations select a native geometric retarded state;
    its lost fractional epoch is restored to first order. The high-precision
    deflection and aberration are then transformed by checked native frame
    pairs. This is not an independent ephemeris or a physical accuracy bound.
    """
    swe = runtime.swe
    if (
        not math.isfinite(epoch)
        or planet not in {"Mercury", "Venus", "Mars"}
        or model not in {"swieph", "jpl"}
    ):
        raise EphemerisSourceError("coordinate_motion_unavailable")
    selected = configured_ephemeris_path()
    base = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_XYZ | swe.FLG_TRUEPOS
    fixed = base | swe.FLG_EQUATORIAL | swe.FLG_J2000 | swe.FLG_ICRS
    display = base | (swe.FLG_SIDEREAL if sidereal else 0)
    mask = 0
    for name in COORDINATE_FLAGS:
        mask |= getattr(swe, name)

    def state(at: float, body: int, flags: int, suffix: str) -> List[Decimal]:
        values, returned = runtime.ephemeris_call("calc", at, body, flags)
        assert_physical_configuration(selected)
        expected = flags | swe.FLG_NOABERR | swe.FLG_NOGDEFL
        if flags & (swe.FLG_J2000 | swe.FLG_SIDEREAL):
            expected |= swe.FLG_NONUT
        if (
            returned < 0
            or returned & mask != expected & mask
            or not returned & swe.FLG_SPEED
        ):
            raise EphemerisSourceError("coordinate_contract_changed")
        if runtime.ephemeris_model_from_retflag(returned) != model:
            raise EphemerisSourceError("model_changed")
        if len(values) != 6 or not all(math.isfinite(x) for x in values):
            raise EphemerisSourceError("coordinate_values_unavailable")
        factor = prefix + suffix
        context = trace.observe(factor, model, record_factor=False)
        contexts[factor] = context
        if context != center_source:
            raise EphemerisSourceError("dependency_source_window_incoherent")
        return [Decimal.from_float(float(x)) for x in values]

    with (
        localcontext() as ctx,
        preserve_native_dependency_context(
            epoch, epoch, model, native=ephemeris_runtime.swe
        ),
    ):
        ctx.prec = PRECISION
        mass = mass_profile()
        au, light, day = Decimal(149597870700), Decimal(299792458), Decimal(86400)
        body = PLANET_SWISSEPH_IDS[planet]
        initial = state(epoch, body, fixed | swe.FLG_BARYCTR, "_initial")
        earth = state(epoch, swe.EARTH, fixed | swe.FLG_BARYCTR, "_earth")
        sun = state(epoch, swe.SUN, fixed | swe.FLG_BARYCTR, "_sun")
        rough = initial[:3]
        delay = Decimal(0)
        for _ in range(2):
            delay = norm(sub(rough, earth[:3])) * au / light / day
            rough = sub(initial[:3], scale(initial[3:], delay))
        at = float(Decimal.from_float(epoch) - delay)
        remainder = Decimal.from_float(epoch) - Decimal.from_float(at) - delay
        with preserve_native_dependency_context(
            epoch, at, model, native=ephemeris_runtime.swe
        ):
            retarded = state(at, body, fixed | swe.FLG_BARYCTR, "_retarded")
        ray = sub(add(retarded[:3], scale(retarded[3:], remainder)), earth[:3])
        radius = norm(ray)
        u = unit(ray)
        eh = sub(earth[:3], sun[:3])
        re = norm(eh)
        e = unit(eh)
        q = unit(sub(add(ray, earth[:3]), sub(sun[:3], scale(sun[3:], delay))))
        impact = norm(cross(u, e)) / (
            Decimal.from_float(math.radians(959.63 / 3600)) / re
        )
        source_cell = stable_interpolation_cell(
            impact, Decimal.from_float(math.radians(959.63 / 3600)) / re, re / radius
        )
        if impact <= 0:
            fraction = Decimal(0)
        elif impact >= 1:
            fraction = Decimal(1)
        else:
            for (r0, m0), (r1, m1) in zip(mass, mass[1:]):
                if impact >= r1:
                    fraction = m0 + (impact - r0) * (m1 - m0) / (r1 - r0)
                    break
            else:
                raise EphemerisSourceError("coordinate_values_unavailable")
        strength = 2 * Decimal("1.32712440017987e20") * fraction / light**2 / au / re
        denominator = dot(add(q, e), add(q, e)) / 2
        if denominator <= 0:
            raise EphemerisSourceError("coordinate_motion_unavailable")
        deflected = scale(
            add(u, scale(cross(u, cross(e, q)), strength / denominator)), radius
        )
        beta = scale(earth[3:], au / light / day)
        r = norm(deflected)
        lorentz = (1 - dot(beta, beta)).sqrt()
        f = dot(deflected, beta) / r
        apparent = scale(
            add(scale(deflected, lorentz), scale(beta, (1 + f / (1 + lorentz)) * r)),
            1 / (1 + f),
        )
        pairs = [
            (
                state(epoch, PLANET_SWISSEPH_IDS[name], fixed, f"_basis_{name}_fixed"),
                state(
                    epoch, PLANET_SWISSEPH_IDS[name], display, f"_basis_{name}_display"
                ),
            )
            for name in FRAME_BODIES
        ]
        displayed, orthogonal = rotate(apparent, pairs)
        longitude = (
            math.degrees(math.atan2(float(displayed[1]), float(displayed[0]))) % 360
        )
        return longitude, {
            "frame_orthogonality_error": float(orthogonal),
            "epoch_remainder_days": float(remainder),
            "solar_interpolation_branch": source_cell,
            "ephemeris_model": model,
        }
