"""Natal and directional relationship aspects, midpoints and antiscia."""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fatebridge.core.astro.geometry import (
    Angle,
    angle_fraction,
    angular_separation_fraction,
    longitude_float,
)
from fatebridge.core.astro.reference import (
    _TRADITIONAL_PLANET_IDS,
    ASPECTS,
    DEFAULT_PLANET_ORBS,
)
from fatebridge.core.astro.relationship_geometry import midpoint_candidates_fraction

AspectMatch = Tuple[str, Fraction, float, float, Fraction]


def _checked_orb(orb: float) -> Fraction:
    if not math.isfinite(orb) or not 0 <= orb <= 180:
        raise ValueError("Aspect orb must be finite and within 0..180 degrees")
    return Fraction(orb)


def _get_dynamic_orb(
    planet_a_id: str, planet_b_id: str, aspect_name: str, default_orb: float = 6.0
) -> float:
    orb_a = DEFAULT_PLANET_ORBS.get(planet_a_id, default_orb)
    orb_b = DEFAULT_PLANET_ORBS.get(planet_b_id, default_orb)
    base_orb = (orb_a + orb_b) / 2.0

    if aspect_name in {"sextile", "square"}:
        return base_orb * 0.8
    return base_orb


def _build_aspects(
    planets: Iterable[Dict[str, Any]],
    orb: float = 6.0,
    *,
    include_evidence: bool = False,
) -> List[Dict[str, Any]]:
    _checked_orb(orb)
    items = list(planets)
    ranked: List[Tuple[Fraction, Dict[str, Any]]] = []
    for index, first in enumerate(items):
        for second in items[index + 1 :]:
            matched = _match_cross_aspect_fraction(
                first["longitude"],
                second["longitude"],
                orb=orb,
                planet_a_id=first["id"],
                planet_b_id=second["id"],
            )
            if matched is None:
                continue
            fact = {
                "planet_a": first["id"],
                "planet_b": second["id"],
                "aspect": matched[0],
                "orb": float(matched[1]),
            }
            if include_evidence:
                fact.update(
                    {
                        "exact_angle": matched[2],
                        "orb_limit": matched[3],
                        "separation": float(matched[4]),
                        "rule_id": "fatebridge_modern_dynamic_orbs_v1",
                    }
                )
            ranked.append((matched[1], fact))
    ranked.sort(key=lambda row: (row[0], row[1]["planet_a"], row[1]["planet_b"]))
    return [fact for _, fact in ranked]


def _match_cross_aspect_fraction(
    longitude_a: Angle,
    longitude_b: Angle,
    orb: float = 4.0,
    planet_a_id: Optional[str] = None,
    planet_b_id: Optional[str] = None,
) -> Optional[AspectMatch]:
    _checked_orb(orb)
    difference = angular_separation_fraction(longitude_a, longitude_b)
    matched: Optional[AspectMatch] = None
    for aspect_name, exact_angle in ASPECTS:
        current_orb = abs(difference - Fraction(exact_angle))
        dynamic_max_orb = orb
        if planet_a_id and planet_b_id:
            dynamic_max_orb = _get_dynamic_orb(
                planet_a_id, planet_b_id, aspect_name, default_orb=orb
            )

        if current_orb <= _checked_orb(dynamic_max_orb) and (
            matched is None or current_orb < matched[1]
        ):
            matched = (
                aspect_name,
                current_orb,
                exact_angle,
                dynamic_max_orb,
                difference,
            )

    return matched


def _match_cross_aspect(
    longitude_a: float,
    longitude_b: float,
    orb: float = 4.0,
    planet_a_id: Optional[str] = None,
    planet_b_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    matched = _match_cross_aspect_fraction(
        longitude_a, longitude_b, orb, planet_a_id, planet_b_id
    )

    if matched is None:
        return None

    return {
        "aspect": matched[0],
        "delta": float(matched[1]),
    }


def _build_directional_relative_aspects(
    source_planets: List[Dict[str, Any]],
    target_planets: List[Dict[str, Any]],
    orb: float = 4.0,
) -> List[Dict[str, Any]]:
    _checked_orb(orb)
    grouped: List[Dict[str, Any]] = []

    for source_planet in source_planets:
        if source_planet["id"] not in _TRADITIONAL_PLANET_IDS:
            continue

        matches: List[Tuple[Fraction, Dict[str, Any]]] = []
        for target_planet in target_planets:
            if target_planet["id"] not in _TRADITIONAL_PLANET_IDS:
                continue
            matched = _match_cross_aspect_fraction(
                source_planet["longitude"],
                target_planet["longitude"],
                orb=orb,
                planet_a_id=source_planet["id"],
                planet_b_id=target_planet["id"],
            )
            if matched is None:
                continue
            matches.append(
                (
                    matched[1],
                    {
                        "id": target_planet["id"],
                        "aspect": matched[0],
                        "delta": float(matched[1]),
                    },
                )
            )

        if not matches:
            continue

        grouped.append(
            {
                "id": source_planet["id"],
                "objects": [
                    row
                    for _, row in sorted(
                        matches, key=lambda item: (item[0], item[1]["id"])
                    )
                ],
            }
        )

    return grouped


def _flatten_directional_relative_aspects(
    grouped_aspects: List[Dict[str, Any]],
    *,
    source_key: str,
    target_key: str,
) -> List[Dict[str, Any]]:
    flattened: List[Dict[str, Any]] = []
    for item in grouped_aspects:
        source_id = item.get("id")
        if not source_id:
            continue
        for target in item.get("objects", []):
            target_id = target.get("id")
            if not target_id:
                continue
            flattened.append(
                {
                    source_key: source_id,
                    target_key: target_id,
                    "aspect": target["aspect"],
                    "orb": target["delta"],
                }
            )
    return flattened


def _relative_midpoint_catalog_fraction(
    target_planets: List[Dict[str, Any]],
) -> List[Tuple[Fraction, Dict[str, Any]]]:
    midpoint_bodies = [
        item for item in target_planets if item["id"] in _TRADITIONAL_PLANET_IDS
    ]
    catalog: List[Tuple[Fraction, Dict[str, Any]]] = []
    for index, first in enumerate(midpoint_bodies):
        for second in midpoint_bodies[index + 1 :]:
            candidates = midpoint_candidates_fraction(
                first["longitude"], second["longitude"]
            )
            for midpoint_longitude in candidates:
                catalog.append(
                    (
                        midpoint_longitude,
                        {
                            "idA": first["id"],
                            "idB": second["id"],
                            "longitude": longitude_float(midpoint_longitude),
                            "antipodal_inputs": len(candidates) == 2,
                        },
                    )
                )
    return catalog


def _build_directional_relative_midpoints(
    source_planets: List[Dict[str, Any]],
    target_planets: List[Dict[str, Any]],
    orb: float = 3.0,
) -> Dict[str, List[Dict[str, Any]]]:
    _checked_orb(orb)
    target_midpoints = _relative_midpoint_catalog_fraction(target_planets)
    midpoint_hits: Dict[str, List[Dict[str, Any]]] = {}

    for source_planet in source_planets:
        if source_planet["id"] not in _TRADITIONAL_PLANET_IDS:
            continue

        hits: List[Tuple[Fraction, Dict[str, Any]]] = []
        for exact_midpoint, midpoint in target_midpoints:
            matched = _match_cross_aspect_fraction(
                source_planet["longitude"], exact_midpoint, orb=orb
            )
            if matched is None:
                continue
            hits.append(
                (
                    matched[1],
                    {
                        "midpoint": midpoint,
                        "aspect": matched[0],
                        "delta": float(matched[1]),
                    },
                )
            )

        if hits:
            midpoint_hits[source_planet["id"]] = [
                row
                for _, row in sorted(
                    hits,
                    key=lambda item: (
                        item[0],
                        item[1]["midpoint"]["idA"],
                        item[1]["midpoint"]["idB"],
                    ),
                )
            ]

    return midpoint_hits


def _build_directional_relative_antiscia(
    source_planets: List[Dict[str, Any]],
    target_planets: List[Dict[str, Any]],
    *,
    contra: bool = False,
    orb: float = 3.0,
) -> List[Dict[str, Any]]:
    limit = _checked_orb(orb)
    matched_items: List[Tuple[Fraction, Dict[str, Any]]] = []

    for source_planet in source_planets:
        if source_planet["id"] not in _TRADITIONAL_PLANET_IDS:
            continue

        for target_planet in target_planets:
            if target_planet["id"] not in _TRADITIONAL_PLANET_IDS:
                continue
            target = angle_fraction(target_planet["longitude"])
            reference_longitude = -target if contra else 180 - target
            difference = angular_separation_fraction(
                source_planet["longitude"], reference_longitude
            )
            if difference > limit:
                continue
            matched_items.append(
                (
                    difference,
                    {
                        "idA": source_planet["id"],
                        "idB": target_planet["id"],
                        "delta": float(difference),
                    },
                )
            )

    return [
        row
        for _, row in sorted(
            matched_items,
            key=lambda item: (item[0], item[1]["idA"], item[1]["idB"]),
        )
    ]


def _count_directional_relative_midpoint_hits(
    midpoint_hits: Dict[str, List[Dict[str, Any]]],
) -> int:
    return sum(len(items) for items in midpoint_hits.values())
