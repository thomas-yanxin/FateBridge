"""Astrodice symbols with a separate, optional astronomical context chart."""

from __future__ import annotations

from typing import Any

from fatebridge.core.astro.astrology_tables import SIGNS
from fatebridge.core.astro.context_geometry import FORTUNE_METHODS
from fatebridge.core.astrodice import (
    build_symbolic_evidence,
    normalize_house,
    normalize_planet,
    normalize_sign,
    validate_context,
)
from fatebridge.core.local_techniques.chart import (
    _build_house_ring,
    _build_local_chart_response,
    _normalize_date_text,
    _normalize_time_text,
)


def build_otherbu_result(
    *,
    date: str | None = None,
    time: str | None = None,
    zone: str | None = None,
    lat: str | float | None = None,
    lon: str | float | None = None,
    gps_lat: float | None = None,
    gps_lon: float | None = None,
    tradition: bool = False,
    sign: str | None = None,
    house: int | None = None,
    planet: str | None = None,
    question: str | None = None,
    hsys: int = 8,
    zodiacal: int = 0,
    fortune_method: str = "sect_reversing",
) -> dict[str, Any]:
    normalized_sign = normalize_sign(sign)
    normalized_planet = normalize_planet(planet)
    normalized_house = normalize_house(house)
    if type(hsys) is not int or hsys not in range(9):
        raise ValueError("hsys必须为0..8的整数，仅用于附加天象盘")
    if type(zodiacal) is not int or zodiacal not in {0, 1}:
        raise ValueError("zodiacal必须为0或1的整数，仅用于附加天象盘")
    if fortune_method not in FORTUNE_METHODS:
        raise ValueError("fortune_method必须为sect_reversing或ptolemy_iii10")
    validate_context(
        date=date,
        time=time,
        zone=zone,
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
    )
    date_text = _normalize_date_text(date) if date is not None else None
    time_text = _normalize_time_text(time) if time is not None else None
    inputs = {
        "date": date_text,
        "time": time_text,
        "zone": zone,
        "lat": lat,
        "lon": lon,
        "gpsLat": gps_lat,
        "gpsLon": gps_lon,
        "tradition": tradition,
        "sign": normalized_sign,
        "house": normalized_house,
        "planet": normalized_planet,
        "question": question,
        "hsys": hsys,
        "zodiacal": zodiacal,
        "fortune_method": fortune_method,
    }
    evidence = build_symbolic_evidence(
        normalized_planet, normalized_sign, normalized_house
    )
    first_longitude = ((SIGNS.index(normalized_sign) - normalized_house) % 12) * 30.0
    # A die encodes a sign, not an exact longitude. Never copy sky bodies into it.
    dice_chart = {
        "params": {
            "chartKind": "symbolic_whole_sign_diagram",
            "houseSystemResolved": "symbolic_whole_sign",
            "engineBackend": "symbolic_rules",
            "enginePrecision": "sign_and_house_only",
            "diceHouse1Longitude": first_longitude,
            "diceTargetHouse": f"House{normalized_house + 1}",
            "longitudeMeaning": "宫首经度仅为假设整宫轮坐标；非观测宫头或真实上升点。",
        },
        "chart": {
            "ok": True,
            "houses": _build_house_ring(first_longitude),
            "objects": [
                {
                    "id": normalized_planet,
                    "sign": normalized_sign,
                    "house": f"House{normalized_house + 1}",
                }
            ],
            "angles": {},
        },
    }
    base_chart = None
    if date_text is not None and time_text is not None:
        base_chart = _build_local_chart_response(
            date_text=date_text,
            time_text=time_text,
            timezone_name=zone,
            lat=lat,
            lon=lon,
            gps_lat=gps_lat,
            gps_lon=gps_lon,
            tradition=tradition,
            hsys=hsys,
            zodiacal=zodiacal,
            allow_extended_hsys=True,
            include_calculation_metadata=True,
            preserve_context_geometry=True,
            context_fortune_method=fortune_method,
        )
        base_chart["params"]["chartKind"] = "astronomical_context_only"
        evidence["validation"]["calendar"] = "separate_astronomical_context_computed"
    return {
        "analysis_type": "西洋游戏 / 占星骰子",
        "input_normalized": inputs,
        "planet": normalized_planet,
        "sign": normalized_sign,
        "house": normalized_house,
        "diceChart": dice_chart,
        "chart": base_chart,
        "question": question,
        **evidence,
        "summary": f"星骰符号：{normalized_planet} / {normalized_sign} / 第{normalized_house + 1}宫。",
    }
