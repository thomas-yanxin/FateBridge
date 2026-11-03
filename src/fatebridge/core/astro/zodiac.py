"""Native Lahiri projection, keeping physical and zodiac coordinates separate.

Swiss Ephemeris 12.2 recommends FLG_SIDEREAL for positions; subtracting a
mean ayanamsha from apparent tropical positions leaves nutation unremoved.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fatebridge.core.astro import runtime
from fatebridge.core.astro.angle_definitions import (
    native_ecliptic_horizon_angle_definition,
)
from fatebridge.core.astro.geometry import normalize_angle
from fatebridge.core.astro.house_axes import canonical_house_geometry
from fatebridge.core.astro.longitude_motion import (
    LunarAdjustment,
    corrected_longitude_motion,
)
from fatebridge.core.astro.lunar_source_window import (
    coherent_lunar_native_state,
)
from fatebridge.core.astro.native_coordinates import require_spherical_coordinates
from fatebridge.core.astro.native_motion import require_longitude_speed
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS


def native_lahiri_positions(
    planets: List[str],
    *,
    julian_day_ut1: float,
    julian_day_tt: Optional[float],
    lunar_adjustments: Optional[Dict[str, LunarAdjustment]] = None,
    motion_metadata: Optional[Dict[str, Any]] = None,
    source_trace: Optional[PhysicalEphemerisTrace] = None,
) -> Dict[str, Dict[str, float]]:
    """Native zodiac coordinates/speeds; physical states remain for horizon."""
    if runtime.swe is None:
        raise ValueError("原生Lahiri黄道转换需要Swiss Ephemeris")
    operation = "calc" if julian_day_tt is not None else "calc_ut"
    instant = julian_day_tt if julian_day_tt is not None else julian_day_ut1
    result: Dict[str, Dict[str, float]] = {}
    trace = source_trace if source_trace is not None else PhysicalEphemerisTrace()
    with runtime.preserve_ephemeris_path():
        runtime.swe.set_sid_mode(runtime.swe.SIDM_LAHIRI, 0, 0)
        for planet in planets:
            coordinates, flags = runtime.ephemeris_call(
                operation,
                instant,
                PLANET_SWISSEPH_IDS[planet],
                runtime.swe.FLG_SWIEPH
                | runtime.swe.FLG_SPEED
                | runtime.swe.FLG_SIDEREAL,
            )
            longitude_speed = require_longitude_speed(
                coordinates, flags, runtime.swe.FLG_SPEED
            )
            longitude, latitude, _ = require_spherical_coordinates(
                coordinates, flags, native=runtime.swe, sidereal=True
            )
            result[planet] = {
                "longitude": normalize_angle(longitude),
                "latitude": latitude,
                "longitude_speed": longitude_speed,
            }
            motion_tt = (
                julian_day_tt
                if julian_day_tt is not None
                else julian_day_ut1
                + float(
                    runtime.ephemeris_call(
                        "deltat_ex",
                        julian_day_ut1,
                        flags
                        & (
                            runtime.swe.FLG_SWIEPH
                            | runtime.swe.FLG_MOSEPH
                            | runtime.swe.FLG_JPLEPH
                        ),
                    )
                )
            )
            if planet == "Moon":
                model = runtime.ephemeris_model_from_retflag(flags)
                coordinates, flags, policy = coherent_lunar_native_state(
                    operation,
                    instant,
                    runtime.swe.FLG_SWIEPH
                    | runtime.swe.FLG_SPEED
                    | runtime.swe.FLG_SIDEREAL,
                    motion_tt,
                    model,
                    trace,
                    initial=coordinates,
                    initial_flags=flags,
                )
                speed = require_longitude_speed(
                    coordinates, flags, runtime.swe.FLG_SPEED
                )
                lon, lat, _ = require_spherical_coordinates(
                    coordinates, flags, native=runtime.swe, sidereal=True
                )
                result[planet].update(
                    longitude=normalize_angle(lon), latitude=lat, longitude_speed=speed
                )
                if motion_metadata is not None:
                    motion_metadata.setdefault("lunar_source_windows", {})[
                        "lahiri"
                    ] = policy
            result[planet].update(
                corrected_longitude_motion(
                    planet,
                    motion_tt,
                    coordinates,
                    runtime.ephemeris_model_from_retflag(flags),
                    sidereal=True,
                    context=motion_metadata,
                    source_trace=trace,
                    lunar_adjustment=(lunar_adjustments or {}).get(planet),
                )
            )
        if source_trace is None:
            trace.finish()
    return result


def native_lahiri_houses(
    *,
    julian_day_ut1: float,
    julian_day_tt: Optional[float],
    latitude: float,
    longitude: float,
    house_code: bytes,
) -> Dict[str, Any]:
    """Native sidereal cusps/angles and separately labelled true/mean offsets."""
    if runtime.swe is None:
        raise ValueError("原生Lahiri宫头计算需要Swiss Ephemeris")
    operation = "get_ayanamsa_ex" if julian_day_tt is not None else "get_ayanamsa_ex_ut"
    instant = julian_day_tt if julian_day_tt is not None else julian_day_ut1
    with runtime.preserve_ephemeris_path():
        runtime.swe.set_sid_mode(runtime.swe.SIDM_LAHIRI, 0, 0)
        cusps, angles = runtime.ephemeris_call(
            "houses_ex",
            julian_day_ut1,
            latitude,
            longitude,
            house_code,
            runtime.swe.FLG_SIDEREAL,
        )
        cusps, angles, house_axis_convention = canonical_house_geometry(
            julian_day_ut1=julian_day_ut1,
            latitude=latitude,
            longitude=longitude,
            house_code=house_code,
            native_angles=angles,
            native_cusps=cusps,
            flags=runtime.swe.FLG_SIDEREAL,
        )
        flags, apparent_offset = runtime.ephemeris_call(
            operation, instant, runtime.swe.FLG_SWIEPH
        )
        mean_flags, mean_offset = runtime.ephemeris_call(
            operation, instant, runtime.swe.FLG_SWIEPH | runtime.swe.FLG_NONUT
        )
        if flags < 0 or mean_flags < 0:
            raise ValueError("Lahiri偏移计算失败")
        definition = native_ecliptic_horizon_angle_definition(
            julian_day_ut1=julian_day_ut1, latitude=latitude, armc=float(angles[2])
        )
    return {
        "ascendant": normalize_angle(float(angles[0])),
        "midheaven": normalize_angle(float(angles[1])),
        "house_cusps": [normalize_angle(float(c)) for c in cusps[:12]],
        "ayanamsha": float(apparent_offset),
        "ayanamsha_mean": float(mean_offset),
        "ayanamsha_includes_nutation": True,
        "sidereal_house_method": "swisseph_houses_ex_sidereal_lahiri",
        "angle_method": "swisseph",
        **(
            {"house_axis_convention": house_axis_convention}
            if house_axis_convention
            else {}
        ),
        **({"angle_definition": definition} if definition is not None else {}),
    }
