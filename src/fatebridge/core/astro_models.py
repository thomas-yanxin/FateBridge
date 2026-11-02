"""Portable extension of Swiss's near-J2000 Earth-rotation convention.

Use IERS 2010 in the adopted near-J2000 window. Outside it retain Swiss's
long-term variation with a constant phase alignment at the corresponding edge,
as Swiss itself aligns its long-term/standard functions at its native edges.
LST = GAST + longitude: rotating native-frame longitude by the GAST difference
retains native house/refraction/parallax rules and the supplied real location.
No private C ABI or astronomical-model mutation is required.
"""

from __future__ import annotations

import math
from types import ModuleType
from typing import Any, Dict, Tuple

from fatebridge.core.astro.iers_ut1 import active_ut1, ut1_reference
from fatebridge.core.iers2010_series import EECT_TERMS

POLICY_ID = "fatebridge_standard_rotation_v3"
MODERN_REFERENCE_JD_TT = 2451545.0
MODERN_HALF_WINDOW_DAYS = 2 * 36525.0
NATIVE_IERS_UT1_INTERVAL = (2396758.5, 2469807.5)


def selected_sidereal_model(julian_day_tt: float) -> int:
    if not math.isfinite(julian_day_tt):
        raise ValueError("Rotation model epoch must be finite")
    return (
        3
        if abs(julian_day_tt - MODERN_REFERENCE_JD_TT) <= MODERN_HALF_WINDOW_DAYS
        else 4
    )


def earth_rotation_policy(
    julian_day_tt: float | None = None, julian_day_ut1: float | None = None
) -> Dict[str, Any]:
    extension = (
        julian_day_tt is not None
        and julian_day_ut1 is not None
        and (
            active_ut1.get() is not None
            or not NATIVE_IERS_UT1_INTERVAL[0]
            < julian_day_ut1
            < NATIVE_IERS_UT1_INTERVAL[1]
        )
    )
    value = {
        "policy_id": POLICY_ID,
        "sidereal_time_model": (
            (
                "IERS2010_expression_Swiss_nutation"
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
            "public_native_geometry_with_longitude_frame_rotation"
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
        "selection_basis": "FateBridge near-J2000 window; longterm variation phase-matched at each outer edge",
        "longterm_phase_alignment": (
            {
                "method": "constant_standard_minus_native_at_corresponding_TT_window_edge",
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
        "nutation_model": "current_Swiss_nutation_and_mean_obliquity",
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
        "geographic_longitude_policy": "native-frame longitude = supplied longitude + desired GAST - native GAST; supplied location unchanged",
        "scope": "Managed sidereal-time, house, horizon and solar-event operations",
        "measured_eop_applied": False,
        "precision_scope": "Model agreement and phase continuity; no remote absolute accuracy or derivative certification",
        "source_url": "https://iers-conventions.obspm.fr/content/chapter5/additional_info/tab5.2e.txt",
    }
    reference = ut1_reference(julian_day_tt, julian_day_ut1)
    if reference is not None:
        value.update(
            measured_eop_applied=True,
            ut1_reference=reference,
            precision_scope="Selected final daily UT1 series with declared interpolation; polar motion, CIP offsets and subdaily tides are not applied. Formal source errors are not complete physical uncertainty; native auxiliary geometry retains its documented model limits.",
        )
    return value


_LUNAR = (
    (485868.249036, 1717915923.2178, 31.8792, 0.051635, -0.00024470),
    (1287104.793048, 129596581.0481, -0.5532, 0.000136, -0.00001149),
    (335779.526232, 1739527262.8478, -12.7512, -0.001037, 0.00000417),
    (1072260.703692, 1602961601.2090, -6.3706, 0.006593, -0.00003169),
    (450160.398036, -6962890.5431, 7.4722, 0.007702, -0.00005939),
)


def _fundamental_arguments(t: float) -> Tuple[float, ...]:
    values = []
    for coefficients in _LUNAR:
        value = 0.0
        for coefficient in reversed(coefficients):
            value = value * t + coefficient
        values.append(math.radians((value % 1296000.0) / 3600))
    values.extend(
        (
            (3.176146697 + 1021.3285546211 * t) % math.tau,
            (1.753470314 + 628.3075849991 * t) % math.tau,
            (0.024381750 + 0.00000538691 * t) * t,
        )
    )
    return tuple(values)


def iers2010_gast(
    jd_ut1: float, jd_tt: float, nutation_longitude: float, mean_obliquity: float
) -> float:
    """IERS Table 5.2e; degrees, UT1 for ERA and TT for polynomial/series."""
    if not all(
        math.isfinite(x) for x in (jd_ut1, jd_tt, nutation_longitude, mean_obliquity)
    ):
        raise ValueError("Rotation inputs must be finite")
    days = jd_ut1 - MODERN_REFERENCE_JD_TT
    era = 360 * (
        math.fsum((0.7790572732640, days % 1.0, 0.00273781191135448 * days)) % 1.0
    )
    t = (jd_tt - MODERN_REFERENCE_JD_TT) / 36525
    polynomial = 0.014506 + t * (
        4612.156534
        + t * (1.3915817 + t * (-0.00000044 + t * (-0.000029956 + t * (-0.0000000368))))
    )
    arguments = _fundamental_arguments(t)
    series = math.fsum(
        (
            sine * math.sin(math.fsum(m * a for m, a in zip(multipliers, arguments)))
            + cosine
            * math.cos(math.fsum(m * a for m, a in zip(multipliers, arguments)))
        )
        * (t**power)
        for power, sine, cosine, multipliers in EECT_TERMS
    )
    return (
        era
        + polynomial / 3600
        + nutation_longitude * math.cos(math.radians(mean_obliquity))
        + series / 3_600_000_000
    ) % 360


def _extension(module: Any, jd_ut1: float) -> bool:
    if not isinstance(module, ModuleType) or not math.isfinite(jd_ut1):
        return False
    if active_ut1.get() is not None:
        return True
    if NATIVE_IERS_UT1_INTERVAL[0] < jd_ut1 < NATIVE_IERS_UT1_INTERVAL[1]:
        return False
    return True


def _rotation_tt(module: Any, jd_ut1: float) -> float:
    # Import at call time: the native runtime imports this rotation adapter
    # while time_scales itself depends on that runtime.
    from fatebridge.core.astro.utc_policy import default_delta_t_flag

    selected = active_ut1.get()
    return (
        selected.tt_from_ut1(jd_ut1)
        if selected is not None
        else jd_ut1
        + module.deltat_ex(jd_ut1, default_delta_t_flag(jd_ut1, module.FLG_SWIEPH))
    )


def _standard_correction(module: Any, jd_ut1: float) -> float:
    jd_tt = _rotation_tt(module, jd_ut1)
    coordinates, flag = module.calc(jd_tt, module.ECL_NUT, module.FLG_SWIEPH)
    if flag < 0:
        raise ValueError("Nutation/obliquity unavailable for standard rotation")
    desired = iers2010_gast(jd_ut1, jd_tt, coordinates[2], coordinates[1])
    native = module.sidtime(jd_ut1) * 15
    return float((desired - native + 180) % 360 - 180)


def _correction(module: Any, jd_ut1: float) -> float:
    from fatebridge.core.astro.utc_policy import default_delta_t_flag

    jd_tt = _rotation_tt(module, jd_ut1)
    if selected_sidereal_model(jd_tt) == 3:
        return _standard_correction(module, jd_ut1)
    # Do not extrapolate the near-J2000 polynomial into remote epochs or blend
    # its derivative into the long-term theory. Match only the phase at the
    # corresponding fixed boundary; the native long-term variation is retained.
    boundary_tt = MODERN_REFERENCE_JD_TT + (
        -MODERN_HALF_WINDOW_DAYS
        if jd_tt < MODERN_REFERENCE_JD_TT
        else MODERN_HALF_WINDOW_DAYS
    )
    boundary_ut1 = boundary_tt
    for _ in range(5):
        boundary_ut1 = boundary_tt - module.deltat_ex(
            boundary_ut1, default_delta_t_flag(boundary_ut1, module.FLG_SWIEPH)
        )
    return _standard_correction(module, boundary_ut1)


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
    module: Any, operation: str, args: Tuple[Any, ...], kwargs: Dict[str, Any]
) -> Any:
    backend = getattr(module, operation)
    supported = {
        "sidtime",
        "houses",
        "houses_ex",
        "azalt",
        "azalt_rev",
        "rise_trans",
        "rise_trans_true_hor",
    }
    if operation not in supported:
        return backend(*args, **kwargs)
    jd = _argument(args, kwargs, 0, "tjdut")
    if jd is None:
        return backend(*args, **kwargs)
    rise = operation in {"rise_trans", "rise_trans_true_hor"}
    if not _extension(module, jd):
        result = backend(*args, **kwargs)
        # A search can start in the native IERS interval and return an event
        # across its 2050 transition. Decide using that returned event too.
        if not rise or result[0] < 0 or not _extension(module, float(result[1][0])):
            return result
        delta = _correction(module, float(result[1][0]))
    else:
        delta = _correction(module, jd)
    if operation == "sidtime":
        return (module.sidtime(jd) * 15 + delta) % 360 / 15
    if operation in {"houses", "houses_ex"}:
        longitude = _argument(args, kwargs, 2, "lon")
        updated, options = _changed(
            args, kwargs, 2, "lon", _longitude(longitude, delta)
        )
        return backend(*updated, **options)
    if operation in {"azalt", "azalt_rev"}:
        geopos = _argument(args, kwargs, 2, "geopos")
        updated, options = _changed(
            args, kwargs, 2, "geopos", (_longitude(geopos[0], delta), *geopos[1:])
        )
        return backend(*updated, **options)
    geopos = _argument(args, kwargs, 3, "geopos")
    rsmi = _argument(args, kwargs, 2, "rsmi", 0)
    previous = None
    try:
        # Refine the rotation phase at the returned event, not the query epoch.
        for _ in range(6):
            updated, options = _changed(
                args, kwargs, 3, "geopos", (_longitude(geopos[0], delta), *geopos[1:])
            )
            result = backend(*updated, **options)
            if result[0] < 0:
                return result
            event = float(result[1][0])
            refined = _correction(module, event)
            if event == previous or abs(refined - delta) <= 1e-10:
                return result
            previous = event
            delta = refined
        raise RuntimeError("Standard-rotation event correction did not converge")
    finally:
        geocentric = module.BIT_HINDU_RISING & ~(
            module.BIT_DISC_CENTER | module.BIT_NO_REFRACTION
        )
        if not rsmi & geocentric:
            module.set_topo(*geopos)
