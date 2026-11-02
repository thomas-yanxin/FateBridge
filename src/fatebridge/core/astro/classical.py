"""Classical chart layers, fixed stars and planetary hours."""

from __future__ import annotations

import math
from bisect import bisect_right
from typing import Any, Dict, List, Optional, Tuple

from fatebridge.core.astro import runtime
from fatebridge.core.astro.geometry import (
    _degree_in_sign,
    _sign_name,
    _week_ruler,
    combine_longitudes,
    normalize_angle,
)
from fatebridge.core.astro.native_coordinates import (
    require_altitude,
    require_spherical_coordinates,
)
from fatebridge.core.astro.native_motion import require_longitude_speed
from fatebridge.core.astro.physical_epoch import utc_from_tt, utc_representation
from fatebridge.core.astro.syzygy_sources import SyzygySourceTrace
from fatebridge.core.astro.time_scales import (
    datetime_from_ut1,
    tt_from_ut1,
    ut1_from_tt,
)
from fatebridge.core.astrology_tables import RULER_BY_SIGN as RULER_BY_SIGN
from fatebridge.core.astrology_tables import SIGN_LABELS_ZH as SIGN_LABELS_ZH
from fatebridge.core.ephemeris_runtime import lock_ephemeris_configuration
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.timezones import parse_timezone_name


def _sect(sun_altitude: float) -> str:
    """Day/night by the Sun's geometric centre, independent of house system."""
    return "day" if require_altitude(sun_altitude) >= 0.0 else "night"


def _luminary_lon_speed(
    julian_day_tt: float,
    body_id: int,
    *,
    source_trace: Optional[SyzygySourceTrace] = None,
) -> Optional[Tuple[float, float]]:
    """Tropical apparent longitude/speed evaluated in TT, or None on failure."""
    try:
        coordinates, retflag = runtime.ephemeris_call(
            "calc",
            julian_day_tt,
            body_id,
            runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED,
        )
    except EphemerisSourceError:
        raise
    except Exception as error:  # pragma: no cover - defensive
        runtime._log_swe_runtime_failure("calc(syzygy)", error)
        return None
    if retflag < 0:
        return None
    speed = require_longitude_speed(coordinates, retflag, runtime.swe.FLG_SPEED)
    longitude, _, _ = require_spherical_coordinates(
        coordinates, retflag, native=runtime.swe
    )
    if source_trace is not None:
        source_trace.observe(body_id, retflag, julian_day_tt, "tropical_search")
    return normalize_angle(longitude), speed


@lock_ephemeris_configuration()
def _prenatal_syzygy(
    julian_day: float, *, julian_day_tt: Optional[float] = None, sidereal: bool = False
) -> Optional[Dict[str, Any]]:
    """The last New or Full Moon strictly before birth (prenatal lunation).

    The positional input retained for compatibility is UT1; chart assembly also
    supplies TT explicitly. Search and bisection operate on tropical apparent
    elongation in TT. The returned event is the first representable JD on the
    post-crossing side, and must be strictly less than birth's TT. At that same
    representable event instant, the previous lunation is selected instead.

    The point is the Sun's longitude at New Moon, the Moon's at Full Moon.
    Sidereal display uses a native Lahiri calculation at the event epoch;
    changing the zodiac does not change the physical event. A supported UTC
    label outside datetime's range does not erase the astronomical result.
    """
    if runtime.swe is None:
        return None
    try:
        source_trace = SyzygySourceTrace()
        birth_tt = tt_from_ut1(julian_day) if julian_day_tt is None else julian_day_tt
        search_end = birth_tt

        def phase(at: float) -> float:
            sun = _luminary_lon_speed(at, runtime.swe.SUN, source_trace=source_trace)
            moon = _luminary_lon_speed(at, runtime.swe.MOON, source_trace=source_trace)
            if sun is None or moon is None or moon[1] <= sun[1]:
                raise ValueError("Unavailable or non-increasing lunar elongation")
            return normalize_angle(moon[0] - sun[0])

        for _ in range(2):
            right = search_end
            elongation = phase(right)
            target = 180.0 if elongation >= 180.0 else 0.0

            def offset(at: float) -> float:
                difference = phase(at) - target
                return difference - 360.0 if difference >= 180.0 else difference

            f_right = elongation - target
            for _ in range(20):
                left = right - 1.0
                f_left = offset(left)
                if f_left < 0 <= f_right and f_right - f_left < 90:
                    break
                right, f_right = left, f_left
            else:
                return None
            for _ in range(60):
                mid = (left + right) / 2
                if mid in (left, right):
                    break
                if offset(mid) >= 0:
                    right = mid
                else:
                    left = mid
            if right >= birth_tt:
                search_end = left
                continue
            residual = offset(right)
            if not 0 <= residual < 1e-6:
                return None
            body = runtime.swe.MOON if target == 180 else runtime.swe.SUN
            tropical = _luminary_lon_speed(right, body, source_trace=source_trace)
            if tropical is None:
                return None
            longitude = tropical[0]
            if sidereal:
                with runtime.preserve_ephemeris_path():
                    runtime.ephemeris_call("set_sid_mode", runtime.swe.SIDM_LAHIRI)
                    coordinates, flag = runtime.ephemeris_call(
                        "calc",
                        right,
                        body,
                        runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SIDEREAL,
                    )
                    if flag < 0:
                        return None
                    longitude, _, _ = require_spherical_coordinates(
                        coordinates, flag, native=runtime.swe, sidereal=True
                    )
                    # File slots describe the last native call. Observe them
                    # before restoring the path can close or replace caches.
                    source_trace.observe(body, flag, right, "sidereal_display")
                longitude = normalize_angle(longitude)
            event_ut1 = ut1_from_tt(right)
            label, moment, leap = utc_from_tt(right)
            return {
                "type": "full" if target == 180 else "new",
                "longitude": longitude,
                "tropical_longitude": tropical[0],
                "sign": _sign_name(longitude),
                "degree_in_sign": _degree_in_sign(longitude),
                "julian_day": event_ut1,
                "julian_day_ut1": event_ut1,
                "julian_day_tt": right,
                "event_datetime_utc": label,
                "utc_representation": utc_representation(label, moment, leap),
                "zodiac": "sidereal_lahiri" if sidereal else "tropical",
                "ephemeris_source": source_trace.finish(),
                "solver": {
                    "method": "bracketed_TT_elongation_bisection",
                    "target_elongation": target,
                    "residual_degrees": residual,
                    "strictly_before_birth": right < birth_tt,
                },
            }
    except EphemerisSourceError:
        raise
    except Exception as error:
        runtime._log_swe_runtime_failure("prenatal_syzygy", error)
    return None


def _sun_event(
    julian_day: float, longitude: float, latitude: float, rising: bool
) -> Optional[float]:
    """Julian day of the next sunrise (``rising``) or sunset after ``julian_day``.

    ``None`` when swisseph reports no event (polar day/night) or a soft failure.
    This legacy convention is apparent solar centre with refraction at sea
    level, 1013.25 hPa and 0 Celsius. It differs from the geometric sect horizon
    and the conventional upper-limb sunrise published in public almanacs.
    """
    flag = (
        runtime.swe.CALC_RISE if rising else runtime.swe.CALC_SET
    ) | runtime.swe.BIT_DISC_CENTER
    try:
        retflag, times = runtime.ephemeris_call(
            "rise_trans",
            julian_day,
            runtime.swe.SUN,
            flag,
            (longitude, latitude, 0.0),
            1013.25,
            0.0,
        )
    except EphemerisSourceError:
        raise
    except Exception as error:  # pragma: no cover - defensive
        runtime._log_swe_runtime_failure("rise_trans", error)
        return None
    if retflag < 0:
        return None
    event = float(times[0])
    return event if math.isfinite(event) else None


def _bracket_sun_event(
    julian_day: float, longitude: float, latitude: float, rising: bool
) -> Optional[Tuple[float, float]]:
    """Consecutive events bracketing the instant; a solar day is not fixed 24h."""
    query = julian_day - 2.0
    previous = None
    for _ in range(8):
        event = _sun_event(query, longitude, latitude, rising)
        if event is None or event < query or event > julian_day + 2.0:
            return None
        if event > julian_day:
            return (previous, event) if previous is not None else None
        previous = event
        # Consecutive risings (or settings) cannot occur within half a rotation.
        # Advance past this occurrence without a boundary-sized epsilon.
        query = event + 0.5
    return None


def _planetary_hours(
    julian_day: float,
    longitude: float,
    latitude: float,
    timezone_name: str,
    *,
    weekday_clock_basis: str = "civil",
) -> Optional[Dict[str, Any]]:
    """Planetary hour of the birth instant + the ruler of the planetary day.

    The day runs sunrise→sunset (12 unequal *day* hours) and sunset→next sunrise
    (12 *night* hours). Hour 1 is ruled by the weekday's planet — fixed by the
    sunrise that opened the current planetary day — and rulers step through the
    Chaldean order from there (see :func:`planetary_hour_sequence`).

    ``None`` when swisseph is unavailable or the Sun neither rises nor sets
    (polar latitudes) — the day/night arcs are then undefined.
    """
    if weekday_clock_basis not in {"civil", "local_mean_solar", "local_apparent_solar"}:
        raise ValueError("Unknown planetary weekday clock basis")
    if runtime.swe is None:
        return None
    from fatebridge.core.classical_western import planetary_hour_sequence

    rises = _bracket_sun_event(julian_day, longitude, latitude, rising=True)
    sets = _bracket_sun_event(julian_day, longitude, latitude, rising=False)
    if rises is None or sets is None:
        return None
    prev_rise, next_rise = rises
    prev_set, next_set = sets
    is_day = prev_rise > prev_set
    if is_day:
        arc_start, arc_end = prev_rise, next_set
    else:
        arc_start, arc_end = prev_set, next_rise
    arc_length = arc_end - arc_start
    if not arc_start <= julian_day < arc_end or arc_length <= 0:
        return None
    boundaries = [arc_start + arc_length * i / 12 for i in range(12)] + [arc_end]
    index = bisect_right(boundaries, julian_day) - 1
    if not 0 <= index < 12:
        return None

    # Weekday ruler of the planetary day = weekday at the opening sunrise, taken
    # in local civil time so a pre-dawn birth correctly belongs to the prior day.
    try:
        rise_utc = datetime_from_ut1(prev_rise)
        arc_start_utc, arc_end_utc = map(datetime_from_ut1, (arc_start, arc_end))
        hour_start_utc, hour_end_utc = map(
            datetime_from_ut1, (boundaries[index], boundaries[index + 1])
        )
    except EphemerisSourceError:
        raise
    except Exception as error:
        runtime._log_swe_runtime_failure("planetary_hours_civil_conversion", error)
        return None
    weekday_receipt = {}
    if weekday_clock_basis == "civil":
        sunrise_label = rise_utc.astimezone(parse_timezone_name(timezone_name))
    else:
        from fatebridge.core.astro.birth_clock import solar_wall_clock

        sunrise_label = solar_wall_clock(rise_utc, longitude, weekday_clock_basis)
        weekday_receipt = {
            "weekday_clock_basis": weekday_clock_basis,
            "weekday_opening_sunrise_label": sunrise_label.isoformat(),
            "weekday_policy": "Opening sunrise date in the declared local solar clock; UTC is only the physical carrier. Implementation convention, not an identified original author's clock or source-method acceptance.",
        }
    day_ruler = _week_ruler(sunrise_label)

    sequence = planetary_hour_sequence(day_ruler)
    sequence_index = index if is_day else index + 12
    hour_ruler = sequence[sequence_index] if sequence else None
    return {
        "is_day": is_day,
        "day_ruler": day_ruler,
        "hour_ruler": hour_ruler,
        "hour_number": index + 1,
        "planetary_day_start_utc": rise_utc.isoformat(),
        "arc_start_utc": arc_start_utc.isoformat(),
        "arc_end_utc": arc_end_utc.isoformat(),
        "hour_start_utc": hour_start_utc.isoformat(),
        "hour_end_utc": hour_end_utc.isoformat(),
        "arc_start_jd_ut1": arc_start,
        "arc_end_jd_ut1": arc_end,
        "rule_id": "unequal_hours_chaldean_sunrise_weekday_v1",
        "sunrise_convention": "apparent_solar_center_sea_level_1013.25hPa_0C",
        "time_scale": "UT1_arcs_TT_to_frozen_civil_UTC",
        "sequence_source": "Cassius Dio, Roman History 37.19, Loeb 1914",
        "sequence_source_url": "https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Cassius_Dio/37%2A.html#19",
        "source_scope": "Planet order and 24-hour weekday succession only; horizon and unequal-hour geometry are separate declared policies",
        **weekday_receipt,
    }


def _build_classical_layer(
    planets: List[Dict[str, Any]],
    houses: List[Dict[str, Any]],
    ascendant: float,
    *,
    chart_sect: str,
    states: Optional[Dict[str, Dict[str, float]]] = None,
    julian_day: Optional[float] = None,
    julian_day_tt: Optional[float] = None,
    sidereal: bool = False,
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
        orientality_policy,
        solar_condition_policy,
    )

    states = states or {}
    obliquity = None
    if runtime.swe is not None and julian_day is not None:
        try:
            angles, flag = runtime.ephemeris_call(
                "calc_ut", julian_day, runtime.swe.ECL_NUT
            )
            if flag >= 0:
                obliquity = float(angles[0])
        except EphemerisSourceError:
            raise
        except Exception as error:
            runtime._log_swe_runtime_failure("calc_ut(obliquity)", error)
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
            altitude=state.get("altitude"),
            obliquity=obliquity,
        )
        placements[item["id"]] = item["sign"]
        lons[item["id"].lower()] = item["longitude"]

    houses_for_almuten = {
        house["house"]: {
            "sign": house["sign"],
            "degree_in_sign": float(house["cusp_longitude"]) % 30.0,
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
    syzygy = (
        _prenatal_syzygy(julian_day, julian_day_tt=julian_day_tt, sidereal=sidereal)
        if julian_day is not None
        else None
    )
    fortune = lots.get("fortune")
    figuris_points: Dict[str, Dict[str, Any]] = {}
    if sun:
        figuris_points["Sun"] = sun
    if moon:
        figuris_points["Moon"] = moon
    figuris_points["Ascendant"] = {
        "sign": asc_sign,
        "degree_in_sign": ascendant % 30.0,
    }
    if fortune:
        figuris_points["fortune"] = fortune
    if syzygy:
        figuris_points["syzygy"] = syzygy

    return {
        "sect": chart_sect,
        "orientality_policy": orientality_policy(),
        "solar_condition_policy": solar_condition_policy(),
        "obliquity": obliquity,
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
    *,
    julian_day_tt: Optional[float] = None,
    sidereal: bool = False,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """``fixed_stars`` block — catalogue stars conjunct planets / Asc / MC.

    The catalogue is bundled. Missing native positions are explicitly marked
    unavailable, separately from a computed empty conjunction list.
    """
    from fatebridge.core.classical_western import build_fixed_star_layer

    points = {planet["id"]: planet["longitude"] for planet in planets}
    points["Ascendant"] = normalize_angle(ascendant)
    points["Midheaven"] = normalize_angle(midheaven)
    return build_fixed_star_layer(
        points, julian_day, julian_day_tt=julian_day_tt, sidereal=sidereal
    )


def _build_classical_patterns(
    planets: List[Dict[str, Any]],
    aspects: List[Dict[str, Any]],
    states: Optional[Dict[str, Dict[str, float]]] = None,
    *,
    chart_sect: str,
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
        chart_sect,
        speeds=speeds,
        latitudes={
            pid: state["latitude"]
            for pid, state in states.items()
            if state.get("latitude") is not None
        },
        node_longitude=node_longitude,
    )


def _fortune_lot(
    planets: List[Dict[str, Any]], ascendant: float, *, chart_sect: str
) -> Dict[str, Any]:
    sun = next(item for item in planets if item["id"] == "Sun")
    moon = next(item for item in planets if item["id"] == "Moon")
    if chart_sect == "day":
        longitude = combine_longitudes(ascendant, moon["longitude"], -sun["longitude"])
    else:
        longitude = combine_longitudes(ascendant, sun["longitude"], -moon["longitude"])
    sign = _sign_name(longitude)
    return {
        "longitude": longitude,
        "sign": sign,
        "sign_zh": SIGN_LABELS_ZH[sign],
        "degree_in_sign": _degree_in_sign(longitude),
    }
