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
from fatebridge.core.astro.solar_events import (
    SOLAR_EVENT_MODEL,
    solar_crossings_in_window,
)
from fatebridge.core.astro.solar_observer import (
    SOLAR_SOURCE_POLICY,
    NativeSolarSource,
    select_solar_source,
    solar_source_reference,
)
from fatebridge.core.astro.time_scales import tt_from_ut1
from fatebridge.core.jyotish.jyotish_balas import (
    PLANETS,
    DirectionalResolution,
    directed_angle,
    moon_nature_readings,
    strength_branch_display,
    strength_branch_summary,
)
from fatebridge.core.jyotish.jyotish_mean import model_balas
from fatebridge.core.jyotish.jyotish_sthana import SthanaResolution
from fatebridge.core.jyotish.jyotish_strength import SOURCE_ID
from fatebridge.core.jyotish.jyotish_war import war_bala_result

WEEK = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
HORA_ORDER = ("Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars")
STAR_PLANETS = ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")


def solar_packet(
    jd_ut1: float, longitude: float, latitude: float, policy: str
) -> dict[str, Any]:
    """Keep all crossings in each supporting day, without post-event cursors."""
    start = math.floor(jd_ut1 - 0.5) + 0.5 - 3
    end = start + 8
    events: dict[tuple[str, float], dict[str, Any]] = {}
    no_events = []
    with runtime.preserve_ephemeris_path():
        source = select_solar_source(
            tt_from_ut1(start),
            tt_from_ut1(end),
            require_data_files=policy == "require_data_files",
        )
        for day in range(8):
            day_start = start + day
            day_end = day_start + 1
            solved = solar_crossings_in_window(
                day_start,
                day_end,
                longitude=longitude,
                latitude=latitude,
                definition="hindu_geometric_center",
                source=source,
                ephemeris_policy=(
                    "require_data_files" if policy == "require_data_files" else "auto"
                ),
            )
            daily_events = [event for event in solved if event.julian_day_ut1 < day_end]
            for event in daily_events:
                kind = "rise" if event.rising else "set"
                events[(kind, event.julian_day_ut1)] = {
                    "kind": kind,
                    "julian_day_ut1": event.julian_day_ut1,
                    "julian_day_tt": event.julian_day_tt,
                    "ephemeris_model": event.ephemeris_model,
                }
            for kind in ("rise", "set"):
                if not any(event.rising == (kind == "rise") for event in daily_events):
                    no_events.append({"search_jd_ut1": day_start, "kind": kind})
    rows = sorted(events.values(), key=lambda item: item["julian_day_ut1"])
    models = {row["ephemeris_model"] for row in rows}
    if not models:
        models.add(
            source.value
            if not isinstance(source, NativeSolarSource)
            else runtime.ephemeris_model_from_retflag(source.requested_flags)
        )
    return {
        "events": rows,
        "ephemeris_policy": policy,
        "ephemeris_models": sorted(models),
        "ephemeris_sources": {
            model: solar_source_reference(model, str(runtime.swe.version))
            for model in sorted(models)
        },
        "ephemeris_source_policy": SOLAR_SOURCE_POLICY,
        "no_event_searches": no_events,
        "search_start_jd_ut1": start,
        "search_end_jd_ut1": end,
        "enumeration": {
            "method": "all_directed_crossings_in_half_open_daily_windows",
            "partition_hours": 24,
            "scope": "Complete resolved crossing sequence per declared daily window; no fixed same-kind cursor or timestamp shift. Not observational precision or a continuous proof of arbitrarily small tangent arcs.",
        },
        "definition": "Swiss BIT_HINDU_RISING: geocentric solar centre, no refraction, solar ecliptic latitude ignored, zero horizon altitude",
        "event_model": SOLAR_EVENT_MODEL,
        "equatorial_frame": "selected_physical_equator_and_equinox_of_date",
        "search_window_hours": 192,
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
            local_day = mean_date(jd_ut1, longitude)
            before_sunrise = (
                not is_day and local_day == mean_date(arc_end, longitude)
                if local_day is not None
                else None
            )
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
                    "before_local_sunrise": before_sunrise,
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


def _nathonnatha_values(meridian: float, sun_ra: float) -> dict[str, Fraction]:
    """Keep the source values available for both display and chained strength."""
    arc = directed_angle(sun_ra, meridian)
    night = min(arc, 360 - arc) / 3
    return {
        p: (
            Fraction(60)
            if p == "Mercury"
            else 60 - night if p in {"Sun", "Jupiter", "Venus"} else night
        )
        for p in PLANETS
    }


def nathonnatha(meridian: float, sun_ra: float) -> dict[str, float]:
    """Render both source formulas without using one display to derive another."""
    return {
        p: float(value) for p, value in _nathonnatha_values(meridian, sun_ra).items()
    }


def _ayana_values(declinations: dict[str, float]) -> dict[str, Fraction]:
    limit = Fraction(469, 20)  # fixed23deg27min in selected commentary
    result = {}
    for p in PLANETS:
        dec = Fraction(declinations[p])
        signed = (
            abs(dec) if p == "Mercury" else -dec if p in {"Moon", "Saturn"} else dec
        )
        result[p] = (limit + signed) * 30 / limit * (2 if p == "Sun" else 1)
    return result


def ayana_values(declinations: dict[str, float]) -> dict[str, float]:
    return {p: float(value) for p, value in _ayana_values(declinations).items()}


def paksha_scenarios(longitudes: dict[str, float]) -> dict[str, Any]:
    return _paksha_results(longitudes)[0]


def _paksha_results(
    longitudes: dict[str, float],
) -> tuple[dict[str, Any], dict[str, dict[str, Fraction]]]:
    elongation = directed_angle(longitudes["Sun"], longitudes["Moon"])
    benefic = min(elongation, 360 - elongation) / 3
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
    result = {
        "summary": strength_branch_summary(scenarios),
        "scenarios": strength_branch_display(scenarios),
        "benefic_value": float(benefic),
        "malefic_value": float(60 - benefic),
        "moon_readings": options,
        "scope": "Santhanam27.10-11 grouping and doubled Moon; conflicting nature readings retained, not a physical illumination percentage",
    }
    return result, scenarios


def temporal_balas(
    raw: dict[str, Any],
    packet: dict[str, Any],
    longitude: float,
    *,
    sthana: SthanaResolution | dict[str, Any] | None = None,
    dig: DirectionalResolution | dict[str, Any] | None = None,
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
    natha = _nathonnatha_values(
        raw["local_apparent_sidereal_meridian"],
        raw["equatorial"]["Sun"]["right_ascension"],
    )
    declinations = {p: raw["equatorial"][p]["declination"] for p in PLANETS}
    ayana = _ayana_values(declinations)
    paksha, exact_paksha = _paksha_results(raw["longitudes"])
    tribhaga = one_lord(parts["tribhaga_lord"], 60)
    tribhaga["Jupiter"] = 60.0
    components: dict[str, Any] = {
        "nathonnatha_bala": {
            "summary": natha,
            "rule": "27.8-9 apparent solar meridian, not civil clock",
        },
        "paksha_bala": paksha,
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
    components["yuddha_bala"], exact_war = war_bala_result(
        raw["longitudes"], components, exact_paksha, sthana, dig
    )
    scenarios: dict[str, dict[str, Fraction | None]] = {}
    for name, lunar in exact_paksha.items():
        values: dict[str, Fraction | None] = {}
        for p in PLANETS:
            inputs = [
                (
                    lunar[p]
                    if key == "paksha_bala"
                    else (
                        exact_war[name][p]
                        if key == "yuddha_bala"
                        else part["summary"][p]
                    )
                )
                for key, part in components.items()
            ]
            values[p] = (
                None
                if None in inputs
                else sum((Fraction(v) for v in inputs if v is not None), Fraction())
            )
        scenarios[name] = values
    summary = strength_branch_summary(scenarios)
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
        for name, lunar in exact_paksha.items()
    }
    motion_summary = strength_branch_summary(lunar_motion)
    # These are display boundaries. War, Kala totals and luminary motion above
    # consume the source values, never these separately rounded leaf labels.
    components["nathonnatha_bala"]["summary"] = {
        p: float(value) for p, value in natha.items()
    }
    components["ayana_bala"]["summary"] = {
        p: float(value) for p, value in ayana.items()
    }
    return {
        "kala_bala": {
            "temporal_scope": "natal birth instant; not analysis_year/as_of transits or future-year rulership",
            "status": "partial_components" if missing else "conditional_nature_results",
            "method": "santhanam_27_8_17_declared_commentary",
            "unit": "virupa",
            "arithmetic_policy": "unrounded_temporal_source_values_v1",
            "source_id": SOURCE_ID,
            "source_section": "27.8-17 printed268-283; conditional war formula separately Raman76-77",
            "summary": summary,
            "conditional_targets": [
                p
                for p in PLANETS
                if summary[p] is None
                and all(row[p] is not None for row in scenarios.values())
            ],
            "components": components,
            "scenarios": strength_branch_display(scenarios),
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
                "jyotish.solar_event_enumeration.v2",
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
            "summary": motion_summary,
            "conditional_targets": [
                p
                for p in PLANETS
                if motion_summary[p] is None
                and all(row[p] is not None for row in lunar_motion.values())
            ],
            "scenarios": strength_branch_display(lunar_motion),
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
