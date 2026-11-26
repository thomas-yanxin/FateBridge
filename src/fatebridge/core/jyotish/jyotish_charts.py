"""Build divisional points, whole-sign houses and traditional graha aspects."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from fatebridge.core.astro.astrology_tables import SIGN_LABELS_ZH, SIGNS
from fatebridge.core.jyotish.jyotish_longitude_motion import (
    RULE as LONGITUDE_MOTION_RULE,
)
from fatebridge.core.jyotish.jyotish_relationships import relationship
from fatebridge.core.jyotish.jyotish_vargas import RASI_LORDS as LORDS
from fatebridge.core.jyotish.jyotish_vargas import varga_coordinates, varga_longitude

GRAHAS = [
    "Sun",
    "Moon",
    "Mars",
    "Mercury",
    "Jupiter",
    "Venus",
    "Saturn",
    "Rahu",
    "Ketu",
]


LABELS = dict(
    zip(
        GRAHAS, ["太阳", "月亮", "火星", "水星", "木星", "金星", "土星", "罗睺", "计都"]
    )
)


EXALTATION = {
    "Sun": 0,
    "Moon": 1,
    "Mars": 9,
    "Mercury": 5,
    "Jupiter": 3,
    "Venus": 11,
    "Saturn": 6,
}


ASPECT_OFFSETS = {"Mars": [4, 7, 8], "Jupiter": [5, 7, 9], "Saturn": [3, 7, 10]}


def dignity(planet: str, sign: int) -> dict[str, Any]:
    if planet not in EXALTATION:
        state = "not_assigned"
    elif sign == EXALTATION[planet]:
        state = "exalted"
    elif sign == (EXALTATION[planet] + 6) % 12:
        state = "debilitated"
    elif LORDS[sign] == planet:
        state = "own_sign"
    else:
        state = "other"
    return {
        "state": state,
        "own_sign": LORDS[sign] == planet,
        "rule_id": "jyotish.sign_dignity.v1",
        "scope": "sign-level only; no shadbala, moolatrikona degree ranges or node dignity doctrine",
    }


def point_record(
    planet: str,
    longitude: float | None,
    asc_sign: int,
    *,
    sign_index: int,
    degree_in_sign: float | None,
) -> dict[str, Any]:
    """Keep both independently rendered coordinates from the same varga result."""
    sign = sign_index
    return {
        "id": planet,
        "label_zh": LABELS.get(planet, "上升"),
        "longitude": longitude,
        "sign": SIGNS[sign],
        "sign_zh": SIGN_LABELS_ZH[SIGNS[sign]],
        "degree_in_sign": degree_in_sign,
        "house": (sign - asc_sign) % 12 + 1,
        "dignity": dignity(planet, sign),
    }


def partition_longitudes(raw: dict[str, Any]) -> dict[str, float | Fraction]:
    """Keep the exact antipode through partitions of ephemeris-derived Ketu."""
    longitudes: dict[str, float | Fraction] = raw["longitudes"]
    if (
        raw.get("nonphysical_factor_models", {}).get("Ketu")
        == "derived_antipode_of_Rahu"
    ):
        return {**longitudes, "Ketu": (Fraction(longitudes["Rahu"]) + 180) % 360}
    return longitudes


def divisional_chart(
    raw: dict[str, Any],
    division: int,
    *,
    partition_longitudes: dict[str, float | Fraction] | None = None,
) -> dict[str, Any]:
    longitudes = (
        raw["longitudes"] if partition_longitudes is None else partition_longitudes
    )
    asc_sign, asc_degree = varga_coordinates(raw["ascendant"], division)
    asc = None if division == 30 else varga_longitude(raw["ascendant"], division)
    planets = []
    for p in GRAHAS:
        sign, degree = varga_coordinates(longitudes[p], division)
        longitude = None if division == 30 else varga_longitude(longitudes[p], division)
        planets.append(
            point_record(p, longitude, asc_sign, sign_index=sign, degree_in_sign=degree)
        )
    if division == 1:
        signs = {p["id"]: int(p["longitude"] // 30) for p in planets}
        for planet in planets:
            interpretation = (
                raw.get("apparent_position_policy", {})
                .get("bodies", {})
                .get(planet["id"])
            )
            if interpretation is not None:
                planet["native_position_interpretation"] = interpretation
            if planet["id"] in raw.get("physical_states", {}):
                planet["physical_state"] = raw["physical_states"][planet["id"]]
            if planet["id"] in EXALTATION:
                planet["dispositor_relationship"] = relationship(
                    planet["id"], LORDS[signs[planet["id"]]], signs
                )
    houses = []
    for house in range(1, 13):
        sign = (asc_sign + house - 1) % 12
        lord = LORDS[sign]
        placed = next(p for p in planets if p["id"] == lord)
        houses.append(
            {
                "house": house,
                "sign": SIGNS[sign],
                "lord": lord,
                "lord_house": placed["house"],
                "lord_dignity": placed["dignity"],
                "occupants": [p["id"] for p in planets if p["house"] == house],
            }
        )
    aspects = []
    for planet in planets:
        if planet["id"] in {"Rahu", "Ketu"}:
            continue  # Node aspect doctrines differ; this ruleset assigns none.
        for distance in ASPECT_OFFSETS.get(planet["id"], [7]):
            target = (planet["house"] + distance - 2) % 12 + 1
            aspects.append(
                {
                    "from_planet": planet["id"],
                    "from_house": planet["house"],
                    "distance": distance,
                    "target_house": target,
                    "target_planets": [
                        p["id"] for p in planets if p["house"] == target
                    ],
                    "rule_id": "jyotish.graha_drishti.v1",
                }
            )
    return {
        "division": division,
        "method": {
            1: "rasi_whole_sign",
            2: "parashari_hora_sun_moon",
            3: "parashari_drekkana_trines",
            4: "parashari_chaturthamsa",
            7: "parashari_saptamsa",
            9: "parashari_navamsa",
            10: "parashari_dasamsa",
            12: "parashari_dvadasamsa",
            16: "parashari_shodasamsa",
            20: "parashari_vimsamsa",
            24: "parashari_chaturvimsamsa",
            27: "parashari_saptavimsamsa",
            30: "parashari_trimsamsa_unequal_signs_only",
            40: "parashari_khavedamsa",
            45: "parashari_akshavedamsa",
            60: "parashari_shashtiamsa",
        }[division],
        "coordinate_scope": (
            "sign assignment only; source does not specify a unique within-sign degree"
            if division == 30
            else (
                "linearly transformed varga coordinates; not physical sky longitude"
                if division != 1
                else "sidereal ecliptic longitude"
            )
        ),
        "ascendant": point_record(
            "Ascendant", asc, asc_sign, sign_index=asc_sign, degree_in_sign=asc_degree
        ),
        "planets": planets,
        "houses": houses,
        "graha_aspects": aspects,
        "rule_ids": [
            (
                "jyotish.extended_varga.v1"
                if division in {2, 3, 4, 7, 12, 16, 20, 24, 27, 30, 40, 45, 60}
                else "jyotish.varga.v1"
            ),
            "jyotish.house_lords.v1",
            "jyotish.sign_dignity.v1",
            "jyotish.graha_drishti.v1",
            *(
                [
                    "jyotish.bphs_degree_zones.v1",
                    "jyotish.bphs_uchcha_bala.v1",
                    "jyotish.bphs_baladi.v1",
                    LONGITUDE_MOTION_RULE,
                    "jyotish.satyacharya_relationships.v1",
                    "jyotish.santhanam_solar_orb.v1",
                ]
                if division == 1
                else []
            ),
        ],
    }
