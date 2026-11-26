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
from fatebridge.core.astro.ephemeris import (
    _swisseph_planet_state,
    fast_swe_call,
)
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
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.ephemeris_runtime import (
    EPHEMERIS_LOCK,
    _ensure_thread_ephemeris_path,
    configured_ephemeris_path,
)
from fatebridge.core.ephemeris_runtime import ephemeris_call as _ORIG_EPHEMERIS_CALL
from fatebridge.core.jpl_ephemeris import configured_jpl_file
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


def _root(
    a: float,
    b: float,
    function: PlanetaryEventResidual,
    float_function: PlanetarySpeedAtTt | None = None,
    fa_init: float | None = None,
    fb_init: float | None = None,
) -> TtRootBracket:
    orig_a, orig_b = a, b
    if float_function is not None:
        fa_f = float_function(a) if fa_init is None else fa_init
        fb_f = float_function(b) if fb_init is None else fb_init
        if fa_f != 0.0 and fb_f != 0.0 and (fa_f < 0.0) != (fb_f < 0.0):
            # Illinois-modified safeguarded secant collapses both endpoints in ~5-7 evals.
            fa_s, fb_s = fa_f, fb_f
            last_side = 0
            for step in range(48):
                mid = (a + b) / 2
                if mid in (a, b):
                    break
                cand = mid
                if step % 4 != 3:
                    denom = fb_s - fa_s
                    if denom != 0.0 and math.isfinite(denom):
                        sec = a - fa_s * (b - a) / denom
                        if a < sec < b:
                            cand = sec
                fm_f = float_function(cand)
                if fm_f == 0.0:
                    a = max(orig_a, math.nextafter(cand, -math.inf))
                    b = min(orig_b, math.nextafter(cand, math.inf))
                    break
                if (fm_f < 0.0) == (fa_f < 0.0):
                    a, fa_f, fa_s = cand, fm_f, fm_f
                    if last_side == -1:
                        fb_s *= 0.5
                    last_side = -1
                else:
                    b, fb_f, fb_s = cand, fm_f, fm_f
                    if last_side == 1:
                        fa_s *= 0.5
                    last_side = 1
            if (
                (a + b) / 2 in (a, b)
                and (fa_f < 0.0) != (fb_f < 0.0)
                and abs(fa_f) > 1e-11
                and abs(fb_f) > 1e-11
            ):
                return a, b
    fa, fb = function(a), function(b)
    if fa == 0:
        return a, a
    if fb == 0:
        return b, b
    if (fa < 0) == (fb < 0) and (a, b) != (orig_a, orig_b):
        a, b = orig_a, orig_b
        fa, fb = function(a), function(b)
        if fa == 0:
            return a, a
        if fb == 0:
            return b, b
    if (fa < 0) == (fb < 0):
        raise ValueError("Event root is not bracketed")
    for step in range(80):
        mid = (a + b) / 2
        if mid in (a, b):
            return a, b
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
        fm = function(cand)
        if fm == 0:
            return cand, cand
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
    step_days: float = 0.25,
    bodies: tuple[str, ...] = BODIES,
    moon_contacts_only: bool = False,
) -> dict[str, Any]:
    if (
        not all(math.isfinite(x) for x in (start_tt, past_days, future_days, step_days))
        or min(past_days, future_days) < 0
        or not 0 < step_days <= 0.5
        or not 0 < past_days + future_days <= 120
        or len(set(bodies)) != len(bodies)
        or len(bodies) < 2
    ):
        raise ValueError("Invalid finite planetary-event search window")
    left, end = start_tt - past_days, start_tt + future_days
    beginning = left
    if left == end or left >= start_tt and past_days > 0:
        raise ValueError("Unrepresentable event window")

    sample_cache: dict[tuple[str, float], SampledPlanetMotion] = {}

    def sample(planet: str, at: float) -> SampledPlanetMotion:
        key = (planet, at)
        cached = sample_cache.get(key)
        if cached is not None:
            return cached
        value = sampler(planet, at)
        if not all(math.isfinite(value[k]) for k in ("longitude", "speed")):
            raise ValueError("Event sampler must supply finite longitude and speed")
        if abs(value["speed"]) > 30:
            raise ValueError("Event sampler exceeds declared daily-motion guard")
        out = {**value, "longitude": normalize_angle(value["longitude"])}
        sample_cache[key] = out
        return out

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

    def extrema(a: float, b: float, rate: PlanetarySpeedAtTt) -> list[TtRootBracket]:
        va, vb = rate(a), rate(b)
        min_v = min(abs(va), abs(vb))
        if va * vb > 0.0 and abs(vb - va) < 0.45 * min_v and min_v > 0.01:
            return []
        mid = (a + b) / 2
        roots: list[TtRootBracket] = []
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
        longitude: PlanetaryLongitudeAtTt,
        rate: PlanetarySpeedAtTt,
        rays: tuple[int, ...],
        kind: str,
        actors: tuple[str, ...],
        longitude_float: PlanetarySpeedAtTt | None = None,
        precomputed_turns: list[TtRootBracket] | None = None,
    ) -> None:
        turns = extrema(a, b, rate) if precomputed_turns is None else precomputed_turns
        fast_lon = longitude_float or longitude
        if not turns:
            vx_a = float(fast_lon(a))
            vy_b = float(fast_lon(b))
            step_ab = math.remainder(vy_b - vx_a, 360.0)
            if vx_a != vy_b and abs(step_ab) < 45.0:
                knots_pairs: list[
                    tuple[float, float, float | None, float | None, float | None]
                ] = [(a, b, vx_a, vy_b, step_ab)]
            else:
                knots = [a, (a + b) / 2, b]
                knots_pairs = [
                    (x, y, None, None, None) for x, y in zip(knots, knots[1:])
                ]
        else:
            knots = sorted({a, (a + b) / 2, b, *(sum(r) / 2 for r in turns)})
            knots_pairs = [(x, y, None, None, None) for x, y in zip(knots, knots[1:])]
        for x, y, vx_pre, vy_pre, step_pre in knots_pairs:
            vx_f = vx_pre if vx_pre is not None else float(fast_lon(x))
            vy_f = vy_pre if vy_pre is not None else float(fast_lon(y))
            step_f = (
                step_pre if step_pre is not None else math.remainder(vy_f - vx_f, 360.0)
            )
            if abs(step_f) >= 90.0:
                value = longitude(x)
                first = Fraction(value)
                last = first + _step(value, longitude(y))
                if abs(last - first) >= 90:
                    raise ValueError("Unwrapped event increment exceeds scan guard")
            if vx_f == vy_f:
                value = longitude(x)
                first = Fraction(value)
                last = first + _step(value, longitude(y))
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
            low_f, high_f = (
                (vx_f, vx_f + step_f) if step_f >= 0.0 else (vx_f + step_f, vx_f)
            )
            t_min = int(math.floor(low_f / 360.0)) - 1
            t_max = int(math.floor(high_f / 360.0)) + 1
            candidate_targets: list[tuple[int, int]] = []
            for turn in range(t_min, t_max + 1):
                base = turn * 360
                for ray in rays:
                    tgt_f = base + ray
                    if low_f - 1e-6 <= tgt_f <= high_f + 1e-6:
                        candidate_targets.append((turn, ray))
            if not candidate_targets:
                continue
            exact_val: float | Fraction | None = None
            exact_first: Fraction | None = None
            exact_last: Fraction | None = None
            for turn, ray in candidate_targets:
                target_int = turn * 360 + ray
                target_f = float(target_int)
                if not (low_f + 1e-6 < target_f < high_f - 1e-6):
                    if exact_val is None:
                        exact_val = longitude(x)
                        exact_first = Fraction(exact_val)
                        exact_last = exact_first + _step(exact_val, longitude(y))
                    assert exact_first is not None and exact_last is not None
                    target = Fraction(target_int)
                    if not (
                        exact_first < target <= exact_last
                        or exact_last <= target < exact_first
                    ):
                        continue
                else:
                    target = Fraction(target_int)

                def residual(at: float) -> Fraction:
                    nonlocal exact_val, exact_first
                    if exact_val is None:
                        exact_val = longitude(x)
                        exact_first = Fraction(exact_val)
                    assert exact_first is not None
                    return exact_first + _step(exact_val, longitude(at)) - target

                def residual_f(at: float) -> float:
                    return (
                        vx_f
                        + math.remainder(float(fast_lon(at)) - vx_f, 360.0)
                        - target_f
                    )

                fa0 = (vx_f - target_f) if vx_pre is not None else None
                fb0 = (vx_f + step_f - target_f) if vy_pre is not None else None
                bracket = _root(x, y, residual, residual_f, fa_init=fa0, fb_init=fb0)
                topology = "crossing"
                if any(r[0] <= bracket[1] and bracket[0] <= r[1] for r in turns):
                    topology = "relative_station_contact_unresolved"
                add(
                    kind,
                    actors,
                    bracket,
                    ray_degrees=ray,
                    direction=(
                        1
                        if step_f > 0.0
                        or (
                            exact_last is not None
                            and exact_first is not None
                            and exact_last > exact_first
                        )
                        else -1
                    ),
                    topology=topology,
                    **({"aspect": RAYS[ray][0]} if kind == "contact" else {}),
                )

    lon_fast_fn = getattr(sampler, "_longitude_only", None)
    if lon_fast_fn is None:

        def fast_lon_lookup(planet: str, at: float) -> float:
            return sample(planet, at)["longitude"]

    else:
        lon_cache: dict[tuple[str, float], float] = {}

        def fast_lon_lookup(planet: str, at: float) -> float:
            key = (planet, at)
            cached = lon_cache.get(key)
            if cached is not None:
                return cached
            val = float(lon_fast_fn(planet, at))
            if not math.isfinite(val):
                raise ValueError("Event sampler must supply finite longitude and speed")
            val = normalize_angle(val)
            lon_cache[key] = val
            return val

    slow_stride = max(1, int(round(3.0 / step_days))) if step_days <= 0.5 else 1
    ingress_rays = tuple(range(0, 360, 30))
    contact_rays = tuple(RAYS)

    # Pre-sample regular grid once; skip closure creation & crossings() on non-hit cells.
    step_times: list[float] = []
    cur_t = left
    while cur_t < end:
        step_times.append(cur_t)
        nxt_t = min(end, cur_t + step_days)
        if nxt_t == cur_t:
            raise ValueError("Unrepresentable event scan step")
        cur_t = nxt_t
    step_times.append(end)
    n_steps = len(step_times) - 1

    grid_lon: dict[str, list[float]] = {p: [0.0] * (n_steps + 1) for p in bodies}
    grid_spd: dict[str, list[float]] = {p: [0.0] * (n_steps + 1) for p in bodies}
    for p in bodies:
        stride_p = 1 if p == "Moon" else slow_stride
        p_lons = grid_lon[p]
        p_spds = grid_spd[p]
        for k in range(0, n_steps + 1, stride_p):
            s = sample(p, step_times[k])
            p_lons[k] = s["longitude"]
            p_spds[k] = s["speed"]
        if n_steps % stride_p != 0:
            s = sample(p, step_times[n_steps])
            p_lons[n_steps] = s["longitude"]
            p_spds[n_steps] = s["speed"]
        if stride_p > 1:
            # Linearly fill interior half-step positions strictly for broad-phase ray-hit guard.
            for k in range(0, n_steps, stride_p):
                k_end = min(n_steps, k + stride_p)
                if k_end - k <= 1:
                    continue
                l0, l1 = p_lons[k], p_lons[k_end]
                dl = math.remainder(l1 - l0, 360.0)
                s0, s1 = p_spds[k], p_spds[k_end]
                span = k_end - k
                for sub in range(1, span):
                    frac = sub / span
                    p_lons[k + sub] = (l0 + dl * frac) % 360.0
                    p_spds[k + sub] = s0 + (s1 - s0) * frac

    def _has_ray_hit(
        vx: float, vy: float, rays: tuple[int, ...], pad: float = 1e-6
    ) -> bool:
        step_f = math.remainder(vy - vx, 360.0)
        if abs(step_f) >= 45.0 or vx == vy:
            return True
        low_f, high_f = (vx, vx + step_f) if step_f >= 0.0 else (vx + step_f, vx)
        t_min = int(math.floor(low_f / 360.0)) - 1
        t_max = int(math.floor(high_f / 360.0)) + 1
        for turn in range(t_min, t_max + 1):
            base = turn * 360
            for ray in rays:
                tgt_f = base + ray
                if low_f - pad <= tgt_f <= high_f + pad:
                    return True
        return False

    def _might_turn(va: float, vb: float) -> bool:
        min_v = min(abs(va), abs(vb))
        return not (va * vb > 0.0 and abs(vb - va) < 0.45 * min_v and min_v > 0.01)

    if not moon_contacts_only:
        for planet in bodies:
            stride = 1 if planet == "Moon" else slow_stride
            lons_p = grid_lon[planet]
            spds_p = grid_spd[planet]
            for idx in range(0, n_steps, stride):
                idx_end = min(n_steps, idx + stride)
                a_t, b_t = step_times[idx], step_times[idx_end]
                va_s, vb_s = spds_p[idx], spds_p[idx_end]
                need_turn = _might_turn(va_s, vb_s)
                if not need_turn and not _has_ray_hit(
                    lons_p[idx], lons_p[idx_end], ingress_rays
                ):
                    continue

                def rate(t: float, p: str = planet) -> float:
                    return sample(p, t)["speed"]

                def longitude(t: float, p: str = planet) -> float:
                    return fast_lon_lookup(p, t)

                turns = extrema(a_t, b_t, rate) if need_turn else []
                for bracket in turns:
                    before = rate(max(beginning, bracket[0] - step_days / 16))
                    after = rate(min(end, bracket[1] + step_days / 16))
                    if before * after < 0:
                        add(
                            "station",
                            (planet,),
                            bracket,
                            direction=1 if after > 0 else -1,
                        )
                crossings(
                    a_t,
                    b_t,
                    longitude,
                    rate,
                    ingress_rays,
                    "ingress",
                    (planet,),
                    longitude_float=longitude,
                    precomputed_turns=turns,
                )
    for first, second in itertools.combinations(bodies, 2):
        has_moon = "Moon" in (first, second)
        if moon_contacts_only and not has_moon:
            continue
        stride = 1 if has_moon else slow_stride
        lons_p, lons_q = grid_lon[first], grid_lon[second]
        spds_p, spds_q = grid_spd[first], grid_spd[second]
        for idx in range(0, n_steps, stride):
            idx_end = min(n_steps, idx + stride)
            va_r = spds_p[idx] - spds_q[idx]
            vb_r = spds_p[idx_end] - spds_q[idx_end]
            need_turn = _might_turn(va_r, vb_r)
            vx_r = (lons_p[idx] - lons_q[idx]) % 360.0
            vy_r = (lons_p[idx_end] - lons_q[idx_end]) % 360.0
            if not need_turn and not _has_ray_hit(
                vx_r, vy_r, contact_rays, pad=1.0 if has_moon else 1e-6
            ):
                continue
            a_t, b_t = step_times[idx], step_times[idx_end]

            def relative_longitude(
                t: float, p: str = first, q: str = second
            ) -> Fraction:
                return (
                    Fraction(fast_lon_lookup(p, t)) - Fraction(fast_lon_lookup(q, t))
                ) % 360

            def relative_longitude_f(
                t: float, p: str = first, q: str = second
            ) -> float:
                return (fast_lon_lookup(p, t) - fast_lon_lookup(q, t)) % 360.0

            def relative_rate(t: float, p: str = first, q: str = second) -> float:
                return sample(p, t)["speed"] - sample(q, t)["speed"]

            crossings(
                a_t,
                b_t,
                relative_longitude,
                relative_rate,
                contact_rays,
                "contact",
                (first, second),
                longitude_float=relative_longitude_f,
                precomputed_turns=None if need_turn else [],
            )
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
def native_planetary_events(
    subject: Any,
    *,
    past_days: float = 30,
    future_days: float = 30,
    step_days: float = 0.5,
    moon_contacts_only: bool = False,
) -> dict[str, Any]:
    selected = configured_ephemeris_path()
    trace = PhysicalEphemerisTrace()
    models: dict[str, str] = {}
    question_tt = getattr(subject, "julian_day_tt", None)
    question_motion: dict[str, Any] = {}
    failed_sample: dict[str, Any] = {}
    question_states: dict[str, SampledPlanetMotion] = {}
    sidereal = getattr(subject, "zodiac_type", None) == "Sidereal"
    use_fast = (
        runtime.ephemeris_call is _ORIG_EPHEMERIS_CALL
        and configured_jpl_file() is None
        and runtime.swe is not None
    )

    @lru_cache(maxsize=None)
    def offset(at: float) -> float:
        return native_lahiri_ayanamsha(julian_day_tt=at) if sidereal else 0.0

    swe_mod = runtime.swe
    fast_flags = (swe_mod.FLG_SWIEPH | swe_mod.FLG_SPEED) if swe_mod is not None else 0
    fast_lon_flags = swe_mod.FLG_SWIEPH if swe_mod is not None else 0
    flag_models: dict[int, str] = {}
    sample_cache: dict[tuple[str, float], SampledPlanetMotion] = {}

    def _model_for_flag(flag: int) -> str:
        cached_m = flag_models.get(flag)
        if cached_m is None:
            cached_m = runtime.ephemeris_model_from_retflag(flag)
            flag_models[flag] = cached_m
        return cached_m

    def sample(planet: str, at: float) -> SampledPlanetMotion:
        key = (planet, at)
        cached_s = sample_cache.get(key)
        if cached_s is not None:
            return cached_s
        if use_fast and at != question_tt:
            body_id = PLANET_SWISSEPH_IDS[planet]
            coords, flag = swe_mod.calc(at, body_id, fast_flags)
            if flag < 0:
                raise ValueError("Physical planetary-event ephemeris unavailable")
            model = _model_for_flag(flag)
            if planet in models and models[planet] != model:
                raise EphemerisSourceError("model_changed")
            models[planet] = model
            raw_lon = float(coords[0]) % 360.0
            lon = (raw_lon - offset(at)) % 360.0 if sidereal else raw_lon
            spd_corr = (offset(at + 0.5) - offset(at - 0.5)) if sidereal else 0.0
            res = {
                "longitude": lon,
                "latitude": float(coords[1]),
                "speed": float(coords[3]) - spd_corr,
                "speed_display_offset_correction": -spd_corr,
            }
            sample_cache[key] = res
            return res
        assert_physical_configuration(selected)
        try:
            result = _swisseph_planet_state(
                planet,
                julian_day_tt=at,
                source_trace=trace,
                motion_metadata=question_motion if at == question_tt else None,
                correct_motion=(at == question_tt),
                include_declination=(at == question_tt),
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
        seen_longitudes[(planet, at)] = values["longitude"]
        return values

    seen_longitudes: dict[tuple[str, float], float] = {}

    lon_cache: dict[tuple[str, float], float] = {}

    def sample_longitude(planet: str, at: float) -> float:
        key = (planet, at)
        cached = lon_cache.get(key)
        if cached is not None:
            return cached
        cached_sample = sample_cache.get(key)
        if cached_sample is not None:
            lon = cached_sample["longitude"]
            lon_cache[key] = lon
            return lon
        if use_fast:
            body_id = PLANET_SWISSEPH_IDS[planet]
            coords, flag = swe_mod.calc(at, body_id, fast_lon_flags)
            if flag < 0:
                raise ValueError("Physical planetary-event ephemeris unavailable")
            model = _model_for_flag(flag)
            if planet in models and models[planet] != model:
                raise EphemerisSourceError("model_changed")
            models[planet] = model
            raw_lon = float(coords[0]) % 360.0
            lon = (raw_lon - offset(at)) % 360.0 if sidereal else raw_lon
            lon_cache[key] = lon
            return lon
        cached = seen_longitudes.get(key)
        if cached is not None:
            lon_cache[key] = cached
            return cached
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
            raise
        if result is None:
            raise ValueError("Physical planetary-event ephemeris unavailable")
        state, model = result
        if planet in models and models[planet] != model:
            raise EphemerisSourceError("model_changed")
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
        at = question_tt
        if at is None:
            raise ValueError("Native question TT is unavailable")
        for planet in BODIES:
            question_states[planet] = sample(planet, at)
        if use_fast:
            with EPHEMERIS_LOCK:
                _ensure_thread_ephemeris_path()
                assert_physical_configuration(selected)
                result = solve_planetary_events(
                    at,
                    sample,
                    past_days=past_days,
                    future_days=future_days,
                    step_days=step_days,
                    moon_contacts_only=moon_contacts_only,
                )
        else:
            result = solve_planetary_events(
                at,
                sample,
                past_days=past_days,
                future_days=future_days,
                step_days=step_days,
                moon_contacts_only=moon_contacts_only,
            )
        result.update(
            unavailable_reason=None, unavailable_code=None, failed_sample=None
        )
        result["physical_ephemeris_source"] = trace.finish()
        result["ephemeris_reference_points"] = {
            "system_barycenters": sorted(
                b
                for b in models
                if b in {"Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"}
            ),
            "body_centers": sorted(
                b
                for b in models
                if b
                not in {
                    "Mars",
                    "Jupiter",
                    "Saturn",
                    "Uranus",
                    "Neptune",
                    "Pluto",
                    "North Node",
                }
            ),
            "theoretical_points": ["North Node"] if "North Node" in models else [],
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
            "unavailable_reason": str(error),
            "unavailable_code": error.reason,
            "failed_sample": failed_sample,
        }
    except (ValueError, ImportError, AttributeError, RuntimeError) as error:
        return {
            "status": "unavailable",
            "method_id": "native_tt_seven_planet_event_history_v1",
            "constant_velocity_projection": False,
            "events": [],
            "unavailable_reason": str(error),
        }


def _sample_longitude(
    sampler: PlanetMotionSampler, sample: PlanetMotionSampler, planet: str, at: float
) -> float:
    fast = getattr(sampler, "_longitude_only", None)
    if callable(fast):
        value = fast(planet, at)
        if not math.isfinite(value):
            raise ValueError("Event sampler must supply finite longitude and speed")
        return normalize_angle(value)
    return sample(planet, at)["longitude"]
