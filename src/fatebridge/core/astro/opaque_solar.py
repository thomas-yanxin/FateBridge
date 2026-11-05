"""A named opaque-Sun apparent-position model, separate from the native chart.

The model uses finite-source solar monopole deflection outside the opaque
solar sphere. An intercepted ray keeps light time and aberration but has zero
solar deflection, as demonstrated by the paired Horizons observer/LT+S data.
Inside-disk coordinates are a mathematical convention, not observable light.
"""

from __future__ import annotations

import math
from fractions import Fraction
from importlib.util import find_spec
from typing import Callable, NamedTuple, Sequence

from pydantic import JsonValue

from fatebridge.core.astro import runtime
from fatebridge.core.astro.geometry import normalize_angle
from fatebridge.core.astro.native_coordinates import COORDINATE_FLAGS
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.astro.reference_points import ephemeris_reference_points
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.utils.errors import EphemerisSourceError

METHOD_ID = "finite_source_opaque_solar_apparent_positions_v1"
FRAME = "IAU2006/2000A_true_ecliptic_of_date"
SOLAR_RADIUS_M = 695700000
SOLAR_RADIUS_AU = Fraction(SOLAR_RADIUS_M, 149597870700)
LIGHT_SPEED_AU_DAY_EXACT = Fraction(299792458 * 86400, 149597870700)
LIGHT_SPEED_AU_DAY = float(LIGHT_SPEED_AU_DAY_EXACT)
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


class _RetardedSample(NamedTuple):
    epoch: float
    coordinates: tuple[float, ...]
    flags: int
    distance: float
    residual_squared: Fraction
    delay: Fraction


def _retarded_state(
    observation: float,
    observer: Sequence[float],
    sample: Callable[[float], tuple[tuple[float, ...], int]],
) -> tuple[_RetardedSample, int, dict[str, JsonValue]]:
    """Bracket the light cone at adjacent representable TT, without a tolerance.

    For the subluminal physical sources F(e)=e-observation+distance(e)/c is
    increasing. Its sign is evaluated by exact squared distances of supplied
    binary64 states, avoiding a rounded large-JD subtraction or square root.
    Fixed-point steps only propose samples; equality never certifies a root.
    """
    emission = observation
    lower: _RetardedSample | None = None
    upper: _RetardedSample | None = None
    for iteration in range(20):
        coordinates, flags = sample(emission)
        ray = [coordinates[i] - observer[i] for i in range(3)]
        distance = math.hypot(*ray)
        distance_squared = sum(
            ((Fraction(coordinates[i]) - Fraction(observer[i])) ** 2 for i in range(3)),
            Fraction(),
        )
        delay = Fraction(observation) - Fraction(emission)
        residual = distance_squared - (LIGHT_SPEED_AU_DAY_EXACT * delay) ** 2
        current = _RetardedSample(
            emission, coordinates, flags, distance, residual, delay
        )
        if residual == 0:
            lower = upper = current
            break
        if residual < 0:
            lower = current
        else:
            upper = current
        if (
            lower is not None
            and upper is not None
            and math.nextafter(lower.epoch, math.inf) == upper.epoch
        ):
            break
        proposal = observation - distance / LIGHT_SPEED_AU_DAY
        if proposal == emission:
            proposal = math.nextafter(emission, math.inf if residual < 0 else -math.inf)
        if (
            lower is not None
            and upper is not None
            and not lower.epoch < proposal < upper.epoch
        ):
            proposal = lower.epoch + (upper.epoch - lower.epoch) / 2
        emission = proposal
    else:
        raise EphemerisSourceError("opaque_solar_light_time_not_stabilized")
    assert lower is not None and upper is not None
    residual_seconds = []
    for endpoint in (lower, upper):
        # Rationalization retains the sign when distance/c almost equals the
        # small elapsed delay. This display value does not decide the bracket.
        denominator = LIGHT_SPEED_AU_DAY_EXACT * (
            Fraction(endpoint.distance) + LIGHT_SPEED_AU_DAY_EXACT * endpoint.delay
        )
        residual_seconds.append(
            float(endpoint.residual_squared / denominator) * 86400
            if endpoint.residual_squared
            else 0.0
        )
    return (
        upper,
        iteration + 1,
        {
            "method_id": "exact_source_light_cone_adjacent_tt_v1",
            "selected_endpoint": "first_nonnegative_F",
            "lower_jd_tt": lower.epoch,
            "upper_jd_tt": upper.epoch,
            "lower_residual_seconds": residual_seconds[0],
            "upper_residual_seconds": residual_seconds[1],
            "bracket_width_seconds": float(
                Fraction(upper.epoch) - Fraction(lower.epoch)
            )
            * 86400,
            "exact_root": lower.epoch == upper.epoch,
            "lower_target_barycentric_icrs_au_au_day": list(lower.coordinates),
        },
    )


def opaque_solar_intersection(
    earth: Sequence[float], target: Sequence[float], solar: Sequence[float]
) -> bool:
    """Intersect the finite unbent ray using the exact supplied double states.

    A tangent is assigned to the exterior. The sphere radius is the nominal
    695700 km in the Horizons source header, not a residual-fitted cutoff.
    This classifies the given geometry; it is not a physical limb-error bound.
    """
    ray = [Fraction(target[i]) - Fraction(earth[i]) for i in range(3)]
    observer = [Fraction(earth[i]) - Fraction(solar[i]) for i in range(3)]
    ray_squared = sum((x * x for x in ray), Fraction())
    along = -sum((a * b for a, b in zip(ray, observer)), Fraction())
    if along <= 0:
        minimum_squared = sum((x * x for x in observer), Fraction())
    elif along >= ray_squared:
        minimum_squared = sum(((a + b) ** 2 for a, b in zip(observer, ray)), Fraction())
    else:
        minimum_squared = (
            sum((x * x for x in observer), Fraction()) - along * along / ray_squared
        )
    return minimum_squared < SOLAR_RADIUS_AU * SOLAR_RADIUS_AU


@runtime.preserve_ephemeris_path()
def opaque_solar_positions(
    jd_tt: float,
    bodies: Sequence[str] = PHYSICAL_BODIES,
    *,
    source_trace: PhysicalEphemerisTrace | None = None,
) -> dict[str, JsonValue]:
    """Return actual position coordinates, without changing natal chart facts.

    Optional ERFA supplies the published aberration/deflection/frame formulas.
    Input vectors are native geometric barycentric ICRS states in AU/AU per
    day. Their native flags never describe the final derived apparent places.
    """
    if find_spec("erfa") is None:
        raise ImportError("opaque_solar requires the jpl extra (pyerfa)")
    import erfa  # type: ignore[import-untyped]

    swe = runtime.swe
    if swe is None:
        raise ImportError("opaque_solar requires Swiss Ephemeris")
    flags = (
        swe.FLG_SWIEPH
        | swe.FLG_XYZ
        | swe.FLG_EQUATORIAL
        | swe.FLG_J2000
        | swe.FLG_ICRS
        | swe.FLG_TRUEPOS
        | swe.FLG_BARYCTR
        | swe.FLG_SPEED
    )
    mask = (
        sum(getattr(swe, name) for name in COORDINATE_FLAGS)
        | swe.FLG_SPEED
        | swe.FLG_SPEED3
    )
    expected = flags | swe.FLG_NOABERR | swe.FLG_NOGDEFL | swe.FLG_NONUT
    selected = configured_ephemeris_path()
    trace = source_trace if source_trace is not None else PhysicalEphemerisTrace()
    input_models: set[str] = set()

    def state(at: float, body: int, label: str) -> tuple[tuple[float, ...], int]:
        try:
            values, returned = runtime.ephemeris_call("calc", at, body, flags)
        except swe.Error as error:
            raise EphemerisSourceError(
                "opaque_solar_barycentric_unavailable"
            ) from error
        assert_physical_configuration(selected)
        if returned < 0 or returned & mask != expected & mask:
            raise EphemerisSourceError("coordinate_contract_changed")
        model = runtime.ephemeris_model_from_retflag(returned)
        if model not in {"swieph", "jpl"}:
            raise EphemerisSourceError("opaque_solar_requires_barycentric_files")
        input_models.add(model)
        if len(input_models) != 1:
            raise EphemerisSourceError("model_changed")
        if len(values) != 6 or not all(math.isfinite(value) for value in values):
            raise EphemerisSourceError("coordinate_values_unavailable")
        trace.observe(label, model)
        return tuple(float(value) for value in values), int(returned)

    earth, earth_flags = state(jd_tt, swe.EARTH, "opaque_solar_observer")
    sun, sun_flags = state(jd_tt, swe.SUN, "opaque_solar_sun_observation")
    beta = [x / LIGHT_SPEED_AU_DAY for x in earth[3:]]
    bm1 = math.sqrt(1 - math.fsum(x * x for x in beta))
    delta = jd_tt - 2451545.0
    matrix = erfa.pnm06a(2451545.0, delta)
    epsilon = float(erfa.obl06(2451545.0, delta)) + float(
        erfa.nut06a(2451545.0, delta)[1]
    )
    positions: list[JsonValue] = []
    for name in bodies:
        body = PLANET_SWISSEPH_IDS[name]
        solved, iterations, light_time_solution = _retarded_state(
            jd_tt, earth, lambda at: state(at, body, name)
        )
        emission, target, target_flags, distance = solved[:4]
        ray = [target[i] - earth[i] for i in range(3)]
        light_time = distance / LIGHT_SPEED_AU_DAY
        direction = [x / distance for x in ray]
        closest_delay = min(
            max(
                math.fsum(direction[i] * (sun[i] - earth[i]) for i in range(3))
                / LIGHT_SPEED_AU_DAY,
                0.0,
            ),
            light_time,
        )
        solar_epoch = jd_tt - closest_delay
        solar, solar_flags = state(solar_epoch, swe.SUN, "opaque_solar_deflector")
        solar_to_observer = [earth[i] - solar[i] for i in range(3)]
        em = math.hypot(*solar_to_observer)
        intercepted = body != swe.SUN and opaque_solar_intersection(
            earth, target, solar
        )
        if body != swe.SUN and not intercepted:
            solar_to_target = [target[i] - solar[i] for i in range(3)]
            rq = math.hypot(*solar_to_target)
            direction = [
                float(x)
                for x in erfa.ld(
                    1.0,
                    direction,
                    [x / rq for x in solar_to_target],
                    [x / em for x in solar_to_observer],
                    em,
                    DEFLECTION_LIMITER,
                )
            ]
        apparent = erfa.ab(direction, beta, em, bm1)
        equator = matrix @ apparent
        x = float(equator[0])
        y = math.cos(epsilon) * float(equator[1]) + math.sin(epsilon) * float(
            equator[2]
        )
        z = -math.sin(epsilon) * float(equator[1]) + math.cos(epsilon) * float(
            equator[2]
        )
        positions.append(
            {
                "body": name,
                "longitude": normalize_angle(math.degrees(math.atan2(y, x))),
                "latitude": math.degrees(math.atan2(z, math.hypot(x, y))),
                "distance_au": distance,
                "apparent_icrs_unit_direction": [float(x) for x in apparent],
                "solar_disc_intercepted": intercepted,
                "solar_deflection_applied": body != swe.SUN and not intercepted,
                "emission_jd_tt": emission,
                "solar_passage_jd_tt": solar_epoch,
                "light_time_iterations": iterations,
                "light_time_solution": light_time_solution,
                "target_barycentric_icrs_au_au_day": list(target),
                "solar_barycentric_icrs_au_au_day": list(solar),
                "input_state_return_flags": [target_flags, solar_flags],
            }
        )
    return {
        "status": "computed",
        "method_id": METHOD_ID,
        "apparent_model": "opaque_solar",
        "scope": "standalone_positions_only",
        "frame": FRAME,
        "jd_tt": jd_tt,
        "positions": positions,
        "earth_barycentric_icrs_au_au_day": list(earth),
        "sun_at_observation_barycentric_icrs_au_au_day": list(sun),
        "input_state_return_flags": [earth_flags, sun_flags],
        "physical_ephemeris_source": trace.finish() if source_trace is None else None,
        "ephemeris_reference_points": ephemeris_reference_points(
            {name: next(iter(input_models)) for name in bodies}, []
        ),
        "convention": {
            "observer": "Earth_geocenter",
            "solar_radius_m": SOLAR_RADIUS_M,
            "deflection": "finite_source_solar_monopole_except_intercepted_opaque_rays",
            "tangent_boundary": "exterior",
            "opaque_intersection_arithmetic": "exact_supplied_binary64_states",
            "deflection_limiter": DEFLECTION_LIMITER,
            "aberration": "ERFA_ab",
            "light_speed_au_day": LIGHT_SPEED_AU_DAY,
            "inside_solar_disk": "nonobservable_mathematical_extension",
        },
        "natal_chart_recomputed": False,
        "speeds_and_derived_chart_assessed": False,
        "physical_accuracy_certified": False,
    }
