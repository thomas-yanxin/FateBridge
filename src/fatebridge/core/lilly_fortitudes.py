"""Literal p115 row ledger, distinct from complete Lilly judgement.

The pp178-180 worked totals are an independent acceptance check. They do not
authorize dropping contradictory rows from the printed table. Motion, stars,
occupancy and essential dignity keep their separate input/source policies.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from fatebridge.core.astro.geometry import angle_fraction, angular_separation_fraction
from fatebridge.core.classical_western import combustion_state, solar_condition_policy
from fatebridge.core.lilly import PLANETS, SOURCE_URL, dignity_at, pair_reception
from fatebridge.core.lilly_star_orbs import (
    STELLAR_ORB_DEGREES,
    STELLAR_ORB_SOURCE_PAGES,
)

RULESET = "lilly1647_p115_fortitudes_cusp_virtue_v3"
ORDER = ("Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon")
MEAN_MOTION_ARCSECONDS = {
    "Saturn": 121,
    "Jupiter": 299,
    "Mars": 1887,
    "Sun": 3548,
    "Venus": 3548,
    "Mercury": 3548,
    "Moon": 47436,
}
MEAN_MOTION_PAGES = {
    "Saturn": 57,
    "Jupiter": 61,
    "Mars": 65,
    "Sun": 69,
    "Venus": 72,
    "Mercury": 76,
    "Moon": 80,
}
PRINTED_STARS = {"Regulus": 144, "Spica": 198, "Algol": 50}
ROW_SPECS = (
    ("E01", "essential", 5, "own_domicile_or_mutual_domicile_reception"),
    ("E02", "essential", 4, "own_exaltation_or_mutual_exaltation_reception"),
    ("E03", "essential", 3, "own_triplicity"),
    ("E04", "essential", 2, "own_term"),
    ("E05", "essential", 1, "own_face"),
    ("E06", "essential", -5, "detriment"),
    ("E07", "essential", -4, "fall"),
    ("E08", "essential", -5, "peregrine"),
    ("F01", "accidental", 5, "house_1_or_10"),
    ("F02", "accidental", 4, "house_7_4_or_11"),
    ("F03", "accidental", 3, "house_2_or_5"),
    ("F04", "accidental", 2, "house_9"),
    ("F05", "accidental", 1, "house_3"),
    ("F06", "accidental", 4, "direct_except_sun_and_moon"),
    ("F07", "accidental", 2, "swift_daily_motion"),
    ("F08", "accidental", 2, "superiors_oriental"),
    ("F09", "accidental", 2, "mercury_venus_occidental"),
    ("F10", "accidental", 2, "moon_increasing_or_occidental"),
    ("F11", "accidental", 5, "free_from_combustion_and_beams"),
    ("F12", "accidental", 5, "cazimi"),
    ("F13", "accidental", 5, "partile_conjunction_jupiter_or_venus"),
    ("F14", "accidental", 4, "partile_conjunction_north_node"),
    ("F15", "accidental", 4, "partile_trine_jupiter_or_venus"),
    ("F16", "accidental", 3, "partile_sextile_jupiter_or_venus"),
    ("F17", "accidental", 6, "regulus_within_six_degrees"),
    ("F18", "accidental", 5, "spica_within_five_degrees"),
    ("D01", "accidental", -5, "house_12"),
    ("D02", "accidental", -2, "house_8_or_6"),
    ("D03", "accidental", -5, "retrograde"),
    ("D04", "accidental", -2, "slow_daily_motion"),
    ("D05", "accidental", -2, "superiors_occidental"),
    ("D06", "accidental", -2, "mercury_venus_oriental"),
    ("D07", "accidental", -2, "moon_decreasing"),
    ("D08", "accidental", -5, "combust"),
    ("D09", "accidental", -4, "under_beams"),
    ("D10", "accidental", -5, "partile_conjunction_saturn_or_mars"),
    ("D11", "accidental", -4, "partile_conjunction_south_node"),
    ("D12", "accidental", -5, "bodily_besieged_saturn_mars"),
    ("D13", "accidental", -4, "partile_opposition_saturn_or_mars"),
    ("D14", "accidental", -3, "partile_square_saturn_or_mars"),
    ("D15", "accidental", -5, "algol_within_five_degrees"),
)
ROW_LABELS_ZH = {
    "E01": "本垣或本垣互纳",
    "E02": "擢升或擢升互纳",
    "E03": "本三分",
    "E04": "本界",
    "E05": "本十度面",
    "E06": "失势（本垣对宫）",
    "E07": "落陷",
    "E08": "游离（无本质尊贵）",
    "F01": "计分归第一或第十宫",
    "F02": "计分归第七、第四或第十一宫",
    "F03": "计分归第二或第五宫",
    "F04": "计分归第九宫",
    "F05": "计分归第三宫",
    "F06": "顺行（日月不计此项）",
    "F07": "24小时位移快于原书中运动",
    "F08": "土木火对日东方黄经阶段",
    "F09": "金水对日西方黄经阶段",
    "F10": "月亮处于日月黄经朔至望段",
    "F11": "脱离日灼与日光束",
    "F12": "日心（Cazimi）",
    "F13": "与木或金黄经精确合相",
    "F14": "与北交点黄经精确合相",
    "F15": "与木或金黄经精确三分相",
    "F16": "与木或金黄经精确六分相",
    "F17": "与轩辕十四黄经相距六度内",
    "F18": "与角宿一黄经相距五度内",
    "D01": "计分归第十二宫",
    "D02": "计分归第八或第六宫",
    "D03": "逆行",
    "D04": "24小时位移慢于原书中运动",
    "D05": "土木火对日西方黄经阶段",
    "D06": "金水对日东方黄经阶段",
    "D07": "月亮处于日月黄经望至朔段",
    "D08": "日灼",
    "D09": "日光束下",
    "D10": "与土或火黄经精确合相",
    "D11": "与南交点黄经精确合相",
    "D12": "位于土火两体黄经短弧之间",
    "D13": "与土或火黄经精确对分相",
    "D14": "与土或火黄经精确四分相",
    "D15": "与大陵五黄经相距五度内",
}


def _any(values: list[bool | None]) -> bool | None:
    return True if True in values else None if None in values else False


def _longitude(state: dict[str, Any]) -> Fraction | None:
    value = state.get("longitude")
    return None if value is None else angle_fraction(value) % 360


def bodily_between(target: Fraction, first: Fraction, second: Fraction) -> bool | None:
    """Strict shorter-arc body containment, without an invented 15-degree cap."""
    arc = (second - first) % 360
    if arc == 180:
        return None
    if arc > 180:
        first, arc = second, 360 - arc
    return 0 < (target - first) % 360 < arc


def evaluate_fortitudes(
    states: dict[str, dict[str, Any]],
    sect: str | None,
    physical_inputs: dict[str, Any],
    *,
    house_system: str | None,
    zodiac_type: str | None,
) -> dict[str, Any]:
    """Evaluate every printed row; unknown required facts never contribute zero."""
    if not set(states) <= PLANETS:
        raise ValueError("Lilly fortitudes require the seven traditional planets")
    longitudes = {p: _longitude(states.get(p, {})) for p in ORDER}
    own = {
        p: dignity_at(p, lon, sect) if lon is not None else None
        for p, lon in longitudes.items()
    }
    sun = longitudes["Sun"]
    bodies, summaries = {}, {}
    for planet in ORDER:
        state, lon, essential = states.get(planet, {}), longitudes[planet], own[planet]
        evaluations: dict[str, tuple[bool | None, bool, dict[str, Any], list[int]]] = {}

        def put(
            code: str,
            holds: bool | None,
            facts: dict[str, Any],
            pages: list[int],
            applicable: bool = True,
        ) -> None:
            evaluations[code] = (holds, applicable, facts, pages)

        for code, kind in [("E01", "rulership"), ("E02", "exaltation")]:
            mutual: list[bool | None] = []
            witnesses = []
            for other in ORDER:
                if other == planet:
                    continue
                other_lon = longitudes[other]
                if lon is None or other_lon is None:
                    mutual.append(None)
                    continue
                pair = pair_reception(planet, lon, other, other_lon, sect)
                present = kind in pair["mutual_same_kind"]
                mutual.append(present)
                if present:
                    witnesses.append(other)
            local = None if essential is None else kind in essential["dignities"]
            put(
                code,
                _any([local, _any(mutual)]),
                {
                    "own_dignity": local,
                    "mutual_same_kind_partners": witnesses,
                    "grouped_alternatives_count_once": True,
                },
                [104, 112, 115],
            )
        for code, kind in [("E03", "triplicity"), ("E04", "bound"), ("E05", "face")]:
            value = (
                None
                if essential is None or kind in essential["unknown_dignities"]
                else kind in essential["dignities"]
            )
            put(code, value, {"dignity": kind, "chart_sect": sect}, [104, 115])
        for code, kind in [("E06", "detriment"), ("E07", "fall")]:
            put(
                code,
                None if essential is None else kind in essential["debilities"],
                {"debility": kind},
                [104, 115],
            )
        put(
            "E08",
            None if essential is None else essential["peregrine"],
            {"peregrine_is_separate_from_detriment_and_fall": True},
            [112, 115],
        )
        assignment = state.get("house_assignment")
        house = (
            assignment.get("assigned_house")
            if assignment is not None
            else state.get("occupied_house")
        )
        if house is not None and house not in range(1, 13):
            raise ValueError("Occupied house must be1..12 or unknown")
        for code, houses in [
            ("F01", [1, 10]),
            ("F02", [7, 4, 11]),
            ("F03", [2, 5]),
            ("F04", [9]),
            ("F05", [3]),
            ("D01", [12]),
            ("D02", [8, 6]),
        ]:
            put(
                code,
                None if house is None else house in houses,
                {
                    "occupied_house": state.get("occupied_house"),
                    "scored_house": house,
                    "house_system": house_system,
                    "assignment_policy": (
                        assignment.get("assignment_policy")
                        if assignment is not None
                        else "literal_transcribed_occupancy_no_cusp_inputs_supplied"
                    ),
                    "assignment_status": (
                        None if assignment is None else assignment.get("status")
                    ),
                },
                [33, 115] if assignment is not None else [115],
            )
        motion = physical_inputs.get("motion", {}).get(planet, {})
        direction = motion.get("direction")
        if direction not in {None, "direct", "retrograde", "stationary"}:
            raise ValueError("Invalid motion direction")
        for code, name in [("F06", "direct"), ("D03", "retrograde")]:
            put(
                code,
                None if direction is None else direction == name,
                {"direction": direction, "sun_moon_direct_points_void": True},
                [114, 115],
                planet not in {"Sun", "Moon"},
            )
        daily = motion.get("daily_motion_degrees")
        exact = motion.get("daily_motion_exact_degrees")
        displacement = (
            Fraction(exact)
            if exact is not None
            else None if daily is None else angle_fraction(daily)
        )
        if (
            exact is not None
            and daily is not None
            and displacement is not None
            and float(displacement) != daily
        ):
            raise ValueError(
                "Daily displacement and its exact supplied-value receipt differ"
            )
        magnitude = None if displacement is None else abs(displacement)
        mean = Fraction(MEAN_MOTION_ARCSECONDS[planet], 3600)
        for code, value in [
            ("F07", None if magnitude is None else magnitude > mean),
            ("D04", None if magnitude is None else magnitude < mean),
        ]:
            put(
                code,
                value,
                {
                    "daily_motion_degrees": None if daily is None else float(daily),
                    "comparison_uses_magnitude": True,
                    "daily_motion_exact_degrees": (
                        None if displacement is None else str(displacement)
                    ),
                    "mean_daily_motion_exact_degrees": str(mean),
                    "equality_awards_neither_swift_nor_slow": True,
                    "instantaneous_rate_is_not_daily_displacement": True,
                },
                [MEAN_MOTION_PAGES[planet], 115, 178],
            )
        elongation = None if lon is None or sun is None else (lon - sun) % 360
        occidental = (
            None if elongation is None or elongation in {0, 180} else elongation < 180
        )
        oriental = None if occidental is None else not occidental
        for code, value, eligible in [
            ("F08", oriental, {"Saturn", "Jupiter", "Mars"}),
            ("D05", occidental, {"Saturn", "Jupiter", "Mars"}),
            ("F09", occidental, {"Mercury", "Venus"}),
            ("D06", oriental, {"Mercury", "Venus"}),
            ("F10", occidental, {"Moon"}),
            ("D07", oriental, {"Moon"}),
        ]:
            put(
                code,
                value,
                {
                    "planet_minus_sun_degrees": (
                        None if elongation is None else float(elongation)
                    ),
                    "new_full_and_exact_solar_opposition_boundary_unknown": True,
                },
                [114, 115],
                planet in eligible,
            )
        solar_known = lon is not None and sun is not None
        solar = (
            combustion_state(lon, sun) if lon is not None and sun is not None else None
        )
        for code, solar_kind in [
            ("F11", None),
            ("F12", "cazimi"),
            ("D08", "combust"),
            ("D09", "under_beams"),
        ]:
            put(
                code,
                None if not solar_known else solar == solar_kind,
                {
                    "solar_condition": (
                        "unknown" if not solar_known else solar or "clear_of_beams"
                    ),
                    "free_requires_clear_of_both_combustion_and_beams": True,
                    "printed_worked_example_discrepancy_not_emended": True,
                },
                [113, 115, 179, 180],
                planet != "Sun",
            )

        def contact(
            others: list[str], ray: int
        ) -> tuple[bool | None, list[dict[str, Any]]]:
            candidates, values = [], []
            for other in others:
                if other == planet:
                    continue
                other_lon = longitudes[other]
                gap = (
                    None
                    if lon is None or other_lon is None
                    else angular_separation_fraction(lon, other_lon)
                )
                holds = None if gap is None else gap == ray
                values.append(holds)
                candidates.append(
                    {
                        "other": other,
                        "separation_degrees": None if gap is None else float(gap),
                        "exact_ray": holds,
                    }
                )
            return _any(values), candidates

        for code, others, ray in [
            ("F13", ["Jupiter", "Venus"], 0),
            ("F15", ["Jupiter", "Venus"], 120),
            ("F16", ["Jupiter", "Venus"], 60),
            ("D10", ["Saturn", "Mars"], 0),
            ("D13", ["Saturn", "Mars"], 180),
            ("D14", ["Saturn", "Mars"], 90),
        ]:
            holds, contact_rows = contact(others, ray)
            put(
                code,
                holds,
                {
                    "ray_degrees": ray,
                    "candidates": contact_rows,
                    "partile_policy": "exact_supplied_longitude_ray_no_one_degree_band",
                    "grouped_targets_count_once_self_excluded": True,
                },
                [106, 115],
            )
        north = physical_inputs.get("north_node_longitude")
        for code, opposite in [("F14", False), ("D11", True)]:
            node = (
                None
                if north is None
                else (angle_fraction(north) + (180 if opposite else 0)) % 360
            )
            gap = (
                None
                if node is None or lon is None
                else angular_separation_fraction(lon, node)
            )
            put(
                code,
                None if gap is None else gap == 0,
                {
                    "node_longitude": None if node is None else float(node),
                    "node_model": physical_inputs.get("node_model"),
                    "partile_policy": "exact_supplied_longitude_ray",
                },
                [106, 115],
            )
        saturn, mars = longitudes["Saturn"], longitudes["Mars"]
        between = (
            None
            if lon is None or saturn is None or mars is None
            else bodily_between(lon, saturn, mars)
        )
        put(
            "D12",
            between,
            {
                "policy": "strict_shorter_arc_corporal_containment",
                "no_arbitrary_fifteen_degree_cap": True,
                "full_historical_enclosure_variants_accepted": False,
            },
            [114, 115],
            planet not in {"Saturn", "Mars"},
        )
        for code, star in [("F17", "Regulus"), ("F18", "Spica"), ("D15", "Algol")]:
            star_lon = physical_inputs.get("star_longitudes", {}).get(star)
            gap = (
                None
                if star_lon is None or lon is None
                else angular_separation_fraction(lon, star_lon)
            )
            put(
                code,
                None if gap is None else gap <= STELLAR_ORB_DEGREES[star],
                {
                    "star": star,
                    "longitude": None if star_lon is None else float(star_lon),
                    "separation_degrees": None if gap is None else float(gap),
                    "printed_p115_longitude": PRINTED_STARS[star],
                    "position_policy": physical_inputs.get("star_position_policy"),
                    "orb_degrees": STELLAR_ORB_DEGREES[star],
                    "longitude_only_closed_range": True,
                },
                list(STELLAR_ORB_SOURCE_PAGES[star]),
            )
        rows: list[dict[str, Any]] = []
        for code, group, points, condition in ROW_SPECS:
            holds, applicable, facts, pages = evaluations[code]
            rows.append(
                {
                    "code": code,
                    "group": group,
                    "condition": condition,
                    "label_zh": ROW_LABELS_ZH[code],
                    "points": points,
                    "applicable": applicable,
                    "satisfied": holds if applicable else None,
                    "contribution": (
                        0
                        if not applicable or holds is False
                        else points if holds is True else None
                    ),
                    "status": (
                        "not_applicable"
                        if not applicable
                        else (
                            "unknown"
                            if holds is None
                            else "satisfied" if holds else "not_satisfied"
                        )
                    ),
                    "inputs": facts,
                    "source_pages": pages,
                }
            )
        unknown = [r["code"] for r in rows if r["status"] == "unknown"]
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
        summary = {
            "status": "partial" if unknown else "computed_under_declared_policy",
            "known_fortitudes": positive,
            "known_debilities": negative,
            "known_balance": positive - negative,
            "literal_table_balance": None if unknown else positive - negative,
            "unknown_rows": unknown,
            "applied_conditions": [
                {
                    "code": r["code"],
                    "label_zh": r["label_zh"],
                    "contribution": r["contribution"],
                    "source_pages": r["source_pages"],
                }
                for r in rows
                if r["status"] == "satisfied"
            ],
            "row_count": len(rows),
            "points_are_success_probability": False,
            "conditional_reading_zh": f"{planet}在本次已核定表格行中，助力分值{positive}、减损分值{negative}；尚未知{len(unknown)}行。它们描述所选原典表的条件，不能直接推出所问事情成败，也不等于原书例题或整盘判断已复现。",
        }
        bodies[planet] = {**summary, "rows": rows}
        summaries[planet] = summary
    return {
        "method_id": RULESET,
        "source_url": SOURCE_URL,
        "source_edition": "William Lilly Christian Astrology London1647",
        "source_pages": [
            57,
            61,
            65,
            69,
            72,
            76,
            80,
            104,
            106,
            112,
            113,
            114,
            115,
            178,
            179,
            180,
            181,
        ],
        "row_count_per_planet": len(ROW_SPECS),
        "planets": bodies,
        "summary": summaries,
        "physical_inputs": physical_inputs,
        "solar_policy": solar_condition_policy(),
        "zodiac_type": zodiac_type,
        "house_system": house_system,
        "source_method_scope": (
            "tropical_regiomontanus_literal_rows"
            if house_system == "R" and zodiac_type in {"Tropic", "Tropical"}
            else "other_or_unknown_chart_method_modern_extension"
        ),
        "aggregation_policy": "All satisfied printed rows counted once; grouped alternatives and multiple partners do not multiply a row; unknown rows never imputed zero. This literal rule ledger does not reproduce every pp178-180 worked total.",
        "source_conflicts": [
            "p65 printed mean-motion unit typo, resolved by errata and explicit p17831minutes27seconds",
            "p76 Mercury maximum100arcmin conflicts with p178104arcmin example, not used as rejection bound",
            "p115 clear of both combustion and beams conflicts with some pp179-180 worked credits",
            "p104 daytime Sun triplicity row not credited in p179 Sun worked total",
            "p177 Moon19Leo07 lies within p179 Regulus24Leo six-degree range, but p180 omits that credit",
        ],
        "full_original_text_acceptance": False,
        "full_judgement_accepted": False,
        "real_world_prediction_established": False,
    }
