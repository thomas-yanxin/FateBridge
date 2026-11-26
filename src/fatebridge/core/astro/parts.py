"""Planet and house records, balance and chart summaries."""

from __future__ import annotations

import math
from collections import Counter
from fractions import Fraction
from typing import Any, Iterable

from fatebridge.core.astro.astrology_tables import DOMICILE_RULERS as DOMICILE_RULERS
from fatebridge.core.astro.astrology_tables import ELEMENT_BY_SIGN as ELEMENT_BY_SIGN
from fatebridge.core.astro.astrology_tables import EXALTATION_SIGNS as EXALTATION_SIGNS
from fatebridge.core.astro.astrology_tables import MODALITY_BY_SIGN as MODALITY_BY_SIGN
from fatebridge.core.astro.astrology_tables import SIGN_LABELS_ZH as SIGN_LABELS_ZH
from fatebridge.core.astro.astrology_tables import _opposite_sign as _opposite_sign
from fatebridge.core.astro.geometry import (
    _degree_in_sign,
    _house_for_longitude,
    _nakshatra,
    _sector13_for_longitude,
    _sign_name,
    _su28,
    normalize_angle,
)
from fatebridge.core.astro.reference import (
    DIGNITY_LABELS_ZH,
    NODE_BODIES,
    STATION_SPEED_THRESHOLDS,
)


def _essential_dignity(planet: str, sign: str) -> dict[str, str] | None:
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
    ascendant: float | None,
    house_system: str,
    house_cusps: list[float] | None = None,
    midheaven: float | None = None,
    *,
    round_coordinates: bool = False,
) -> list[dict[str, Any]]:
    houses: list[dict[str, Any]] = []
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
    if house_system == "equal_mc" and midheaven is not None:
        first_cusp = midheaven
    elif ascendant is None:
        return houses
    elif house_system == "whole_sign":
        first_cusp = float(((Fraction(ascendant) % 360) // 30) * 30)
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


def _build_planet_record(
    planet: str,
    longitude: float,
    latitude: float,
    ascendant: float | None,
    house_system: str,
    *,
    house_cusps: list[float] | None = None,
    sidereal: bool = False,
    ayanamsha: float = 0.0,
    include_sector13: bool = False,
    include_nakshatra: bool = False,
    include_su28: bool = False,
    zodiac_longitude: float | None = None,
    projected_house_position: float | None = None,
    longitude_speed: float | None = None,
    declination: float | None = None,
    obliquity: float | None = None,
    houses_resolved: bool = True,
) -> dict[str, Any]:
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
    if not houses_resolved or (
        projected_house_position is None and ascendant is None and not house_cusps
    ):
        house_num: int | None = None
    elif projected_house_position is not None:
        house_num = int(projected_house_position)
    else:
        house_num = _house_for_longitude(
            effective_longitude,
            ascendant if ascendant is not None else 0.0,
            house_system,
            house_cusps=house_cusps,
        )
    speed_val = (
        float(longitude_speed)
        if longitude_speed is not None and math.isfinite(longitude_speed)
        else None
    )
    decl_val = (
        float(declination)
        if declination is not None and math.isfinite(declination)
        else None
    )
    threshold = STATION_SPEED_THRESHOLDS.get(planet)
    stationary = bool(
        speed_val is not None and threshold is not None and abs(speed_val) < threshold
    )
    out_of_bounds = bool(
        decl_val is not None
        and obliquity is not None
        and math.isfinite(obliquity)
        and abs(decl_val) > abs(obliquity)
    )
    record: dict[str, Any] = {
        "id": planet,
        "longitude": effective_longitude,
        "latitude": latitude,
        "longitude_speed": speed_val,
        "retrograde": bool(speed_val is not None and speed_val < 0),
        "stationary": stationary,
        "declination": decl_val,
        "out_of_bounds": out_of_bounds,
        "sign": sign,
        "sign_zh": SIGN_LABELS_ZH[sign],
        "degree_in_sign": _degree_in_sign(effective_longitude),
        "house": house_num,
        "element": ELEMENT_BY_SIGN[sign],
        "modality": MODALITY_BY_SIGN[sign],
        "dignity": _essential_dignity(planet, sign),
    }
    if projected_house_position is not None:
        record["ecliptic_house_position"] = projected_house_position
    if include_sector13 and ascendant is not None:
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


def _balance(planets: Iterable[dict[str, Any]], key: str) -> dict[str, int]:
    # 元素 / 模式平衡只统计行星本体；月亮交点是计算虚点（且仅排北交、不排南交，
    # 计入会造成不对称偏置），故排除在外。交点仍保留在 planets 列表中。
    counter = Counter(
        item[key] for item in planets if item.get("id") not in NODE_BODIES
    )
    return dict(counter)


def _summary(
    chart_variant: str,
    planets: list[dict[str, Any]],
    aspects: list[dict[str, Any]],
    *,
    engine_precision: str,
) -> list[str]:
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
