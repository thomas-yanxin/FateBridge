"""Candidate-time geometry and selected electional source predicates."""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

from fatebridge.core.astro.astrology_tables import (
    EXALTATION_SIGNS,
    RULER_BY_SIGN,
    SIGNS,
)
from fatebridge.core.astro.classical import _resolve_planetary_hour
from fatebridge.core.astro.event_reference import (
    reference_qualification,
    unresolved_ascendant,
    unresolved_houses,
)
from fatebridge.core.astro.geometry import (
    angular_separation_fraction,
    longitude_float,
    normalize_angle,
)
from fatebridge.core.astro.horary_events import native_planetary_events
from fatebridge.core.astro.horary_motion import native_lunar_contacts

_ORIG_NATIVE_PLANETARY_EVENTS = native_planetary_events
from fatebridge.core.classical_western import combustion_state
from fatebridge.core.planetary_event_order import ordered_contact
from fatebridge.core.predictive._common import (
    planet_label,
    point_absolute_position,
    sign_label,
)

BENEFICS = ("Venus", "Jupiter")
MALEFICS = ("Mars", "Saturn")
ANGLE_ORB = 5.0  # a planet within this of the Asc/MC degree counts as "on the angle"

PLANET_ATTRIBUTES: dict[str, str] = {
    "Sun": "sun",
    "Moon": "moon",
    "Mercury": "mercury",
    "Venus": "venus",
    "Mars": "mars",
    "Jupiter": "jupiter",
    "Saturn": "saturn",
}

TOPIC_MASTER: dict[str, dict[str, Any]] = {
    "marriage": {
        "house": 7,
        "significator": "Venus",
        "label": "结婚",
    },
    "business": {
        "house": 10,
        "significator": "Jupiter",
        "label": "开业/创业",
    },
    "move_in": {
        "house": 4,
        "significator": "Moon",
        "label": "入宅/迁居",
    },
    "buy_property": {
        "house": 4,
        "significator": "Venus",
        "label": "购屋",
    },
    "trade": {
        "house": 2,
        "significator": "Mercury",
        "label": "买卖交易",
    },
    "buy_car": {
        "house": 3,
        "significator": "Mercury",
        "label": "购车",
    },
    "contract": {
        "house": 7,
        "significator": "Mercury",
        "label": "签约",
    },
    "travel": {
        "house": 9,
        "significator": "Mercury",
        "label": "出行",
    },
    "job_hunt": {
        "house": 10,
        "significator": "Sun",
        "label": "求职",
    },
    "general": {
        "house": 1,
        "significator": "Moon",
        "label": "通用",
    },
}


def _dignity(planet: str, sign: str) -> str:
    """Sign-only major dignity; missing minor dignities cannot prove peregrine."""
    opposite = SIGNS[(SIGNS.index(sign) + 6) % 12]
    if RULER_BY_SIGN.get(sign) == planet:
        return "rulership"
    if EXALTATION_SIGNS.get(planet) == sign:
        return "exaltation"
    if RULER_BY_SIGN.get(opposite) == planet:
        return "detriment"
    if EXALTATION_SIGNS.get(planet) == opposite:
        return "fall"
    return "no_major_dignity"


def _planet_view(subject: Any, planet: str) -> dict[str, Any]:
    point = getattr(subject, PLANET_ATTRIBUTES[planet])
    longitude = normalize_angle(float(point.abs_pos))
    sign = SIGNS[int(Fraction(longitude) // 30)]
    raw_speed = getattr(point, "speed", None)
    speed = None if raw_speed is None else float(raw_speed)
    if speed is not None and not math.isfinite(speed):
        raise RuntimeError("Nonfinite native longitude speed")
    return {
        "planet": planet,
        "sign": sign,
        "longitude": longitude,
        "speed": speed,
        "retrograde": None if speed is None else speed < 0.0,
        "house": getattr(point, "house", None),
        "dignity": _dignity(planet, sign),
    }


def build_election_payload(subject: Any, *, topic_id: str) -> dict[str, Any]:
    """Return observable conditions for the requested candidate moment."""
    if topic_id not in TOPIC_MASTER:
        raise ValueError("不支持的择日主题；医疗择时不开放")
    topic = TOPIC_MASTER[topic_id]

    views = {planet: _planet_view(subject, planet) for planet in PLANET_ATTRIBUTES}
    moon, sun = views["Moon"], views["Sun"]
    backend_asc = normalize_angle(point_absolute_position(subject, "Ascendant"))
    unresolved_reference = unresolved_ascendant(subject)
    asc_lon = None if unresolved_reference else backend_asc
    mc_lon = normalize_angle(point_absolute_position(subject, "Medium_Coeli"))
    asc_sign = None if asc_lon is None else SIGNS[int(Fraction(asc_lon) // 30)]
    backend_sign = SIGNS[int(Fraction(backend_asc) // 30)]
    backend_reference_factors: list[dict[str, Any]] = []

    factors: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    native_epoch = getattr(subject, "julian_day_tt", None)
    motion = (
        native_lunar_contacts(subject)
        if native_epoch is not None
        else {
            "status": "unavailable",
            "method_id": "native_tt_lunar_contacts_before_ingress_v1",
            "constant_velocity_projection": False,
            "void_of_course": None,
            "contacts": [],
            "unavailable_reason": "No native TT chart epoch; no civil time or linear substitute was guessed",
        }
    )
    moon_voc = motion["void_of_course"]
    if moon_voc is None:
        unresolved.append(
            {
                "code": "moon_void_of_course",
                "reason": "Native before-ingress event condition is unknown",
            }
        )
    elif moon_voc:
        factors.append({"code": "moon_void_of_course", "body": "Moon"})

    elongation = (Fraction(moon["longitude"]) - Fraction(sun["longitude"])) % 360
    phase = (
        "new"
        if elongation == 0
        else "full" if elongation == 180 else "waxing" if elongation < 180 else "waning"
    )
    solar_state = combustion_state(moon["longitude"], sun["longitude"])
    if solar_state == "combust":
        factors.append({"code": "moon_combust", "body": "Moon"})
    if Fraction(195) <= Fraction(moon["longitude"]) <= Fraction(225):
        factors.append({"code": "moon_via_combusta", "body": "Moon"})

    for planets, kind in ((MALEFICS, "malefic"), (BENEFICS, "benefic")):
        for planet in planets:
            longitude = views[planet]["longitude"]
            code = f"{kind}_on_angle_{planet.lower()}"
            on_midheaven = angular_separation_fraction(longitude, mc_lon) <= ANGLE_ORB
            hit_axes = ["Midheaven"] if on_midheaven else []
            if (
                asc_lon is not None
                and angular_separation_fraction(longitude, asc_lon) <= ANGLE_ORB
            ):
                hit_axes.append("Ascendant")
            if hit_axes:
                factors.append(
                    {"code": code, "body": planet, "resolved_hit_axes": hit_axes}
                )
            elif asc_lon is None:
                unresolved.append(
                    {
                        "code": code,
                        "reason": "No MC hit; physical ASC remains unresolved",
                    }
                )
            if unresolved_reference:
                backend_axes = ["Midheaven"] if on_midheaven else []
                if angular_separation_fraction(longitude, backend_asc) <= ANGLE_ORB:
                    backend_axes.append("Ascendant")
                if backend_axes:
                    backend_reference_factors.append(
                        {
                            "code": code,
                            "body": planet,
                            "resolved_hit_axes": backend_axes,
                        }
                    )

    asc_ruler = None if asc_sign is None else RULER_BY_SIGN[asc_sign]
    asc_ruler_dignity = None if asc_ruler is None else views[asc_ruler]["dignity"]
    if unresolved_reference:
        unresolved.append(
            {
                "code": "ascendant_ruler_condition",
                "reason": "Unresolved physical ASC cannot select its ruler",
            }
        )
    significator = topic["significator"]
    for planet, code in (
        ("Mercury", "mercury_retrograde"),
        (significator, "significator_retrograde"),
    ):
        if code == "significator_retrograde" and planet == "Mercury":
            continue
        retrograde = views[planet]["retrograde"]
        if retrograde is None:
            unresolved.append(
                {"code": code, "reason": f"{planet} longitude speed is unavailable"}
            )
        elif retrograde:
            factors.append({"code": code, "body": planet})

    contacts = motion.get("contacts") or []
    next_applying_aspect = contacts[0] if contacts else None

    ut1_epoch = getattr(subject, "ut1", None) or getattr(subject, "julian_day", None)
    lng, lat, tz = (
        getattr(subject, "lng", None),
        getattr(subject, "lat", None),
        getattr(subject, "tz_str", None),
    )
    planetary_hour_info = None
    planetary_hour_match: bool | None = None
    if ut1_epoch is not None and lng is not None and lat is not None and tz is not None:
        hour_res = _resolve_planetary_hour(ut1_epoch, lng, lat, tz)
        if isinstance(hour_res, dict):
            planetary_hour_info = hour_res
            planetary_hour_match = (
                hour_res.get("hour_ruler") == significator
                or hour_res.get("day_ruler") == significator
            )

    payload: dict[str, Any] = {
        "system": "election",
        "system_label": "择日（电选）",
        "topic_id": topic_id,
        "topic_label": topic["label"],
        "topic_house": topic["house"],
        "significator": significator,
        "significator_label": planet_label(significator),
        "planets": views,
        "calculation_basis": getattr(subject, "calculation_basis", None),
        "axes": {
            "ascendant_longitude": asc_lon,
            "midheaven_longitude": mc_lon,
            "first_house_cusp": normalize_angle(float(subject.first_house.abs_pos)),
            "tenth_house_cusp": normalize_angle(float(subject.tenth_house.abs_pos)),
        },
        "ascendant": {
            "sign": asc_sign,
            "sign_label": None if asc_sign is None else sign_label(asc_sign),
            "ruler": asc_ruler,
            "ruler_label": None if asc_ruler is None else planet_label(asc_ruler),
            "ruler_dignity": asc_ruler_dignity,
            "longitude": asc_lon,
        },
        "moon": {
            "sign": moon["sign"],
            "sign_label": sign_label(moon["sign"]),
            "void_of_course": moon_voc,
            "next_applying_aspect": next_applying_aspect,
            "longitude": moon["longitude"],
            "phase": phase,
            "elongation_degrees": longitude_float(elongation),
            "solar_condition": solar_state,
            "motion_basis": motion,
        },
        "planetary_hour": planetary_hour_info,
        "planetary_hour_match": planetary_hour_match,
        "factors": factors,
        "unresolved_factors": unresolved,
        "marriage_significators": None,
    }
    if topic_id == "marriage":
        house_code = getattr(subject, "houses_system_identifier", None)
        zodiac = getattr(subject, "zodiac_type", None)
        source_method = house_code == "R" and zodiac in {"Tropic", "Tropical"}
        houses = []
        parties = []
        history = None
        if source_method:
            for house, point, role, longitude in [
                (1, "Ascendant", "first_source_party", asc_lon),
                (
                    7,
                    "Descendant",
                    "second_source_party",
                    (
                        None
                        if asc_lon is None
                        else longitude_float(Fraction(asc_lon) + 180)
                    ),
                ),
                (10, "Midheaven", "between_parties", mc_lon),
                (
                    4,
                    "Imum_Coeli",
                    "conclusion",
                    longitude_float(Fraction(mc_lon) + 180),
                ),
            ]:
                sign = (
                    None if longitude is None else SIGNS[int(Fraction(longitude) // 30)]
                )
                ruler = None if sign is None else RULER_BY_SIGN[sign]
                houses.append(
                    {
                        "house": house,
                        "reference_point": point,
                        "role_in_source": role,
                        "longitude": longitude,
                        "sign": sign,
                        "ruler": ruler,
                        "ruler_state": (
                            None
                            if ruler is None
                            else {
                                **views[ruler],
                                "house": (
                                    None
                                    if unresolved_houses(subject)
                                    else views[ruler]["house"]
                                ),
                            }
                        ),
                    }
                )
            if native_epoch is not None:
                if native_planetary_events is _ORIG_NATIVE_PLANETARY_EVENTS:
                    history = native_planetary_events(
                        subject,
                        past_days=5.0,
                        future_days=5.0,
                        moon_contacts_only=True,
                    )
                    if history.get("status") == "computed":
                        past_c, past_ok = ordered_contact(
                            history.get("events", []),
                            history.get("unresolved_intervals", []),
                            "Moon",
                            past=True,
                        )
                        fut_c, fut_ok = ordered_contact(
                            history.get("events", []),
                            history.get("unresolved_intervals", []),
                            "Moon",
                            past=False,
                        )
                        if (
                            past_c is None
                            or fut_c is None
                            or past_ok is not True
                            or fut_ok is not True
                        ):
                            history = native_planetary_events(
                                subject, moon_contacts_only=True
                            )
                else:
                    history = native_planetary_events(subject)
            else:
                history = {
                    "status": "unavailable",
                    "constant_velocity_projection": False,
                    "events": [],
                    "unavailable_reason": "No native TT chart epoch; no civil time or linear substitute was guessed",
                }
            for role, natural, past in [
                ("first_source_party", "Sun", True),
                ("second_source_party", "Venus", False),
            ]:
                contact, order = (
                    ordered_contact(
                        history["events"],
                        history.get("unresolved_intervals", []),
                        "Moon",
                        past=past,
                    )
                    if history["status"] == "computed"
                    and history["constant_velocity_projection"] is False
                    else (None, None)
                )
                parties.append(
                    {
                        "role_in_source": role,
                        "natural_significator": natural,
                        "lunar_contact_role": (
                            "last_separating_contact"
                            if past
                            else "next_applying_contact"
                        ),
                        "lunar_significator": (
                            next(p for p in contact["bodies"] if p != "Moon")
                            if contact is not None and order is True
                            else None
                        ),
                        "contact_order_established": order,
                        "contact": contact,
                    }
                )
        payload["marriage_significators"] = {
            "method_id": "ramesey_1653_p175_marriage_significators_v2",
            "status": (
                "not_assessed_for_selected_method"
                if not source_method
                else (
                    "partial_reference_geometry"
                    if unresolved_reference
                    else (
                        "computed_source_facts"
                        if all(p["contact_order_established"] is True for p in parties)
                        else "partial_lunar_history"
                    )
                )
            ),
            "author": "William Ramesey",
            "edition": "Astrologia Restaurata, London 1653, Book III, Section VIII, Chapter I",
            "source_pages": [175],
            "house_system": house_code,
            "zodiac_type": zodiac,
            "houses": houses,
            "parties": parties,
            "event_history": history,
        }
    if unresolved_reference:
        nominal_ruler = RULER_BY_SIGN[backend_sign]
        payload["backend_convention"] = {
            "ascendant": {
                "longitude": backend_asc,
                "sign": backend_sign,
                "ruler": nominal_ruler,
                "ruler_dignity": views[nominal_ruler]["dignity"],
            },
            "axes": {
                "ascendant_longitude": backend_asc,
                "first_house_cusp": payload["axes"]["first_house_cusp"],
                "tenth_house_cusp": payload["axes"]["tenth_house_cusp"],
            },
            "planets": views,
            "reference_factors": backend_reference_factors,
        }
        if unresolved_houses(subject):
            payload["planets"] = {p: {**v, "house": None} for p, v in views.items()}
            payload["axes"]["first_house_cusp"] = None
            payload["axes"]["tenth_house_cusp"] = None
        payload["reference_geometry"] = reference_qualification(subject)
    return payload
