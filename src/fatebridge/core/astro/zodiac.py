"""Native Lahiri projection, keeping physical and zodiac coordinates separate.

Swiss Ephemeris 12.2 recommends FLG_SIDEREAL for positions; subtracting a
mean ayanamsha from apparent tropical positions leaves nutation unremoved.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.angle_definitions import (
    native_ecliptic_horizon_angle_definition,
)
from fatebridge.core.astro.ephemeris import (
    _resolve_swe_body_id,
    _swisseph_planet_state,
    fast_swe_call,
)
from fatebridge.core.astro.geometry import normalize_angle
from fatebridge.core.astro.house_axes import canonical_house_geometry
from fatebridge.core.astro.native_coordinates import require_spherical_coordinates
from fatebridge.core.astro.native_motion import require_longitude_speed
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant


def native_lahiri_positions(
    planets: list[str],
    *,
    julian_day_ut1: float,
    julian_day_tt: float | TTInstant | None,
    lunar_adjustments: dict[str, Any] | None = None,
    motion_metadata: dict[str, Any] | None = None,
    source_trace: PhysicalEphemerisTrace | None = None,
    node_mode: str = "mean",
) -> dict[str, dict[str, float]]:
    """Native zodiac coordinates/speeds; physical states remain for horizon."""
    del lunar_adjustments, motion_metadata
    if runtime.swe is None:
        raise ValueError("原生Lahiri黄道转换需要Swiss Ephemeris")
    operation = "calc" if julian_day_tt is not None else "calc_ut"
    instant = (
        TTInstant.from_value(julian_day_tt).as_float()
        if julian_day_tt is not None
        else julian_day_ut1
    )
    result: dict[str, dict[str, float]] = {}
    trace = source_trace if source_trace is not None else PhysicalEphemerisTrace()
    with runtime.preserve_ephemeris_path():
        runtime.swe.set_sid_mode(runtime.swe.SIDM_LAHIRI, 0, 0)
        for planet in planets:
            if planet == "South Node":
                north = result.get("North Node")
                if north is None:
                    n_id = _resolve_swe_body_id("North Node", node_mode=node_mode)
                    assert n_id is not None
                    coords, flags = fast_swe_call(
                        operation,
                        instant,
                        n_id,
                        runtime.swe.FLG_SWIEPH
                        | runtime.swe.FLG_SPEED
                        | runtime.swe.FLG_SIDEREAL,
                    )
                    spd = require_longitude_speed(coords, flags, runtime.swe.FLG_SPEED)
                    lon, lat, _ = require_spherical_coordinates(
                        coords, flags, native=runtime.swe, sidereal=True
                    )
                    north = {
                        "longitude": normalize_angle(lon),
                        "latitude": lat,
                        "longitude_speed": spd,
                    }
                result[planet] = {
                    "longitude": normalize_angle(north["longitude"] + 180.0),
                    "latitude": -float(north["latitude"]),
                    "longitude_speed": float(north["longitude_speed"]),
                }
                continue
            body_id = _resolve_swe_body_id(planet, node_mode=node_mode)
            if body_id is None:
                continue
            coordinates, flags = fast_swe_call(
                operation,
                instant,
                body_id,
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
        if source_trace is None:
            trace.finish()
    return result


def native_lahiri_houses(
    *,
    julian_day_ut1: float | UT1Instant,
    julian_day_tt: float | TTInstant | None,
    latitude: float,
    longitude: float,
    house_code: bytes,
) -> dict[str, Any]:
    """Native sidereal cusps/angles and separately labelled true/mean offsets."""
    if runtime.swe is None:
        raise ValueError("原生Lahiri宫头计算需要Swiss Ephemeris")
    operation = "get_ayanamsa_ex" if julian_day_tt is not None else "get_ayanamsa_ex_ut"
    instant = (
        TTInstant.from_value(julian_day_tt).as_float()
        if julian_day_tt is not None
        else UT1Instant.from_value(julian_day_ut1).as_float()
    )
    with runtime.preserve_ephemeris_path():
        runtime.swe.set_sid_mode(runtime.swe.SIDM_LAHIRI, 0, 0)
        cusps, angles = runtime.ephemeris_call(
            "houses_ex",
            julian_day_ut1,
            latitude,
            longitude,
            house_code,
            runtime.swe.FLG_SIDEREAL,
            _julian_day_tt=julian_day_tt,
        )
        cusps, angles, house_axis_convention = canonical_house_geometry(
            julian_day_ut1=julian_day_ut1,
            julian_day_tt=julian_day_tt,
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
            julian_day_ut1=julian_day_ut1,
            julian_day_tt=julian_day_tt,
            latitude=latitude,
            longitude=longitude,
            armc=float(angles[2]),
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
