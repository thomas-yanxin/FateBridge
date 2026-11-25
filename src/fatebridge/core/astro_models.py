"""Reduce native geometry inputs using the selected physical Earth attitude.

Sidereal time, houses and horizons share one pole, equinox and epoch pair.
Solar-event consumers use the dedicated physical observer and optical solver;
raw native event calls retain their source convention without a phase shim.
"""

from __future__ import annotations

import math
from fractions import Fraction
from types import ModuleType
from typing import Any, Protocol, Sequence

from fatebridge.core.astro.earth_attitude import earth_attitude, physical_equator
from fatebridge.core.astro.native_coordinates import require_spherical_coordinates
from fatebridge.core.astro.reference_frames import dot, rotate_spherical
from fatebridge.core.astro.terrestrial_observer import house_site, terrestrial_frame
from fatebridge.core.astro.ut1_epoch import UT1Instant


class CalculateNativePosition(Protocol):
    def __call__(
        self, julian_day_tt: float, body_index: int, flags: int, /
    ) -> tuple[Sequence[float], int]: ...


def _extension(module: object, jd_ut1: float) -> bool:
    return isinstance(module, ModuleType) and math.isfinite(jd_ut1)


def _argument(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    index: int,
    name: str,
    default: Any = None,
) -> Any:
    return args[index] if len(args) > index else kwargs.get(name, default)


def _changed(
    args: tuple[Any, ...], kwargs: dict[str, Any], index: int, name: str, value: Any
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    if len(args) > index:
        result = list(args)
        result[index] = value
        return tuple(result), dict(kwargs)
    return args, {**kwargs, name: value}


def _longitude(value: float, correction: float) -> float:
    return (math.fsum((value, correction)) + 180) % 360 - 180


def native_rotation_call(
    module: Any,
    operation: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    calculate: CalculateNativePosition,
) -> Any:
    backend = getattr(module, operation)
    if operation == "house_pos" and "_sun_declination" in kwargs:
        options = dict(kwargs)
        sun_declination = options.pop("_sun_declination")
        # Swiss takes Sunshine inverse declination from its last forward frame.
        # Seed it and invert within this single managed runtime call.
        module.houses_armc(*args[:3], args[4], sun_declination)
        return backend(*args, **options)
    supported = {
        "sidtime",
        "houses",
        "houses_ex",
        "azalt",
        "azalt_rev",
    }
    if operation not in supported:
        return backend(*args, **kwargs)
    options = dict(kwargs)
    julian_day_tt = options.pop("_julian_day_tt", None)
    return_sun_declination = options.pop("_return_sun_declination", False)
    kwargs = options
    ut1 = _argument(args, kwargs, 0, "tjdut")
    if ut1 is None:
        return backend(*args, **kwargs)
    jd = ut1.as_float() if isinstance(ut1, UT1Instant) else ut1
    if isinstance(ut1, UT1Instant):
        args, kwargs = _changed(args, kwargs, 0, "tjdut", jd)
    if operation in {"azalt", "azalt_rev"} and _extension(module, jd):
        attitude = earth_attitude(module, ut1, julian_day_tt=julian_day_tt)
        geopos = _argument(args, kwargs, 2, "geopos")
        flag = _argument(args, kwargs, 1, "flag")
        reverse = operation == "azalt_rev"
        twist = 0.0
        if attitude.equator.polar_motion is None:
            delta = (
                attitude.equator.greenwich_sidereal_degrees - module.sidtime(jd) * 15
            )
            site = (_longitude(geopos[0], delta), *geopos[1:])
        else:
            frame = terrestrial_frame(
                attitude.equator, longitude=geopos[0], latitude=geopos[1]
            )
            right_ascension, declination = frame.equatorial_site()
            theta, phi = map(math.radians, (right_ascension, declination))
            native_east = (-math.sin(theta), math.cos(theta), 0.0)
            native_north = (
                -math.sin(phi) * math.cos(theta),
                -math.sin(phi) * math.sin(theta),
                math.cos(phi),
            )
            twist = math.degrees(
                math.atan2(dot(frame.east, native_north), dot(frame.east, native_east))
            )
            site = (
                _longitude(right_ascension, -module.sidtime(jd) * 15),
                declination,
                *geopos[2:],
            )
        updated, options = _changed(
            args,
            kwargs,
            2,
            "geopos",
            site,
        )
        updated, options = _changed(
            updated,
            options,
            1,
            "flag",
            module.HOR2EQU if reverse else module.EQU2HOR,
        )
        if reverse:
            if attitude.equator.polar_motion is not None:
                # The Python binding takes scalar azimuth/true_altitude,
                # unlike the original C API's internal xin[2] array.
                azimuth = _argument(args, kwargs, 3, "azimuth")
                updated, options = _changed(
                    updated, options, 3, "azimuth", (azimuth - twist) % 360
                )
            ra, dec = backend(*updated, **options)
            longitude, latitude = ra, dec
            matrix = (
                attitude.reduction.target_to_ecliptic
                if flag == module.HOR2ECL
                else attitude.reduction.target_to_native
            )
        else:
            coordinates = _argument(args, kwargs, 5, "xin")
            longitude, latitude = coordinates[:2]
            matrix = (
                attitude.reduction.ecliptic_to_target
                if flag == module.ECL2HOR
                else attitude.reduction.native_to_target
            )
        result = rotate_spherical(matrix, longitude, latitude)
        if reverse:
            return result
        updated, options = _changed(
            updated, options, 5, "xin", (*result, coordinates[2])
        )
        horizontal = backend(*updated, **options)
        if attitude.equator.polar_motion is not None:
            return ((horizontal[0] + twist) % 360, *horizontal[1:])
        return horizontal
    if operation in {"houses", "houses_ex"} and _extension(module, jd):
        attitude = earth_attitude(module, ut1, julian_day_tt=julian_day_tt)
        latitude = _argument(args, kwargs, 1, "lat")
        longitude = _argument(args, kwargs, 2, "lon")
        house_code = _argument(args, kwargs, 3, "hsys", b"P")
        flags = (
            _argument(args, kwargs, 4, "flags", 0) if operation == "houses_ex" else 0
        )
        armc, latitude = house_site(attitude, longitude=longitude, latitude=latitude)
        sun_declination = 0.0
        if house_code.upper() == b"I":

            sun, returned = calculate(
                attitude.equator.jd_tt,
                module.SUN,
                module.FLG_SWIEPH | module.FLG_EQUATORIAL,
            )
            ra, dec, _ = require_spherical_coordinates(
                sun, returned, native=module, equatorial=True
            )
            _, sun_declination = rotate_spherical(
                attitude.reduction.native_to_target, ra, dec
            )
        cusp_values, angle_values = module.houses_armc(
            armc,
            latitude,
            attitude.reduction.house_obliquity,
            b"E" if house_code.upper() == b"W" else house_code,
            sun_declination,
        )
        origin = Fraction(attitude.reduction.house_longitude_origin)
        if flags & module.FLG_SIDEREAL:
            returned, ayanamsha = module.get_ayanamsa_ex(attitude.equator.jd_tt, flags)
            if returned < 0:
                raise ValueError("Sidereal house origin is unavailable")
            origin -= Fraction(ayanamsha)
        cusps = tuple(
            float((Fraction(value) + origin) % 360) % 360 for value in cusp_values
        )
        angles = tuple(
            value if index == 2 else float((Fraction(value) + origin) % 360) % 360
            for index, value in enumerate(angle_values)
        )
        if house_code.upper() == b"W":
            start = math.floor(angles[0] / 30) * 30
            cusps = tuple(float((start + index * 30) % 360) for index in range(12))
        elif house_code.upper() == b"N":
            cusps = tuple(index * 30.0 for index in range(12))
        if flags & module.FLG_RADIANS:
            cusps = tuple(map(math.radians, cusps))
            angles = tuple(map(math.radians, angles))
        if return_sun_declination:
            return cusps, angles, sun_declination
        return cusps, angles
    if operation == "sidtime" and _extension(module, jd):
        return (
            physical_equator(
                module, ut1, julian_day_tt=julian_day_tt
            ).greenwich_sidereal_degrees
            / 15
        )
    return backend(*args, **kwargs)
