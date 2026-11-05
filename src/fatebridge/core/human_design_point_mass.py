"""Explicit finite-source Sun monopole comparison at fixed TT epochs.

This is a separate apparent-place convention, never a replacement for the
native Swiss receipt. In particular the point-mass continuation inside the
nominal solar disk is mathematical, not an observable unobscured position.
"""

from __future__ import annotations

import math
from importlib.util import find_spec

from pydantic import JsonValue

from fatebridge.core.astro import runtime
from fatebridge.utils.errors import EphemerisSourceError

METHOD_ID = "swiss_barycentric_sun_monopole_iau2006_v1"
LIGHT_SPEED_AU_DAY = 299792458 * 86400 / 149597870700
DEFLECTION_LIMITER = 1e-11
PHYSICAL_BODIES = (
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
)


def point_mass_positions(
    jd_tt: float, *, bodies: tuple[str, ...] = PHYSICAL_BODIES
) -> dict[str, JsonValue]:
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
        return tuple(coordinates), int(returned)

    earth, earth_flags = state(jd_tt, runtime.swe.EARTH)
    sun_at_observation, sun_flags = state(jd_tt, runtime.swe.SUN)
    velocity = [x / LIGHT_SPEED_AU_DAY for x in earth[3:]]
    bm1 = math.sqrt(1 - sum(x * x for x in velocity))
    matrix = erfa.pnm06a(2451545.0, jd_tt - 2451545.0)
    eps = float(erfa.obl06(2451545.0, jd_tt - 2451545.0)) + float(
        erfa.nut06a(2451545.0, jd_tt - 2451545.0)[1]
    )
    rows: list[JsonValue] = []
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


def solve_point_mass_design_root(birth_tt: float) -> dict[str, JsonValue]:
    """Solve the same 88-degree relation with this profile's Sun throughout.

    Reuse the established adjacent-float TT solver and lattice witness. Its
    endpoints bound the evaluated numerical function, not physical time error.
    """
    from fatebridge.core.human_design_solar_root import solve_solar_root

    samples: dict[float, float] = {}
    input_flags: set[int] = set()
    initial = point_mass_positions(birth_tt, bodies=("Sun",))
    if initial["status"] != "computed":
        return initial

    def sun(tt: float) -> float:
        if tt not in samples:
            sample = (
                initial if tt == birth_tt else point_mass_positions(tt, bodies=("Sun",))
            )
            positions, earth_flags = (
                sample["positions"],
                sample["input_state_return_flags"],
            )
            assert isinstance(positions, list) and isinstance(earth_flags, list)
            position = positions[0]
            assert isinstance(position, dict)
            longitude, body_flags = (
                position["longitude"],
                position["input_state_return_flags"],
            )
            assert isinstance(longitude, float) and isinstance(body_flags, list)
            samples[tt] = longitude
            for flag in (*earth_flags, *body_flags):
                assert isinstance(flag, int)
                input_flags.add(flag)
        return samples[tt]

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
