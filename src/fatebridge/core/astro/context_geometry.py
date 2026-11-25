"""Unrounded geometry for optional sky context, from one core calculation.

Formatting must not decide signs, derived points or cusp membership. Keep
working lot angles through the ordinary house partition.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core.astro.geometry import (
    Angle,
    _house_for_longitude,
    _sign_name,
    angle_fraction,
    combine_longitudes,
    longitude_float,
    normalize_angle,
)
from fatebridge.core.astro.house_positions import (
    EclipticHouseProjection,
    HouseCoordinate,
)
from fatebridge.core.astro.house_projection_precision import RC_PLANE_PROJECTION_METHOD
from fatebridge.core.astro.native_motion import context_motion
from fatebridge.core.astro.parts import _build_houses
from fatebridge.core.astro.ptolemy import FORTUNE_SOURCE_URL, fortune_working_longitude
from fatebridge.core.astro.reference_points import ephemeris_reference_points
from fatebridge.core.astro.topocentric_precision import TOPOCENTRIC_PROJECTION_METHOD
from fatebridge.core.classical_western import LOTS, lot_longitude

FORTUNE_METHODS = ("sect_reversing", "ptolemy_iii10")


def build_context_geometry(
    states: dict[str, dict[str, float]],
    planet_ids: list[str],
    *,
    ascendant: float,
    midheaven: float,
    house_system: str,
    house_cusps: list[float],
    ayanamsha: float,
    chart_sect: str,
    fortune_method: str = "sect_reversing",
    ascendant_resolved: bool = True,
    houses_resolved: bool = True,
    zodiac_longitudes: dict[str, float] | None = None,
    house_projection: EclipticHouseProjection | None = None,
    house_coordinates: dict[str, HouseCoordinate] | None = None,
    planetary_models: dict[str, str] | None = None,
    motion_rates: dict[str, float | None] | None = None,
    motion_states: dict[str, dict[str, float]] | None = None,
    motion_frame: str | None = None,
    motion_derivative_policies: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
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
    partition_longitudes: dict[str, Angle] = {**longitudes}
    if "North Node" in longitudes:
        partition_longitudes["South Node"] = (
            angle_fraction(longitudes["North Node"]) + 180
        ) % 360
        longitudes["South Node"] = combine_longitudes(longitudes["North Node"], 180.0)
    markers = {name.lower(): lon for name, lon in longitudes.items()}
    if ascendant_resolved:
        markers["asc"] = ascendant
    if fortune_method == "ptolemy_iii10":
        fortune = (
            fortune_working_longitude(ascendant, longitudes["Sun"], longitudes["Moon"])
            if ascendant_resolved and {"Sun", "Moon"} <= longitudes.keys()
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
        fortune = lot_longitude(LOTS["fortune"][chart_sect], markers)
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
        partition_longitudes["Pars Fortuna"] = fortune
        longitudes["Pars Fortuna"] = longitude_float(fortune)
    projected_positions: dict[str, HouseCoordinate] = {}
    if houses_resolved and house_projection is not None:
        for name, lon in longitudes.items():
            if house_coordinates is not None and name in house_coordinates:
                projected_positions[name] = house_coordinates[name]
                continue
            exact_tropical_longitude = None
            if name in states:
                tropical_longitude = states[name]["longitude"]
            elif name == "South Node":
                tropical_longitude = combine_longitudes(
                    states["North Node"]["longitude"], 180.0
                )
                exact_tropical_longitude = (
                    angle_fraction(states["North Node"]["longitude"]) + 180
                ) % 360
            else:
                tropical_longitude = combine_longitudes(lon, ayanamsha)
            projected_positions[name] = house_projection.coordinate(
                tropical_longitude, exact_longitude=exact_tropical_longitude
            )
    houses = _build_houses(
        ascendant,
        house_system,
        house_cusps=house_cusps,
        round_coordinates=False,
    )
    result: dict[str, Any] = {
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
            if houses_resolved
        ],
        "objects": [
            {
                "id": name,
                "lon": lon,
                "signlon": lon % 30.0,
                "sign": _sign_name(lon),
                "house": (
                    f"House{int(projected_positions[name].position) if house_projection is not None else _house_for_longitude(partition_longitudes.get(name, lon), ascendant, house_system, house_cusps=house_cusps)}"
                    if houses_resolved
                    else None
                ),
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
                    {
                        "ecliptic_house_position": projected_positions[name].position,
                        "ecliptic_house_phase_degrees_ratio": str(
                            projected_positions[name].phase_degrees
                        ),
                    }
                    if houses_resolved and house_projection is not None
                    else {}
                ),
            }
            for name, lon in longitudes.items()
        ],
        "angles": {
            "ascendant": ascendant if ascendant_resolved else None,
            "midheaven": midheaven,
        },
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
