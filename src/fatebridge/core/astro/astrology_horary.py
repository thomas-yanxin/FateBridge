"""
FateBridge 卜卦 (horary) evidence calculation.

The chart belongs to the question's recorded instant. Native TT motion supplies
lunar sign-exit events and finite seven-planet histories. Instantaneous geometry,
event-epoch reception and named source conditions retain their respective
verification states under the selected Lilly 1647 method.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from fractions import Fraction
from functools import partial
from typing import Any

from fatebridge.core.astro.astrology_events import (
    FileContext,
    build_ephemeris_source_identity,
)
from fatebridge.core.astro.astrology_tables import CHALDEAN_ORDER, RULER_BY_SIGN, SIGNS
from fatebridge.core.astro.event_reference import (
    reference_qualification,
    unresolved_ascendant,
    unresolved_houses,
)
from fatebridge.core.astro.geometry import angular_separation_fraction, normalize_angle
from fatebridge.core.astro.horary_conditions import evaluate_lilly_conditions
from fatebridge.core.astro.horary_events import native_planetary_events
from fatebridge.core.astro.horary_motion import (
    first_lunar_contact,
    native_lunar_contacts,
)
from fatebridge.core.astro.lilly import dignity_at
from fatebridge.core.astro.lilly_fortitude_inputs import collect_fortitude_inputs
from fatebridge.core.astro.lilly_fortitudes import evaluate_fortitudes
from fatebridge.core.astro.lilly_fortune import evaluate_fortune
from fatebridge.core.astro.lilly_house_assignment import (
    assign_from_cusps,
    subject_cusps,
)
from fatebridge.core.astro.lilly_houses import house_condition
from fatebridge.core.astro.lilly_orbs import (
    DEFAULT_ORB_PROFILE,
    orb_receipt,
    pair_radius,
)
from fatebridge.core.astro.lilly_radicality import evaluate_radicality
from fatebridge.core.astro.lilly_radicality_inputs import collect_radicality_hour
from fatebridge.core.astro.lilly_rays import METHOD_ID as LILLY_SIGN_RAYS_METHOD
from fatebridge.core.astro.lilly_rays import directed_sign_relationship
from fatebridge.core.astro.western_points import (
    house_number,
    normalize_sign_name,
    planet_label,
    point_absolute_position,
    sign_label,
)
from fatebridge.core.classical_western import _aspect_phase, build_almuten_figuris

# The seven traditional planets in Chaldean order.
TRADITIONAL_PLANETS = list(CHALDEAN_ORDER)

# Ptolemaic aspects only — horary does not judge by minor aspects.
PTOLEMAIC_ASPECTS: list[tuple[str, str, float]] = [
    ("conjunction", "合", 0.0),
    ("sextile", "六合", 60.0),
    ("square", "刑", 90.0),
    ("trine", "拱", 120.0),
    ("opposition", "冲", 180.0),
]

# Question topic → quesited house (whole derived-house logic kept simple: the
# turned house is not modelled; the radical house of the matter is used).
HOUSE_BY_CATEGORY: dict[str, int] = {
    "general": 1,
    "wealth": 2,
    "family": 3,
    "property": 4,
    "marriage": 7,
    "lawsuit": 7,
    "theft": 7,
    "travel": 9,
    "career": 10,
    "hope": 11,
    "enemy": 12,
}
CATEGORY_LABELS_ZH: dict[str, str] = {
    "general": "综合",
    "wealth": "财物",
    "family": "兄弟/亲属",
    "property": "房产/田宅",
    "marriage": "婚姻/感情",
    "lawsuit": "官非/对手",
    "theft": "失物/盗贼",
    "travel": "旅行",
    "career": "事业/职位",
    "hope": "愿望",
    "enemy": "私敌",
}

HOUSE_ATTRIBUTES = [
    "first_house",
    "second_house",
    "third_house",
    "fourth_house",
    "fifth_house",
    "sixth_house",
    "seventh_house",
    "eighth_house",
    "ninth_house",
    "tenth_house",
    "eleventh_house",
    "twelfth_house",
]

PLANET_ATTRIBUTES: dict[str, str] = {
    "Sun": "sun",
    "Moon": "moon",
    "Mercury": "mercury",
    "Venus": "venus",
    "Mars": "mars",
    "Jupiter": "jupiter",
    "Saturn": "saturn",
}


def _aspect_orb(
    planet_a: str, planet_b: str, orb_profile: str = DEFAULT_ORB_PROFILE
) -> float:
    return float(pair_radius(planet_a, planet_b, orb_profile))


def _planet_state(subject: Any, planet: str) -> dict[str, Any]:
    point = getattr(subject, PLANET_ATTRIBUTES[planet])
    longitude = normalize_angle(float(point.abs_pos))
    essential = dignity_at(planet, longitude, _chart_sect(subject))
    sign = essential["sign"]
    raw_speed = getattr(point, "speed", None)
    speed = None if raw_speed is None else float(raw_speed)
    if speed is not None and not math.isfinite(speed):
        raise ValueError("Horary longitude speed must be finite or unknown")
    occupied = house_number(getattr(point, "house", None))
    return {
        "occupied_house": occupied,
        "house_assignment": assign_from_cusps(
            longitude,
            subject_cusps(subject),
            native_occupied_house=occupied,
            house_system=getattr(subject, "houses_system_identifier", None),
            zodiac_type=getattr(subject, "zodiac_type", None),
        ),
        "house_condition": house_condition(
            occupied,
            getattr(subject, "houses_system_identifier", None),
            getattr(subject, "zodiac_type", None),
        ),
        "planet": planet,
        "planet_label": planet_label(planet),
        "sign": sign,
        "sign_label": sign_label(sign),
        "degree": longitude % 30.0,
        "absolute_degree": longitude,
        "longitude": longitude,
        "speed": speed,
        "retrograde": None if speed is None else speed < 0.0,
        "dignities": essential["dignities"],
        "essential_condition": essential,
    }


def _chart_sect(subject: Any) -> str | None:
    value = getattr(subject, "is_diurnal", None)
    return "day" if value is True else "night" if value is False else None


def _degree_aspect_candidate(
    state_a: dict[str, Any],
    state_b: dict[str, Any],
    *,
    orb_profile: str = DEFAULT_ORB_PROFILE,
) -> dict[str, Any] | None:
    """Select the existing unsigned degree/orb candidate, without phase calls."""
    lon_a, lon_b = state_a["longitude"], state_b["longitude"]
    orb_limit = _aspect_orb(state_a["planet"], state_b["planet"], orb_profile)
    separation = angular_separation_fraction(lon_a, lon_b)

    for key, label, angle in PTOLEMAIC_ASPECTS:
        orb = abs(separation - Fraction(angle))
        if orb > Fraction(orb_limit):
            continue
        return {
            "aspect": key,
            "aspect_label": label,
            "angle": angle,
            "orb": float(orb),
            "orb_limit": orb_limit,
            "orb_profile": orb_profile,
            "separation": float(separation),
        }
    return None


def _applying_aspect(
    state_a: dict[str, Any],
    state_b: dict[str, Any],
    *,
    orb_profile: str = DEFAULT_ORB_PROFILE,
) -> dict[str, Any] | None:
    """Existing within-orb candidate and instantaneous real-speed phase."""
    candidate = _degree_aspect_candidate(state_a, state_b, orb_profile=orb_profile)
    if candidate is None:
        return None
    phase = _aspect_phase(
        state_a["longitude"],
        state_a["speed"],
        state_b["longitude"],
        state_b["speed"],
        candidate["angle"],
    )
    return {
        **candidate,
        "applying": {"applying": True, "separating": False}.get(phase),
        "phase": phase,
    }


def _house_sign(subject: Any, house_number: int) -> str:
    cusp = getattr(subject, HOUSE_ATTRIBUTES[house_number - 1])
    return normalize_sign_name(getattr(cusp, "sign", ""))


def _moon_void_of_course(
    moon_state: dict[str, Any],
    other_states: list[dict[str, Any]],
    *,
    physical_motion: dict[str, Any] | None = None,
    orb_profile: str = DEFAULT_ORB_PROFILE,
) -> dict[str, Any]:
    """
    Report the declared strict-future longitude-contact query before ingress.

    Keep its physical events and current orb context separate from the source's
    unresolved application/orb variants. Missing motion remains unknown.
    """
    others = {state["planet"]: state for state in other_states}
    if physical_motion is None:
        physical_motion = {
            "status": "unavailable",
            "method_id": "native_tt_lunar_contacts_before_ingress_v1",
            "constant_velocity_projection": False,
            "void_of_course": None,
            "contacts": [],
            "unavailable_reason": "Native lunar-event evidence was not supplied",
        }
    for contact in physical_motion["contacts"]:
        contact["other_label"] = others[contact["other"]]["planet_label"]
        exact_orb = abs(
            angular_separation_fraction(
                moon_state["longitude"], others[contact["other"]]["longitude"]
            )
            - Fraction(contact["angle"])
        )
        contact["orb"] = float(exact_orb)
        contact["orb_limit"] = _aspect_orb("Moon", contact["other"], orb_profile)
        contact["orb_profile"] = orb_profile
        contact["inside_current_orb"] = exact_orb <= Fraction(contact["orb_limit"])
    first, ordered, _ = first_lunar_contact(physical_motion)
    return {
        "void_of_course": physical_motion["void_of_course"],
        "degrees_left_in_sign": physical_motion.get("degrees_left_in_sign"),
        "next_aspect": first if ordered else None,
        "motion_basis": physical_motion,
    }


def _extract_source_models(source: object) -> dict[str, str]:
    if not isinstance(source, Mapping):
        return {}
    by_factor = source.get("by_factor")
    if not isinstance(by_factor, Mapping):
        return {}
    models: dict[str, str] = {}
    for body, row in by_factor.items():
        if isinstance(row, Mapping) and row.get("model"):
            models[str(body)] = str(row["model"])
    return models


def _extract_file_contexts(source: object) -> FileContext:
    if not isinstance(source, Mapping):
        return ()
    files = source.get("files")
    if not isinstance(files, list | tuple):
        return ()
    contexts: list[tuple[str, float, float, int]] = []
    for row in files:
        if not isinstance(row, Mapping) or not row.get("filename"):
            continue
        start = row.get("start_julian_day_tt", row.get("start_julian_day_tdb", 0.0))
        end = row.get("end_julian_day_tt", row.get("end_julian_day_tdb", 0.0))
        contexts.append(
            (
                str(row["filename"]),
                float(start),
                float(end),
                int(row.get("de_number", 0)),
            )
        )
    return tuple(contexts)


def _horary_ephemeris_source_identity(
    subject: Any, event_history: Mapping[str, Any]
) -> dict[str, Any]:
    raw_basis = getattr(subject, "calculation_basis", None)
    basis: Mapping[str, Any] = raw_basis if isinstance(raw_basis, Mapping) else {}
    chart_source = basis.get("physical_ephemeris_source")
    event_source = event_history.get("physical_ephemeris_source")
    chart_models = _extract_source_models(chart_source)
    event_models = _extract_source_models(event_source)
    planetary_models = chart_models or event_models

    file_contexts = _extract_file_contexts(chart_source) or _extract_file_contexts(
        event_source
    )
    earth_rotation = basis.get("earth_rotation")
    earth_rotation_model: str | None = None
    if isinstance(earth_rotation, Mapping) and earth_rotation.get("method"):
        earth_rotation_model = str(earth_rotation["method"])
    elif basis.get("time_scale"):
        earth_rotation_model = str(basis["time_scale"])

    zodiac = getattr(subject, "zodiac_type", None)
    frame = (
        "sidereal_lahiri" if zodiac == "Sidereal" else "tropical_true_ecliptic_of_date"
    )
    engine_backend = (
        str(basis["engine_backend"])
        if basis.get("engine_backend")
        else ("swisseph_api" if event_models else "synthetic_subject")
    )
    event_summary: str | None = None
    if event_models:
        unique_event_models = set(event_models.values())
        event_summary = (
            next(iter(unique_event_models))
            if len(unique_event_models) == 1
            else "mixed"
        )
    elif event_history.get("status") == "unavailable":
        event_summary = "unavailable"

    consistent: bool | None = None
    if chart_models and event_models:
        consistent = {p: chart_models.get(p) for p in TRADITIONAL_PLANETS} == {
            p: event_models.get(p) for p in TRADITIONAL_PLANETS
        }

    return build_ephemeris_source_identity(
        planetary_models,
        planetary_time_scale="TT",
        angles_time_scale=(
            "UT1"
            if (
                basis.get("julian_day_ut1") is not None
                or earth_rotation_model
                or getattr(subject, "first_house", None) is not None
            )
            else None
        ),
        earth_rotation_model=earth_rotation_model,
        apparent_position_mode="geocentric_apparent",
        frame=frame,
        engine_backend=engine_backend,
        derived_points=["Ascendant", "Medium_Coeli", "Descendant", "Imum_Coeli"],
        file_contexts=file_contexts,
        event_search_backend=event_summary,
        consistent_with_chart_ephemeris=consistent,
    )


def _antiscia_contacts(
    states: dict[str, dict[str, Any]],
    asc_longitude: float | None = None,
    orb: float = 1.5,
) -> list[dict[str, Any]]:
    points: dict[str, float] = {
        name: float(state["longitude"]) for name, state in states.items()
    }
    if asc_longitude is not None:
        points["Ascendant"] = float(asc_longitude)
    names = list(points)
    hits: list[dict[str, Any]] = []
    for idx, body_a in enumerate(names):
        lon_a = points[body_a]
        antiscion_a = (180.0 - lon_a) % 360.0
        contra_a = (360.0 - lon_a) % 360.0
        for body_b in names[idx + 1 :]:
            lon_b = points[body_b]
            orb_anti = abs(math.remainder(antiscion_a - lon_b, 360.0))
            if orb_anti <= orb:
                hits.append(
                    {
                        "kind": "antiscia",
                        "body_a": body_a,
                        "body_b": body_b,
                        "orb": round(orb_anti, 4),
                    }
                )
            orb_contra = abs(math.remainder(contra_a - lon_b, 360.0))
            if orb_contra <= orb:
                hits.append(
                    {
                        "kind": "contra_antiscia",
                        "body_a": body_a,
                        "body_b": body_b,
                        "orb": round(orb_contra, 4),
                    }
                )
    return hits


def _direct_ingress_and_intervening_info(
    lilly_conditions: dict[str, Any],
) -> tuple[bool | None, int, bool]:
    """Inspect event_paths for direct contact sign-ingress order, intervening hits, and sequence verification."""
    event_paths = lilly_conditions.get("event_paths") or {}
    direct_path = next(
        (p for p in (event_paths.get("paths") or []) if p.get("mode") == "direct"),
        None,
    )
    if not isinstance(direct_path, dict):
        return None, 0, True
    future = direct_path.get("future_contact")
    transitions = direct_path.get("transitions") or []
    intervening = direct_path.get("intervening_contacts") or []
    seq_unverified = direct_path.get("sequence_conditions_satisfied") is not True
    if not isinstance(future, dict) or not future.get("root_bracket_tt"):
        return None, len(intervening), seq_unverified
    future_start = future["root_bracket_tt"][0]
    ingress_before = any(
        t.get("kind") == "ingress"
        and isinstance(t.get("root_bracket_tt"), list)
        and len(t["root_bracket_tt"]) >= 2
        and t["root_bracket_tt"][1] < future_start
        for t in transitions
        if isinstance(t, dict)
    )
    return (not ingress_before), len(intervening), seq_unverified


def _summarize_perfection(
    querent_planet: str,
    quesited_planet: str,
    lilly_conditions: dict[str, Any],
    moon_voc: dict[str, Any],
) -> dict[str, Any]:
    event_paths = lilly_conditions.get("event_paths") or {}
    paths = event_paths.get("paths") or []
    refranations = event_paths.get("refranation_patterns") or []
    prohibitions = event_paths.get("prohibition_patterns") or []
    frustrations = event_paths.get("frustration_patterns") or []

    obstructions: list[str] = []
    if prohibitions:
        obstructions.append("prohibition")
    if refranations:
        obstructions.append("refranation")
    if frustrations:
        obstructions.append("frustration")

    before_ingress, intervening_count, seq_unverified = (
        _direct_ingress_and_intervening_info(lilly_conditions)
    )

    event_path_summary: list[dict[str, Any]] = []
    for ep in event_paths.get("paths") or []:
        if not isinstance(ep, dict):
            continue
        fc = ep.get("future_contact")
        compact_fc = (
            {
                "bodies": fc.get("bodies"),
                "aspect": fc.get("aspect"),
                "julian_day_tt": fc.get("julian_day_tt"),
                "datetime_utc": fc.get("datetime_utc"),
            }
            if isinstance(fc, dict)
            else None
        )
        event_path_summary.append(
            {
                "mode": ep.get("mode"),
                "actors": ep.get("actors"),
                "status": ep.get("status"),
                "sequence_conditions_satisfied": ep.get(
                    "sequence_conditions_satisfied"
                ),
                "future_contact": compact_fc,
                "transitions_count": len(ep.get("transitions") or []),
                "intervening_contacts_count": len(ep.get("intervening_contacts") or []),
            }
        )

    active_routes: list[str] = []
    for row in paths:
        mode = row.get("mode")
        if mode == "direct":
            if row.get("future_contact") is not None and not obstructions:
                active_routes.append("direct")
        elif mode == "translation":
            conds = row.get("conditions") or []
            ok = all(c.get("passed") is not False for c in conds)
            if ok and row.get("future_contact") is not None:
                active_routes.append("translation")
        elif mode == "collection":
            conds = row.get("conditions") or []
            ok = all(c.get("passed") is not False for c in conds)
            if ok and row.get("collection_contacts"):
                active_routes.append("collection")

    base = {
        "before_ingress": before_ingress,
        "intervening_contacts_count": intervening_count,
        "sequence_conditions_unverified": seq_unverified,
        "principal_reception": lilly_conditions.get("principal_reception"),
        "event_path_summary": event_path_summary,
    }

    if obstructions:
        return {
            **base,
            "perfected": False,
            "status": f"obstructed_{obstructions[0]}",
            "perfection_routes": [],
            "obstructions": obstructions,
        }
    if active_routes:
        primary = active_routes[0]
        if primary == "direct":
            if before_ingress is False:
                return {
                    **base,
                    "perfected": False,
                    "status": "post_ingress_contact_unverified",
                    "perfection_routes": active_routes,
                    "obstructions": obstructions,
                }
            if intervening_count > 0:
                return {
                    **base,
                    "perfected": False,
                    "status": "direct_contact_with_intervening_unverified",
                    "perfection_routes": active_routes,
                    "obstructions": obstructions,
                }
            return {
                **base,
                "perfected": True,
                "status": "perfected_direct_before_ingress",
                "perfection_routes": active_routes,
                "obstructions": obstructions,
            }
        return {
            **base,
            "perfected": True,
            "status": f"perfected_{primary}",
            "perfection_routes": active_routes,
            "obstructions": obstructions,
        }
    if querent_planet == quesited_planet:
        voc = moon_voc.get("void_of_course")
        return {
            **base,
            "perfected": voc is False,
            "status": "same_ruler",
            "perfection_routes": ["co_significator_moon"] if voc is False else [],
            "obstructions": [],
        }
    return {
        **base,
        "perfected": False,
        "status": "no_perfection",
        "perfection_routes": [],
        "obstructions": [],
    }


def build_horary_payload(
    subject: Any,
    *,
    category: str,
    orb_profile: str = DEFAULT_ORB_PROFILE,
    radicality_context: dict[str, Any] | None = None,
    clock_basis: str = "civil",
    turned_from_house: int | None = None,
    turned_house: int | None = None,
    include_inactive_fortitude_rows: bool = True,
) -> dict[str, Any]:
    """Build horary chart facts, lunar motion, radicality, fortitudes, and perfection."""
    if category not in HOUSE_BY_CATEGORY:
        raise ValueError("不支持的卜卦类别；生死与临床判断不开放")
    selected_orbs = orb_receipt(orb_profile)
    phase = partial(_applying_aspect, orb_profile=orb_profile)
    base_house = HOUSE_BY_CATEGORY[category]
    if turned_from_house is not None and turned_house is not None:
        quesited_house = ((turned_from_house - 1 + turned_house - 1) % 12) + 1
    elif turned_house is not None:
        quesited_house = ((base_house - 1 + turned_house - 1) % 12) + 1
    elif turned_from_house is not None:
        quesited_house = ((turned_from_house - 1 + base_house - 1) % 12) + 1
    else:
        quesited_house = base_house

    states = {planet: _planet_state(subject, planet) for planet in TRADITIONAL_PLANETS}
    fortitudes = evaluate_fortitudes(
        states,
        _chart_sect(subject),
        collect_fortitude_inputs(subject),
        house_system=getattr(subject, "houses_system_identifier", None),
        zodiac_type=getattr(subject, "zodiac_type", None),
        include_inactive_rows=include_inactive_fortitude_rows,
    )
    moon_state = states["Moon"]

    asc_longitude = normalize_angle(point_absolute_position(subject, "Ascendant"))
    fortune = evaluate_fortune(
        asc_longitude,
        states,
        fortitudes["physical_inputs"],
        cusps=subject_cusps(subject),
        house_system=getattr(subject, "houses_system_identifier", None),
        zodiac_type=getattr(subject, "zodiac_type", None),
    )
    asc_sign = SIGNS[int(Fraction(asc_longitude) // 30)]
    asc_degree = asc_longitude % 30.0
    querent_planet = RULER_BY_SIGN[asc_sign]
    quesited_sign = (
        asc_sign if quesited_house == 1 else _house_sign(subject, quesited_house)
    )
    quesited_planet = RULER_BY_SIGN[quesited_sign]

    querent_state = states[querent_planet]
    quesited_state = states[quesited_planet]

    others_for_moon = [states[p] for p in TRADITIONAL_PLANETS if p != "Moon"]
    motion = (
        native_lunar_contacts(subject)
        if getattr(subject, "julian_day_tt", None) is not None
        else None
    )
    moon_voc = _moon_void_of_course(
        moon_state, others_for_moon, physical_motion=motion, orb_profile=orb_profile
    )
    radicality = evaluate_radicality(
        asc_longitude,
        states,
        moon_voc,
        collect_radicality_hour(subject, clock_basis=clock_basis),
        seventh_sign=_house_sign(subject, 7) or None,
        quesited_house=quesited_house,
        sect=_chart_sect(subject),
        context=radicality_context,
        house_system=getattr(subject, "houses_system_identifier", None),
        zodiac_type=getattr(subject, "zodiac_type", None),
    )
    event_history = native_planetary_events(subject)
    lilly_conditions = evaluate_lilly_conditions(
        states,
        querent_planet,
        quesited_planet,
        _chart_sect(subject),
        phase,
        lunar_motion=motion,
        zodiac_type=getattr(subject, "zodiac_type", None),
        event_history=event_history,
    )
    perfection_summary = _summarize_perfection(
        querent_planet, quesited_planet, lilly_conditions, moon_voc
    )
    perfection_status = perfection_summary["status"]
    perfection = {
        **perfection_summary,
        "event_history": event_history,
        "lilly_conditions": lilly_conditions,
    }

    degree_candidate = _degree_aspect_candidate(
        querent_state, quesited_state, orb_profile=orb_profile
    )
    sign_relationship = directed_sign_relationship(
        querent_planet,
        querent_state["longitude"],
        quesited_planet,
        quesited_state["longitude"],
        selected_degree_aspect=(
            degree_candidate["aspect"] if degree_candidate else None
        ),
        zodiac_type=getattr(subject, "zodiac_type", None),
    )

    is_day = _chart_sect(subject) == "day"
    almuten_points: dict[str, Any] = {
        "Sun": {
            "sign": states["Sun"]["sign"],
            "degree_in_sign": states["Sun"]["degree"],
        },
        "Moon": {"sign": moon_state["sign"], "degree_in_sign": moon_state["degree"]},
        "Ascendant": {"sign": asc_sign, "degree_in_sign": asc_degree},
    }
    if (
        isinstance(fortune, Mapping)
        and fortune.get("sign")
        and fortune.get("degree_in_sign") is not None
    ):
        almuten_points["fortune"] = {
            "sign": fortune["sign"],
            "degree_in_sign": fortune["degree_in_sign"],
        }
    chart_almuten = build_almuten_figuris(almuten_points, is_day)
    antiscia = _antiscia_contacts(states, asc_longitude=asc_longitude)

    raw_basis = getattr(subject, "calculation_basis", None)
    source_identity = _horary_ephemeris_source_identity(subject, event_history)
    calculation_basis = (
        {**raw_basis, "ephemeris_source_identity": source_identity}
        if isinstance(raw_basis, dict)
        else raw_basis
    )

    payload = {
        "system": "horary",
        "system_label": "卜卦证据",
        "category": category,
        "category_label": CATEGORY_LABELS_ZH[category],
        "quesited_house": quesited_house,
        "turned_from_house": turned_from_house,
        "turned_house": turned_house,
        "ascendant": {
            "sign": asc_sign,
            "sign_label": sign_label(asc_sign),
            "degree": asc_degree,
            "longitude": asc_longitude,
        },
        "significators": {
            "querent": {"house": 1, **querent_state},
            "quesited": {"house": quesited_house, **quesited_state},
            "moon_co_significator": moon_state,
            "directed_sign_relationship": sign_relationship,
        },
        "planets": states,
        "fortitudes": fortitudes,
        "fortune": fortune,
        "chart_almuten": chart_almuten,
        "antiscia_contacts": antiscia,
        "radicality": radicality,
        "moon": {
            "sign": moon_state["sign"],
            "sign_label": moon_state["sign_label"],
            "speed": moon_state["speed"],
            **moon_voc,
        },
        "perfection": perfection,
        "rule_profile": {
            "rule_id": "horary_lilly_consideration_review_v10",
            "sign_relationship_policy": LILLY_SIGN_RAYS_METHOD,
            "source_edition": "William Lilly, Christian Astrology, London 1647",
            "orb_table": selected_orbs,
            "judgement_status": perfection_status,
        },
        "calculation_basis": calculation_basis,
        "ephemeris_source_identity": source_identity,
    }
    if unresolved_ascendant(subject):
        _qualify_unresolved_reference(
            payload, subject, radicality_context=radicality_context
        )
    return payload


def _qualify_unresolved_reference(
    payload: dict[str, Any],
    subject: Any,
    *,
    radicality_context: dict[str, Any] | None,
) -> None:
    """Retain formal replay without promoting an arbitrary ASC to a judgement."""
    dependent_houses = unresolved_houses(subject)
    backend = {
        key: payload[key]
        for key in [
            "ascendant",
            "significators",
            "planets",
            "fortune",
            "fortitudes",
            "radicality",
            "perfection",
        ]
    }
    states = {}
    for name, original in payload["planets"].items():
        state = dict(original)
        if dependent_houses:
            state.update(
                occupied_house=None,
                house_assignment=assign_from_cusps(
                    state["longitude"],
                    None,
                    house_system=getattr(subject, "houses_system_identifier", None),
                    zodiac_type=getattr(subject, "zodiac_type", None),
                ),
                house_condition=house_condition(
                    None,
                    getattr(subject, "houses_system_identifier", None),
                    getattr(subject, "zodiac_type", None),
                ),
            )
        states[name] = state
    physical = payload["fortitudes"]["physical_inputs"]
    payload["planets"] = states
    payload["fortitudes"] = evaluate_fortitudes(
        states,
        _chart_sect(subject),
        physical,
        house_system=getattr(subject, "houses_system_identifier", None),
        zodiac_type=getattr(subject, "zodiac_type", None),
    )
    payload["fortune"] = evaluate_fortune(
        None,
        states,
        physical,
        cusps=None if dependent_houses else subject_cusps(subject),
        house_system=getattr(subject, "houses_system_identifier", None),
        zodiac_type=getattr(subject, "zodiac_type", None),
    )
    payload["radicality"] = evaluate_radicality(
        None,
        states,
        payload["moon"],
        backend["radicality"]["hour_inputs"],
        seventh_sign=None if dependent_houses else _house_sign(subject, 7),
        quesited_house=payload["quesited_house"],
        sect=_chart_sect(subject),
        context=radicality_context,
        house_system=getattr(subject, "houses_system_identifier", None),
        zodiac_type=getattr(subject, "zodiac_type", None),
    )
    payload["ascendant"] = {
        "longitude": None,
        "sign": None,
        "sign_label": None,
        "degree": None,
        "status": "underdetermined_reference_geometry",
    }
    independent_quesited = None
    if not dependent_houses and payload["quesited_house"] != 1:
        ruler = RULER_BY_SIGN[_house_sign(subject, payload["quesited_house"])]
        independent_quesited = {"house": payload["quesited_house"], **states[ruler]}
    payload["significators"] = {
        "querent": None,
        "quesited": independent_quesited,
        "moon_co_significator": states["Moon"],
        "directed_sign_relationship": None,
    }
    payload["perfection"] = {
        "status": "underdetermined_reference_geometry",
        "missing_conditions": ["physically_resolved_ascendant_and_querent_identity"],
        "event_history": backend["perfection"]["event_history"],
        "lilly_conditions": None,
    }
    payload["reference_geometry"] = reference_qualification(subject)
    payload["backend_convention"] = backend
    payload["rule_profile"] = {
        **payload["rule_profile"],
        "judgement_status": "reference_geometry_unresolved",
    }


__all__ = [
    "HOUSE_BY_CATEGORY",
    "CATEGORY_LABELS_ZH",
    "build_horary_payload",
]
