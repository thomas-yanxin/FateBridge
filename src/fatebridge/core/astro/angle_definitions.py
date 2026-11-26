"""Qualify geographic and selected-model pole conventions.

The frozen USNO altitude model loses its hour-angle term at a rotation-axis
latitude of +/-90 degrees. A geographic pole has that property in the default
zero-polar-motion convention; selected EOP can separate those directions.
Swiss near-pole limits and the supplied meridian remain a distinct convention
(general documentation 6.3-6.4; swehouse.c CalcH).
"""

from __future__ import annotations

import math
import sys
from collections.abc import Mapping
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.earth_attitude import earth_attitude, physical_equator
from fatebridge.core.astro.iers_ut1 import active_ut1
from fatebridge.core.astro.terrestrial_observer import (
    TerrestrialFrame,
    terrestrial_frame,
)
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant

# R is the length of the horizon normal projected onto the ecliptic plane.
# Normalizing the intersection amplifies perturbations by roughly 1/R. Below
# sqrt(eps), half the double's significant bits can be lost. These are numerical
# diagnostics, not bounds on observation, clock, location or model errors.
INTERSECTION_CONDITION_THRESHOLD = math.sqrt(sys.float_info.epsilon)
INTERSECTION_RESOLUTION_GUARD = 64 * sys.float_info.epsilon
UNRESOLVED_ASCENDANT_STATUSES = frozenset(
    {
        "ecliptic_horizon_numerically_unresolved",
        "underdetermined_ascendant",
        "underdetermined_reference_geometry",
    }
)


def is_ascendant_resolved(source: object) -> bool:
    """Return whether a chart, subject, reference, or angle_definition resolves ASC."""
    if source is None:
        return True
    if isinstance(source, Mapping):
        if "geometric_ascendant_resolved" in source:
            return source.get("geometric_ascendant_resolved") is not False
        if source.get("status") in UNRESOLVED_ASCENDANT_STATUSES:
            return False
        for key in ("angle_definition", "calculation_basis", "chart_profile"):
            nested = source.get(key)
            if isinstance(nested, Mapping) and not is_ascendant_resolved(nested):
                return False
        angles = source.get("angles")
        if isinstance(angles, Mapping):
            asc = angles.get("ascendant")
            if isinstance(asc, Mapping) and not is_ascendant_resolved(asc):
                return False
        ascendant = source.get("ascendant")
        if isinstance(ascendant, Mapping) and not is_ascendant_resolved(ascendant):
            return False
        if (
            ("absolute_degree" in source or "longitude" in source)
            and source.get("absolute_degree") is None
            and source.get("longitude") is None
        ):
            return False
        return True
    for attr in ("calculation_basis", "chart_profile", "angle_definition"):
        nested = getattr(source, attr, None)
        if isinstance(nested, Mapping) and not is_ascendant_resolved(nested):
            return False
    return True


def ecliptic_horizon_angle_definition(
    *, latitude: float, armc: float, obliquity: float, angle_method: str
) -> dict[str, Any] | None:
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
        "source_scope": "Conditioning derived from altitude equation; backend conventions are separate from primary-text rules",
    }


def native_ecliptic_horizon_angle_definition(
    *,
    julian_day_ut1: float | UT1Instant,
    latitude: float,
    longitude: float,
    armc: float,
    julian_day_tt: float | TTInstant | None = None,
) -> dict[str, Any] | None:
    """Use the managed house equator and its exact selected epoch.

    |A| alone lower-bounds R, so ordinary charts need no extra reduction.
    The longitude origin does not change the intersection's conditioning.
    """
    geographic_latitude = latitude
    observed = active_ut1.get() is not None
    if (
        not observed
        and abs(math.cos(math.radians(latitude)) * math.cos(math.radians(armc)))
        > INTERSECTION_CONDITION_THRESHOLD
    ):
        return None
    if runtime.swe is None:
        raise ValueError("Native angle conditioning requires Swiss Ephemeris")
    if observed:
        equator = physical_equator(
            runtime.swe, julian_day_ut1, julian_day_tt=julian_day_tt
        )
        _, latitude = terrestrial_frame(
            equator, longitude=longitude, latitude=latitude
        ).equatorial_site()
        if abs(math.cos(math.radians(latitude)) * math.cos(math.radians(armc))) > (
            INTERSECTION_CONDITION_THRESHOLD
        ):
            return None
    attitude = earth_attitude(runtime.swe, julian_day_ut1, julian_day_tt=julian_day_tt)
    definition = ecliptic_horizon_angle_definition(
        latitude=latitude,
        armc=armc,
        obliquity=attitude.reduction.house_obliquity,
        angle_method="swisseph",
    )
    if observed and definition is not None:
        definition["geometry_inputs"].update(
            geographic_latitude=geographic_latitude,
            rotation_axis_latitude=latitude,
        )
    return definition


def geographic_pole_angle_definition(
    latitude: float, *, frame: TerrestrialFrame | None = None
) -> dict[str, Any] | None:
    """Exact poles only; do not classify nearby, well-defined latitudes as poles."""
    if abs(latitude) != 90.0:
        return None
    result: dict[str, object] = {
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
    }
    if frame is not None:
        _, rotation_latitude = frame.equatorial_site()
        result["geometry_inputs"] = {
            "geographic_latitude": latitude,
            "rotation_axis_latitude": rotation_latitude,
            "frame": "selected_model_vertical_relative_to_CIP",
        }
        if abs(rotation_latitude) != 90:
            result.update(
                status="geographic_pole_distinct_from_rotation_pole",
                fixed_direction_diurnal_rising_defined=None,
                note_zh=(
                    "输入位于地理极点，但所选极移模型的当地竖直不与天极重合；"
                    "不能仅凭地理纬度断言固定方向没有每日升落。"
                    "本记录只说明地理坐标约定，实际高度与交点按所选地平模型读取。"
                ),
            )
    return result
