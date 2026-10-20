"""
Western / local pseudo-chart substrate for the FateBridge local-techniques package.

The shared engine every local-divination builder sits on: zodiac/house tables,
chart-object and house-ring construction, coordinate/date parsing, the
MetaphysicsSeed bridge, and snapshot helpers. Kept free of any single
technique's logic so the per-technique modules import from here without cycling
back through the package facade.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.utils.coordinates import parse_geo_coordinate
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE
from fatebridge.utils.solar_time import (
    SOLAR_TIME_STRATEGY_APPARENT,
    calculate_solar_time_adjustment,
)

from ..almanac import (
    DAY_GANZHI_STRATEGY_STANDARD,
    build_calendar_context,
    localize_datetime,
)
from ..astro.birth import AstroBirthInfo, build_astro_birth_info
from ..astro.chart import build_core_chart_payload
from ..calendar import BaZiCalendar

SU28_NAMES = [
    "角",
    "亢",
    "氐",
    "房",
    "心",
    "尾",
    "箕",
    "斗",
    "牛",
    "女",
    "虚",
    "危",
    "室",
    "壁",
    "奎",
    "娄",
    "胃",
    "昴",
    "毕",
    "觜",
    "参",
    "井",
    "鬼",
    "柳",
    "星",
    "张",
    "翼",
    "轸",
]


ZODIAC_SIGNS = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
]


ZODIAC_SIGN_CN = {
    "Aries": "白羊座",
    "Taurus": "金牛座",
    "Gemini": "双子座",
    "Cancer": "巨蟹座",
    "Leo": "狮子座",
    "Virgo": "处女座",
    "Libra": "天秤座",
    "Scorpio": "天蝎座",
    "Sagittarius": "射手座",
    "Capricorn": "摩羯座",
    "Aquarius": "水瓶座",
    "Pisces": "双鱼座",
}


OUTER_PLANETS = {"Uranus", "Neptune", "Pluto"}


SANSHI_REFERENCES = [
    "门迫逢旺，先阻后成。",
    "先整队形，再抢窗口。",
    "利于借势，不利单点硬冲。",
    "宜先稳住节奏，再谈放大。",
    "外部有助，内部更要对齐。",
    "此局贵在先定边界后发力。",
]


def _option_value(options: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in options and options[key] is not None:
            return options[key]
    return None


def _rotate_items(items: List[Any], shift: int) -> List[Any]:
    if not items:
        return []
    normalized_shift = shift % len(items)
    if normalized_shift == 0:
        return list(items)
    return list(items[normalized_shift:] + items[:normalized_shift])


def _join_lines(lines: List[str]) -> str:
    return "\n".join(line for line in lines if line).strip()


def _render_snapshot_text(sections: List[Tuple[str, str]]) -> str:
    blocks: List[str] = []
    for title, body in sections:
        blocks.append(f"[{title}]")
        if body:
            blocks.append(body.strip())
        blocks.append("")
    return "\n".join(blocks).strip()


def _normalize_date_text(date_text: str) -> str:
    """Normalize YYYY/M/D or YYYY-M-D (potentially unpadded) into YYYY-MM-DD.

    Callers then feed the result to ``datetime.fromisoformat`` which rejects
    non-zero-padded month/day components, so we must pad here rather than let
    a natural ``"2026/4/23"`` input crash the endpoint.
    """
    raw = (date_text or "").strip()
    if not raw:
        return raw

    canonical = raw.replace("/", "-")
    parts = canonical.split("-")
    if len(parts) != 3:
        return canonical

    year_text, month_text, day_text = (part.strip() for part in parts)
    if not (year_text.isdigit() and month_text.isdigit() and day_text.isdigit()):
        return canonical

    return f"{int(year_text):04d}-{int(month_text):02d}-{int(day_text):02d}"


def _normalize_time_text(time_text: str) -> str:
    value = (time_text or "").strip()
    if not value:
        return "00:00:00"
    parts = value.split(":")
    if len(parts) < 2 or len(parts) > 3:
        return value
    hours_text = parts[0]
    minutes_text = parts[1]
    seconds_text = parts[2] if len(parts) == 3 else "0"
    if not all(p.isdigit() for p in (hours_text, minutes_text, seconds_text)):
        return value
    return f"{int(hours_text):02d}:{int(minutes_text):02d}:{int(seconds_text):02d}"


def parse_local_datetime(
    date_text: str,
    time_text: str,
    timezone_name: Optional[str] = None,
) -> datetime:
    moment = datetime.fromisoformat(
        f"{_normalize_date_text(date_text)} {_normalize_time_text(time_text)}"
    )
    return localize_datetime(moment, timezone_name or DEFAULT_BIRTH_TIMEZONE)


def _julian_day(moment: datetime) -> float:
    utc_moment = moment.astimezone(timezone.utc) if moment.tzinfo else moment
    timestamp = utc_moment.timestamp()
    return timestamp / 86400.0 + 2440587.5


def _sign_name(longitude: float) -> str:
    return ZODIAC_SIGNS[int(longitude // 30) % 12]


def _su28_name(longitude: float) -> str:
    span = 360.0 / 28.0
    index = int(longitude // span) % 28
    return SU28_NAMES[index]


def _split_degree(value: Any) -> Tuple[int, int]:
    try:
        degree = float(value)
    except (TypeError, ValueError):
        return 0, 0
    if degree < 0:
        degree += 360.0
    degree %= 30.0
    whole_degree = int(degree)
    minute = int((degree - whole_degree) * 60)
    return whole_degree, minute


def _resolve_coordinates(
    *,
    lat: Any = None,
    lon: Any = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
) -> Tuple[float, float]:
    latitude = parse_geo_coordinate(
        gps_lat if gps_lat is not None else lat, axis="latitude"
    )
    longitude = parse_geo_coordinate(
        gps_lon if gps_lon is not None else lon, axis="longitude"
    )
    return (
        31.2167 if latitude is None else latitude,
        121.4667 if longitude is None else longitude,
    )


def _build_birth_info(
    *,
    date_text: str,
    time_text: str,
    timezone_name: Optional[str],
    lat: Any = None,
    lon: Any = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
) -> Tuple[AstroBirthInfo, float, float]:
    moment = parse_local_datetime(date_text, time_text, timezone_name)
    latitude, longitude = _resolve_coordinates(
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
    )
    birth_info = build_astro_birth_info(
        birth_year=moment.year,
        birth_month=moment.month,
        birth_day=moment.day,
        birth_hour=moment.hour,
        birth_minute=moment.minute,
        birth_timezone=timezone_name or DEFAULT_BIRTH_TIMEZONE,
        birth_longitude=longitude,
        birth_latitude=latitude,
    )
    return birth_info, latitude, longitude


def _normalize_mode(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _house_step(shape_mode: int) -> float:
    return -30.0 if shape_mode % 2 else 30.0


def _display_house_system_name(house_system: Any) -> Optional[str]:
    name = str(house_system or "").strip()
    if not name:
        return None
    if name == "equal_mc":
        return "equal"
    return name


def _build_house_ring(
    house1_longitude: float,
    *,
    step_degrees: float = 30.0,
) -> List[Dict[str, Any]]:
    houses: List[Dict[str, Any]] = []
    for index in range(12):
        longitude = round((house1_longitude + index * step_degrees) % 360.0, 4)
        sign = _sign_name(longitude)
        houses.append(
            {
                "id": f"House{index + 1}",
                "lon": longitude,
                "sign": sign,
                "sign_zh": ZODIAC_SIGN_CN.get(sign),
            }
        )
    return houses


def _reindex_houses(source_houses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    houses: List[Dict[str, Any]] = []
    for index, item in enumerate(source_houses, start=1):
        longitude = round(float(item.get("lon", 0.0)), 4)
        sign = item.get("sign") or _sign_name(longitude)
        houses.append(
            {
                "id": f"House{index}",
                "lon": longitude,
                "sign": sign,
                "sign_zh": item.get("sign_zh") or ZODIAC_SIGN_CN.get(sign),
            }
        )
    return houses


def _reverse_houses(source_houses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not source_houses:
        return []
    return _reindex_houses([source_houses[0], *reversed(source_houses[1:])])


def _house_direction(houses: List[Dict[str, Any]]) -> str:
    if len(houses) < 2:
        return "forward"

    forward_steps = 0
    reverse_steps = 0
    for index, house in enumerate(houses):
        current = float(house.get("lon", 0.0))
        next_longitude = float(houses[(index + 1) % len(houses)].get("lon", 0.0))
        delta = (next_longitude - current) % 360.0
        if delta == 0:
            continue
        if delta <= 180.0:
            forward_steps += 1
        else:
            reverse_steps += 1

    return "reverse" if reverse_steps > forward_steps else "forward"


def _build_houses(
    core_payload: Dict[str, Any],
    *,
    house_start_mode: int = 1,
    shape_mode: int = 0,
    preserve_core_cusps: bool = False,
) -> Tuple[List[Dict[str, Any]], float, float]:
    ascendant = round(float(core_payload["angles"]["ascendant"]["longitude"]), 4)
    base_houses = _adapt_chart_houses(core_payload)
    if preserve_core_cusps and house_start_mode != 2 and base_houses:
        houses = _reindex_houses(base_houses)
        if shape_mode % 2:
            houses = _reverse_houses(houses)
        house_direction = _house_direction(houses)
        house_step = -30.0 if house_direction == "reverse" else 30.0
        house1_longitude = houses[0]["lon"]
        return houses, house1_longitude, house_step

    if house_start_mode == 2:
        house1_longitude = round(float(int(ascendant // 30) * 30), 4)
    else:
        house1_longitude = base_houses[0]["lon"] if base_houses else ascendant

    house_step = _house_step(shape_mode)
    houses = _build_house_ring(house1_longitude, step_degrees=house_step)
    return houses, house1_longitude, house_step


def _adapt_chart_houses(core_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    houses: List[Dict[str, Any]] = []
    for item in core_payload.get("houses", []):
        if not isinstance(item, dict):
            continue
        houses.append(
            {
                "id": f"House{item.get('house')}",
                "lon": round(float(item.get("cusp_longitude", 0.0)), 4),
                "sign": item.get("sign"),
                "sign_zh": item.get("sign_zh"),
            }
        )
    return houses


def _build_point_object(
    *,
    point_id: str,
    longitude: float,
    houses: List[Dict[str, Any]],
    include_su28: bool,
) -> Dict[str, Any]:
    sign = _sign_name(longitude)
    payload = {
        "id": point_id,
        "house": _house_id_for_houses(longitude, houses),
        "sign": sign,
        "signlon": round(longitude % 30.0, 4),
        "lon": round(longitude, 4),
    }
    if include_su28:
        payload["su28"] = _su28_name(longitude)
    return payload


def _adapt_chart_objects(
    core_payload: Dict[str, Any],
    *,
    tradition: bool,
    include_su28: bool,
    houses: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    objects: List[Dict[str, Any]] = []
    for item in core_payload.get("planets", []):
        if not isinstance(item, dict):
            continue
        point_id = str(item.get("id") or "")
        if tradition and point_id in OUTER_PLANETS:
            continue
        longitude = round(float(item.get("longitude", 0.0)), 4)
        payload: Dict[str, Any] = {
            "id": point_id,
            "house": _house_id_for_houses(longitude, houses),
            "sign": item.get("sign"),
            "signlon": round(float(item.get("degree_in_sign", 0.0)), 4),
            "lon": longitude,
        }
        if include_su28:
            payload["su28"] = _su28_name(payload["lon"])
        objects.append(payload)

    north_node = next(
        (item for item in objects if item.get("id") == "North Node"), None
    )
    if north_node is not None:
        south_node_longitude = round((float(north_node["lon"]) + 180.0) % 360.0, 4)
        objects.append(
            _build_point_object(
                point_id="South Node",
                longitude=south_node_longitude,
                houses=houses,
                include_su28=include_su28,
            )
        )

    sun = next((item for item in objects if item.get("id") == "Sun"), None)
    moon = next((item for item in objects if item.get("id") == "Moon"), None)
    if sun is not None and moon is not None:
        try:
            sun_house = int(str(sun["house"]).removeprefix("House"))
        except (TypeError, ValueError):
            sun_house = 7
        if sun_house >= 7:
            fortuna_longitude = (
                float(houses[0]["lon"]) + moon["lon"] - sun["lon"]
            ) % 360.0
        else:
            fortuna_longitude = (
                float(houses[0]["lon"]) + sun["lon"] - moon["lon"]
            ) % 360.0
        objects.append(
            _build_point_object(
                point_id="Pars Fortuna",
                longitude=fortuna_longitude,
                houses=houses,
                include_su28=include_su28,
            )
        )

    return objects


def _build_local_chart_response(
    *,
    date_text: str,
    time_text: str,
    timezone_name: Optional[str],
    lat: Any = None,
    lon: Any = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
    tradition: bool = False,
    include_su28: bool = True,
    chart_variant: str = "chart",
    house_start_mode: int = 1,
    shape_mode: int = 0,
    hsys: Optional[int] = None,
    zodiacal: Optional[int] = None,
    extra_params: Optional[Dict[str, Any]] = None,
    allow_extended_hsys: bool = False,
) -> Dict[str, Any]:
    birth_info, latitude, longitude = _build_birth_info(
        date_text=date_text,
        time_text=time_text,
        timezone_name=timezone_name,
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
    )
    resolved_hsys = None
    if chart_variant == "chart" and (hsys is not None or zodiacal is not None):
        resolved_hsys = 8 if hsys is None else int(hsys)
        resolved_zodiacal = 0 if zodiacal is None else int(zodiacal)
        if not allow_extended_hsys and resolved_hsys not in {0, 8}:
            raise ValueError("本地盘当前仅支持 hsys=0(整宫制) 或 hsys=8(等宫制)。")
        core_payload = build_core_chart_payload(
            birth_info,
            chart_variant,
            hsys=resolved_hsys,
            zodiacal=resolved_zodiacal,
        )
    else:
        core_payload = build_core_chart_payload(birth_info, chart_variant)
    houses, house1_longitude, house_step_degrees = _build_houses(
        core_payload,
        house_start_mode=house_start_mode,
        shape_mode=shape_mode,
        preserve_core_cusps=allow_extended_hsys,
    )
    objects = _adapt_chart_objects(
        core_payload,
        tradition=tradition,
        include_su28=include_su28,
        houses=houses,
    )
    params = {
        "date": _normalize_date_text(date_text),
        "time": _normalize_time_text(time_text),
        "zone": timezone_name or DEFAULT_BIRTH_TIMEZONE,
        "lat": lat,
        "lon": lon,
        "gpsLat": gps_lat,
        "gpsLon": gps_lon,
        "birthLatitude": round(latitude, 4),
        "birthLongitude": round(longitude, 4),
        "tradition": tradition,
        "chartVariant": chart_variant,
        "houseStartModeApplied": house_start_mode,
        "houseOrientation": "reverse" if house_step_degrees < 0 else "forward",
        "houseSystemResolved": _display_house_system_name(
            (core_payload.get("chart_profile") or {}).get("house_system")
        ),
        "zodiacMode": (core_payload.get("chart_profile") or {}).get("zodiac"),
        "enginePrecision": (core_payload.get("chart_profile") or {}).get(
            "engine_precision"
        ),
        "engineBackend": (core_payload.get("chart_profile") or {}).get(
            "engine_backend"
        ),
    }
    if resolved_hsys is not None:
        params["hsys"] = resolved_hsys
    if resolved_hsys is not None:
        params["zodiacal"] = (core_payload.get("chart_profile") or {}).get("zodiacal")
        params["zodiacLabelZh"] = (core_payload.get("chart_profile") or {}).get(
            "zodiac_label_zh"
        )
    ayanamsha = (core_payload.get("chart_profile") or {}).get("ayanamsha")
    if ayanamsha:
        params["ayanamsha"] = ayanamsha
    if extra_params:
        params.update(extra_params)
    return {
        "params": params,
        "chart": {
            "ok": True,
            "houses": houses,
            "objects": objects,
            "angles": {
                "ascendant": round(
                    float(core_payload["angles"]["ascendant"]["longitude"]), 4
                ),
                "midheaven": round(
                    float(core_payload["angles"]["midheaven"]["longitude"]), 4
                ),
            },
        },
    }


def _house_id_for_houses(longitude: float, houses: List[Dict[str, Any]]) -> str:
    if not houses:
        return "House1"

    ring_direction = _house_direction(houses)
    normalized_longitude = float(longitude) % 360.0
    for index, house in enumerate(houses):
        current = float(house.get("lon", 0.0)) % 360.0
        next_longitude = (
            float(houses[(index + 1) % len(houses)].get("lon", 0.0)) % 360.0
        )
        if ring_direction == "reverse":
            span = (current - next_longitude) % 360.0 or 360.0
            distance = (current - normalized_longitude) % 360.0
        else:
            span = (next_longitude - current) % 360.0 or 360.0
            distance = (normalized_longitude - current) % 360.0
        if distance < span or abs(distance) < 1e-9:
            return str(house.get("id") or f"House{index + 1}")

    return str(houses[0].get("id") or "House1")


def _build_metaphysics_seed(
    *,
    date_text: str,
    time_text: str,
    timezone_name: Optional[str],
    lat: Any = None,
    lon: Any = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
    use_true_solar_time: bool = False,
    day_pillar_strategy: str = DAY_GANZHI_STRATEGY_STANDARD,
) -> MetaphysicsSeed:
    timezone_value = timezone_name or DEFAULT_BIRTH_TIMEZONE
    input_datetime_naive = datetime.fromisoformat(
        f"{_normalize_date_text(date_text)} {_normalize_time_text(time_text)}"
    )
    input_datetime = localize_datetime(input_datetime_naive, timezone_value)
    corrected_datetime = input_datetime
    total_correction_minutes = 0.0
    _, longitude = _resolve_coordinates(
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
    )

    if use_true_solar_time:
        adjustment = calculate_solar_time_adjustment(
            input_datetime_naive,
            timezone_value,
            longitude,
            strategy=SOLAR_TIME_STRATEGY_APPARENT,
        )
        total_correction_minutes = adjustment["total_correction_minutes"]
        corrected_datetime = localize_datetime(
            input_datetime_naive + timedelta(minutes=total_correction_minutes),
            timezone_value,
        )

    pillars = BaZiCalendar.get_four_pillars(
        corrected_datetime,
        timezone_name=timezone_value,
        day_pillar_strategy=day_pillar_strategy,
        civil_datetime=input_datetime,
    )
    calendar_context = build_calendar_context(
        corrected_datetime,
        timezone_name=timezone_value,
        pillars=pillars,
        civil_datetime=input_datetime,
    )
    return MetaphysicsSeed(
        input_datetime=input_datetime,
        corrected_datetime=corrected_datetime,
        timezone=timezone_value,
        longitude=longitude,
        applied_true_solar=use_true_solar_time,
        total_correction_minutes=total_correction_minutes,
        pillars=pillars,
        calendar_context=calendar_context,
    )


def _normalize_canping_gender(value: Any) -> str:
    text = f"{value if value is not None else ''}".strip().lower()
    if text in {"女", "f", "female", "0"}:
        return "女"
    return "男"


def _build_metaphysics_analysis_context(seed: MetaphysicsSeed) -> Dict[str, Any]:
    lunar_context = seed.calendar_context.get("lunar_calendar") or {}
    return {
        "input_datetime": seed.input_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        "corrected_datetime": seed.corrected_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": seed.timezone,
        "longitude": seed.longitude,
        "applied_true_solar": seed.applied_true_solar,
        "time_algorithm": "真太阳时" if seed.applied_true_solar else "直接时间",
        "total_correction_minutes": round(seed.total_correction_minutes, 2),
        "current_jieqi": seed.calendar_context["current_solar_term"]["name"],
        "next_jieqi": seed.calendar_context["next_solar_term"]["name"],
        "lunar_display": lunar_context.get("display"),
    }


def _render_qimen_palace_sections(qimen: Dict[str, Any]) -> List[Tuple[str, str]]:
    sections: List[Tuple[str, str]] = []
    for palace in qimen.get("palaces", []) or []:
        if not isinstance(palace, dict):
            continue
        content_palace = palace.get("content_palace")
        content_trigram = palace.get("content_trigram")
        content_line = ""
        if content_palace and (
            content_palace != palace.get("name")
            or content_trigram != palace.get("trigram")
        ):
            content_line = f"内容来源：{content_palace} / {content_trigram or '无'}"
        sections.append(
            (
                palace.get("name", "宫位"),
                _join_lines(
                    [
                        f"宫卦：{palace.get('trigram', '无')}",
                        content_line,
                        f"天盘干：{palace.get('heaven_stem', '无')}",
                        f"地盘干：{palace.get('earth_stem', '无')}",
                        f"八神：{palace.get('god', '无')}",
                        f"九星：{palace.get('star', '无')}",
                        f"八门：{palace.get('door', '无')}",
                        f"门卦：{(palace.get('door_hexagram') or {}).get('name', '无')}",
                    ]
                ),
            )
        )
    return sections


def _build_qimen_palace_overview_lines(qimen: Dict[str, Any]) -> List[str]:
    return [
        (
            f"{palace.get('name', '宫位')}："
            f"天盘干：{palace.get('heaven_stem', '无')}；"
            f"地盘干：{palace.get('earth_stem', '无')}；"
            f"八神：{palace.get('god', '无')}；"
            f"九星：{palace.get('star', '无')}；"
            f"八门：{palace.get('door', '无')}"
            + (
                f"；内容来源：{palace.get('content_palace', '无')} / {palace.get('content_trigram', '无')}"
                if palace.get("content_palace")
                and (
                    palace.get("content_palace") != palace.get("name")
                    or palace.get("content_trigram") != palace.get("trigram")
                )
                else ""
            )
        )
        for palace in qimen.get("palaces", []) or []
        if isinstance(palace, dict)
    ]
