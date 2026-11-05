"""Complete pp121-123 consideration inventory, with contextual unknowns.

This is a clause review, not a certified radicality verdict. Literal house
occupancy and p33 cusp virtue remain separate; the selected operational house
policy is explicit. No score or lack of a caution becomes a safe-to-judge proof.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core.astro.geometry import Angle, angle_fraction, longitude_float
from fatebridge.core.classical_western import combustion_state
from fatebridge.core.lilly import (
    DOMICILES,
    PLANETS,
    SIGNS,
    SOURCE_URL,
    TRIPLICITIES,
    dignity_at,
)

CLAUSES = (
    ("R01", "hour_lord_affinity", [121, 122]),
    ("C01", "early_ascendant_with_reported_exception", [122]),
    ("C02", "late_ascendant_with_reported_exceptions", [122]),
    ("C03", "moon_latter_degrees_unspecified_cutoff", [122]),
    ("C04", "via_combusta_attributed_variant", [122]),
    ("C05", "void_moon_with_strength_and_sign_qualifications", [122]),
    ("C06", "seventh_affliction_when_not_seventh_matter", [122]),
    ("C07", "saturn_in_ascendant_especially_retrograde", [122]),
    ("C08", "saturn_in_seventh_arabian_rule", [123]),
    ("C09", "ascendant_lord_combust", [123]),
    ("C10", "seventh_lord_unfortunate_fallen_or_malefic_bound", [123]),
    ("C11", "equal_fortune_infortune_testimonies", [123]),
)
OWN_NATURES = {
    "Saturn": ("cold", "dry", 58),
    "Jupiter": ("hot", "moist", 62),
    "Mars": ("hot", "dry", 66),
    "Sun": ("hot", "dry", 70),
    "Venus": ("cold", "moist", 73),
    "Mercury": ("cold", "dry", 77),
    "Moon": ("cold", "moist", 81),
}
SHORT_ASCENSION_PRINTED = (
    "Capricorn",
    "Aquarius",
    "Pisces",
    "Aries",
    "Taurus",
    "Gemini",
)
MOON_LATE_SPECIAL = ("Gemini", "Scorpio", "Capricorn")
VOC_SOME_PERFORMANCE = ("Taurus", "Cancer", "Sagittarius", "Pisces")
CONTEXT_FLAGS = (
    "very_young_querent_reported",
    "rising_description_agreement_reported",
    "age_degree_agreement_reported",
    "event_time_certain_reported",
    "principal_significators_very_strong_reported",
    "seventh_cusp_afflicted_reported",
    "seventh_lord_impeded_reported",
    "seventh_lord_unfortunate_reported",
    "equal_fortune_infortune_testimonies_reported",
)


def _all(values: list[bool | None]) -> bool | None:
    return False if False in values else None if None in values else True


def _any(values: list[bool | None]) -> bool | None:
    return True if True in values else None if None in values else False


def normalize_context(value: dict[str, Any] | None) -> dict[str, Any]:
    """Reports stay reports; no age, appearance or timed-event certainty inferred."""
    if value is not None and not isinstance(value, dict):
        raise ValueError("Radicality context must be an object or unknown")
    raw = value or {}
    if set(raw) - {*CONTEXT_FLAGS, "figure_origin"}:
        raise ValueError("Unknown radicality context field")
    for key in CONTEXT_FLAGS:
        if raw.get(key) is not None and type(raw[key]) is not bool:
            raise ValueError("Radicality reports must be booleans or unknown")
    origin = raw.get("figure_origin")
    if origin not in {None, "propounded_question", "timed_event", "unknown"}:
        raise ValueError("Invalid figure origin")
    return {
        "figure_origin": origin or "propounded_question",
        **{key: raw.get(key) for key in CONTEXT_FLAGS},
        "figure_origin_source": (
            "api_question_instant_default" if origin is None else "caller_report"
        ),
        "provided_fields": sorted(key for key, v in raw.items() if v is not None),
        "verification_scope": "Caller-reported context only; not independently verified or inferred from coordinates, scores, age or timestamp syntax",
    }


def hour_affinity(
    hour_ruler: str | None, ascendant: Angle | None, sect: str | None
) -> dict[str, Any]:
    if hour_ruler is not None and hour_ruler not in PLANETS:
        raise ValueError("Hour ruler must be a traditional planet or unknown")
    if sect not in {"day", "night", None}:
        raise ValueError("Invalid chart sect")
    sign_index = (
        None if ascendant is None else int((angle_fraction(ascendant) % 360) // 30)
    )
    lord = None if sign_index is None else DOMICILES[sign_index]
    listed = (
        [] if sign_index is None else list(dict.fromkeys(TRIPLICITIES[sign_index % 4]))
    )
    selected = (
        None
        if ascendant is None
        else dignity_at("Sun", ascendant, sect)["lords"]["triplicity"]
    )
    same = None if hour_ruler is None or lord is None else hour_ruler == lord
    trip = None if hour_ruler is None or selected is None else hour_ruler == selected
    nature = (
        None
        if hour_ruler is None or lord is None
        else OWN_NATURES[hour_ruler][:2] == OWN_NATURES[lord][:2]
    )
    return {
        "hour_ruler": hour_ruler,
        "ascendant_sign": None if sign_index is None else SIGNS[sign_index],
        "ascendant_lord": lord,
        "chart_sect": sect,
        "same_ruler": same,
        "ascendant_triplicity": trip,
        "same_own_nature": nature,
        "selected_triplicity_lord": selected,
        "listed_triplicity_lords": listed,
        "hour_ruler_in_any_listed_triplicity": (
            None if hour_ruler is None or sign_index is None else hour_ruler in listed
        ),
        "hour_ruler_own_nature": (
            None if hour_ruler is None else list(OWN_NATURES[hour_ruler][:2])
        ),
        "ascendant_lord_own_nature": (
            None if lord is None else list(OWN_NATURES[lord][:2])
        ),
        "supported_under_declared_policy": _any([same, trip, nature]),
        "triplicity_policy": "Selected sect-specific p104 lord; the either-listed-lord sensitivity is separate, p121 wording not exhaustively adjudicated",
        "nature_policy": "Own hot/cold and dry/moist qualities, not gender, benefic status, physical temperature or observer weather",
        "source_pages": [104, 121, 122]
        + ([] if hour_ruler is None else [OWN_NATURES[hour_ruler][2]])
        + ([] if lord is None else [OWN_NATURES[lord][2]]),
        "full_original_text_acceptance": False,
    }


def evaluate_radicality(
    ascendant: Angle | None,
    states: dict[str, dict[str, Any]],
    moon_voc: dict[str, Any],
    hour_inputs: dict[str, Any],
    *,
    seventh_sign: str | None,
    quesited_house: int,
    sect: str | None,
    context: dict[str, Any] | None = None,
    house_system: str | None = None,
    zodiac_type: str | None = None,
) -> dict[str, Any]:
    """All selected clauses retain prerequisites, exceptions and unresolved terms."""
    if quesited_house not in range(1, 13):
        raise ValueError("Quesited house must be1..12")
    if seventh_sign not in {*SIGNS, None}:
        raise ValueError("Seventh cusp sign must be known or unknown")
    reported = normalize_context(context)
    lon = None if ascendant is None else angle_fraction(ascendant) % 360
    degree = None if lon is None else lon % 30
    asc_sign = None if lon is None else SIGNS[int(lon // 30)]
    asc_lord = None if lon is None else DOMICILES[int(lon // 30)]
    seventh_lord = (
        None if seventh_sign is None else DOMICILES[SIGNS.index(seventh_sign)]
    )
    positions = {
        p: None if s.get("longitude") is None else angle_fraction(s["longitude"]) % 360
        for p, s in states.items()
    }
    moon = positions.get("Moon")
    moon_sign = None if moon is None else SIGNS[int(moon // 30)]
    affinity = hour_affinity(
        (hour_inputs.get("hour") or {}).get("hour_ruler"), lon, sect
    )
    early = None if degree is None else degree < 3
    late = None if degree is None else degree >= 27
    early_exception = _all(
        [
            reported["very_young_querent_reported"],
            reported["rising_description_agreement_reported"],
        ]
    )
    origin = reported["figure_origin"]
    event_exception = _all(
        [
            None if origin == "unknown" else origin == "timed_event",
            reported["event_time_certain_reported"],
        ]
    )
    late_exception = _any([reported["age_degree_agreement_reported"], event_exception])
    voc = moon_voc.get("void_of_course")
    if voc is not None and type(voc) is not bool:
        raise ValueError("Moon VOC must be a boolean or unknown")
    via = None if moon is None else 195 <= moon < 225
    moon_sign_qualification = (
        None if moon_sign is None else moon_sign in VOC_SOME_PERFORMANCE
    )
    seventh_state = states.get(seventh_lord, {}) if seventh_lord is not None else {}
    retro = seventh_state.get("retrograde")
    if retro is None and seventh_state.get("speed") is not None:
        speed = seventh_state["speed"]
        if not isinstance(speed, (int, float)):
            raise ValueError("Longitude speed must be finite")
        from math import isfinite

        if not isfinite(speed):
            raise ValueError("Longitude speed must be finite")
        retro = speed < 0
    if retro is not None and type(retro) is not bool:
        raise ValueError("Retrograde state must be a boolean or unknown")
    seventh_afflicted = _any(
        [
            reported["seventh_cusp_afflicted_reported"],
            retro,
            reported["seventh_lord_impeded_reported"],
        ]
    )
    saturn = states.get("Saturn", {})
    assignment = saturn.get("house_assignment")
    selected_saturn_house = (
        None if assignment is None else assignment.get("assigned_house")
    )
    saturn_house_facts = {
        "geometric_house": saturn.get("occupied_house"),
        "cusp_virtue_house": selected_saturn_house,
        "selected_policy": "p33 cusp virtue; geometric occupancy separately retained, full historical variant not accepted",
        "saturn_retrograde": saturn.get("retrograde"),
    }
    sun = positions.get("Sun")
    querent_pos = positions.get(asc_lord) if asc_lord is not None else None
    solar_known = sun is not None and querent_pos is not None
    solar = (
        None
        if querent_pos is None or sun is None
        else combustion_state(querent_pos, sun)
    )
    seventh_pos = positions.get(seventh_lord) if seventh_lord is not None else None
    essential = (
        None
        if seventh_lord is None or seventh_pos is None
        else dignity_at(seventh_lord, seventh_pos, sect)
    )
    seventh_fall = None if essential is None else "fall" in essential["debilities"]
    bad_bound = (
        None if essential is None else essential["lords"]["bound"] in {"Saturn", "Mars"}
    )
    seventh_bad = _any(
        [reported["seventh_lord_unfortunate_reported"], seventh_fall, bad_bound]
    )
    rows: list[dict[str, Any]] = []

    def put(
        code: str,
        value: bool | None,
        reading: str,
        facts: dict[str, Any],
        *,
        applicable: bool = True,
        exception: bool | None = None,
        attributed: bool = False,
        has_exception: bool = False,
    ) -> None:
        spec = next(r for r in CLAUSES if r[0] == code)
        status = (
            "not_applicable"
            if not applicable
            else (
                "unknown"
                if value is None
                else (
                    "qualified_by_reported_exception"
                    if value and has_exception and exception is True
                    else (
                        "present_exception_unknown"
                        if value and has_exception and exception is None
                        else "present" if value else "absent"
                    )
                )
            )
        )
        rows.append(
            {
                "code": code,
                "condition": spec[1],
                "source_pages": spec[2],
                "condition_present": value,
                "applicable": applicable,
                "exception_satisfied": exception,
                "exception_applicable": has_exception,
                "attributed_variant": attributed,
                "status": status,
                "inputs": facts,
                "conditional_reading_zh": reading,
            }
        )

    put(
        "R01",
        affinity["supported_under_declared_policy"],
        "时主与上升主的同主、所选三分及本性对应分别核对；此对应是具名原典的一个前提，不是整盘可判断性或现实效力证明。",
        affinity,
    )
    put(
        "C01",
        early,
        "上升前三度的原文审慎条件保留极年轻且体貌相应的例外；未报告的上下文仍未知。",
        {
            "degree_in_sign": None if degree is None else longitude_float(degree),
            "interval": "[0,3)",
            "printed_short_ascension_sign": (
                None if asc_sign is None else asc_sign in SHORT_ASCENSION_PRINTED
            ),
            "short_ascension_scope": "Printed northern-context list; not recomputed local rising-time geometry",
        },
        exception=early_exception,
        has_exception=True,
    )
    put(
        "C02",
        late,
        "上升27至29度须核对原文年龄对应或确定事件时刻的例外；提问时间已填写不等于确定事件图。",
        {
            "degree_in_sign": None if degree is None else longitude_float(degree),
            "interval": "[27,30)",
            "age_degree_exception_reported": reported["age_degree_agreement_reported"],
            "certain_timed_event_exception": event_exception,
        },
        exception=late_exception,
        has_exception=True,
    )
    put(
        "C03",
        None,
        "原文月亮晚度未给数值界限，不能套用上升27度阈值；双子、天蝎、摩羯为原页特别列出的星座。",
        {
            "moon_sign": moon_sign,
            "moon_degree_in_sign": None if moon is None else longitude_float(moon % 30),
            "printed_special_sign": (
                None if moon_sign is None else moon_sign in MOON_LATE_SPECIAL
            ),
            "numeric_cutoff_supplied_by_source": False,
        },
    )
    put(
        "C04",
        via,
        "燃烧之路按声明的天秤后15度至天蝎前15度计算；原文将它列为部分作者的说法，不能改写为所有流派的统一裁决。",
        {
            "moon_longitude": None if moon is None else longitude_float(moon),
            "interval": "[195,225)",
        },
        attributed=True,
    )
    put(
        "C05",
        voc,
        "空亡几何状态与原文修饰分别保留：主星很强为例外，金牛、巨蟹、射手、双鱼另有仍可有所作为的说法，不能仅凭空亡断定失败。",
        {
            "void_of_course": voc,
            "motion_basis": (moon_voc.get("motion_basis") or {}).get("method_id"),
            "moon_sign": moon_sign,
            "some_performance_sign_qualification": moon_sign_qualification,
            "qualification_does_not_clear_geometric_voc": True,
        },
        exception=reported["principal_significators_very_strong_reported"],
        has_exception=True,
    )
    put(
        "C06",
        seventh_afflicted,
        "非第七宫事项的七宫头／主受损条款单列；逆行可核定，笼统受损定义及未报告条件保留未知。",
        {
            "quesited_house": quesited_house,
            "seventh_lord": seventh_lord,
            "seventh_lord_retrograde": retro,
            "cusp_affliction_reported": reported["seventh_cusp_afflicted_reported"],
            "lord_impediment_reported": reported["seventh_lord_impeded_reported"],
        },
        applicable=quesited_house != 7,
    )
    put(
        "C07",
        None if selected_saturn_house is None else selected_saturn_house == 1,
        "土星第一宫条款保留尤其逆行的强调；按声明的宫头效力政策核对，不由此确认现实结果。",
        saturn_house_facts,
    )
    put(
        "C08",
        None if selected_saturn_house is None else selected_saturn_house == 7,
        "土星第七宫是原页转述的另一条审慎规则，与前一条非七宫事项的适用前提分开。",
        saturn_house_facts,
        attributed=True,
    )
    put(
        "C09",
        None if not solar_known else solar == "combust",
        "上升主日灼按已声明太阳分类核对，日光束和日心不冒充此条日灼条件。",
        {
            "ascendant_lord": asc_lord,
            "solar_state": "unknown" if not solar_known else solar or "clear_of_beams",
        },
        applicable=asc_lord != "Sun",
    )
    put(
        "C10",
        seventh_bad,
        "七宫主落陷、入土火之界可分别核定；原文笼统不利状态不以任意分数阈值替代。",
        {
            "seventh_lord": seventh_lord,
            "fall": seventh_fall,
            "bound_lord": None if essential is None else essential["lords"]["bound"],
            "unfortunate_reported": reported["seventh_lord_unfortunate_reported"],
        },
    )
    put(
        "C11",
        reported["equal_fortune_infortune_testimonies_reported"],
        "原文证词相当时暂缓判断；这项报告不由第115页加权余额等于零自动推得。",
        {
            "equal_testimonies_reported": reported[
                "equal_fortune_infortune_testimonies_reported"
            ],
            "p115_zero_balance_substituted": False,
        },
    )
    strictures = [
        {
            "code": r["code"],
            "detail": r["conditional_reading_zh"],
            "source_pages": r["source_pages"],
            "status": r["status"],
            "exception_satisfied": r["exception_satisfied"],
            "exception_applicable": r["exception_applicable"],
            "attributed_variant": r["attributed_variant"],
        }
        for r in rows
        if r["code"] not in {"R01", "C03"}
        and r["applicable"]
        and r["condition_present"] is True
    ]
    return {
        "method_id": "lilly1647_p121_123_consideration_review_v1",
        "source_url": SOURCE_URL,
        "source_pages": [33, 104, 121, 122, 123],
        "clause_count": len(rows),
        "clauses": rows,
        "hour_inputs": hour_inputs,
        "hour_affinity": affinity,
        "reported_context": reported,
        "ascendant_degree_gate": {
            "early": early,
            "late": late,
            "early_exception_satisfied": early_exception,
            "late_exception_satisfied": late_exception,
            "certain_timed_event_exception": event_exception,
        },
        "unknown_clauses": [
            r["code"]
            for r in rows
            if r["applicable"]
            and (
                r["condition_present"] is None
                or r["status"] == "present_exception_unknown"
            )
        ],
        "strictures": strictures,
        "safe_to_judge": None,
        "safe_to_judge_scope": "Complete source fitness not established; no caution, matched affinity or reported exception certifies a safe/true prediction",
        "status": "clause_review_with_unresolved_source_and_context",
        "house_policy": "p33 cusp virtue for selected Saturn conditions; literal occupied house separately retained, other historical readings unaccepted",
        "house_system": house_system,
        "zodiac_type": zodiac_type,
        "source_method_scope": (
            "tropical_regiomontanus_declared_review"
            if house_system == "R" and zodiac_type in {"Tropic", "Tropical"}
            else "other_or_unknown_chart_method_modern_extension"
        ),
        "conditional_reading_zh": f"已逐条核对Lilly起盘审慎段落的{len(rows)}项条款，时主对应、角度条件、例外及待核定义分别保留；它们描述判断前提，不直接给出所问事情的成败。",
        "full_original_text_acceptance": False,
        "full_judgement_accepted": False,
        "real_world_prediction_established": False,
    }
