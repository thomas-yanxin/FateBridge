"""
FateBridge western *lifespan* techniques.

This module hosts deterministic derived techniques with method-specific inputs.
Some read fixed natal tables; others use actual postbirth positions or a target
date. Source conformity and numerical accuracy require separate comparisons.

The techniques:

* build_harmonic_payload — 调波盘 (harmonic chart): natal longitudes
  multiplied by an integer harmonic number, then re-read for conjunctions.
* build_planetary_ages_payload — 行星年龄 (Ptolemy's seven ages):
  a fixed age table mapping each life band to its ruling planet.
* build_triplicity_rulers_payload — 三分主星推运: the sect light's
  triplicity rulers, ordered by sect, divide life into stages.
* build_lunation_phase_payload — 月相推运: actual postbirth Sun–Moon
  crossings mapped to symbolic years through the shared progression clock.
* build_distributions_payload — 界推运 / 分配法: the Ascendant directed
  through the Egyptian bounds, each bound's lord governing one period.
* build_balbillus_payload — Balbillus 129年系统: small-year periods
  shortened by each planet's distance from its exaltation, in zodiacal order.
* build_keypoints_payload — 数字相位推运 (120-year keypoints): planets
  activated by year when it is a multiple of their position- or period-number.

Builders receive method-specific inputs and return plain dict payloads.
Envelope assembly and snapshot rendering live in the service layer, mirroring
western_timing_tools — this module stays computation-only.
"""

from __future__ import annotations

from datetime import timedelta
from fractions import Fraction
from typing import Any

from fatebridge.core.astro.angle_definitions import is_ascendant_resolved
from fatebridge.core.astro.astrology_tables import ELEMENT_BY_SIGN, SIGNS
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.ephemeris import _swisseph_planet_state
from fatebridge.core.astro.geometry import Angle, angle_fraction, longitude_float
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    PhysicalSourceCohort,
)
from fatebridge.core.astro.time_scales import ephemeris_time, utc_point_from_tt
from fatebridge.core.ephemeris_runtime import preserve_ephemeris_path
from fatebridge.core.lunar_phase_events import phase_crossings_tt
from fatebridge.core.predictive._common import (
    TIMING_POINT_NAMES,
    collect_aspect_hits,
    longitude_to_point_dict,
    normalize_sign_name,
    planet_label,
    resolve_egyptian_bound,
    sign_label,
    source_arc_positions,
)
from fatebridge.core.predictive.native_chart import NativeSubject
from fatebridge.core.predictive.progressions import secondary_progression_clock_options
from fatebridge.utils.civil_time import nominal_calendar_bracket

# Fixed classical tables.

# Ptolemy's seven ages of man (Tetrabiblos IV.10). Each entry is the *start* age
# of the band in years; the band runs until the next entry's start (Saturn runs
# open-ended to the end of life). The order is the natural planetary speed order
# from fastest (Moon) to slowest (Saturn).
PTOLEMY_SEVEN_AGES: list[tuple[str, float, float | None]] = [
    ("Moon", 0.0, 4.0),
    ("Mercury", 4.0, 14.0),
    ("Venus", 14.0, 22.0),
    ("Sun", 22.0, 41.0),
    ("Mars", 41.0, 56.0),
    ("Jupiter", 56.0, 68.0),
    ("Saturn", 68.0, None),
]
# Dorothean triplicity rulers — the standard table used for triplicity life-period
# techniques (distinct from the Ptolemaic variant, which we deliberately do not
# use here). Each element maps to its day ruler, night ruler, and the cooperating
# "participating" ruler.
DOROTHEAN_TRIPLICITY_RULERS: dict[str, dict[str, str]] = {
    "Fire": {"day": "Sun", "night": "Jupiter", "participating": "Saturn"},
    "Earth": {"day": "Venus", "night": "Moon", "participating": "Mars"},
    "Air": {"day": "Saturn", "night": "Mercury", "participating": "Jupiter"},
    "Water": {"day": "Venus", "night": "Mars", "participating": "Moon"},
}
ELEMENT_LABELS_ZH: dict[str, str] = {
    "Fire": "火象",
    "Earth": "土象",
    "Air": "风象",
    "Water": "水象",
}

# Classical planetary period-years (行星期), used to time triplicity stage handovers.
PLANETARY_PERIOD_YEARS: dict[str, int] = {
    "Sun": 19,
    "Moon": 25,
    "Mercury": 20,
    "Venus": 8,
    "Mars": 15,
    "Jupiter": 12,
    "Saturn": 30,
}

# Nominal lifespan that triplicity stages divide. 75 matches the 星阙/Horosa
# reference default; it is an explicit dividing convention, not a prediction.
TRIPLICITY_DEFAULT_LIFESPAN = 75.0

# House angularity classes (角/续/果宫) for a quick ruler-strength readout.
ANGULAR_HOUSES = {1, 4, 7, 10}
SUCCEDENT_HOUSES = {2, 5, 8, 11}
ANGULARITY_LABELS_ZH = {
    "angular": "角宫·旺",
    "succedent": "续宫·中",
    "cadent": "果宫·衰",
}

# The eight lunar phases, each spanning 45° of Sun–Moon elongation.
LUNAR_PHASES: list[tuple[str, str, float]] = [
    ("new", "新月", 0.0),
    ("crescent", "蛾眉月", 45.0),
    ("first_quarter", "上弦月", 90.0),
    ("gibbous", "盈凸月", 135.0),
    ("full", "满月", 180.0),
    ("disseminating", "亏凸月", 225.0),
    ("last_quarter", "下弦月", 270.0),
    ("balsamic", "残月", 315.0),
]
# Time-key rates for directing the Ascendant in 界推运 (degrees of arc per year).
DISTRIBUTION_TIME_KEY_RATES: dict[str, float] = {
    "Ptolemy": 1.0,
    "Naibod": 0.98564733,
}


# Small geometry helpers.


def _wrap360(degree: float) -> float:
    """Normalize an angle into the [0, 360) range."""
    return degree % 360.0


def _natal_longitudes(natal_reference: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Map TIMING_POINT_NAMES to their absolute natal longitudes."""
    longitudes: dict[str, float] = {}
    for point_name in TIMING_POINT_NAMES:
        point = natal_reference.get(point_name.lower())
        if point is None:
            continue
        elif point_name == "Ascendant" and not is_ascendant_resolved(natal_reference):
            continue
        else:
            longitudes[point_name] = float(point["absolute_degree"])
    return longitudes


def _angularity(house: int | None) -> str | None:
    """Classify a house number as angular / succedent / cadent."""
    if house is None:
        return None
    if house in ANGULAR_HOUSES:
        return "angular"
    if house in SUCCEDENT_HOUSES:
        return "succedent"
    return "cadent"


def _planet_condition(
    point_name: str, natal_reference: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Compact natal placement of point_name for ruler/age readouts."""
    point = natal_reference.get(point_name.lower(), {})
    house = point.get("house")
    angularity = _angularity(house)
    return {
        "planet": point_name,
        "planet_label": planet_label(point_name),
        "sign": point.get("sign"),
        "sign_label": point.get("sign_label"),
        "degree": point.get("degree"),
        "house": house,
        "house_label": point.get("house_label"),
        "angularity": angularity,
        "angularity_label": ANGULARITY_LABELS_ZH.get(angularity or ""),
        "retrograde": point.get("retrograde"),
    }


# 1. 调波盘 (harmonic chart).


def build_harmonic_payload(
    natal_reference: dict[str, dict[str, Any]],
    *,
    harmonic: int,
    orb: float,
) -> dict[str, Any]:
    """
    Build the harmonic chart: each natal longitude is multiplied by harmonic
    and reduced mod 360. Bodies that fall within orb of each other in this
    harmonic field form 同频合相 (harmonic conjunctions).
    """
    longitudes = _natal_longitudes(natal_reference)

    # Keep the product before one display conversion: 7 * float(30/7) can
    # round a value below 30 onto the next sign, and alter orb membership.
    exact_longitudes = {
        point_name: (Fraction(natal_lon) * harmonic) % 360
        for point_name, natal_lon in longitudes.items()
    }
    positions: dict[str, dict[str, Any]] = {}
    for point_name, natal_longitude in longitudes.items():
        exact_longitude = exact_longitudes[point_name]
        displayed_longitude = longitude_float(exact_longitude)
        # note (Claude Code): Preserve ordinary display values and correct rounding across a whole-degree boundary.
        position_longitude = (
            exact_longitude
            if int(displayed_longitude % 30) != int(exact_longitude % 30)
            else displayed_longitude
        )
        position = longitude_to_point_dict(point_name, position_longitude)
        position["natal_absolute_degree"] = round(natal_longitude, 4)
        positions[point_name.lower()] = position

    conjunctions = []
    ordered = list(longitudes.keys())
    for index, first_name in enumerate(ordered):
        for second_name in ordered[index + 1 :]:
            difference = (
                exact_longitudes[first_name] - exact_longitudes[second_name]
            ) % 360
            separation = min(difference, 360 - difference)
            if separation <= orb:
                conjunctions.append(
                    (
                        separation,
                        {
                            "points": [first_name, second_name],
                            "points_label": [
                                planet_label(first_name),
                                planet_label(second_name),
                            ],
                            "separation_degree": round(float(separation), 4),
                            "orb": orb,
                        },
                    )
                )
    conjunctions.sort(key=lambda item: item[0])

    return {
        "harmonic": harmonic,
        "orb": orb,
        "method": "natal_longitude_times_harmonic",
        "method_label": f"{harmonic} 调波（本命黄经 × {harmonic} 取模 360°）",
        "positions": positions,
        "resonant_conjunctions": [row for _, row in conjunctions],
    }


# 2. 行星年龄 (Ptolemy's seven ages).


def build_planetary_ages_payload(
    natal_reference: dict[str, dict[str, Any]],
    *,
    current_age_years: float | None = None,
) -> dict[str, Any]:
    """
    Build Ptolemy's seven-ages table. Each life band is governed by one of the
    seven traditional planets; when current_age_years is given, the active
    band is flagged.
    """
    bands: list[dict[str, Any]] = []
    active_planet: str | None = None
    for planet, start_age, end_age in PTOLEMY_SEVEN_AGES:
        is_active = (
            current_age_years is not None
            and start_age <= current_age_years
            and (end_age is None or current_age_years < end_age)
        )
        if is_active:
            active_planet = planet
        bands.append(
            {
                "planet": planet,
                "planet_label": planet_label(planet),
                "start_age": start_age,
                "end_age": end_age,
                "duration_years": (
                    None if end_age is None else round(end_age - start_age, 2)
                ),
                "natal_condition": _planet_condition(planet, natal_reference),
                "active": is_active,
            }
        )

    if current_age_years is None:
        status = "reference_date_unspecified"
    elif current_age_years < 0:
        status = "pre_birth"
    else:
        status = "active"

    return {
        "system": "ptolemy_seven_ages",
        "system_label": "托勒密七年龄段",
        "status": status,
        "current_age_years": (
            None if current_age_years is None else round(current_age_years, 2)
        ),
        "active_planet": active_planet,
        "active_planet_label": (
            None if active_planet is None else planet_label(active_planet)
        ),
        "bands": bands,
    }


# 3. 三分主星推运 (triplicity rulers of the sect light).


def build_triplicity_rulers_payload(
    natal_reference: dict[str, dict[str, Any]],
    *,
    sect: str,
    lifespan: float = TRIPLICITY_DEFAULT_LIFESPAN,
    division: str = "thirds",
) -> dict[str, Any]:
    """
    Divide life into stages governed by the three triplicity rulers of the sect
    light's sign. Ruler order follows sect: a day birth runs day → night →
    participating; a night birth runs night → day → participating.

    division controls how the (nominal) lifespan is split:

    * "thirds" — three equal stages (0–L/3, L/3–2L/3, 2L/3–L).
    * "halves" — main ruler the first half, secondary the second, with the
      participating ruler running across the whole life.

    The age bands use lifespan purely as a dividing convention (default 75,
    matching the Horosa reference), not as a prediction.
    """
    light_name = "Sun" if sect == "day" else "Moon"
    light_point = natal_reference.get(light_name.lower(), {})
    light_sign = normalize_sign_name(light_point.get("sign", "") or "")
    element = ELEMENT_BY_SIGN.get(light_sign)
    rulers = DOROTHEAN_TRIPLICITY_RULERS.get(element or "", {})

    if sect == "day":
        ordered_roles = ["day", "night", "participating"]
    else:
        ordered_roles = ["night", "day", "participating"]

    role_labels = {"day": "昼主星", "night": "夜主星", "participating": "共主星"}
    if division == "halves":
        spans = [(0.0, lifespan / 2), (lifespan / 2, lifespan), (0.0, lifespan)]
        stage_labels = ["主星·上半生", "次星·下半生", "共主星·贯穿"]
    else:
        division = "thirds"
        third = lifespan / 3
        spans = [(0.0, third), (third, 2 * third), (2 * third, lifespan)]
        stage_labels = ["前期（早年）", "中期（中年）", "后期（晚年）"]

    stages: list[dict[str, Any]] = []
    for index, role in enumerate(ordered_roles):
        planet = rulers.get(role)
        start_age, end_age = spans[index]
        stages.append(
            {
                "stage": index + 1,
                "stage_label": stage_labels[index],
                "role": role,
                "role_label": role_labels[role],
                "ruler": planet,
                "ruler_label": None if planet is None else planet_label(planet),
                "start_age": round(start_age, 2),
                "end_age": round(end_age, 2),
                "planetary_period_years": (
                    PLANETARY_PERIOD_YEARS.get(planet) if planet else None
                ),
                "natal_condition": (
                    _planet_condition(planet, natal_reference) if planet else None
                ),
            }
        )

    return {
        "system": "dorothean_triplicity",
        "system_label": "多罗修斯三分主星",
        "sect": sect,
        "sect_label": "日盘" if sect == "day" else "夜盘",
        "sect_light": light_name,
        "sect_light_label": planet_label(light_name),
        "sect_light_sign": light_sign,
        "sect_light_sign_label": sign_label(light_sign) if light_sign else None,
        "element": element,
        "element_label": ELEMENT_LABELS_ZH.get(element or ""),
        "lifespan_years": lifespan,
        "division": division,
        "stages": stages,
    }


# 4. 月相推运 (progressed lunation phase).


def _phase_for_elongation(elongation: Angle) -> tuple[str, str]:
    """Return the (key, label) of the lunar phase containing elongation."""
    band = int((angle_fraction(elongation) % 360) // 45)
    key, label, _ = LUNAR_PHASES[band]
    return key, label


@preserve_ephemeris_path()
def build_lunation_phase_payload(
    birth_info: AstroBirthInfo,
    natal_subject: NativeSubject,
    *,
    max_age_years: float,
) -> dict[str, Any]:
    """
    Solve actual postbirth Sun–Moon crossings, then map raw UTC nominal days
    since birth to symbolic years. No universal synodic rate or cycle is used.
    """
    birth_day = birth_info.utc_calendar.julian_day_exact()
    max_age = Fraction(max_age_years)
    # This is only a search enclosure. Membership below uses the original
    # exact nominal cap, never this calendar rounding or a formatting cap.
    cap_calendar = nominal_calendar_bracket(birth_day + max_age)[1]
    cap_tt = ephemeris_time(cap_calendar).tt
    if cap_tt is None:
        raise ValueError("Progressed lunation window requires a known TT clock")
    trace = PhysicalEphemerisTrace()
    cohort = PhysicalSourceCohort()
    natal_source = natal_subject.calculation_basis["physical_ephemeris_source"]
    natal_factors = {name: natal_source["by_factor"][name] for name in ("Sun", "Moon")}
    natal_file_ids = {
        identity for factor in natal_factors.values() for identity in factor["file_ids"]
    }
    cohort.add(
        {
            **natal_source,
            "by_factor": natal_factors,
            "files": [
                file for file in natal_source["files"] if file["id"] in natal_file_ids
            ],
        }
    )
    samples: dict[float, Fraction] = {}
    from fatebridge.core.astro import runtime as _astro_rt
    from fatebridge.core.ephemeris_runtime import EPHEMERIS_LOCK as _EPHEM_LOCK
    from fatebridge.core.ephemeris_runtime import (
        _ensure_thread_ephemeris_path as _ensure_ephem_path,
    )
    from fatebridge.core.ephemeris_runtime import ephemeris_call as _orig_ephem_call
    from fatebridge.core.jpl_ephemeris import configured_jpl_file as _jpl_file

    use_fast_lunation = (
        _astro_rt.ephemeris_call is _orig_ephem_call
        and _jpl_file() is None
        and _astro_rt.swe is not None
    )
    swe_mod = _astro_rt.swe
    fast_lun_flags = (
        (swe_mod.FLG_SWIEPH | swe_mod.FLG_SPEED) if swe_mod is not None else 0
    )

    def phase_at(jd_tt: float) -> Fraction:
        if jd_tt in samples:
            return samples[jd_tt]
        longitudes: list[Fraction] = []
        speeds: list[float] = []
        if use_fast_lunation and jd_tt != natal_subject.tt.as_float():
            for body_id in (swe_mod.SUN, swe_mod.MOON):
                coords, flag = swe_mod.calc(jd_tt, body_id, fast_lun_flags)
                if flag < 0:
                    raise ValueError("Progressed lunation ephemeris source unavailable")
                longitudes.append(Fraction(float(coords[0]) % 360.0))
                speeds.append(float(coords[3]))
        else:
            for name in ("Sun", "Moon"):
                result = _swisseph_planet_state(
                    name,
                    julian_day_tt=jd_tt,
                    source_trace=trace,
                    correct_motion=False,
                    include_declination=False,
                )
                if result is None:
                    raise ValueError("Progressed lunation ephemeris source unavailable")
                state, _model = result
                longitudes.append(Fraction(state["longitude"]))
                speeds.append(state["longitude_speed"])
            cohort.add(trace.snapshot())
        if speeds[1] <= speeds[0]:
            raise ValueError("Progressed lunation requires increasing Moon–Sun motion")
        elongation = (longitudes[1] - longitudes[0]) % 360
        samples[jd_tt] = elongation
        return elongation

    def phase_float_at(jd_tt: float) -> float:
        if jd_tt in samples:
            return float(samples[jd_tt])
        if use_fast_lunation and jd_tt != natal_subject.tt.as_float():
            c_sun, f_sun = swe_mod.calc(jd_tt, swe_mod.SUN, fast_lun_flags)
            c_moon, f_moon = swe_mod.calc(jd_tt, swe_mod.MOON, fast_lun_flags)
            if f_sun < 0 or f_moon < 0:
                raise ValueError("Progressed lunation ephemeris source unavailable")
            if float(c_moon[3]) <= float(c_sun[3]):
                raise ValueError(
                    "Progressed lunation requires increasing Moon–Sun motion"
                )
            return ((float(c_moon[0]) % 360.0) - (float(c_sun[0]) % 360.0)) % 360.0
        return float(phase_at(jd_tt))

    natal_elongation = phase_at(natal_subject.tt.as_float())
    natal_key, natal_label = _phase_for_elongation(natal_elongation)
    timeline: list[dict[str, Any]] = []
    if use_fast_lunation:
        with _EPHEM_LOCK:
            _ensure_ephem_path()
            crossings = phase_crossings_tt(
                natal_subject.tt,
                cap_tt,
                phase_at,
                step_degrees=45,
                include_end=True,
                phase_float_at=phase_float_at,
            )
    else:
        crossings = phase_crossings_tt(
            natal_subject.tt,
            cap_tt,
            phase_at,
            step_degrees=45,
            include_end=True,
            phase_float_at=phase_float_at,
        )
    for crossing in crossings:
        civil = utc_point_from_tt(crossing.tt)
        age = civil.day - birth_day
        if not 0 < age <= max_age:
            continue
        key, label, _start_degree = LUNAR_PHASES[crossing.target_elongation // 45]
        timeline.append(
            {
                "phase": key,
                "phase_label": label,
                "ingress_age_years": float(round(age, 3)),
                "elongation_degree": float(crossing.target_elongation),
                "progressed_julian_day_tt": crossing.tt.as_float(),
                "progressed_utc_point": civil.to_record(),
                "progressed_datetime_utc": civil.as_calendar().isoformat(),
                "source_root_bracket_tt": [
                    crossing.lower_tt.as_float(),
                    crossing.upper_tt.as_float(),
                ],
                "residual_degrees": float(crossing.residual),
            }
        )

    return {
        "system": "progressed_lunation_phase",
        "system_label": "次限月相推运",
        "method_id": "fatebridge_secondary_ephemeris_lunation_v1",
        "natal_elongation_degree": round(float(natal_elongation), 4),
        "natal_phase": natal_key,
        "natal_phase_label": natal_label,
        "max_age_years": max_age_years,
        "progression_options": secondary_progression_clock_options(),
        "age_basis": "exact_progressed_utc_nominal_days_from_birth_per_symbolic_year",
        "physical_ephemeris_source": trace.finish(),
        "solver": {
            "method": "daily_full_window_scan_with_bracketed_bisection_native_tt",
            "step_days": 1.0,
            "max_bisection_iterations": 64,
            "window_tt_jd": [natal_subject.tt.as_float(), cap_tt.as_float()],
            "window_membership": "strictly_after_birth_through_exact_nominal_age_cap",
        },
        "phase_ingresses": timeline,
        "phase_ingress_count": len(timeline),
    }


# 5. 界推运 / 分配法 (distributions through the Egyptian bounds).


def _bound_segments_from(
    asc_longitude: float, span_degrees: float
) -> list[dict[str, Any]]:
    """
    Walk span_degrees of zodiacal arc forward from asc_longitude, yielding
    one entry per Egyptian bound crossed, with the absolute arc at which the
    directed Ascendant enters that bound.
    """
    segments: list[dict[str, Any]] = []
    origin = Fraction(asc_longitude) % 360
    span = Fraction(span_degrees)
    cursor = Fraction(0)
    while cursor < span:
        directed = (origin + cursor) % 360
        sign_name = SIGNS[int(directed // 30)]
        degree_in_sign = directed % 30
        bound = resolve_egyptian_bound(sign_name, float(degree_in_sign))
        to_boundary = Fraction(bound["segment_end_degree"]) - degree_in_sign
        segments.append(
            {
                "bound": bound,
                "sign": sign_name,
                "enter_arc": cursor,
                "exit_arc": min(cursor + to_boundary, span),
            }
        )
        cursor += to_boundary
    return segments


def build_distributions_payload(
    natal_reference: dict[str, dict[str, Any]],
    *,
    time_key: str,
    max_age_years: float,
) -> dict[str, Any]:
    """
    Direct the Ascendant through the Egyptian bounds at the chosen time_key
    rate. Each bound the directed Ascendant occupies defines a period whose
    distributor is that bound's lord; natal bodies the directed Ascendant
    conjoins inside a period are recorded as participants (partners).
    """
    rate = DISTRIBUTION_TIME_KEY_RATES.get(time_key, 1.0)
    asc_point = natal_reference.get("ascendant", {})
    asc_raw = asc_point.get("absolute_degree")
    if asc_raw is None or not is_ascendant_resolved(natal_reference):
        return {
            "system": "distributions_through_bounds",
            "system_label": "界推运（上升历经埃及界限）",
            "status": "underdetermined_ascendant",
            "ascendant_resolved": False,
            "unavailable_reason": "ascendant_required_for_bounds_directions",
            "direction_model": "zodiacal",
            "direction_model_label": "黄道度数推进（每年 rate° 推进上升黄经）",
            "time_key": time_key,
            "rate_deg_per_year": round(rate, 8),
            "ascendant_absolute_degree": None,
            "max_age_years": max_age_years,
            "periods": [],
        }

    asc_longitude = float(asc_raw)
    span_degrees = max_age_years * rate
    longitudes = _natal_longitudes(natal_reference)

    periods: list[dict[str, Any]] = []
    for segment in _bound_segments_from(asc_longitude, span_degrees):
        bound = segment["bound"]
        start_age = segment["enter_arc"] / rate
        end_age = segment["exit_arc"] / rate

        participants: list[dict[str, Any]] = []
        for point_name, natal_lon in longitudes.items():
            if point_name in ("Ascendant", "Medium_Coeli"):
                continue
            # Arc from the Ascendant to this body, measured forward.
            contact_arc = (Fraction(natal_lon) - Fraction(asc_longitude)) % 360
            if segment["enter_arc"] <= contact_arc < segment["exit_arc"]:
                participants.append(
                    {
                        "planet": point_name,
                        "planet_label": planet_label(point_name),
                        "contact_age_years": round(contact_arc / rate, 3),
                    }
                )
        participants.sort(key=lambda item: item["contact_age_years"])

        periods.append(
            {
                "distributor": bound["bound_lord"],
                "distributor_label": bound["bound_lord_label"],
                "sign": segment["sign"],
                "sign_label": sign_label(segment["sign"]),
                "bound_start_degree": bound["segment_start_degree"],
                "bound_end_degree": bound["segment_end_degree"],
                "start_age_years": round(start_age, 3),
                "end_age_years": round(end_age, 3),
                "participants": participants,
            }
        )

    return {
        "system": "distributions_through_bounds",
        "system_label": "界推运（上升历经埃及界限）",
        "direction_model": "zodiacal",
        "direction_model_label": "黄道度数推进（每年 rate° 推进上升黄经）",
        "time_key": time_key,
        "rate_deg_per_year": round(rate, 8),
        "ascendant_absolute_degree": round(asc_longitude, 4),
        "max_age_years": max_age_years,
        "periods": periods,
    }


# 6. Balbillus 129年系统 (旺距削减主限).

# Seven-planet "small years" of the Balbillus 129-year system (Σ = 129).
BALBILLUS_SMALL_YEARS: dict[str, int] = {
    "Sun": 19,
    "Moon": 25,
    "Saturn": 30,
    "Jupiter": 12,
    "Mars": 15,
    "Venus": 8,
    "Mercury": 20,
}
# Traditional exaltation degrees (absolute ecliptic longitude).
BALBILLUS_EXALTATION: dict[str, float] = {
    "Sun": 19.0,  # Aries 19°
    "Moon": 33.0,  # Taurus 3°
    "Saturn": 201.0,  # Libra 21°
    "Jupiter": 105.0,  # Cancer 15°
    "Mars": 298.0,  # Capricorn 28°
    "Venus": 357.0,  # Pisces 27°
    "Mercury": 165.0,  # Virgo 15°
}
# CCAG VIII.4 p237.16-22 assigns complete small years at exaltation and a
# degree-distance reduction. Keep the declared continuous-angle reading; do
# not fit planet-specific offsets to another program.
BALBILLUS_PLANET_ORDER = [
    "Sun",
    "Moon",
    "Saturn",
    "Jupiter",
    "Mars",
    "Venus",
    "Mercury",
]
BALBILLUS_MODES = {"nearest": "最近角距", "forward": "顺黄道距"}


def _balbillus_distance(longitude: float, exaltation: float, mode: str) -> float:
    """Angular distance from a natal longitude to its exaltation degree."""
    raw = _wrap360(longitude - exaltation)
    if mode == "forward":
        return raw
    return min(raw, 360.0 - raw)


def _balbillus_period_years(planet: str, longitude: float | None, mode: str) -> float:
    """Major-period length (years) = small-year × (1 − distance/360)."""
    small_year = BALBILLUS_SMALL_YEARS[planet]
    if longitude is None:
        return float(small_year)
    distance = _balbillus_distance(longitude, BALBILLUS_EXALTATION[planet], mode)
    return small_year * (1.0 - distance / 360.0)


def _balbillus_order(
    longitudes: dict[str, float | None], start_planet: str
) -> list[str]:
    """Seven planets sorted by natal longitude, rotated to start_planet."""
    present = [p for p in BALBILLUS_PLANET_ORDER if longitudes.get(p) is not None]
    ordered = sorted(present, key=lambda p: _wrap360(float(longitudes[p])))  # type: ignore[arg-type]
    if not ordered:
        ordered = list(BALBILLUS_PLANET_ORDER)
    if start_planet in ordered:
        pivot = ordered.index(start_planet)
        ordered = ordered[pivot:] + ordered[:pivot]
    return ordered


def build_balbillus_payload(
    natal_reference: dict[str, dict[str, Any]],
    *,
    start_planet: str = "Sun",
    mode: str = "nearest",
    max_age_years: float = 120.0,
) -> dict[str, Any]:
    """
    Build the selected Balbillus time-lord reading. Reduce each small year by
    its distance from exaltation, and subdivide that parent in 129 small-year
    shares. The natal zodiacal sequence is a conditional reading of the text.
    """
    if mode not in BALBILLUS_MODES:
        mode = "nearest"
    if start_planet not in BALBILLUS_SMALL_YEARS:
        start_planet = "Sun"

    longitudes: dict[str, float | None] = {
        p: (
            float(natal_reference[p.lower()]["absolute_degree"])
            if p.lower() in natal_reference
            else None
        )
        for p in BALBILLUS_PLANET_ORDER
    }
    order = _balbillus_order(longitudes, start_planet)

    periods: list[dict[str, Any]] = []
    cursor = 0.0
    guard = 0
    while cursor < max_age_years and guard < 200:
        planet = order[guard % len(order)]
        duration = _balbillus_period_years(planet, longitudes[planet], mode)
        if duration <= 0:
            break
        # CCAG VIII.4 p237.23-p238.2: divide this parent's years into 129
        # shares, allotting each child its unmodified small-year weight.
        # The parent receives its own share first, then the following stars.
        sub_order = order[order.index(planet) :] + order[: order.index(planet)]
        parent_end = cursor + duration
        sub_periods: list[dict[str, Any]] = []
        sub_cursor = cursor
        for sub_planet in sub_order:
            sub_duration = duration * BALBILLUS_SMALL_YEARS[sub_planet] / 129.0
            sub_periods.append(
                {
                    "planet": sub_planet,
                    "planet_label": planet_label(sub_planet),
                    "start_age_years": round(sub_cursor, 4),
                    "duration_years": round(sub_duration, 4),
                }
            )
            sub_cursor += sub_duration
        periods.append(
            {
                "planet": planet,
                "planet_label": planet_label(planet),
                "start_age_years": round(cursor, 4),
                "duration_years": round(duration, 4),
                "sub_periods": sub_periods,
            }
        )
        cursor = parent_end
        guard += 1

    return {
        "system": "balbillus_129",
        "system_label": "Balbillus 129年系统（旺距削减主限）",
        "start_planet": start_planet,
        "start_planet_label": planet_label(start_planet),
        "mode": mode,
        "mode_label": BALBILLUS_MODES[mode],
        "reduction_model": {
            "method_id": "balbillus_continuous_proportional_v3",
            "formula": "small_years * (1 - distance_degrees / 360)",
            "subperiod_formula": "parent_period * child_small_years / 129",
            "degree_basis": "continuous_ecliptic_longitude",
            "fitted_offsets_used": False,
            "source": {
                "title": "CCAG VIII.4, Balbillus excerpts, pp.237-238",
                "attribution": "Balbillus, transmitted by Palchus; catalogue P. Boudreaux, edition and appendix F. Cumont",
                "edition_year": 1921,
                "publisher": "Mauritius Lamertin, Brussels",
                "printed_pages": [237, 238],
                "critical_apparatus": "p237 note24 corrects manuscript 119 to 129 total shares and 119 to 19 Sun shares; compare the small-year list at lines18-19",
            },
            "source_scope": "selected critical-edition small years and129 subperiod shares; continuous degrees,360-day reduction and zodiacal sequence are conditional readings, not whole-procedure certification",
            "sequence_model": "natal_longitude_order_conditional_reading",
            "subperiod_model": "parent_period_times_child_small_years_over_129",
            "whole_procedure_certified": False,
        },
        "max_age_years": max_age_years,
        "zodiacal_order": order,
        "periods": periods,
    }


# 7. 数字相位推运 (120年关键点 / keypoints).

# Seven-planet period numbers for the keypoints (数字相位) technique.
KEYPOINTS_PERIOD_NUMBERS: dict[str, int] = {
    "Saturn": 3,
    "Mercury": 8,
    "Sun": 18,
    "Venus": 5,
    "Mars": 7,
    "Jupiter": 9,
    "Moon": 13,
}
KEYPOINTS_RELEASE_MODES = {"soul": "身（月亮起）", "body": "命（上升起）"}
KEYPOINTS_PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]


def _factor_pairs(number: int) -> list[list[int]]:
    """Non-trivial factor pairs [a, b] with a ≤ b (empty for primes)."""
    pairs: list[list[int]] = []
    factor = 2
    while factor * factor <= number:
        if number % factor == 0:
            pairs.append([factor, number // factor])
        factor += 1
    return pairs


def build_keypoints_payload(
    natal_reference: dict[str, dict[str, Any]],
    *,
    release_mode: str = "soul",
    max_age_years: int = 120,
) -> dict[str, Any]:
    """
    Build the 120-year keypoints timeline. Each planet carries a position-number
    k (signs from the release point) and a period-number; a year activates a
    planet when it is a multiple of that planet's k (position transfer) or of
    its period-number (table activation).
    """
    if release_mode not in KEYPOINTS_RELEASE_MODES:
        release_mode = "soul"
    max_age = max(1, min(120, int(max_age_years)))

    release_key = "ascendant" if release_mode == "body" else "moon"
    release_point = natal_reference.get(release_key, {})
    release_longitude = release_point.get("absolute_degree")
    if release_mode == "body" and (
        release_longitude is None or not is_ascendant_resolved(natal_reference)
    ):
        return {
            "system": "keypoints_120",
            "system_label": "数字相位推运（120年关键点）",
            "status": "underdetermined_ascendant",
            "ascendant_resolved": False,
            "unavailable_reason": "ascendant_required_for_body_release_mode",
            "release_mode": release_mode,
            "release_mode_label": KEYPOINTS_RELEASE_MODES[release_mode],
            "release_sign_index": None,
            "positions": [],
            "activations": [],
            "activation_count": 0,
        }
    if release_longitude is None:
        return {
            "system": "keypoints_120",
            "system_label": "数字相位推运（120年关键点）",
            "status": "unavailable",
            "unavailable_reason": f"missing_release_point_{release_key}",
            "release_mode": release_mode,
            "release_mode_label": KEYPOINTS_RELEASE_MODES[release_mode],
            "release_sign_index": None,
            "positions": [],
            "activations": [],
            "activation_count": 0,
        }

    release_sign = int(_wrap360(float(release_longitude)) // 30)
    positions: list[dict[str, Any]] = []
    for planet in KEYPOINTS_PLANETS:
        point = natal_reference.get(planet.lower())
        if point is None:
            continue
        sign_index = int(_wrap360(float(point["absolute_degree"])) // 30)
        position_number = ((sign_index - release_sign) % 12 + 12) % 12 + 1
        positions.append(
            {
                "planet": planet,
                "planet_label": planet_label(planet),
                "position_number": position_number,
                "period_number": KEYPOINTS_PERIOD_NUMBERS[planet],
            }
        )

    activations: list[dict[str, Any]] = []
    for age in range(1, max_age + 1):
        position_active = [
            {"planet": pos["planet"], "planet_label": pos["planet_label"]}
            for pos in positions
            if age % pos["position_number"] == 0
        ]
        period_active = [
            {
                "planet": planet,
                "planet_label": planet_label(planet),
                "period_number": KEYPOINTS_PERIOD_NUMBERS[planet],
            }
            for planet in KEYPOINTS_PLANETS
            if age % KEYPOINTS_PERIOD_NUMBERS[planet] == 0
        ]
        if not position_active and not period_active:
            continue
        activations.append(
            {
                "age": age,
                "house": ((age - 1) % 12) + 1,
                "factors": _factor_pairs(age),
                "position_active": position_active,
                "period_active": period_active,
            }
        )

    return {
        "system": "keypoints_120",
        "system_label": "数字相位推运（120年关键点）",
        "release_mode": release_mode,
        "release_mode_label": KEYPOINTS_RELEASE_MODES[release_mode],
        "release_sign_index": release_sign,
        "positions": positions,
        "activations": activations,
        "activation_count": len(activations),
    }


# 8. 129年系统 (yearsystem129).
# Shares Balbillus' seven "small years" (Σ = 129) but, unlike Balbillus, each
# planet rules its FULL small-year — there is no exaltation-distance reduction.
# The period order reuses Balbillus' verified zodiacal sequence (planets by natal
# longitude, rotated to a start planet). Horosa computes this in its closed
# backend with an ordering convention we cannot cross-check, so the sequence is
# labelled ``sequence_model="zodiacal"`` rather than claimed as bit-parity.


def build_yearsystem129_payload(
    natal_reference: dict[str, dict[str, Any]],
    *,
    start_planet: str = "Sun",
    max_age_years: float = 129.0,
) -> dict[str, Any]:
    """
    Build the 129-year system: seven planets each rule their full small-year, in
    zodiacal order from start_planet, cycling until max_age_years.
    """
    if start_planet not in BALBILLUS_SMALL_YEARS:
        start_planet = "Sun"
    longitudes: dict[str, float | None] = {
        p: (
            float(natal_reference[p.lower()]["absolute_degree"])
            if p.lower() in natal_reference
            else None
        )
        for p in BALBILLUS_PLANET_ORDER
    }
    order = _balbillus_order(longitudes, start_planet)

    periods: list[dict[str, Any]] = []
    cursor = 0.0
    guard = 0
    while cursor < max_age_years and guard < 200:
        planet = order[guard % len(order)]
        duration = float(BALBILLUS_SMALL_YEARS[planet])
        periods.append(
            {
                "planet": planet,
                "planet_label": planet_label(planet),
                "small_year": BALBILLUS_SMALL_YEARS[planet],
                "start_age_years": round(cursor, 4),
                "duration_years": duration,
            }
        )
        cursor += duration
        guard += 1

    return {
        "system": "yearsystem129",
        "system_label": "129年系统（七星小年轮值）",
        "sequence_model": "zodiacal",
        "sequence_model_label": "本命黄经序（与 Balbillus 同序；非 horosa 后端逐值核验）",
        "start_planet": start_planet,
        "start_planet_label": planet_label(start_planet),
        "total_cycle_years": sum(BALBILLUS_SMALL_YEARS.values()),
        "max_age_years": max_age_years,
        "zodiacal_order": order,
        "periods": periods,
    }


# 9. 行星弧方向 (planetaryarc).


def build_planetary_arc_payload(
    natal_longitudes: dict[str, float],
    progressed_longitudes: dict[str, float],
    *,
    arc_source: str,
    orb: float = 1.0,
    max_hits: int | None = None,
) -> dict[str, Any]:
    """
    Direct the whole natal chart by a single arc: the secondary-progressed motion
    of arc_source (default Moon). Every natal point advances by that arc, then
    we read the aspects the directed points make back to the natal chart.

    This generalises the solar arc (which always uses the Sun's progressed motion)
    to any progressing body, and is verifiable against FateBridge's own secondary
    progression: arc = progressed[arc_source] − natal[arc_source].
    """
    if arc_source not in natal_longitudes or arc_source not in progressed_longitudes:
        arc_source = "Moon"
    arc_degrees, directed_points = source_arc_positions(
        natal_longitudes,
        natal_longitudes[arc_source],
        progressed_longitudes[arc_source],
    )
    hits = collect_aspect_hits(
        source_longitudes=directed_points,
        target_longitudes=natal_longitudes,
        orb_limit=orb,
    )
    hits_total_count = len(hits)
    selected_hits = hits[:max_hits] if max_hits is not None else hits
    positions = {
        name.lower(): longitude_to_point_dict(name, longitude_float(degree))
        for name, degree in directed_points.items()
    }
    return {
        "system": "planetary_arc",
        "system_label": "行星弧方向",
        "arc_source": arc_source,
        "arc_source_label": planet_label(arc_source),
        "arc_degrees": round(float(arc_degrees), 4),
        "orb": orb,
        "positions": positions,
        "hits": selected_hits,
        "hits_total_count": hits_total_count,
    }


# 10. 波斯向运 (Persian Directed).

# 向运星 (promittors): only the seven classical planets advance.
PERSIAN_MOVERS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
# 触发的相位 (Ptolemaic set); 0°/180° are symmetric so they fire once, the rest twice (±).
PERSIAN_ASPECTS = [0, 60, 90, 120, 180]
# Symbolic rate: every mover gains 1° per year; the tropical year used to date the 应期.
PERSIAN_RATE_DEG_PER_YEAR = 1.0
PERSIAN_TROPICAL_YEAR_DAYS = 365.2421904


def build_persian_directed_payload(
    natal_longitudes: dict[str, float],
    house_cusps: list[float],
    *,
    birth_datetime: Any = None,
    max_age_years: float = 90.0,
    limit: int | None = 120,
) -> dict[str, Any]:
    """
    波斯向运 / Persian Directed (symbolic 1°/year).

    Faithful port of 星阙 AstroPersianDirected: every classical promittor advances
    +1°/year while the natal chart (every body plus the 12 house cusps) stays fixed; we
    list each age at which a directed promittor reaches a Ptolemaic aspect to a natal
    target, capped at max_age_years and the first limit hits by age.

    Rational arcs determine selection before display rounding. The hit set
    is bounded by the natal objects FateBridge exposes (planets + nodes + 12 cusps); it
    does NOT include 星阙's enriched bodies (asteroids / midpoints / Arabic lots / 四余),
    so the table is a clean subset of 星阙's, not a row-for-row match on a live chart.
    """
    by_id = {name: Fraction(lon) % 360 for name, lon in natal_longitudes.items()}
    targets = list(by_id.items())
    for index, cusp in enumerate(house_cusps):
        targets.append((f"{index + 1}宫头", Fraction(cusp) % 360))

    hits = []
    for promittor in PERSIAN_MOVERS:
        mover_lon = by_id.get(promittor)
        if mover_lon is None:
            continue
        for target_id, target_lon in targets:
            if target_id == promittor:
                continue
            for aspect in PERSIAN_ASPECTS:
                for sign in (1, -1):
                    if aspect in (0, 180) and sign == -1:
                        continue
                    contact = (target_lon + sign * aspect) % 360
                    arc = (contact - mover_lon) % 360
                    age = arc / Fraction(PERSIAN_RATE_DEG_PER_YEAR)
                    if not 0 < age <= max_age_years:
                        continue
                    date = ""
                    if birth_datetime is not None:
                        date = (
                            birth_datetime
                            + timedelta(days=float(age) * PERSIAN_TROPICAL_YEAR_DAYS)
                        ).strftime("%Y-%m-%d")
                    hits.append(
                        (
                            age,
                            {
                                "age": round(float(age) * 100) / 100,
                                "promittor": promittor,
                                "promittor_label": planet_label(promittor),
                                "aspect": aspect,
                                "significator": target_id,
                                "date": date,
                            },
                        )
                    )
    hits.sort(key=lambda hit: hit[0])
    selected = [row for _, row in (hits[:limit] if limit is not None else hits)]
    return {
        "system": "persian_directed",
        "system_label": "波斯向运",
        "rate_deg_per_year": PERSIAN_RATE_DEG_PER_YEAR,
        "max_age_years": max_age_years,
        "hit_count": len(selected),
        "hits_total_count": len(hits),
        "hits": selected,
    }


# 11. 年龄推进点 (Age Point / Huber).

# Huber 年龄推进点 traverses the 12 Koch houses from the Ascendant, 6 years per
# house, returning to the Ascendant after a full 72-year cycle (12 × 6).
AGE_POINT_YEARS_PER_HOUSE = 6.0
AGE_POINT_CYCLE_YEARS = 72.0


def _house_containing(
    longitude: float, koch_cusps: list[float]
) -> tuple[int, Fraction]:
    """Return (0-indexed house, fractional position within it) for longitude.

    Houses partition the circle, so exactly one Koch segment [cusp_h, cusp_{h+1})
    contains the point; the fraction is how far along that segment the point sits.
    """
    point = Fraction(longitude) % 360
    for house_index in range(12):
        start = Fraction(koch_cusps[house_index]) % 360
        end = Fraction(koch_cusps[(house_index + 1) % 12]) % 360
        arc = (end - start) % 360
        offset = (point - start) % 360
        if arc > 0 and offset < arc:
            return house_index, offset / arc
    raise ValueError("年龄推进点宫头未覆盖给定黄经，不能补为零岁上升点")


def build_age_point_payload(
    natal_longitudes: dict[str, float],
    koch_cusps: list[float],
    *,
    max_age_years: float = 72.0,
) -> dict[str, Any]:
    """
    年龄推进点 / Age Point (Huber).

    Reconstruction of the public Huber technique — 星阙/horosa computes this in a
    closed backend with no readable source or fixture, so this is verified by the
    technique's own geometric invariants (age 0 = Ascendant, age 6 = 2nd cusp, age 72
    = back to the Ascendant, monotone progress through the Koch houses) plus
    ground-truth on a real chart, NOT byte-parity against 星阙.

    The age point leaves the Ascendant and sweeps the 12 Koch houses in zodiacal
    order, spending exactly 6 years in each (linear in time within a house, so the
    angular speed varies with each Koch house's width). contacts gives the exact
    age at which the point conjoins each natal body; points is the per-year
    timeline (position + house), tagged with any conjunction landing that year.
    """
    cusps = koch_cusps
    years_per_house = Fraction(AGE_POINT_YEARS_PER_HOUSE)
    cycle_years = Fraction(AGE_POINT_CYCLE_YEARS)

    # Exact conjunction ages: where the swept point crosses each natal longitude.
    contacts: list[tuple[Fraction, str, float]] = []
    for body, longitude in natal_longitudes.items():
        house_index, fraction = _house_containing(longitude, cusps)
        base_age = (house_index + fraction) * years_per_house
        cycle = 0
        while base_age + cycle * cycle_years <= max_age_years:
            contact_age = base_age + cycle * cycle_years
            if contact_age > 0:
                contacts.append((contact_age, body, round(longitude % 360.0, 4)))
            cycle += 1
    contacts.sort(key=lambda contact: contact[0])

    # Per-year timeline: position + house, tagged with a conjunction landing that year.
    points: list[dict[str, Any]] = []
    for age in range(int(max_age_years) + 1):
        cycle_pos = age % AGE_POINT_CYCLE_YEARS
        house_index = int(cycle_pos // AGE_POINT_YEARS_PER_HOUSE)
        within = (Fraction(age) % cycle_years - house_index * years_per_house) / (
            years_per_house
        )
        start = Fraction(cusps[house_index]) % 360
        arc = (Fraction(cusps[(house_index + 1) % 12]) - start) % 360
        longitude = longitude_float((start + within * arc) % 360)
        point = longitude_to_point_dict("AgePoint", longitude)
        aspect_to = next(
            (body for exact_age, body, _ in contacts if round(exact_age) == age),
            None,
        )
        points.append(
            {
                "age": age,
                "longitude": point["absolute_degree"],
                "sign": point["sign"],
                "sign_label": point["sign_label"],
                "signlon": point["degree"],
                "house": house_index + 1,
                "aspect_to": aspect_to,
                "aspect_to_label": planet_label(aspect_to) if aspect_to else None,
            }
        )

    return {
        "system": "age_point",
        "system_label": "年龄推进点",
        "years_per_house": AGE_POINT_YEARS_PER_HOUSE,
        "cycle_years": AGE_POINT_CYCLE_YEARS,
        "max_age_years": max_age_years,
        "contacts": [
            {
                "age": round(float(age), 2),
                "body": body,
                "body_label": planet_label(body),
                "longitude": longitude,
            }
            for age, body, longitude in contacts
        ],
        "points": points,
        "point_count": len(points),
    }


# 12. 恒星推运 (Vedic sidereal secondary progression).


def build_vedic_progression_payload(
    progressed_longitudes: dict[str, float],
    natal_longitudes: dict[str, float],
    *,
    orb: float = 1.5,
    max_hits: int | None = None,
) -> dict[str, Any]:
    """
    恒星推运 / Vedic sidereal secondary progression.

    The same "a day for a year" secondary progression as the tropical version, but
    read in the sidereal zodiac (the caller casts both subjects Sidereal, so the
    longitudes arrive already ayanamsa-corrected). We report the directed positions
    and the aspects the progressed points make back to the natal chart.

    星阙/horosa computes this on a closed backend with no fixture, so this is verified
    by progression invariants (the progressed–natal arc equals the secondary motion
    of each body) rather than byte-parity.
    """
    positions = {
        name.lower(): longitude_to_point_dict(name, degree)
        for name, degree in progressed_longitudes.items()
    }
    hits = collect_aspect_hits(
        source_longitudes=progressed_longitudes,
        target_longitudes=natal_longitudes,
        orb_limit=orb,
    )
    hits_total_count = len(hits)
    selected_hits = hits[:max_hits] if max_hits is not None else hits
    return {
        "system": "vedic_progression",
        "system_label": "恒星推运",
        "zodiac": "sidereal",
        "orb": orb,
        "positions": positions,
        "hits": selected_hits,
        "hits_total_count": hits_total_count,
    }


# 13. 赤纬推运 (Jayne declination progression).


def build_jaynes_declination_payload(
    progressed_declinations: dict[str, float],
    natal_declinations: dict[str, float],
    *,
    orb: float = 1.0,
) -> dict[str, Any]:
    """
    赤纬推运 / Charles Jayne declination progression.

    Compare one secondary-progressed declination with each natal declination.
    Opposite nonzero signs use the distance to the reflected declination.
    Same signs and equatorial zero use the direct distance. Compare and sort
    with exact differences of the supplied coordinates before formatting.
    """
    orb_limit = Fraction(orb)
    natal_working = {body: Fraction(decl) for body, decl in natal_declinations.items()}
    parallels: list[dict[str, Any]] = []
    for prog_body, prog_decl in progressed_declinations.items():
        prog_working = Fraction(prog_decl)
        for natal_body, natal_work in natal_working.items():
            if prog_working < 0 < natal_work or natal_work < 0 < prog_working:
                kind, hit_orb = "contraparallel", abs(prog_working + natal_work)
            else:
                kind, hit_orb = "parallel", abs(prog_working - natal_work)
            if hit_orb > orb_limit:
                continue
            parallels.append(
                {
                    "progressed": prog_body,
                    "progressed_label": planet_label(prog_body),
                    "natal": natal_body,
                    "natal_label": planet_label(natal_body),
                    "kind": kind,
                    "kind_label": "平行" if kind == "parallel" else "反平行",
                    "progressed_declination": round(prog_decl, 4),
                    "natal_declination": round(natal_declinations[natal_body], 4),
                    "orb": hit_orb,
                }
            )
    parallels.sort(key=lambda item: item["orb"])
    for parallel in parallels:
        parallel["orb"] = round(float(parallel["orb"]), 4)
    return {
        "system": "jaynes_declination",
        "system_label": "赤纬推运",
        "orb": orb,
        "parallels": parallels,
    }


__all__ = [
    "build_harmonic_payload",
    "build_planetary_ages_payload",
    "build_triplicity_rulers_payload",
    "build_lunation_phase_payload",
    "build_distributions_payload",
    "build_balbillus_payload",
    "build_keypoints_payload",
    "build_yearsystem129_payload",
    "build_planetary_arc_payload",
    "build_persian_directed_payload",
    "build_age_point_payload",
    "build_vedic_progression_payload",
    "build_jaynes_declination_payload",
    "AGE_POINT_YEARS_PER_HOUSE",
    "AGE_POINT_CYCLE_YEARS",
    "PERSIAN_MOVERS",
    "PERSIAN_ASPECTS",
    "PERSIAN_RATE_DEG_PER_YEAR",
    "PERSIAN_TROPICAL_YEAR_DAYS",
    "PTOLEMY_SEVEN_AGES",
    "DOROTHEAN_TRIPLICITY_RULERS",
    "LUNAR_PHASES",
    "DISTRIBUTION_TIME_KEY_RATES",
    "BALBILLUS_SMALL_YEARS",
    "BALBILLUS_EXALTATION",
    "KEYPOINTS_PERIOD_NUMBERS",
]
