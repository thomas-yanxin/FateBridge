"""Locate cardinal solar ingresses and exact planetary returns."""

from __future__ import annotations

import math
import re
from collections.abc import Iterator, Mapping, Sequence
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

from fatebridge.core.astro import runtime
from fatebridge.core.astro.ephemeris import fast_swe_call
from fatebridge.core.astro.iers_ut1 import active_ut1
from fatebridge.core.astro.physical_epoch import utc_from_tt
from fatebridge.core.astro.profiles import (
    ANALYTICAL_MEAN_NODE_MODEL,
    native_factor_model,
    physical_ephemeris_summary,
)
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.ephemeris_runtime import (
    EPHEMERIS_LOCK,
    _ensure_thread_ephemeris_path,
)
from fatebridge.core.ephemeris_runtime import ephemeris_call as _ORIG_EPHEMERIS_CALL
from fatebridge.core.ephemeris_runtime import (
    lock_ephemeris_configuration,
    native_ephemeris_errors,
    swe,
)
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.utils.civil_time import UTCCalendar, ZonedCalendar
from fatebridge.utils.errors import EphemerisSourceError

# Cardinal solar ingresses → (target tropical longitude, anchor month/day used to
# pick the right yearly crossing). Spring equinox is the standard mundane year.
CARDINAL_INGRESSES: dict[str, dict[str, float]] = {
    "春分": {"longitude": 0.0, "anchor_month": 3, "anchor_day": 20},
    "夏至": {"longitude": 90.0, "anchor_month": 6, "anchor_day": 21},
    "秋分": {"longitude": 180.0, "anchor_month": 9, "anchor_day": 23},
    "冬至": {"longitude": 270.0, "anchor_month": 12, "anchor_day": 22},
}
CARDINAL_INGRESS_LABELS: dict[str, str] = {
    "春分": "春分（白羊入宫·世俗年盘）",
    "夏至": "夏至（巨蟹入宫）",
    "秋分": "秋分（天秤入宫）",
    "冬至": "冬至（摩羯入宫）",
}

# Geocentric return periods (days) used to bound the contiguous scan window.
# Inner planets (Mercury/Venus) orbit the Sun and return geocentrically once per
# ~365.25 days (with retrograde loops resolved via station splitting).
RETURN_BODIES: dict[str, dict[str, object]] = {
    "Pluto": {"planet_id": 9, "period_days": 90560.0, "label": "冥王星返照"},
    "Neptune": {"planet_id": 8, "period_days": 60195.0, "label": "海王星返照"},
    "Uranus": {"planet_id": 7, "period_days": 30688.5, "label": "天王星返照"},
    "Chiron": {"planet_id": 15, "period_days": 18530.0, "label": "凯龙星返照"},
    "Saturn": {"planet_id": 6, "period_days": 10759.22, "label": "土星返照"},
    "North Node": {"planet_id": 10, "period_days": 6798.38, "label": "月交点返照"},
    "Jupiter": {"planet_id": 5, "period_days": 4332.59, "label": "木星返照"},
    "Mars": {"planet_id": 4, "period_days": 686.98, "label": "火星返照"},
    "Venus": {"planet_id": 3, "period_days": 365.25, "label": "金星返照"},
    "Mercury": {"planet_id": 2, "period_days": 365.25, "label": "水星返照"},
}


class EphemerisUnavailableError(RuntimeError):
    """Raised when swisseph is not importable and these tools cannot run."""


def _require_swe() -> None:
    if swe is None:  # pragma: no cover - exercised only without pyswisseph
        raise EphemerisUnavailableError(
            "swisseph (pyswisseph) is required for ingress / return solving"
        )


def _julian_day(moment: datetime | UTCCalendar) -> float:
    times = ephemeris_time(moment)
    if times.jd_tt is None:
        raise EphemerisUnavailableError("Swiss Ephemeris is required for TT events")
    return times.jd_tt


FileContext = tuple[tuple[str, float, float, int], ...]
MotionSample = tuple[float, float, int, FileContext]
MotionSource = tuple[int, frozenset[int]]


def _motion_source(sample: MotionSample) -> MotionSource:
    return sample[2], frozenset(
        edition for _, _, _, edition in sample[3] if edition > 0
    )


BODY_SOURCE_NAMES: dict[int, str] = {
    0: "Sun",
    1: "Moon",
    2: "Mercury",
    3: "Venus",
    4: "Mars",
    5: "Jupiter",
    6: "Saturn",
    7: "Uranus",
    8: "Neptune",
    9: "Pluto",
    10: "North Node",
    11: "True Node",
    15: "Chiron",
}
SYSTEM_BARYCENTER_BODIES: frozenset[str] = frozenset(
    {"Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"}
)
THEORETICAL_NODE_BODIES: frozenset[str] = frozenset({"North Node", "True Node"})
GOLDEN_RATIO_RECIPROCAL = (math.sqrt(5.0) - 1.0) / 2.0


def build_ephemeris_source_identity(
    planetary_models: Mapping[str, str],
    *,
    planetary_time_scale: str = "TT",
    angles_time_scale: str | None = None,
    earth_rotation_model: str | None = None,
    apparent_position_mode: str = "geocentric_apparent",
    frame: str = "tropical_true_ecliptic_of_date",
    engine_backend: str = "swisseph_api",
    derived_points: Sequence[str] = (),
    reference_point_kind: str | None = None,
    file_contexts: FileContext = (),
    event_search_backend: str | None = None,
    consistent_with_chart_ephemeris: bool | None = None,
) -> dict[str, object]:
    """Build explicit ephemeris source metadata shared across events and horary."""
    body_centers: list[str] = []
    system_barycenters: list[str] = []
    theoretical_points: list[str] = []
    for body, model in planetary_models.items():
        if body in THEORETICAL_NODE_BODIES or model == ANALYTICAL_MEAN_NODE_MODEL:
            theoretical_points.append(body)
        elif body in SYSTEM_BARYCENTER_BODIES:
            system_barycenters.append(body)
        else:
            body_centers.append(body)

    if planetary_models:
        summary = physical_ephemeris_summary(planetary_models)
        if summary == "none":
            summary = next(iter(planetary_models.values()))
    else:
        summary = "synthetic_subject"

    ephemeris_files: list[dict[str, object]] = []
    seen_files: set[tuple[str, float, float, int]] = set()
    de_editions: set[int] = set()
    for filename, start, end, edition in file_contexts:
        if not filename:
            continue
        basename = Path(filename).name
        file_key = (basename, start, end, edition)
        if file_key not in seen_files:
            seen_files.add(file_key)
            ephemeris_files.append(
                {
                    "filename": basename,
                    "start_jd_tt": start,
                    "end_jd_tt": end,
                    "de_number": edition,
                }
            )
        if edition > 0:
            de_editions.add(edition)

    reference_points: dict[str, object] = {
        "body_centers": body_centers,
        "system_barycenters": system_barycenters,
        "theoretical_points": theoretical_points,
        "derived_horizontal_points": list(derived_points),
        "center_body_correction_applied": False,
    }
    if reference_point_kind is not None:
        reference_points["reference_point_kind"] = reference_point_kind

    backend_payload: dict[str, object] = {
        "summary": summary,
        "engine_backend": engine_backend,
        "per_body_models": dict(planetary_models),
        "swisseph_version": str(swe.version) if swe is not None else None,
        "de_editions": sorted(de_editions),
        "ephemeris_files": ephemeris_files,
    }
    if event_search_backend is not None:
        backend_payload["event_search_backend"] = event_search_backend
    if consistent_with_chart_ephemeris is not None:
        backend_payload["consistent_with_chart_ephemeris"] = (
            consistent_with_chart_ephemeris
        )

    return {
        "schema_version": "fatebridge_ephemeris_source_identity_v1",
        "reference_points": reference_points,
        "time_scales": {
            "planetary_positions_and_events": planetary_time_scale,
            "angles_houses_and_horizon": angles_time_scale,
            "earth_rotation_model": earth_rotation_model,
            "canonical_root_axis": planetary_time_scale,
        },
        "apparent_position": {
            "mode": apparent_position_mode,
            "frame": frame,
            "light_time_and_aberration_applied": (
                apparent_position_mode == "geocentric_apparent"
            ),
        },
        "backend": backend_payload,
    }


def _body_source_identity(
    planet_id: int,
    returned_flags: int,
    file_contexts: FileContext,
    *,
    sidereal: bool = False,
) -> dict[str, object]:
    body = BODY_SOURCE_NAMES.get(planet_id, f"body_{planet_id}")
    model = native_factor_model(planet_id, returned_flags)
    if planet_id == 10:
        point_kind = "analytical_mean_node"
    elif planet_id == 11:
        point_kind = "osculating_true_node"
    elif body in SYSTEM_BARYCENTER_BODIES:
        point_kind = "system_barycenter"
    else:
        point_kind = "body_center"
    return build_ephemeris_source_identity(
        {body: model},
        frame="sidereal_lahiri" if sidereal else "tropical_true_ecliptic_of_date",
        reference_point_kind=point_kind,
        file_contexts=file_contexts,
    )


@dataclass(frozen=True)
class LongitudeCrossing:
    """One solved native IEEE TT point and its rounded civil display."""

    tt: TTInstant
    utc_datetime: datetime | None
    utc_label: str | None = None
    utc_is_leap_second: bool = False
    source_identity: dict[str, object] | None = None

    def require_utc_datetime(self) -> datetime:
        if self.utc_datetime is None:
            raise ValueError("Solved event has no Python-representable UTC datetime")
        return self.utc_datetime


@dataclass(frozen=True)
class ResolvedPlanetReturns:
    """Events partitioned by native TT; their labels never select a side."""

    past: tuple[LongitudeCrossing, ...]
    future: tuple[LongitudeCrossing, ...]
    source_identity: dict[str, object] | None = None


def _is_asteroid_body(planet_id: int) -> bool:
    chiron_id = getattr(swe, "CHIRON", 15) if swe is not None else 15
    ast_offset = getattr(swe, "AST_OFFSET", 10000) if swe is not None else 10000
    return planet_id >= chiron_id and (planet_id >= ast_offset or planet_id <= 20)


def _planet_motion(
    jd: float, planet_id: int, *, sidereal: bool = False, collect_files: bool = False
) -> MotionSample:
    if not math.isfinite(jd):
        raise ValueError("Julian day TT must be finite")
    _require_swe()
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    if sidereal:
        fast_swe_call("set_sid_mode", swe.SIDM_LAHIRI, 0.0, 0.0)
        flags |= swe.FLG_SIDEREAL
    try:
        result, returned = fast_swe_call("calc", jd, planet_id, flags)
    except native_ephemeris_errors() as exc:
        raw_message = str(exc)
        missing_match = re.search(r"'([^']+\.se1)'", raw_message)
        if missing_match is not None:
            raise EphemerisUnavailableError(
                f"Ephemeris data file '{missing_match.group(1)}' unavailable for body {planet_id}"
            ) from exc
        safe_message = raw_message.split(" in PATH ")[0]
        raise EphemerisUnavailableError(
            f"Swiss Ephemeris failed for body {planet_id}: {safe_message}"
        ) from exc
    disallowed = (
        swe.FLG_TRUEPOS
        | swe.FLG_NOABERR
        | swe.FLG_NOGDEFL
        | swe.FLG_BARYCTR
        | swe.FLG_HELCTR
        | getattr(swe, "FLG_CENTER_BODY", 1048576)
    )
    if (
        returned < 0
        or not (returned & swe.FLG_SPEED)
        or bool(returned & swe.FLG_SIDEREAL) != sidereal
        or bool(returned & disallowed)
        or not all(math.isfinite(result[index]) for index in (0, 3))
    ):
        raise EphemerisUnavailableError(
            f"Astronomical event ephemeris returned unexpected coordinate flags ({returned}) for body {planet_id}"
        )
    contexts: tuple[tuple[str, float, float, int], ...] = ()
    if (
        collect_files
        and planet_id != swe.MEAN_NODE
        and (returned & (swe.FLG_SWIEPH | swe.FLG_JPLEPH))
    ):
        slots: tuple[int, ...]
        if returned & swe.FLG_JPLEPH:
            slots = (0, 2) if _is_asteroid_body(planet_id) else (0,)
        else:
            slots = (0, 1, 2) if _is_asteroid_body(planet_id) else (0, 1)
        items: list[tuple[str, float, float, int]] = []
        for slot in slots:
            filename, start, end, edition = swe.get_current_file_data(slot)
            items.append((str(filename), float(start), float(end), int(edition)))
        contexts = tuple(items)
    return float(result[0] % 360.0), float(result[3]), int(returned), contexts


_ORIG_PLANET_MOTION = _planet_motion
_NULL_LOCK = nullcontext()


def _wrapped_diff(longitude: float, target: float) -> float:
    """Signed residual in [-180,180], retaining small nonzero root offsets."""
    return math.remainder(longitude - target, 360.0)


def _longitude_crossings(
    planet_id: int,
    target_longitude: float,
    start_jd: float,
    end_jd: float,
    step_days: float,
    *,
    sidereal: bool = False,
    expected_source: MotionSource | None = None,
    reverse: bool = False,
) -> Iterator[LongitudeCrossing]:
    """Yield refined crossings in the scan direction on the native TT axis."""
    if not math.isfinite(step_days) or step_days <= 0:
        raise ValueError("Longitude-crossing scan step must be finite and positive")
    cursor, limit = (end_jd, start_jd) if reverse else (start_jd, end_jd)
    collect_files = bool(expected_source and expected_source[1])
    fast_direct = (
        _planet_motion is _ORIG_PLANET_MOTION
        and runtime.ephemeris_call is _ORIG_EPHEMERIS_CALL
        and configured_jpl_file() is None
        and active_ut1.get() is None
        and runtime.swe is not None
        and not collect_files
    )
    swe_mod = runtime.swe
    flags = (
        (
            (swe_mod.FLG_SWIEPH | swe_mod.FLG_SPEED)
            | (swe_mod.FLG_SIDEREAL if sidereal else 0)
        )
        if swe_mod is not None
        else 0
    )

    def _motion_fast(at_jd: float) -> MotionSample:
        if fast_direct:
            res, ret = swe_mod.calc(at_jd, planet_id, flags)
            if ret < 0:
                return _planet_motion(
                    at_jd, planet_id, sidereal=sidereal, collect_files=False
                )
            return float(res[0] % 360.0), float(res[3]), int(ret), ()
        return _planet_motion(
            at_jd, planet_id, sidereal=sidereal, collect_files=collect_files
        )

    lock_ctx = EPHEMERIS_LOCK if fast_direct else _NULL_LOCK
    with lock_ctx:
        if fast_direct:
            _ensure_thread_ephemeris_path()
            if sidereal:
                swe_mod.set_sid_mode(swe_mod.SIDM_LAHIRI, 0.0, 0.0)
        sample = _motion_fast(cursor)
        if expected_source is not None and _motion_source(sample) != expected_source:
            raise EphemerisSourceError("model_changed")
        last_point: TTInstant | None = None
        while cursor != limit:
            following = (
                max(cursor - step_days, limit)
                if reverse
                else min(cursor + step_days, limit)
            )
            if following == cursor:
                raise ValueError("Longitude-crossing scan step does not advance TT")
            next_sample = _motion_fast(following)
            if (
                expected_source is not None
                and _motion_source(next_sample) != expected_source
            ):
                raise EphemerisSourceError("model_changed")
            if reverse:
                previous_jd, previous, jd, current = (
                    following,
                    next_sample,
                    cursor,
                    sample,
                )
            else:
                previous_jd, previous, jd, current = (
                    cursor,
                    sample,
                    following,
                    next_sample,
                )

            def same_source(at: float) -> MotionSample:
                value = _motion_fast(at)
                if value[2:] != current[2:]:
                    raise EphemerisSourceError("model_changed")
                return value

            knots = [(previous_jd, previous[0])]
            near_target = (
                min(
                    abs(_wrapped_diff(previous[0], target_longitude)),
                    abs(_wrapped_diff(current[0], target_longitude)),
                )
                <= 8.0
            )
            if near_target and (
                previous[1] * current[1] < 0
                or ((previous[1] == 0.0) != (current[1] == 0.0))
            ):
                if previous[2:] != current[2:]:
                    raise EphemerisSourceError("model_changed")
                if previous[1] == 0.0:
                    turn = previous_jd
                elif current[1] == 0.0:
                    turn = jd
                else:
                    low, high = previous_jd, jd
                    for _ in range(64):
                        mid = (low + high) / 2
                        if mid in (low, high):
                            break
                        sample_mid = same_source(mid)
                        if sample_mid[1] == 0:
                            low = high = mid
                            break
                        if (sample_mid[1] < 0) == (previous[1] < 0):
                            low = mid
                        else:
                            high = mid
                    turn = (low + high) / 2
                split_jds: set[float] = set()
                if previous_jd < turn < jd:
                    split_jds.add(turn)
                a, b = previous_jd, jd
                direction = 1 if previous[1] > 0.0 or current[1] < 0.0 else -1
                turn_lon = same_source(turn)[0]

                def altitude(at: float) -> tuple[int, float]:
                    longitude = same_source(at)[0]
                    delta = longitude - turn_lon
                    wrap = int(delta < -180) - int(delta > 180)
                    return direction * wrap, direction * longitude

                turn_score = (0, direction * turn_lon)
                c = b - GOLDEN_RATIO_RECIPROCAL * (b - a)
                d = a + GOLDEN_RATIO_RECIPROCAL * (b - a)
                fc, fd = altitude(c), altitude(d)
                best = max((turn_score, turn), (fc, c), (fd, d))
                for _ in range(96):
                    if b - a <= 4 * math.ulp(max(abs(a), abs(b))) or c >= d:
                        break
                    if fc < fd:
                        a, c, fc = c, d, fd
                        d = a + GOLDEN_RATIO_RECIPROCAL * (b - a)
                        fd = altitude(d)
                    else:
                        b, d, fd = d, c, fc
                        c = b - GOLDEN_RATIO_RECIPROCAL * (b - a)
                        fc = altitude(c)
                    best = max(best, (fc, c), (fd, d))
                for _ in range(8):
                    if a > b:
                        break
                    best = max(best, (altitude(a), a))
                    a = math.nextafter(a, math.inf)
                extremum_score, extremum = best
                if extremum_score > turn_score and previous_jd < extremum < jd:
                    split_jds.add(extremum)
                for split_jd in sorted(split_jds):
                    knots.append((split_jd, same_source(split_jd)[0]))
            knots.append((jd, current[0]))
            cells = list(zip(knots, knots[1:]))
            if reverse:
                cells.reverse()
            for (left_jd, left_longitude), (right_jd, right_longitude) in cells:
                left_diff = _wrapped_diff(left_longitude, target_longitude)
                right_diff = _wrapped_diff(right_longitude, target_longitude)
                if (
                    left_diff <= 0.0 <= right_diff or right_diff <= 0.0 <= left_diff
                ) and abs(right_diff - left_diff) < 90.0:
                    if previous[2] != current[2]:
                        raise EphemerisSourceError("model_changed")
                    if fast_direct:
                        mid_res, mid_ret = swe_mod.calc(
                            (left_jd + right_jd) / 2.0, planet_id, flags
                        )
                        contexts: FileContext = ()
                        if planet_id != swe_mod.MEAN_NODE and (
                            mid_ret & (swe_mod.FLG_SWIEPH | swe_mod.FLG_JPLEPH)
                        ):
                            slots = (
                                ((0, 2) if _is_asteroid_body(planet_id) else (0,))
                                if (mid_ret & swe_mod.FLG_JPLEPH)
                                else (
                                    (0, 1, 2)
                                    if _is_asteroid_body(planet_id)
                                    else (0, 1)
                                )
                            )
                            contexts = tuple(
                                (str(fn), float(st), float(en), int(ed))
                                for fn, st, en, ed in (
                                    swe_mod.get_current_file_data(s) for s in slots
                                )
                            )
                        source_id = _body_source_identity(
                            planet_id, int(mid_ret), contexts, sidereal=sidereal
                        )
                    else:
                        final_sample = _planet_motion(
                            (left_jd + right_jd) / 2.0,
                            planet_id,
                            sidereal=sidereal,
                            collect_files=True,
                        )
                        source_id = _body_source_identity(
                            planet_id,
                            final_sample[2],
                            final_sample[3],
                            sidereal=sidereal,
                        )
                    low, high = left_jd, right_jd
                    low_negative = left_diff < 0.0 if left_diff != 0 else right_diff > 0
                    if left_diff == 0:
                        high = low
                    elif right_diff == 0:
                        low = high
                    for _ in range(64):
                        mid = (low + high) / 2.0
                        if mid in (low, high):
                            break
                        cand = mid
                        if _ % 3 != 2:
                            d_low = _wrapped_diff(same_source(low)[0], target_longitude)
                            d_high = _wrapped_diff(
                                same_source(high)[0], target_longitude
                            )
                            denom = d_high - d_low
                            if denom != 0.0 and math.isfinite(denom):
                                sec = low - d_low * (high - low) / denom
                                if low < sec < high:
                                    cand = sec
                        mid_diff = _wrapped_diff(
                            same_source(cand)[0],
                            target_longitude,
                        )
                        if mid_diff == 0.0:
                            low = high = cand
                            break
                        if (mid_diff < 0.0) == low_negative:
                            low = cand
                        else:
                            high = cand
                    point = TTInstant.from_float(high)
                    if point == last_point:
                        continue
                    label, moment, leap = utc_from_tt(point, legacy_pre_utc=True)
                    original_display = label, moment, leap
                    for _ in range(8):
                        if moment is not None:
                            recovered = _julian_day(moment)
                        elif label is not None and not leap:
                            recovered = _julian_day(
                                ZonedCalendar.from_isoformat(label).utc
                            )
                        else:
                            break
                        value = _wrapped_diff(
                            same_source(recovered)[0], target_longitude
                        )
                        if value >= 0.0 if low_negative else value <= 0.0:
                            break
                        following = math.nextafter(high, math.inf)
                        following_diff = _wrapped_diff(
                            same_source(following)[0], target_longitude
                        )
                        if (
                            following_diff < 0.0
                            if low_negative
                            else following_diff > 0.0
                        ):
                            label, moment, leap = original_display
                            break
                        high = following
                        label, moment, leap = utc_from_tt(
                            TTInstant.from_float(high), legacy_pre_utc=True
                        )
                    else:
                        raise EphemerisUnavailableError(
                            "Civil crossing instant could not preserve its crossing side"
                        )
                    last_point = point
                    yield LongitudeCrossing(
                        point, moment, label, leap, source_identity=source_id
                    )
            cursor, sample = following, next_sample


def resolve_longitude_crossing(
    planet_id: int,
    target_longitude: float,
    anchor_utc: datetime,
    *,
    window_days: float = 40.0,
    step_days: float = 1.0,
    sidereal: bool = False,
) -> LongitudeCrossing | None:
    """Nearest observed crossing in a finite TT scan, in either direction.

    Bisection refines every observed crossing before choosing the nearest one;
    scan-cell midpoints are not substitutes for actual event distances.
    """
    _require_swe()
    anchor_jd = _julian_day(anchor_utc)
    crossings = _longitude_crossings(
        planet_id,
        target_longitude,
        anchor_jd - window_days,
        anchor_jd + window_days,
        step_days,
        sidereal=sidereal,
    )
    anchor = Fraction(anchor_jd)
    return min(crossings, key=lambda at: abs(at.tt.days - anchor), default=None)


def find_longitude_crossing_utc(
    planet_id: int,
    target_longitude: float,
    anchor_utc: datetime,
    *,
    window_days: float = 40.0,
    step_days: float = 1.0,
    sidereal: bool = False,
) -> datetime | None:
    """Civil display adapter for the nearest native TT crossing."""
    crossing = resolve_longitude_crossing(
        planet_id,
        target_longitude,
        anchor_utc,
        window_days=window_days,
        step_days=step_days,
        sidereal=sidereal,
    )
    return crossing.require_utc_datetime() if crossing is not None else None


def planet_longitude_at_utc(
    planet_id: int,
    moment: datetime | UTCCalendar,
    *,
    sidereal: bool = False,
) -> float:
    """Tropical or native Lahiri longitude at a civil instant, used as natal anchor."""
    return planet_motion_at_utc(planet_id, moment, sidereal=sidereal)[0]


def planet_motion_at_utc(
    planet_id: int, moment: datetime | UTCCalendar, *, sidereal: bool = False
) -> MotionSample:
    """Native motion and returned source flags at the return anchor."""
    return _planet_motion(_julian_day(moment), planet_id, sidereal=sidereal)


def resolve_cardinal_ingress(year: int, term: str) -> LongitudeCrossing:
    """Native TT crossing and display for the given yearly cardinal ingress."""
    _require_swe()
    spec = CARDINAL_INGRESSES[term]
    anchor = datetime(
        year,
        int(spec["anchor_month"]),
        int(spec["anchor_day"]),
        12,
        0,
        tzinfo=timezone.utc,
    )
    crossing = resolve_longitude_crossing(swe.SUN, float(spec["longitude"]), anchor)
    if crossing is None:  # pragma: no cover - the Sun always crosses within ±40d
        raise EphemerisUnavailableError(
            f"could not resolve {term} ingress for year {year}"
        )
    return crossing


def find_cardinal_ingress_utc(year: int, term: str) -> datetime:
    """UTC display of the given cardinal ingress in the given year."""
    return resolve_cardinal_ingress(year, term).require_utc_datetime()


def resolve_planet_returns(
    planet_id: int,
    natal_longitude: float,
    *,
    period_days: float,
    reference_utc: datetime | UTCCalendar,
    past: int = 1,
    future: int = 1,
    sidereal: bool = False,
    natal_motion: MotionSample | None = None,
    not_before_utc: datetime | UTCCalendar | None = None,
    not_before_tt: float | None = None,
) -> ResolvedPlanetReturns:
    """Return the requested nearest past/future crossings in a bounded scan.

    When not_before_utc or not_before_tt is provided (typically the birth instant),
    past returns never extend prior to birth + 1 minute.
    """
    _require_swe()
    if not math.isfinite(period_days) or period_days <= 0.0:
        raise ValueError("period_days must be finite and positive")
    if past < 0 or future < 0:
        raise ValueError("past and future return counts must be non-negative")
    reference_jd = _julian_day(reference_utc)
    reference = Fraction(reference_jd)
    min_past_jd: float | None = (
        _julian_day(not_before_utc) if not_before_utc is not None else not_before_tt
    )
    expected_source = (
        _motion_source(
            natal_motion
            if natal_motion is not None
            else _planet_motion(
                reference_jd, planet_id, sidereal=sidereal, collect_files=True
            )
        )
        if past or future
        else None
    )
    if period_days <= 100.0:
        step_days = min(1.0, max(1e-3, period_days / 4.0))
    elif period_days <= 1000.0:
        step_days = 5.0
    elif period_days <= 5000.0:
        step_days = 25.0
    elif period_days <= 12000.0:
        step_days = 45.0
    elif period_days <= 25000.0:
        step_days = 120.0
    elif period_days <= 40000.0:
        step_days = 180.0
    else:
        step_days = 280.0
    selected: list[tuple[LongitudeCrossing, ...]] = []
    observed_identity: dict[str, object] | None = None
    for direction, count in ((-1, past), (1, future)):
        found: list[LongitudeCrossing] = []
        if count:
            limit = reference_jd + direction * (
                period_days * (1.25 * count + 0.5) + 15.0
            )
            if direction < 0 and min_past_jd is not None:
                floor_jd = min_past_jd + 1.0 / 1440.0
                if reference_jd <= floor_jd:
                    selected.append(())
                    continue
                limit = max(limit, floor_jd)
            for crossing in _longitude_crossings(
                planet_id,
                natal_longitude,
                min(reference_jd, limit),
                max(reference_jd, limit),
                step_days,
                sidereal=sidereal,
                expected_source=expected_source,
                reverse=direction < 0,
            ):
                if direction > 0 and crossing.tt.days == reference:
                    continue
                if (
                    direction < 0
                    and min_past_jd is not None
                    and crossing.tt.days <= Fraction(min_past_jd) + Fraction(1, 1440)
                ):
                    continue
                if observed_identity is None:
                    observed_identity = crossing.source_identity
                found.append(crossing)
                if len(found) == count:
                    break
        selected.append(tuple(reversed(found) if direction < 0 else found))
    return ResolvedPlanetReturns(selected[0], selected[1], observed_identity)


def find_planet_returns(
    planet_id: int,
    natal_longitude: float,
    *,
    period_days: float,
    reference_utc: datetime,
    past: int = 1,
    future: int = 1,
    sidereal: bool = False,
    not_before_utc: datetime | UTCCalendar | None = None,
) -> list[datetime]:
    """Civil displays of native TT-selected past and future returns."""
    resolved = resolve_planet_returns(
        planet_id,
        natal_longitude,
        period_days=period_days,
        reference_utc=reference_utc,
        past=past,
        future=future,
        sidereal=sidereal,
        not_before_utc=not_before_utc,
    )
    return [at.require_utc_datetime() for at in (*resolved.past, *resolved.future)]


__all__ = [
    "BODY_SOURCE_NAMES",
    "CARDINAL_INGRESSES",
    "CARDINAL_INGRESS_LABELS",
    "RETURN_BODIES",
    "EphemerisUnavailableError",
    "LongitudeCrossing",
    "ResolvedPlanetReturns",
    "build_ephemeris_source_identity",
    "resolve_longitude_crossing",
    "resolve_cardinal_ingress",
    "resolve_planet_returns",
    "find_longitude_crossing_utc",
    "find_cardinal_ingress_utc",
    "find_planet_returns",
    "planet_longitude_at_utc",
    "planet_motion_at_utc",
]
