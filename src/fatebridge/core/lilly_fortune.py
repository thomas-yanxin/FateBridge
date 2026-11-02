"""Lilly's non-reversing Fortune and every p145 row, with explicit policies.

The printed table is complete here; complete historical interpretation is not.
Exact planetary rays and the transfer of p179 stellar range are disclosed
conventions, not proof that every aspect/orb reading has been adjudicated.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Sequence

from fatebridge.core.astro.geometry import (
    Angle,
    angle_fraction,
    angular_separation_fraction,
    longitude_float,
)
from fatebridge.core.classical_western import combustion_state
from fatebridge.core.lilly import SIGNS, SOURCE_URL, dignity_at
from fatebridge.core.lilly_house_assignment import assign_from_cusps
from fatebridge.core.lilly_star_orbs import STELLAR_ORB_DEGREES

ROW_SPECS = (
    ("P01", 5, "sign_taurus_pisces"),
    ("P02", 4, "sign_libra_sagittarius_leo_cancer"),
    ("P03", 3, "sign_gemini"),
    ("P04", 2, "virgo_in_jupiter_venus_terms"),
    ("P05", 5, "conjunction_jupiter_venus"),
    ("P06", 4, "trine_jupiter_venus"),
    ("P07", 3, "sextile_jupiter_venus"),
    ("P08", 3, "conjunction_north_node"),
    ("P09", 5, "house_1_10"),
    ("P10", 4, "house_7_4_11"),
    ("P11", 3, "house_2_5"),
    ("P12", 2, "house_9"),
    ("P13", 1, "house_3"),
    ("P14", 6, "regulus"),
    ("P15", 5, "spica"),
    ("P16", 5, "clear_combustion_and_beams"),
    ("Z01", 0, "sign_aries_neutral"),
    ("N01", -5, "sign_scorpio_capricorn_aquarius"),
    ("N02", -5, "conjunction_saturn_mars"),
    ("N03", -3, "conjunction_south_node"),
    ("N04", -4, "opposition_saturn_mars"),
    ("N05", -3, "square_saturn_mars"),
    ("N06", -2, "saturn_mars_terms"),
    ("N07", -5, "house_12"),
    ("N08", -4, "house_8"),
    ("N09", -4, "house_6"),
    ("N10", -4, "algol"),
    ("N11", -5, "combust"),
)
LABELS_ZH = (
    "福点在金牛或双鱼",
    "福点在天秤、射手、狮子或巨蟹",
    "福点在双子",
    "福点在处女且入木星或金星之界",
    "木星或金星合福点",
    "木星或金星拱福点",
    "木星或金星六合福点",
    "北交点合福点",
    "福点效力归第一或第十宫",
    "福点效力归第七、第四或第十一宫",
    "福点效力归第二或第五宫",
    "福点效力归第九宫",
    "福点效力归第三宫",
    "福点与轩辕十四同度附近",
    "福点与角宿一同度附近",
    "福点脱离日灼及日光束",
    "福点在白羊不增不减",
    "福点在天蝎、摩羯或水瓶",
    "土星或火星合福点",
    "南交点合福点",
    "土星或火星冲福点",
    "土星或火星刑福点",
    "福点入土星或火星之界",
    "福点效力归第十二宫",
    "福点效力归第八宫",
    "福点效力归第六宫",
    "福点与大陵五同度附近",
    "福点日灼",
)


def _any(values: list[bool | None]) -> bool | None:
    return True if True in values else None if None in values else False


def evaluate_fortune(
    ascendant: Angle | None,
    states: dict[str, dict[str, Any]],
    physical_inputs: dict[str, Any],
    *,
    cusps: Sequence[Angle] | None = None,
    house_assignment: dict[str, Any] | None = None,
    house_system: str | None = None,
    zodiac_type: str | None = None,
) -> dict[str, Any]:
    """Compute ASC + Moon - Sun in both sects, without a fictional orb for a lot."""
    positions = {
        p: None if s.get("longitude") is None else angle_fraction(s["longitude"]) % 360
        for p, s in states.items()
    }
    sun, moon = positions.get("Sun"), positions.get("Moon")
    lon = (
        None
        if ascendant is None or sun is None or moon is None
        else (angle_fraction(ascendant) + moon - sun) % 360
    )
    sign = None if lon is None else SIGNS[int(lon // 30)]
    term = None if lon is None else dignity_at("Mars", lon, None)["lords"]["bound"]
    assignment = dict(
        house_assignment
        if house_assignment is not None
        else assign_from_cusps(
            lon, cusps, house_system=house_system, zodiac_type=zodiac_type
        )
    )
    house = assignment.get("assigned_house")
    if house is not None and house not in range(1, 13):
        raise ValueError("Fortune assigned house must be1..12 or unknown")
    evaluated: dict[str, tuple[bool | None, dict[str, Any]]] = {}

    def put(code: str, holds: bool | None, **facts: Any) -> None:
        evaluated[code] = (holds, facts)

    for code, signs in [
        ("P01", {"Taurus", "Pisces"}),
        ("P02", {"Libra", "Sagittarius", "Leo", "Cancer"}),
        ("P03", {"Gemini"}),
        ("Z01", {"Aries"}),
        ("N01", {"Scorpio", "Capricorn", "Aquarius"}),
    ]:
        put(code, None if sign is None else sign in signs, sign=sign)
    put(
        "P04",
        None if sign is None else sign == "Virgo" and term in {"Jupiter", "Venus"},
        sign=sign,
        bound_lord=term,
    )
    put(
        "N06",
        None if term is None else term in {"Saturn", "Mars"},
        bound_lord=term,
        bound_table="Lilly1647 p104 half-open intervals",
    )
    for code, planets, angle in [
        ("P05", ["Jupiter", "Venus"], 0),
        ("P06", ["Jupiter", "Venus"], 120),
        ("P07", ["Jupiter", "Venus"], 60),
        ("N02", ["Saturn", "Mars"], 0),
        ("N04", ["Saturn", "Mars"], 180),
        ("N05", ["Saturn", "Mars"], 90),
    ]:
        gaps: dict[str, Fraction | None] = {}
        for p in planets:
            other = positions.get(p)
            gaps[p] = (
                None
                if lon is None or other is None
                else angular_separation_fraction(lon, other)
            )
        put(
            code,
            _any([None if gap is None else gap == angle for gap in gaps.values()]),
            planet_to_fortune_rays=True,
            angle=angle,
            exact_separations={
                p: None if g is None else str(g) for p, g in gaps.items()
            },
            aspect_policy="Strict exact supplied longitude ray; p145 non-partile/orb variants not adjudicated; Fortune emits no ray",
        )
    node = physical_inputs.get("north_node_longitude")
    for code, delta in [("P08", 0), ("N03", 180)]:
        node_lon = None if node is None else (angle_fraction(node) + delta) % 360
        put(
            code,
            (
                None
                if lon is None or node_lon is None
                else angular_separation_fraction(lon, node_lon) == 0
            ),
            node_longitude=None if node_lon is None else float(node_lon),
            node_model=physical_inputs.get("node_model"),
            exact_longitude_policy=True,
        )
    for code, houses in [
        ("P09", [1, 10]),
        ("P10", [7, 4, 11]),
        ("P11", [2, 5]),
        ("P12", [9]),
        ("P13", [3]),
        ("N07", [12]),
        ("N08", [8]),
        ("N09", [6]),
    ]:
        put(
            code,
            None if house is None else house in houses,
            geometric_house=assignment.get("geometric_house"),
            assigned_house=house,
            assignment_policy=assignment.get("assignment_policy"),
            p145_separate_from_planet_house_points=True,
        )
    for code, star in [("P14", "Regulus"), ("P15", "Spica"), ("N10", "Algol")]:
        position = physical_inputs.get("star_longitudes", {}).get(star)
        gap = (
            None
            if lon is None or position is None
            else angular_separation_fraction(lon, position)
        )
        put(
            code,
            None if gap is None else gap <= STELLAR_ORB_DEGREES[star],
            star=star,
            star_longitude=position,
            separation_degrees=None if gap is None else float(gap),
            orb_degrees=STELLAR_ORB_DEGREES[star],
            star_policy=(
                f"{star} {STELLAR_ORB_DEGREES[star]}-degree planetary range from "
                f"p{115 if star == 'Algol' else 179}, transferred to p145 lot row "
                "as declared convention; p145 itself supplies no range; full interpretation unaccepted"
            ),
            current_position_policy=physical_inputs.get("star_position_policy"),
        )
    solar_known = lon is not None and sun is not None
    solar = None if lon is None or sun is None else combustion_state(lon, sun)
    put(
        "P16",
        None if not solar_known else solar is None,
        solar_state=solar,
        policy="Shared p113 classification; clear of both combustion and beams",
    )
    put(
        "N11",
        None if not solar_known else solar == "combust",
        solar_state=solar,
        policy="Shared p113 classification; cazimi has no separate p145 bonus; lot-specific variants unaccepted",
    )
    rows: list[dict[str, Any]] = []
    for (code, points, condition), label in zip(ROW_SPECS, LABELS_ZH):
        holds, facts = evaluated[code]
        rows.append(
            dict(
                code=code,
                points=points,
                condition=condition,
                label_zh=label,
                applicable=True,
                satisfied=holds,
                status=(
                    "unknown"
                    if holds is None
                    else "satisfied" if holds else "not_satisfied"
                ),
                contribution=None if holds is None else points if holds else 0,
                inputs=facts,
                source_pages=(
                    [145, 179]
                    if code in {"P14", "P15"}
                    else [115, 145] if code == "N10" else [145]
                ),
            )
        )
    # A lot has its own p145 house weights; do not expose p115 planet points
    # as if they applied to Fortune (sixth/eighth are materially different).
    assignment.pop("assigned_p115_house_points", None)
    assignment["assigned_p145_house_points"] = (
        None
        if house is None
        else sum(r["contribution"] for r in rows if r["condition"].startswith("house_"))
    )
    unknown = [r["code"] for r in rows if r["satisfied"] is None]
    positive = sum(
        r["contribution"]
        for r in rows
        if r["contribution"] is not None and r["contribution"] > 0
    )
    negative = -sum(
        r["contribution"]
        for r in rows
        if r["contribution"] is not None and r["contribution"] < 0
    )
    return {
        "method_id": "lilly_1647_fortune_p143_145_declared_rows_v2",
        "source_url": SOURCE_URL,
        "source_pages": [33, 104, 113, 143, 144, 145, 177, 179, 180],
        "longitude": None if lon is None else longitude_float(lon),
        "exact_longitude": None if lon is None else str(lon),
        "sign": sign,
        "degree_in_sign": None if lon is None else longitude_float(lon % 30),
        "formula": {
            "expression": "(Ascendant + Moon - Sun) mod360",
            "reverses_at_night": False,
            "ascendant": (
                None if ascendant is None else float(angle_fraction(ascendant) % 360)
            ),
            "sun": None if sun is None else float(sun),
            "moon": None if moon is None else float(moon),
            "uses_physical_ascendant_not_first_cusp": True,
            "source_pages": [143, 144],
            "scope": "Lilly formula; separate from generic sect-reversing lots and named Ptolemy layers",
        },
        "house_assignment": assignment,
        "bound_lord": term,
        "solar_state": "unknown" if not solar_known else solar or "clear_of_beams",
        "row_count": len(rows),
        "rows": rows,
        "status": "partial" if unknown else "computed_under_declared_policy",
        "known_fortitudes": positive,
        "known_debilities": negative,
        "known_balance": positive - negative,
        "literal_table_balance": None if unknown else positive - negative,
        "unknown_rows": unknown,
        "applied_conditions": [
            {k: r[k] for k in ["code", "label_zh", "contribution", "source_pages"]}
            for r in rows
            if r["satisfied"] is True
        ],
        "points_are_success_probability": False,
        "conditional_reading_zh": f"Lilly福点采用昼夜同式，已核定助力{positive}、减损{negative}，尚未知{len(unknown)}行；分值仅描述声明规则的传统条件，不能当作财富金额、现实成功概率或原书整盘判断。",
        "source_method_scope": (
            "tropical_regiomontanus_declared_p145_policy"
            if house_system == "R" and zodiac_type in {"Tropic", "Tropical"}
            else "other_or_unknown_chart_method_modern_extension"
        ),
        "interpretation_policies": [
            "p143 planets cast rays to Fortune; Fortune emits none",
            "p145 exact aspect policy and p179 stellar range transfer explicitly unaccepted as exhaustive source interpretation",
            "p180 beyond-five-degree assignment and omitted p145 rows retained as failed source controls",
        ],
        "full_original_text_acceptance": False,
        "full_judgement_accepted": False,
        "real_world_prediction_established": False,
    }
