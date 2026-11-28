"""Shared Western chart point, label, bound, arc, and aspect-hit primitives."""

from __future__ import annotations

import math
from collections.abc import Mapping
from fractions import Fraction
from typing import Any

from fatebridge.core.astro.astrology_tables import (
    EGYPTIAN_BOUNDS_BY_SIGN,
    SIGN_LABELS_ZH,
    SIGNS,
)
from fatebridge.core.astro.geometry import (
    Angle,
    angular_separation_fraction,
    longitude_float,
    normalize_angle,
)
from fatebridge.core.astro.native_chart import NativePoint, NativeSubject

TIMING_POINT_NAMES = [
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Ascendant",
    "Medium_Coeli",
]
TRANSIT_POINT_NAMES = [
    *TIMING_POINT_NAMES,
    "Uranus",
    "Neptune",
    "Pluto",
]

POINT_ATTRIBUTE_NAMES = {
    "Sun": "sun",
    "Moon": "moon",
    "Mercury": "mercury",
    "Venus": "venus",
    "Mars": "mars",
    "Jupiter": "jupiter",
    "Saturn": "saturn",
    "Uranus": "uranus",
    "Neptune": "neptune",
    "Pluto": "pluto",
    "Ascendant": "ascendant",
    "Medium_Coeli": "medium_coeli",
}

SIGN_ABBREVIATIONS = {
    "Ari": "Aries",
    "Tau": "Taurus",
    "Gem": "Gemini",
    "Can": "Cancer",
    "Leo": "Leo",
    "Vir": "Virgo",
    "Lib": "Libra",
    "Sco": "Scorpio",
    "Sag": "Sagittarius",
    "Cap": "Capricorn",
    "Aqu": "Aquarius",
    "Pis": "Pisces",
}

PLANET_LABELS = {
    "Sun": "太阳",
    "Moon": "月亮",
    "Mercury": "水星",
    "Venus": "金星",
    "Mars": "火星",
    "Jupiter": "木星",
    "Saturn": "土星",
    "Uranus": "天王星",
    "Neptune": "海王星",
    "Pluto": "冥王星",
    "Ascendant": "上升点",
    "Medium_Coeli": "天顶",
    "North Node": "北交点",
    "South Node": "南交点",
    "Fortune": "幸运点",
    "Spirit": "精神点",
    "Eros": "爱神点",
}

HOUSE_NAME_TO_NUMBER = {
    "First_House": 1,
    "Second_House": 2,
    "Third_House": 3,
    "Fourth_House": 4,
    "Fifth_House": 5,
    "Sixth_House": 6,
    "Seventh_House": 7,
    "Eighth_House": 8,
    "Ninth_House": 9,
    "Tenth_House": 10,
    "Eleventh_House": 11,
    "Twelfth_House": 12,
}

ASPECT_DEGREES = [
    ("conjunction", "合相", 0.0),
    ("sextile", "六合", 60.0),
    ("square", "刑", 90.0),
    ("trine", "拱", 120.0),
    ("opposition", "冲", 180.0),
]
# Degree -> (key, label) for O(1) aspect-meta lookup. ASPECT_DEGREES above stays
# the single source of truth; this index is derived from it once at import.
ASPECT_DEGREE_TO_META = {
    int(value): (key, label) for key, label, value in ASPECT_DEGREES
}
SWISSEPH_PLANET_IDS = {
    "Sun": 0,
    "Moon": 1,
    "Mercury": 2,
    "Venus": 3,
    "Mars": 4,
    "Jupiter": 5,
    "Saturn": 6,
}


def normalize_sign_name(sign_name: str) -> str:
    return SIGN_ABBREVIATIONS.get(sign_name, sign_name)


def sign_label(sign_name: str) -> str:
    normalized = normalize_sign_name(sign_name)
    return f"{SIGN_LABELS_ZH.get(normalized, normalized)}座"


def planet_label(planet_name: str) -> str:
    return PLANET_LABELS.get(planet_name, planet_name)


def resolve_egyptian_bound(sign_name: str, degree_in_sign: float) -> dict[str, Any]:
    normalized_sign = normalize_sign_name(sign_name)
    for lord, start_degree, end_degree in EGYPTIAN_BOUNDS_BY_SIGN.get(
        normalized_sign, []
    ):
        if start_degree <= degree_in_sign < end_degree:
            return {
                "bound_lord": lord,
                "bound_lord_label": planet_label(lord),
                "segment_start_degree": round(start_degree, 4),
                "segment_end_degree": round(end_degree, 4),
            }
    raise ValueError("Egyptian bounds require a known sign and a degree in [0, 30)")


def house_number(house_name: str | None) -> int | None:
    if house_name is None:
        return None
    return HOUSE_NAME_TO_NUMBER.get(house_name)


def house_label(house_name: str | None) -> str | None:
    number = house_number(house_name)
    if number is None:
        return None
    return f"第{number}宫"


def point_attribute_name(point_name: str) -> str:
    return POINT_ATTRIBUTE_NAMES.get(point_name, point_name.lower())


def point_absolute_position(subject: NativeSubject, point_name: str) -> float:
    point = getattr(subject, point_attribute_name(point_name))
    return float(point.abs_pos)


def point_to_dict(point_name: str, point: NativePoint) -> dict[str, Any]:
    sign_name = normalize_sign_name(point.sign)
    house_name = point.house
    return {
        "point": point_name,
        "point_label": planet_label(point_name),
        "sign": sign_name,
        "sign_label": sign_label(sign_name),
        "degree": float(point.position),
        "absolute_degree": float(point.abs_pos),
        "longitude": float(point.abs_pos),
        "house": house_number(house_name),
        "house_label": house_label(house_name),
        "retrograde": point.retrograde,
    }


def longitude_to_point_dict(point_name: str, absolute_degree: Angle) -> dict[str, Any]:
    if isinstance(absolute_degree, Fraction):
        sign_index, degree = divmod(absolute_degree % 30, 30)
        normalized_degree = longitude_float(absolute_degree)
        displayed_degree = float(degree)
        # Preserve ownership of whole-degree table intervals in the public record.
        if int(displayed_degree) != int(degree):
            displayed_degree = math.nextafter(displayed_degree, -math.inf)
    else:
        normalized_degree = normalize_angle(absolute_degree)
        sign_index = int(normalized_degree // 30)
        displayed_degree = normalized_degree % 30
    sign_name = SIGNS[sign_index]
    return {
        "point": point_name,
        "point_label": planet_label(point_name),
        "sign": sign_name,
        "sign_label": sign_label(sign_name),
        "degree": displayed_degree,
        "absolute_degree": normalized_degree,
        "longitude": normalized_degree,
    }


def source_arc_positions(
    natal_longitudes: Mapping[str, float],
    natal_source: float,
    progressed_source: float,
) -> tuple[Fraction, dict[str, Fraction]]:
    """Retain one source displacement through rotations and aspect decisions."""
    arc = (Fraction(progressed_source) - Fraction(natal_source)) % 360
    directed = {
        name: (Fraction(longitude) + arc) % 360
        for name, longitude in natal_longitudes.items()
    }
    return arc, directed


def collect_aspect_hits(
    *,
    source_longitudes: Mapping[str, Angle],
    target_longitudes: Mapping[str, Angle],
    orb_limit: float = 1.5,
) -> list[dict[str, Any]]:
    if not math.isfinite(orb_limit) or not 0 <= orb_limit <= 180:
        raise ValueError("Aspect orb must be finite and within 0..180 degrees")
    limit = Fraction(orb_limit)
    hits = []
    for source_name, source_longitude in source_longitudes.items():
        for target_name, target_longitude in target_longitudes.items():
            difference = angular_separation_fraction(source_longitude, target_longitude)
            for aspect_key, aspect_label_text, aspect_degree in ASPECT_DEGREES:
                orb = abs(difference - Fraction(aspect_degree))
                if orb <= limit:
                    hits.append(
                        (
                            orb,
                            {
                                "source": source_name,
                                "source_label": planet_label(source_name),
                                "target": target_name,
                                "target_label": planet_label(target_name),
                                "aspect": aspect_key,
                                "aspect_label": aspect_label_text,
                                "orb": float(orb),
                            },
                        )
                    )
    hits.sort(key=lambda item: item[0])
    return [row for _, row in hits]
