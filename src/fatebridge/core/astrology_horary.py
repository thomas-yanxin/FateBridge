"""
FateBridge 卜卦 (horary) judgment engine.

The chart belongs to the question's recorded instant. Native TT motion supplies
lunar sign-exit events and finite seven-planet histories. Instantaneous geometry,
event-epoch reception, named source conditions and complete judgement retain
distinct verification states. Legacy verdicts remain research output while
complete source event variants, house and accidental conditions are unverified.
The explicit source scope is Lilly's 1647 edition, not an entire-school claim.
"""

from __future__ import annotations

import math
from fractions import Fraction
from functools import partial
from typing import Any, Dict, List, Optional, Tuple

from fatebridge.core.astro.event_reference import (
    reference_qualification,
    unresolved_ascendant,
    unresolved_houses,
)
from fatebridge.core.astro.geometry import angular_separation_fraction, normalize_angle
from fatebridge.core.astrology_tables import RULER_BY_SIGN, SIGNS
from fatebridge.core.classical_western import _aspect_phase
from fatebridge.core.horary_conditions import evaluate_lilly_conditions
from fatebridge.core.horary_events import native_planetary_events
from fatebridge.core.horary_motion import linear_lunar_contacts, native_lunar_contacts
from fatebridge.core.lilly import dignity_at, pair_reception
from fatebridge.core.lilly_fortitude_inputs import collect_fortitude_inputs
from fatebridge.core.lilly_fortitudes import evaluate_fortitudes
from fatebridge.core.lilly_fortune import evaluate_fortune
from fatebridge.core.lilly_house_assignment import assign_from_cusps, subject_cusps
from fatebridge.core.lilly_houses import house_condition
from fatebridge.core.lilly_orbs import (
    DEFAULT_ORB_PROFILE,
    full_orbs,
    orb_receipt,
    pair_radius,
)
from fatebridge.core.lilly_radicality import evaluate_radicality
from fatebridge.core.lilly_radicality_inputs import collect_radicality_hour
from fatebridge.core.lilly_rays import METHOD_ID as LILLY_SIGN_RAYS_METHOD
from fatebridge.core.lilly_rays import (
    describe_sign_relationship,
    directed_sign_relationship,
)
from fatebridge.core.predictive._common import (
    house_number,
    normalize_sign_name,
    planet_label,
    point_absolute_position,
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

# Historical public symbol retained for compatibility; these are FULL orbs,
# not moieties. Request-local profile selection never mutates this alias.
PLANET_MOIETIES: Dict[str, float] = full_orbs()

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


def _aspect_orb(
    planet_a: str, planet_b: str, orb_profile: str = DEFAULT_ORB_PROFILE
) -> float:
    return float(pair_radius(planet_a, planet_b, orb_profile))


def _planet_state(subject: Any, planet: str) -> Dict[str, Any]:
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


def _chart_sect(subject: Any) -> Optional[str]:
    value = getattr(subject, "is_diurnal", None)
    return "day" if value is True else "night" if value is False else None


def _degree_aspect_candidate(
    state_a: Dict[str, Any],
    state_b: Dict[str, Any],
    *,
    orb_profile: str = DEFAULT_ORB_PROFILE,
) -> Optional[Dict[str, Any]]:
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
    state_a: Dict[str, Any],
    state_b: Dict[str, Any],
    *,
    orb_profile: str = DEFAULT_ORB_PROFILE,
) -> Optional[Dict[str, Any]]:
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


def _reception_labels(
    state_a: Dict[str, Any], state_b: Dict[str, Any], sect: Optional[str]
) -> List[str]:
    pair = pair_reception(
        state_a["planet"],
        state_a["longitude"],
        state_b["planet"],
        state_b["longitude"],
        sect,
    )
    labels = {
        "rulership": "庙",
        "exaltation": "旺",
        "triplicity": "三分",
        "bound": "界",
        "face": "面",
    }
    return [
        f"{planet_label(row['receiver'])}以{'、'.join(labels[k] for k in row['dignities'])}纳{planet_label(row['guest'])}"
        for row in pair["directions"]
        if row["receives"] is True
    ]


def _house_sign(subject: Any, house_number: int) -> str:
    cusp = getattr(subject, HOUSE_ATTRIBUTES[house_number - 1])
    return normalize_sign_name(getattr(cusp, "sign", ""))


def _moon_void_of_course(
    moon_state: Dict[str, Any],
    other_states: List[Dict[str, Any]],
    *,
    physical_motion: Optional[Dict[str, Any]] = None,
    orb_profile: str = DEFAULT_ORB_PROFILE,
) -> Dict[str, Any]:
    """
    The Moon is void of course if it completes no applying Ptolemaic aspect to a
    traditional planet before leaving its current sign. Returns the next aspect
    (if any) so the service can explain the judgment.
    """
    others = {state["planet"]: state for state in other_states}
    if physical_motion is None:
        try:
            physical_motion = linear_lunar_contacts(moon_state, others)
        except ValueError as error:
            physical_motion = {
                "status": "unavailable",
                "method_id": "linear_signed_velocity_projection_v1",
                "constant_velocity_projection": True,
                "void_of_course": None,
                "contacts": [],
                "unavailable_reason": str(error),
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
    next_aspect = next(iter(physical_motion["contacts"]), None)
    return {
        "void_of_course": physical_motion["void_of_course"],
        "degrees_left_in_sign": physical_motion.get("degrees_left_in_sign"),
        "next_aspect": next_aspect,
        "motion_basis": physical_motion,
    }


def build_horary_payload(
    subject: Any,
    *,
    category: str,
    orb_profile: str = DEFAULT_ORB_PROFILE,
    radicality_context: Optional[Dict[str, Any]] = None,
    clock_basis: str = "civil",
) -> Dict[str, Any]:
    """
    Judge a horary chart for ``category``. Returns significators, radicality
    strictures, the perfection finding, and an overall verdict with reasoning.
    """
    if category not in HOUSE_BY_CATEGORY:
        raise ValueError("不支持的卜卦类别；生死与临床判断不开放")
    selected_orbs = orb_receipt(orb_profile)  # Validate before any event search.
    phase = partial(_applying_aspect, orb_profile=orb_profile)
    quesited_house = HOUSE_BY_CATEGORY[category]

    states = {planet: _planet_state(subject, planet) for planet in TRADITIONAL_PLANETS}
    fortitudes = evaluate_fortitudes(
        states,
        _chart_sect(subject),
        collect_fortitude_inputs(subject),
        house_system=getattr(subject, "houses_system_identifier", None),
        zodiac_type=getattr(subject, "zodiac_type", None),
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

    # --- Moon void of course ----------------------------------------------
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
    strictures = radicality["strictures"]

    # --- Perfection --------------------------------------------------------
    perfection = _judge_perfection(
        querent_state,
        quesited_state,
        moon_state,
        states,
        querent_planet,
        quesited_planet,
        chart_sect=_chart_sect(subject),
        orb_profile=orb_profile,
    )

    heuristic_verdict, heuristic_reasoning = _verdict(
        perfection, moon_voc, strictures, category
    )
    # A present-tense aspect is not proof of a future or a full Lilly judgement.
    perfection["heuristic_perfection_signal"] = perfection["perfects"]
    perfection["candidate"] = (
        bool(perfection["perfects"]) and perfection["mode"] != "same_ruler"
    )
    perfection["candidate_scope"] = (
        "selected_orb_profile_instantaneous_geometric_proxy_only; p112_reciprocal_reception_support_is_reported_separately"
    )
    perfection["perfects"] = None
    perfection["status"] = (
        "same_ruler_insufficient"
        if perfection["mode"] == "same_ruler"
        else (
            "instantaneous_candidate_unverified"
            if perfection["candidate"]
            else "no_route_in_instantaneous_model"
        )
    )
    perfection["missing_conditions"] = [
        "source_interpretation_of_required_reception_epochs",
        "full_event_horizon_and_continuous_interval_completeness",
        "remaining_prohibition_refranation_frustration_variants",
        "remaining_source_specific_house_accidental_and_transfer_conditions",
    ]
    event_history = native_planetary_events(subject)
    perfection["event_history"] = event_history
    perfection["lilly_conditions"] = evaluate_lilly_conditions(
        states,
        querent_planet,
        quesited_planet,
        _chart_sect(subject),
        phase,
        lunar_motion=motion,
        zodiac_type=getattr(subject, "zodiac_type", None),
        event_history=event_history,
    )
    verdict = "uncertain"
    if event_history["status"] == "computed":
        reasoning = "已按Lilly1647指定表计算本质尊贵、有向接纳、双列可选容许度和实际落宫，并实际追踪提问前后各30天七曜成相、入宫及停滞折返；主星历史分离与传光星历史分离分别核对，接纳保留相应事件历元。尚未完成Lilly全部阻碍变体、原典宫位与偶然条件，有限扫描和指定坐标系的事件也不等于现实成败。"
    else:
        reasoning = "已按Lilly1647指定表计算本质尊贵、有向接纳、双列可选容许度、实际落宫和逐项条件；七曜实际事件历史当前不可用，主星与传光星的历史分离及后续成相均不能核定；不能把未知当作没有阻碍。尚未完成Lilly全部宫位与偶然条件，不能由此确认事情成败。"
    reasoning += (
        " 第115页41行尊贵／减损表另有逐星回执，快慢按24小时位移、顺逆按瞬时方向，日月不计顺行奖励。"
        + (
            "本次各行已在声明政策下核算；"
            if all(not p["unknown_rows"] for p in fortitudes["summary"].values())
            else "本次未核定行保留未知，完整余额为空；"
        )
        + "逐行累计尚不能复现全部原书例题总计，不能当作完整原典判断。"
    )
    reasoning += " 宫头五度效力归属与几何落宫分别回执；福点按Lilly昼夜同式计算，第145页独立表保留28项（含白羊零分行），不套用七曜的第六／八宫减分。原书超五度归宫及福点累计差异仍未解决，余额不能作为现实成败结论。"
    reasoning += " 起盘审慎段落另有12项逐条核对，时主对应、上升区间、例外及待核定义分别保留；原先只看上升度数的整体可判断标记改为未认证，不能由未见某条提示推定可作确定预测。"

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
    reasoning += " " + describe_sign_relationship(
        sign_relationship, planet_label(querent_planet), planet_label(quesited_planet)
    )

    payload = {
        "system": "horary",
        "system_label": "卜卦判断",
        "category": category,
        "category_label": CATEGORY_LABELS_ZH[category],
        "quesited_house": quesited_house,
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
        "radicality": radicality,
        "moon": {
            "sign": moon_state["sign"],
            "sign_label": moon_state["sign_label"],
            "speed": moon_state["speed"],
            **moon_voc,
        },
        "perfection": perfection,
        "verdict": verdict,
        "reasoning": reasoning,
        "heuristic_verdict": heuristic_verdict,
        "heuristic_reasoning": f"按所选容许度的瞬时几何研究代理给出 {heuristic_verdict}，所用条件为『{perfection['mode_label']}』；该代理未完成原典成事条件核验，仅作研究比较。",
        "rule_profile": {
            "rule_id": "horary_lilly_consideration_review_v9",
            "sign_relationship_policy": LILLY_SIGN_RAYS_METHOD,
            "source_edition": "William Lilly, Christian Astrology, London 1647",
            "source_url": "https://wellcomecollection.org/works/s7z7c46y",
            "chapter_pages": [
                33,
                48,
                50,
                57,
                61,
                65,
                69,
                72,
                76,
                80,
                104,
                105,
                106,
                107,
                108,
                109,
                110,
                111,
                112,
                113,
                114,
                115,
                121,
                122,
                123,
                125,
                126,
                127,
                143,
                144,
                145,
                154,
                177,
                178,
                179,
                180,
                181,
            ],
            "full_original_text_acceptance": False,
            "instantaneous_phase": "instantaneous_longitude_phase_v1",
            "orb_policy": "Selected Lilly1647 p107 full-orb column; half-sum pair radius, explicit closed equality convention",
            "orb_table": selected_orbs,
            "moon_policy": "strict_future_longitude_contacts_before_next_lunar_ingress; apply/orb textual variants remain explicit",
            "judgement_status": "source_conditions_incomplete",
            "essential_dignity_policy": "Lilly1647 pp104-105 selected printed seven-planet table; sect-specific triplicity, Mars both sects in water, explicit half-open endpoints; not Robbins1940 or the eclectic Egyptian/Dorothean layer",
            "house_axis_policy": "Physical named ASC determines querent/house1 identity and strictures; other topic houses retain selected cusps. Non-Regiomontanus source-method extensions remain unverified",
            "fortitudes_policy": "All41 literal p115 rows with explicit applicability/unknowns, forward TT-day displacement, dated stellar positions and retained worked-example conflicts; no complete original-method acceptance or verdict override",
            "cusp_virtue_policy": "p33 nearest cusp within five degrees, separate from geometric occupancy; declared closed equality, tied cusps unknown, reversed partitions unavailable; p180 beyond-five-degree exception not fitted",
            "fortune_policy": "Lilly pp143-144 ASC+Moon-Sun day and night, physical ASC; complete p145 printed28-row ledger under explicit aspect/stellar/solar conventions; unknowns and original-case conflicts retained",
            "radicality_policy": "Complete pp121-123 manual clause inventory, actual unequal-hour inputs, selected triplicity and own nature; reported exceptions and unresolved definitions separate; safe_to_judge unknown, not an ASC-only certificate",
        },
        "calculation_basis": getattr(subject, "calculation_basis", None),
    }
    if unresolved_ascendant(subject):
        _qualify_unresolved_reference(
            payload, subject, radicality_context=radicality_context
        )
    return payload


def _qualify_unresolved_reference(
    payload: Dict[str, Any],
    subject: Any,
    *,
    radicality_context: Optional[Dict[str, Any]],
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
            "heuristic_verdict",
            "heuristic_reasoning",
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
        "perfects": None,
        "candidate": None,
        "heuristic_perfection_signal": None,
        "mode": None,
        "status": "underdetermined_reference_geometry",
        "missing_conditions": ["physically_resolved_ascendant_and_querent_identity"],
        "event_history": backend["perfection"]["event_history"],
        "lilly_conditions": None,
    }
    payload["heuristic_verdict"] = None
    payload["heuristic_reasoning"] = (
        "ASC参考几何未解析，不能把后端约定主星代入瞬时成事代理。"
    )
    payload["reference_geometry"] = reference_qualification(subject)
    payload["backend_convention"] = backend
    payload["rule_profile"] = {
        **payload["rule_profile"],
        "judgement_status": "reference_geometry_unresolved",
    }
    payload["reasoning"] = (
        "本次黄道与地平交线未能解析唯一ASC，求问者主星、依赖ASC的福点和成事候选保持未知；"
        "后端数值约定另列，不能作为原典条件成立或不成立的依据。星体位置、MC和独立的月亮事件仍保留；"
        "依赖未定宫制参考的落宫行不计作已核定条件，独立定义的宫制事实不受此项直接限制。"
        "本质尊贵、接纳、月亮条款和各项已知事实按实际输入分别保留；未完成原典整盘判断及现实效力验证。"
    )


def _judge_perfection(
    querent_state: Dict[str, Any],
    quesited_state: Dict[str, Any],
    moon_state: Dict[str, Any],
    states: Dict[str, Dict[str, Any]],
    querent_planet: str,
    quesited_planet: str,
    *,
    chart_sect: Optional[str] = None,
    orb_profile: str = DEFAULT_ORB_PROFILE,
) -> Dict[str, Any]:
    """First instantaneous research proxy; not a future or original-text verdict."""
    phase = partial(_applying_aspect, orb_profile=orb_profile)
    receptions = _reception_labels(querent_state, quesited_state, chart_sect)

    # 1. Direct aspect between the two significators.
    if querent_planet != quesited_planet:
        direct = phase(querent_state, quesited_state)
        if direct is not None and direct["applying"]:
            return {
                "perfects": True,
                "mode": "direct",
                "mode_label": "当前两造主星黄经呈入相候选",
                "aspect": direct,
                "receptions": receptions,
            }
    else:
        return {
            "perfects": True,
            "mode": "same_ruler",
            "mode_label": "两造同主星（同一征象，不构成独立的成事证明）",
            "receptions": receptions,
        }

    # 2. Translation of light: a third (faster) planet separating from one
    #    significator and applying to the other.
    for planet, state in states.items():
        if planet in (querent_planet, quesited_planet):
            continue
        to_querent = phase(state, querent_state)
        to_quesited = phase(state, quesited_state)
        applies = [
            a for a in (to_querent, to_quesited) if a and a["phase"] == "applying"
        ]
        separates = [
            a for a in (to_querent, to_quesited) if a and a["phase"] == "separating"
        ]
        if (
            applies
            and separates
            and TRADITIONAL_PLANETS.index(planet)
            > max(
                TRADITIONAL_PLANETS.index(querent_planet),
                TRADITIONAL_PLANETS.index(quesited_planet),
            )
            and all(
                s["speed"] is not None for s in (state, querent_state, quesited_state)
            )
            and abs(state["speed"])
            > max(abs(querent_state["speed"]), abs(quesited_state["speed"]))
        ):
            return {
                "perfects": True,
                "mode": "translation",
                "mode_label": f"{state['planet_label']}当前黄经一端出相、一端入相（真实先后未验）",
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
            TRADITIONAL_PLANETS.index(planet)
            >= min(
                TRADITIONAL_PLANETS.index(querent_planet),
                TRADITIONAL_PLANETS.index(quesited_planet),
            )
            or any(s["speed"] is None for s in (state, querent_state, quesited_state))
            or not (
                abs(state["speed"]) < abs(querent_state["speed"])
                and abs(state["speed"]) < abs(quesited_state["speed"])
            )
        ):
            continue
        to_querent = phase(querent_state, state)
        to_quesited = phase(quesited_state, state)
        if (
            to_querent
            and to_querent["applying"]
            and to_quesited
            and to_quesited["applying"]
        ):
            return {
                "perfects": True,
                "mode": "collection",
                "mode_label": f"当前两造黄经均向{state['planet_label']}入相（接纳与未来成相未验）",
                "collector": state["planet"],
                "collector_label": state["planet_label"],
                "receptions": receptions,
            }

    # 4. The Moon (querent's co-significator) applies to the quesited significator.
    if quesited_planet != "Moon":
        moon_to_quesited = phase(moon_state, quesited_state)
        if moon_to_quesited is not None and moon_to_quesited["applying"]:
            return {
                "perfects": True,
                "mode": "moon",
                "mode_label": "月亮当前黄经向所问主星入相（完整条件未验）",
                "aspect": moon_to_quesited,
                "receptions": receptions,
            }

    return {
        "perfects": False,
        "mode": "none",
        "mode_label": "当前瞬时几何代理未找到候选路径",
        "receptions": receptions,
    }


def _verdict(
    perfection: Dict[str, Any],
    moon_voc: Dict[str, Any],
    strictures: List[Dict[str, Any]],
    category: str,
) -> Tuple[str, str]:
    """Boil the findings down to a verdict + a human-readable reasoning line."""
    stricture_codes = {
        s["code"] for s in strictures if s.get("exception_satisfied") is not True
    }
    too_early_or_late = stricture_codes & {"ascendant_too_early", "ascendant_too_late"}

    if too_early_or_late:
        return (
            "uncertain",
            "上升处于声明的早／晚度区间，本旧几何代理未确认该条例外时暂缓判断；完整原典可判断性仍未认证。",
        )

    if moon_voc["void_of_course"] is None:
        return "uncertain", "月亮出宫前事件未完成计算，不能把未知状态当成空亡或不空亡。"

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
        reception_note = f"，且有接纳（{'、'.join(receptions)}）" if receptions else ""
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
