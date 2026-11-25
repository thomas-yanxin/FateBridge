"""Recover the sub-ULP remainder of the inspected native light-time epoch.

This stabilizes auxiliary position samples for differentiation. It never
rewrites a displayed native position or substitutes an analytical orbit.
The small first-order displacement retains an explicit policy and is not an
independent apparent-motion accuracy certificate.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Sequence, Tuple

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

METHOD_ID = "native_retarded_epoch_remainder_linearization_v1"
SOURCE_URL = "https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/sweph.c"
AU_METRES = 149597870700.0
LIGHT_METRES_PER_SECOND = 299792458.0


def epoch_subtraction_remainder(epoch: float, delay: float) -> Tuple[float, float]:
    if not math.isfinite(epoch) or not math.isfinite(delay) or delay < 0:
        raise EphemerisSourceError("coordinate_values_unavailable")
    rounded = epoch - delay
    return rounded, math.fsum((epoch, -rounded, -delay))


@runtime.preserve_ephemeris_path()
def stabilized_longitude_sample(
    planet: str,
    julian_day_tt: float,
    coordinates: Sequence[float],
    model: str,
    *,
    sidereal: bool,
    source_trace: PhysicalEphemerisTrace,
    contexts: Dict[str, Any],
    factor_prefix: str,
) -> Tuple[float, Dict[str, Any]]:
    """Linearize only the lost retarded-epoch fraction, using physical states.

    The two rough light-time iterations follow app_pos_etc_plan, before the
    precise retarded body evaluation. Fixed ICRS states determine that epoch;
    the retarded velocity is projected in the display frame. Frame motion and
    apparent-position Jacobian cross terms are higher-order omissions, so the
    caller still requires bounded multi-step agreement and external audits.
    """
    swe = runtime.swe
    if swe is None or planet not in {"Mercury", "Venus", "Mars"}:
        raise EphemerisSourceError("coordinate_motion_unavailable")
    selected = configured_ephemeris_path()
    mask = 0
    for name in COORDINATE_FLAGS:
        mask |= getattr(swe, name)

    def state(epoch: float, body: int, flags: int, suffix: str) -> Tuple[float, ...]:
        values, returned = runtime.ephemeris_call("calc", epoch, body, flags)
        assert_physical_configuration(selected)
        expected = flags
        if flags & swe.FLG_TRUEPOS:
            expected |= swe.FLG_NOABERR | swe.FLG_NOGDEFL
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
        if len(values) != 6 or not all(math.isfinite(v) for v in values):
            raise EphemerisSourceError("coordinate_values_unavailable")
        factor = factor_prefix + suffix
        contexts[factor] = source_trace.observe(factor, model, record_factor=False)
        return tuple(float(v) for v in values)

    # Reception and retarded auxiliary states must retain the displayed
    # coordinate's checked source window through all dependent calls.
    with preserve_native_dependency_context(
        julian_day_tt, julian_day_tt, model, native=ephemeris_runtime.swe
    ):
        fixed = (
            swe.FLG_SWIEPH
            | swe.FLG_SPEED
            | swe.FLG_XYZ
            | swe.FLG_BARYCTR
            | swe.FLG_TRUEPOS
            | swe.FLG_J2000
            | swe.FLG_ICRS
            | swe.FLG_EQUATORIAL
        )
        body_id = PLANET_SWISSEPH_IDS[planet]
        initial = state(julian_day_tt, body_id, fixed, "_initial_body")
        earth = state(julian_day_tt, swe.EARTH, fixed, "_observer")
        rough = initial[:3]
        delay = 0.0
        for _ in range(2):
            displacement = [a - b for a, b in zip(rough, earth[:3])]
            # Preserve the inspected source's arithmetic order for its selected
            # rounded retarded epoch; fsum is used only for the lost subtraction.
            delay = (
                math.sqrt(sum(x * x for x in displacement))
                * AU_METRES
                / LIGHT_METRES_PER_SECOND
                / 86400.0
            )
            rough = tuple(x - delay * v for x, v in zip(initial[:3], initial[3:]))
        retarded, remainder = epoch_subtraction_remainder(julian_day_tt, delay)
        display = (
            swe.FLG_SWIEPH
            | swe.FLG_SPEED
            | swe.FLG_XYZ
            | swe.FLG_BARYCTR
            | swe.FLG_TRUEPOS
            | (swe.FLG_SIDEREAL if sidereal else 0)
        )
        with preserve_native_dependency_context(
            julian_day_tt, retarded, model, native=ephemeris_runtime.swe
        ):
            velocity = state(retarded, body_id, display, "_retarded_velocity")[3:]
        longitude, latitude = map(math.radians, coordinates[:2])
        radius = float(coordinates[2])
        x = radius * math.cos(longitude) * math.cos(latitude)
        y = radius * math.sin(longitude) * math.cos(latitude)
        denominator = x * x + y * y
        if not math.isfinite(denominator) or denominator <= 0:
            raise EphemerisSourceError("coordinate_values_unavailable")
        shift = remainder * math.degrees(
            (x * velocity[1] - y * velocity[0]) / denominator
        )
        if not math.isfinite(shift):
            raise EphemerisSourceError("coordinate_values_unavailable")
        return float(coordinates[0]) + shift, {
            "method_id": METHOD_ID,
            "retarded_epoch_jd_tt": retarded,
            "epoch_remainder_days": remainder,
            "sampling_longitude_shift_arcseconds": shift * 3600,
            "source_url": SOURCE_URL,
            "displayed_native_position_changed": False,
        }
