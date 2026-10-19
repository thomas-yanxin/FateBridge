"""
FateBridge 择日 (electional astrology) engine.

Electional astrology evaluates whether a *candidate moment* is auspicious for
beginning a chosen undertaking. Unlike horary (which answers a question), the
chart is cast for the time being judged, and the topic (``topic_id``) selects
which house + significator matter and which strictures are red lines.

The engine scores a candidate against classical electional doctrine:

* **Universal factors** (every election): the Moon's condition above all — void
  of course, combust the Sun, waxing vs waning, the Via Combusta — plus malefics
  (Mars/Saturn) or benefics (Venus/Jupiter) on the angles, a retrograde Mercury,
  and the dignity of the Ascendant ruler.
* **Topic factors**: the house of the matter and its natural significator should
  be sound; some topics make a factor a hard red line (e.g. Mercury retrograde
  for contracts).

Output is a 0–100 score, a verdict band, and the itemised factors with polarity
and weight so an agent can explain *why*. This is pure geometry + classical
tables over an already-built chart subject; chart casting lives in the service.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fatebridge.core.astrology_tables import EXALTATION_SIGNS, RULER_BY_SIGN, SIGNS
from fatebridge.core.predictive._common import (
    normalize_sign_name,
    planet_label,
    sign_label,
)

BENEFICS = ("Venus", "Jupiter")
MALEFICS = ("Mars", "Saturn")
ANGLE_ORB = 5.0  # a planet within this of the Asc/MC degree counts as "on the angle"
COMBUST_ORB = 8.5  # Moon within this of the Sun is combust

PLANET_ATTRIBUTES: Dict[str, str] = {
    "Sun": "sun",
    "Moon": "moon",
    "Mercury": "mercury",
    "Venus": "venus",
    "Mars": "mars",
    "Jupiter": "jupiter",
    "Saturn": "saturn",
}

# topic_id -> (house of the matter, natural significator, Mercury-retrograde is a
# hard red line for this topic).
TOPIC_MASTER: Dict[str, Dict[str, Any]] = {
    "marriage": {
        "house": 7,
        "significator": "Venus",
        "mercury_hard": False,
        "label": "结婚",
    },
    "business": {
        "house": 10,
        "significator": "Jupiter",
        "mercury_hard": True,
        "label": "开业/创业",
    },
    "move_in": {
        "house": 4,
        "significator": "Moon",
        "mercury_hard": False,
        "label": "入宅/迁居",
    },
    "buy_property": {
        "house": 4,
        "significator": "Venus",
        "mercury_hard": False,
        "label": "购屋",
    },
    "trade": {
        "house": 2,
        "significator": "Mercury",
        "mercury_hard": True,
        "label": "买卖交易",
    },
    "buy_car": {
        "house": 3,
        "significator": "Mercury",
        "mercury_hard": True,
        "label": "购车",
    },
    "contract": {
        "house": 7,
        "significator": "Mercury",
        "mercury_hard": True,
        "label": "签约",
    },
    "travel": {
        "house": 9,
        "significator": "Mercury",
        "mercury_hard": False,
        "label": "出行",
    },
    "job_hunt": {
        "house": 10,
        "significator": "Sun",
        "mercury_hard": False,
        "label": "求职",
    },
    "general": {
        "house": 1,
        "significator": "Moon",
        "mercury_hard": False,
        "label": "通用",
    },
}

BASE_SCORE = 60


def _angular_gap(first: float, second: float) -> float:
    delta = abs(first - second) % 360.0
    return delta if delta <= 180.0 else 360.0 - delta


def _dignity(planet: str, sign: str) -> str:
    """Essential dignity of a traditional planet (rulership/exaltation/detriment/fall/peregrine)."""
    opposite = SIGNS[(SIGNS.index(sign) + 6) % 12]
    if RULER_BY_SIGN.get(sign) == planet:
        return "rulership"
    if EXALTATION_SIGNS.get(planet) == sign:
        return "exaltation"
    if RULER_BY_SIGN.get(opposite) == planet:
        return "detriment"
    if EXALTATION_SIGNS.get(planet) == opposite:
        return "fall"
    return "peregrine"


def _planet_view(subject: Any, planet: str) -> Dict[str, Any]:
    point = getattr(subject, PLANET_ATTRIBUTES[planet])
    sign = normalize_sign_name(getattr(point, "sign", ""))
    longitude = float(point.abs_pos)
    speed = float(getattr(point, "speed", 0.0))
    return {
        "planet": planet,
        "sign": sign,
        "longitude": longitude,
        "speed": speed,
        "retrograde": speed < 0.0,
        "house": getattr(point, "house", None),
        "dignity": _dignity(planet, sign),
    }


def _factor(
    code: str,
    polarity: str,
    weight: int,
    detail: str,
    *,
    hard: bool = False,
) -> Dict[str, Any]:
    return {
        "code": code,
        "polarity": polarity,  # "favorable" | "adverse" | "neutral"
        "weight": weight,  # signed contribution to the score
        "hard": hard,  # a hard red line strongly contraindicates regardless of score
        "detail": detail,
    }


def build_election_payload(subject: Any, *, topic_id: str) -> Dict[str, Any]:
    """Score a candidate moment for ``topic_id`` and return itemised factors + verdict."""
    if topic_id not in TOPIC_MASTER:
        raise ValueError("不支持的择日主题；医疗择时不开放")
    topic = TOPIC_MASTER[topic_id]

    views = {planet: _planet_view(subject, planet) for planet in PLANET_ATTRIBUTES}
    moon, sun = views["Moon"], views["Sun"]
    asc_lon = float(subject.first_house.abs_pos)
    mc_lon = float(subject.tenth_house.abs_pos)
    asc_sign = normalize_sign_name(subject.first_house.sign)

    factors: List[Dict[str, Any]] = []

    # --- The Moon: the soul of any election --------------------------------
    moon_voc = _moon_void_of_course(
        moon, [views[p] for p in PLANET_ATTRIBUTES if p != "Moon"]
    )
    if moon_voc:
        factors.append(
            _factor(
                "moon_void_of_course",
                "adverse",
                -25,
                "月亮空亡：起事多『虎头蛇尾、无果』，择日大忌。",
                hard=True,
            )
        )

    elongation = (moon["longitude"] - sun["longitude"]) % 360.0
    if elongation < 180.0:
        factors.append(
            _factor(
                "moon_waxing", "favorable", 8, "月亮渐盈：利于开端、生长、推进之事。"
            )
        )
    else:
        factors.append(
            _factor(
                "moon_waning",
                "adverse",
                -6,
                "月亮渐亏：利于收束/了结之事，不利新的开端。",
            )
        )

    if _angular_gap(moon["longitude"], sun["longitude"]) <= COMBUST_ORB:
        factors.append(
            _factor(
                "moon_combust",
                "adverse",
                -12,
                f"月亮焦伤（距日 ≤{COMBUST_ORB}°），力弱受蔽。",
            )
        )

    if 195.0 <= moon["longitude"] <= 225.0:
        factors.append(
            _factor(
                "moon_via_combusta",
                "adverse",
                -8,
                "月亮行经燃烧之路（天秤15°–天蝎15°），不稳。",
            )
        )

    # --- Malefics / benefics on the angles ---------------------------------
    for planet in MALEFICS:
        view = views[planet]
        if (
            min(
                _angular_gap(view["longitude"], asc_lon),
                _angular_gap(view["longitude"], mc_lon),
            )
            <= ANGLE_ORB
        ):
            factors.append(
                _factor(
                    f"malefic_on_angle_{planet.lower()}",
                    "adverse",
                    -12,
                    f"{planet_label(planet)}临角宫（上升/天顶），冲犯举事，宜避。",
                    hard=True,
                )
            )
    for planet in BENEFICS:
        view = views[planet]
        if (
            min(
                _angular_gap(view["longitude"], asc_lon),
                _angular_gap(view["longitude"], mc_lon),
            )
            <= ANGLE_ORB
        ):
            factors.append(
                _factor(
                    f"benefic_on_angle_{planet.lower()}",
                    "favorable",
                    10,
                    f"{planet_label(planet)}临角宫（上升/天顶），庇佑举事。",
                )
            )

    # --- Mercury retrograde -------------------------------------------------
    if views["Mercury"]["retrograde"]:
        factors.append(
            _factor(
                "mercury_retrograde",
                "adverse",
                -15 if topic["mercury_hard"] else -6,
                "水星逆行：契约/交易/沟通类用事大忌；其余用事亦宜审慎复核。",
                hard=topic["mercury_hard"],
            )
        )

    # --- Ascendant ruler condition -----------------------------------------
    asc_ruler = RULER_BY_SIGN[asc_sign]
    asc_ruler_dignity = views[asc_ruler]["dignity"]
    if asc_ruler_dignity in ("rulership", "exaltation"):
        factors.append(
            _factor(
                "ascendant_ruler_strong",
                "favorable",
                8,
                f"命主{planet_label(asc_ruler)}得位（{asc_ruler_dignity}），举事根基稳。",
            )
        )
    elif asc_ruler_dignity in ("detriment", "fall"):
        factors.append(
            _factor(
                "ascendant_ruler_weak",
                "adverse",
                -8,
                f"命主{planet_label(asc_ruler)}失势（{asc_ruler_dignity}），举事根基弱。",
            )
        )

    # --- Topic significator condition --------------------------------------
    significator = topic["significator"]
    sig_view = views[significator]
    sig_dignity = sig_view["dignity"]
    if sig_dignity in ("rulership", "exaltation"):
        factors.append(
            _factor(
                "significator_strong",
                "favorable",
                10,
                f"用事星{planet_label(significator)}得位（{sig_dignity}），所求之事有力。",
            )
        )
    elif sig_dignity in ("detriment", "fall"):
        factors.append(
            _factor(
                "significator_weak",
                "adverse",
                -10,
                f"用事星{planet_label(significator)}失势（{sig_dignity}），所求之事受阻。",
            )
        )
    if sig_view["retrograde"] and significator != "Mercury":
        factors.append(
            _factor(
                "significator_retrograde",
                "adverse",
                -6,
                f"用事星{planet_label(significator)}逆行，事多反复。",
            )
        )

    score = max(0, min(100, BASE_SCORE + sum(f["weight"] for f in factors)))
    has_hard_block = any(f["hard"] and f["polarity"] == "adverse" for f in factors)
    verdict, recommendation = _verdict(score, has_hard_block, topic["label"])

    return {
        "system": "election",
        "system_label": "择日（电选）",
        "topic_id": topic_id,
        "topic_label": topic["label"],
        "topic_house": topic["house"],
        "significator": significator,
        "significator_label": planet_label(significator),
        "ascendant": {
            "sign": asc_sign,
            "sign_label": sign_label(asc_sign),
            "ruler": asc_ruler,
            "ruler_label": planet_label(asc_ruler),
            "ruler_dignity": asc_ruler_dignity,
        },
        "moon": {
            "sign": moon["sign"],
            "sign_label": sign_label(moon["sign"]),
            "void_of_course": moon_voc,
            "phase": "waxing" if elongation < 180.0 else "waning",
        },
        "score": score,
        "has_hard_block": has_hard_block,
        "verdict": verdict,
        "recommendation": recommendation,
        "factors": factors,
    }


def _moon_void_of_course(moon: Dict[str, Any], others: List[Dict[str, Any]]) -> bool:
    """The Moon makes no applying Ptolemaic aspect before leaving its sign."""
    degrees_left = 30.0 - (moon["longitude"] % 30.0)
    aspects = (0.0, 60.0, 90.0, 120.0, 180.0)
    moon_lon, moon_speed = moon["longitude"], moon["speed"]
    for other in others:
        gap = _angular_gap(moon_lon, other["longitude"])
        for angle in aspects:
            orb = abs(gap - angle)
            if orb > 12.0:
                continue
            # Applying if the gap to exact shrinks as the (faster) Moon advances.
            future_gap = _angular_gap(
                moon_lon + moon_speed * 0.05, other["longitude"] + other["speed"] * 0.05
            )
            if abs(future_gap - angle) < orb and orb <= degrees_left:
                return False
    return True


def _verdict(score: int, has_hard_block: bool, topic_label: str) -> tuple[str, str]:
    if has_hard_block:
        return (
            "avoid",
            f"存在择日大忌（红线），不宜以此刻起{topic_label}之事；建议另择良辰。",
        )
    if score >= 75:
        return ("auspicious", f"此刻于{topic_label}之事颇为有利，可用。")
    if score >= 55:
        return (
            "workable",
            f"此刻于{topic_label}之事中平可用，留意下方扣分项稍作规避。",
        )
    if score >= 40:
        return ("marginal", f"此刻于{topic_label}之事偏弱，能避则避、能等则等。")
    return ("avoid", f"此刻于{topic_label}之事多有妨碍，不建议起事。")


__all__ = [
    "TOPIC_MASTER",
    "BENEFICS",
    "MALEFICS",
    "build_election_payload",
]
