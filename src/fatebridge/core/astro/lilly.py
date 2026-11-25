"""Lilly's selected 1647 dignity table and directional reception conditions.

The p.104 heading says 'according to Ptolomy'; its cells are not the same
as Robbins' 1940 table. Keep this edition separate from both that table and
the Egyptian/Dorothean eclectic layer. No outcome is inferred here.
"""

from __future__ import annotations

from typing import Any, Iterable

from fatebridge.core.astro.geometry import Angle, angle_fraction, longitude_float

RULESET = "lilly_christian_astrology_1647_p104_112_v1"
SOURCE_URL = "https://wellcomecollection.org/works/s7z7c46y"
SIGNS = (
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
)
DOMICILES = (
    "Mars",
    "Venus",
    "Mercury",
    "Moon",
    "Sun",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Saturn",
    "Jupiter",
)
EXALTATIONS = {
    "Sun": (0, 19),
    "Moon": (1, 3),
    "Jupiter": (3, 15),
    "Mercury": (5, 15),
    "Saturn": (6, 21),
    "Mars": (9, 28),
    "Venus": (11, 27),
}
PLANETS = frozenset(EXALTATIONS)
KINDS = ("rulership", "exaltation", "triplicity", "bound", "face")
# Cumulative endpoints manually read from Lilly p.104, not another edition.
TERMS = (
    (("Jupiter", 6), ("Venus", 14), ("Mercury", 21), ("Mars", 26), ("Saturn", 30)),
    (("Venus", 8), ("Mercury", 15), ("Jupiter", 22), ("Saturn", 26), ("Mars", 30)),
    (("Mercury", 7), ("Jupiter", 14), ("Venus", 21), ("Saturn", 25), ("Mars", 30)),
    (("Mars", 6), ("Jupiter", 13), ("Mercury", 20), ("Venus", 27), ("Saturn", 30)),
    (("Saturn", 6), ("Mercury", 13), ("Venus", 19), ("Jupiter", 25), ("Mars", 30)),
    (("Mercury", 7), ("Venus", 13), ("Jupiter", 18), ("Saturn", 24), ("Mars", 30)),
    (("Saturn", 6), ("Venus", 11), ("Jupiter", 19), ("Mercury", 24), ("Mars", 30)),
    (("Mars", 6), ("Jupiter", 14), ("Venus", 21), ("Mercury", 27), ("Saturn", 30)),
    (("Jupiter", 8), ("Venus", 14), ("Mercury", 19), ("Saturn", 25), ("Mars", 30)),
    (("Venus", 6), ("Mercury", 12), ("Jupiter", 19), ("Mars", 25), ("Saturn", 30)),
    (("Saturn", 6), ("Mercury", 12), ("Venus", 20), ("Jupiter", 25), ("Mars", 30)),
    (("Venus", 8), ("Jupiter", 14), ("Mercury", 20), ("Mars", 26), ("Saturn", 30)),
)
TRIPLICITIES = (
    ("Sun", "Jupiter"),
    ("Venus", "Moon"),
    ("Saturn", "Mercury"),
    ("Mars", "Mars"),
)
FACES = (
    ("Mars", "Sun", "Venus"),
    ("Mercury", "Moon", "Saturn"),
    ("Jupiter", "Mars", "Sun"),
    ("Venus", "Mercury", "Moon"),
    ("Saturn", "Jupiter", "Mars"),
    ("Sun", "Venus", "Mercury"),
    ("Moon", "Saturn", "Jupiter"),
    ("Mars", "Sun", "Venus"),
    ("Mercury", "Moon", "Saturn"),
    ("Jupiter", "Mars", "Sun"),
    ("Venus", "Mercury", "Moon"),
    ("Saturn", "Jupiter", "Mars"),
)


def dignity_at(planet: str, longitude: Angle, sect: str | None) -> dict[str, Any]:
    """Five positive dignities and separate debilities, at unrounded longitude.

    Exaltation dignity is sign-wide; the table's particular exaltation degree
    is recorded separately. Unspecified sect cannot become an invented night
    chart. Peregrine means no positive dignity, even when also fallen (p.112).
    """
    if planet not in PLANETS or sect not in {"day", "night", None}:
        raise ValueError(
            "Lilly dignity requires a traditional planet and explicit or unknown sect"
        )
    value = angle_fraction(longitude) % 360
    index, degree = int(value // 30), value % 30
    start = 0
    for term_lord, end in TERMS[index]:
        if degree < end:
            break
        start = end
    day, night = TRIPLICITIES[index % 4]
    triplicity = (
        day
        if sect == "day"
        else night if sect == "night" else day if day == night else None
    )
    triplicity_holds = (
        planet == triplicity
        if triplicity is not None
        else None if planet in {day, night} else False
    )
    exalted = next(
        (body for body, (sign, _) in EXALTATIONS.items() if sign == index), None
    )
    lords = {
        "rulership": DOMICILES[index],
        "exaltation": exalted,
        "triplicity": triplicity,
        "bound": term_lord,
        "face": FACES[index][int(degree // 10)],
    }
    holds: dict[str, bool | None] = {
        kind: planet == lord for kind, lord in lords.items()
    }
    holds["triplicity"] = triplicity_holds
    known = [kind for kind in KINDS if holds[kind] is True]
    unknown = [kind for kind in KINDS if holds[kind] is None]
    opposite = (index + 6) % 12
    debilities = []
    if DOMICILES[opposite] == planet:
        debilities.append("detriment")
    if EXALTATIONS[planet][0] == opposite:
        debilities.append("fall")
    return {
        "rule_id": RULESET,
        "status": "partial" if unknown else "computed",
        "planet": planet,
        "longitude": longitude_float(value),
        "sign": SIGNS[index],
        "degree_in_sign": longitude_float(degree),
        "chart_sect": sect,
        "dignities": known,
        "unknown_dignities": unknown,
        "debilities": debilities,
        "peregrine": False if known else None if unknown else True,
        "lords": lords,
        "bound_start_degree": start,
        "bound_end_degree": end,
        "exaltation_degree_in_sign": EXALTATIONS[exalted][1] if exalted else None,
        "source_pages": [104, 105, 112],
        "boundary_policy": "Exact supplied longitude; half-open term/face/sign intervals; exaltation sign-wide, degree separately recorded",
    }


def reception(
    receiver: str,
    guest: str,
    guest_longitude: Angle,
    sect: str | None,
    *,
    allowed: Iterable[str] = KINDS,
) -> dict[str, Any]:
    """Receiver holds dignity at guest's place; do not reverse this direction."""
    if guest not in PLANETS or receiver == guest:
        raise ValueError(
            "Distinct traditional planets required for directional reception"
        )
    allowed = tuple(allowed)
    if not set(allowed) <= set(KINDS):
        raise ValueError("Unknown essential dignity")
    placement = dignity_at(receiver, guest_longitude, sect)
    held = [kind for kind in placement["dignities"] if kind in allowed]
    unknown = [kind for kind in placement["unknown_dignities"] if kind in allowed]
    return {
        "rule_id": RULESET,
        "receiver": receiver,
        "guest": guest,
        "guest_longitude": placement["longitude"],
        "guest_sign": placement["sign"],
        "chart_sect": sect,
        "allowed_dignities": list(allowed),
        "dignities": held,
        "unknown_dignities": unknown,
        "receives": True if held else None if unknown else False,
        "source_pages": [104, 105, 112],
    }


def pair_reception(
    first: str,
    first_longitude: Angle,
    second: str,
    second_longitude: Angle,
    sect: str | None,
) -> dict[str, Any]:
    if (
        first not in PLANETS
        or second not in PLANETS
        or sect not in {"day", "night", None}
    ):
        raise ValueError("Traditional planets and explicit or unknown sect required")
    angle_fraction(first_longitude)
    angle_fraction(second_longitude)
    if first == second:
        return {
            "rule_id": RULESET,
            "status": "same_body_not_bilateral",
            "directions": [],
            "mutual": None,
            "mutual_same_kind": [],
        }
    directions = [
        reception(first, second, second_longitude, sect),
        reception(second, first, first_longitude, sect),
    ]
    values = [row["receives"] for row in directions]
    return {
        "rule_id": RULESET,
        "status": "partial" if None in values else "computed",
        "directions": directions,
        "mutual": False if False in values else None if None in values else True,
        "mutual_same_kind": [
            kind
            for kind in KINDS
            if all(kind in row["dignities"] for row in directions)
        ],
    }
