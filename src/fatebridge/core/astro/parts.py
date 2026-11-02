"""Planet and house records, balance and chart summaries."""

from __future__ import annotations

import math
from collections import Counter
from fractions import Fraction
from typing import Any, Dict, Iterable, List, Optional

from fatebridge.core.astro.geometry import (
    _degree_in_sign,
    _house_for_longitude,
    _nakshatra,
    _sector13_for_longitude,
    _sign_name,
    _su28,
    normalize_angle,
)
from fatebridge.core.astro.reference import DIGNITY_LABELS_ZH, NODE_BODIES
from fatebridge.core.astrology_tables import DOMICILE_RULERS as DOMICILE_RULERS
from fatebridge.core.astrology_tables import ELEMENT_BY_SIGN as ELEMENT_BY_SIGN
from fatebridge.core.astrology_tables import EXALTATION_SIGNS as EXALTATION_SIGNS
from fatebridge.core.astrology_tables import MODALITY_BY_SIGN as MODALITY_BY_SIGN
from fatebridge.core.astrology_tables import SIGN_LABELS_ZH as SIGN_LABELS_ZH
from fatebridge.core.astrology_tables import _opposite_sign as _opposite_sign


def _essential_dignity(planet: str, sign: str) -> Optional[Dict[str, str]]:
    """Sign-only major dignity summary; not a full peregrine classification."""
    if planet not in DOMICILE_RULERS:
        return None
    if sign in DOMICILE_RULERS[planet]:
        dignity = "rulership"
    elif sign == EXALTATION_SIGNS[planet]:
        dignity = "exaltation"
    elif sign in {_opposite_sign(s) for s in DOMICILE_RULERS[planet]}:
        dignity = "detriment"
    elif sign == _opposite_sign(EXALTATION_SIGNS[planet]):
        dignity = "fall"
    else:
        dignity = "no_major_dignity"
    return {
        "dignity": dignity,
        "status_zh": DIGNITY_LABELS_ZH[dignity],
        "scope": "sign_only_major_dignity; triplicity_term_face_and_peregrine_not_classified",
    }


def _build_houses(
    ascendant: float,
    house_system: str,
    house_cusps: Optional[List[float]] = None,
    midheaven: Optional[float] = None,
    *,
    round_coordinates: bool = False,
) -> List[Dict[str, Any]]:
    houses: List[Dict[str, Any]] = []
    if house_cusps:
        for house_number, cusp in enumerate(house_cusps, start=1):
            normalized_cusp = normalize_angle(cusp)
            sign = _sign_name(normalized_cusp)
            houses.append(
                {
                    "house": house_number,
                    "cusp_longitude": (
                        round(normalized_cusp, 4)
                        if round_coordinates
                        else normalized_cusp
                    ),
                    "sign": sign,
                    "sign_zh": SIGN_LABELS_ZH[sign],
                }
            )
        return houses
    if house_system == "whole_sign":
        first_cusp = float(((Fraction(ascendant) % 360) // 30) * 30)
    elif house_system == "equal_mc" and midheaven is not None:
        # Equal houses anchored on the midheaven (swisseph code 'D'): the MC is
        # the 10th cusp, so the 1st cusp sits 90° later. The true ascendant is
        # deliberately NOT the anchor here — using it silently degrades the
        # system into plain `equal` and shifts every house by one when the
        # ascendant and MC+90 fall in different signs.
        first_cusp = midheaven
    else:
        first_cusp = ascendant
    for house_number in range(1, 13):
        offset = (
            (house_number - 10) * 30
            if house_system == "equal_mc" and midheaven is not None
            else (house_number - 1) * 30
        )
        # Rotate the original anchor once. Rounding MC+90 before rotating
        # again can even move cusp 10 away from the supplied MC. Preserve
        # the exact input's zodiac partition at representational boundaries.
        exact_cusp = (Fraction(first_cusp) + offset) % 360
        cusp = float(exact_cusp)
        if int(cusp // 30) != int(exact_cusp // 30):
            cusp = math.nextafter(cusp, -math.inf)
        sign = _sign_name(cusp)
        houses.append(
            {
                "house": house_number,
                "cusp_longitude": round(cusp, 4) if round_coordinates else cusp,
                "sign": sign,
                "sign_zh": SIGN_LABELS_ZH[sign],
            }
        )
    return houses


def _build_thirteen_sectors(ascendant: float) -> List[Dict[str, Any]]:
    from fatebridge.core.astro.sectors import thirteen_sectors

    return thirteen_sectors(ascendant)


def _build_planet_record(
    planet: str,
    longitude: float,
    latitude: float,
    ascendant: float,
    house_system: str,
    *,
    house_cusps: Optional[List[float]] = None,
    sidereal: bool = False,
    ayanamsha: float = 0.0,
    include_sector13: bool = False,
    include_nakshatra: bool = False,
    include_su28: bool = False,
    zodiac_longitude: Optional[float] = None,
    projected_house_position: Optional[float] = None,
) -> Dict[str, Any]:
    effective_longitude = (
        normalize_angle(zodiac_longitude)
        if zodiac_longitude is not None
        else (
            normalize_angle(longitude - ayanamsha)
            if sidereal
            else normalize_angle(longitude)
        )
    )
    sign = _sign_name(effective_longitude)
    record = {
        "id": planet,
        "longitude": effective_longitude,
        "latitude": latitude,
        "sign": sign,
        "sign_zh": SIGN_LABELS_ZH[sign],
        "degree_in_sign": _degree_in_sign(effective_longitude),
        "house": (
            int(projected_house_position)
            if projected_house_position is not None
            else _house_for_longitude(
                effective_longitude,
                ascendant,
                house_system,
                house_cusps=house_cusps,
            )
        ),
        "element": ELEMENT_BY_SIGN[sign],
        "modality": MODALITY_BY_SIGN[sign],
        "dignity": _essential_dignity(planet, sign),
    }
    if projected_house_position is not None:
        record["ecliptic_house_position"] = projected_house_position
    if include_sector13:
        record["sector13"] = _sector13_for_longitude(effective_longitude, ascendant)
        record["sector13_evidence"] = {
            "longitude_unrounded": effective_longitude,
            "ascendant_unrounded": ascendant,
            "interval_convention": "[start,end), ascendant-relative 360/13",
            "rule_id": "fatebridge.equal13.exact_partition.v1",
            "birth_time_uncertainty": "not_assessed",
        }
    if include_nakshatra:
        record["nakshatra"] = _nakshatra(effective_longitude)
    if include_su28:
        record["su28"] = _su28(effective_longitude)
    return record


def _balance(planets: Iterable[Dict[str, Any]], key: str) -> Dict[str, int]:
    # 元素 / 模式平衡只统计行星本体；月亮交点是计算虚点（且仅排北交、不排南交，
    # 计入会造成不对称偏置），故排除在外。交点仍保留在 planets 列表中。
    counter = Counter(
        item[key] for item in planets if item.get("id") not in NODE_BODIES
    )
    return dict(counter)


def _summary(
    chart_variant: str,
    planets: List[Dict[str, Any]],
    aspects: List[Dict[str, Any]],
    *,
    engine_precision: str,
) -> List[str]:
    sun = next((item for item in planets if item["id"] == "Sun"), None)
    moon = next((item for item in planets if item["id"] == "Moon"), None)
    top_aspect = aspects[0] if aspects else None
    chart_label = (
        "离线高精度星盘"
        if engine_precision == "ephemeris_runtime_model"
        else "离线近似星盘"
    )
    lines = [f"已生成 {chart_variant} 的 {chart_label}。"]
    if sun is not None:
        lines.append(f"太阳落在 {sun['sign_zh']}，宫位 {sun['house']}。")
    if moon is not None:
        lines.append(f"月亮落在 {moon['sign_zh']}，宫位 {moon['house']}。")
    if top_aspect is not None:
        lines.append(
            f"{top_aspect['planet_a']} 与 {top_aspect['planet_b']} 形成 {top_aspect['aspect']}，容许度 {top_aspect['orb']}。"
        )
    return lines
