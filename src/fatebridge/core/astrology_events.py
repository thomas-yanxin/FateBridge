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

This module owns only the swisseph root-finding (it imports nothing from
kerykeion). Casting the chart at a solved moment and rendering output is the
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


def _planet_longitude(jd: float, planet_id: int, *, sidereal: bool = False) -> float:
    return _planet_motion(jd, planet_id, sidereal=sidereal)[0]


def _jd_to_utc(jd: float) -> datetime:
    return datetime_from_tt(jd)


def _wrapped_diff(longitude: float, target: float) -> float:
    """Signed residual in [-180,180], retaining small nonzero root offsets."""
    return math.remainder(longitude - target, 360.0)


def _longitude_crossings_utc(
    planet_id: int,
    target_longitude: float,
    start_jd: float,
    end_jd: float,
    step_days: float,
    *,
    sidereal: bool = False,
) -> List[datetime]:
    """Scan the whole finite TT window and refine each observed crossing."""
    moments: List[datetime] = []
    previous_jd = start_jd
    previous = _planet_motion(previous_jd, planet_id, sidereal=sidereal)
    while previous_jd < end_jd:
        jd = min(previous_jd + step_days, end_jd)
        current = _planet_motion(jd, planet_id, sidereal=sidereal)

        def same_source(at: float) -> MotionSample:
            value = _planet_motion(at, planet_id, sidereal=sidereal)
            if value[2:] != current[2:]:
                raise EphemerisSourceError("model_changed")
            return value

        knots = [(previous_jd, previous[0])]
        if previous[1] * current[1] < 0:
            if previous[2:] != current[2:]:
                raise EphemerisSourceError("model_changed")
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
            # Native speed only locates a candidate split. The actual
            # longitude on both sides must still bracket each returned root.
            knots.append((turn, same_source(turn)[0]))
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
                # Preserve the post-crossing side through civil-time quantization.
                for _ in range(8):
                    moment = _jd_to_utc(high)
                    recovered = _julian_day(moment)
                    value = _wrapped_diff(
                        same_source(recovered)[0],
                        target_longitude,
                    )
                    on_crossed_side = value >= 0.0 if low_negative else value <= 0.0
                    if on_crossed_side:
                        if not moments or moment != moments[-1]:
                            moments.append(moment)
                        break
                    high = math.nextafter(high, math.inf)
                else:
                    raise EphemerisUnavailableError(
                        "Civil crossing instant could not preserve its crossing side"
                    )
        previous_jd, previous = jd, current
    return moments


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
    moments = _longitude_crossings_utc(
        planet_id,
        target_longitude,
        anchor_jd - window_days,
        anchor_jd + window_days,
        step_days,
        sidereal=sidereal,
    )
    return min(moments, key=lambda at: abs(at - anchor_utc), default=None)


def planet_longitude_at_utc(
    planet_id: int, moment: datetime, *, sidereal: bool = False
) -> float:
    """Tropical or native Lahiri longitude at a civil instant, used as natal anchor."""
    _require_swe()
    return _planet_longitude(_julian_day(moment), planet_id, sidereal=sidereal)


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
    """Return the requested nearest past/future crossings in a bounded scan.

    One mean-period seed can choose a remote revolution while skipping a closer
    retrograde recrossing. Scan one contiguous window instead, retaining each
    observed event before selecting either side of the reference. The daily
    scan is a finite numerical search, not an interval-wide completeness proof
    for unresolved grazing contacts near a station.
    """
    _require_swe()
    reference_jd = _julian_day(reference_utc)
    selected: List[datetime] = []
    for direction, count in ((-1, past), (1, future)):
        found: set[datetime] = set()
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
            moments = _longitude_crossings_utc(
                planet_id,
                natal_longitude,
                min(cursor, following),
                max(cursor, following),
                min(1.0, period_days / 360.0),
                sidereal=sidereal,
            )
            found.update(
                at
                for at in moments
                if (at <= reference_utc if direction < 0 else at > reference_utc)
            )
            cursor = following
        ordered = sorted(found)
        selected.extend(
            ordered[-count:] if direction < 0 and count else ordered[:count]
        )
    return selected


__all__ = [
    "CARDINAL_INGRESSES",
    "CARDINAL_INGRESS_LABELS",
    "RETURN_BODIES",
    "EphemerisUnavailableError",
    "find_longitude_crossing_utc",
    "find_cardinal_ingress_utc",
    "find_planet_returns",
    "planet_longitude_at_utc",
]
