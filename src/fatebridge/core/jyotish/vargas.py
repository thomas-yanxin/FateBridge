"""Divisional charts (D1-D60 Shodashavarga), Whole Sign & Bhava Chalit houses, and Graha Drishti."""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

from fatebridge.core.astro.astrology_tables import SIGN_LABELS_ZH, SIGNS

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
RASI_LORDS = [
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
]
EXALTATION = {
    "Sun": 0,
    "Moon": 1,
    "Mars": 9,
    "Mercury": 5,
    "Jupiter": 3,
    "Venus": 11,
    "Saturn": 6,
}
EXALTATION_PEAKS = {
    "Sun": 10.0,
    "Moon": 33.0,
    "Mars": 298.0,
    "Mercury": 165.0,
    "Jupiter": 95.0,
    "Venus": 357.0,
    "Saturn": 200.0,
}
MOOLATRIKONA = {
    "Sun": (4, 0, 20),
    "Moon": (1, 3, 30),
    "Mars": (0, 0, 12),
    "Mercury": (5, 15, 20),
    "Jupiter": (8, 0, 10),
    "Venus": (6, 0, 15),
    "Saturn": (10, 0, 20),
}
COMBUSTION_ORBS = {
    "Moon": (12, 12),
    "Mars": (17, 8),
    "Mercury": (14, 12),
    "Jupiter": (11, 11),
    "Venus": (10, 8),
    "Saturn": (16, 16),
}
ASPECT_OFFSETS = {"Mars": [4, 7, 8], "Jupiter": [5, 7, 9], "Saturn": [3, 7, 10]}
SUPPORTED_DIVISIONS = (2, 3, 4, 7, 9, 10, 12, 16, 20, 24, 27, 30, 40, 45, 60)
SHODASHAVARGA_DIVISIONS = (1, *SUPPORTED_DIVISIONS)
SAPTA_DIVISIONS = (1, 2, 3, 7, 9, 12, 30)

NATURAL_RELATIONS = {
    "Sun": ({"Moon", "Mars", "Jupiter"}, {"Venus", "Saturn"}),
    "Moon": ({"Sun", "Mercury"}, set()),
    "Mars": ({"Sun", "Moon", "Jupiter"}, {"Mercury"}),
    "Mercury": ({"Sun", "Venus"}, {"Moon"}),
    "Jupiter": ({"Sun", "Moon", "Mars"}, {"Mercury", "Venus"}),
    "Venus": ({"Mercury", "Saturn"}, {"Sun", "Moon"}),
    "Saturn": ({"Mercury", "Venus"}, {"Sun", "Moon", "Mars"}),
}
COMPOUND_LABELS = {
    -2: "great_enemy",
    -1: "enemy",
    0: "neutral",
    1: "friend",
    2: "great_friend",
}

VARGA_METHODS = {
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
}


def longitude_ratio(longitude: float | Fraction) -> tuple[int, int]:
    if isinstance(longitude, Fraction):
        n, d = longitude.as_integer_ratio()
    else:
        if not math.isfinite(longitude):
            raise ValueError("经度必须为有限数。")
        n, d = float(longitude).as_integer_ratio()
    return n % (360 * d), d


def _varga_components(
    longitude: float | Fraction, division: int
) -> tuple[int, Fraction | None]:
    n, d = longitude_ratio(longitude)
    sign, degree_numerator = divmod(n, 30 * d)
    if division == 1:
        return sign, Fraction(degree_numerator, d)
    if division == 30:
        bounds, destinations = (
            ([5, 10, 18, 25, 30], [0, 10, 8, 2, 6])
            if sign % 2 == 0
            else ([5, 12, 20, 25, 30], [1, 5, 11, 9, 7])
        )
        for end, destination in zip(bounds, destinations):
            if degree_numerator < end * d:
                return destination, None
        raise AssertionError("Normalized longitude must belong to one D30 interval")
    if division not in SUPPORTED_DIVISIONS:
        raise ValueError(
            "仅支持十六分盘（2, 3, 4, 7, 9, 10, 12, 16, 20, 24, 27, 30, 40, 45, 60）。"
        )
    part, remainder = divmod(degree_numerator * division, 30 * d)
    if division == 2:
        destination = ([4, 3] if sign % 2 == 0 else [3, 4])[part]
    elif division == 3:
        destination = (sign + 4 * part) % 12
    elif division == 4:
        destination = (sign + 3 * part) % 12
    elif division == 7:
        destination = (sign + (0 if sign % 2 == 0 else 6) + part) % 12
    elif division == 9:
        destination = ([0, 9, 6, 3][sign % 4] + part) % 12
    elif division == 10:
        destination = (sign + (0 if sign % 2 == 0 else 8) + part) % 12
    elif division in (12, 60):
        destination = (sign + part) % 12
    elif division == 20:
        destination = ([0, 8, 4][sign % 3] + part) % 12
    elif division == 24:
        destination = ((4 if sign % 2 == 0 else 3) + part) % 12
    elif division == 27:
        destination = ([0, 3, 6, 9][sign % 4] + part) % 12
    elif division == 40:
        destination = ((0 if sign % 2 == 0 else 6) + part) % 12
    else:  # D16 and D45
        destination = ([0, 4, 8][sign % 3] + part) % 12
    return destination, Fraction(remainder, d)


def varga_coordinates(
    longitude: float | Fraction, division: int
) -> tuple[int, float | None]:
    sign, degree = _varga_components(longitude, division)
    return sign, (
        None if degree is None else min(float(degree), math.nextafter(30.0, 0.0))
    )


def varga_sign(longitude: float | Fraction, division: int) -> int:
    return _varga_components(longitude, division)[0]


def varga_longitude(longitude: float | Fraction, division: int) -> float:
    sign, degree = _varga_components(longitude, division)
    if degree is None:
        raise ValueError("D30 Trimsamsa 仅定义星座，无唯一分盘度数。")
    exact = sign * 30 + degree
    return min(float(exact), math.nextafter(float((sign + 1) * 30), -math.inf))


def relationship(planet: str, other: str, signs: dict[str, int]) -> dict[str, Any]:
    if planet not in NATURAL_RELATIONS or other not in NATURAL_RELATIONS:
        raise ValueError("Node relationship not assigned")
    if planet == other:
        return {
            "from_planet": planet,
            "to_planet": other,
            "natural": "self",
            "temporary": "na",
            "compound": "self",
        }
    friends, enemies = NATURAL_RELATIONS[planet]
    natural = 1 if other in friends else -1 if other in enemies else 0
    dist = (signs[other] - signs[planet]) % 12 + 1
    temp = 1 if dist in {2, 3, 4, 10, 11, 12} else -1
    return {
        "from_planet": planet,
        "to_planet": other,
        "natural": {1: "friend", 0: "neutral", -1: "enemy"}[natural],
        "temporary": "friend" if temp == 1 else "enemy",
        "compound": COMPOUND_LABELS[natural + temp],
    }


def dignity(planet: str, sign: int) -> dict[str, Any]:
    if planet not in EXALTATION:
        state = "not_assigned"
    elif sign == EXALTATION[planet]:
        state = "exalted"
    elif sign == (EXALTATION[planet] + 6) % 12:
        state = "debilitated"
    elif RASI_LORDS[sign] == planet:
        state = "own_sign"
    else:
        state = "other"
    return {"state": state, "own_sign": RASI_LORDS[sign] == planet}


def partition_longitudes(raw: dict[str, Any]) -> dict[str, float | Fraction]:
    longitudes: dict[str, float | Fraction] = raw["longitudes"]
    return {**longitudes, "Ketu": (Fraction(longitudes["Rahu"]) + 180) % 360}


def _d1_physical_state(
    planet: str,
    lon: float,
    sun_lon: float,
    speed: float,
) -> dict[str, Any]:
    sign = int(lon // 30)
    deg = lon % 30
    baladi_names = ["bala", "kumara", "yuva", "vriddha", "mrita"]
    baladi = (
        baladi_names[min(4, int(deg // 6))]
        if sign % 2 == 0
        else baladi_names[4 - min(4, int(deg // 6))]
    )
    moola = MOOLATRIKONA[planet]
    zone = (
        "moolatrikona"
        if (sign == moola[0] and moola[1] <= deg < moola[2])
        else dignity(planet, sign)["state"]
    )
    state: dict[str, Any] = {
        "retrograde": speed < 0 and planet not in {"Sun", "Moon"},
        "speed_deg_per_day": round(speed, 6),
        "baladi_avastha": baladi,
        "degree_zone": zone,
    }
    if planet in COMBUSTION_ORBS:
        sep = abs(((lon - sun_lon + 180) % 360) - 180)
        orb = COMBUSTION_ORBS[planet][1] if speed < 0 else COMBUSTION_ORBS[planet][0]
        state["combustion"] = {
            "combust": sep < orb,
            "sun_separation_deg": round(sep, 4),
            "orb_deg": orb,
        }
    return state


def divisional_chart(
    raw: dict[str, Any],
    division: int,
    *,
    partition_longitudes_map: dict[str, float | Fraction] | None = None,
) -> dict[str, Any]:
    longitudes = (
        raw["longitudes"]
        if partition_longitudes_map is None
        else partition_longitudes_map
    )
    asc_sign, asc_degree = varga_coordinates(raw["ascendant"], division)
    asc = None if division == 30 else varga_longitude(raw["ascendant"], division)

    planets = []
    for p in GRAHAS:
        sign, degree = varga_coordinates(longitudes[p], division)
        lon = None if division == 30 else varga_longitude(longitudes[p], division)
        planets.append(
            {
                "id": p,
                "label_zh": LABELS[p],
                "longitude": lon,
                "sign": SIGNS[sign],
                "sign_zh": SIGN_LABELS_ZH[SIGNS[sign]],
                "degree_in_sign": degree,
                "house": (sign - asc_sign) % 12 + 1,
                "dignity": dignity(p, sign),
            }
        )

    if division == 1:
        signs = {p["id"]: int(p["longitude"] // 30) for p in planets}
        sun_lon = float(longitudes["Sun"])
        speeds = raw.get("speeds", {})
        for planet in planets:
            pid = planet["id"]
            if pid in EXALTATION:
                planet["physical_state"] = _d1_physical_state(
                    pid, float(longitudes[pid]), sun_lon, float(speeds.get(pid, 1.0))
                )
                planet["dispositor_relationship"] = relationship(
                    pid, RASI_LORDS[signs[pid]], signs
                )

    houses = []
    for house in range(1, 13):
        sign = (asc_sign + house - 1) % 12
        lord = RASI_LORDS[sign]
        placed = next(p for p in planets if p["id"] == lord)
        houses.append(
            {
                "house": house,
                "sign": SIGNS[sign],
                "lord": lord,
                "lord_house": placed["house"],
                "occupants": [p["id"] for p in planets if p["house"] == house],
            }
        )

    aspects = []
    for planet in planets:
        if planet["id"] in {"Rahu", "Ketu"}:
            continue
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
                }
            )

    return {
        "division": division,
        "method": VARGA_METHODS[division],
        "ascendant": {
            "id": "Ascendant",
            "label_zh": "上升",
            "longitude": asc,
            "sign": SIGNS[asc_sign],
            "sign_zh": SIGN_LABELS_ZH[SIGNS[asc_sign]],
            "degree_in_sign": asc_degree,
            "house": 1,
        },
        "planets": planets,
        "houses": houses,
        "graha_aspects": aspects,
    }


def _forward_arc(start: float, end: float) -> float:
    return (end - start) % 360.0


def _angle_in_arc(angle: float, start: float, end: float) -> bool:
    span = _forward_arc(start, end)
    pos = _forward_arc(start, angle)
    return pos < span


def bhava_chalit(
    longitudes: dict[str, float], ascendant: float, midheaven: float
) -> dict[str, Any]:
    """Compute Sripati (Porphyry-style equal quadrant) Bhava midpoints, sandhis, and house shifts."""
    ic = (midheaven + 180.0) % 360.0
    dsc = (ascendant + 180.0) % 360.0
    q1 = _forward_arc(ascendant, ic) / 3.0
    q2 = _forward_arc(ic, dsc) / 3.0
    q3 = _forward_arc(dsc, midheaven) / 3.0
    q4 = _forward_arc(midheaven, ascendant) / 3.0

    cusps = [
        ascendant % 360.0,
        (ascendant + q1) % 360.0,
        (ascendant + 2 * q1) % 360.0,
        ic,
        (ic + q2) % 360.0,
        (ic + 2 * q2) % 360.0,
        dsc,
        (dsc + q3) % 360.0,
        (dsc + 2 * q3) % 360.0,
        midheaven % 360.0,
        (midheaven + q4) % 360.0,
        (midheaven + 2 * q4) % 360.0,
    ]
    # Sandhi (house boundary) = midpoint between adjacent Bhava cusps
    sandhis = [
        (cusps[i] + _forward_arc(cusps[i], cusps[(i + 1) % 12]) / 2.0) % 360.0
        for i in range(12)
    ]
    bhavas = []
    for i in range(12):
        start = sandhis[(i - 1) % 12]
        end = sandhis[i]
        bhavas.append(
            {
                "house": i + 1,
                "cusp": round(cusps[i], 4),
                "start_sandhi": round(start, 4),
                "end_sandhi": round(end, 4),
            }
        )

    asc_sign = int(ascendant // 30)
    placements = {}
    shifted = []
    for planet in GRAHAS:
        lon = float(longitudes[planet]) % 360.0
        rasi_house = (int(lon // 30) - asc_sign) % 12 + 1
        chalit_house = next(
            (
                i + 1
                for i in range(12)
                if _angle_in_arc(lon, sandhis[(i - 1) % 12], sandhis[i])
            ),
            1,
        )
        placements[planet] = {"rasi_house": rasi_house, "bhava_house": chalit_house}
        if rasi_house != chalit_house:
            shifted.append(
                {
                    "planet": planet,
                    "rasi_house": rasi_house,
                    "bhava_house": chalit_house,
                }
            )

    return {
        "method": "sripati_bhava_chalit",
        "cusps": [round(c, 4) for c in cusps],
        "bhavas": bhavas,
        "placements": placements,
        "shifted_planets": shifted,
    }
