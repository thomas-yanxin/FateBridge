"""Temporal components with physical solar days and declared textual readings.

War amounts preserve their declared source and conditional inputs. Optional
mean positions are handled separately; missing values are never fabricated.
"""

from __future__ import annotations

import math
from datetime import date
from fractions import Fraction
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.jyotish_balas import PLANETS, directed_angle, moon_nature_readings
from fatebridge.core.jyotish_mean import model_balas
from fatebridge.core.jyotish_strength import SOURCE_ID
from fatebridge.core.jyotish_war import war_bala

WEEK = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
HORA_ORDER = ("Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars")
STAR_PLANETS = ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")
SOLAR_EVENT_ADVANCE_DAYS = 1 / 86400


def solar_packet(
    jd_ut1: float, longitude: float, latitude: float, policy: str
) -> dict[str, Any]:
    """Enumerate the supporting window, including two events in one UT1 day.

    The solver returns the next event, not every event on a calendar date.
    After each event advance the search by one second to avoid returning the
    same numerical root. This changes the search cursor, never the event time.
    Daily seeds remain necessary after a polar no-event result.
    """
    start = math.floor(jd_ut1 - 0.5) + 0.5 - 3
    end = start + 8
    events: dict[tuple[str, float], dict[str, Any]] = {}
    resume: dict[str, float] = {}
    no_events = []
    swe = runtime.swe
    with runtime.preserve_ephemeris_path():
        swe.set_ephe_path(configured_ephemeris_path() or "")
        for day in range(8):
            for kind, flag in (("rise", swe.CALC_RISE), ("set", swe.CALC_SET)):
                cursor = max(start + day, resume.get(kind, start))
                day_end = start + day + 1
                for _ in range(32):
                    result, times = runtime.ephemeris_call(
                        "rise_trans",
                        cursor,
                        swe.SUN,
                        flag | swe.BIT_HINDU_RISING,
                        (longitude, latitude, 0.0),
                        0.0,
                        0.0,
                        swe.FLG_SWIEPH,
                    )
                    if result == -2:
                        no_events.append({"search_jd_ut1": cursor, "kind": kind})
                        break
                    if result != 0 or not math.isfinite(times[0]):
                        raise ValueError(
                            "Swiss Ephemeris could not compute the supporting solar event"
                        )
                    event = float(times[0])
                    if event < cursor:
                        raise ValueError(
                            "Supporting solar event search did not advance"
                        )
                    if event >= day_end:
                        break
                    _, retflag = runtime.ephemeris_call(
                        "calc_ut", event, swe.SUN, swe.FLG_SWIEPH
                    )
                    if retflag < 0:
                        raise ValueError(
                            "Swiss Ephemeris could not validate the supporting Sun ephemeris"
                        )
                    model = runtime.ephemeris_model_from_retflag(retflag)
                    if policy == "require_data_files" and model not in {
                        "swieph",
                        "jpl",
                    }:
                        raise ValueError(
                            "require_data_files rejects Sun analytical fallback at supporting rise/set events"
                        )
                    events[(kind, event)] = {
                        "kind": kind,
                        "julian_day_ut1": event,
                        "ephemeris_model": model,
                    }
                    cursor = event + SOLAR_EVENT_ADVANCE_DAYS
                    resume[kind] = cursor
                    if cursor >= day_end:
                        break
                else:
                    raise ValueError(
                        "Supporting solar event enumeration limit exceeded"
                    )
    rows = sorted(events.values(), key=lambda item: item["julian_day_ut1"])
    return {
        "events": rows,
        "ephemeris_policy": policy,
        "ephemeris_models": sorted({row["ephemeris_model"] for row in rows}),
        "fallback_event_count": sum(
            row["ephemeris_model"] not in {"swieph", "jpl"} for row in rows
        ),
        "no_event_searches": no_events,
        "search_start_jd_ut1": start,
        "search_end_jd_ut1": end,
        "enumeration": {
            "method": "daily_seeds_then_all_successive_events_before_each_day_end",
            "post_event_search_advance_seconds": 1.0,
            "scope": "One-second anti-repeat search cursor for same-kind solar events; returned event timestamps are unshifted. Not observational precision or a continuous proof for arbitrary bodies.",
        },
        "definition": "Swiss BIT_HINDU_RISING: geocentric solar centre, no refraction, solar ecliptic latitude ignored, zero horizon altitude",
        "scope": "UT1 event coordinates, not UTC timestamps; finite supporting window, no invented polar sunrise",
    }


def mean_date(jd_ut1: float, longitude: float) -> date | None:
    """Classify given binary inputs without rounding across local midnight.

    Gregorian ordinal1 starts at JD1721425.5. This preserves the inherited
    UT1/longitude precision; it does not establish observational clock accuracy.
    """
    ordinal = (
        math.floor(Fraction(jd_ut1) + Fraction(longitude) / 360 + Fraction(1, 2))
        - 1_721_425
    )
    return date.fromordinal(ordinal) if 1 <= ordinal <= date.max.toordinal() else None


def ahargana_lords(day: date) -> dict[str, Any]:
    count = 714_404_108_573 + (day - date(1860, 1, 1)).days
    # Source numbers weekdays from1=Sunday; remainder0 is Saturday.
    year_index = ((count // 360 * 3 + 1) % 7 - 1) % 7
    month_index = ((count // 30 * 2 + 1) % 7 - 1) % 7
    return {
        "ahargana": count,
        "local_mean_date": day.isoformat(),
        "year_lord": WEEK[year_index],
        "month_lord": WEEK[month_index],
        "civil_weekday_lord": WEEK[(day.weekday() + 1) % 7],
        "year_days": 360,
        "month_days": 30,
        "scope": "traditional reference day index; not a cosmological-age or creation-date claim",
    }


def one_lord(lord: str | None, value: float) -> dict[str, float | None]:
    return {p: None if lord is None else value if p == lord else 0.0 for p in PLANETS}


def solar_parts(
    jd_ut1: float, longitude: float, packet: dict[str, Any]
) -> dict[str, Any]:
    events = packet["events"]
    rises = [row["julian_day_ut1"] for row in events if row["kind"] == "rise"]
    before_rise = [t for t in rises if t <= jd_ut1]
    after_rise = [t for t in rises if t > jd_ut1]
    result: dict[str, Any] = {
        "status": "solar_day_not_bracketed",
        "day_lord": None,
        "hora_lord": None,
        "tribhaga_lord": None,
        "sunrise_day_status": "not_bracketed",
        "active_arc_status": "not_bracketed",
        "dependency_scope": "Dina/Hora need consecutive sunrises enclosing the instant; Tribhaga needs only adjacent opposite events enclosing the active day/night arc. Neither depends on unrelated previous/next sunsets.",
        "boundary_convention": "half-open intervals; actual next sunrise resets weekday/hora. No clamping a possible25th mean hour into24.",
    }
    sunrise_day = bool(before_rise and after_rise)
    if sunrise_day:
        rise, next_rise = max(before_rise), min(after_rise)
        day = mean_date(rise, longitude)
        day_lord = WEEK[(day.weekday() + 1) % 7] if day else None
        # Equal *mean-clock* hours; no unequal Western planetary-hour reuse.
        elapsed_hours = (Fraction(jd_ut1) - Fraction(rise)) * 24
        hora = int(elapsed_hours // 1) + 1
        hora_lord = (
            HORA_ORDER[(HORA_ORDER.index(day_lord) + hora - 1) % 7]
            if day_lord and 1 <= hora <= 24
            else None
        )
        result.update(
            {
                "sunrise_day_status": "bracketed",
                "opening_sunrise_jd_ut1": rise,
                "next_sunrise_jd_ut1": next_rise,
                "opening_local_mean_date": day.isoformat() if day else None,
                "day_lord": day_lord,
                "hora_number": hora,
                "hora_lord": hora_lord,
                "hora_status": (
                    "computed_equal_mean_hour"
                    if hora_lord
                    else "outside_24_hora_table_or_calendar_range"
                ),
            }
        )

    before = [row for row in events if row["julian_day_ut1"] <= jd_ut1]
    after = [row for row in events if row["julian_day_ut1"] > jd_ut1]
    active_arc = False
    if before and after:
        arc_start = max(row["julian_day_ut1"] for row in before)
        arc_end = min(row["julian_day_ut1"] for row in after)
        left = {row["kind"] for row in before if row["julian_day_ut1"] == arc_start}
        right = {row["kind"] for row in after if row["julian_day_ut1"] == arc_end}
        if len(left) != 1 or len(right) != 1:
            result["active_arc_status"] = "ambiguous_coincident_events"
        elif left == right or left | right != {"rise", "set"}:
            result["active_arc_status"] = "inconsistent_event_sequence"
        else:
            active_arc = True
            is_day = left == {"rise"}
            start, end, instant = (
                Fraction(arc_start),
                Fraction(arc_end),
                Fraction(jd_ut1),
            )
            third = int(3 * (instant - start) // (end - start))
            result.update(
                {
                    "active_arc_status": "bracketed",
                    "is_day": is_day,
                    "arc_start_jd_ut1": arc_start,
                    "arc_end_jd_ut1": arc_end,
                    "third_number": third + 1,
                    "tribhaga_lord": (
                        ("Mercury", "Sun", "Saturn")
                        if is_day
                        else ("Moon", "Venus", "Mars")
                    )[third],
                }
            )
    result["status"] = (
        "bracketed"
        if sunrise_day and active_arc
        else (
            "partial_solar_brackets"
            if sunrise_day or active_arc
            else "solar_day_not_bracketed"
        )
    )
    if result["status"] != "bracketed":
        result["limitation"] = (
            "Only the unbracketed component remains unavailable; no missing event is invented. Supporting window is finite and polar/transition cases can remain partial."
        )
    return result


def nathonnatha(meridian: float, sun_ra: float) -> dict[str, float]:
    arc = directed_angle(sun_ra, meridian)
    day_value = float(60 - min(arc, 360 - arc) / 3)
    return {
        p: (
            60.0
            if p == "Mercury"
            else day_value if p in {"Sun", "Jupiter", "Venus"} else 60 - day_value
        )
        for p in PLANETS
    }


def ayana_values(declinations: dict[str, float]) -> dict[str, float]:
    limit = Fraction(469, 20)  # fixed23deg27min in selected commentary
    result = {}
    for p in PLANETS:
        dec = Fraction(declinations[p])
        signed = (
            abs(dec) if p == "Mercury" else -dec if p in {"Moon", "Saturn"} else dec
        )
        result[p] = float((limit + signed) * 30 / limit * (2 if p == "Sun" else 1))
    return result


def paksha_scenarios(longitudes: dict[str, float]) -> dict[str, Any]:
    elongation = directed_angle(longitudes["Sun"], longitudes["Moon"])
    benefic = float(min(elongation, 360 - elongation) / 3)
    options = moon_nature_readings(elongation)
    scenarios = {}
    for moon in options["options"]:
        for mercury in ("benefic", "malefic"):
            values = {
                p: benefic if p in {"Jupiter", "Venus"} else 60 - benefic
                for p in PLANETS
            }
            values["Mercury"] = benefic if mercury == "benefic" else 60 - benefic
            values["Moon"] = 2 * (benefic if moon == "benefic" else 60 - benefic)
            scenarios[f"moon_{moon}__mercury_{mercury}"] = values
    return {
        "scenarios": scenarios,
        "benefic_value": benefic,
        "malefic_value": 60 - benefic,
        "moon_readings": options,
        "scope": "Santhanam27.10-11 grouping and doubled Moon; conflicting nature readings retained, not a physical illumination percentage",
    }


def consensus(scenarios: dict[str, dict[str, Any]]) -> dict[str, float | None]:
    result = {}
    for p in PLANETS:
        values = {branch[p] for branch in scenarios.values()}
        result[p] = next(iter(values)) if len(values) == 1 else None
    return result


def temporal_balas(
    raw: dict[str, Any],
    packet: dict[str, Any],
    longitude: float,
    *,
    sthana: dict[str, Any] | None = None,
    dig: dict[str, Any] | None = None,
) -> dict[str, Any]:
    jd = raw["julian_day_ut"]
    day = mean_date(jd, longitude)
    calendar = (
        ahargana_lords(day)
        if day
        else {
            "year_lord": None,
            "month_lord": None,
            "status": "local_mean_date_outside_datetime_range",
        }
    )
    parts = solar_parts(jd, longitude, packet)
    natha = nathonnatha(
        raw["local_apparent_sidereal_meridian"],
        raw["equatorial"]["Sun"]["right_ascension"],
    )
    declinations = {p: raw["equatorial"][p]["declination"] for p in PLANETS}
    ayana = ayana_values(declinations)
    paksha = paksha_scenarios(raw["longitudes"])
    tribhaga = one_lord(parts["tribhaga_lord"], 60)
    tribhaga["Jupiter"] = 60.0
    components: dict[str, Any] = {
        "nathonnatha_bala": {
            "summary": natha,
            "rule": "27.8-9 apparent solar meridian, not civil clock",
        },
        "paksha_bala": {"summary": consensus(paksha["scenarios"]), **paksha},
        "tribhaga_bala": {
            "summary": tribhaga,
            "ruler": parts["tribhaga_lord"],
            "rule": "27.12 separate day/night thirds; Jupiter60 always",
        },
        "abda_bala": {
            "summary": one_lord(calendar["year_lord"], 15),
            "ruler": calendar["year_lord"],
        },
        "masa_bala": {
            "summary": one_lord(calendar["month_lord"], 30),
            "ruler": calendar["month_lord"],
        },
        "dina_bala": {
            "summary": one_lord(parts["day_lord"], 45),
            "ruler": parts["day_lord"],
        },
        "hora_bala": {
            "summary": one_lord(parts["hora_lord"], 60),
            "ruler": parts["hora_lord"],
        },
        "ayana_bala": {
            "summary": ayana,
            "declinations": declinations,
            "fixed_limit_degrees": 23.45,
            "rule": "27.15-17 commentary actual equatorial declination; Sun doubled, Mercury absolute; no invented cap",
            "outside_nominal_range": [
                p for p, v in ayana.items() if not 0 <= v <= (120 if p == "Sun" else 60)
            ],
        },
    }
    components["yuddha_bala"] = war_bala(
        raw["longitudes"], components, paksha["scenarios"], sthana, dig
    )
    scenarios: dict[str, dict[str, Any]] = {}
    for name, lunar in paksha["scenarios"].items():
        values = {}
        for p in PLANETS:
            inputs = [
                (
                    lunar[p]
                    if key == "paksha_bala"
                    else (
                        part["scenarios"][name][p]
                        if key == "yuddha_bala"
                        else part["summary"][p]
                    )
                )
                for key, part in components.items()
            ]
            values[p] = None if any(v is None for v in inputs) else sum(inputs)
        scenarios[name] = values
    summary = consensus(scenarios)
    missing = [
        name
        for name, part in components.items()
        if name != "paksha_bala"
        and any(
            value is None
            for row in (
                part["scenarios"].values()
                if name == "yuddha_bala"
                else [part["summary"]]
            )
            for value in row.values()
        )
    ]
    motion_model = model_balas(raw)
    lunar_motion = {
        name: {
            p: (
                ayana["Sun"]
                if p == "Sun"
                else lunar["Moon"] if p == "Moon" else motion_model["summary"][p]
            )
            for p in PLANETS
        }
        for name, lunar in paksha["scenarios"].items()
    }
    return {
        "kala_bala": {
            "temporal_scope": "natal birth instant; not analysis_year/as_of transits or future-year rulership",
            "status": "partial_components" if missing else "conditional_nature_results",
            "method": "santhanam_27_8_17_declared_commentary",
            "unit": "virupa",
            "source_id": SOURCE_ID,
            "source_section": "27.8-17 printed268-283; conditional war formula separately Raman76-77",
            "summary": summary,
            "components": components,
            "scenarios": scenarios,
            "missing_components": missing,
            "calendar_context": {
                **calendar,
                "date_basis": "geographic local mean Gregorian birth date for year/month; sunrise opening date only for Dina/Hora. Independent of arbitrary civil-zone labels.",
            },
            "solar_context": parts,
            "solar_events": packet,
            "source_disagreements": [
                "Fixed23deg27min commentary is not the verse Khandas approximation or a24deg Raman coefficient.",
                "Mean60-minute Hora can produce a25th index before late next sunrise; that part remains unadjudicated.",
                "Moon central-bright-window and waxing/waning classifications are not identical; both author readings retained.",
            ],
            "rule_ids": [
                "jyotish.kala_components.v1",
                "jyotish.solar_component_dependencies.v1",
                "jyotish.solar_event_enumeration.v1",
                "jyotish.yuddha_raman_76_77.v1",
            ],
            "interpretation_scope": "Traditional temporal components under declared readings, not empirical probability. Partial/conditional values cannot certify complete Shadbala or full classical acceptance.",
        },
        "cheshta_bala": {
            "temporal_scope": "natal birth instant only",
            "status": (
                "computed_declared_mean_model_with_conditional_luminaries"
                if motion_model["model_context"]["status"]
                == "computed_declared_secular_model"
                else "partial_luminaries_only"
            ),
            "method": "santhanam_luminaries_and_explicit_mean_model",
            "unit": "virupa",
            "source_id": SOURCE_ID,
            "source_section": "27.18 printed284 luminaries;27.24-25 printed285 angular formula; five-star mean model declared separately",
            "summary": consensus(lunar_motion),
            "scenarios": lunar_motion,
            "model_context": motion_model["model_context"],
            "missing_planets": [
                p for p in STAR_PLANETS if motion_model["summary"][p] is None
            ],
            "rule_ids": [
                "jyotish.luminary_cheshta.v1",
                *(
                    ["jyotish.cheshta_simon1994.v1"]
                    if raw.get("cheshta_model") == "simon1994_j2000"
                    else []
                ),
            ],
            "interpretation_scope": "Sun=selected Ayana, Moon=selected Paksha. Five-star values require an explicit admitted mean model; read model_context. The modern secular model is not Raman1900 table acceptance, complete Shadbala or prediction evidence; no speed-label or trueSun substitution.",
        },
    }
