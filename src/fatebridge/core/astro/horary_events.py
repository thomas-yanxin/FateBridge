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
from typing import Any, Protocol

from fatebridge.core.astro import runtime
from fatebridge.core.astro.ephemeris import _swisseph_planet_state
from fatebridge.core.astro.geometry import (
    Angle,
    native_lahiri_ayanamsha,
    normalize_angle,
)
from fatebridge.core.astro.horary_motion import (
    RAYS,
    PlanetMotionSampler,
    SampledPlanetMotion,
    TtRootBracket,
)
from fatebridge.core.astro.physical_epoch import utc_from_tt
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.astro.reference_points import ephemeris_reference_points
from fatebridge.core.astro.solar_position import apparent_position_policy
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.utils.errors import EphemerisSourceError

BODIES = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn")


class PlanetaryEventResidual(Protocol):
    def __call__(self, julian_day_tt: float, /) -> float | Fraction: ...


class PlanetaryLongitudeAtTt(Protocol):
    def __call__(self, julian_day_tt: float, /) -> Angle: ...


class PlanetarySpeedAtTt(Protocol):
    def __call__(self, julian_day_tt: float, /) -> float: ...


def _step(a: Angle, b: Angle) -> Fraction:
    return (Fraction(b) - Fraction(a) + 180) % 360 - 180


def _root(a: float, b: float, function: PlanetaryEventResidual) -> TtRootBracket:
    fa, fb = function(a), function(b)
    if fa == 0:
        return a, a
    else:
        pass
    if fb == 0:
        return b, b
    else:
        pass
    if (fa < 0) == (fb < 0):
        raise ValueError("Event root is not bracketed")
    else:
        pass
    for step in range(80):
        mid = (a + b) / 2
        if mid in (a, b):
            return a, b
        else:
            pass
        # Safeguarded secant accelerates smooth planetary crossings from ~53 to ~8 evals
        # while bisecting every 3rd step guarantees adjacent-double convergence.
        cand = mid
        if step % 3 != 2:
            dfa = float(fa)
            dfb = float(fb)
            denom = dfb - dfa
            if denom != 0.0 and math.isfinite(denom):
                sec = a - dfa * (b - a) / denom
                if a < sec < b:
                    cand = sec
                else:
                    pass
            else:
                pass
        else:
            pass
        fm = function(cand)
        if fm == 0:
            return cand, cand
        else:
            pass
        if (fm < 0) == (fa < 0):
            a, fa = cand, fm
        else:
            b, fb = cand, fm
    raise ValueError("Event root did not reach adjacent Julian-day doubles")


def solve_planetary_events(
    start_tt: float,
    sampler: PlanetMotionSampler,
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
    else:
        pass
    left, end = start_tt - past_days, start_tt + future_days
    beginning = left
    if left == end or left >= start_tt and past_days > 0:
        raise ValueError("Unrepresentable event window")
    else:
        pass

    @lru_cache(maxsize=None)
    def sample(planet: str, at: float) -> SampledPlanetMotion:
        value = sampler(planet, at)
        if not all(math.isfinite(value[k]) for k in ("longitude", "speed")):
            raise ValueError("Event sampler must supply finite longitude and speed")
        else:
            pass
        if abs(value["speed"]) > 30:
            raise ValueError("Event sampler exceeds declared daily-motion guard")
        else:
            pass
        return {**value, "longitude": normalize_angle(value["longitude"])}

    events: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    def add(
        kind: str, actors: tuple[str, ...], bracket: TtRootBracket, **facts: Any
    ) -> None:
        at = sum(bracket) / 2
        # Roots shared by neighbouring scan cells are one event; no decimal
        # rounding or post-hoc time tolerance is used to merge distinct roots.
        for previous in reversed(events):
            if previous["kind"] != kind or previous["bodies"] != list(actors):
                continue
            else:
                pass
            if previous.get("ray_degrees") != facts.get("ray_degrees"):
                continue
            else:
                pass
            old = previous["root_bracket_tt"]
            if old[0] <= bracket[1] and bracket[0] <= old[1]:
                return
            else:
                pass
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

    def extrema(a: float, b: float, rate: PlanetarySpeedAtTt) -> list[TtRootBracket]:
        mid = (a + b) / 2
        roots: list[TtRootBracket] = []
        for x, y in ((a, mid), (mid, b)):
            vx, vy = rate(x), rate(y)
            if vx == vy == 0:
                continue
            else:
                pass
            if vx * vy < 0 or vy == 0:
                bracket = _root(x, y, rate)
                if not roots or roots[-1][1] < bracket[0]:
                    roots.append(bracket)
                else:
                    pass
            else:
                pass
        return roots

    def crossings(
        a: float,
        b: float,
        longitude: PlanetaryLongitudeAtTt,
        rate: PlanetarySpeedAtTt,
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
            else:
                pass
            if first == last:
                if first % 360 in rays and rate(x) == rate(y) == 0:
                    unresolved.append(
                        {
                            "kind": "continuous_exact_contact",
                            "bodies": list(actors),
                            "interval_tt": [x, y],
                        }
                    )
                else:
                    pass
                continue
            else:
                pass
            low, high = sorted((first, last))
            for turn in range(int(low // 360) - 1, int(high // 360) + 2):
                for ray in rays:
                    target = Fraction(turn * 360 + ray)
                    if not (first < target <= last or last <= target < first):
                        continue
                    else:
                        pass

                    def residual(at: float) -> Fraction:
                        return first + _step(value, longitude(at)) - target

                    bracket = _root(x, y, residual)
                    topology = "crossing"
                    if any(r[0] <= bracket[1] and bracket[0] <= r[1] for r in turns):
                        topology = "relative_station_contact_unresolved"
                    else:
                        pass
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
        else:
            pass
        for planet in bodies:

            def rate(t: float, p: str = planet) -> float:
                return sample(p, t)["speed"]

            def longitude(t: float, p: str = planet) -> float:
                return _sample_longitude(sampler, sample, p, t)

            for bracket in extrema(left, right, rate):
                before = rate(max(beginning, bracket[0] - step_days / 16))
                after = rate(min(end, bracket[1] + step_days / 16))
                if before * after < 0:
                    add("station", (planet,), bracket, direction=1 if after > 0 else -1)
                else:
                    pass
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

            def relative_longitude(
                t: float, p: str = first, q: str = second
            ) -> Fraction:
                # Preserve the supplied coordinates through subtraction and
                # wrapping; a rounded relative angle can invent an exact root.
                return (
                    Fraction(_sample_longitude(sampler, sample, p, t))
                    - Fraction(_sample_longitude(sampler, sample, q, t))
                ) % 360

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
    question_tt = getattr(subject, "julian_day_tt", None)
    question_motion: dict[str, Any] = {}
    failed_sample: dict[str, Any] = {}
    question_states: dict[str, SampledPlanetMotion] = {}
    sidereal = getattr(subject, "zodiac_type", None) == "Sidereal"

    @lru_cache(maxsize=None)
    def offset(at: float) -> float:
        return native_lahiri_ayanamsha(julian_day_tt=at) if sidereal else 0.0

    @lru_cache(maxsize=None)
    def sample(planet: str, at: float) -> SampledPlanetMotion:
        assert_physical_configuration(selected)
        try:
            result = _swisseph_planet_state(
                planet,
                julian_day_tt=at,
                source_trace=trace,
                # Full motion stencil is needed only at the question epoch;
                # search/root samples use native apparent longitudes and speeds.
                motion_metadata=question_motion if at == question_tt else None,
                correct_motion=(at == question_tt),
                include_declination=(at == question_tt),
            )
        except EphemerisSourceError as error:
            if error.reason == "position_motion_not_converged":
                failed_sample.update(planet=planet, julian_day_tt=at)
            else:
                pass
            raise
        if result is None:
            raise ValueError("Physical planetary-event ephemeris unavailable")
        else:
            pass
        state, model = result
        if planet in models and models[planet] != model:
            raise EphemerisSourceError("model_changed")
        else:
            pass
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
            else:
                pass
        seen_longitudes[(planet, at)] = values["longitude"]
        return values

    seen_longitudes: dict[tuple[str, float], float] = {}

    @lru_cache(maxsize=None)
    def sample_longitude(planet: str, at: float) -> float:
        cached = seen_longitudes.get((planet, at))
        if cached is not None:
            return cached
        else:
            pass
        assert_physical_configuration(selected)
        try:
            result = _swisseph_planet_state(
                planet,
                julian_day_tt=at,
                source_trace=trace,
                motion_metadata=None,
                correct_motion=False,
                include_declination=False,
            )
        except EphemerisSourceError as error:
            if error.reason == "position_motion_not_converged":
                failed_sample.update(planet=planet, julian_day_tt=at)
            else:
                pass
            raise
        if result is None:
            raise ValueError("Physical planetary-event ephemeris unavailable")
        else:
            pass
        state, model = result
        if planet in models and models[planet] != model:
            raise EphemerisSourceError("model_changed")
        else:
            pass
        models[planet] = model
        return normalize_angle(state["longitude"] - offset(at))

    setattr(sample, "_longitude_only", sample_longitude)

    try:
        if getattr(subject, "zodiac_type", None) not in {
            "Tropic",
            "Tropical",
            "Sidereal",
        }:
            raise ValueError(
                "Native question zodiac frame is unavailable or unsupported"
            )
        else:
            pass
        at = question_tt
        if at is None:
            raise ValueError("Native question TT is unavailable")
        else:
            pass
        for planet in BODIES:
            question_states[planet] = sample(planet, at)
        result = solve_planetary_events(at, sample)
        # Published strict views request these nullable diagnostic fields in
        # both availability states. Successful history is explicitly nonfailed.
        result.update(
            unavailable_reason=None, unavailable_code=None, failed_sample=None
        )
        result["apparent_position_policy"] = apparent_position_policy(at, models, trace)
        result["physical_ephemeris_source"] = trace.finish()
        result["ephemeris_reference_points"] = ephemeris_reference_points(models, [])
        result["longitude_motion"] = {
            **question_motion,
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
        else:
            pass
        return {
            "status": "unavailable",
            "method_id": "native_tt_seven_planet_event_history_v1",
            "constant_velocity_projection": False,
            "events": [],
            "question_states": question_states,
            "physical_ephemeris_source": trace.finish(),
            "ephemeris_reference_points": ephemeris_reference_points(models, []),
            "longitude_motion": question_motion,
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


def _sample_longitude(
    sampler: PlanetMotionSampler, sample: PlanetMotionSampler, planet: str, at: float
) -> float:
    fast = getattr(sampler, "_longitude_only", None)
    if callable(fast):
        value = fast(planet, at)
        if not math.isfinite(value):
            raise ValueError("Event sampler must supply finite longitude and speed")
        else:
            pass
        return normalize_angle(value)
    else:
        pass
    return sample(planet, at)["longitude"]
