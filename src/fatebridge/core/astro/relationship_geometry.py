"""Explicit circular, geographical and time policies for relationship charts.

Astrodienst documents arithmetic, spherical and MC-corrected Davison variants.
The subsecond UT1 midpoint and longitude-unwrapping policies are declared here;
the published prose does not specify atomic-time or floating-point details.
"""

from __future__ import annotations

import math
from dataclasses import replace
from fractions import Fraction
from typing import Any, Dict, Tuple

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.geometry import (
    Angle,
    angle_fraction,
    longitude_float,
    normalize_angle,
)
from fatebridge.core.astro.time_scales import datetime_from_ut1, ephemeris_time
from fatebridge.utils.timezones import parse_timezone_name

DAVISON_SOURCE = "https://www.astro.com/cgi/h.cgi?f=gch&h=gch64&lang=e"
COMPOSITE_SOURCE = "https://www.astro.com/faq/fq_fh_compo_e.htm"
MARKS_SOURCE = "https://astroer.com/htmls/bob/bobmar/markschart28.0.htm"


def unique_midpoint(first: float, second: float) -> float:
    """Unordered shorter-arc midpoint; a diametric pair has two equal answers."""
    if not math.isfinite(first) or not math.isfinite(second):
        raise ValueError("中点坐标必须为有限数值")
    values = midpoint_candidates_fraction(first, second)
    if len(values) != 1:
        raise ValueError("精确相隔180°的输入没有唯一短弧中点；不能任取一个方向")
    return longitude_float(values[0])


def midpoint_candidates_fraction(first: Angle, second: Angle) -> Tuple[Fraction, ...]:
    """Retain the original midpoint formula for subsequent classifications."""
    a, b = angle_fraction(first) % 360, angle_fraction(second) % 360
    delta = (b - a) % 360
    if delta == 180:
        axis = ((a + b) / 2) % 180
        return axis, axis + 180
    if delta > 180:
        delta -= 360
    return ((a + delta / 2) % 360,)


def _signed_longitude(value: float) -> float:
    result = float((Fraction(value) + 180) % 360 - 180)
    return min(result, math.nextafter(180.0, 0.0))


def midpoint_candidates(first: float, second: float) -> Tuple[float, ...]:
    """Short-arc point, or both equal candidates for an exact diametric pair."""
    return tuple(
        longitude_float(value) for value in midpoint_candidates_fraction(first, second)
    )


def geographic_midpoint(
    first_longitude: float,
    first_latitude: float,
    second_longitude: float,
    second_latitude: float,
    *,
    spherical: bool = False,
) -> Tuple[float, float]:
    """Coordinate mean on the short longitude arc, or spherical geodesic mean.

    Half-angle identities avoid subtracting nearly opposite unit vectors.
    Exact antipodes are undefined; a pole itself has canonical longitude zero.
    The sphere is an explicit convention, not a WGS84 ellipsoidal midpoint.
    """
    values = (first_longitude, first_latitude, second_longitude, second_latitude)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("地理坐标必须为有限数值")
    if not (-90 <= first_latitude <= 90 and -90 <= second_latitude <= 90):
        raise ValueError("纬度必须在[-90,90]内")
    if not (-180 <= first_longitude <= 180 and -180 <= second_longitude <= 180):
        raise ValueError("经度必须在[-180,180]内")
    if not spherical:
        return (
            _signed_longitude(unique_midpoint(first_longitude, second_longitude)),
            float((Fraction(first_latitude) + Fraction(second_latitude)) / 2),
        )
    delta = (Fraction(second_longitude) - Fraction(first_longitude) + 180) % 360 - 180
    if first_latitude == -second_latitude and (
        abs(delta) == 180 or abs(first_latitude) == 90
    ):
        raise ValueError("对跖点没有唯一球面中点")
    if first_latitude == second_latitude and abs(first_latitude) == 90:
        return 0.0, first_latitude
    mean_lat = math.radians(
        float((Fraction(first_latitude) + Fraction(second_latitude)) / 2)
    )
    half_lat_diff = math.radians(
        float((Fraction(second_latitude) - Fraction(first_latitude)) / 2)
    )
    half_lon_diff = math.radians(float(delta / 2))
    cos_half_lon = 0.0 if abs(delta) == 180 else math.cos(half_lon_diff)
    x = math.cos(mean_lat) * math.cos(half_lat_diff) * cos_half_lon
    y = -math.sin(mean_lat) * math.sin(half_lat_diff) * math.sin(half_lon_diff)
    z = math.sin(mean_lat) * math.cos(half_lat_diff)
    latitude = math.degrees(math.atan2(z, math.hypot(x, y)))
    if abs(latitude) == 90:
        return 0.0, latitude
    longitude = float(Fraction(first_longitude) + delta / 2) + math.degrees(
        math.atan2(y, x)
    )
    return _signed_longitude(longitude), latitude


def _tropical_mc(ut1: float, longitude: float) -> float:
    # MC depends on the meridian, not geographic latitude. Latitude zero avoids
    # undefined polar ASC geometry in this MC-only correction calculation.
    _, angles = runtime.ephemeris_call("houses_ex", ut1, 0.0, longitude, b"E")
    return normalize_angle(float(angles[1]))


def _corrected_ut1(
    centre: float, longitude: float, first: AstroBirthInfo, second: AstroBirthInfo
) -> Tuple[float, Dict[str, Any]]:
    if runtime.swe is None:
        raise ValueError("Davison MC校正需要Swiss Ephemeris")
    natal_mcs = [
        _tropical_mc(ephemeris_time(p.require_utc_datetime).jd_ut1, p.longitude)
        for p in (first, second)
    ]
    axis = float(((Fraction(natal_mcs[0]) + Fraction(natal_mcs[1])) / 2) % 180)
    candidates = [axis, axis + 180]
    mc_here = _tropical_mc(centre, longitude)
    distances = [
        abs((mc_here - candidate + 180) % 360 - 180) for candidate in candidates
    ]
    if distances[0] == distances[1]:
        raise ValueError("Davison MC轴校正有两个等距方向，无法唯一选择")
    target = candidates[distances.index(min(distances))]

    def residual(at: float) -> float:
        difference = normalize_angle(_tropical_mc(at, longitude) - target)
        return difference - 360 if difference >= 180 else difference

    brackets = []
    left, f_left = centre - 0.4, residual(centre - 0.4)
    for step in range(1, 41):
        right = centre - 0.4 + step * 0.02
        f_right = residual(right)
        if f_left <= 0 <= f_right and f_right - f_left < 90:
            brackets.append((left, right))
        left, f_left = right, f_right
    if not brackets:
        raise ValueError("Davison MC校正未找到有效括界")
    solutions = []
    for left, right in brackets:
        for _ in range(60):
            mid = (left + right) / 2
            if mid in (left, right):
                break
            if residual(mid) >= 0:
                right = mid
            else:
                left = mid
        solutions.append(right)
    solved = min(solutions, key=lambda at: abs(at - centre))
    error = abs(residual(solved))
    if error > 1e-5:
        raise ValueError("Davison MC校正残差超限")
    return solved, {
        "mc_target_tropical": target,
        "mc_actual_tropical": _tropical_mc(solved, longitude),
        "mc_residual_degrees": error,
        "time_correction_seconds_ut1": (solved - centre) * 86400,
        "mc_target_policy": "nearest direction of the natal MC midpoint meridian axis",
    }


def davison_birth(
    first: AstroBirthInfo, second: AstroBirthInfo, *, variant: str = "uncorrected"
) -> Tuple[AstroBirthInfo, Dict[str, Any]]:
    if variant not in {"uncorrected", "corrected", "spherical"}:
        raise ValueError("davison_variant必须为uncorrected、corrected或spherical")
    first_time, second_time = (
        ephemeris_time(p.require_utc_datetime) for p in (first, second)
    )
    if runtime.swe is None:
        raise ValueError("Davison时间尺度换算需要Swiss Ephemeris，不能冒用UTC为UT1")
    midpoint = float((Fraction(first_time.jd_ut1) + Fraction(second_time.jd_ut1)) / 2)
    longitude, latitude = geographic_midpoint(
        first.longitude,
        first.latitude,
        second.longitude,
        second.latitude,
        spherical=variant == "spherical",
    )
    correction: Dict[str, Any] = {}
    if variant == "corrected":
        midpoint, correction = _corrected_ut1(midpoint, longitude, first, second)
    utc = datetime_from_ut1(midpoint)
    if variant == "corrected":
        actual_mc = _tropical_mc(ephemeris_time(utc).jd_ut1, longitude)
        target = correction["mc_target_tropical"]
        actual_error = abs((actual_mc - target + 180) % 360 - 180)
        if actual_error > 1e-5:
            raise ValueError("民用时间转换后Davison MC校正残差超限")
        correction.update(
            mc_actual_tropical=actual_mc, mc_residual_degrees=actual_error
        )
    zone = first.timezone if first.timezone == second.timezone else "UTC"
    birth = AstroBirthInfo(
        name=f"{first.name}/{second.name} 时空中点",
        birth_place=f"{first.birth_place} / {second.birth_place} 中点",
        timezone=zone,
        longitude=longitude,
        latitude=latitude,
        local_datetime=utc.astimezone(parse_timezone_name(zone)),
        utc_datetime=utc,
    )
    return birth, {
        "method_id": "davison_geometry_v2",
        "variant": variant,
        "source_url": DAVISON_SOURCE,
        "source_kind": "first_party_implementation_documentation",
        "positions_from_single_instant": True,
        "time_policy": "arithmetic mean of modeled UT1 Julian days, then frozen-policy civil conversion",
        "time_source_scope": "Source specifies mean birth times; UT1 and subsecond policy are explicit FateBridge conventions, not a quote from Davison's original book",
        "geographic_policy": (
            "spherical_shortest_geodesic"
            if variant == "spherical"
            else "latitude_mean_short_arc_longitude_mean"
        ),
        "longitude_unwrapping": (
            "shortest great-circle; exact antipodes undefined; longitude zero at a pole"
            if variant == "spherical"
            else "short arc; exact opposite meridians require an explicit alternative"
        ),
        "midpoint_jd_ut1": midpoint,
        "input_julian_days_ut1": [first_time.jd_ut1, second_time.jd_ut1],
        "midpoint_longitude": longitude,
        "midpoint_latitude": latitude,
        **correction,
    }


def marks_birth(
    person: AstroBirthInfo, relationship: AstroBirthInfo, *, variant: str
) -> Tuple[AstroBirthInfo, Dict[str, Any]]:
    birth, policy = davison_birth(person, relationship, variant=variant)
    return replace(birth, name=f"{person.name} 马克斯盘"), {
        **policy,
        "method_id": "marks_natal_davison_v1",
        "source_url": MARKS_SOURCE,
        "source_kind": "author_lesson_mirror_original_site_unavailable",
        "recipe": "Davison between this person's natal data and the couple's Davison data",
        "base_davison_variant": variant,
    }
