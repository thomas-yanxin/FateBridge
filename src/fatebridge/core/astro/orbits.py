"""Bounded DE441 or zero-byte Moshier/astronomy-engine orbital fallback.

When DE441 coefficient chunks are present (or FATEBRIDGE_DE441_DIR is explicitly
configured), receiver Earth/Sun, planetary-system barycenters and Moon share the
bounded DE441 source grid and light-cone optics. When DE441 chunks are absent
and FATEBRIDGE_DE441_DIR is unset, approximate positions use Swiss Ephemeris
built-in Moshier (when available) or astronomy-engine, keeping the same dict
structure without claiming native file-backed accuracy.
"""

from __future__ import annotations

import math
from typing import Any, Sequence, TypedDict

import astronomy

from fatebridge.core.astro import runtime
from fatebridge.core.astro.aberration_math import longitude_rate_change
from fatebridge.core.astro.analytic_observer import (
    ABERRATION_METHOD,
    LIGHT_TIME_METHOD,
    AnalyticObserver,
)
from fatebridge.core.astro.de441_source import (
    SOURCE_VERSION as PLANETARY_SOURCE_VERSION,
)
from fatebridge.core.astro.de441_source import (
    coefficient_files_available,
    de441_dir_explicitly_configured,
)
from fatebridge.core.astro.mean_node import MODEL_ID as MEAN_NODE_MODEL
from fatebridge.core.astro.mean_node import (
    SOURCE_NATIVE_VERSION as MEAN_NODE_SOURCE_VERSION,
)
from fatebridge.core.astro.mean_node import mean_lunar_node
from fatebridge.core.astro.nutation import nutation
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.astro.reference_frames import (
    ecliptic_rotation,
    madd,
    mm,
    mv,
    pair,
    precession,
)
from fatebridge.core.astro.solar_deflection import MODEL_ID as DEFLECTION_MODEL
from fatebridge.core.astro.time_scales import fallback_julian_day_tt
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.ephemeris_runtime import EPHEMERIS_LOCK

DE441_ORBITAL_MODEL = "bounded_de441_earth_moon_planetary_fallback_v9"
MOSHIER_ORBITAL_MODEL = "moshier_astronomy_engine_orbital_fallback_v1"
ORBITAL_MODEL = (
    DE441_ORBITAL_MODEL
    if (coefficient_files_available() or de441_dir_explicitly_configured())
    else MOSHIER_ORBITAL_MODEL
)
FALLBACK_MODELS = frozenset(
    {ORBITAL_MODEL, DE441_ORBITAL_MODEL, MOSHIER_ORBITAL_MODEL, MEAN_NODE_MODEL}
)
LIBRARY_VERSION = "2.1.19"
MOTION_METHOD = (
    "analytic_local_TT_source_clock_implicit_light_cone_bending_Lorentz_and_display_v1"
)
MOSHIER_MOTION_METHOD = "swisseph_moshier_analytical_TT_FLG_SPEED"
ASTRONOMY_ENGINE_MOTION_METHOD = (
    "astronomy_engine_geocentric_true_ecliptic_TT_finite_difference_speed_v1"
)

_ASTRONOMY_BODIES: dict[str, astronomy.Body] = {
    "Sun": astronomy.Body.Sun,
    "Moon": astronomy.Body.Moon,
    "Mercury": astronomy.Body.Mercury,
    "Venus": astronomy.Body.Venus,
    "Mars": astronomy.Body.Mars,
    "Jupiter": astronomy.Body.Jupiter,
    "Saturn": astronomy.Body.Saturn,
    "Uranus": astronomy.Body.Uranus,
    "Neptune": astronomy.Body.Neptune,
    "Pluto": astronomy.Body.Pluto,
}


def _use_de441_source() -> bool:
    return coefficient_files_available() or de441_dir_explicitly_configured()


def _active_backend() -> str:
    if _use_de441_source():
        return "de441"
    if runtime.swe is not None:
        return "moshier"
    return "astronomy_engine"


class FallbackFactorSource(TypedDict):
    source_version: str
    method_id: str


def fallback_factor_source(
    planet: str, *, backend: str | None = None
) -> FallbackFactorSource:
    """One source/method definition for provider receipts and object motion."""
    if planet == "North Node":
        version = f"Swiss Ephemeris {MEAN_NODE_SOURCE_VERSION} numerical parameters"
        method = "analytic_mean_node_polynomial_secular_correction_and_nutation_TT"
        return {"source_version": version, "method_id": method}
    selected = _active_backend() if backend is None else backend
    if selected == "de441":
        point = (
            "Moon center from EMB/geocentric Moon"
            if planet == "Moon"
            else "Sun" if planet == "Sun" else f"{planet}-system barycenter"
        )
        version = f"{PLANETARY_SOURCE_VERSION} {point}; losslessly retained original binary64 coefficient words on the bounded source grid; same-source receiving Earth/Sun; geocentric ERFA 2.0.1 TDB-TT and derivative; fixed ERFA mean-J2000 frame bias; native-TDB polynomial p/v/a, right-hand source-cell derivatives except final endpoint; local TT chain, not a derivative of binary rounding"
        method = MOTION_METHOD
    elif selected == "moshier":
        swe_ver = str(getattr(runtime.swe, "version", "2.10.03"))
        version = (
            f"Swiss Ephemeris {swe_ver} Moshier DE404 analytical series (fallback)"
        )
        method = MOSHIER_MOTION_METHOD
    else:
        version = f"astronomy-engine {LIBRARY_VERSION} VSOP87/ELP2000/JPL geocentric apparent TT"
        method = ASTRONOMY_ENGINE_MOTION_METHOD
    return {"source_version": version, "method_id": method}


class FallbackProvenance(TypedDict):
    approximate_planets: list[str]
    time_argument: str
    factor_time_arguments: dict[str, str]
    julian_day_tt: float
    tt_source: str
    source_path: str
    library: str
    library_version: str
    dependency_versions: dict[str, str]
    factor_source_versions: dict[str, str]
    position_convention: str
    longitude_motion_method: str
    factor_longitude_motion_methods: dict[str, str]
    uncomputed_motion_reasons: dict[str, str]
    light_time_method: str
    factor_light_time_methods: dict[str, str]
    observer_aberration_method: str
    factor_solar_deflection_models: dict[str, str]
    accuracy_certified: bool


def _astronomy_engine_ecliptic(
    tt_days_from_j2000: float, body: astronomy.Body
) -> tuple[float, float, float, float]:
    astro_time = astronomy.Time.FromTerrestrialTime(tt_days_from_j2000)
    v_eqj = astronomy.GeoVector(body, astro_time, True)
    sph_ect = astronomy.SphereFromVector(
        astronomy.RotateVector(astronomy.Rotation_EQJ_ECT(astro_time), v_eqj)
    )
    sph_eqd = astronomy.SphereFromVector(
        astronomy.RotateVector(astronomy.Rotation_EQJ_EQD(astro_time), v_eqj)
    )
    return (
        float(sph_ect.lon) % 360.0,
        float(sph_ect.lat),
        float(sph_ect.dist),
        float(sph_eqd.lat),
    )


def _moshier_state(swe_module: Any, planet: str, tt: TTInstant) -> dict[str, float]:
    body_id = PLANET_SWISSEPH_IDS.get(planet)
    if body_id is None:
        raise ValueError(f"Unsupported approximate body for Moshier fallback: {planet}")
    tt_jd = tt.as_float()
    with EPHEMERIS_LOCK:
        ecliptic, ecl_flag = swe_module.calc(
            tt_jd, body_id, swe_module.FLG_MOSEPH | swe_module.FLG_SPEED
        )
        equatorial, eq_flag = swe_module.calc(
            tt_jd, body_id, swe_module.FLG_MOSEPH | swe_module.FLG_EQUATORIAL
        )
    if ecl_flag < 0 or not all(math.isfinite(float(v)) for v in ecliptic[:4]):
        raise RuntimeError(f"Moshier fallback failed for {planet}: retflag={ecl_flag}")
    state: dict[str, float] = {
        "longitude": float(ecliptic[0]) % 360.0,
        "latitude": float(ecliptic[1]),
        "distance": float(ecliptic[2]),
        "longitude_speed": float(ecliptic[3]),
    }
    if eq_flag >= 0 and math.isfinite(float(equatorial[1])):
        state["declination"] = float(equatorial[1])
    return state


def _astronomy_engine_state(planet: str, tt: TTInstant) -> dict[str, float]:
    body = _ASTRONOMY_BODIES.get(planet)
    if body is None:
        raise ValueError(
            f"Unsupported approximate body for astronomy-engine fallback: {planet}"
        )
    tt_j2000 = float(tt.days - 2451545)
    lon, lat, distance, declination = _astronomy_engine_ecliptic(tt_j2000, body)
    dt = 1.0 / 128.0
    lon_minus = _astronomy_engine_ecliptic(tt_j2000 - dt, body)[0]
    lon_plus = _astronomy_engine_ecliptic(tt_j2000 + dt, body)[0]
    longitude_speed = math.remainder(lon_plus - lon_minus, 360.0) / (2.0 * dt)
    return {
        "longitude": lon,
        "latitude": lat,
        "distance": distance,
        "declination": declination,
        "longitude_speed": longitude_speed,
    }


class ApproximateEphemeris:
    def __init__(
        self, julian_day_ut1: float, julian_day_tt: float | TTInstant | None
    ) -> None:
        self.uncomputed_motion_reasons: dict[str, str] = {}
        self._backend = _active_backend()
        self.observer: AnalyticObserver | None = (
            AnalyticObserver() if self._backend == "de441" else None
        )
        self.tt = fallback_julian_day_tt(julian_day_ut1, julian_day_tt)
        self.tt_source = (
            "chart_tt"
            if julian_day_tt is not None
            else "astronomy_engine_espenak_meeus_delta_t_estimate"
        )

    @property
    def julian_day_tt(self) -> float:
        """Scalar receipt adapter; computation retains the canonical point."""
        return self.tt.as_float()

    def state(self, planet: str, offset_days: float = 0.0) -> dict[str, float]:
        tt = self.tt.shifted_by(offset_days)
        self.uncomputed_motion_reasons.pop(planet, None)
        if planet == "North Node":
            state = mean_lunar_node(tt)
            if "longitude_speed" not in state:
                self.uncomputed_motion_reasons[planet] = (
                    "piecewise_mean_node_correction_has_no_unique_derivative_at_knot"
                )
            return state
        if self.observer is None:
            if self._backend == "moshier" and runtime.swe is not None:
                return _moshier_state(runtime.swe, planet, tt)
            return _astronomy_engine_state(planet, tt)
        motion = self.observer.apparent_state(
            planet, self.tt.days - 2451545, offset_days
        )
        matrix, matrix_d = precession(tt)
        values, derivatives = pair(tt, "pepol", "peper")
        rotation, rotation_d = ecliptic_rotation(values[1], derivatives[1])
        display = mm(rotation, matrix)
        mean = mv(display, motion.position)
        dpsi, deps, dpsi_d, _ = nutation(tt)
        psi = math.radians(dpsi)
        co, si = math.cos(psi), math.sin(psi)
        x, y, z = co * mean[0] - si * mean[1], si * mean[0] + co * mean[1], mean[2]
        epsilon = values[1] + math.radians(deps)
        eqy = y * math.cos(epsilon) - z * math.sin(epsilon)
        eqz = y * math.sin(epsilon) + z * math.cos(epsilon)
        state = {
            "longitude": math.degrees(math.atan2(y, x)) % 360,
            "latitude": math.degrees(math.atan2(z, math.hypot(x, y))),
            "distance": math.hypot(*motion.position),
            "declination": math.degrees(math.atan2(eqz, math.hypot(x, eqy))),
        }

        if motion.velocity is None:
            self.uncomputed_motion_reasons[planet] = (
                "solar_deflection_has_no_unique_local_TT_derivative_at_profile_or_limiter_corner"
            )
            return state
        display_d = madd(mm(rotation_d, matrix), mm(rotation, matrix_d))
        mean_d = tuple(
            a + b
            for a, b in zip(
                mv(display, motion.velocity), mv(display_d, motion.position)
            )
        )
        state["longitude_speed"] = math.fsum(
            (longitude_rate_change(mean, mean_d), dpsi_d)
        )
        return state

    def provenance(self, planets: Sequence[str]) -> FallbackProvenance:
        """Keep every receipt with the actual shared source and optical method."""
        physical = [name for name in planets if name != "North Node"]
        factors = {
            name: fallback_factor_source(name, backend=self._backend)
            for name in planets
        }
        dependencies: dict[str, str] = {}
        if physical:
            if self._backend == "de441":
                dependencies["JPL DE441 bounded source"] = PLANETARY_SOURCE_VERSION
                dependencies["geocentric ERFA TDB-TT coefficients"] = "2.0.1"
            elif self._backend == "moshier":
                dependencies["Swiss Ephemeris Moshier"] = str(
                    getattr(runtime.swe, "version", "2.10.03")
                )
            else:
                dependencies["astronomy-engine"] = LIBRARY_VERSION
        if "North Node" in planets:
            dependencies["Swiss numerical mean-node parameters"] = (
                MEAN_NODE_SOURCE_VERSION
            )
        if self.tt_source != "chart_tt":
            dependencies["astronomy-engine"] = LIBRARY_VERSION

        if not physical or self._backend == "de441":
            library = "FateBridge analytic ephemeris"
            position_convention = "geocentric_Vondrak_scalar_obliquity_77term_true_ecliptic_and_equator_of_date"
            light_time_method = "per_factor" if physical else "not_applicable"
            factor_light_time_methods = {name: LIGHT_TIME_METHOD for name in physical}
            aberration_method = ABERRATION_METHOD if physical else "not_applicable"
            deflection_models = {
                name: (
                    "self_luminous_source_not_applicable"
                    if name == "Sun"
                    else (
                        "omitted_for_Moon_native_convention"
                        if name == "Moon"
                        else DEFLECTION_MODEL
                    )
                )
                for name in physical
            }
            physical_time_arg = "TT; DE441 evaluated at geocentric TDB(TT)"
            library_version = ORBITAL_MODEL if physical else MEAN_NODE_MODEL
        elif self._backend == "moshier":
            library = "Swiss Ephemeris Moshier fallback"
            position_convention = "geocentric_true_ecliptic_and_equator_of_date"
            light_time_method = "per_factor"
            factor_light_time_methods = {
                name: "swisseph_moshier_apparent_light_time" for name in physical
            }
            aberration_method = "swisseph_moshier_aberration"
            deflection_models = {
                name: "swisseph_moshier_deflection" for name in physical
            }
            physical_time_arg = "TT"
            library_version = MOSHIER_ORBITAL_MODEL
        else:
            library = "astronomy-engine fallback"
            position_convention = "geocentric_true_ecliptic_and_equator_of_date"
            light_time_method = "per_factor"
            factor_light_time_methods = {
                name: "astronomy_engine_apparent_light_time" for name in physical
            }
            aberration_method = "astronomy_engine_annual_aberration"
            deflection_models = {
                name: "omitted_in_astronomy_engine" for name in physical
            }
            physical_time_arg = "TT"
            library_version = MOSHIER_ORBITAL_MODEL

        return {
            "approximate_planets": list(planets),
            "time_argument": "TT",
            "factor_time_arguments": {
                name: "TT" if name == "North Node" else physical_time_arg
                for name in planets
            },
            "julian_day_tt": self.julian_day_tt,
            "tt_source": self.tt_source,
            "source_path": "src/fatebridge/core/astro/orbits.py",
            "library": library,
            "library_version": library_version,
            "dependency_versions": dependencies,
            "factor_source_versions": {
                name: source["source_version"] for name, source in factors.items()
            },
            "position_convention": position_convention,
            "longitude_motion_method": "per_factor",
            "factor_longitude_motion_methods": {
                name: source["method_id"] for name, source in factors.items()
            },
            "uncomputed_motion_reasons": self.uncomputed_motion_reasons,
            "light_time_method": light_time_method,
            "factor_light_time_methods": factor_light_time_methods,
            "observer_aberration_method": aberration_method,
            "factor_solar_deflection_models": deflection_models,
            "accuracy_certified": False,
        }
