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
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fatebridge.core.astro.time_scales import datetime_from_tt, ephemeris_time
from fatebridge.core.ephemeris_runtime import ephemeris_call, swe

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


def _planet_longitude(jd: float, planet_id: int) -> float:
    result, flag = ephemeris_call("calc", jd, planet_id, swe.FLG_SWIEPH | swe.FLG_SPEED)
    if flag < 0:
        raise ValueError("Astronomical event ephemeris failed")
    return float(result[0] % 360.0)


def _jd_to_utc(jd: float) -> datetime:
    return datetime_from_tt(jd)


def _wrapped_diff(longitude: float, target: float) -> float:
    """Signed angular distance ``longitude − target`` folded into (−180, 180]."""
    return (longitude - target + 540.0) % 360.0 - 180.0


def find_longitude_crossing_utc(
    planet_id: int,
    target_longitude: float,
    anchor_utc: datetime,
    *,
    window_days: float = 40.0,
    step_days: float = 1.0,
) -> Optional[datetime]:
    """
    Solve the UTC moment a body reaches ``target_longitude`` nearest ``anchor_utc``.

    Coarse-scans ``±window_days`` for the crossing nearest ``anchor_utc`` in
    EITHER direction (so it also handles the retrograde lunar node), then bisects
    to sub-second precision. Returns None if no crossing falls in the window.
    """
    _require_swe()
    anchor_jd = _julian_day(anchor_utc)
    start_jd = anchor_jd - window_days

    previous_jd = start_jd
    previous_diff = _wrapped_diff(
        _planet_longitude(previous_jd, planet_id), target_longitude
    )
    jd = previous_jd + step_days
    best: Optional[tuple[float, float]] = None
    best_distance = float("inf")
    while jd <= anchor_jd + window_days:
        current_diff = _wrapped_diff(_planet_longitude(jd, planet_id), target_longitude)
        # Sign change in either direction, excluding the far-side 180° wrap.
        if (
            previous_diff <= 0.0 <= current_diff or current_diff <= 0.0 <= previous_diff
        ) and abs(current_diff - previous_diff) < 90.0:
            distance = abs((previous_jd + jd) / 2.0 - anchor_jd)
            if distance < best_distance:
                best, best_distance = (previous_jd, jd), distance
        previous_jd, previous_diff = jd, current_diff
        jd += step_days

    if best is None:
        return None

    low, high = best
    low_negative = (
        _wrapped_diff(_planet_longitude(low, planet_id), target_longitude) < 0.0
    )
    for _ in range(48):
        mid = (low + high) / 2.0
        mid_negative = (
            _wrapped_diff(_planet_longitude(mid, planet_id), target_longitude) < 0.0
        )
        if mid_negative == low_negative:
            low = mid
        else:
            high = mid
    # The civil representation must be on the post-crossing side, including
    # retrograde crossings. TT→UTC→TT rounding can move one representable JD;
    # inspect the recovered instant instead of assigning the requested sign.
    for _ in range(8):
        moment = _jd_to_utc(high)
        recovered = _julian_day(moment)
        value = _wrapped_diff(_planet_longitude(recovered, planet_id), target_longitude)
        if value >= 0.0 if low_negative else value <= 0.0:
            return moment
        high = math.nextafter(high, math.inf)
    raise EphemerisUnavailableError(
        "Civil crossing instant could not preserve its crossing side"
    )


def planet_longitude_at_utc(planet_id: int, moment: datetime) -> float:
    """Tropical longitude (0–360°) of a body at a UTC moment — natal anchor for returns."""
    _require_swe()
    return _planet_longitude(_julian_day(moment), planet_id)


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
) -> List[datetime]:
    """
    Find planetary-return moments bracketing ``reference_utc``: the ``past`` most
    recent returns before it and the ``future`` upcoming ones, sorted ascending.
    The body's mean period seeds each search window; bisection pins each exact
    return to the natal longitude.
    """
    _require_swe()
    moments: List[datetime] = []
    # Step backward then forward in mean-period strides; solve the crossing nearest
    # each seed. De-duplicate by day to absorb seeds that resolve to the same return.
    seeds = [
        reference_utc + timedelta(days=period_days * k)
        for k in range(-past, future + 1)
    ]
    for seed in seeds:
        crossing = find_longitude_crossing_utc(
            planet_id,
            natal_longitude,
            seed,
            window_days=period_days / 2.0 + 5.0,
            step_days=max(1.0, period_days / 360.0),
        )
        if crossing is not None:
            moments.append(crossing)

    unique: List[datetime] = []
    for moment in sorted(moments):
        if not unique or abs((moment - unique[-1]).total_seconds()) > 86400.0:
            unique.append(moment)
    return unique


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
