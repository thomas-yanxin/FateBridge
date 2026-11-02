"""Native ephemeris calls and explicit approximation fallback."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from fatebridge.core.astro import runtime
from fatebridge.core.astro.angle_definitions import (
    native_ecliptic_horizon_angle_definition,
)
from fatebridge.core.astro.geometry import normalize_angle
from fatebridge.core.astro.house_axes import canonical_house_axes
from fatebridge.core.astro.longitude_motion import corrected_longitude_motion
from fatebridge.core.astro.lunar_source_window import (
    coherent_lunar_native_state,
)
from fatebridge.core.astro.native_coordinates import require_spherical_coordinates
from fatebridge.core.astro.native_motion import require_longitude_speed
from fatebridge.core.astro.orbits import _planet_state, _sun_state
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.astro.profiles import (
    native_factor_model,
    physical_ephemeris_summary,
)
from fatebridge.core.astro.reference import (
    PLANET_SEQUENCE,
    PLANET_SWISSEPH_IDS,
    TRADITIONAL_PLANETS,
)
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.utils.errors import EphemerisSourceError


def _swisseph_angles(
    julian_day: float,
    longitude: float,
    latitude: float,
) -> Optional[Dict[str, Any]]:
    if runtime.swe is None:
        return None
    try:
        with runtime.preserve_ephemeris_path():
            _, ascmc = runtime.ephemeris_call(
                "houses_ex", julian_day, latitude, longitude, b"E"
            )
            ascmc, convention = canonical_house_axes(
                julian_day_ut1=julian_day,
                latitude=latitude,
                longitude=longitude,
                house_code=b"E",
                native_angles=ascmc,
            )
            definition = native_ecliptic_horizon_angle_definition(
                julian_day_ut1=julian_day, latitude=latitude, armc=float(ascmc[2])
            )
    except EphemerisSourceError:
        raise
    except Exception as error:
        runtime._log_swe_runtime_failure("houses_ex", error)
        return None
    result: Dict[str, Any] = {
        "ascendant": normalize_angle(float(ascmc[0])),
        "midheaven": normalize_angle(float(ascmc[1])),
    }
    if definition is not None:
        result["angle_definition"] = definition
    if convention is not None:
        result["house_axis_convention"] = convention
    return result


def _planet_set(chart_variant: str) -> List[str]:
    if chart_variant in {"hellen_chart", "guolao_chart"}:
        return list(TRADITIONAL_PLANETS)
    return list(PLANET_SEQUENCE)


def _swisseph_planet_state(
    planet: str,
    julian_day: Optional[float] = None,
    *,
    julian_day_tt: Optional[float] = None,
    source_trace: Optional[PhysicalEphemerisTrace] = None,
    motion_metadata: Optional[Dict[str, Any]] = None,
    correct_motion: bool = True,
) -> Optional[Tuple[Dict[str, float], str]]:
    """One coherent physical state, with optional shared batch file tracing.

    Explicit TT needs no Earth-rotation epoch. An unavailable equatorial
    position leaves declination unknown. A changed source is a consistency
    error, never an orbital approximation trigger.
    """
    if runtime.swe is None or planet not in PLANET_SWISSEPH_IDS:
        return None
    operation = "calc" if julian_day_tt is not None else "calc_ut"
    epoch = julian_day_tt if julian_day_tt is not None else julian_day
    if epoch is None or not math.isfinite(epoch):
        raise ValueError("A finite TT or UT1 Julian day is required")
    trace = source_trace if source_trace is not None else PhysicalEphemerisTrace()
    physical = planet not in {"North Node", "South Node"}
    with runtime.preserve_ephemeris_path():
        selected = configured_ephemeris_path()
        # Set the calling thread's C configuration even when a third-party
        # direct API call bypassed the managed runtime signature.
        runtime.swe.set_ephe_path(selected or "")
        try:
            coordinates, flag = runtime.ephemeris_call(
                operation,
                epoch,
                PLANET_SWISSEPH_IDS[planet],
                runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED,
            )
        except EphemerisSourceError:
            raise
        except Exception as error:
            runtime._log_swe_runtime_failure(operation, error)
            return None
        assert_physical_configuration(selected)
        if flag < 0:
            runtime._log_swe_runtime_failure(operation, RuntimeError(f"retflag={flag}"))
            return None
        model = runtime.ephemeris_model_from_retflag(flag)
        longitude_speed = require_longitude_speed(
            coordinates, flag, runtime.swe.FLG_SPEED
        )
        longitude, latitude, _ = require_spherical_coordinates(
            coordinates, flag, native=runtime.swe
        )
        if physical:
            trace.observe(planet, model)
        state = {
            "longitude": normalize_angle(longitude),
            "latitude": latitude,
            "longitude_speed": longitude_speed,
        }
        motion_tt = (
            epoch
            if operation == "calc"
            else epoch
            + float(
                runtime.ephemeris_call(
                    "deltat_ex",
                    epoch,
                    flag
                    & (
                        runtime.swe.FLG_SWIEPH
                        | runtime.swe.FLG_MOSEPH
                        | runtime.swe.FLG_JPLEPH
                    ),
                )
            )
        )
        if planet == "Moon":
            coordinates, flag, policy = coherent_lunar_native_state(
                operation,
                epoch,
                runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED,
                motion_tt,
                model,
                trace,
                initial=coordinates,
                initial_flags=flag,
            )
            speed = require_longitude_speed(coordinates, flag, runtime.swe.FLG_SPEED)
            lon, lat, _ = require_spherical_coordinates(
                coordinates, flag, native=runtime.swe
            )
            state.update(
                longitude=normalize_angle(lon), latitude=lat, longitude_speed=speed
            )
            trace.observe(planet, model)
            if motion_metadata is not None:
                motion_metadata.setdefault("lunar_source_windows", {})[
                    "tropical"
                ] = policy
        if correct_motion:
            state.update(
                corrected_longitude_motion(
                    planet,
                    motion_tt,
                    coordinates,
                    model,
                    source_trace=trace,
                    context=motion_metadata,
                )
            )
        try:
            if planet == "Moon":
                equatorial, eq_flag, eq_policy = coherent_lunar_native_state(
                    operation,
                    epoch,
                    runtime.swe.FLG_SWIEPH | runtime.swe.FLG_EQUATORIAL,
                    motion_tt,
                    model,
                    trace,
                )
                if motion_metadata is not None:
                    motion_metadata.setdefault("lunar_source_windows", {})[
                        "equatorial"
                    ] = eq_policy
            else:
                equatorial, eq_flag = runtime.ephemeris_call(
                    operation,
                    epoch,
                    PLANET_SWISSEPH_IDS[planet],
                    runtime.swe.FLG_SWIEPH | runtime.swe.FLG_EQUATORIAL,
                )
        except EphemerisSourceError:
            raise
        except Exception as error:
            runtime._log_swe_runtime_failure(operation + "(equatorial)", error)
        else:
            if eq_flag >= 0:
                if runtime.ephemeris_model_from_retflag(eq_flag) != model:
                    raise EphemerisSourceError("coordinate_model_changed")
                if physical:
                    trace.observe(planet, model)
                _, declination, _ = require_spherical_coordinates(
                    equatorial, eq_flag, native=runtime.swe, equatorial=True
                )
                state["declination"] = declination
        assert_physical_configuration(selected)
        if source_trace is None:
            trace.finish()
        return state, native_factor_model(PLANET_SWISSEPH_IDS[planet], flag)


def _build_planet_states(
    chart_variant: str,
    julian_day: float,
    day_number: float,
    *,
    julian_day_tt: Optional[float] = None,
    source_trace: Optional[PhysicalEphemerisTrace] = None,
    motion_metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Dict[str, float]], str, str, str, Dict[str, str]]:
    if configured_jpl_file() is not None and runtime.swe is None:
        raise ImportError(
            "Swiss Ephemeris is required for explicitly selected JPL mode"
        )
    planet_names = _planet_set(chart_variant)
    ephemeris_states: Dict[str, Dict[str, float]] = {}
    models: Dict[str, str] = {}
    native_count = 0
    sun_state = None
    trace = source_trace if source_trace is not None else PhysicalEphemerisTrace()
    with runtime.preserve_ephemeris_path():
        selected = configured_ephemeris_path()
        for planet in planet_names:
            result = _swisseph_planet_state(
                planet,
                julian_day,
                julian_day_tt=julian_day_tt,
                source_trace=trace,
                motion_metadata=motion_metadata,
            )
            if result is not None:
                state, model = result
                ephemeris_states[planet] = state
                models[planet] = model
                native_count += 1
            else:
                # A failed body must not discard successful native coordinates of
                # other bodies. Preserve the inherited UT-based approximation's
                # epoch convention; do not mix its solar vector with a native Sun.
                if sun_state is None:
                    sun_state = _sun_state(day_number)
                ephemeris_states[planet] = _planet_state(planet, day_number, sun_state)
                models[planet] = "fatebridge_approximate_orbital_model"
                if planet not in {"North Node", "South Node"}:
                    trace.observe(planet, models[planet])
            assert_physical_configuration(selected)
        trace.finish()

    if native_count == len(planet_names):
        return (
            ephemeris_states,
            "ephemeris_runtime_model",
            "swisseph_api",
            physical_ephemeris_summary(models),
            models,
        )
    return (
        ephemeris_states,
        (
            "mixed_precision_runtime_model"
            if native_count
            else "approximate_orbital_model"
        ),
        (
            "swisseph_api_with_approximate_orbits"
            if native_count
            else "fatebridge_approximate_orbital_model"
        ),
        physical_ephemeris_summary(models),
        models,
    )
