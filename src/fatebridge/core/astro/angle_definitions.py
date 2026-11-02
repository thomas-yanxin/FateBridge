"""Qualify geographic-pole angle conventions without discarding computed sky.

USNO's altitude equation loses its hour-angle term at latitude +/-90 degrees:
a fixed celestial direction has no daily rise/set there. Swiss Ephemeris
nevertheless returns an ecliptic/horizon intersection using a near-pole limit
and the supplied meridian (general documentation 6.3-6.4; swehouse.c CalcH).
"""

from __future__ import annotations

import math
import sys
from typing import Any, Dict, Optional

from fatebridge.core.astro import runtime

# R is the length of the horizon normal projected onto the ecliptic plane.
# Normalizing the intersection amplifies perturbations by roughly 1/R. Below
# sqrt(eps), half the double's significant bits can be lost. These are numerical
# diagnostics, not bounds on observation, clock, location or model errors.
INTERSECTION_CONDITION_THRESHOLD = math.sqrt(sys.float_info.epsilon)
INTERSECTION_RESOLUTION_GUARD = 64 * sys.float_info.epsilon


def ecliptic_horizon_angle_definition(
    *, latitude: float, armc: float, obliquity: float, angle_method: str
) -> Optional[Dict[str, Any]]:
    """Qualify a nearly coincident horizon/ecliptic in the actual angle model.

    USNO altitude equation, with zero ecliptic latitude, gives
    sin(alt) = A*cos(lambda) + B*sin(lambda). R=hypot(A,B) is the sine of
    the acute angle between the two planes. At R=0 every ecliptic longitude
    is on the horizon; no unique ASC exists. Finite precision can only detect
    proximity to that degeneracy, not prove exact physical coincidence.
    """
    if not all(math.isfinite(v) for v in (latitude, armc, obliquity)):
        raise ValueError("Angle conditioning requires finite geometry inputs")
    phi, theta, eps = map(math.radians, (latitude, armc, obliquity))
    a = math.cos(phi) * math.cos(theta)
    b = math.fsum(
        [math.cos(phi) * math.sin(theta) * math.cos(eps), math.sin(phi) * math.sin(eps)]
    )
    r = math.hypot(a, b)
    if r > INTERSECTION_CONDITION_THRESHOLD:
        return None
    resolved = r > INTERSECTION_RESOLUTION_GUARD
    return {
        "status": (
            "ecliptic_horizon_ill_conditioned"
            if resolved
            else "ecliptic_horizon_numerically_unresolved"
        ),
        "angle_method": angle_method,
        "geometric_ascendant_resolved": resolved,
        "retained_ascendant_role": (
            "ill_conditioned_intersection"
            if resolved
            else "backend_numeric_convention_only"
        ),
        "geometry_inputs": {
            "geographic_latitude": latitude,
            "armc": armc,
            "obliquity": obliquity,
            "frame": "equatorial_meridian_and_physical_ecliptic_of_angle_model",
        },
        "conditioning": {
            "altitude_cos_longitude_coefficient": a,
            "altitude_sin_longitude_coefficient": b,
            "intersection_normal_norm": r,
            "plane_separation_degrees": math.degrees(math.asin(min(1.0, r))),
            "condition_threshold": INTERSECTION_CONDITION_THRESHOLD,
            "float_resolution_guard": INTERSECTION_RESOLUTION_GUARD,
            "threshold_basis": "sqrt_binary64_epsilon_and_64_binary64_epsilon",
            "not_an_input_or_model_error_bound": True,
        },
        "dependent_quantities": [
            "ascendant",
            "ascendant_dependent_house_cusps",
            "ascendant_dependent_house_membership",
            "ascendant_dependent_lots",
        ],
        "midheaven_restricted_by_this_condition": False,
        "note_zh": (
            "黄道与地平面几乎重合，交线对输入扰动高度敏感；"
            "ASC及依赖它的宫位、福点须连同条件指标读取。指标不是输入或模型误差界。"
            if resolved
            else (
                "本角度模型的黄道与地平面接近重合，已落入浮点分辨保护尺度，"
                "无法从这些数值解析唯一ASC；返回的ASC及依赖它的宫位、福点"
                "仅保留为后端数值约定。MC与不依赖ASC的星体位置不受这项退化直接限制。"
            )
        ),
        "source_urls": [
            "https://aa.usno.navy.mil/faq/alt_az",
            "https://www.astro.com/swisseph/swisseph.htm",
        ],
        "source_scope": "Conditioning derived from altitude equation; backend conventions are separate from primary-text rules",
    }


def native_ecliptic_horizon_angle_definition(
    *, julian_day_ut1: float, latitude: float, armc: float
) -> Optional[Dict[str, Any]]:
    """Use the same true obliquity and UT1 argument as houses_ex, not an offset.

    |A| alone lower-bounds R, so most charts need no extra native call.
    houses_ex internally uses jd_ut1 + deltat_ex(jd_ut1, house_flags). For
    our flags=0/SIDEREAL both use the no-ephemeris-bit Delta T convention.
    calc_ut defaults its ephemeris bit to SWIEPH, which can select a different
    tidal acceleration for ancient dates. Do not substitute it here. A sidereal
    zodiac does not rotate the physical horizon or equatorial ascmc[2].
    """
    if abs(math.cos(math.radians(latitude)) * math.cos(math.radians(armc))) > (
        INTERSECTION_CONDITION_THRESHOLD
    ):
        return None
    if runtime.swe is None:
        raise ValueError("Native angle conditioning requires Swiss Ephemeris")
    delta_t = float(runtime.ephemeris_call("deltat_ex", julian_day_ut1, 0))
    ecliptic, flags = runtime.ephemeris_call(
        "calc", julian_day_ut1 + delta_t, runtime.swe.ECL_NUT, 0
    )
    if flags < 0:
        raise ValueError("Native angle conditioning has no valid obliquity")
    return ecliptic_horizon_angle_definition(
        latitude=latitude,
        armc=armc,
        obliquity=float(ecliptic[0]),
        angle_method="swisseph",
    )


def geographic_pole_angle_definition(latitude: float) -> Optional[Dict[str, Any]]:
    """Exact poles only; do not classify nearby, well-defined latitudes as poles."""
    if abs(latitude) != 90.0:
        return None
    return {
        "status": "geographic_pole_meridian_convention",
        "ascendant_definition": "eastern_ecliptic_horizon_intersection_relative_to_supplied_meridian",
        "fixed_direction_diurnal_rising_defined": False,
        "reference_meridian": "supplied_geographic_longitude",
        "dependent_quantities": [
            "ascendant",
            "midheaven",
            "house_cusps",
            "house_membership",
            "ascendant_dependent_lots",
        ],
        "note_zh": (
            "精确地理极点：固定天球方向不发生由地球自转造成的每日升落；"
            "ASC为相对输入经度所定子午线的黄道／地平交点约定。"
            "天顶、宫位与依赖ASC的福点须连同此约定读取，不能视为物理升起时刻。"
        ),
        "source_urls": [
            "https://www.astro.com/swisseph/swisseph.htm",
            "https://aa.usno.navy.mil/faq/alt_az",
        ],
    }
