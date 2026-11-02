"""A bounded Tetrabiblos reference layer, never a blended dignity score.

Claudius Ptolemy, Tetrabiblos, F. E. Robbins (Loeb, 1940), I.7, I.13-21.
In I.18 Mars governs the water triangle WITH Venus by day / Moon by night.
Neither a single water lord nor Dorotheus' three rotating rulers reproduces
that passage. The Fortune formula in III.10 is exposed separately from reversing lots;
The three reported term systems stay separate; no dignity score,
degree-exaltations or lifespan judgements are inferred here.
"""

from __future__ import annotations

from typing import Any, Dict

from fatebridge.core.astro.geometry import combine_longitudes, normalize_angle
from fatebridge.core.astrology_tables import (
    ELEMENT_BY_SIGN,
    EXALTATION_SIGNS,
    RULER_BY_SIGN,
    SIGNS,
)
from fatebridge.core.classical_western import (
    orientality,
    orientality_policy,
    planet_sect,
)
from fatebridge.core.ptolemy_terms import (
    SCAN_URL,
    TERM_POLICY,
    TRANSCRIPTION_NOTE,
    terms_at,
)

SOURCE_URL = (
    "https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Ptolemy/Tetrabiblos/1B%2A.html"
)
FORTUNE_SOURCE_URL = "https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Ptolemy/Tetrabiblos/3B%2A.html#10"
RULESET_ID = "ptolemy_tetrabiblos_robbins_1940_bounded_v4"
_TRIANGLES = {
    "Fire": {"day": "Sun", "night": "Jupiter"},
    "Earth": {"day": "Venus", "night": "Moon"},
    "Air": {"day": "Saturn", "night": "Mercury"},
}
_TRIANGLE_ASSIGNMENTS = {
    "Fire": ("Sun", "Jupiter"),
    "Earth": ("Moon", "Venus"),
    "Air": ("Saturn", "Mercury"),
    "Water": ("Mars", "Moon", "Venus"),
}

_SIGN_ASPECTS = {
    2: ("sextile", "harmonious"),
    3: ("square", "disharmonious"),
    4: ("trine", "harmonious"),
    6: ("opposition", "disharmonious"),
}


def sign_relationship(sign_a: str, sign_b: str) -> Dict[str, Any]:
    """Robbins I.13-16 sign relationships, independent of degree orbs.

    I.16 excludes the other stated familiarities before calling a pair disjunct.
    The northern summer/winter hemispheres are the original text's convention,
    not a recomputation of the native's local season or horizon.
    """
    a, b = SIGNS.index(sign_a), SIGNS.index(sign_b)
    distance = min((a - b) % 12, (b - a) % 12)
    aspect, quality = _SIGN_ASPECTS.get(distance, (None, None))
    commanding = (a + b) % 12 == 11
    beholding = (a + b) % 12 == 5
    summer_sign = sign_a if a < 6 else sign_b
    winter_sign = sign_b if a < 6 else sign_a
    return {
        "sign_a": sign_a,
        "sign_b": sign_b,
        "separation_signs": distance,
        "same_sign": a == b,
        "sign_aspect": aspect,
        "aspect_quality": quality,
        "commanding_sign": summer_sign if commanding else None,
        "obeying_sign": winter_sign if commanding else None,
        "beholding_equal_power": beholding,
        "disjunct": distance in {1, 5} and not (commanding or beholding),
        "chapter_refs": ["I.13", "I.14", "I.15", "I.16"],
    }


def triplicity_assigned_rulers(sign: str) -> list[str]:
    """I.18 overall assignment, distinct from governance under a named sect.

    A listed planet's general familiarity is not a claim that it holds the
    selected primary/explicit co-ruler role in both conditions, or a score.
    """
    return list(_TRIANGLE_ASSIGNMENTS[ELEMENT_BY_SIGN[sign]])


def triplicity_rulers(sign: str, chart_sect: str) -> Dict[str, str | None]:
    """I.18 selected primary/explicit co-ruler roles under a named condition.

    Water retains Mars and its sect-dependent co-ruler. This is not the
    Dorothean ordering of three successive rulers. Other overall assignments
    remain available through triplicity_assigned_rulers, not inferred absent.
    """
    if chart_sect not in {"day", "night"}:
        raise ValueError("Triplicity requires an explicit day or night condition")
    element = ELEMENT_BY_SIGN[sign]
    return {
        "primary": "Mars" if element == "Water" else _TRIANGLES[element][chart_sect],
        "co_ruler": (
            ("Venus" if chart_sect == "day" else "Moon") if element == "Water" else None
        ),
    }


def fortune_longitude(ascendant: float, sun: float, moon: float) -> float:
    """Robbins 1940 III.10 main-text formula, identical by day and night."""
    return combine_longitudes(ascendant, moon, -sun)


def build_ptolemy_layer(
    longitudes: Dict[str, float],
    chart_sect: str,
    *,
    tropical: bool,
    ascendant: float | None = None,
) -> Dict[str, Any]:
    """Compute only the named edition's explicit, supported relationships."""
    result: Dict[str, Any] = {
        "ruleset_id": RULESET_ID,
        "author": "Claudius Ptolemy",
        "edition": "Tetrabiblos; F. E. Robbins; Loeb Classical Library; 1940",
        "source_url": SOURCE_URL,
        "chapters": {
            "planet_sect": "I.7",
            "sign_relationships": "I.13-16",
            "domicile": "I.17",
            "triplicity": "I.18",
            "exaltation_depression": "I.19",
            "terms": "I.20-21 (three reported systems; printed main tables)",
            "lot_of_fortune": "III.10 (Fortune formula only)",
        },
        "status": "computed_subset" if tropical else "unsupported_zodiac",
        "scope": "Tropical signs; seven planets; sect, sign relationships, domicile, triangle, exaltation, depression, three reported term systems and the III.10 Fortune formula only",
        "term_policy": TERM_POLICY,
        "term_source_url": SCAN_URL,
        "term_transcription_note": TRANSCRIPTION_NOTE,
        "planets": {},
        "lot_of_fortune": None,
        "sign_relationships": [],
        "sign_relationship_policy": "Robbins I.13-16; whole signs; I.16 excludes I.14/I.15 familiarities; northern hemisphere convention",
    }
    if not tropical:
        return result
    result["orientality_policy"] = orientality_policy()
    if ascendant is not None and "Sun" in longitudes and "Moon" in longitudes:
        fortune = fortune_longitude(ascendant, longitudes["Sun"], longitudes["Moon"])
        result["lot_of_fortune"] = {
            "formula": "ascendant + Moon - Sun (day and night)",
            "longitude": fortune,
            "sign": SIGNS[int(fortune // 30)],
            "degree_in_sign": fortune % 30,
            "source_url": FORTUNE_SOURCE_URL,
        }
    for planet in EXALTATION_SIGNS:
        if planet not in longitudes:
            continue
        longitude = normalize_angle(longitudes[planet])
        sign = SIGNS[int(longitude // 30)]
        triangle = triplicity_rulers(sign, chart_sect)
        own_exaltation = EXALTATION_SIGNS[planet]
        depression = SIGNS[(SIGNS.index(own_exaltation) + 6) % 12]
        solar_lon = longitudes.get("Sun")
        orient = None if planet == "Sun" else orientality(longitude, solar_lon)
        result["planets"][planet] = {
            "longitude": longitude,
            "sign": sign,
            "degree_in_sign": longitude % 30.0,
            "domicile_lord": RULER_BY_SIGN[sign],
            "in_domicile": RULER_BY_SIGN[sign] == planet,
            "in_exaltation": sign == own_exaltation,
            "in_depression": sign == depression,
            "triplicity_primary": triangle["primary"],
            "triplicity_co_ruler": triangle["co_ruler"],
            "natural_sect": planet_sect(planet, orient),
            "terms": terms_at(longitude, chart_sect),
        }
    planets = list(result["planets"])
    for index, planet_a in enumerate(planets):
        for planet_b in planets[index + 1 :]:
            result["sign_relationships"].append(
                {
                    "planet_a": planet_a,
                    "planet_b": planet_b,
                    **sign_relationship(
                        result["planets"][planet_a]["sign"],
                        result["planets"][planet_b]["sign"],
                    ),
                }
            )
    return result
