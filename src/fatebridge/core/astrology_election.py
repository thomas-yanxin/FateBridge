"""
FateBridge 择日 (electional astrology) engine.

Electional astrology evaluates whether a *candidate moment* is auspicious for
beginning a chosen undertaking. Unlike horary (which answers a question), the
chart is cast for the time being judged, and the topic (``topic_id``) selects
which house + significator matter and which strictures are red lines.

The engine applies an explicitly uncalibrated product scoring policy to
geometric/traditional conditions. This is not a complete original-text method.

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

import math
from fractions import Fraction
from typing import Any, Dict, List

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
from fatebridge.core.astrology_tables import EXALTATION_SIGNS, RULER_BY_SIGN, SIGNS
from fatebridge.core.classical_western import combustion_state, solar_condition_policy
from fatebridge.core.horary_motion import native_lunar_contacts
from fatebridge.core.predictive._common import (
    planet_label,
    point_absolute_position,
    sign_label,
)

BENEFICS = ("Venus", "Jupiter")
MALEFICS = ("Mars", "Saturn")
ANGLE_ORB = 5.0  # a planet within this of the Asc/MC degree counts as "on the angle"

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


def _planet_view(subject: Any, planet: str) -> Dict[str, Any]:
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
        "dignity_scope": "sign_only_major_dignity; triplicity_term_face_and_peregrine_not_classified",
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
    backend_asc = normalize_angle(point_absolute_position(subject, "Ascendant"))
    unresolved_reference = unresolved_ascendant(subject)
    asc_lon = None if unresolved_reference else backend_asc
    mc_lon = normalize_angle(point_absolute_position(subject, "Medium_Coeli"))
    asc_sign = None if asc_lon is None else SIGNS[int(Fraction(asc_lon) // 30)]
    backend_sign = SIGNS[int(Fraction(backend_asc) // 30)]
    backend_reference_factors: List[Dict[str, Any]] = []

    factors: List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []

    # --- The Moon: the soul of any election --------------------------------
    motion = (
        native_lunar_contacts(subject)
        if getattr(subject, "julian_day_tt", None) is not None
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
                "minimum_weight": -25,
                "maximum_weight": 0,
                "may_be_hard": True,
                "reason": "Native before-ingress event condition is unknown",
            }
        )
    if moon_voc is True:
        factors.append(
            _factor(
                "moon_void_of_course",
                "adverse",
                -25,
                "原生搜索在月亮下一星座界前未找到严格未来主相位；按本评分约定计-25并列硬限制。此操作定义不直接证明现实事情无果。",
                hard=True,
            )
        )

    elongation = (Fraction(moon["longitude"]) - Fraction(sun["longitude"])) % 360
    phase = (
        "new"
        if elongation == 0
        else "full" if elongation == 180 else "waxing" if elongation < 180 else "waning"
    )
    if elongation < 180.0:
        factors.append(
            _factor(
                "moon_waxing",
                "favorable",
                8,
                "月亮处于新月至满月的[0,180°)半周；本评分约定计+8。精确新月另标new，不当作已经渐盈，也不证明现实开端有利。",
            )
        )
    else:
        factors.append(
            _factor(
                "moon_waning",
                "adverse",
                -6,
                "月亮处于满月至新月的[180,360°)半周；本评分约定计-6。精确满月另标full，不当作已经渐亏，也不证明现实开端不利。",
            )
        )

    solar_state = combustion_state(moon["longitude"], sun["longitude"])
    if solar_state == "combust":
        factors.append(
            _factor(
                "moon_combust",
                "adverse",
                -12,
                "按Lilly1647第113页所选定义，月亮同星座内距日<8.5°且不在日心区间；按本评分约定计-12。纬度、掩食与完整择日效力另需核验。",
            )
        )

    if Fraction(195) <= Fraction(moon["longitude"]) <= Fraction(225):
        factors.append(
            _factor(
                "moon_via_combusta",
                "adverse",
                -8,
                "月亮黄经在本评分声明的[195°,225°]区间，按约定计-8；此标签不是现实不稳定的证据。",
            )
        )

    # --- Malefics / benefics on the angles ---------------------------------
    for planets, kind, weight, hard in [
        (MALEFICS, "malefic", -12, True),
        (BENEFICS, "benefic", 10, False),
    ]:
        for planet in planets:
            view = views[planet]
            code = f"{kind}_on_angle_{planet.lower()}"
            mc_holds = angular_separation_fraction(
                view["longitude"], mc_lon
            ) <= Fraction(ANGLE_ORB)
            asc_holds = (
                None
                if asc_lon is None
                else angular_separation_fraction(view["longitude"], asc_lon)
                <= Fraction(ANGLE_ORB)
            )
            holds = True if mc_holds else asc_holds
            detail = (
                f"{planet_label(planet)}黄经距物理ASC或MC≤{ANGLE_ORB}°；本评分计-12并列硬限制。黄经接近不等同实际落角宫。"
                if hard
                else f"{planet_label(planet)}黄经距物理ASC或MC≤{ANGLE_ORB}°；本评分计+10。黄经接近不等同实际落角宫或现实庇佑。"
            )
            if holds is True:
                factor = _factor(
                    code, "adverse" if hard else "favorable", weight, detail, hard=hard
                )
                if unresolved_reference:
                    factor["detail"] = (
                        f"{planet_label(planet)}与已解析MC的黄经接近满足本项；ASC未知不抹去这个已知或条件，仍只计一次。"
                        + detail
                    )
                    factor["resolved_hit_axes"] = ["Midheaven"]
                factors.append(factor)
            elif holds is None:
                unresolved.append(
                    {
                        "code": code,
                        "minimum_weight": min(0, weight),
                        "maximum_weight": max(0, weight),
                        "may_be_hard": hard,
                        "reason": "No MC hit; unresolved physical ASC leaves the grouped ASC-or-MC condition unknown, not false",
                    }
                )
            if unresolved_reference and (
                mc_holds
                or angular_separation_fraction(view["longitude"], backend_asc)
                <= Fraction(ANGLE_ORB)
            ):
                backend_reference_factors.append(
                    _factor(
                        code,
                        "adverse" if hard else "favorable",
                        weight,
                        detail,
                        hard=hard,
                    )
                )

    # --- Mercury retrograde -------------------------------------------------
    if views["Mercury"]["retrograde"] is None:
        unresolved.append(
            {
                "code": "mercury_retrograde",
                "minimum_weight": -15 if topic["mercury_hard"] else -6,
                "maximum_weight": 0,
                "may_be_hard": topic["mercury_hard"],
                "reason": "Mercury speed is unknown, not zero",
            }
        )
    if views["Mercury"]["retrograde"] is True:
        factors.append(
            _factor(
                "mercury_retrograde",
                "adverse",
                -15 if topic["mercury_hard"] else -6,
                "水星实际黄经速度为负；按本评分的主题约定扣分，契约／交易类另列硬限制。它不是现实失败概率。",
                hard=topic["mercury_hard"],
            )
        )

    # --- Ascendant ruler condition -----------------------------------------
    asc_ruler = None if asc_sign is None else RULER_BY_SIGN[asc_sign]
    asc_ruler_dignity = None if asc_ruler is None else views[asc_ruler]["dignity"]
    if unresolved_reference:
        unresolved.append(
            {
                "code": "ascendant_ruler_condition",
                "minimum_weight": -8,
                "maximum_weight": 8,
                "may_be_hard": False,
                "reason": "Unresolved ASC cannot select its ruler; strong/weak alternatives are mutually exclusive, not zero",
            }
        )
        nominal_ruler = RULER_BY_SIGN[backend_sign]
        nominal_dignity = views[nominal_ruler]["dignity"]
        if nominal_dignity in {"rulership", "exaltation", "detriment", "fall"}:
            strong = nominal_dignity in {"rulership", "exaltation"}
            backend_reference_factors.append(
                _factor(
                    "ascendant_ruler_strong" if strong else "ascendant_ruler_weak",
                    "favorable" if strong else "adverse",
                    8 if strong else -8,
                    "Backend numerical ASC convention only; not an actual ruler selection",
                )
            )
    if asc_ruler is not None and asc_ruler_dignity in ("rulership", "exaltation"):
        factors.append(
            _factor(
                "ascendant_ruler_strong",
                "favorable",
                8,
                f"上升主星{planet_label(asc_ruler)}的星座级状态为{asc_ruler_dignity}，本评分计+8。",
            )
        )
    elif asc_ruler is not None and asc_ruler_dignity in ("detriment", "fall"):
        factors.append(
            _factor(
                "ascendant_ruler_weak",
                "adverse",
                -8,
                f"上升主星{planet_label(asc_ruler)}的星座级状态为{asc_ruler_dignity}，本评分计-8。",
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
                f"用事星{planet_label(significator)}的星座级状态为{sig_dignity}，本评分计+10。",
            )
        )
    elif sig_dignity in ("detriment", "fall"):
        factors.append(
            _factor(
                "significator_weak",
                "adverse",
                -10,
                f"用事星{planet_label(significator)}的星座级状态为{sig_dignity}，本评分计-10。",
            )
        )
    if sig_view["retrograde"] is None and significator != "Mercury":
        unresolved.append(
            {
                "code": "significator_retrograde",
                "minimum_weight": -6,
                "maximum_weight": 0,
                "may_be_hard": False,
                "reason": "Significator speed is unknown, not zero",
            }
        )
    if sig_view["retrograde"] is True and significator != "Mercury":
        factors.append(
            _factor(
                "significator_retrograde",
                "adverse",
                -6,
                f"用事星{planet_label(significator)}实际黄经速度为负；本评分计-6，不能据此断言现实反复。",
            )
        )

    scoring = _score_with_unknowns(factors, unresolved, topic["label"])

    payload: Dict[str, Any] = {
        "system": "election",
        "system_label": "择日（电选）",
        "topic_id": topic_id,
        "topic_label": topic["label"],
        "topic_house": topic["house"],
        "significator": significator,
        "significator_label": planet_label(significator),
        "dignity_scope": views["Moon"]["dignity_scope"],
        "planets": views,
        "calculation_basis": getattr(subject, "calculation_basis", None),
        "axes": {
            "ascendant_longitude": asc_lon,
            "midheaven_longitude": mc_lon,
            "first_house_cusp": normalize_angle(float(subject.first_house.abs_pos)),
            "tenth_house_cusp": normalize_angle(float(subject.tenth_house.abs_pos)),
            "policy": "Named physical ASC/MC, never house1/10 substitutes; longitude proximity to these two axes only, not mundane angularity or all four angles",
        },
        "solar_condition_policy": solar_condition_policy(),
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
            "longitude": moon["longitude"],
            "phase": phase,
            "elongation_degrees": longitude_float(elongation),
            "solar_condition": solar_state,
            "motion_basis": motion,
        },
        **scoring,
        "factors": factors,
        "unresolved_factors": unresolved,
        "scoring_policy": {
            "rule_id": "election_legacy_weights_observed_conditions_v2",
            "base_score": BASE_SCORE,
            "weights_and_band_boundaries_changed": False,
            "scope": "Custom fixed-weight calculation only; unknown predicates yield score bounds, not assumed zero. Numeric score/bands are not probability, full classical judgement or empirical validation",
            "full_original_text_acceptance": False,
            "empirically_calibrated": False,
            "moon_operational_policy": "Strict future longitude perfection before ingress; p112 apply/forthwith/orb textual equivalence remains open",
            "solar_rule": "Lilly1647 p113 selected longitude definitions, printed10-degree contradiction retained",
            "phase_weight_policy": "Legacy+8 on[0,180),-6 on[180,360); exact new/full separately labeled; not full election doctrine",
        },
    }
    if unresolved_reference:
        angular_codes = {
            f"{kind}_on_angle_{p.lower()}"
            for kind, names in [("malefic", MALEFICS), ("benefic", BENEFICS)]
            for p in names
        }
        reference_codes = angular_codes | {
            "ascendant_ruler_strong",
            "ascendant_ruler_weak",
            "ascendant_ruler_condition",
        }
        backend_scoring = _score_with_unknowns(
            [f for f in factors if f["code"] not in reference_codes]
            + backend_reference_factors,
            [u for u in unresolved if u["code"] not in reference_codes],
            topic["label"],
        )
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
            **backend_scoring,
        }
        if unresolved_houses(subject):
            payload["planets"] = {p: {**v, "house": None} for p, v in views.items()}
            payload["axes"]["first_house_cusp"] = None
            payload["axes"]["tenth_house_cusp"] = None
        payload["reference_geometry"] = reference_qualification(subject)
        payload["recommendation"] = (
            "ASC参考几何未解析；保留独立星体与MC条件及声明权重范围，不把后端约定主星或范围当作实际成事概率。"
            + payload["recommendation"]
        )
    return payload


def _score_with_unknowns(
    factors: List[Dict[str, Any]], unresolved: List[Dict[str, Any]], label: str
) -> Dict[str, Any]:
    raw = BASE_SCORE + sum(f["weight"] for f in factors)
    clamp = lambda value: max(0, min(100, value))
    known_hard = any(f["hard"] and f["polarity"] == "adverse" for f in factors)
    hard = (
        True
        if known_hard
        else None if any(f["may_be_hard"] for f in unresolved) else False
    )
    bounds = [
        clamp(raw + sum(f[key] for f in unresolved))
        for key in ("minimum_weight", "maximum_weight")
    ]
    score = None if unresolved else clamp(raw)
    if unresolved:
        verdict = "avoid" if known_hard else "incomplete"
        recommendation = (
            "按本评分约定已有确定的硬限制，且仍有未核算条件。"
            if known_hard
            else "仍有未核算条件，不能给出完整评分或吉利结论。"
        )
    else:
        verdict, recommendation = _verdict(clamp(raw), bool(hard), label)
    return {
        "score": score,
        "score_bounds": bounds,
        "has_hard_block": hard,
        "verdict": verdict,
        "recommendation": recommendation,
        "score_evidence": {
            "status": "partial" if unresolved else "complete_for_declared_weights",
            "base_score": BASE_SCORE,
            "known_contribution": raw - BASE_SCORE,
            "raw_known_subtotal": raw,
            "missing_factor_codes": [f["code"] for f in unresolved],
            "bounds_scope": "Bounds over declared unresolved contributions only; no confidence interval or outcome probability",
        },
    }


def _verdict(score: int, has_hard_block: bool, topic_label: str) -> tuple[str, str]:
    if has_hard_block:
        return (
            "avoid",
            f"按本评分约定，{topic_label}候选包含已算出的硬限制；这不是现实成败预测。",
        )
    if score >= 75:
        return (
            "auspicious",
            f"按本评分约定，{topic_label}候选落在≥75分档；未据此验证现实有利或成功率。",
        )
    if score >= 55:
        return (
            "workable",
            f"按本评分约定，{topic_label}候选落在55–74分档；结合实际条件评估，不能把分档当成事情可成。",
        )
    if score >= 40:
        return (
            "marginal",
            f"按本评分约定，{topic_label}候选落在40–54分档；不代表现实障碍已被证实。",
        )
    return (
        "avoid",
        f"按本评分约定，{topic_label}候选低于40分；不据此单独决定现实行动。",
    )


__all__ = [
    "TOPIC_MASTER",
    "BENEFICS",
    "MALEFICS",
    "build_election_payload",
]
