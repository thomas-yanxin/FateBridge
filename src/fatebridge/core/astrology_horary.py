"""
FateBridge 卜卦 (horary) judgment engine.

Horary answers a specific question from a chart cast for the *moment the question
was asked* (not a birth). Judgment follows classical doctrine (Lilly / Bonatti):

1. **Significators** — the querent is the ruler of the 1st house, co-signified by
   the Moon; the quesited is the ruler of the house matching the question's topic.
2. **Radicality** — strictures that warn the chart may not be safe to judge
   (Ascendant too early/late, Moon void of course, Via Combusta, Saturn in the
   1st/7th).
3. **Perfection** — the matter comes to pass if the significators join by an
   *applying* Ptolemaic aspect, or light is carried between them (translation) or
   gathered by a third planet (collection), or the Moon applies to the quesited.

This module is pure geometry + tables over an already-built chart subject; it
imports the ruler/dignity tables from :mod:`fatebridge.core.astrology_tables` and reads
longitudes, speeds and house cusps off the kerykeion subject. Casting the chart
and rendering output is the service layer's job.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fatebridge.core.astrology_tables import EXALTATION_SIGNS, RULER_BY_SIGN
from fatebridge.core.classical_western import bound_lord as _bound_lord
from fatebridge.core.classical_western import triplicity_members
from fatebridge.core.predictive._common import (
    normalize_sign_name,
    planet_label,
    sign_label,
)

# The seven traditional planets, in classical (Chaldean, slowest-first) order so
# "collection of light" prefers the heavier collector.
TRADITIONAL_PLANETS = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]

# Ptolemaic aspects only — horary does not judge by minor aspects.
PTOLEMAIC_ASPECTS: List[Tuple[str, str, float]] = [
    ("conjunction", "合", 0.0),
    ("sextile", "六合", 60.0),
    ("square", "刑", 90.0),
    ("trine", "拱", 120.0),
    ("opposition", "冲", 180.0),
]

# Classical moieties (half-orbs, degrees). The combined orb of two planets is the
# average of their moieties.
PLANET_MOIETIES: Dict[str, float] = {
    "Sun": 15.0,
    "Moon": 12.0,
    "Mercury": 7.0,
    "Venus": 7.0,
    "Mars": 8.0,
    "Jupiter": 9.0,
    "Saturn": 9.0,
}

# Question topic → quesited house (whole derived-house logic kept simple: the
# turned house is not modelled; the radical house of the matter is used).
HOUSE_BY_CATEGORY: Dict[str, int] = {
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
CATEGORY_LABELS_ZH: Dict[str, str] = {
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

PLANET_ATTRIBUTES: Dict[str, str] = {
    "Sun": "sun",
    "Moon": "moon",
    "Mercury": "mercury",
    "Venus": "venus",
    "Mars": "mars",
    "Jupiter": "jupiter",
    "Saturn": "saturn",
}

# Via Combusta — the "burnt path", 15° Libra to 15° Scorpio (195°–225° absolute).
VIA_COMBUSTA = (195.0, 225.0)


def _signed_separation(first: float, second: float) -> float:
    """Signed angular gap ``first − second`` folded into (−180, 180]."""
    return (first - second + 540.0) % 360.0 - 180.0


def _aspect_orb(planet_a: str, planet_b: str) -> float:
    return (PLANET_MOIETIES[planet_a] + PLANET_MOIETIES[planet_b]) / 2.0


def _planet_state(subject: Any, planet: str) -> Dict[str, Any]:
    point = getattr(subject, PLANET_ATTRIBUTES[planet])
    sign = normalize_sign_name(getattr(point, "sign", ""))
    longitude = float(point.abs_pos)
    speed = float(getattr(point, "speed", 0.0))
    return {
        "planet": planet,
        "planet_label": planet_label(planet),
        "sign": sign,
        "sign_label": sign_label(sign),
        "degree": round(longitude % 30.0, 4),
        "absolute_degree": round(longitude, 4),
        # Round to 9 decimals (~3 µarcsec) so the serialized longitude is stable
        # against sub-1e-12 float-representation noise that shifts between
        # ephemeris dependency micro-versions; far finer than any orb tolerance,
        # so downstream aspect math is unaffected.
        "longitude": round(longitude, 9),
        "speed": round(speed, 5),
        "retrograde": speed < 0.0,
        "dignities": _dignities(planet, sign, longitude % 30.0),
    }


def _dignities(planet: str, sign: str, degree_in_sign: float) -> List[str]:
    """Which essential dignities ``planet`` holds at this sign+degree.

    Membership-style (triplicity = any of the three Dorothean rulers), kept
    byte-identical to the pre-extraction horary behaviour; the bound and
    triplicity primitives now live in :mod:`fatebridge.core.classical_western`.
    """
    found: List[str] = []
    if RULER_BY_SIGN.get(sign) == planet:
        found.append("rulership")
    if EXALTATION_SIGNS.get(planet) == sign:
        found.append("exaltation")
    if planet in triplicity_members(sign):
        found.append("triplicity")
    if _bound_lord(sign, degree_in_sign) == planet:
        found.append("bound")
    return found


def _applying_aspect(
    state_a: Dict[str, Any], state_b: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    The Ptolemaic aspect between two bodies within orb, flagged applying or
    separating. Applying means the exact-aspect gap shrinks as time advances
    (using each body's real speed, so retrogrades are handled).
    """
    lon_a, lon_b = state_a["longitude"], state_b["longitude"]
    speed_a, speed_b = state_a["speed"], state_b["speed"]
    orb_limit = _aspect_orb(state_a["planet"], state_b["planet"])
    separation = abs(_signed_separation(lon_a, lon_b))

    for key, label, angle in PTOLEMAIC_ASPECTS:
        orb = abs(separation - angle)
        if orb > orb_limit:
            continue
        # Step a small increment forward; if the orb to this aspect shrinks the
        # bodies are applying.
        step = 0.05
        future_sep = abs(
            _signed_separation(lon_a + speed_a * step, lon_b + speed_b * step)
        )
        applying = abs(future_sep - angle) < orb
        return {
            "aspect": key,
            "aspect_label": label,
            "angle": angle,
            "orb": round(orb, 4),
            "applying": applying,
            "phase": "applying" if applying else "separating",
        }
    return None


def _mutual_reception(state_a: Dict[str, Any], state_b: Dict[str, Any]) -> List[str]:
    """
    Reception terms where one significator sits in the other's dignity. A planet
    in the sign another rules (or exalts) is "received" by that other — reception
    softens otherwise hard contacts.
    """
    receptions: List[str] = []
    if RULER_BY_SIGN.get(state_a["sign"]) == state_b["planet"]:
        receptions.append(f"{state_b['planet_label']}以庙纳{state_a['planet_label']}")
    if RULER_BY_SIGN.get(state_b["sign"]) == state_a["planet"]:
        receptions.append(f"{state_a['planet_label']}以庙纳{state_b['planet_label']}")
    if EXALTATION_SIGNS.get(state_b["planet"]) == state_a["sign"]:
        receptions.append(f"{state_b['planet_label']}以旺纳{state_a['planet_label']}")
    if EXALTATION_SIGNS.get(state_a["planet"]) == state_b["sign"]:
        receptions.append(f"{state_a['planet_label']}以旺纳{state_b['planet_label']}")
    return receptions


def _house_sign(subject: Any, house_number: int) -> str:
    cusp = getattr(subject, HOUSE_ATTRIBUTES[house_number - 1])
    return normalize_sign_name(getattr(cusp, "sign", ""))


def _moon_void_of_course(
    moon_state: Dict[str, Any], other_states: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    The Moon is void of course if it completes no applying Ptolemaic aspect to a
    traditional planet before leaving its current sign. Returns the next aspect
    (if any) so the service can explain the judgment.
    """
    moon_lon = moon_state["longitude"]
    degrees_left_in_sign = 30.0 - (moon_lon % 30.0)
    next_aspect: Optional[Dict[str, Any]] = None
    best_distance = float("inf")

    for other in other_states:
        aspect = _applying_aspect(moon_state, other)
        if aspect is None or not aspect["applying"]:
            continue
        # Degrees of Moon travel until exact (Moon is far faster, approximate by
        # its own motion toward the aspect).
        distance_to_exact = aspect["orb"]
        if (
            distance_to_exact <= degrees_left_in_sign
            and distance_to_exact < best_distance
        ):
            best_distance = distance_to_exact
            next_aspect = {
                "other": other["planet"],
                "other_label": other["planet_label"],
                **aspect,
            }

    return {
        "void_of_course": next_aspect is None,
        "degrees_left_in_sign": round(degrees_left_in_sign, 4),
        "next_aspect": next_aspect,
    }


def build_horary_payload(subject: Any, *, category: str) -> Dict[str, Any]:
    """
    Judge a horary chart for ``category``. Returns significators, radicality
    strictures, the perfection finding, and an overall verdict with reasoning.
    """
    if category not in HOUSE_BY_CATEGORY:
        raise ValueError("不支持的卜卦类别；生死与临床判断不开放")
    quesited_house = HOUSE_BY_CATEGORY[category]

    states = {planet: _planet_state(subject, planet) for planet in TRADITIONAL_PLANETS}
    moon_state = states["Moon"]

    asc_sign = _house_sign(subject, 1)
    asc_degree = float(subject.first_house.abs_pos) % 30.0
    querent_planet = RULER_BY_SIGN[asc_sign]
    quesited_sign = _house_sign(subject, quesited_house)
    quesited_planet = RULER_BY_SIGN[quesited_sign]

    querent_state = states[querent_planet]
    quesited_state = states[quesited_planet]

    # --- Radicality strictures --------------------------------------------
    strictures: List[Dict[str, Any]] = []
    if asc_degree < 3.0:
        strictures.append(
            {
                "code": "ascendant_too_early",
                "detail": f"上升 {round(asc_degree, 2)}°，过早。",
            }
        )
    elif asc_degree > 27.0:
        strictures.append(
            {
                "code": "ascendant_too_late",
                "detail": f"上升 {round(asc_degree, 2)}°，过晚。",
            }
        )
    saturn_house = getattr(subject.saturn, "house", "")
    if saturn_house == "Seventh_House":
        strictures.append(
            {
                "code": "saturn_in_seventh",
                "detail": "土星落第七宫。",
            }
        )
    if saturn_house == "First_House":
        strictures.append({"code": "saturn_in_first", "detail": "土星落第一宫。"})
    moon_abs = moon_state["absolute_degree"]
    if VIA_COMBUSTA[0] <= moon_abs <= VIA_COMBUSTA[1]:
        strictures.append(
            {
                "code": "moon_via_combusta",
                "detail": "月亮行经燃烧之路(天秤15°–天蝎15°)。",
            }
        )

    # --- Moon void of course ----------------------------------------------
    others_for_moon = [states[p] for p in TRADITIONAL_PLANETS if p != "Moon"]
    moon_voc = _moon_void_of_course(moon_state, others_for_moon)
    if moon_voc["void_of_course"]:
        strictures.append(
            {
                "code": "moon_void_of_course",
                "detail": "月亮空亡：在离开本宫前不再完成任何主相位。",
            }
        )

    # --- Perfection --------------------------------------------------------
    perfection = _judge_perfection(
        querent_state,
        quesited_state,
        moon_state,
        states,
        querent_planet,
        quesited_planet,
    )

    verdict, reasoning = _verdict(perfection, moon_voc, strictures, category)

    return {
        "system": "horary",
        "system_label": "卜卦判断",
        "category": category,
        "category_label": CATEGORY_LABELS_ZH[category],
        "quesited_house": quesited_house,
        "ascendant": {
            "sign": asc_sign,
            "sign_label": sign_label(asc_sign),
            "degree": round(asc_degree, 4),
        },
        "significators": {
            "querent": {"house": 1, **querent_state},
            "quesited": {"house": quesited_house, **quesited_state},
            "moon_co_significator": moon_state,
        },
        "radicality": {
            "safe_to_judge": not any(
                s["code"] in ("ascendant_too_early", "ascendant_too_late")
                for s in strictures
            ),
            "strictures": strictures,
        },
        "moon": {
            "sign": moon_state["sign"],
            "sign_label": moon_state["sign_label"],
            "speed": moon_state["speed"],
            **moon_voc,
        },
        "perfection": perfection,
        "verdict": verdict,
        "reasoning": reasoning,
    }


def _judge_perfection(
    querent_state: Dict[str, Any],
    quesited_state: Dict[str, Any],
    moon_state: Dict[str, Any],
    states: Dict[str, Dict[str, Any]],
    querent_planet: str,
    quesited_planet: str,
) -> Dict[str, Any]:
    """Find how (if at all) the matter perfects: direct, translation, collection, or moon."""
    receptions = _mutual_reception(querent_state, quesited_state)

    # 1. Direct aspect between the two significators.
    if querent_planet != quesited_planet:
        direct = _applying_aspect(querent_state, quesited_state)
        if direct is not None and direct["applying"]:
            return {
                "perfects": True,
                "mode": "direct",
                "mode_label": "两造主星直接入相",
                "aspect": direct,
                "receptions": receptions,
            }
    else:
        return {
            "perfects": True,
            "mode": "same_ruler",
            "mode_label": "两造同主星（事主与所问同源，多主成）",
            "receptions": receptions,
        }

    # 2. Translation of light: a third (faster) planet separating from one
    #    significator and applying to the other.
    for planet, state in states.items():
        if planet in (querent_planet, quesited_planet):
            continue
        to_querent = _applying_aspect(state, querent_state)
        to_quesited = _applying_aspect(state, quesited_state)
        applies = [a for a in (to_querent, to_quesited) if a and a["applying"]]
        separates = [a for a in (to_querent, to_quesited) if a and not a["applying"]]
        if applies and separates:
            return {
                "perfects": True,
                "mode": "translation",
                "mode_label": f"{state['planet_label']}传递光线（先离一造、再入相另一造）",
                "carrier": state["planet"],
                "carrier_label": state["planet_label"],
                "receptions": receptions,
            }

    # 3. Collection of light: a third (slower) planet receiving applying aspects
    #    from both significators.
    for planet in TRADITIONAL_PLANETS:
        if planet in (querent_planet, quesited_planet):
            continue
        state = states[planet]
        if (
            state["speed"] >= querent_state["speed"]
            and state["speed"] >= quesited_state["speed"]
        ):
            continue
        to_querent = _applying_aspect(querent_state, state)
        to_quesited = _applying_aspect(quesited_state, state)
        if (
            to_querent
            and to_querent["applying"]
            and to_quesited
            and to_quesited["applying"]
        ):
            return {
                "perfects": True,
                "mode": "collection",
                "mode_label": f"{state['planet_label']}收集光线（两造皆入相于它）",
                "collector": state["planet"],
                "collector_label": state["planet_label"],
                "receptions": receptions,
            }

    # 4. The Moon (querent's co-significator) applies to the quesited significator.
    if quesited_planet != "Moon":
        moon_to_quesited = _applying_aspect(moon_state, quesited_state)
        if moon_to_quesited is not None and moon_to_quesited["applying"]:
            return {
                "perfects": True,
                "mode": "moon",
                "mode_label": "月亮（事主副星）入相所问主星",
                "aspect": moon_to_quesited,
                "receptions": receptions,
            }

    return {
        "perfects": False,
        "mode": "none",
        "mode_label": "两造之间无成相之路",
        "receptions": receptions,
    }


def _verdict(
    perfection: Dict[str, Any],
    moon_voc: Dict[str, Any],
    strictures: List[Dict[str, Any]],
    category: str,
) -> Tuple[str, str]:
    """Boil the findings down to a verdict + a human-readable reasoning line."""
    stricture_codes = {s["code"] for s in strictures}
    too_early_or_late = stricture_codes & {"ascendant_too_early", "ascendant_too_late"}

    if too_early_or_late:
        return (
            "uncertain",
            "上升过早/过晚，传统视为不宜遽下判断；先确认提问时刻确为心念成形之时。",
        )

    if perfection["perfects"]:
        if moon_voc["void_of_course"]:
            return (
                "qualified_yes",
                f"主星可经『{perfection['mode_label']}』成相，但月亮空亡——多主『虽有路径、却拖延或落空』，宜谨慎乐观。",
            )
        aspect = perfection.get("aspect")
        hard = aspect and aspect["aspect"] in ("square", "opposition")
        if hard:
            return (
                "qualified_yes",
                f"经『{perfection['mode_label']}』成相，但以刑冲成之，事虽成而多波折、需费力。",
            )
        receptions = perfection.get("receptions") or []
        reception_note = (
            f"，且有互纳（{ '、'.join(receptions) }）相助" if receptions else ""
        )
        return (
            "yes",
            f"主星经『{perfection['mode_label']}』以吉相成相{reception_note}，主『可成』。",
        )

    if moon_voc["void_of_course"]:
        return (
            "no",
            "两造之间无成相之路，且月亮空亡——传统断为『不成 / 无事发生』。",
        )
    return (
        "no",
        "两造主星之间无应许的入相成相，亦无传递/收集光线——主『难成』。",
    )


__all__ = [
    "HOUSE_BY_CATEGORY",
    "CATEGORY_LABELS_ZH",
    "PLANET_MOIETIES",
    "build_horary_payload",
]
