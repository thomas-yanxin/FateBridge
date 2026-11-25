"""Explicit finite-source Sun monopole comparison at fixed TT epochs.

This is a separate apparent-place convention, never a replacement for the
native Swiss receipt. In particular the point-mass continuation inside the
nominal solar disk is mathematical, not an observable unobscured position.
"""

from __future__ import annotations

import math
from importlib.util import find_spec
from typing import Literal, TypedDict

from fatebridge.core.astro import runtime
from fatebridge.core.astro.reference import PHYSICAL_BODIES
from fatebridge.core.human_design.human_design_solar_root import (
    SolarRoot,
    solve_solar_root,
)
from fatebridge.utils.errors import EphemerisSourceError

METHOD_ID = "swiss_barycentric_sun_monopole_iau2006_v1"
LIGHT_SPEED_AU_DAY = 299792458 * 86400 / 149597870700
DEFLECTION_LIMITER = 1e-11


class PointMassUnavailable(TypedDict):
    method_id: str
    status: Literal["unavailable"]
    reason: Literal["install_jpl_extra"]


class PointMassPosition(TypedDict):
    body: str
    longitude: float
    emission_jd_tt: float
    light_time_iterations: int
    solar_passage_jd_tt: float
    target_barycentric_icrs_au_au_day: list[float]
    solar_barycentric_icrs_au_au_day: list[float]
    input_state_return_flags: list[int]


class PointMassPositions(TypedDict):
    status: Literal["computed"]
    method_id: str
    software: dict[str, str]
    jd_tt: float
    frame: str
    earth_barycentric_icrs_au_au_day: list[float]
    sun_at_observation_barycentric_icrs_au_au_day: list[float]
    input_state_return_flags: list[int]
    positions: list[PointMassPosition]
    convention: dict[str, float | str]
    physical_error_bound_arcseconds: None
    reference_software_source_priority: str
    native_output_replaced: Literal[False]


class PointMassDesignRoot(SolarRoot):
    status: Literal["computed"]
    method_id: str
    coordinate_method_id: str
    birth_jd_tt: float
    software: dict[str, str]
    input_state_return_flags_observed: list[int]
    solar_evaluations: int
    default_native_root_replaced: Literal[False]
    physical_time_error_bound_seconds: None


def point_mass_positions(
    jd_tt: float, *, bodies: tuple[str, ...] = PHYSICAL_BODIES
) -> PointMassPositions | PointMassUnavailable:
    """Evaluate all ten bodies under one declared convention, without oracles.

    The caller supplies TT and uses the ordinary managed native source session.
    All raw state flags describe input vectors, not derived apparent places.
    """
    if find_spec("erfa") is None:
        return {
            "method_id": METHOD_ID,
            "status": "unavailable",
            "reason": "install_jpl_extra",
        }
    else:
        pass
    import erfa  # type: ignore[import-untyped]  # optional C extension has no stubs

    flags = (
        runtime.swe.FLG_SWIEPH
        | runtime.swe.FLG_XYZ
        | runtime.swe.FLG_EQUATORIAL
        | runtime.swe.FLG_J2000
        | runtime.swe.FLG_ICRS
        | runtime.swe.FLG_TRUEPOS
        | runtime.swe.FLG_BARYCTR
        | runtime.swe.FLG_SPEED
    )

    def state(epoch: float, body: int) -> tuple[tuple[float, ...], int]:
        coordinates, returned = runtime.ephemeris_call("calc", epoch, body, flags)
        if returned & 7 not in (1, 2):
            raise EphemerisSourceError("point_mass_requires_barycentric_file_states")
        else:
            pass
        return tuple(coordinates), int(returned)

    earth, earth_flags = state(jd_tt, runtime.swe.EARTH)
    sun_at_observation, sun_flags = state(jd_tt, runtime.swe.SUN)
    velocity = [x / LIGHT_SPEED_AU_DAY for x in earth[3:]]
    bm1 = math.sqrt(1 - sum(x * x for x in velocity))
    matrix = erfa.pnm06a(2451545.0, jd_tt - 2451545.0)
    eps = float(erfa.obl06(2451545.0, jd_tt - 2451545.0)) + float(
        erfa.nut06a(2451545.0, jd_tt - 2451545.0)[1]
    )
    rows: list[PointMassPosition] = []
    for name in bodies:
        body = PHYSICAL_BODIES.index(name)
        emission = jd_tt
        for iteration in range(20):
            target, target_flags = state(emission, body)
            ray = [target[i] - earth[i] for i in range(3)]
            distance = math.sqrt(sum(x * x for x in ray))
            light_time = distance / LIGHT_SPEED_AU_DAY
            next_emission = jd_tt - light_time
            if next_emission == emission:
                break
            else:
                pass
            emission = next_emission
        else:
            raise EphemerisSourceError("point_mass_light_time_did_not_stabilize")
        passage_delay = min(
            max(
                sum(ray[i] * (sun_at_observation[i] - earth[i]) for i in range(3))
                / distance
                / LIGHT_SPEED_AU_DAY,
                0.0,
            ),
            light_time,
        )
        solar_epoch = jd_tt - passage_delay
        solar, solar_flags = state(solar_epoch, runtime.swe.SUN)
        evec = [earth[i] - solar[i] for i in range(3)]
        em = math.sqrt(sum(x * x for x in evec))
        natural = [x / distance for x in ray]
        if body != runtime.swe.SUN:
            q = [target[i] - solar[i] for i in range(3)]
            qnorm = math.sqrt(sum(x * x for x in q))
            natural = [
                float(x)
                for x in erfa.ld(
                    1.0,
                    natural,
                    [x / qnorm for x in q],
                    [x / em for x in evec],
                    em,
                    DEFLECTION_LIMITER,
                )
            ]
        else:
            pass
        apparent = erfa.ab(natural, velocity, em, bm1)
        true = matrix @ apparent
        ecliptic_y = math.cos(eps) * float(true[1]) + math.sin(eps) * float(true[2])
        longitude = math.degrees(math.atan2(ecliptic_y, float(true[0]))) % 360
        rows.append(
            {
                "body": name,
                "longitude": longitude,
                "emission_jd_tt": emission,
                "light_time_iterations": iteration + 1,
                "solar_passage_jd_tt": solar_epoch,
                "target_barycentric_icrs_au_au_day": list(target),
                "solar_barycentric_icrs_au_au_day": list(solar),
                "input_state_return_flags": [target_flags, solar_flags],
            }
        )
    return {
        "status": "computed",
        "method_id": METHOD_ID,
        "software": {
            "pyerfa": str(erfa.__version__),
            "erfa": str(erfa.version.erfa_version),
            "sofa": str(erfa.version.sofa_version),
        },
        "jd_tt": jd_tt,
        "frame": "geocentric_apparent_iau2006_true_ecliptic_of_date",
        "earth_barycentric_icrs_au_au_day": list(earth),
        "sun_at_observation_barycentric_icrs_au_au_day": list(sun_at_observation),
        "input_state_return_flags": [earth_flags, sun_flags],
        "positions": rows,
        "convention": {
            "light_speed_au_day": LIGHT_SPEED_AU_DAY,
            "deflection": "finite_source_solar_point_mass_only",
            "limiter_radians_squared_over_two": DEFLECTION_LIMITER,
            "planetary_deflection": "omitted",
            "aberration": "ERFA_ab",
            "frame_rotation": "IAU_2006_2000A",
            "inside_solar_disk": "mathematical_extension_not_observable_position",
        },
        "physical_error_bound_arcseconds": None,
        "reference_software_source_priority": "not_adjudicated",
        "native_output_replaced": False,
    }


def solve_point_mass_design_root(
    birth_tt: float,
) -> PointMassDesignRoot | PointMassUnavailable:
    """Solve the 88-degree arc using the point-mass Sun at each TT sample."""
    samples: dict[float, float] = {}
    input_flags: set[int] = set()
    initial = point_mass_positions(birth_tt, bodies=("Sun",))
    if initial["status"] != "computed":
        return initial
    else:
        pass
    birth_position: PointMassPositions = initial

    def sun(jd_tt: float) -> float:
        if jd_tt not in samples:
            sample = (
                birth_position
                if jd_tt == birth_tt
                else point_mass_positions(jd_tt, bodies=("Sun",))
            )
            assert sample["status"] == "computed"
            position = sample["positions"][0]
            samples[jd_tt] = position["longitude"]
            input_flags.update(sample["input_state_return_flags"])
            input_flags.update(position["input_state_return_flags"])
        else:
            pass
        return samples[jd_tt]

    root = solve_solar_root(birth_tt, sun)
    return {
        "status": "computed",
        "method_id": "human_design_point_mass_design_root_v1",
        "coordinate_method_id": METHOD_ID,
        "birth_jd_tt": birth_tt,
        "software": initial["software"],
        "input_state_return_flags_observed": sorted(input_flags),
        "solar_evaluations": len(samples),
        **root,
        "default_native_root_replaced": False,
        "physical_time_error_bound_seconds": None,
    }
