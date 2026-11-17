"""Physical Earth attitude and explicit reduction of native geometry inputs.

Sidereal time, houses and horizons share one pole, equinox and epoch pair.
Solar-event consumers use the dedicated physical observer and optical solver;
raw native event calls retain their source convention without a phase shim.
"""

from __future__ import annotations

import math
from fractions import Fraction
from types import ModuleType
from typing import Any, Callable, Dict, Sequence, Tuple

from fatebridge.core.astro.earth_attitude import _correction as _correction
from fatebridge.core.astro.earth_attitude import _rotation_tt as _rotation_tt
from fatebridge.core.astro.earth_attitude import (
    _standard_correction as _standard_correction,
)
from fatebridge.core.astro.earth_attitude import earth_attitude, physical_equator
from fatebridge.core.astro.earth_rotation import (
    MODERN_HALF_WINDOW_DAYS as MODERN_HALF_WINDOW_DAYS,
)
from fatebridge.core.astro.earth_rotation import (
    MODERN_REFERENCE_JD_TT as MODERN_REFERENCE_JD_TT,
)
from fatebridge.core.astro.earth_rotation import _era_turn as _era_turn
from fatebridge.core.astro.earth_rotation import (
    _fundamental_arguments as _fundamental_arguments,
)
from fatebridge.core.astro.earth_rotation import frame_gast as frame_gast
from fatebridge.core.astro.earth_rotation import iers2010_gast as iers2010_gast
from fatebridge.core.astro.earth_rotation import (
    selected_sidereal_model as selected_sidereal_model,
)
from fatebridge.core.astro.iers_ut1 import active_ut1, ut1_reference
from fatebridge.core.astro.reference_frames import rotate_spherical

POLICY_ID = "fatebridge_physical_earth_attitude_v6"
NATIVE_IERS_UT1_INTERVAL = (2396758.5, 2469807.5)


def earth_rotation_policy(
    julian_day_tt: float | None = None, julian_day_ut1: float | None = None
) -> Dict[str, Any]:
    import erfa

    extension = julian_day_tt is not None and julian_day_ut1 is not None
    value = {
        "policy_id": POLICY_ID,
        "sidereal_time_model": (
            (
                "IAU2006_2000A_CIO"
                if selected_sidereal_model(julian_day_tt) == 3
                else "Swiss_longterm_with_boundary_phase_alignment"
            )
            if extension and julian_day_tt is not None
            else (
                "Swiss_native"
                if julian_day_tt is not None
                else "not_selected_without_epoch"
            )
        ),
        "implementation": (
            "explicit_source_frame_reduction_and_physical_earth_attitude"
            if extension
            else "native_public_API"
        ),
        "model_epoch_jd_tt": julian_day_tt,
        "model_epoch_jd_ut1": julian_day_ut1,
        "modern_adoption_window_tt": {
            "reference_jd": MODERN_REFERENCE_JD_TT,
            "half_window_julian_centuries": 2.0,
        },
        "native_iers_interval_ut1": {
            "start": NATIVE_IERS_UT1_INTERVAL[0],
            "end": NATIVE_IERS_UT1_INTERVAL[1],
        },
        "native_interval_role": "Documented native switch points; not an application bypass",
        "celestial_frame_model": (
            "IAU2006_2000A"
            if julian_day_tt is not None and selected_sidereal_model(julian_day_tt) == 3
            else (
                "native_longterm_triad_with_IAU_boundary_alignment"
                if julian_day_tt is not None
                else "not_selected_without_epoch"
            )
        ),
        "celestial_frame_scope": "Physical pole and equinox; source coordinates are explicitly reduced from their own frame. Does not replace source ecliptic longitudes or dynamical ephemerides.",
        "source_equatorial_frame_model": "Swiss2.10.03_default_Vondrak_nutation2000B_native_bias",
        "origin_method": "ERFA_S06_and_equation_of_origins_from_the_same_NPB",
        "erfa_version": str(erfa.version.erfa_version),
        "selection_basis": "FateBridge near-J2000 window; longterm phase and complete equatorial triad aligned at each outer edge",
        "longterm_phase_alignment": (
            {
                "method": "constant_GAST_offset_and_native_triad_transport_from_IAU_boundary",
                "boundary_tt_jd": (
                    MODERN_REFERENCE_JD_TT
                    + (
                        -MODERN_HALF_WINDOW_DAYS
                        if julian_day_tt < MODERN_REFERENCE_JD_TT
                        else MODERN_HALF_WINDOW_DAYS
                    )
                    if julian_day_tt is not None
                    and selected_sidereal_model(julian_day_tt) == 4
                    else None
                ),
                "native_longterm_variation_retained": True,
                "absolute_accuracy_certified": False,
                "derivative_continuity_certified": False,
                "source_url": "https://www.astro.com/swisseph/swisseph.htm",
                "source_section": "6.1",
                "attribution": "FateBridge window placement and computed constants; Swiss documents the constant-offset continuity method",
            }
            if julian_day_tt is not None and selected_sidereal_model(julian_day_tt) == 4
            else None
        ),
        "nutation_model": (
            "IAU2000A_with_IAU2006_adjustments"
            if julian_day_tt is not None and selected_sidereal_model(julian_day_tt) == 3
            else (
                "native_longterm_variation_after_boundary_triad_alignment"
                if julian_day_tt is not None
                else "not_selected_without_epoch"
            )
        ),
        "tt_argument_policy": (
            (
                "selected_IERS_C04_UT1_to_TT"
                if active_ut1.get() is not None
                else "shared_default_DeltaT_minus1_before1960_SWIEPH_from1960"
            )
            if extension
            else "native_internal_sidereal_time_argument"
        ),
        "other_astronomical_models": "not_mutated_by_rotation_adapter",
        "geographic_longitude_policy": "Supplied terrestrial location retained; source-frame rays, house plane and receiver are reduced into the selected physical attitude",
        "native_event_api_scope": "Raw SDK rise_trans/true_hor retain native conventions; published solar-event consumers use the physical domain solver",
        "scope": "Managed sidereal time, houses, horizons and the two published solar-event definitions",
        "measured_eop_applied": False,
        "precision_scope": "Finite model/frame/observer/root agreement; no measured polar motion, remote absolute accuracy, derivative or all-input certification",
        "source_url": "https://iers-conventions.obspm.fr/content/chapter5/icc5.pdf",
        "origin_source_url": "https://github.com/liberfa/erfa/blob/v2.0.1/src/gst06.c",
        "frame_source_url": "https://www.iausofa.org/2023-10-11c",
        "native_frame_source_url": "https://github.com/aloistr/swisseph/blob/175e1fcb3108bcd5c0d146c803f51dcf23508012/swephlib.c",
    }
    reference = ut1_reference(julian_day_tt, julian_day_ut1)
    if reference is not None:
        value.update(
            measured_eop_applied=True,
            ut1_reference=reference,
            precision_scope="Selected final daily UT1 series with declared interpolation; polar motion, CIP offsets and subdaily tides are not applied. Formal source errors are not complete physical uncertainty; native auxiliary geometry retains its documented model limits.",
        )
    return value


def _extension(module: Any, jd_ut1: float) -> bool:
    return isinstance(module, ModuleType) and math.isfinite(jd_ut1)


def _argument(
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
    index: int,
    name: str,
    default: Any = None,
) -> Any:
    return args[index] if len(args) > index else kwargs.get(name, default)


def _changed(
    args: Tuple[Any, ...], kwargs: Dict[str, Any], index: int, name: str, value: Any
) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
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
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
    *,
    calculate: Callable[[float, int, int], tuple[Sequence[float], int]],
) -> Any:
    backend = getattr(module, operation)
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
    kwargs = options
    jd = _argument(args, kwargs, 0, "tjdut")
    if jd is None:
        return backend(*args, **kwargs)
    if operation in {"azalt", "azalt_rev"} and _extension(module, jd):
        attitude = earth_attitude(module, jd, julian_day_tt=julian_day_tt)
        geopos = _argument(args, kwargs, 2, "geopos")
        flag = _argument(args, kwargs, 1, "flag")
        delta = attitude.equator.greenwich_sidereal_degrees - module.sidtime(jd) * 15
        updated, options = _changed(
            args,
            kwargs,
            2,
            "geopos",
            (_longitude(geopos[0], delta), *geopos[1:]),
        )
        reverse = operation == "azalt_rev"
        updated, options = _changed(
            updated,
            options,
            1,
            "flag",
            module.HOR2EQU if reverse else module.EQU2HOR,
        )
        if reverse:
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
        return backend(*updated, **options)
    if operation in {"houses", "houses_ex"} and _extension(module, jd):
        attitude = earth_attitude(module, jd, julian_day_tt=julian_day_tt)
        latitude = _argument(args, kwargs, 1, "lat")
        longitude = _argument(args, kwargs, 2, "lon")
        house_code = _argument(args, kwargs, 3, "hsys", b"P")
        flags = (
            _argument(args, kwargs, 4, "flags", 0) if operation == "houses_ex" else 0
        )
        armc = (attitude.house_sidereal_degrees + longitude) % 360
        sun_declination = 0.0
        if house_code.upper() == b"I":
            from fatebridge.core.astro.native_coordinates import (
                require_spherical_coordinates,
            )

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
        return cusps, angles
    if operation == "sidtime" and _extension(module, jd):
        return (
            physical_equator(
                module, jd, julian_day_tt=julian_day_tt
            ).greenwich_sidereal_degrees
            / 15
        )
    return backend(*args, **kwargs)
