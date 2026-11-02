"""Directional, natural and conditional aspect strength with explicit sources.

These are separate classical components, never a fabricated Shadbala total.
Mercury's unadjudicated association rule is kept as conditional branches.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

from fatebridge.core.jyotish_sthana import RAMAN_SOURCE
from fatebridge.core.jyotish_strength import SOURCE_ID
from fatebridge.core.jyotish_vargas import longitude_ratio
from fatebridge.utils.errors import JyotishCalculationError

PLANETS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
NATURAL_RANKS = dict(
    zip(("Saturn", "Mars", "Mercury", "Jupiter", "Venus", "Moon", "Sun"), range(1, 8))
)
ASPECT_METHOD = "raman_113_120_additive_specials"


def directed_angle(aspector: float, aspected: float) -> Fraction:
    """Exact binary input ratio prevents subtraction from changing cusp side."""
    a, ad = longitude_ratio(aspector)
    b, bd = longitude_ratio(aspected)
    return (Fraction(b, bd) - Fraction(a, ad)) % 360


def aspect_value(
    aspector: str, aspector_longitude: float, aspected_longitude: float
) -> dict[str, float]:
    """Raman sections113-115: directed base plus literal special additions.

    The book does not adjudicate each endpoint. Use right-hand half-open
    intervals consistently and report that convention; do not hide jumps.
    """
    if aspector not in PLANETS:
        raise ValueError("Quantitative aspects cover the seven physical grahas only")
    angle = directed_angle(aspector_longitude, aspected_longitude)
    if angle < 30 or angle >= 300:
        base = Fraction(0)
    elif angle < 60:
        base = (angle - 30) / 2
    elif angle < 90:
        base = angle - 45
    elif angle < 120:
        base = (120 - angle) / 2 + 30
    elif angle < 150:
        base = 150 - angle
    elif angle < 180:
        base = 2 * (angle - 150)
    else:
        base = (300 - angle) / 2
    extra = 0
    if aspector == "Mars" and (90 <= angle < 120 or 210 <= angle < 240):
        extra = 15
    elif aspector == "Jupiter" and (120 <= angle < 150 or 240 <= angle < 270):
        extra = 30
    elif aspector == "Saturn" and (60 <= angle < 90 or 270 <= angle < 300):
        extra = 45
    return {
        "directed_angle": float(angle),
        "ordinary_virupa": float(base),
        "special_virupa": float(extra),
        "value": float(base + extra),
    }


def directional_strength(raw: dict[str, Any]) -> dict[str, Any]:
    asc, mc = raw["ascendant"], raw["midheaven"]
    exact_angles = {
        "Ascendant": Fraction(asc),
        "Midheaven": Fraction(mc),
        "Descendant": (Fraction(asc) + 180) % 360,
        "ImumCoeli": (Fraction(mc) + 180) % 360,
    }
    angles = {
        "Ascendant": asc,
        "Midheaven": mc,
        "Descendant": float((Fraction(asc) + 180) % 360),
        "ImumCoeli": float((Fraction(mc) + 180) % 360),
    }
    weak = {
        "Sun": "ImumCoeli",
        "Moon": "Midheaven",
        "Mars": "ImumCoeli",
        "Mercury": "Descendant",
        "Jupiter": "Descendant",
        "Venus": "Midheaven",
        "Saturn": "Ascendant",
    }
    summary, evidence = {}, {}
    for planet in PLANETS:
        angle = (Fraction(raw["longitudes"][planet]) - exact_angles[weak[planet]]) % 360
        distance = min(angle, 360 - angle)
        summary[planet] = float(distance / 3)
        evidence[planet] = {
            "powerless_point": weak[planet],
            "powerless_longitude": angles[weak[planet]],
            "planet_longitude": raw["longitudes"][planet],
            "shortest_arc_degrees": float(distance),
        }
    return {
        "status": "computed_under_declared_rule",
        "method": "santhanam_27_7_cardinal_angles",
        "unit": "virupa",
        "source_id": SOURCE_ID,
        "source_section": "27.7, printed p.267",
        "summary": summary,
        "evidence": evidence,
        "basis": {
            "angles": angles,
            "numerical_policy": "Exact given binary longitudes and unrounded opposite points; one final float conversion per arc/value. Displayed opposite-point longitudes are rounded labels, not arithmetic inputs or an astronomical-accuracy claim.",
            "scope": "D1 sidereal physical ecliptic angles using modeled UT1; not whole-sign house starts or a varga transformation",
        },
        "rule_ids": ["jyotish.dig_bala.v1"],
        "interpretation_scope": "directional-strength component, not real-world authority, beneficence or outcome probability",
    }


def natural_strength() -> dict[str, Any]:
    return {
        "status": "computed_under_declared_rule",
        "method": "santhanam_27_14_exact_sevenths",
        "unit": "virupa",
        "source_id": SOURCE_ID,
        "source_section": "27.14, printed p.276",
        "summary": {p: float(Fraction(60 * NATURAL_RANKS[p], 7)) for p in PLANETS},
        "evidence": {
            p: {"rank": NATURAL_RANKS[p], "exact_virupa": f"{60 * NATURAL_RANKS[p]}/7"}
            for p in PLANETS
        },
        "basis": {
            "scope": "fixed traditional coefficients; not observed luminosity, personal strength or modern photometry"
        },
        "rule_ids": ["jyotish.naisargika_bala.v1"],
        "interpretation_scope": "same coefficients for every chart; cannot distinguish individual outcomes",
    }


def moon_nature_readings(elongation: Fraction) -> dict[str, Any]:
    waxing = (
        ["benefic", "malefic"]
        if elongation in {0, 180}
        else ["benefic" if elongation < 180 else "malefic"]
    )
    eighth_day = (
        ["benefic"]
        if 96 <= elongation < 264
        else (
            ["malefic"]
            if elongation < 84 or elongation >= 276
            else ["benefic", "malefic"]
        )
    )
    options = [
        nature
        for nature in ("benefic", "malefic")
        if nature in waxing or nature in eighth_day
    ]
    return {
        "options": options,
        "readings": {
            "raman_117_118_waxing_waning": waxing,
            "raman_53_eighth_day_window": eighth_day,
        },
        "status": "author_readings_not_uniquely_adjudicated",
        "boundary_scope": "eighth-tithi inclusivity unspecified: [84,96) and [264,276) retain both; do not silently choose a 90/270 or 84/276 threshold",
    }


def aspect_strength(longitudes: dict[str, float]) -> dict[str, Any]:
    matrix = {
        p: {q: aspect_value(p, longitudes[p], longitudes[q])["value"] for q in PLANETS}
        for p in PLANETS
    }
    elongation = directed_angle(longitudes["Sun"], longitudes["Moon"])
    nature_readings = moon_nature_readings(elongation)
    moon_options = nature_readings["options"]
    scenarios: dict[str, Any] = {}
    for moon_nature in moon_options:
        for mercury_nature in ("benefic", "malefic"):
            natures = {
                "Sun": "malefic",
                "Moon": moon_nature,
                "Mars": "malefic",
                "Mercury": mercury_nature,
                "Jupiter": "benefic",
                "Venus": "benefic",
                "Saturn": "malefic",
            }
            contributions = {
                target: {
                    p: matrix[p][target] / 4 * (1 if natures[p] == "benefic" else -1)
                    for p in PLANETS
                }
                for target in PLANETS
            }
            scenarios[f"moon_{moon_nature}__mercury_{mercury_nature}"] = {
                "natures": natures,
                "summary": {p: sum(contributions[p].values()) for p in PLANETS},
                "contributions": contributions,
            }
    summary: dict[str, float | None] = {}
    for p in PLANETS:
        values = {s["summary"][p] for s in scenarios.values()}
        summary[p] = next(iter(values)) if len(values) == 1 else None
    pending = [p for p, value in summary.items() if value is None]
    return {
        "status": (
            "conditional_nature_results"
            if pending
            else "same_value_in_all_nature_branches"
        ),
        "method": ASPECT_METHOD,
        "unit": "signed virupa",
        "source_id": RAMAN_SOURCE["id"],
        "source_section": "53 and113-120, printed38,82-88/PDF43,87-93; fixed primary page images checked; worked-table conflicts retained",
        "source_witness": {
            "status": "stated_rules_checked_worked_tables_conflicted",
            "sha256": RAMAN_SOURCE["sha256"],
            "pdf_pages_checked": [43, 87, 88, 89, 90, 91, 92, 93],
            "complete_single_original_accepted": False,
            "scope": "Section113 direction,114 ordinary formula,115 additive specials and120 signed quarter sum; printed examples are counterevidence, not silently amended target values.",
        },
        "source_reading_conflicts": [
            {
                "location": "Example53/PDF88-89",
                "fact": "Mercury header181deg31min disagrees by1minute with twelve displayed row/column differences; Jupiter-to-Mars145deg20min disagrees by10minutes with displayed headings145deg30min.",
                "adjudicated": False,
            },
            {
                "location": "Example54 Jupiter/PDF93",
                "fact": "Listed negative contributions18.43+15.00+42.75+18.75 sum94.93; printed subtotal94.23. Printed net-64.14 also differs from30.79-94.23=-63.44.",
                "adjudicated": False,
            },
            {
                "location": "Examples54-55 Moon/PDF92-93",
                "fact": "46.25-133.18=-86.93, whereas Example54 prints-86.23 and Example55 prints-86.93. Literal witnesses are retained separately.",
                "adjudicated": False,
            },
        ],
        "summary": summary,
        "conditional_targets": pending,
        "scenarios": scenarios,
        "matrix": matrix,
        "nature_context": {
            "moon_directed_elongation": float(elongation),
            "moon_options": moon_options,
            "moon_rule": "Union of Raman117-118 waxing/waning and Raman53 eighth-day window readings; unresolved differences and endpoint bands retain both natures",
            "moon_readings": nature_readings,
            "mercury_options": ["benefic", "malefic"],
            "mercury_status": "association_predicate_not_adjudicated",
            "mercury_rule": "No invented same-sign, distance or solar-orb predicate substituted for author-specific good/bad association",
            "mercury_worked_example": "Example55/PDF93 explicitly labels the standard-horoscope Mercury malefic because of close solar association or combustion; no general numerical orb is supplied there. This example-specific classification does not adjudicate arbitrary charts.",
        },
        "calculation_scope": "target minus aspector modulo360; ordinary strength plus additive special strength, signed by aspector nature, then divided by4. Seven physical bodies only; self-aspect zero.",
        "endpoint_convention": "right-hand half-open intervals [start,end); author endpoint ambiguity not silently adjudicated",
        "source_disagreements": [
            "Additive Saturn special can exceed60 Virupa; no cap invented.",
            "Santhanam26 verse-specific formulas and commentary additive rules differ; this layer explicitly follows Raman113-120.",
            "Santhanam27.19 additionally mentions whole Mercury/Jupiter aspects; Raman120 planetary Drik uses quarter signed sum. House-aspect strength is a separate rule and is not computed here.",
            "Santhanam26 English subtraction wording and target-plus360 instruction conflict; no alternative direction is silently applied to this Raman result.",
            "Santhanam commentary printed257/PDF256 gives Mars210-249, whereas the selected Raman interval ends240. The printed249 is retained as another witness, not repaired to match this method.",
        ],
        "alternative_source_witnesses": {
            "santhanam_26_27_19": {
                "source_id": SOURCE_ID,
                "source_sha256": "13609f1af89541e070c798b8c70c6bfd74a8b9a71a71388913bf898e9f9ddf3f",
                "status": "selected_english_witness_not_uniquely_adjudicated",
                "applied_to_native_drik": False,
                "native_method_unchanged": ASPECT_METHOD,
                "complete_single_original_accepted": False,
                "layers": {
                    "translated_verses": "26.6-12, printed255-256/PDF254-255",
                    "commentary": "printed257-258/PDF256-257",
                    "ordinary_speculum": "printed258-263/PDF257-262 (PDF pages one-based)",
                    "planetary_drik": "27.19, printed284/PDF283",
                },
                "ordinary_speculum": {
                    "printed_cells": 540,
                    "first_angle_degrees": 30,
                    "last_angle_degrees": 299.5,
                    "step_minutes": 30,
                    "unique_literal_coordinates": 538,
                    "ordinary_scalar_relation_conflicts": 2,
                    "literal_coordinate_labels_preserved": True,
                    "terminal300_not_printed": True,
                    "scope": "Printed ordinary scalar rows, including two conflicting coordinate labels; no special-planet, direction, whole-Drik or predictive acceptance follows from the other rows agreeing.",
                },
                "commentary_mars_upper_degree_literal": 249,
                "selected_raman_mars_upper_degree": 240,
                "unresolved": [
                    "Subtraction wording versus wrap direction instruction",
                    "Translated special clauses versus commentary additions",
                    "Mars sum6 fractional-sector coverage",
                    "Special-rule endpoint inclusion",
                    "27.19 entire Mercury/Jupiter aspect clause",
                ],
                "primary_transcription_sha256": "ab77bddd393fe930824c1080f39d0f1b6507b9424952c88b3106e90bbf1e2eba",
                "scope": "Non-applied source witness, not another computed native profile, consensus source, full Shadbala or real-world evidence.",
            }
        },
        "rule_ids": [
            "jyotish.quantitative_drishti.v1",
            "jyotish.drik_bala_conditional.v2",
            "jyotish.moon_nature_readings.v1",
        ],
        "interpretation_scope": "conditional traditional aspect component; null means unresolved classification, not zero or absent influence. Branches are not probability bounds, real-world good/bad outcomes or complete Shadbala.",
    }


def _same_drik_value(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and actual.keys() == expected.keys()
            and all(_same_drik_value(actual[k], v) for k, v in expected.items())
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(_same_drik_value(a, b) for a, b in zip(actual, expected))
        )
    return type(actual) is type(expected) and actual == expected


def verify_drik_evidence(component: dict[str, Any], d1: dict[str, Any]) -> None:
    """Bind the full internal receipt to this D1 before constructing topic prose.

    This re-evaluates the selected domain calculator. It authenticates neither
    the physical birth/ephemeris nor a source edition or predictive model.
    """
    try:
        if (
            type(d1["division"]) is not int
            or d1["division"] != 1
            or d1["method"] != "rasi_whole_sign"
        ):
            raise ValueError("The physical D1 is required for natal Drik")
        longitudes = {}
        for row in d1["planets"]:
            planet = row["id"]
            if planet not in PLANETS:
                continue
            value = row["longitude"]
            if (
                planet in longitudes
                or type(value) not in (int, float)
                or not math.isfinite(value)
                or not 0 <= value < 360
            ):
                raise ValueError("Unique finite physical D1 operands are required")
            longitudes[planet] = value
        if set(longitudes) != set(PLANETS) or not _same_drik_value(
            component, aspect_strength(longitudes)
        ):
            raise ValueError("The Drik calculation and its receipt disagree")
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise JyotishCalculationError("drik_chain_inconsistent") from error


def other_balas(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "dig_bala": directional_strength(raw),
        "naisargika_bala": natural_strength(),
        "drik_bala": aspect_strength(raw["longitudes"]),
        "shadbala_assessment": {
            "status": "not_complete",
            "computed": ["sthana_bala", "dig_bala", "naisargika_bala"],
            "conditional": ["drik_bala"],
            "missing": ["kala_bala", "cheshta_bala"],
            "total_virupa": None,
            "scope": "No sum or sufficiency ranking while required branches and nature adjudication remain incomplete; source profiles remain separate.",
        },
    }
