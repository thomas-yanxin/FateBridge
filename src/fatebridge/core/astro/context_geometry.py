"""Unrounded geometry for optional sky context, from one core calculation.

Formatting must not decide signs, derived points or cusp membership. The lot
uses the shared LOTS definition and compute_lot, not an adapter-owned formula.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fatebridge.core.astro.geometry import (
    _house_for_longitude,
    _sign_name,
    combine_longitudes,
    normalize_angle,
)
from fatebridge.core.astro.house_positions import EclipticHouseProjection
from fatebridge.core.astro.house_projection_precision import RC_PLANE_PROJECTION_METHOD
from fatebridge.core.astro.native_motion import context_motion
from fatebridge.core.astro.parts import _build_houses
from fatebridge.core.astro.reference_points import ephemeris_reference_points
from fatebridge.core.astro.topocentric_precision import TOPOCENTRIC_PROJECTION_METHOD
from fatebridge.core.classical_western import LOTS, compute_lot
from fatebridge.core.ptolemy import FORTUNE_SOURCE_URL, fortune_longitude

FORTUNE_METHODS = ("sect_reversing", "ptolemy_iii10")


def build_context_geometry(
    states: Dict[str, Dict[str, float]],
    planet_ids: List[str],
    *,
    ascendant: float,
    midheaven: float,
    house_system: str,
    house_cusps: List[float],
    ayanamsha: float,
    chart_sect: str,
    fortune_method: str = "sect_reversing",
    zodiac_longitudes: Optional[Dict[str, float]] = None,
    house_projection: Optional[EclipticHouseProjection] = None,
    planetary_models: Optional[Dict[str, str]] = None,
    motion_rates: Optional[Dict[str, Optional[float]]] = None,
    motion_states: Optional[Dict[str, Dict[str, float]]] = None,
    motion_frame: Optional[str] = None,
    motion_derivative_policies: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if motion_rates is not None and motion_frame not in {
        "tropical_ecliptic_of_date",
        "lahiri_sidereal_ecliptic_of_date",
    }:
        raise ValueError("Motion rates require their explicit display reference frame")
    if fortune_method not in FORTUNE_METHODS:
        raise ValueError("fortune_method必须为sect_reversing或ptolemy_iii10")
    if chart_sect not in {"day", "night"}:
        raise ValueError("天象福点需要核心引擎的明确昼夜条件")
    longitudes = {
        name: normalize_angle(
            zodiac_longitudes[name]
            if zodiac_longitudes is not None
            else states[name]["longitude"] - ayanamsha
        )
        for name in planet_ids
    }
    if "North Node" in longitudes:
        longitudes["South Node"] = normalize_angle(longitudes["North Node"] + 180.0)
    markers = {name.lower(): lon for name, lon in longitudes.items()}
    markers["asc"] = ascendant
    if fortune_method == "ptolemy_iii10":
        fortune = (
            fortune_longitude(ascendant, longitudes["Sun"], longitudes["Moon"])
            if {"Sun", "Moon"} <= longitudes.keys()
            else None
        )
        fortune_definition = {
            "method": fortune_method,
            "formula": "ASC + Moon - Sun",
            "sect_applied": None,
            "author": "Claudius Ptolemy; tr. F. E. Robbins",
            "edition": "Tetrabiblos; Loeb Classical Library; 1940; III.10 main text",
            "source_url": FORTUNE_SOURCE_URL,
            "source_kind": "primary_text_translation",
            "scope": "Fortune formula only; no full-chart or dice-method conformity claim",
        }
    else:
        fortune = compute_lot(LOTS["fortune"][chart_sect], markers)
        fortune_definition = {
            "method": fortune_method,
            "formula": (
                "ASC + Moon - Sun" if chart_sect == "day" else "ASC + Sun - Moon"
            ),
            "sect_applied": chart_sect,
            "author": "FateBridge contributors; inherited reversing-lot convention",
            "source_path": "src/fatebridge/core/classical_western.py:LOTS.fortune",
            "source_kind": "runtime_convention",
            "scope": "Shared day/night reversing formula; no specified original-text certification",
        }
    if fortune is not None:
        longitudes["Pars Fortuna"] = fortune
    projected_positions: Dict[str, float] = {}
    if house_projection is not None:
        for name, lon in longitudes.items():
            if name in states:
                tropical_longitude = states[name]["longitude"]
            elif name == "South Node":
                tropical_longitude = combine_longitudes(
                    states["North Node"]["longitude"], 180.0
                )
            else:
                tropical_longitude = combine_longitudes(lon, ayanamsha)
            projected_positions[name] = house_projection.position(tropical_longitude)
    houses = _build_houses(
        ascendant,
        house_system,
        house_cusps=house_cusps,
        round_coordinates=False,
    )
    result: Dict[str, Any] = {
        "coordinate_policy": "unrounded_engine_values_not_an_accuracy_claim",
        "interval_convention": (
            (
                "precision-checked zero-latitude house position [1,13); house=floor(position)"
                if house_projection.metadata()["method"]
                in (RC_PLANE_PROJECTION_METHOD, TOPOCENTRIC_PROJECTION_METHOD)
                else "native zero-latitude house position [1,13); house=floor(position)"
            )
            if house_projection is not None
            else "zodiac and house intervals [start,end)"
        ),
        "houses": [
            {
                "id": f"House{h['house']}",
                "lon": h["cusp_longitude"],
                "sign": h["sign"],
                "sign_zh": h["sign_zh"],
            }
            for h in houses
        ],
        "objects": [
            {
                "id": name,
                "lon": lon,
                "signlon": lon % 30.0,
                "sign": _sign_name(lon),
                "house": f"House{int(projected_positions[name]) if house_projection is not None else _house_for_longitude(lon, ascendant, house_system, house_cusps=house_cusps)}",
                **(
                    {
                        "motion": context_motion(
                            name,
                            motion_rates,
                            planetary_models or {},
                            str(motion_frame),
                            (motion_states or {}).get(
                                "North Node" if name == "South Node" else name
                            ),
                            derivative_policy=(motion_derivative_policies or {}).get(
                                f"{'North Node' if name == 'South Node' else name}:"
                                f"{'lahiri' if motion_frame == 'lahiri_sidereal_ecliptic_of_date' else 'tropical'}"
                            ),
                        )
                    }
                    if motion_rates is not None
                    else {}
                ),
                **(
                    {"ecliptic_house_position": projected_positions[name]}
                    if house_projection is not None
                    else {}
                ),
            }
            for name, lon in longitudes.items()
        ],
        "angles": {"ascendant": ascendant, "midheaven": midheaven},
        "fortune_definition": fortune_definition,
        "auxiliary_point_sources": {
            "South Node": "opposite_unrounded_core_north_node",
            "Pars Fortuna": (
                "core.ptolemy.fortune_longitude; Robbins 1940 III.10"
                if fortune_method == "ptolemy_iii10"
                else "core.classical_western.LOTS.fortune/compute_lot; unrounded zodiac coordinates and core horizon sect"
            ),
        },
    }
    if house_projection is not None:
        result["house_position_projection"] = house_projection.metadata()
    if planetary_models is not None:
        result["ephemeris_reference_points"] = ephemeris_reference_points(
            planetary_models, [name for name in longitudes if name not in states]
        )
    if motion_rates is not None:
        uncomputed = [
            obj["id"]
            for obj in result["objects"]
            if obj["motion"]["direction"] == "not_computed"
        ]
        result["motion_policy"] = {
            "policy_id": "astrodice_context_motion_v1",
            "status": "partial" if uncomputed else "computed",
            "uncomputed_points": uncomputed,
            "reference_frame": motion_frame,
            "unit": "degree_per_day",
            "sign_policy": "unrounded_rate_sign; zero_is_not_a_located_station_event",
            "source_url": "https://www.astro.com/swisseph/swephprg.htm",
            "source_sections": "3.3.3, 3.4, 12.2",
            "scope": "Instantaneous sky longitude motion only; does not alter dice conditions or establish event timing, observational accuracy or divination validity.",
        }
    return result
