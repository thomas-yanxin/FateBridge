"""Lunar longitude contacts before ingress, with explicit numerical models.

The production path samples the physical ephemeris in TT and brackets roots.
Neither a future angular contact nor an absent contact establishes an outcome.
"""

from __future__ import annotations

import math
from fractions import Fraction
from functools import lru_cache
from typing import Any, Protocol

from fatebridge.core.astro import runtime
from fatebridge.core.astro.ephemeris import _swisseph_planet_state, fast_swe_call
from fatebridge.core.astro.geometry import (
    angle_fraction,
    angular_separation_fraction,
    native_lahiri_ayanamsha,
    normalize_angle,
)
from fatebridge.core.astro.physical_epoch import utc_from_tt
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.classical_western import _aspect_phase
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.ephemeris_runtime import ephemeris_call as _ORIG_EPHEMERIS_CALL
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.utils.errors import EphemerisSourceError

RAYS = {
    0: ("conjunction", "合"),
    60: ("sextile", "六合"),
    90: ("square", "刑"),
    120: ("trine", "拱"),
    180: ("opposition", "冲"),
    240: ("trine", "拱"),
    270: ("square", "刑"),
    300: ("sextile", "六合"),
}
BODIES = ("Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn")
SampledPlanetMotion = dict[str, float]
TtRootBracket = tuple[float, float]


class PlanetMotionSampler(Protocol):
    def __call__(self, planet: str, julian_day_tt: float, /) -> SampledPlanetMotion: ...


class LunarCrossingResidual(Protocol):
    def __call__(self, julian_day_tt: float, /) -> Fraction: ...


def _signed_step(first: float, second: float) -> Fraction:
    return (angle_fraction(second) - angle_fraction(first) + 180) % 360 - 180


def _bisect_crossing(
    left: float, right: float, residual: LunarCrossingResidual
) -> TtRootBracket:
    """Return adjacent TT endpoints with negative left and nonnegative right."""
    if not residual(left) < 0 <= residual(right):
        raise ValueError("Lunar event root is not bracketed")
    for _ in range(80):
        middle = (left + right) / 2
        if middle == left or middle == right:
            return left, right
        if residual(middle) < 0:
            left = middle
        else:
            right = middle
    raise ValueError("Lunar event root failed to reach adjacent Julian-day doubles")


def first_lunar_contact(
    motion: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, bool, str]:
    """Return the displayed candidate and whether its strict order is known."""
    if (
        not motion
        or motion.get("constant_velocity_projection") is not False
        or motion.get("status") not in {"computed", "boundary_ambiguous"}
    ):
        return (
            None,
            False,
            "Native lunar event search unavailable; a linear projection is not historical event evidence",
        )
    contacts = motion.get("contacts", [])
    if not contacts:
        return (
            None,
            False,
            "No certain contact in the lunar before-ingress window; no assertion about events outside this window",
        )
    first = contacts[0]
    first_end = first["root_bracket_tt"][1]
    # The lunar solver proves (lower, upper]. A competing root is strictly
    # later even if its excluded lower endpoint equals the first upper bound.
    if any(row["root_bracket_tt"][0] < first_end for row in contacts[1:]):
        return (
            first,
            False,
            "Overlapping first-event brackets cannot establish a strict order",
        )
    if any(
        row["root_bracket_tt"][0] < first_end
        for row in motion.get("ambiguous_boundary_contacts", [])
    ):
        return (
            first,
            False,
            "An ambiguous boundary event may overlap or precede the selected contact",
        )
    return (
        first,
        True,
        "First certain native longitude contact before lunar ingress, under the declared scan model; not a complete prohibition or historical separation test",
    )


def _event_fields(
    moon: SampledPlanetMotion, other: SampledPlanetMotion, ray: int
) -> dict[str, Any]:
    name, label = RAYS[ray]
    angle = float(min(ray, 360 - ray))
    phase = _aspect_phase(
        moon["longitude"], moon["speed"], other["longitude"], other["speed"], angle
    )
    return {
        "aspect": name,
        "aspect_label": label,
        "angle": angle,
        "ray_degrees": ray,
        "orb": float(
            abs(
                angular_separation_fraction(moon["longitude"], other["longitude"])
                - Fraction(angle)
            )
        ),
        "phase": phase,
        "applying": {"applying": True, "separating": False}.get(phase),
    }


def solve_lunar_contacts(
    start_tt: float, sampler: PlanetMotionSampler, *, bodies: tuple[str, ...] = BODIES
) -> dict[str, Any]:
    """Bracket every strictly future lunar ray crossing before first sign exit.

    The physical Moon must be prograde and faster than every selected body.
    An unverified monotonic interval or unresolved boundary stays unknown.
    """
    if not math.isfinite(start_tt):
        raise ValueError("Finite TT epoch required")
    unchecked_sample = sampler

    def sample(planet: str, at: float) -> SampledPlanetMotion:
        value = unchecked_sample(planet, at)
        if not all(math.isfinite(value[key]) for key in ("longitude", "speed")):
            raise ValueError(
                "Finite longitude and speed required for every event sample"
            )
        return value

    first = {p: sample(p, start_tt) for p in ("Moon", *bodies)}
    initial_moon = angle_fraction(first["Moon"]["longitude"]) % 360
    boundary = (initial_moon // 30 + 1) * 30
    longitude = initial_moon
    relative = {
        p: initial_moon - angle_fraction(first[p]["longitude"]) % 360 for p in bodies
    }
    left, before = start_tt, first
    contacts = []
    exit_bracket = None
    for step in range(1, 7 * 12 + 1):
        right = start_tt + step / 12
        after = {p: sample(p, right) for p in ("Moon", *bodies)}
        if before["Moon"]["speed"] <= 0 or after["Moon"]["speed"] <= 0:
            raise ValueError("Lunar forward-motion condition not established")
        moon_step = _signed_step(
            before["Moon"]["longitude"], after["Moon"]["longitude"]
        )
        if not 0 < moon_step < 5:
            raise ValueError("Lunar scan interval violates the declared unwrap bound")
        next_longitude = longitude + moon_step
        if longitude < boundary <= next_longitude:

            def ingress_residual(at: float) -> Fraction:
                return (
                    longitude
                    + _signed_step(
                        before["Moon"]["longitude"], sample("Moon", at)["longitude"]
                    )
                    - boundary
                )

            exit_bracket = _bisect_crossing(left, right, ingress_residual)
        for planet in bodies:
            if any(
                row["Moon"]["speed"] <= row[planet]["speed"] for row in (before, after)
            ):
                raise ValueError("Lunar relative-motion condition not established")
            change = moon_step - _signed_step(
                before[planet]["longitude"], after[planet]["longitude"]
            )
            if not 0 < change < 5:
                raise ValueError(
                    "Relative lunar scan is not monotone within unwrap bounds"
                )
            low, high = relative[planet], relative[planet] + change
            for turn in range(low // 360 - 1, high // 360 + 2):
                for ray in RAYS:
                    target = ray + turn * 360
                    if not low < target <= high:
                        continue

                    def residual(at: float) -> Fraction:
                        current_moon = _signed_step(
                            before["Moon"]["longitude"], sample("Moon", at)["longitude"]
                        )
                        current_other = _signed_step(
                            before[planet]["longitude"], sample(planet, at)["longitude"]
                        )
                        return low + current_moon - current_other - target

                    bracket = _bisect_crossing(left, right, residual)
                    event_moon, event_other = sample("Moon", bracket[1]), sample(
                        planet, bracket[1]
                    )
                    contacts.append(
                        {
                            "other": planet,
                            "after_days": bracket[1] - start_tt,
                            "julian_day_tt": bracket[1],
                            "root_bracket_tt": list(bracket),
                            "moon_longitude": event_moon["longitude"],
                            "other_longitude": event_other["longitude"],
                            "moon_latitude": event_moon.get("latitude"),
                            "other_latitude": event_other.get("latitude"),
                            **_event_fields(first["Moon"], first[planet], ray),
                        }
                    )
            relative[planet] = high
        if exit_bracket is not None:
            break
        left, before, longitude = right, after, next_longitude
    if exit_bracket is None:
        raise ValueError("No lunar ingress bracket within the declared seven-day guard")
    accepted = [row for row in contacts if row["root_bracket_tt"][1] <= exit_bracket[0]]
    ambiguous = [
        row
        for row in contacts
        if row not in accepted and row["root_bracket_tt"][0] < exit_bracket[1]
    ]
    accepted.sort(
        key=lambda row: (row["julian_day_tt"], row["other"], row["ray_degrees"])
    )
    return {
        "status": "boundary_ambiguous" if ambiguous else "computed",
        "method_id": "native_tt_lunar_contacts_before_ingress_v1",
        "constant_velocity_projection": False,
        "start_julian_day_tt": start_tt,
        "degrees_left_in_sign": float(boundary - initial_moon),
        "sign_exit_julian_day_tt": exit_bracket[1],
        "sign_exit_root_bracket_tt": list(exit_bracket),
        "sign_exit_after_days": exit_bracket[1] - start_tt,
        "contacts": accepted,
        "ambiguous_boundary_contacts": ambiguous,
        "void_of_course": False if accepted else (None if ambiguous else True),
        "time_scale": "TT",
        "scan_step_days": 1 / 12,
        "scan_guard_days": 7,
    }


@runtime.preserve_ephemeris_path()
def native_lunar_contacts(subject: Any) -> dict[str, Any]:
    """Production sampler uses the same TT, zodiac and source configuration."""
    selected = configured_ephemeris_path()
    trace = PhysicalEphemerisTrace()
    models: dict[str, str] = {}
    motion_contexts: dict[float, dict[str, Any]] = {}
    sidereal = subject.zodiac_type == "Sidereal"
    use_fast = (
        runtime.ephemeris_call is _ORIG_EPHEMERIS_CALL
        and configured_jpl_file() is None
        and runtime.swe is not None
    )

    @lru_cache(maxsize=None)
    def offset(at: float) -> float:
        return native_lahiri_ayanamsha(julian_day_tt=at) if sidereal else 0.0

    def offset_speed(at: float) -> float:
        return offset(at + 0.5) - offset(at - 0.5) if sidereal else 0.0

    @lru_cache(maxsize=None)
    def sample(planet: str, at: float) -> SampledPlanetMotion:
        assert_physical_configuration(selected)
        if use_fast and at != subject.julian_day_tt:
            body_id = PLANET_SWISSEPH_IDS[planet]
            coords, flag = fast_swe_call(
                "calc", at, body_id, runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED
            )
            if flag < 0:
                raise ValueError("Physical lunar-event ephemeris unavailable")
            model = runtime.ephemeris_model_from_retflag(flag)
            if planet in models and models[planet] != model:
                raise EphemerisSourceError("model_changed")
            models[planet] = model
            values = {
                "longitude": normalize_angle(float(coords[0]) - offset(at)),
                "speed": float(coords[3]) - offset_speed(at),
                "latitude": float(coords[1]),
            }
            if not all(math.isfinite(v) for v in values.values()):
                raise ValueError("Nonfinite physical lunar-event state")
            return values
        result = _swisseph_planet_state(
            planet,
            julian_day_tt=at,
            source_trace=trace,
            motion_metadata=motion_contexts.setdefault(at, {}),
            correct_motion=at == subject.julian_day_tt,
            include_declination=at == subject.julian_day_tt,
        )
        if result is None:
            raise ValueError("Physical lunar-event ephemeris unavailable")
        state, model = result
        if planet in models and models[planet] != model:
            raise EphemerisSourceError("model_changed")
        models[planet] = model
        values = {
            "longitude": normalize_angle(state["longitude"] - offset(at)),
            "speed": state["longitude_speed"] - offset_speed(at),
            "latitude": state["latitude"],
        }
        if not all(math.isfinite(v) for v in values.values()):
            raise ValueError("Nonfinite physical lunar-event state")
        return values

    try:
        result = solve_lunar_contacts(subject.julian_day_tt, sample)
        result["physical_ephemeris_source"] = trace.finish()
        result["longitude_frame"] = (
            "sidereal_lahiri" if sidereal else "tropical_true_ecliptic_of_date"
        )
        for event in [
            result,
            *result["contacts"],
            *result["ambiguous_boundary_contacts"],
        ]:
            epoch = event.get("julian_day_tt", event.get("sign_exit_julian_day_tt"))
            try:
                event["datetime_utc"] = utc_from_tt(epoch)[0]
            except EphemerisSourceError:
                raise
            except (ValueError, OverflowError):
                event["datetime_utc"] = None
        return result
    except EphemerisSourceError:
        raise
    except (ValueError, ImportError, AttributeError, RuntimeError) as error:
        return {
            "status": "unavailable",
            "method_id": "native_tt_lunar_contacts_before_ingress_v1",
            "void_of_course": None,
            "constant_velocity_projection": False,
            "contacts": [],
            "unavailable_reason": str(error),
        }
