"""Calculate circular, geographic, and physical-epoch relationship midpoints."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Literal, TypedDict

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.geometry import (
    Angle,
    angle_fraction,
    longitude_float,
    normalize_angle,
)
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.utils.timezones import parse_timezone_name

DAVISON_SOURCE = "https://www.astro.com/cgi/h.cgi?f=gch&h=gch64&lang=e"
COMPOSITE_SOURCE = "https://www.astro.com/faq/fq_fh_compo_e.htm"
MARKS_SOURCE = "https://astroer.com/htmls/bob/bobmar/markschart28.0.htm"

DavisonVariant = Literal["uncorrected", "corrected", "spherical"]
DAVISON_VARIANTS: frozenset[DavisonVariant] = frozenset(
    {"uncorrected", "corrected", "spherical"}
)
MC_CORRECTION_LIMIT_DEGREES = 1e-5
MC_SEARCH_HALF_WINDOW_DAYS = 0.4
MC_SEARCH_STEP_DAYS = 0.02
MC_SEARCH_STEP_COUNT = 40
MC_BISECTION_LIMIT = 60
SECONDS_PER_DAY = 86400


@dataclass(frozen=True, kw_only=True)
class CorrectedMidpoint:
    julian_day_ut1: float
    target_mc_degrees: float


class DavisonCorrectionFacts(TypedDict, total=False):
    mc_target_tropical: float
    mc_actual_tropical: float
    mc_residual_degrees: float
    time_correction_seconds_ut1: float
    mc_target_policy: str


class DavisonPolicy(DavisonCorrectionFacts):
    method_id: str
    variant: str
    source_url: str
    source_kind: str
    positions_from_single_instant: bool
    time_policy: str
    time_source_scope: str
    geographic_policy: str
    longitude_unwrapping: str
    midpoint_jd_ut1: float
    input_julian_days_ut1: list[float]
    midpoint_longitude: float
    midpoint_latitude: float


class MarksPolicy(DavisonPolicy):
    recipe: str
    base_davison_variant: str


def unique_midpoint(first: float, second: float) -> float:
    """Unordered shorter-arc midpoint; a diametric pair has two equal answers."""
    return longitude_float(_unique_midpoint_fraction(first, second))


def _unique_midpoint_fraction(first: Angle, second: Angle) -> Fraction:
    values = midpoint_candidates_fraction(first, second)
    if len(values) != 1:
        raise ValueError("精确相隔180°的输入没有唯一短弧中点；不能任取一个方向")
    return values[0]


def midpoint_candidates_fraction(first: Angle, second: Angle) -> tuple[Fraction, ...]:
    """Retain the original midpoint formula for subsequent classifications."""
    first_degrees = angle_fraction(first) % 360
    second_degrees = angle_fraction(second) % 360
    delta = (second_degrees - first_degrees) % 360
    if delta == 180:
        axis = ((first_degrees + second_degrees) / 2) % 180
        return axis, axis + 180
    if delta > 180:
        delta -= 360
    return ((first_degrees + delta / 2) % 360,)


def _signed_longitude(value: Angle) -> float:
    result = float((Fraction(value) + 180) % 360 - 180)
    return min(result, math.nextafter(180.0, 0.0))


def geographic_midpoint(
    first_longitude: float,
    first_latitude: float,
    second_longitude: float,
    second_latitude: float,
    *,
    spherical: bool = False,
) -> tuple[float, float]:
    """Calculate a short-arc coordinate mean or midpoint on a sphere.

    Exact spherical antipodes are undefined and poles use longitude zero.
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
            _signed_longitude(
                _unique_midpoint_fraction(first_longitude, second_longitude)
            ),
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
    half_lat_diff_degrees = (Fraction(second_latitude) - Fraction(first_latitude)) / 2
    half_lat_diff = math.radians(float(half_lat_diff_degrees))
    half_lon_diff = math.radians(float(delta / 2))
    # note (precision): Take the exact complements before converting to radians near a zero cosine.
    cos_half_lon = math.sin(math.radians(float((180 - abs(delta)) / 2)))
    cos_half_lat = math.sin(math.radians(float(90 - abs(half_lat_diff_degrees))))
    x = math.cos(mean_lat) * cos_half_lat * cos_half_lon
    y = -math.sin(mean_lat) * math.sin(half_lat_diff) * math.sin(half_lon_diff)
    z = math.sin(mean_lat) * cos_half_lat
    latitude = math.degrees(math.atan2(z, math.hypot(x, y)))
    if abs(latitude) == 90:
        return 0.0, latitude
    longitude = float(Fraction(first_longitude) + delta / 2) + math.degrees(
        math.atan2(y, x)
    )
    return _signed_longitude(longitude), latitude


def _tropical_mc(ut1: float | UT1Instant, longitude: float) -> float:
    # note (midheaven): The equator avoids polar ASC errors without changing the meridian.
    _, angles = runtime.ephemeris_call("houses_ex", ut1, 0.0, longitude, b"E")
    return normalize_angle(float(angles[1]))


def _corrected_ut1(
    midpoint_julian_day_ut1: float,
    midpoint_longitude_degrees: float,
    first_birth: AstroBirthInfo,
    second_birth: AstroBirthInfo,
) -> CorrectedMidpoint:
    natal_mcs = [
        _tropical_mc(birth.time_scales.ut1, birth.longitude)
        for birth in (first_birth, second_birth)
    ]
    midpoint_axis_degrees = float(
        ((Fraction(natal_mcs[0]) + Fraction(natal_mcs[1])) / 2) % 180
    )
    candidate_mc_degrees = [midpoint_axis_degrees, midpoint_axis_degrees + 180]
    midpoint_mc_degrees = _tropical_mc(
        midpoint_julian_day_ut1, midpoint_longitude_degrees
    )
    distances_degrees = [
        abs((midpoint_mc_degrees - candidate + 180) % 360 - 180)
        for candidate in candidate_mc_degrees
    ]
    if distances_degrees[0] == distances_degrees[1]:
        raise ValueError("Davison MC轴校正有两个等距方向，无法唯一选择")
    else:
        target_mc_degrees = candidate_mc_degrees[
            distances_degrees.index(min(distances_degrees))
        ]

    def residual(julian_day_ut1: float) -> float:
        difference_degrees = normalize_angle(
            _tropical_mc(julian_day_ut1, midpoint_longitude_degrees) - target_mc_degrees
        )
        return (
            difference_degrees - 360
            if difference_degrees >= 180
            else difference_degrees
        )

    brackets: list[tuple[float, float]] = []
    window_start_julian_day_ut1 = midpoint_julian_day_ut1 - MC_SEARCH_HALF_WINDOW_DAYS
    left_julian_day_ut1 = window_start_julian_day_ut1
    left_residual_degrees = residual(left_julian_day_ut1)
    for step in range(1, MC_SEARCH_STEP_COUNT + 1):
        right_julian_day_ut1 = window_start_julian_day_ut1 + step * MC_SEARCH_STEP_DAYS
        right_residual_degrees = residual(right_julian_day_ut1)
        if (
            left_residual_degrees <= 0 <= right_residual_degrees
            and right_residual_degrees - left_residual_degrees < 90
        ):
            brackets.append((left_julian_day_ut1, right_julian_day_ut1))
        left_julian_day_ut1, left_residual_degrees = (
            right_julian_day_ut1,
            right_residual_degrees,
        )
    if not brackets:
        raise ValueError("Davison MC校正未找到有效括界")
    solutions_julian_day_ut1: list[float] = []
    for left_julian_day_ut1, right_julian_day_ut1 in brackets:
        for _ in range(MC_BISECTION_LIMIT):
            trial_julian_day_ut1 = (left_julian_day_ut1 + right_julian_day_ut1) / 2
            if trial_julian_day_ut1 in (left_julian_day_ut1, right_julian_day_ut1):
                break
            elif residual(trial_julian_day_ut1) >= 0:
                right_julian_day_ut1 = trial_julian_day_ut1
            else:
                left_julian_day_ut1 = trial_julian_day_ut1
        solutions_julian_day_ut1.append(right_julian_day_ut1)
    corrected_julian_day_ut1 = min(
        solutions_julian_day_ut1,
        key=lambda julian_day_ut1: abs(julian_day_ut1 - midpoint_julian_day_ut1),
    )
    if abs(residual(corrected_julian_day_ut1)) > MC_CORRECTION_LIMIT_DEGREES:
        raise ValueError("Davison MC校正残差超限")
    else:
        return CorrectedMidpoint(
            julian_day_ut1=corrected_julian_day_ut1, target_mc_degrees=target_mc_degrees
        )


def davison_birth(
    first: AstroBirthInfo, second: AstroBirthInfo, *, variant: str = "uncorrected"
) -> tuple[AstroBirthInfo, DavisonPolicy]:
    """Use the selected UT1 midpoint and preserve its physical epoch."""
    if variant not in DAVISON_VARIANTS:
        raise ValueError("davison_variant必须为uncorrected、corrected或spherical")
    first_time, second_time = first.time_scales, second.time_scales
    if runtime.swe is None:
        raise ValueError("Davison时间尺度换算需要Swiss Ephemeris，不能冒用UTC为UT1")
    midpoint = UT1Instant((first_time.ut1.days + second_time.ut1.days) / 2)
    longitude, latitude = geographic_midpoint(
        first.longitude,
        first.latitude,
        second.longitude,
        second.latitude,
        spherical=variant == "spherical",
    )
    mean_julian_day_ut1 = midpoint.as_float() if variant == "corrected" else None
    if mean_julian_day_ut1 is not None:
        corrected_midpoint = _corrected_ut1(
            mean_julian_day_ut1, longitude, first, second
        )
        midpoint = UT1Instant.from_float(corrected_midpoint.julian_day_ut1)
    else:
        corrected_midpoint = None
    epoch = PhysicalEpoch.from_ut1(midpoint)
    utc = epoch.require_datetime()
    correction: DavisonCorrectionFacts = {}
    if corrected_midpoint is not None:
        assert mean_julian_day_ut1 is not None
        actual_mc_degrees = _tropical_mc(epoch.time.ut1, longitude)
        target_mc_degrees = corrected_midpoint.target_mc_degrees
        residual_degrees = abs(
            (actual_mc_degrees - target_mc_degrees + 180) % 360 - 180
        )
        if residual_degrees > MC_CORRECTION_LIMIT_DEGREES:
            raise ValueError("民用时间转换后Davison MC校正残差超限")
        else:
            correction = {
                "mc_target_tropical": target_mc_degrees,
                "mc_actual_tropical": actual_mc_degrees,
                "mc_residual_degrees": residual_degrees,
                "time_correction_seconds_ut1": (
                    corrected_midpoint.julian_day_ut1 - mean_julian_day_ut1
                )
                * SECONDS_PER_DAY,
                "mc_target_policy": "nearest direction of the natal MC midpoint meridian axis",
            }
    zone = first.timezone if first.timezone == second.timezone else "UTC"
    birth = AstroBirthInfo(
        name=f"{first.name}/{second.name} 时空中点",
        birth_place=f"{first.birth_place} / {second.birth_place} 中点",
        timezone=zone,
        longitude=longitude,
        latitude=latitude,
        local_datetime=utc.astimezone(parse_timezone_name(zone)),
        utc_datetime=utc,
        native_epoch=epoch,
    )
    return birth, {
        "method_id": "davison_geometry_v2",
        "variant": variant,
        "source_url": DAVISON_SOURCE,
        "source_kind": "first_party_implementation_documentation",
        "positions_from_single_instant": True,
        "time_policy": "arithmetic mean of selected UT1 Julian days; retain solved UT1/TT and format frozen-policy civil display",
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
        "midpoint_jd_ut1": midpoint.as_float(),
        "input_julian_days_ut1": [first_time.jd_ut1, second_time.jd_ut1],
        "midpoint_longitude": longitude,
        "midpoint_latitude": latitude,
        **correction,
    }


def marks_birth(
    person: AstroBirthInfo, relationship: AstroBirthInfo, *, variant: str
) -> tuple[AstroBirthInfo, MarksPolicy]:
    """Derive a personal Marks chart from the shared Davison birth data."""
    birth, policy = davison_birth(person, relationship, variant=variant)
    return replace(birth, name=f"{person.name} 马克斯盘"), {
        **policy,
        "method_id": "marks_natal_davison_v1",
        "source_url": MARKS_SOURCE,
        "source_kind": "author_lesson_mirror_original_site_unavailable",
        "recipe": "Davison between this person's natal data and the couple's Davison data",
        "base_davison_variant": variant,
    }
