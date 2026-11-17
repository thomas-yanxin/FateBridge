"""Bounded coherent DE441 fallback, separate from native ephemeris states.

Receiver Earth/Sun, planetary-system barycenters and Moon share the same
source grid, declared geocentric TDB(TT) and fixed mean-J2000 frame bias.
Fixed-reception light time, finite-source bending and Lorentz aberration act
on one ray before the shared long-period display frame and TT longitude
motion. Source representation bounds are separate from physical precision;
this remains an approximation without Swiss/JPL or SOTA certification.
"""

from __future__ import annotations

import math
from typing import Sequence, TypedDict

from fatebridge.core.astro.aberration_math import longitude_rate_change
from fatebridge.core.astro.analytic_observer import (
    ABERRATION_METHOD,
    LIGHT_TIME_METHOD,
    AnalyticObserver,
)
from fatebridge.core.astro.de441_source import FRAME_URL as SOURCE_FRAME_URL
from fatebridge.core.astro.de441_source import PAPER_URL as PLANETARY_PAPER_URL
from fatebridge.core.astro.de441_source import SOURCE_URL as PLANETARY_SOURCE_URL
from fatebridge.core.astro.de441_source import (
    SOURCE_VERSION as PLANETARY_SOURCE_VERSION,
)
from fatebridge.core.astro.mean_node import MODEL_ID as MEAN_NODE_MODEL
from fatebridge.core.astro.mean_node import SOURCE_CODE_URL as MEAN_NODE_SOURCE_CODE_URL
from fatebridge.core.astro.mean_node import (
    SOURCE_NATIVE_VERSION as MEAN_NODE_SOURCE_VERSION,
)
from fatebridge.core.astro.mean_node import SOURCE_URL as MEAN_NODE_SOURCE_URL
from fatebridge.core.astro.mean_node import mean_lunar_node
from fatebridge.core.astro.nutation import SOURCE_URL as FRAME_SOURCE_URL
from fatebridge.core.astro.nutation import nutation
from fatebridge.core.astro.reference_frames import (
    ecliptic_rotation,
    madd,
    mm,
    mv,
    pair,
    precession,
)
from fatebridge.core.astro.solar_deflection import FORMULA_URL as DEFLECTION_FORMULA_URL
from fatebridge.core.astro.solar_deflection import MODEL_ID as DEFLECTION_MODEL
from fatebridge.core.astro.solar_deflection import SOURCE_URL as DEFLECTION_SOURCE_URL
from fatebridge.core.astro.tdb import SOURCE_URL as TDB_SOURCE_URL
from fatebridge.core.astro.time_scales import fallback_julian_day_tt

ORBITAL_MODEL = "bounded_de441_earth_moon_planetary_fallback_v9"
FALLBACK_MODELS = frozenset({ORBITAL_MODEL, MEAN_NODE_MODEL})
LIBRARY_VERSION = "2.1.19"
SOURCE_URL = "https://github.com/cosinekitty/astronomy/tree/v2.1.19"
MOTION_METHOD = (
    "analytic_local_TT_source_clock_implicit_light_cone_bending_Lorentz_and_display_v1"
)


class FallbackFactorSource(TypedDict):
    source_version: str
    source_url: str
    method_id: str


def fallback_factor_source(planet: str) -> FallbackFactorSource:
    """One source/method definition for provider receipts and object motion."""
    if planet == "North Node":
        version = f"Swiss Ephemeris {MEAN_NODE_SOURCE_VERSION} numerical parameters"
        url = MEAN_NODE_SOURCE_CODE_URL
        method = "analytic_mean_node_polynomial_secular_correction_and_nutation_TT"
    else:
        point = (
            "Moon center from EMB/geocentric Moon"
            if planet == "Moon"
            else "Sun" if planet == "Sun" else f"{planet}-system barycenter"
        )
        version = f"{PLANETARY_SOURCE_VERSION} {point}; bounded binary coefficient quanta; same-source receiving Earth/Sun; geocentric ERFA 2.0.1 TDB-TT and derivative; fixed ERFA mean-J2000 frame bias; native-TDB polynomial p/v/a, right-hand source-cell derivatives except final endpoint; local TT chain, not a derivative of binary rounding"
        url = PLANETARY_SOURCE_URL
        method = MOTION_METHOD
    return {"source_version": version, "source_url": url, "method_id": method}


class FallbackProvenance(TypedDict):
    approximate_planets: list[str]
    time_argument: str
    factor_time_arguments: dict[str, str]
    julian_day_tt: float
    tt_source: str
    source_path: str
    method_reference_url: str
    library: str
    library_version: str
    dependency_versions: dict[str, str]
    factor_source_versions: dict[str, str]
    factor_source_urls: dict[str, str]
    additional_source_urls: list[str]
    position_convention: str
    longitude_motion_method: str
    factor_longitude_motion_methods: dict[str, str]
    uncomputed_motion_reasons: dict[str, str]
    light_time_method: str
    factor_light_time_methods: dict[str, str]
    observer_aberration_method: str
    factor_solar_deflection_models: dict[str, str]
    accuracy_certified: bool


class ApproximateEphemeris:
    def __init__(self, julian_day_ut1: float, julian_day_tt: float | None) -> None:
        self.uncomputed_motion_reasons: dict[str, str] = {}
        self.observer = AnalyticObserver()
        self.julian_day_tt = fallback_julian_day_tt(julian_day_ut1, julian_day_tt)
        self.tt_source = (
            "chart_tt"
            if julian_day_tt is not None
            else "astronomy_engine_espenak_meeus_delta_t_estimate"
        )

    def state(self, planet: str, offset_days: float = 0.0) -> dict[str, float]:
        days = self.julian_day_tt - 2451545.0 + offset_days
        tt = days + 2451545.0
        self.uncomputed_motion_reasons.pop(planet, None)
        if planet == "North Node":
            state = mean_lunar_node(tt)
            if "longitude_speed" not in state:
                self.uncomputed_motion_reasons[planet] = (
                    "piecewise_mean_node_correction_has_no_unique_derivative_at_knot"
                )
            return state
        motion = self.observer.apparent_state(
            planet, self.julian_day_tt - 2451545.0, offset_days
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
        factors = {name: fallback_factor_source(name) for name in planets}
        additional = []
        dependencies = {}
        if physical:
            additional.extend(
                [
                    FRAME_SOURCE_URL,
                    PLANETARY_SOURCE_URL,
                    PLANETARY_PAPER_URL,
                    SOURCE_FRAME_URL,
                    TDB_SOURCE_URL,
                    "https://dlmf.nist.gov/18.5.E1",
                    "https://dlmf.nist.gov/18.9.E21",
                    "https://github.com/liberfa/erfa/blob/v2.0.1/src/ab.c",
                ]
            )
            dependencies["JPL DE441 bounded source"] = PLANETARY_SOURCE_VERSION
            dependencies["geocentric ERFA TDB-TT coefficients"] = "2.0.1"
        if any(name not in {"Sun", "Moon"} for name in physical):
            additional.extend([DEFLECTION_SOURCE_URL, DEFLECTION_FORMULA_URL])
        if "North Node" in planets:
            additional.append(MEAN_NODE_SOURCE_URL)
            dependencies["Swiss numerical mean-node parameters"] = (
                MEAN_NODE_SOURCE_VERSION
            )
        if self.tt_source != "chart_tt":
            dependencies["astronomy-engine"] = LIBRARY_VERSION
            additional.append(SOURCE_URL)
        return {
            "approximate_planets": list(planets),
            "time_argument": "TT",
            "factor_time_arguments": {
                name: (
                    "TT"
                    if name == "North Node"
                    else "TT; DE441 evaluated at geocentric TDB(TT)"
                )
                for name in planets
            },
            "julian_day_tt": self.julian_day_tt,
            "tt_source": self.tt_source,
            "source_path": "src/fatebridge/core/astro/orbits.py",
            "method_reference_url": (
                PLANETARY_SOURCE_URL if physical else MEAN_NODE_SOURCE_URL
            ),
            "library": "FateBridge analytic ephemeris",
            "library_version": ORBITAL_MODEL if physical else MEAN_NODE_MODEL,
            "dependency_versions": dependencies,
            "factor_source_versions": {
                name: source["source_version"] for name, source in factors.items()
            },
            "factor_source_urls": {
                name: source["source_url"] for name, source in factors.items()
            },
            "additional_source_urls": additional,
            "position_convention": "geocentric_Vondrak_scalar_obliquity_77term_true_ecliptic_and_equator_of_date",
            "longitude_motion_method": "per_factor",
            "factor_longitude_motion_methods": {
                name: source["method_id"] for name, source in factors.items()
            },
            "uncomputed_motion_reasons": self.uncomputed_motion_reasons,
            "light_time_method": "per_factor" if physical else "not_applicable",
            "factor_light_time_methods": {name: LIGHT_TIME_METHOD for name in physical},
            "observer_aberration_method": (
                ABERRATION_METHOD if physical else "not_applicable"
            ),
            "factor_solar_deflection_models": {
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
            },
            "accuracy_certified": False,
        }
