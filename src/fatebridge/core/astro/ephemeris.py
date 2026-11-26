"""Native ephemeris calls and explicit approximation fallback."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.angle_definitions import (
    native_ecliptic_horizon_angle_definition,
)
from fatebridge.core.astro.geometry import normalize_angle
from fatebridge.core.astro.house_axes import canonical_house_axes
from fatebridge.core.astro.iers_ut1 import active_ut1
from fatebridge.core.astro.native_coordinates import require_spherical_coordinates
from fatebridge.core.astro.native_motion import require_longitude_speed
from fatebridge.core.astro.orbits import (
    MEAN_NODE_MODEL,
    ORBITAL_MODEL,
    ApproximateEphemeris,
)
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.astro.profiles import (
    native_factor_model,
    physical_ephemeris_summary,
)
from fatebridge.core.astro.reference import (
    EXTRA_BODY_SWISSEPH_IDS,
    NODE_BODIES,
    PLANET_SEQUENCE,
    PLANET_SWISSEPH_IDS,
    TRADITIONAL_PLANETS,
)
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.core.ephemeris_runtime import (
    EPHEMERIS_LOCK,
    _ensure_thread_ephemeris_path,
    configured_ephemeris_path,
)
from fatebridge.core.ephemeris_runtime import ephemeris_call as _ORIG_EPHEMERIS_CALL
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.utils.errors import EphemerisSourceError


def fast_swe_call(operation: str, *args: Any, **kwargs: Any) -> Any:
    """Invoke Swiss Ephemeris directly under EPHEMERIS_LOCK unless mocked, IERS UT1, or JPL."""
    if (
        runtime.ephemeris_call is _ORIG_EPHEMERIS_CALL
        and configured_jpl_file() is None
        and active_ut1.get() is None
        and runtime.swe is not None
    ):
        with EPHEMERIS_LOCK:
            _ensure_thread_ephemeris_path()
            clean_args = tuple(
                arg.as_float() if hasattr(arg, "as_float") else arg for arg in args
            )
            clean_kwargs = {k: v for k, v in kwargs.items() if not k.startswith("_")}
            return getattr(runtime.swe, operation)(*clean_args, **clean_kwargs)
    return runtime.ephemeris_call(operation, *args, **kwargs)


def _swisseph_angles(
    julian_day: float | UT1Instant,
    longitude: float,
    latitude: float,
    *,
    julian_day_tt: float | TTInstant | None = None,
) -> dict[str, Any] | None:
    if runtime.swe is None:
        return None
    try:
        with runtime.preserve_ephemeris_path():
            _, ascmc = runtime.ephemeris_call(
                "houses_ex",
                julian_day,
                latitude,
                longitude,
                b"E",
                _julian_day_tt=julian_day_tt,
            )
    except EphemerisSourceError:
        raise
    except runtime.native_ephemeris_errors() as error:
        runtime._log_swe_runtime_failure("houses_ex", error)
        return None
    with runtime.preserve_ephemeris_path():
        ascmc, convention = canonical_house_axes(
            julian_day_ut1=julian_day,
            julian_day_tt=julian_day_tt,
            latitude=latitude,
            longitude=longitude,
            house_code=b"E",
            native_angles=ascmc,
        )
        definition = native_ecliptic_horizon_angle_definition(
            julian_day_ut1=julian_day,
            julian_day_tt=julian_day_tt,
            latitude=latitude,
            longitude=longitude,
            armc=float(ascmc[2]),
        )
    result: dict[str, Any] = {
        "ascendant": normalize_angle(float(ascmc[0])),
        "midheaven": normalize_angle(float(ascmc[1])),
    }
    if definition is not None:
        result["angle_definition"] = definition
    if convention is not None:
        result["house_axis_convention"] = convention
    return result


def _planet_set(
    chart_variant: str, extra_bodies: tuple[str, ...] | list[str] = ()
) -> list[str]:
    base = (
        list(TRADITIONAL_PLANETS)
        if chart_variant in {"hellen_chart", "guolao_chart"}
        else list(PLANET_SEQUENCE)
    )
    if extra_bodies:
        seen = set(base)
        for body in extra_bodies:
            if body not in seen and (
                body in PLANET_SWISSEPH_IDS
                or body in EXTRA_BODY_SWISSEPH_IDS
                or body == "South Node"
            ):
                base.append(body)
                seen.add(body)
    return base


def _resolve_swe_body_id(planet: str, *, node_mode: str = "mean") -> int | None:
    if runtime.swe is None:
        return None
    if planet == "North Node":
        return int(
            runtime.swe.TRUE_NODE if node_mode == "true" else runtime.swe.MEAN_NODE
        )
    if planet in PLANET_SWISSEPH_IDS:
        return int(PLANET_SWISSEPH_IDS[planet])
    if planet in EXTRA_BODY_SWISSEPH_IDS:
        return int(EXTRA_BODY_SWISSEPH_IDS[planet])
    return None


def _swisseph_planet_state(
    planet: str,
    julian_day: float | None = None,
    *,
    julian_day_tt: float | TTInstant | None = None,
    source_trace: PhysicalEphemerisTrace | None = None,
    motion_metadata: dict[str, Any] | None = None,
    correct_motion: bool = True,
    include_declination: bool = True,
    node_mode: str = "mean",
) -> tuple[dict[str, float], str] | None:
    """One coherent physical state, with optional shared batch file tracing."""
    del motion_metadata, correct_motion  # Instantaneous FLG_SPEED is used directly.
    if runtime.swe is None:
        return None
    if planet == "South Node":
        north = _swisseph_planet_state(
            "North Node",
            julian_day,
            julian_day_tt=julian_day_tt,
            source_trace=source_trace,
            include_declination=include_declination,
            node_mode=node_mode,
        )
        if north is None:
            return None
        north_state, model = north
        south_state: dict[str, float] = {
            "longitude": normalize_angle(north_state["longitude"] + 180.0),
            "latitude": -float(north_state["latitude"]),
            "longitude_speed": float(north_state["longitude_speed"]),
        }
        if "declination" in north_state:
            south_state["declination"] = -float(north_state["declination"])
        return south_state, model

    body_id = _resolve_swe_body_id(planet, node_mode=node_mode)
    if body_id is None:
        return None
    operation = "calc" if julian_day_tt is not None else "calc_ut"
    epoch = (
        TTInstant.from_value(julian_day_tt).as_float()
        if julian_day_tt is not None
        else julian_day
    )
    if epoch is None or not math.isfinite(epoch):
        raise ValueError("A finite TT or UT1 Julian day is required")
    trace = source_trace if source_trace is not None else PhysicalEphemerisTrace()
    physical = planet not in NODE_BODIES and planet != "True Node"
    selected = configured_ephemeris_path()
    try:
        coordinates, flag = fast_swe_call(
            operation,
            epoch,
            body_id,
            runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED,
        )
    except EphemerisSourceError:
        raise
    except runtime.native_ephemeris_errors() as error:
        runtime._log_swe_runtime_failure(operation, error)
        return None
    assert_physical_configuration(selected)
    if flag < 0:
        runtime._log_swe_runtime_failure(operation, RuntimeError(f"retflag={flag}"))
        return None
    model = runtime.ephemeris_model_from_retflag(flag)
    longitude_speed = require_longitude_speed(coordinates, flag, runtime.swe.FLG_SPEED)
    longitude, latitude, _ = require_spherical_coordinates(
        coordinates, flag, native=runtime.swe
    )
    if physical:
        trace.observe(planet, model)
    state: dict[str, float] = {
        "longitude": normalize_angle(longitude),
        "latitude": latitude,
        "longitude_speed": longitude_speed,
    }
    if include_declination:
        try:
            equatorial, eq_flag = fast_swe_call(
                operation,
                epoch,
                body_id,
                runtime.swe.FLG_SWIEPH | runtime.swe.FLG_EQUATORIAL,
            )
        except EphemerisSourceError:
            raise
        except runtime.native_ephemeris_errors() as error:
            runtime._log_swe_runtime_failure(operation + "(equatorial)", error)
        else:
            if eq_flag >= 0:
                if physical:
                    trace.observe(planet, runtime.ephemeris_model_from_retflag(eq_flag))
                _, declination, _ = require_spherical_coordinates(
                    equatorial, eq_flag, native=runtime.swe, equatorial=True
                )
                state["declination"] = declination
    assert_physical_configuration(selected)
    if source_trace is None:
        trace.finish()
    return state, native_factor_model(body_id, flag)


@dataclass(frozen=True)
class PlanetStateBatch:
    states: dict[str, dict[str, float]]
    precision: str
    backend: str
    physical_model: str
    models: dict[str, str]
    fallback: ApproximateEphemeris | None


def _build_planet_states(
    chart_variant: str,
    julian_day: float,
    *,
    julian_day_tt: float | TTInstant | None = None,
    source_trace: PhysicalEphemerisTrace | None = None,
    motion_metadata: dict[str, Any] | None = None,
    node_mode: str = "mean",
    extra_bodies: tuple[str, ...] | list[str] = (),
    include_declination: bool = True,
) -> PlanetStateBatch:
    """Build one batch; a caller-supplied trace keeps its outer endpoint owner."""
    if configured_jpl_file() is not None and runtime.swe is None:
        raise ModuleNotFoundError(
            "Swiss Ephemeris is required for explicitly selected JPL mode"
        )
    planet_names = _planet_set(chart_variant, extra_bodies=extra_bodies)
    ephemeris_states: dict[str, dict[str, float]] = {}
    models: dict[str, str] = {}
    native_count = 0
    fallback = None
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
                include_declination=include_declination,
                node_mode=node_mode,
            )
            if result is not None:
                state, model = result
                ephemeris_states[planet] = state
                models[planet] = model
                native_count += 1
            elif planet not in EXTRA_BODY_SWISSEPH_IDS:
                if fallback is None:
                    fallback = ApproximateEphemeris(julian_day, julian_day_tt)
                if planet == "South Node":
                    north = fallback.state("North Node")
                    ephemeris_states[planet] = {
                        "longitude": normalize_angle(north["longitude"] + 180.0),
                        "latitude": -float(north["latitude"]),
                        "longitude_speed": float(north["longitude_speed"]),
                    }
                    models[planet] = MEAN_NODE_MODEL
                else:
                    ephemeris_states[planet] = fallback.state(planet)
                    models[planet] = (
                        MEAN_NODE_MODEL if planet == "North Node" else ORBITAL_MODEL
                    )
                    trace.observe(planet, models[planet])
            assert_physical_configuration(selected)
        if source_trace is None:
            trace.finish()

    if native_count == len(planet_names):
        return PlanetStateBatch(
            ephemeris_states,
            "ephemeris_runtime_model",
            "swisseph_api",
            physical_ephemeris_summary(models),
            models,
            None,
        )
    return PlanetStateBatch(
        ephemeris_states,
        (
            "mixed_precision_runtime_model"
            if native_count
            else "approximate_orbital_model"
        ),
        (
            "swisseph_api_with_analytic_fallback"
            if native_count
            else "fatebridge_analytic_ephemerides"
        ),
        physical_ephemeris_summary(models),
        models,
        fallback,
    )
