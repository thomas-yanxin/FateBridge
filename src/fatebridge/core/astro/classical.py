"""Classical chart layers, fixed stars and planetary hours."""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any, Literal

from fatebridge.core.astro import runtime
from fatebridge.core.astro.astrology_tables import RULER_BY_SIGN as RULER_BY_SIGN
from fatebridge.core.astro.birth_clock import solar_wall_clock
from fatebridge.core.astro.ephemeris import fast_swe_call
from fatebridge.core.astro.geometry import (
    _degree_in_sign,
    _sign_name,
    _week_ruler,
    normalize_angle,
)
from fatebridge.core.astro.iers_ut1 import active_ut1
from fatebridge.core.astro.native_coordinates import (
    require_altitude,
    require_spherical_coordinates,
)
from fatebridge.core.astro.native_motion import require_longitude_speed
from fatebridge.core.astro.physical_epoch import (
    PhysicalEpoch,
    utc_from_tt,
    utc_representation,
)
from fatebridge.core.astro.reference_frames import analytic_ecliptic_frame
from fatebridge.core.astro.time_scales import (
    fallback_julian_day_tt,
    resolve_tt_from_ut1,
    ut1_from_tt,
    utc_calendar_from_tt,
)
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.core.classical_western import (
    build_almuten_figuris,
    build_classical_patterns,
    build_dispositor_layer,
    build_fixed_star_layer,
    build_lots_layer,
    build_planet_classical,
    build_temperament,
    build_topic_almutens,
    orientality_policy,
    planetary_hour_sequence,
    solar_condition_policy,
)
from fatebridge.core.ephemeris_runtime import lock_ephemeris_configuration
from fatebridge.utils.civil_time import ZonedCalendar
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.timezones import is_unspecified_local_time, parse_timezone_name


def _sect(sun_altitude: float) -> str:
    """Day/night by the Sun's geometric centre, independent of house system."""
    return "day" if require_altitude(sun_altitude) >= 0.0 else "night"


def _luminary_lon_speed(
    julian_day_tt: float,
    body_id: int,
) -> tuple[float, float, int] | None:
    """Tropical apparent longitude/speed evaluated in TT, or None on failure."""
    try:
        coordinates, retflag = fast_swe_call(
            "calc",
            julian_day_tt,
            body_id,
            runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED,
        )
    except EphemerisSourceError:
        raise
    except runtime.native_ephemeris_errors() as error:  # pragma: no cover - defensive
        runtime._log_swe_runtime_failure("calc(syzygy)", error)
        return None
    if retflag < 0:
        return None
    speed = require_longitude_speed(coordinates, retflag, runtime.swe.FLG_SPEED)
    longitude, _, _ = require_spherical_coordinates(
        coordinates, retflag, native=runtime.swe
    )
    return longitude, speed, retflag


@lock_ephemeris_configuration()
def _prenatal_syzygy(
    julian_day: float | UT1Instant,
    *,
    julian_day_tt: float | TTInstant | None = None,
    sidereal: bool = False,
) -> dict[str, Any] | None:
    """The last New or Full Moon strictly before birth (prenatal lunation)."""
    if runtime.swe is None:
        return None
    try:
        birth_point = TTInstant.from_value(
            resolve_tt_from_ut1(julian_day) if julian_day_tt is None else julian_day_tt
        )
        birth_tt = birth_point.as_float()
        search_end = birth_tt

        def phase(at: float) -> Fraction:
            sun = _luminary_lon_speed(at, runtime.swe.SUN)
            moon = _luminary_lon_speed(at, runtime.swe.MOON)
            if sun is None or moon is None or moon[1] <= sun[1]:
                raise ValueError("Unavailable or non-increasing lunar elongation")
            return (Fraction(moon[0]) - Fraction(sun[0])) % 360

        for _ in range(2):
            right = search_end
            elongation = phase(right)
            target = 180 if elongation >= 180 else 0

            def offset(at: float) -> Fraction:
                difference = phase(at) - target
                return difference - 360 if difference >= 180 else difference

            f_right = elongation - target
            for _ in range(20):
                left = right - 1.0
                f_left = offset(left)
                if f_left < 0 <= f_right and f_right - f_left < 90:
                    break
                right, f_right = left, f_left
            else:
                return None
            for _ in range(55):
                mid = (left + right) / 2
                if mid in (left, right):
                    break
                if offset(mid) >= 0:
                    right = mid
                else:
                    left = mid
            if Fraction(right) >= birth_point.days:
                search_end = left
                continue
            residual = offset(right)
            residual_limit = 1e-6
            if not 0 <= residual < residual_limit:
                return None
            body = runtime.swe.MOON if target == 180 else runtime.swe.SUN
            tropical = _luminary_lon_speed(right, body)
            if tropical is None:
                return None
            tropical_longitude = normalize_angle(tropical[0])
            longitude = tropical_longitude
            display_flag = tropical[2]
            if sidereal:
                with runtime.preserve_ephemeris_path():
                    fast_swe_call("set_sid_mode", runtime.swe.SIDM_LAHIRI, 0, 0)
                    coordinates, flag = fast_swe_call(
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
                    display_flag = flag
                longitude = normalize_angle(longitude)
            event_ut1 = ut1_from_tt(right)
            label, moment, leap = utc_from_tt(right)
            return {
                "type": "full" if target == 180 else "new",
                "longitude": longitude,
                "tropical_longitude": tropical_longitude,
                "sign": _sign_name(longitude),
                "degree_in_sign": _degree_in_sign(longitude),
                "julian_day": event_ut1,
                "julian_day_ut1": event_ut1,
                "julian_day_tt": right,
                "event_datetime_utc": label,
                "utc_representation": utc_representation(label, moment, leap),
                "zodiac": "sidereal_lahiri" if sidereal else "tropical",
                "ephemeris_source": {
                    "model": runtime.ephemeris_model_from_retflag(display_flag),
                },
                "solver": {
                    "method": "bracketed_TT_elongation_bisection",
                    "target_elongation": float(target),
                    "residual_degrees": min(
                        float(residual), math.nextafter(residual_limit, 0.0)
                    ),
                    "strictly_before_birth": Fraction(right) < birth_point.days,
                },
            }
    except EphemerisSourceError:
        raise
    except runtime.native_ephemeris_errors() as error:
        runtime._log_swe_runtime_failure("prenatal_syzygy", error)
    return None


solar_crossings_in_window: Any = None


def _collect_solar_events(
    window_start: float,
    window_end: float,
    longitude: float,
    latitude: float,
    *,
    rising: bool,
) -> list[tuple[float, bool]]:
    rsmi = (
        runtime.swe.CALC_RISE if rising else runtime.swe.CALC_SET
    ) | runtime.swe.BIT_DISC_CENTER
    events: list[tuple[float, bool]] = []
    cursor = window_start
    geopos = (longitude, latitude, 0.0)
    for _ in range(8):
        if cursor >= window_end:
            break
        res, tret = fast_swe_call(
            "rise_trans",
            cursor,
            runtime.swe.SUN,
            rsmi,
            geopos,
            1013.25,
            0.0,
            runtime.swe.FLG_SWIEPH,
        )
        if res != 0:
            break
        event_ut = float(tret[0])
        if event_ut >= window_end:
            break
        events.append((event_ut, rising))
        cursor = event_ut + 1e-4
    return events


def _planetary_hours(
    julian_day: float | UT1Instant,
    longitude: float,
    latitude: float,
    timezone_name: str,
    *,
    weekday_clock_basis: str = "civil",
) -> dict[str, Any] | None:
    """Return the unequal hour when available for chart and research callers."""
    result = _resolve_planetary_hour(
        julian_day,
        longitude,
        latitude,
        timezone_name,
        weekday_clock_basis=weekday_clock_basis,
    )
    return None if isinstance(result, str) else result


def _resolve_planetary_hour(
    julian_day: float | UT1Instant,
    longitude: float,
    latitude: float,
    timezone_name: str,
    *,
    weekday_clock_basis: str = "civil",
) -> dict[str, Any] | Literal["opening_sunrise_civil_weekday_undefined"] | None:
    """Planetary hour of the query instant using Swiss Ephemeris rise_trans."""
    if weekday_clock_basis not in {"civil", "local_mean_solar", "local_apparent_solar"}:
        raise ValueError("Unknown planetary weekday clock basis")
    if runtime.swe is None:
        return None
    query = UT1Instant.from_value(julian_day)
    search_day = query.as_float()
    window_start, window_end = search_day - 2.0, search_day + 2.0
    rotation_source = active_ut1.get()
    if rotation_source is not None:
        first, last = rotation_source.ut1_bounds
        if not first <= query.days <= last:
            raise ValueError("Planetary hour is outside the IERS C04 source bounds")
        lower, upper = float(first), float(last)
        if lower < first:
            lower = math.nextafter(lower, math.inf)
        if upper > last:
            upper = math.nextafter(upper, -math.inf)
        window_start, window_end = max(window_start, lower), min(window_end, upper)

    if solar_crossings_in_window is not None:
        crossings = solar_crossings_in_window(
            window_start, window_end, longitude=longitude, latitude=latitude
        )
        events = sorted(
            ((float(e.julian_day_ut1), bool(e.rising)) for e in crossings),
            key=lambda item: item[0],
        )
    else:
        try:
            rises = _collect_solar_events(
                window_start, window_end, longitude, latitude, rising=True
            )
            sets = _collect_solar_events(
                window_start, window_end, longitude, latitude, rising=False
            )
        except EphemerisSourceError:
            raise
        except runtime.native_ephemeris_errors() as error:
            runtime._log_swe_runtime_failure("rise_trans(planetary_hours)", error)
            return None
        events = sorted(rises + sets, key=lambda item: item[0])
    before = [event for event in events if Fraction(event[0]) <= query.days]
    after = [event for event in events if Fraction(event[0]) > query.days]
    opening_rises = [event for event in before if event[1]]
    if not before or not after or not opening_rises:
        return None
    previous, following = before[-1], after[0]
    if previous[1] == following[1]:
        return None
    prev_rise = opening_rises[-1][0]
    is_day = previous[1]
    arc_start, arc_end = previous[0], following[0]
    start, end, at = Fraction(arc_start), Fraction(arc_end), query.days
    arc_length = end - start
    if not start <= at < end or arc_length <= 0:
        return None
    index = int((at - start) * 12 // arc_length)
    boundaries = [float(start + arc_length * i / 12) for i in range(13)]

    opening_label: str | None
    try:
        if weekday_clock_basis == "civil":
            opening_epoch = None
            opening_calendar = utc_calendar_from_tt(resolve_tt_from_ut1(prev_rise))
            opening_label = opening_calendar.isoformat()
        else:
            opening_epoch = PhysicalEpoch.from_ut1(prev_rise)
            opening_label = opening_epoch.utc_label
            if opening_label is None:
                return None
        endpoint_labels = []
        for point in (arc_start, arc_end, boundaries[index], boundaries[index + 1]):
            label, _, _ = utc_from_tt(resolve_tt_from_ut1(point))
            if label is None:
                return None
            endpoint_labels.append(label)
        arc_start_utc, arc_end_utc, hour_start_utc, hour_end_utc = endpoint_labels
    except EphemerisSourceError:
        raise
    except runtime.native_ephemeris_errors() as error:
        runtime._log_swe_runtime_failure("planetary_hours_civil_conversion", error)
        return None
    weekday_receipt = {}
    if opening_epoch is None:
        sunrise_calendar = ZonedCalendar(
            opening_calendar, parse_timezone_name(timezone_name)
        )
        sunrise_label = sunrise_calendar.rule_sample()
        if is_unspecified_local_time(sunrise_label):
            return "opening_sunrise_civil_weekday_undefined"
    else:
        sunrise_label = solar_wall_clock(opening_epoch, longitude, weekday_clock_basis)
        weekday_receipt = {
            "weekday_clock_basis": weekday_clock_basis,
            "weekday_opening_sunrise_label": sunrise_label.isoformat(),
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
        "planetary_day_start_utc": opening_label,
        "arc_start_utc": arc_start_utc,
        "arc_end_utc": arc_end_utc,
        "hour_start_utc": hour_start_utc,
        "hour_end_utc": hour_end_utc,
        "arc_start_jd_ut1": arc_start,
        "arc_end_jd_ut1": arc_end,
        "rule_id": "unequal_hours_chaldean_sunrise_weekday_v1",
        "sunrise_convention": "apparent_solar_center_sea_level_1013.25hPa_0C",
        **weekday_receipt,
    }


def _build_classical_layer(
    planets: list[dict[str, Any]],
    houses: list[dict[str, Any]],
    ascendant: float | None,
    *,
    chart_sect: str,
    states: dict[str, dict[str, float]] | None = None,
    source_ecliptic_coordinates: dict[str, tuple[float, float]] | None = None,
    julian_day: float | UT1Instant | None = None,
    julian_day_tt: float | TTInstant | None = None,
    sidereal: bool = False,
    lot_longitudes: dict[str, Fraction] | None = None,
    houses_resolved: bool = True,
) -> dict[str, Any]:
    """Build planetary conditions, almutens, lots, syzygy and temperament."""
    states = states or {}
    obliquity = None
    if runtime.swe is None:
        frame_tt = julian_day_tt
        if frame_tt is None and julian_day is not None:
            frame_tt = fallback_julian_day_tt(julian_day, None)
        if frame_tt is not None:
            obliquity = analytic_ecliptic_frame(frame_tt).true_obliquity
    elif julian_day is not None or julian_day_tt is not None:
        try:
            angles, flag = (
                fast_swe_call(
                    "calc",
                    TTInstant.from_value(julian_day_tt).as_float(),
                    runtime.swe.ECL_NUT,
                )
                if julian_day_tt is not None
                else fast_swe_call(
                    "calc_ut",
                    (
                        julian_day.as_float()
                        if isinstance(julian_day, UT1Instant)
                        else julian_day
                    ),
                    runtime.swe.ECL_NUT,
                )
            )
            if flag >= 0:
                obliquity = float(angles[0])
        except EphemerisSourceError:
            raise
        except runtime.native_ephemeris_errors() as error:
            runtime._log_swe_runtime_failure("ECL_NUT(obliquity)", error)
    is_day = chart_sect == "day"
    sun = next((item for item in planets if item["id"] == "Sun"), None)
    sun_longitude = sun["longitude"] if sun else None
    moon = next((item for item in planets if item["id"] == "Moon"), None)
    asc_sign = _sign_name(ascendant) if ascendant is not None else None

    planet_layer: dict[str, Any] = {}
    placements: dict[str, str] = {}
    lons: dict[str, float] = {}
    for item in planets:
        state = states.get(item["id"], {})
        planet_layer[item["id"]] = build_planet_classical(
            planet=item["id"],
            sign=item["sign"],
            degree_in_sign=item["degree_in_sign"],
            longitude=item["longitude"],
            house=item.get("house") if houses_resolved else None,
            sun_longitude=sun_longitude,
            chart_sect=chart_sect,
            longitude_speed=state.get("longitude_speed"),
            declination=state.get("declination"),
            altitude=state.get("altitude"),
            obliquity=obliquity,
            source_ecliptic_coordinates=(
                source_ecliptic_coordinates.get(item["id"])
                if source_ecliptic_coordinates is not None
                else None
            ),
        )
        placements[item["id"]] = item["sign"]
        lons[item["id"].lower()] = item["longitude"]

    houses_for_almuten = {
        house["house"]: {
            "sign": house["sign"],
            "degree_in_sign": float(house["cusp_longitude"]) % 30.0,
        }
        for house in houses
        if houses_resolved and house.get("sign") is not None
    }
    # The Fortune marker is the physical ascendant, even in whole-sign houses.
    if ascendant is not None:
        lons["asc"] = ascendant
    for house in houses:
        if houses_resolved and house["house"] == 8:
            lons["eighth"] = float(house["cusp_longitude"])

    lots = build_lots_layer(
        lons, is_day, lot_longitudes=lot_longitudes if ascendant is not None else None
    )
    syzygy = (
        _prenatal_syzygy(julian_day, julian_day_tt=julian_day_tt, sidereal=sidereal)
        if julian_day is not None
        else None
    )
    fortune = lots.get("fortune")
    figuris_points: dict[str, dict[str, Any]] = {}
    if sun:
        figuris_points["Sun"] = sun
    if moon:
        figuris_points["Moon"] = moon
    if ascendant is not None:
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
        "almuten_figuris": build_almuten_figuris(
            figuris_points,
            is_day,
            unknown_points=("Ascendant", "fortune") if ascendant is None else (),
        ),
        "temperament": build_temperament(
            asc_sign,
            RULER_BY_SIGN.get(asc_sign) if asc_sign is not None else None,
            sun["sign"] if sun else None,
            moon["sign"] if moon else None,
            ascendant_resolved=ascendant is not None,
        ),
    }


def _build_fixed_stars(
    planets: list[dict[str, Any]],
    ascendant: float | None,
    midheaven: float,
    julian_day: float,
    *,
    julian_day_tt: float | TTInstant | None = None,
    sidereal: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """fixed_stars block — catalogue stars conjunct planets / Asc / MC.

    The catalogue is bundled. Missing native positions are explicitly marked
    unavailable, separately from a computed empty conjunction list.
    """
    points = {planet["id"]: planet["longitude"] for planet in planets}
    if ascendant is not None:
        points["Ascendant"] = normalize_angle(ascendant)
    points["Midheaven"] = normalize_angle(midheaven)
    return build_fixed_star_layer(
        points,
        julian_day,
        julian_day_tt=(
            TTInstant.from_value(julian_day_tt).as_float()
            if julian_day_tt is not None
            else None
        ),
        sidereal=sidereal,
    )


def _build_classical_patterns(
    planets: list[dict[str, Any]],
    aspects: list[dict[str, Any]],
    states: dict[str, dict[str, float]] | None = None,
    *,
    chart_sect: str,
) -> dict[str, Any]:
    """The chart's classical_patterns block — [古典格局] relational layer
    states carries per-planet speed for translation/
    collection of light; the North Node longitude drives nodal bending. Classical rules
    share tables through astrology_tables."""
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
