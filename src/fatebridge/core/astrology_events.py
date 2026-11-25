"""
FateBridge western *event* techniques — ephemeris moment-solving.

Unlike the ``astrology_lifespan`` family (pure functions of a frozen natal
chart), these techniques locate real astronomical *moments* and read the sky at
them:

* **世俗入宫盘 (mundane ingress)** — the precise instant the Sun reaches a
  cardinal point (0°/90°/180°/270°) in a given year, i.e. the spring equinox,
  summer solstice, autumn equinox, or winter solstice.
* **多重回归 (extra returns)** — the instants a slow body (Saturn / Jupiter /
  lunar node) returns to its natal longitude, around an analysis date.

This module owns the swisseph root-finding. Casting the chart at a solved
moment and rendering output is the
service layer's job, mirroring the rest of the western tools.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fatebridge.core.astro.time_scales import datetime_from_tt, ephemeris_time
from fatebridge.core.ephemeris_runtime import (
    ephemeris_call,
    lock_ephemeris_configuration,
    swe,
)
from fatebridge.utils.errors import EphemerisSourceError

# Cardinal solar ingresses → (target tropical longitude, anchor month/day used to
# pick the right yearly crossing). Spring equinox is the standard mundane year.
CARDINAL_INGRESSES: Dict[str, Dict[str, float]] = {
    "春分": {"longitude": 0.0, "anchor_month": 3, "anchor_day": 20},
    "夏至": {"longitude": 90.0, "anchor_month": 6, "anchor_day": 21},
    "秋分": {"longitude": 180.0, "anchor_month": 9, "anchor_day": 23},
    "冬至": {"longitude": 270.0, "anchor_month": 12, "anchor_day": 22},
}
CARDINAL_INGRESS_LABELS: Dict[str, str] = {
    "春分": "春分（白羊入宫·世俗年盘）",
    "夏至": "夏至（巨蟹入宫）",
    "秋分": "秋分（天秤入宫）",
    "冬至": "冬至（摩羯入宫）",
}

# Synodic-ish return periods (days) for slow bodies, used only to seed the search
# window — the bisection below pins the exact crossing regardless.
RETURN_BODIES: Dict[str, Dict[str, object]] = {
    "Saturn": {"planet_id": 6, "period_days": 10759.22, "label": "土星返照"},
    "Jupiter": {"planet_id": 5, "period_days": 4332.59, "label": "木星返照"},
    "North Node": {"planet_id": 10, "period_days": 6798.38, "label": "月交点返照"},
}


class EphemerisUnavailableError(RuntimeError):
    """Raised when swisseph is not importable and these tools cannot run."""


def _require_swe() -> None:
    if swe is None:  # pragma: no cover - exercised only without pyswisseph
        raise EphemerisUnavailableError(
            "swisseph (pyswisseph) is required for ingress / return solving"
        )


def _julian_day(moment: datetime) -> float:
    times = ephemeris_time(moment)
    if times.jd_tt is None:
        raise EphemerisUnavailableError("Swiss Ephemeris is required for TT events")
    return times.jd_tt


FileContext = tuple[tuple[str, float, float, int], ...]
MotionSample = tuple[float, float, int, FileContext]


def _planet_motion(
    jd: float, planet_id: int, *, sidereal: bool = False
) -> MotionSample:
    with lock_ephemeris_configuration():
        flags = swe.FLG_SWIEPH | swe.FLG_SPEED
        if sidereal:
            swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
            flags |= swe.FLG_SIDEREAL
        result, returned = ephemeris_call("calc", jd, planet_id, flags)
        if (
            returned < 0
            or not returned & swe.FLG_SPEED
            or not all(math.isfinite(result[index]) for index in (0, 3))
        ):
            raise ValueError("Astronomical event ephemeris failed")
        contexts: list[tuple[str, float, float, int]] = []
        if returned & (swe.FLG_SWIEPH | swe.FLG_JPLEPH):
            for slot in ((0,) if returned & swe.FLG_JPLEPH else (0, 1)):
                filename, start, end, edition = swe.get_current_file_data(slot)
                contexts.append((str(filename), float(start), float(end), int(edition)))
    return float(result[0] % 360.0), float(result[3]), int(returned), tuple(contexts)


def _wrapped_diff(longitude: float, target: float) -> float:
    """Signed residual in [-180,180], retaining small nonzero root offsets."""
    return math.remainder(longitude - target, 360.0)


def _longitude_crossings_tt(
    planet_id: int,
    target_longitude: float,
    start_jd: float,
    end_jd: float,
    step_days: float,
    *,
    sidereal: bool = False,
    expected_flags: int | None = None,
) -> List[float]:
    """Solve observed longitude crossings/contacts on the native float TT axis."""
    roots: List[float] = []
    previous_jd = start_jd
    previous = _planet_motion(previous_jd, planet_id, sidereal=sidereal)
    if expected_flags is None:
        expected_flags = previous[2]
    if previous[2] != expected_flags:
        raise EphemerisSourceError("model_changed")
    while previous_jd < end_jd:
        jd = min(previous_jd + step_days, end_jd)
        current = _planet_motion(jd, planet_id, sidereal=sidereal)
        if current[2] != expected_flags:
            raise EphemerisSourceError("model_changed")

        def same_source(at: float) -> MotionSample:
            value = _planet_motion(at, planet_id, sidereal=sidereal)
            if value[2:] != current[2:]:
                raise EphemerisSourceError("model_changed")
            return value

        knots = [(previous_jd, previous[0])]
        if previous[1] * current[1] < 0 or (
            (previous[1] == 0.0) != (current[1] == 0.0)
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
                    sample = same_source(mid)
                    if sample[1] == 0:
                        low = high = mid
                        break
                    if (sample[1] < 0) == (previous[1] < 0):
                        low = mid
                    else:
                        high = mid
                turn = (low + high) / 2
            splits = {turn} if previous_jd < turn < jd else set()
            # Speed brackets guide a finite cell-wide probe of actual longitude.
            # Only a strict coordinate improvement adds an extremum candidate;
            # no angular tolerance turns a nearly reached target into a contact.
            a, b = previous_jd, jd
            maximize = 1.0 if previous[1] > 0 or current[1] < 0 else -1.0
            ratio = (math.sqrt(5.0) - 1.0) / 2.0
            c, d = b - ratio * (b - a), a + ratio * (b - a)
            fc = maximize * _wrapped_diff(same_source(c)[0], target_longitude)
            fd = maximize * _wrapped_diff(same_source(d)[0], target_longitude)
            best = max((fc, c), (fd, d))
            for _ in range(96):
                if b - a <= 4 * math.ulp(max(abs(a), abs(b))) or c >= d:
                    break
                if fc < fd:
                    a, c, fc = c, d, fd
                    d = a + ratio * (b - a)
                    fd = maximize * _wrapped_diff(same_source(d)[0], target_longitude)
                else:
                    b, d, fd = d, c, fc
                    c = b - ratio * (b - a)
                    fc = maximize * _wrapped_diff(same_source(c)[0], target_longitude)
                best = max(best, (fc, c), (fd, d))
            # At physical TT epochs the final bracket contains at most a few
            # floats. Visit them all: a grazing contact can occupy just one.
            probe = a
            for _ in range(8):
                if probe > b:
                    break
                best = max(
                    best,
                    (
                        maximize
                        * _wrapped_diff(same_source(probe)[0], target_longitude),
                        probe,
                    ),
                )
                probe = math.nextafter(probe, math.inf)
            extremum = best[1]
            if (
                previous_jd < extremum < jd
                and maximize
                * _wrapped_diff(same_source(extremum)[0], same_source(turn)[0])
                > 0
            ):
                splits.add(extremum)
            knots.extend((at, same_source(at)[0]) for at in sorted(splits))
        knots.append((jd, current[0]))
        for (left_jd, left_longitude), (right_jd, right_longitude) in zip(
            knots, knots[1:]
        ):
            left_diff = _wrapped_diff(left_longitude, target_longitude)
            right_diff = _wrapped_diff(right_longitude, target_longitude)
            if (
                left_diff <= 0.0 <= right_diff or right_diff <= 0.0 <= left_diff
            ) and abs(right_diff - left_diff) < 90.0:
                if previous[2:] != current[2:]:
                    raise EphemerisSourceError("model_changed")
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
                    mid_negative = (
                        _wrapped_diff(
                            same_source(mid)[0],
                            target_longitude,
                        )
                        < 0.0
                    )
                    if mid_negative == low_negative:
                        low = mid
                    else:
                        high = mid
                if not roots or high != roots[-1]:
                    roots.append(high)
        previous_jd, previous = jd, current
    return roots


def _longitude_crossings_utc(
    planet_id: int,
    target_longitude: float,
    start_jd: float,
    end_jd: float,
    step_days: float,
    *,
    sidereal: bool = False,
) -> List[datetime]:
    """Civil display adapter; root selection and deduplication happen in TT."""
    return [
        datetime_from_tt(at)
        for at in _longitude_crossings_tt(
            planet_id, target_longitude, start_jd, end_jd, step_days, sidereal=sidereal
        )
    ]


def find_longitude_crossing_utc(
    planet_id: int,
    target_longitude: float,
    anchor_utc: datetime,
    *,
    window_days: float = 40.0,
    step_days: float = 1.0,
    sidereal: bool = False,
) -> Optional[datetime]:
    """Nearest observed crossing in a finite TT scan, in either direction.

    Bisection refines every observed crossing before choosing the nearest one;
    scan-cell midpoints are not substitutes for actual event distances.
    """
    _require_swe()
    anchor_jd = _julian_day(anchor_utc)
    roots = _longitude_crossings_tt(
        planet_id,
        target_longitude,
        anchor_jd - window_days,
        anchor_jd + window_days,
        step_days,
        sidereal=sidereal,
    )
    nearest = min(roots, key=lambda at: abs(at - anchor_jd), default=None)
    if nearest is None:
        return None
    # Preserve the ingress chart's crossing side without changing which TT root
    # was selected. Ordinary civil labels can round to the preceding TT sample.
    native = _planet_motion(nearest, planet_id, sidereal=sidereal)
    candidate = nearest
    original = datetime_from_tt(nearest)
    for _ in range(8):
        moment = datetime_from_tt(candidate)
        recovered = _planet_motion(_julian_day(moment), planet_id, sidereal=sidereal)
        if recovered[2:] != native[2:]:
            raise EphemerisSourceError("model_changed")
        residual = _wrapped_diff(recovered[0], target_longitude)
        if residual == 0.0 or residual * native[1] > 0.0:
            return moment
        following = math.nextafter(candidate, math.inf)
        sample = _planet_motion(following, planet_id, sidereal=sidereal)
        if sample[2:] != native[2:]:
            raise EphemerisSourceError("model_changed")
        # An exact grazing contact may have no civil label on its root. Keep
        # its display rather than move away from the independently solved point.
        if _wrapped_diff(sample[0], target_longitude) * native[1] <= 0.0:
            return original
        candidate = following
    raise EphemerisUnavailableError(
        "Civil crossing instant could not preserve its crossing side"
    )


def planet_longitude_at_utc(
    planet_id: int, moment: datetime, *, sidereal: bool = False
) -> float:
    """Tropical or native Lahiri longitude at a civil instant, used as natal anchor."""
    return planet_motion_at_utc(planet_id, moment, sidereal=sidereal)[0]


def planet_motion_at_utc(
    planet_id: int, moment: datetime, *, sidereal: bool = False
) -> MotionSample:
    """Native coordinates and source for a natal anchor used by return solving."""
    _require_swe()
    return _planet_motion(_julian_day(moment), planet_id, sidereal=sidereal)


def find_cardinal_ingress_utc(year: int, term: str) -> datetime:
    """UTC moment of the given cardinal ingress (春分/夏至/秋分/冬至) in ``year``."""
    spec = CARDINAL_INGRESSES[term]
    anchor = datetime(
        year,
        int(spec["anchor_month"]),
        int(spec["anchor_day"]),
        12,
        0,
        tzinfo=timezone.utc,
    )
    moment = find_longitude_crossing_utc(swe.SUN, float(spec["longitude"]), anchor)
    if moment is None:  # pragma: no cover - the Sun always crosses within ±40d
        raise EphemerisUnavailableError(
            f"could not resolve {term} ingress for year {year}"
        )
    return moment


def resolve_planet_returns(
    planet_id: int,
    natal_longitude: float,
    *,
    period_days: float,
    reference_utc: datetime,
    past: int = 1,
    future: int = 1,
    sidereal: bool = False,
    expected_flags: int | None = None,
) -> tuple[List[datetime], List[datetime]]:
    """Partition the requested roots by native TT before civil display.

    One mean-period seed can choose a remote revolution while skipping a closer
    retrograde recrossing. Scan one contiguous window instead, retaining each
    observed event before selecting either side of the reference. The daily
    scan is a finite numerical search, not an interval-wide completeness proof
    for unresolved grazing contacts near a station.
    """
    _require_swe()
    reference_jd = _julian_day(reference_utc)
    if expected_flags is None:
        expected_flags = _planet_motion(reference_jd, planet_id, sidereal=sidereal)[2]
    selected: list[List[datetime]] = []
    for direction, count in ((-1, past), (1, future)):
        found: set[float] = set()
        cursor = reference_jd
        limit = reference_jd + direction * (period_days * (count + 0.5) + 5.0)
        while len(found) < count and cursor != limit:
            # Advance contiguously from the reference, stopping as soon as the
            # requested side is populated. Annual chunks avoid solving remote
            # revolutions that cannot affect the nearest returned event.
            following = (
                max(limit, cursor - min(period_days, 365.25))
                if direction < 0
                else min(limit, cursor + min(period_days, 365.25))
            )
            roots = _longitude_crossings_tt(
                planet_id,
                natal_longitude,
                min(cursor, following),
                max(cursor, following),
                min(1.0, period_days / 360.0),
                sidereal=sidereal,
                expected_flags=expected_flags,
            )
            found.update(
                at
                for at in roots
                if (at <= reference_jd if direction < 0 else at > reference_jd)
            )
            cursor = following
        ordered = sorted(found)
        chosen = ordered[-count:] if direction < 0 and count else ordered[:count]
        selected.append([datetime_from_tt(at) for at in chosen])
    return selected[0], selected[1]


def find_planet_returns(
    planet_id: int,
    natal_longitude: float,
    *,
    period_days: float,
    reference_utc: datetime,
    past: int = 1,
    future: int = 1,
    sidereal: bool = False,
) -> List[datetime]:
    """Civil display adapter for roots already selected on their native TT axis."""
    previous, following = resolve_planet_returns(
        planet_id,
        natal_longitude,
        period_days=period_days,
        reference_utc=reference_utc,
        past=past,
        future=future,
        sidereal=sidereal,
    )
    return previous + following


__all__ = [
    "CARDINAL_INGRESSES",
    "CARDINAL_INGRESS_LABELS",
    "RETURN_BODIES",
    "EphemerisUnavailableError",
    "find_longitude_crossing_utc",
    "find_cardinal_ingress_utc",
    "find_planet_returns",
    "resolve_planet_returns",
    "planet_longitude_at_utc",
    "planet_motion_at_utc",
]
