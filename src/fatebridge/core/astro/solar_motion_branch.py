"""Identify the inspected native solar-deflection interpolation cell.

LBR positions are never changed. The native 2.10.03 source uses linear solar
mass interpolation at radius fractions 0,.01,...,1. At an interior point a
derivative may be computed from a homogeneous side even when the opposite
stencil crosses a knot. This is a local source-domain condition, not a proof
of continuous interval completeness or astronomical/observational accuracy.
"""

from __future__ import annotations

import math
from typing import Any, Dict

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

SOURCE_URL = "https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/sweph.c#L3742"
METHOD_ID = "native_solar_mass_interpolation_cell_geometry_v1"


@runtime.preserve_ephemeris_path()
def solar_interpolation_branch(
    planet: str,
    epoch: float,
    model: str,
    trace: PhysicalEphemerisTrace,
    contexts: Dict[str, Any],
    prefix: str,
) -> Dict[str, Any]:
    """Same pre-deflection ray and Earth/Sun geometry as the pinned source.

    Both the source's sqrt(1-dot²) and a cross-product evaluation must fall
    strictly inside the same cell. The arithmetic margin is conservative
    scale information, not a bound on physical ephemeris errors.
    """
    swe = runtime.swe
    if not math.isfinite(epoch) or planet not in {"Mercury", "Venus", "Mars"}:
        raise EphemerisSourceError("coordinate_motion_unavailable")
    selected = configured_ephemeris_path()
    mask = 0
    for name in COORDINATE_FLAGS:
        mask |= getattr(swe, name)
    fixed = (
        swe.FLG_SWIEPH
        | swe.FLG_SPEED
        | swe.FLG_XYZ
        | swe.FLG_J2000
        | swe.FLG_ICRS
        | swe.FLG_EQUATORIAL
    )

    def state(body: int, flags: int, label: str) -> tuple:
        values, returned = runtime.ephemeris_call("calc", epoch, body, flags)
        assert_physical_configuration(selected)
        expected = flags | swe.FLG_NONUT
        if flags & swe.FLG_TRUEPOS:
            expected |= swe.FLG_NOABERR | swe.FLG_NOGDEFL
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
        factor = prefix + label
        contexts[factor] = trace.observe(factor, model, record_factor=False)
        return tuple(float(x) for x in values)

    ray = state(
        PLANET_SWISSEPH_IDS[planet],
        fixed | swe.FLG_NOGDEFL | swe.FLG_NOABERR,
        "_unbent_ray",
    )[:3]
    # The ray has established this reception's source. Its geometric observer
    # and deflector must not independently reset to another overlapping fit.
    with preserve_native_dependency_context(
        epoch, epoch, model, native=ephemeris_runtime.swe
    ):
        earth = state(swe.EARTH, fixed | swe.FLG_BARYCTR | swe.FLG_TRUEPOS, "_earth")[
            :3
        ]
        sun = state(swe.SUN, fixed | swe.FLG_BARYCTR | swe.FLG_TRUEPOS, "_sun")[:3]
    earth_helio = tuple(a - b for a, b in zip(earth, sun))
    ru = math.sqrt(sum(x * x for x in ray))
    re = math.sqrt(sum(x * x for x in earth_helio))
    if not all(math.isfinite(v) and v > 0 for v in (ru, re)):
        raise EphemerisSourceError("coordinate_values_unavailable")
    u = tuple(x / ru for x in ray)
    e = tuple(x / re for x in earth_helio)
    dot = sum(a * b for a, b in zip(u, e))
    radius = math.radians(959.63 / 3600) / re
    square = 1 - dot * dot
    if square < 0:
        return {
            "method_id": METHOD_ID,
            "status": "boundary_ambiguous",
            "cell": None,
            "source_url": SOURCE_URL,
        }
    impact = math.sqrt(square) / radius
    cross = (
        u[1] * e[2] - u[2] * e[1],
        u[2] * e[0] - u[0] * e[2],
        u[0] * e[1] - u[1] * e[0],
    )
    stable = math.sqrt(sum(x * x for x in cross)) / radius
    # A generous finite-arithmetic scale prevents treating a knot hit as an
    # interior point. No observer/ephemeris uncertainty is inferred here.
    pad = 64 * math.ulp(1.0) / (radius * radius * max(impact, 1e-12))
    lower = min(impact, stable) - pad
    upper = max(impact, stable) + pad
    cell = min(100, math.floor(100 * impact))
    interior = lower > cell / 100 and (cell == 100 or upper < (cell + 1) / 100)
    return {
        "method_id": METHOD_ID,
        "source_url": SOURCE_URL,
        "status": "interior_sampled_cell" if interior else "boundary_ambiguous",
        "cell": cell if interior else None,
        "impact_solar_radius_fraction": impact,
        "cross_product_impact_fraction": stable,
        "arithmetic_margin_fraction": pad,
        "scope": "Pinned native pre-deflection finite-solar-mass interpolation cell; sampled geometry, not continuous monotonicity or physical accuracy certification",
    }
