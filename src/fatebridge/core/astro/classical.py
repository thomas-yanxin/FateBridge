"""Classical chart layers, fixed stars and planetary hours."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fatebridge.core.astro import runtime
from fatebridge.core.astro.geometry import (
    _degree_in_sign,
    _sign_name,
    _week_ruler,
    normalize_angle,
)
from fatebridge.core.astro.reference import _MEAN_ELONGATION_RATE
from fatebridge.core.astrology_tables import RULER_BY_SIGN as RULER_BY_SIGN
from fatebridge.core.astrology_tables import SIGN_LABELS_ZH as SIGN_LABELS_ZH
from fatebridge.utils.timezones import parse_timezone_name


def _sect(planets: List[Dict[str, Any]]) -> str:
    sun = next((item for item in planets if item["id"] == "Sun"), None)
    if sun is None:
        return "day"
    return "day" if sun["house"] >= 7 else "night"


def _luminary_lon_speed(
    julian_day: float, body_id: int
) -> Optional[Tuple[float, float]]:
    """``(longitude, longitude_speed)`` of a luminary, or None on swe failure."""
    try:
        coordinates, retflag = runtime.ephemeris_call(
            "calc_ut",
            julian_day,
            body_id,
            runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED,
        )
    except Exception as error:  # pragma: no cover - defensive
        runtime._log_swe_runtime_failure("calc_ut(syzygy)", error)
        return None
    if retflag < 0:
        return None
    return normalize_angle(float(coordinates[0])), float(coordinates[3])


def _prenatal_syzygy(julian_day: float) -> Optional[Dict[str, Any]]:
    """The last New or Full Moon strictly before birth (prenatal lunation).

    Used as the fifth hylegic point of the Almuten Figuris. The Sun–Moon
    elongation rises ~12.19°/day; a New Moon sits at elongation 0°, a Full Moon
    at 180°. We seed from the mean rate, then Newton-refine on the true
    elongation speed until the lunation instant is pinned. The syzygy *point* is
    the conjunction degree (New Moon) or the Moon's degree (Full Moon).

    Returns ``None`` when swisseph is unavailable — the offline approximate
    engine cannot run the backward search, so the Almuten Figuris simply elects
    over the four points it does have.
    """
    if runtime.swe is None:
        return None
    here = _luminary_lon_speed(julian_day, runtime.swe.SUN)
    moon_here = _luminary_lon_speed(julian_day, runtime.swe.MOON)
    if here is None or moon_here is None:
        return None
    elongation = (moon_here[0] - here[0]) % 360.0
    is_full = elongation >= 180.0
    target = 180.0 if is_full else 0.0
    # Step back by the elongation already accrued past the last syzygy.
    estimate = julian_day - (elongation - target) / _MEAN_ELONGATION_RATE
    for _ in range(40):
        sun = _luminary_lon_speed(estimate, runtime.swe.SUN)
        moon = _luminary_lon_speed(estimate, runtime.swe.MOON)
        if sun is None or moon is None:
            return None
        # Signed distance of current elongation from the target, folded to (−180, 180].
        offset = (moon[0] - sun[0] - target + 540.0) % 360.0 - 180.0
        rate = moon[1] - sun[1]
        if abs(offset) < 1e-9 or rate == 0.0:
            break
        estimate -= offset / rate
    sun = _luminary_lon_speed(estimate, runtime.swe.SUN)
    moon = _luminary_lon_speed(estimate, runtime.swe.MOON)
    if sun is None or moon is None:
        return None
    longitude = moon[0] if is_full else sun[0]
    return {
        "type": "full" if is_full else "new",
        "longitude": round(longitude, 4),
        "sign": _sign_name(longitude),
        "degree_in_sign": round(_degree_in_sign(longitude), 4),
        "julian_day": round(estimate, 6),
    }


def _sun_event(
    julian_day: float, longitude: float, latitude: float, rising: bool
) -> Optional[float]:
    """Julian day of the next sunrise (``rising``) or sunset after ``julian_day``.

    ``None`` when swisseph reports no event (polar day/night) or a soft failure.
    Disc-centre crossing keeps day/night symmetric with the classical horizon.
    """
    flag = (
        runtime.swe.CALC_RISE if rising else runtime.swe.CALC_SET
    ) | runtime.swe.BIT_DISC_CENTER
    try:
        retflag, times = runtime.ephemeris_call(
            "rise_trans", julian_day, runtime.swe.SUN, flag, (longitude, latitude, 0.0)
        )
    except Exception as error:  # pragma: no cover - defensive
        runtime._log_swe_runtime_failure("rise_trans", error)
        return None
    if retflag < 0:
        return None
    return float(times[0])


def _planetary_hours(
    julian_day: float, longitude: float, latitude: float, timezone_name: str
) -> Optional[Dict[str, Any]]:
    """Planetary hour of the birth instant + the ruler of the planetary day.

    The day runs sunrise→sunset (12 unequal *day* hours) and sunset→next sunrise
    (12 *night* hours). Hour 1 is ruled by the weekday's planet — fixed by the
    sunrise that opened the current planetary day — and rulers step through the
    Chaldean order from there (see :func:`planetary_hour_sequence`).

    ``None`` when swisseph is unavailable or the Sun neither rises nor sets
    (polar latitudes) — the day/night arcs are then undefined.
    """
    if runtime.swe is None:
        return None
    from fatebridge.core.classical_western import planetary_hour_sequence

    next_rise = _sun_event(julian_day, longitude, latitude, rising=True)
    next_set = _sun_event(julian_day, longitude, latitude, rising=False)
    # The sunrise that opened the current planetary day fixes the weekday ruler,
    # for both day and night births (search back a full day to bracket it).
    prev_rise = _sun_event(julian_day - 1.0, longitude, latitude, rising=True)
    if next_rise is None or next_set is None or prev_rise is None:
        return None

    is_day = next_set < next_rise
    if is_day:
        arc_start, arc_end = prev_rise, next_set
    else:
        prev_set = _sun_event(julian_day - 1.0, longitude, latitude, rising=False)
        if prev_set is None:
            return None
        arc_start, arc_end = prev_set, next_rise
    arc_length = arc_end - arc_start
    if arc_length <= 0:
        return None

    hour_length = arc_length / 12.0
    index = int((julian_day - arc_start) / hour_length)
    index = max(0, min(11, index))  # clamp boundary rounding into the valid 12

    # Weekday ruler of the planetary day = weekday at the opening sunrise, taken
    # in local civil time so a pre-dawn birth correctly belongs to the prior day.
    try:
        year, month, day, ut_hour = runtime.swe.revjul(prev_rise)
    except Exception as error:
        # Planetary hours are explicitly optional ("None when swisseph is
        # unavailable"); a runtime revjul failure degrades to None rather than
        # crashing the whole chart on the tuple unpack.
        runtime._log_swe_runtime_failure("revjul", error)
        return None
    rise_utc = datetime(
        year, month, day, tzinfo=parse_timezone_name("UTC")
    ) + timedelta(hours=ut_hour)
    day_ruler = _week_ruler(rise_utc.astimezone(parse_timezone_name(timezone_name)))

    sequence = planetary_hour_sequence(day_ruler)
    sequence_index = index if is_day else index + 12
    hour_ruler = sequence[sequence_index] if sequence else None
    return {
        "is_day": is_day,
        "day_ruler": day_ruler,
        "hour_ruler": hour_ruler,
        "hour_number": index + 1,
    }


def _build_classical_layer(
    planets: List[Dict[str, Any]],
    houses: List[Dict[str, Any]],
    ascendant: float,
    *,
    states: Optional[Dict[str, Dict[str, float]]] = None,
    julian_day: Optional[float] = None,
) -> Dict[str, Any]:
    """Hellenistic/medieval condition layer — the chart's ``classical`` block.

    Builds planetary conditions, dispositor chains, house almutens, lots,
    prenatal syzygy, Almuten Figuris and temperament. Public coverage and
    precision boundaries are documented in ``docs/algorithm-coverage.md``.
    Imported lazily so optional classical layers load only when requested.
    """
    from fatebridge.core.classical_western import (
        build_almuten_figuris,
        build_dispositor_layer,
        build_lots_layer,
        build_planet_classical,
        build_temperament,
        build_topic_almutens,
    )

    states = states or {}
    chart_sect = _sect(planets)
    is_day = chart_sect == "day"
    sun = next((item for item in planets if item["id"] == "Sun"), None)
    sun_longitude = sun["longitude"] if sun else None
    moon = next((item for item in planets if item["id"] == "Moon"), None)
    asc_sign = _sign_name(ascendant)

    planet_layer: Dict[str, Any] = {}
    placements: Dict[str, str] = {}
    lons: Dict[str, float] = {}
    for item in planets:
        state = states.get(item["id"], {})
        planet_layer[item["id"]] = build_planet_classical(
            planet=item["id"],
            sign=item["sign"],
            degree_in_sign=item["degree_in_sign"],
            longitude=item["longitude"],
            house=item.get("house"),
            sun_longitude=sun_longitude,
            chart_sect=chart_sect,
            longitude_speed=state.get("longitude_speed"),
            declination=state.get("declination"),
        )
        placements[item["id"]] = item["sign"]
        lons[item["id"].lower()] = item["longitude"]

    houses_for_almuten = {
        house["house"]: {
            "sign": house["sign"],
            "degree_in_sign": round(float(house["cusp_longitude"]) % 30.0, 4),
        }
        for house in houses
        if house.get("sign") is not None
    }
    # Lot longitude markers: the EXACT ascendant (not the whole-sign 1st cusp, so
    # Fortune matches _fortune_lot) + the 8th cusp.
    lons["asc"] = float(ascendant)
    for house in houses:
        if house["house"] == 8:
            lons["eighth"] = float(house["cusp_longitude"])

    lots = build_lots_layer(lons, is_day)
    syzygy = _prenatal_syzygy(julian_day) if julian_day is not None else None
    fortune = lots.get("fortune")
    figuris_points: Dict[str, Dict[str, Any]] = {}
    if sun:
        figuris_points["Sun"] = sun
    if moon:
        figuris_points["Moon"] = moon
    figuris_points["Ascendant"] = {
        "sign": asc_sign,
        "degree_in_sign": round(ascendant % 30.0, 4),
    }
    if fortune:
        figuris_points["fortune"] = fortune
    if syzygy:
        figuris_points["syzygy"] = syzygy

    return {
        "sect": chart_sect,
        "planets": planet_layer,
        "dispositors": build_dispositor_layer(placements),
        "topic_almutens": build_topic_almutens(houses_for_almuten, is_day),
        "lots": lots,
        "syzygy": syzygy,
        "almuten_figuris": build_almuten_figuris(figuris_points, is_day),
        "temperament": build_temperament(
            asc_sign,
            RULER_BY_SIGN.get(asc_sign),
            sun["sign"] if sun else None,
            moon["sign"] if moon else None,
        ),
    }


def _build_fixed_stars(
    planets: List[Dict[str, Any]],
    ascendant: float,
    midheaven: float,
    julian_day: float,
) -> List[Dict[str, Any]]:
    """``fixed_stars`` block — catalogue stars conjunct planets / Asc / MC.

    Pure computation off the vendored J2000 catalogue (no ephemeris file), so it
    runs on every engine. Classical routines share tables through astrology_tables."""
    from fatebridge.core.classical_western import build_fixed_star_hits

    points = {planet["id"]: planet["longitude"] for planet in planets}
    points["Ascendant"] = normalize_angle(ascendant)
    points["Midheaven"] = normalize_angle(midheaven)
    return build_fixed_star_hits(points, julian_day)


def _build_classical_patterns(
    planets: List[Dict[str, Any]],
    aspects: List[Dict[str, Any]],
    states: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict[str, Any]:
    """The chart's ``classical_patterns`` block — [古典格局] relational layer
    ``states`` carries per-planet speed for translation/
    collection of light; the North Node longitude drives nodal bending. Classical rules
    share tables through astrology_tables."""
    from fatebridge.core.classical_western import build_classical_patterns

    states = states or {}
    speeds = {
        pid: state["longitude_speed"]
        for pid, state in states.items()
        if state.get("longitude_speed") is not None
    }
    node_longitude = next(
        (p["longitude"] for p in planets if p["id"] == "North Node"), None
    )
    return build_classical_patterns(
        planets,
        aspects,
        _sect(planets),
        speeds=speeds,
        node_longitude=node_longitude,
    )


def _fortune_lot(planets: List[Dict[str, Any]], ascendant: float) -> Dict[str, Any]:
    sun = next(item for item in planets if item["id"] == "Sun")
    moon = next(item for item in planets if item["id"] == "Moon")
    sect = _sect(planets)
    if sect == "day":
        longitude = normalize_angle(ascendant + moon["longitude"] - sun["longitude"])
    else:
        longitude = normalize_angle(ascendant + sun["longitude"] - moon["longitude"])
    sign = _sign_name(longitude)
    return {
        "longitude": round(longitude, 4),
        "sign": sign,
        "sign_zh": SIGN_LABELS_ZH[sign],
        "degree_in_sign": round(_degree_in_sign(longitude), 4),
    }
