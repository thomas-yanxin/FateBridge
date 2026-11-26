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
from fatebridge.utils.coordinates import parse_geo_coordinate
from fatebridge.utils.house_systems import InvalidHouseSystemError, house_system_fields


def _resolve_otherbu_chart_options(
    house_system: int | str, zodiac_type: str
) -> tuple[int, str, int, str]:
    if isinstance(house_system, bool):
        raise ValueError("house_system不能为布尔值，仅用于附加天象盘")
    try:
        house_fields = house_system_fields(house_system, default="D")
    except InvalidHouseSystemError as exc:
        raise ValueError(str(exc)) from exc
    hsys = house_fields["house_system_code"]
    if hsys is None:
        raise ValueError("house_system仅支持0..8对应宫制，仅用于附加天象盘")
    if not isinstance(zodiac_type, str):
        raise ValueError("zodiac_type必须为Tropic或Sidereal，仅用于附加天象盘")
    token = zodiac_type.strip().casefold()
    if token in {"tropic", "tropical"}:
        return hsys, house_fields["house_system"], 0, "Tropic"
    if token == "sidereal":
        return hsys, house_fields["house_system"], 1, "Sidereal"
    raise ValueError("zodiac_type必须为Tropic或Sidereal，仅用于附加天象盘")


def build_otherbu_result(
    *,
    date: str | None = None,
    time: str | None = None,
    timezone: str | None = None,
    latitude: float | str | None = None,
    longitude: float | str | None = None,
    tradition: bool = False,
    sign: str | None = None,
    house: int | None = None,
    planet: str | None = None,
    question: str | None = None,
    house_system: int | str = "D",
    zodiac_type: str = "Tropic",
    fortune_method: str = "sect_reversing",
) -> dict[str, Any]:
    normalized_sign = normalize_sign(sign)
    normalized_planet = normalize_planet(planet)
    normalized_house = normalize_house(house)
    hsys, resolved_house_system, zodiacal, normalized_zodiac_type = (
        _resolve_otherbu_chart_options(house_system, zodiac_type)
    )
    if fortune_method not in FORTUNE_METHODS:
        raise ValueError("fortune_method必须为sect_reversing或ptolemy_iii10")
    parsed_latitude = parse_geo_coordinate(latitude, axis="latitude")
    parsed_longitude = parse_geo_coordinate(longitude, axis="longitude")
    validate_context(
        date=date,
        time=time,
        timezone=timezone,
        latitude=parsed_latitude,
        longitude=parsed_longitude,
    )
    date_text = _normalize_date_text(date) if date is not None else None
    time_text = _normalize_time_text(time) if time is not None else None
    inputs = {
        "date": date_text,
        "time": time_text,
        "timezone": timezone,
        "latitude": parsed_latitude,
        "longitude": parsed_longitude,
        "tradition": tradition,
        "sign": normalized_sign,
        "house": normalized_house,
        "planet": normalized_planet,
        "question": question,
        "house_system": resolved_house_system,
        "zodiac_type": normalized_zodiac_type,
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
            timezone_name=timezone,
            lat=parsed_latitude,
            lon=parsed_longitude,
            gps_lat=None,
            gps_lon=None,
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
