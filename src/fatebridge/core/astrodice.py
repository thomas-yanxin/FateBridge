"""Symbolic astrodice rules; never invent a degree, aspect or event time.

Duvendack documents the twelve faces; Ptolemy documents sign relationships.
FateBridge owns the synthesis policy, which is not an ancient dice method.
"""

from __future__ import annotations

import re
from fractions import Fraction
from typing import Any, Dict, List, Literal

from fatebridge.core.astro.astrology_tables import (
    DOMICILE_RULERS,
    ELEMENT_BY_SIGN,
    EXALTATION_SIGNS,
    MODALITY_BY_SIGN,
    RULER_BY_SIGN,
    SIGN_LABELS_ZH,
    SIGNS,
)
from fatebridge.core.astro.ptolemy import SOURCE_URL as TRIPLICITY_SOURCE
from fatebridge.core.astro.ptolemy import triplicity_assigned_rulers, triplicity_rulers
from fatebridge.core.classical_western import planet_sect
from fatebridge.utils.coordinates import parse_geo_coordinate

METHOD_ID = "astrodice_symbolic_v7"
SIGN_RULESET = "ptolemy_ashmand_1822_signs"
EDITORIAL_RULESET = "fatebridge_astrodice_editorial_v7"
DETRIMENT_RULESET = "houlding_opposite_domicile_definition_v1"
DETRIMENT_SOURCE = "https://www.skyscript.co.uk/dig2.html"
FACE_SOURCE = (
    "https://418ascendant.com/wp-content/uploads/2012/01/What-are-Astro-Dice.pdf"
)
DOMICILE_SOURCE = "https://sacred-texts.com/astro/ptb/ptb23.htm"
EXALTATION_SOURCE = "https://sacred-texts.com/astro/ptb/ptb25.htm"
HOUSE_SOURCE = "https://www.skyscript.co.uk/lilly_houses.html"
HOUSE_RULESET = "lilly_1647_house_joys_v1"
TRIPLICITY_RULESET = "ptolemy_robbins_1940_symbolic_triangles_v2"
PLANET_SECT_RULESET = "ptolemy_robbins_1940_planet_sect_v1"
# Christian Astrology, 1647, pp. 51-56; these are joys, not sign dignities.
JOY_HOUSES = {
    "Mercury": 1,
    "Moon": 3,
    "Venus": 5,
    "Mars": 6,
    "Sun": 9,
    "Jupiter": 11,
    "Saturn": 12,
}

PLANETS = (
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
    "NorthNode",
    "SouthNode",
)
PLANET_LABELS_ZH = dict(
    zip(
        PLANETS,
        (
            "太阳",
            "月亮",
            "水星",
            "金星",
            "火星",
            "木星",
            "土星",
            "天王星",
            "海王星",
            "冥王星",
            "北交点",
            "南交点",
        ),
    )
)
PLANET_GLYPHS = dict(
    zip(
        PLANETS,
        (
            "☉",
            "☽",
            "☿",
            "♀",
            "♂",
            "♃",
            "♄",
            "♅",
            "♆",
            "♇",
            "☊",
            "☋",
        ),
    )
)
SIGN_GLYPHS = dict(zip(SIGNS, "♈♉♊♋♌♍♎♏♐♑♒♓"))


def _key(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("必须提供实际骰面，不能使用默认骰面")
    return "".join(
        value.strip().casefold().replace("\ufe0f", "").replace("\ufe0e", "").split()
    )


def normalize_sign(value: Any) -> str:
    key = _key(value)
    for sign in SIGNS:
        if key in {
            _key(sign),
            SIGN_LABELS_ZH[sign],
            SIGN_LABELS_ZH[sign] + "座",
            SIGN_GLYPHS[sign],
        }:
            return sign
    raise ValueError("sign必须为十二星座名称、中文名或星座符号")


def normalize_planet(value: Any) -> str:
    key = _key(value)
    aliases = {
        "日": "Sun",
        "月": "Moon",
        "☾": "Moon",
        "⯓": "Pluto",
        "北交": "NorthNode",
        "南交": "SouthNode",
    }
    if key in aliases:
        return aliases[key]
    for planet in PLANETS:
        if key in {_key(planet), PLANET_LABELS_ZH[planet], PLANET_GLYPHS[planet]}:
            return planet
    raise ValueError("planet必须为日月、八颗行星或南北交点的名称、中文名或符号")


def normalize_house(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= 11:
        raise ValueError("house必须为0..11的整数索引；实际第N宫传N-1，不可截断或钳制")
    return value


def _validate_coordinate_aliases(
    text: Any, gps: Any, *, axis: Literal["latitude", "longitude"]
) -> None:
    first = parse_geo_coordinate(text, axis=axis)
    second = parse_geo_coordinate(gps, axis=axis)
    if (text is not None and first is None) or (gps is not None and second is None):
        raise ValueError("附加天象盘不能使用空白坐标")
    if first is not None and second is not None:
        distance = abs(Fraction(first) - Fraction(second))
        if axis == "longitude":
            distance = min(distance, 360 - distance)
        if distance > 1e-9:
            raise ValueError(
                f"{axis}文本坐标与GPS坐标不一致；请仅提供一套已核对坐标，不能静默覆盖"
            )


def validate_context(
    *, date: Any, time: Any, zone: Any, lat: Any, lon: Any, gps_lat: Any, gps_lon: Any
) -> None:
    if date is None and time is None:
        if any(v is not None for v in (zone, lat, lon, gps_lat, gps_lon)):
            raise ValueError(
                "附加天象盘需要同时提供date/time/zone和经纬度；仅骰面解读请省略这些参数"
            )
        return
    if not all(isinstance(v, str) and v.strip() for v in (date, time, zone)):
        raise ValueError("附加天象盘需要明确date/time/zone，不能补默认时刻或时区")
    if (lat is None and gps_lat is None) or (lon is None and gps_lon is None):
        raise ValueError("附加天象盘需要明确经纬度，不能补默认地点")
    _validate_coordinate_aliases(lat, gps_lat, axis="latitude")
    _validate_coordinate_aliases(lon, gps_lon, axis="longitude")
    if (
        re.fullmatch(r"\d{1,2}:\d{1,2}(?::\d{1,2}(?:\.\d{1,6})?)?", time.strip())
        is None
    ):
        raise ValueError("time须为本地HH:MM[:SS[.微秒]]，时区单独通过zone传入")


def sign_condition(planet: str, sign: str) -> Dict[str, Any]:
    """Only sign-level facts: no degrees, sect, terms, faces or total score."""
    supported = planet in DOMICILE_RULERS
    domiciles = list(DOMICILE_RULERS[planet]) if supported else []
    exaltations = [EXALTATION_SIGNS[planet]] if supported else []
    definitions = [
        (
            "domicile",
            domiciles,
            SIGN_RULESET,
            DOMICILE_SOURCE,
            "direct_sign_assignment",
        ),
        (
            "exaltation",
            exaltations,
            SIGN_RULESET,
            EXALTATION_SOURCE,
            "direct_sign_assignment",
        ),
        (
            "detriment",
            [SIGNS[(SIGNS.index(s) + 6) % 12] for s in domiciles],
            DETRIMENT_RULESET,
            DETRIMENT_SOURCE,
            "opposite_domicile_definition",
        ),
        (
            "fall",
            [SIGNS[(SIGNS.index(s) + 6) % 12] for s in exaltations],
            SIGN_RULESET,
            EXALTATION_SOURCE,
            "opposite_exaltation_explicit_in_source",
        ),
    ]
    evidence = [
        {
            "condition": name,
            "matched": sign in signs if supported else None,
            "basis_signs": signs if supported else None,
            "ruleset_id": ruleset,
            "source_url": source,
            "derivation": derivation,
            "status": (
                "evaluated_sign_only" if supported else "outside_seven_planet_scope"
            ),
        }
        for name, signs, ruleset, source, derivation in definitions
    ]
    return {
        "status": "evaluated_sign_only" if supported else "outside_seven_planet_scope",
        "conditions": [row["condition"] for row in evidence if row["matched"] is True],
        "condition_evidence": evidence,
        "domicile_ruler": RULER_BY_SIGN[sign],
        "dispositor_status": (
            "self_symbolic" if RULER_BY_SIGN[sign] == planet else "not_in_roll"
        ),
        "unassessed": [
            "applied_triplicity_sect",
            "bound",
            "face",
            "sect",
            "degree",
            "aspects",
            "reception",
        ],
        "note": "不据此判定游离、总尊贵分或事情成败；自定位仅为符号关系，其他定位星未由本次骰面给出。",
    }


def house_condition(planet: str, house: int) -> Dict[str, Any]:
    joy = JOY_HOUSES.get(planet)
    return {
        "status": (
            "evaluated_house_symbol_only"
            if joy is not None
            else "outside_seven_planet_scope"
        ),
        "joy_house_number": joy,
        "in_joy": house + 1 == joy if joy is not None else None,
        "ruleset_id": HOUSE_RULESET,
        "scope": "Dice house label only; not observed planetary placement or an event outcome",
    }


def triplicity_condition(planet: str, sign: str) -> Dict[str, Any]:
    """Keep both conditional relationships; the roll has no astronomical sect."""
    rulers = {sect: triplicity_rulers(sign, sect) for sect in ("day", "night")}
    assigned = triplicity_assigned_rulers(sign)
    supported = planet in DOMICILE_RULERS

    def conditional_role(rule: Dict[str, Any]) -> str:
        if not supported:
            return "outside_seven_planet_scope"
        if planet == rule["primary"]:
            return "primary"
        if planet == rule["co_ruler"]:
            return "co_ruler"
        return "assigned_not_selected" if planet in assigned else "not_assigned"

    roles = {sect: conditional_role(rule) for sect, rule in rulers.items()}
    return {
        "status": (
            "conditional_sect_not_in_roll"
            if supported
            else "outside_seven_planet_scope"
        ),
        "ruleset_id": TRIPLICITY_RULESET,
        "sect": None,
        "assigned_rulers": assigned,
        "in_assigned_group": planet in assigned if supported else None,
        "roles_by_sect": roles,
        "rulers_by_sect": rulers,
        "matches_by_sect": {
            sect: planet in assignment.values() if supported else None
            for sect, assignment in rulers.items()
        },
        "match_definition": "selected_primary_or_explicit_co_ruler_under_named_sect",
        "scope": "Overall triangle assignment and separately named conditional roles; no sect transferred from optional sky context, no total dignity or event score",
    }


def planet_sect_condition(planet: str) -> Dict[str, Any]:
    """I.7 natural assignment is not the unobserved chart's day/night sect.

    Mercury requires a solar phase absent from the dice. Neither its house
    label nor a separate optional sky chart supplies that symbolic-roll fact.
    """
    supported = planet in DOMICILE_RULERS
    return {
        "status": (
            "conditional_on_solar_phase_not_in_roll"
            if planet == "Mercury"
            else (
                "natural_assignment_without_chart_sect"
                if supported
                else "outside_seven_planet_scope"
            )
        ),
        "ruleset_id": PLANET_SECT_RULESET,
        "natural_sect": planet_sect(planet, None),
        "assignments_by_solar_phase": (
            {
                "morning_star": planet_sect(planet, "oriental"),
                "evening_star": planet_sect(planet, "occidental"),
            }
            if planet == "Mercury"
            else None
        ),
        "solar_phase": None,
        "applied_chart_sect": None,
        "matches_chart_sect": None,
        "scope": "I.7 natural planet assignment only; no chart sect, visibility, dignity score or event judgement inferred from dice or optional sky",
    }


def build_symbolic_evidence(planet: str, sign: str, house: int) -> Dict[str, Any]:
    condition = sign_condition(planet, sign)
    house_number = house + 1
    start = (SIGNS.index(sign) - house) % 12
    ring: List[Dict[str, Any]] = [
        {
            "house_number": i + 1,
            "sign": SIGNS[(start + i) % 12],
            "domicile_ruler": RULER_BY_SIGN[SIGNS[(start + i) % 12]],
        }
        for i in range(12)
    ]
    details: Dict[str, Any] = {
        "house_number": house_number,
        "planet_kind": (
            "lunar_node"
            if planet in {"NorthNode", "SouthNode"}
            else (
                "luminary"
                if planet in {"Sun", "Moon"}
                else "dwarf_planet" if planet == "Pluto" else "planet"
            )
        ),
        "element": ELEMENT_BY_SIGN[sign],
        "modality": MODALITY_BY_SIGN[sign],
        "house_group": ("angular", "succedent", "cadent")[house % 3],
        "sign_condition": condition,
        "house_condition": house_condition(planet, house),
        "triplicity_condition": triplicity_condition(planet, sign),
        "planet_sect_condition": planet_sect_condition(planet),
        "symbolic_house_ring": ring,
        "houses_ruled_by_rolled_planet": [
            row["house_number"] for row in ring if row["domicile_ruler"] == planet
        ],
    }
    rulesets: List[Dict[str, Any]] = [
        {
            "id": "duvendack_2013_faces",
            "author": "Rev Bill Duvendack",
            "version": "2013",
            "source_url": FACE_SOURCE,
            "source_kind": "author_primary_explanation",
            "scope": "十二种骰面与星体/星座/宫位组合；不采用作者另述的出生盘扩展法。",
        },
        {
            "id": SIGN_RULESET,
            "author": "Claudius Ptolemy; tr. J. M. Ashmand",
            "version": "Tetrabiblos, 1822, Book I, chapters XX and XXII",
            "source_url": DOMICILE_SOURCE,
            "additional_urls": [EXALTATION_SOURCE],
            "source_kind": "primary_text_translation",
            "scope": "七曜入庙、擢升与落陷；失势定义另有来源，不归给本章；不声称原典含星骰法。",
        },
        {
            "id": EDITORIAL_RULESET,
            "author": "FateBridge contributors",
            "version": METHOD_ID,
            "source_path": "docs/astrodice.md",
            "source_kind": "product_convention",
            "scope": "元素、模式、宫位组与假设整宫轮。",
        },
        {
            "id": HOUSE_RULESET,
            "author": "William Lilly",
            "version": "Christian Astrology, 1647, pp.51-56; Skyscript transcription",
            "source_url": HOUSE_SOURCE,
            "source_kind": "primary_text_transcription",
            "scope": "七曜喜乐宫关系；不将原文的临床、生死或灾祸判断用于咨询，不以喜乐判定事件吉凶。",
        },
        {
            "id": TRIPLICITY_RULESET,
            "author": "Claudius Ptolemy; tr. F. E. Robbins",
            "version": "Tetrabiblos, Loeb Classical Library, 1940, I.18",
            "source_url": TRIPLICITY_SOURCE,
            "source_kind": "primary_text_translation",
            "scope": "分别保留三角总体分派与昼夜首要/明确共管角色；水象为火星与昼金星/夜月亮共管；不混入Dorotheus第三主星或从天象选定骰面昼夜。",
        },
        {
            "id": DETRIMENT_RULESET,
            "author": "Deborah Houlding",
            "version": "Understanding Planetary Dignity and Debility, part 2; undated",
            "source_url": DETRIMENT_SOURCE,
            "source_kind": "author_primary_explanation",
            "scope": "仅采用作者对失势为守护星座对宫的明确说明；不当作托勒密XX章原文或采用文中其他尊贵表。",
        },
        {
            "id": PLANET_SECT_RULESET,
            "author": "Claudius Ptolemy; tr. F. E. Robbins",
            "version": "Tetrabiblos, Loeb Classical Library, 1940, I.7",
            "source_url": TRIPLICITY_SOURCE + "#7",
            "source_kind": "primary_text_translation",
            "scope": "七曜昼夜分派；水星保留晨星昼曜与昏星夜曜两条件。星体分派不等于实际盘的昼夜；不由骰面宫号或附加天象补条件。",
        },
    ]
    trace = [
        {
            "rule_id": "three_faces",
            "ruleset_id": rulesets[0]["id"],
            "inputs": {"planet": planet, "sign": sign, "house": house},
            "result": {"house_number": house_number},
            "scope": "user_supplied_symbols",
        },
        {
            "rule_id": "sign_relationships",
            "ruleset_id": EDITORIAL_RULESET,
            "supporting_ruleset_ids": [SIGN_RULESET, DETRIMENT_RULESET],
            "inputs": {"planet": planet, "sign": sign},
            "result": condition,
            "scope": "sign_only",
        },
        {
            "rule_id": "symbolic_whole_sign_ring",
            "ruleset_id": rulesets[2]["id"],
            "inputs": {"sign": sign, "house": house},
            "result": {
                "first_sign": SIGNS[start],
                "houses_ruled_by_rolled_planet": details[
                    "houses_ruled_by_rolled_planet"
                ],
            },
            "scope": "hypothetical_wheel_not_observed_sky",
        },
        {
            "rule_id": "symbolic_traits",
            "ruleset_id": rulesets[2]["id"],
            "inputs": {"planet": planet, "sign": sign, "house": house},
            "result": {
                "element": details["element"],
                "modality": details["modality"],
                "house_group": details["house_group"],
            },
            "scope": "symbolic_classification",
        },
        {
            "rule_id": "planetary_house_joy",
            "ruleset_id": HOUSE_RULESET,
            "inputs": {"planet": planet, "house": house},
            "result": details["house_condition"],
            "scope": "symbolic_house_only",
        },
        {
            "rule_id": "conditional_triplicity",
            "ruleset_id": TRIPLICITY_RULESET,
            "inputs": {"planet": planet, "sign": sign},
            "result": details["triplicity_condition"],
            "scope": "overall_triangle_assignment_and_both_conditional_roles_without_selecting_a_sect",
        },
        {
            "rule_id": "natural_planet_sect",
            "ruleset_id": PLANET_SECT_RULESET,
            "inputs": {"planet": planet},
            "result": details["planet_sect_condition"],
            "scope": "natural_assignment_and_conditional_mercury_roles_without_chart_sect",
        },
    ]
    return {
        "method_id": METHOD_ID,
        "symbolic_details": details,
        "rulesets": rulesets,
        "rule_trace": trace,
        "validation": {
            "calendar": "not_applicable_to_symbolic_roll",
            "classical": "specified_sign_joy_triangle_and_natural_planet_sect_subsets_only",
        },
    }
