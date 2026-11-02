"""Finite physical TT histories for all seven traditional planets.

Longitude roots, speed-zero reversals and ingresses are numerical events, not
judgements. Relative-speed extrema split contact searches so a retrograde loop
is not silently treated as a single monotone trajectory. Scan resolution and
the lack of an interval-wide completeness proof remain explicit.
"""

from __future__ import annotations

import itertools
import math
from fractions import Fraction
from functools import lru_cache
from typing import Any, Callable

from fatebridge.core.astro import runtime
from fatebridge.core.astro.ephemeris import _swisseph_planet_state
from fatebridge.core.astro.geometry import native_lahiri_ayanamsha, normalize_angle
from fatebridge.core.astro.physical_epoch import utc_from_tt
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.astro.reference_points import ephemeris_reference_points
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.horary_motion import RAYS
from fatebridge.utils.errors import EphemerisSourceError

BODIES = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn")
State = dict[str, float]
Sampler = Callable[[str, float], State]
Bracket = tuple[float, float]


def _step(a: float, b: float) -> Fraction:
    return (Fraction(b) - Fraction(a) + 180) % 360 - 180


def _root(a: float, b: float, function: Callable[[float], float | Fraction]) -> Bracket:
    fa, fb = function(a), function(b)
    if fa == 0:
        return a, a
    if fb == 0:
        return b, b
    if (fa < 0) == (fb < 0):
        raise ValueError("Event root is not bracketed")
    for _ in range(80):
        mid = (a + b) / 2
        if mid in (a, b):
            return a, b
        fm = function(mid)
        if fm == 0:
            return mid, mid
        if (fm < 0) == (fa < 0):
            a, fa = mid, fm
        else:
            b = mid
    raise ValueError("Event root did not reach adjacent Julian-day doubles")


def solve_planetary_events(
    start_tt: float,
    sampler: Sampler,
    *,
    past_days: float = 30,
    future_days: float = 30,
    step_days: float = 0.125,
    bodies: tuple[str, ...] = BODIES,
) -> dict[str, Any]:
    if (
        not all(math.isfinite(x) for x in (start_tt, past_days, future_days, step_days))
        or min(past_days, future_days) < 0
        or not 0 < step_days <= 0.125
        or not 0 < past_days + future_days <= 120
        or len(set(bodies)) != len(bodies)
        or len(bodies) < 2
    ):
        raise ValueError("Invalid finite planetary-event search window")
    left, end = start_tt - past_days, start_tt + future_days
    beginning = left
    if left == end or left >= start_tt and past_days > 0:
        raise ValueError("Unrepresentable event window")

    @lru_cache(maxsize=None)
    def sample(planet: str, at: float) -> State:
        value = sampler(planet, at)
        if not all(math.isfinite(value[k]) for k in ("longitude", "speed")):
            raise ValueError("Event sampler must supply finite longitude and speed")
        if abs(value["speed"]) > 30:
            raise ValueError("Event sampler exceeds declared daily-motion guard")
        return {**value, "longitude": normalize_angle(value["longitude"])}

    events: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    def add(kind: str, actors: tuple[str, ...], bracket: Bracket, **facts: Any) -> None:
        at = sum(bracket) / 2
        # Roots shared by neighbouring scan cells are one event; no decimal
        # rounding or post-hoc time tolerance is used to merge distinct roots.
        for previous in reversed(events):
            if previous["kind"] != kind or previous["bodies"] != list(actors):
                continue
            if previous.get("ray_degrees") != facts.get("ray_degrees"):
                continue
            old = previous["root_bracket_tt"]
            if old[0] <= bracket[1] and bracket[0] <= old[1]:
                return
        events.append(
            {
                "kind": kind,
                "bodies": list(actors),
                "julian_day_tt": at,
                "root_bracket_tt": list(bracket),
                "epoch_relation": (
                    "past"
                    if bracket[1] < start_tt
                    else "future" if bracket[0] > start_tt else "question_boundary"
                ),
                "states": {p: sample(p, at) for p in actors},
                "state_brackets": {
                    p: [sample(p, bracket[0]), sample(p, bracket[1])] for p in actors
                },
                **facts,
            }
        )

    def extrema(a: float, b: float, rate: Callable[[float], float]) -> list[Bracket]:
        mid = (a + b) / 2
        roots: list[Bracket] = []
        for x, y in ((a, mid), (mid, b)):
            vx, vy = rate(x), rate(y)
            if vx == vy == 0:
                continue
            if vx * vy < 0 or vy == 0:
                bracket = _root(x, y, rate)
                if not roots or roots[-1][1] < bracket[0]:
                    roots.append(bracket)
        return roots

    def crossings(
        a: float,
        b: float,
        longitude: Callable[[float], float],
        rate: Callable[[float], float],
        rays: tuple[int, ...],
        kind: str,
        actors: tuple[str, ...],
    ) -> None:
        turns = extrema(a, b, rate)
        knots = sorted({a, (a + b) / 2, b, *(sum(r) / 2 for r in turns)})
        for x, y in zip(knots, knots[1:]):
            value = longitude(x)
            first = Fraction(value)
            last = first + _step(value, longitude(y))
            if abs(last - first) >= 90:
                raise ValueError("Unwrapped event increment exceeds scan guard")
            if first == last:
                if first % 360 in rays and rate(x) == rate(y) == 0:
                    unresolved.append(
                        {
                            "kind": "continuous_exact_contact",
                            "bodies": list(actors),
                            "interval_tt": [x, y],
                        }
                    )
                continue
            low, high = sorted((first, last))
            for turn in range(int(low // 360) - 1, int(high // 360) + 2):
                for ray in rays:
                    target = Fraction(turn * 360 + ray)
                    if not (first < target <= last or last <= target < first):
                        continue

                    def residual(at: float) -> Fraction:
                        return first + _step(value, longitude(at)) - target

                    bracket = _root(x, y, residual)
                    topology = "crossing"
                    if any(r[0] <= bracket[1] and bracket[0] <= r[1] for r in turns):
                        topology = "relative_station_contact_unresolved"
                    add(
                        kind,
                        actors,
                        bracket,
                        ray_degrees=ray,
                        direction=1 if last > first else -1,
                        topology=topology,
                        **({"aspect": RAYS[ray][0]} if kind == "contact" else {}),
                    )

    while left < end:
        right = min(end, left + step_days)
        if right == left:
            raise ValueError("Unrepresentable event scan step")
        for planet in bodies:

            def rate(t: float, p: str = planet) -> float:
                return sample(p, t)["speed"]

            def longitude(t: float, p: str = planet) -> float:
                return sample(p, t)["longitude"]

            for bracket in extrema(left, right, rate):
                before = rate(max(beginning, bracket[0] - step_days / 16))
                after = rate(min(end, bracket[1] + step_days / 16))
                if before * after < 0:
                    add("station", (planet,), bracket, direction=1 if after > 0 else -1)
            crossings(
                left,
                right,
                longitude,
                rate,
                tuple(range(0, 360, 30)),
                "ingress",
                (planet,),
            )
        for first, second in itertools.combinations(bodies, 2):

            def relative_longitude(t: float, p: str = first, q: str = second) -> float:
                return (sample(p, t)["longitude"] - sample(q, t)["longitude"]) % 360

            def relative_rate(t: float, p: str = first, q: str = second) -> float:
                return sample(p, t)["speed"] - sample(q, t)["speed"]

            crossings(
                left,
                right,
                relative_longitude,
                relative_rate,
                tuple(RAYS),
                "contact",
                (first, second),
            )
        left = right
    events.sort(key=lambda e: (e["julian_day_tt"], e["kind"], e["bodies"]))
    return {
        "status": "computed",
        "method_id": "native_tt_seven_planet_event_history_v1",
        "constant_velocity_projection": False,
        "time_scale": "TT",
        "question_julian_day_tt": start_tt,
        "window_tt": [start_tt - past_days, end],
        "scan_step_days": step_days,
        "bodies": list(bodies),
        "question_states": {p: sample(p, start_tt) for p in bodies},
        "events": events,
        "unresolved_intervals": unresolved,
        "completeness_scope": "Finite sampled search with midpoint/relative-speed-extremum splitting. Continuous-interval monotonicity and arbitrarily narrow multiple reversals are not proved; absence is only within this declared model/window.",
        "full_original_text_acceptance": False,
    }


@runtime.preserve_ephemeris_path()
def native_planetary_events(subject: Any) -> dict[str, Any]:
    selected = configured_ephemeris_path()
    trace = PhysicalEphemerisTrace()
    models: dict[str, str] = {}
    motion_contexts: dict[float, dict[str, Any]] = {}
    failed_sample: dict[str, Any] = {}
    question_states: dict[str, State] = {}
    sidereal = getattr(subject, "zodiac_type", None) == "Sidereal"

    @lru_cache(maxsize=None)
    def offset(at: float) -> float:
        return native_lahiri_ayanamsha(julian_day_tt=at) if sidereal else 0.0

    @lru_cache(maxsize=None)
    def sample(planet: str, at: float) -> State:
        assert_physical_configuration(selected)
        try:
            result = _swisseph_planet_state(
                planet,
                julian_day_tt=at,
                source_trace=trace,
                motion_metadata=motion_contexts.setdefault(at, {}),
            )
        except EphemerisSourceError as error:
            if error.reason == "position_motion_not_converged":
                failed_sample.update(planet=planet, julian_day_tt=at)
            raise
        if result is None:
            raise ValueError("Physical planetary-event ephemeris unavailable")
        state, model = result
        if planet in models and models[planet] != model:
            raise EphemerisSourceError("model_changed")
        models[planet] = model
        speed_offset = offset(at + 0.5) - offset(at - 0.5) if sidereal else 0.0
        values = {
            "longitude": normalize_angle(state["longitude"] - offset(at)),
            "latitude": state["latitude"],
            "speed": state["longitude_speed"] - speed_offset,
            "speed_display_offset_correction": -speed_offset,
        }
        for key in (
            "native",
            "light_time_correction",
            "spatial_aberration_correction",
            "lunar_source_remainder_correction",
            "sidereal_origin_wrap_correction",
            "rotation_correction",
            "analytic_frame_correction",
            "position_derivative_correction",
        ):
            source_key = "longitude_speed_" + key
            if source_key in state:
                values["speed_" + key] = state[source_key]
        return values

    try:
        if getattr(subject, "zodiac_type", None) not in {
            "Tropic",
            "Tropical",
            "Sidereal",
        }:
            raise ValueError(
                "Native question zodiac frame is unavailable or unsupported"
            )
        at = getattr(subject, "julian_day_tt", None)
        if at is None:
            raise ValueError("Native question TT is unavailable")
        for planet in BODIES:
            question_states[planet] = sample(planet, at)
        result = solve_planetary_events(at, sample)
        # Published strict views request these nullable diagnostic fields in
        # both availability states. Successful history is explicitly nonfailed.
        result.update(
            unavailable_reason=None, unavailable_code=None, failed_sample=None
        )
        from fatebridge.core.astro.solar_position import apparent_position_policy

        result["apparent_position_policy"] = apparent_position_policy(at, models, trace)
        result["physical_ephemeris_source"] = trace.finish()
        result["ephemeris_reference_points"] = ephemeris_reference_points(models, [])
        result["longitude_motion"] = {
            **motion_contexts[at],
            "display_frame": (
                "sidereal_lahiri" if sidereal else "tropical_true_ecliptic_of_date"
            ),
            "display_longitude_offset_speed_degrees_per_day": -result[
                "question_states"
            ]["Moon"]["speed_display_offset_correction"],
            "scope": "Source-derived motion policy at question epoch; event state receipts separately retain each native rate and applied correction. Root brackets express numerical resolution, not physical timing uncertainty.",
        }
        result["longitude_frame"] = (
            "sidereal_lahiri" if sidereal else "tropical_true_ecliptic_of_date"
        )
        for event in result["events"]:
            try:
                event["datetime_utc"] = utc_from_tt(event["julian_day_tt"])[0]
            except EphemerisSourceError:
                raise
            except (ValueError, OverflowError):
                event["datetime_utc"] = None
        return result
    except EphemerisSourceError as error:
        if error.reason != "position_motion_not_converged":
            raise
        return {
            "status": "unavailable",
            "method_id": "native_tt_seven_planet_event_history_v1",
            "constant_velocity_projection": False,
            "events": [],
            "question_states": question_states,
            "physical_ephemeris_source": trace.finish(),
            "ephemeris_reference_points": ephemeris_reference_points(models, []),
            "longitude_motion": motion_contexts.get(at, {}) if at is not None else {},
            "unavailable_reason": str(error),
            "unavailable_code": error.reason,
            "failed_sample": failed_sample,
            "completeness_scope": "Search aborted at an unconverged complete-position derivative. Empty events are unknown, not an absence of contacts, stations or ingresses. No native-rate substitute or relaxed convergence line was used.",
            "full_original_text_acceptance": False,
        }
    except (ValueError, ImportError, AttributeError, RuntimeError) as error:
        return {
            "status": "unavailable",
            "method_id": "native_tt_seven_planet_event_history_v1",
            "constant_velocity_projection": False,
            "events": [],
            "unavailable_reason": str(error),
            "full_original_text_acceptance": False,
        }
