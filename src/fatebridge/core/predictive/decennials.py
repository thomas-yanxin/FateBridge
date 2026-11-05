"""十年时主（Decennials）推运法。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fatebridge.core.astro.birth import AstroBirthInfo

from ._common import determine_sect, planet_label, point_absolute_position

# 起始模式与排序方式
DECENNIAL_START_MODE_SECT_LIGHT = "sect_light"
DECENNIAL_ORDER_ZODIACAL = "zodiacal"
DECENNIAL_ORDER_CHALDEAN = "chaldean"

# 日主分配方法
DECENNIAL_DAY_METHOD_VALENS = "valens"
DECENNIAL_DAY_METHOD_HEPHAISTIO = "hephaistio"

# 历法类型
DECENNIAL_CALENDAR_TRADITIONAL = "calendar_360"
DECENNIAL_CALENDAR_ACTUAL = "calendar_365_25"

# 七星顺序与基础月数
DECENNIAL_TRADITIONAL_PLANETS = [
    "Saturn",
    "Jupiter",
    "Mars",
    "Sun",
    "Venus",
    "Mercury",
    "Moon",
]
DECENNIAL_PLANET_BASE_MONTHS = {
    "Saturn": 30,
    "Jupiter": 12,
    "Mars": 15,
    "Sun": 19,
    "Venus": 8,
    "Mercury": 20,
    "Moon": 25,
}

# 赫法伊斯提翁日主分配表（分钟数）
DECENNIAL_HEPHAISTIO_DAY_TABLE = {
    "Saturn": {
        "Saturn": 210,
        "Jupiter": 84,
        "Mars": 105,
        "Sun": 133,
        "Venus": 56,
        "Mercury": 150,
        "Moon": 175,
    },
    "Jupiter": {
        "Jupiter": 34,
        "Saturn": 85,
        "Mars": 42,
        "Sun": 54,
        "Venus": 22,
        "Mercury": 57,
        "Moon": 71,
    },
    "Mars": {
        "Mars": 52,
        "Sun": 66,
        "Venus": 28,
        "Mercury": 70,
        "Moon": 87,
        "Saturn": 105,
        "Jupiter": 42,
    },
    "Sun": {
        "Sun": 83,
        "Moon": 118,
        "Saturn": 130,
        "Jupiter": 52,
        "Mars": 64,
        "Venus": 35,
        "Mercury": 87,
    },
    "Venus": {
        "Venus": 15,
        "Sun": 36,
        "Moon": 47,
        "Saturn": 57,
        "Jupiter": 22,
        "Mars": 28,
        "Mercury": 38,
    },
    "Mercury": {
        "Mercury": 96,
        "Sun": 90,
        "Moon": 117,
        "Saturn": 141,
        "Jupiter": 56,
        "Mars": 70,
        "Venus": 36,
    },
    "Moon": {
        "Moon": 148,
        "Sun": 115,
        "Saturn": 177,
        "Jupiter": 71,
        "Mars": 87,
        "Venus": 47,
        "Mercury": 119,
    },
}

# 总基础月数及时间换算常量
DECENNIAL_TOTAL_BASE_MONTHS = 129
DECENNIAL_TOTAL_L1_DAYS = DECENNIAL_TOTAL_BASE_MONTHS * 30
DECENNIAL_FIVE_MINUTES = 5
DECENNIAL_MINUTES_PER_DAY = 24 * 60
DECENNIAL_MINUTES_PER_MONTH = 30 * DECENNIAL_MINUTES_PER_DAY
DECENNIAL_MINUTES_PER_YEAR = 12 * DECENNIAL_MINUTES_PER_MONTH
DECENNIAL_ACTUAL_YEAR_SCALE_NUMERATOR = 1461
DECENNIAL_ACTUAL_YEAR_SCALE_DENOMINATOR = 1440


def _rotate_items(items: List[str], start_value: Optional[str]) -> List[str]:
    if not items or not start_value or start_value not in items:
        return list(items)
    index = items.index(start_value)
    return items[index:] + items[:index]


def _build_decennial_zodiacal_order(subject: Any) -> List[str]:
    ranked = []
    for index, planet in enumerate(DECENNIAL_TRADITIONAL_PLANETS):
        longitude = point_absolute_position(subject, planet)
        ranked.append((longitude, index, planet))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [planet for _, _, planet in ranked]


def resolve_decennial_start_planet(subject: Any, start_mode: Optional[str]) -> str:
    if start_mode and start_mode != DECENNIAL_START_MODE_SECT_LIGHT:
        if start_mode in DECENNIAL_TRADITIONAL_PLANETS:
            return start_mode
    return "Sun" if determine_sect(subject) == "day" else "Moon"


def get_decennial_order(
    subject: Any, start_planet: str, order_type: Optional[str]
) -> List[str]:
    if order_type == DECENNIAL_ORDER_CHALDEAN:
        base = list(DECENNIAL_TRADITIONAL_PLANETS)
    else:
        base = _build_decennial_zodiacal_order(subject)
    return _rotate_items(base, start_planet)


def _rounded_distribution(
    total_value: float,
    order: List[str],
    round_unit: int,
    preserve_last: bool = True,
) -> List[Dict[str, Any]]:
    segments = []
    consumed = 0.0
    for index, planet in enumerate(order):
        exact = (
            total_value
            * DECENNIAL_PLANET_BASE_MONTHS[planet]
            / DECENNIAL_TOTAL_BASE_MONTHS
        )
        value = exact
        if index == len(order) - 1 and preserve_last:
            value = total_value - consumed
        elif round_unit > 0:
            value = round(exact / round_unit) * round_unit
        value = max(0.0, value)
        consumed += value
        segments.append({"planet": planet, "value": value})
    return segments


def _minutes_from_level_three(
    total_days: float,
    day_method: Optional[str],
    month_lord: str,
    order: List[str],
) -> List[Dict[str, Any]]:
    if day_method == DECENNIAL_DAY_METHOD_HEPHAISTIO:
        table = DECENNIAL_HEPHAISTIO_DAY_TABLE.get(month_lord)
        if table:
            return [
                {
                    "planet": planet,
                    "value": table.get(planet, 0) * DECENNIAL_MINUTES_PER_DAY,
                }
                for planet in order
            ]
    return _rounded_distribution(
        total_days * DECENNIAL_MINUTES_PER_DAY,
        order,
        DECENNIAL_FIVE_MINUTES,
    )


def _minutes_from_level_four(
    total_minutes: float,
    order: List[str],
) -> List[Dict[str, Any]]:
    return _rounded_distribution(total_minutes, order, 1)


def _scale_nominal_minutes(total_minutes: float, calendar_type: Optional[str]) -> int:
    normalized = max(0, round(float(total_minutes or 0)))
    if calendar_type != DECENNIAL_CALENDAR_ACTUAL:
        return normalized
    return round(
        normalized
        * DECENNIAL_ACTUAL_YEAR_SCALE_NUMERATOR
        / DECENNIAL_ACTUAL_YEAR_SCALE_DENOMINATOR
    )


def _scale_nominal_segments(
    segments: List[Dict[str, Any]],
    calendar_type: Optional[str],
    round_unit: int = 1,
) -> List[Dict[str, Any]]:
    if calendar_type != DECENNIAL_CALENDAR_ACTUAL:
        return [
            {
                "planet": item["planet"],
                "value": max(0, round(float(item["value"] or 0))),
            }
            for item in segments
        ]

    unit = round_unit if round_unit > 0 else 1
    total_nominal = sum(max(0.0, float(item["value"] or 0)) for item in segments)
    total_scaled = (
        round(_scale_nominal_minutes(total_nominal, calendar_type) / unit) * unit
    )
    scaled = []
    consumed = 0
    cumulative_exact = 0.0
    for index, item in enumerate(segments):
        nominal_value = max(0.0, float(item["value"] or 0))
        cumulative_exact += (
            nominal_value
            * DECENNIAL_ACTUAL_YEAR_SCALE_NUMERATOR
            / DECENNIAL_ACTUAL_YEAR_SCALE_DENOMINATOR
        )
        if index == len(segments) - 1:
            value = total_scaled - consumed
        else:
            value = round(cumulative_exact / unit) * unit - consumed
        value = max(0, value)
        consumed += value
        scaled.append({"planet": item["planet"], "value": value})
    return scaled


def _format_nominal_offset(total_minutes: int, level: int) -> str:
    minutes = max(0, round(total_minutes or 0))
    years, minutes = divmod(minutes, DECENNIAL_MINUTES_PER_YEAR)
    months, minutes = divmod(minutes, DECENNIAL_MINUTES_PER_MONTH)
    days, minutes = divmod(minutes, DECENNIAL_MINUTES_PER_DAY)
    hours, minutes = divmod(minutes, 60)
    if level >= 4:
        prefix = ""
        if years:
            prefix += f"{years}年"
        if months:
            prefix += f"{months}个月"
        if days:
            prefix += f"{days}天"
        return f"{prefix or '0天'} {hours:02d}:{minutes:02d}"
    if level == 3:
        parts = []
        if years:
            parts.append(f"{years}年")
        if months:
            parts.append(f"{months}个月")
        if days or not parts:
            parts.append(f"{days}天")
        return "".join(parts)
    parts = []
    if years:
        parts.append(f"{years}年")
    if months or not parts:
        parts.append(f"{months}个月")
    return "".join(parts)


def _format_nominal_range(
    start_offset_minutes: int, end_offset_minutes: int, level: int
) -> str:
    return (
        f"{_format_nominal_offset(start_offset_minutes, level)} - "
        f"{_format_nominal_offset(end_offset_minutes, level)}"
    )


def _build_decennial_node(
    level: int,
    key: str,
    planet: str,
    start_moment: datetime,
    end_moment: datetime,
    analysis_datetime: datetime,
    sublevel: List[Dict[str, Any]],
    start_offset_minutes: int,
    end_offset_minutes: int,
) -> Dict[str, Any]:
    active = start_moment <= analysis_datetime < end_moment
    return {
        "key": key,
        "level": level,
        "planet": planet,
        "planet_label": planet_label(planet),
        "date": (
            f"{start_moment.strftime('%Y-%m-%d')} - {end_moment.strftime('%Y-%m-%d')}"
        ),
        "nominal": _format_nominal_range(
            start_offset_minutes, end_offset_minutes, level
        ),
        "start": start_moment.isoformat(),
        "end": end_moment.isoformat(),
        "active": active,
        "sublevel": sublevel,
        "start_offset_minutes": start_offset_minutes,
        "end_offset_minutes": end_offset_minutes,
    }


def _build_decennial_level_four(
    level_three_node: Dict[str, Any],
    base_order: List[str],
    analysis_datetime: datetime,
    calendar_type: Optional[str],
) -> List[Dict[str, Any]]:
    order = _rotate_items(base_order, level_three_node["planet"])
    nominal_segments = _minutes_from_level_four(
        level_three_node["nominal_minutes"], order
    )
    actual_segments = _scale_nominal_segments(nominal_segments, calendar_type, 1)
    data = []
    cursor = level_three_node["start_moment"]
    cursor_offset = level_three_node["start_offset_minutes"]
    for index, nominal_item in enumerate(nominal_segments):
        actual_item = actual_segments[index]
        next_moment = cursor + timedelta(minutes=actual_item["value"])
        next_offset = cursor_offset + round(nominal_item["value"])
        data.append(
            _build_decennial_node(
                4,
                f"{level_three_node['key']}_l4_{index}",
                actual_item["planet"],
                cursor,
                next_moment,
                analysis_datetime,
                [],
                cursor_offset,
                next_offset,
            )
        )
        cursor = next_moment
        cursor_offset = next_offset
    return data


def _build_decennial_level_three(
    level_two_node: Dict[str, Any],
    base_order: List[str],
    day_method: Optional[str],
    analysis_datetime: datetime,
    calendar_type: Optional[str],
) -> List[Dict[str, Any]]:
    order = _rotate_items(base_order, level_two_node["planet"])
    nominal_segments = _minutes_from_level_three(
        level_two_node["nominal_days"],
        day_method,
        level_two_node["planet"],
        order,
    )
    actual_segments = _scale_nominal_segments(nominal_segments, calendar_type, 1)
    data = []
    cursor = level_two_node["start_moment"]
    cursor_offset = level_two_node["start_offset_minutes"]
    for index, nominal_item in enumerate(nominal_segments):
        actual_item = actual_segments[index]
        next_moment = cursor + timedelta(minutes=actual_item["value"])
        meta = {
            "key": f"{level_two_node['key']}_l3_{index}",
            "planet": actual_item["planet"],
            "start_moment": cursor,
            "end_moment": next_moment,
            "nominal_minutes": round(nominal_item["value"]),
            "start_offset_minutes": cursor_offset,
            "end_offset_minutes": cursor_offset + round(nominal_item["value"]),
        }
        sublevel = _build_decennial_level_four(
            meta,
            base_order,
            analysis_datetime,
            calendar_type,
        )
        data.append(
            _build_decennial_node(
                3,
                meta["key"],
                meta["planet"],
                meta["start_moment"],
                meta["end_moment"],
                analysis_datetime,
                sublevel,
                meta["start_offset_minutes"],
                meta["end_offset_minutes"],
            )
        )
        cursor = next_moment
        cursor_offset = meta["end_offset_minutes"]
    return data


def _build_decennial_level_two(
    level_one_node: Dict[str, Any],
    base_order: List[str],
    day_method: Optional[str],
    analysis_datetime: datetime,
    calendar_type: Optional[str],
) -> List[Dict[str, Any]]:
    order = _rotate_items(base_order, level_one_node["planet"])
    nominal_segments: List[Dict[str, Any]] = [
        {
            "planet": planet,
            "value": DECENNIAL_PLANET_BASE_MONTHS[planet] * DECENNIAL_MINUTES_PER_MONTH,
        }
        for planet in order
    ]
    actual_segments = _scale_nominal_segments(nominal_segments, calendar_type, 1)
    data = []
    cursor = level_one_node["start_moment"]
    cursor_offset = level_one_node["start_offset_minutes"]
    for index, nominal_item in enumerate(nominal_segments):
        actual_item = actual_segments[index]
        next_moment = cursor + timedelta(minutes=actual_item["value"])
        meta = {
            "key": f"{level_one_node['key']}_l2_{index}",
            "planet": nominal_item["planet"],
            "nominal_days": round(nominal_item["value"]) / DECENNIAL_MINUTES_PER_DAY,
            "start_moment": cursor,
            "end_moment": next_moment,
            "start_offset_minutes": cursor_offset,
            "end_offset_minutes": cursor_offset + round(nominal_item["value"]),
        }
        sublevel = _build_decennial_level_three(
            meta,
            base_order,
            day_method,
            analysis_datetime,
            calendar_type,
        )
        data.append(
            _build_decennial_node(
                2,
                meta["key"],
                meta["planet"],
                meta["start_moment"],
                meta["end_moment"],
                analysis_datetime,
                sublevel,
                meta["start_offset_minutes"],
                meta["end_offset_minutes"],
            )
        )
        cursor = next_moment
        cursor_offset = meta["end_offset_minutes"]
    return data


def _resolve_decennial_count(
    birth_moment: datetime,
    analysis_datetime: datetime,
    calendar_type: Optional[str],
) -> int:
    age_minutes = max(0.0, (analysis_datetime - birth_moment).total_seconds() / 60.0)
    l1_minutes = _scale_nominal_minutes(
        DECENNIAL_TOTAL_L1_DAYS * DECENNIAL_MINUTES_PER_DAY,
        calendar_type,
    )
    return max(7, int((age_minutes + l1_minutes - 1) // l1_minutes) + 2)


def _truncate_decennial_node(
    node: Optional[Dict[str, Any]], max_level: int
) -> Optional[Dict[str, Any]]:
    """Return a copy of a decennial node with its sublevel tree cut at ``max_level``.

    The decennial tree is four levels deep (``7**4`` ≈ 2400 leaf nodes); serialising
    it whole produced a multi-megabyte response that no agent context — nor the MCP
    /HTTP transports — can carry. The active drill-down is already exposed via
    ``current_level_1/2/3``, so the timeline only needs the decade overview and each
    active level only its immediate children. Nodes at ``max_level`` keep an empty
    ``sublevel``; shallower nodes recurse. No computed value is altered — only the
    depth of the serialised subtree.
    """
    if node is None:
        return None
    truncated = dict(node)
    if node.get("level", 0) >= max_level:
        truncated["sublevel"] = []
    else:
        truncated["sublevel"] = [
            _truncate_decennial_node(child, max_level)
            for child in node.get("sublevel", []) or []
        ]
    return truncated


def build_decennials_payload(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    analysis_datetime: datetime,
    start_mode: str = DECENNIAL_START_MODE_SECT_LIGHT,
    order_type: str = DECENNIAL_ORDER_ZODIACAL,
    day_method: str = DECENNIAL_DAY_METHOD_VALENS,
    calendar_type: str = DECENNIAL_CALENDAR_TRADITIONAL,
) -> Dict[str, Any]:
    birth_moment = birth_info.local_datetime
    start_planet = resolve_decennial_start_planet(natal_subject, start_mode)
    base_order = get_decennial_order(natal_subject, start_planet, order_type)
    count = _resolve_decennial_count(birth_moment, analysis_datetime, calendar_type)
    data = []
    l1_nominal_minutes = DECENNIAL_TOTAL_L1_DAYS * DECENNIAL_MINUTES_PER_DAY
    l1_actual_minutes = _scale_nominal_minutes(l1_nominal_minutes, calendar_type)
    cursor = birth_moment
    for index in range(count):
        planet = base_order[index % len(base_order)]
        start_moment = cursor
        end_moment = start_moment + timedelta(minutes=l1_actual_minutes)
        start_offset = l1_nominal_minutes * index
        end_offset = start_offset + l1_nominal_minutes
        meta: Dict[str, Any] = {
            "key": f"l1_{index}",
            "planet": planet,
            "start_moment": start_moment,
            "end_moment": end_moment,
            "start_offset_minutes": start_offset,
            "end_offset_minutes": end_offset,
        }
        sublevel = _build_decennial_level_two(
            meta,
            base_order,
            day_method,
            analysis_datetime,
            calendar_type,
        )
        data.append(
            _build_decennial_node(
                1,
                meta["key"],
                planet,
                start_moment,
                end_moment,
                analysis_datetime,
                sublevel,
                start_offset,
                end_offset,
            )
        )
        cursor = end_moment

    current_level_1 = next((node for node in data if node["active"]), None)
    current_level_2 = None
    current_level_3 = None
    if current_level_1:
        current_level_2 = next(
            (node for node in current_level_1["sublevel"] if node["active"]),
            None,
        )
        if current_level_2:
            current_level_3 = next(
                (node for node in current_level_2["sublevel"] if node["active"]),
                None,
            )

    return {
        "resolved_start_planet": start_planet,
        "resolved_start_planet_label": planet_label(start_planet),
        "base_order": base_order,
        # The active path keeps full granularity down its own chain; each level
        # exposes only its immediate children (the next level lives in the next
        # current_level_*). The timeline is a decade overview (level 1 only).
        "current_level_1": _truncate_decennial_node(current_level_1, 2),
        "current_level_2": _truncate_decennial_node(current_level_2, 3),
        "current_level_3": _truncate_decennial_node(current_level_3, 4),
        "timeline": [_truncate_decennial_node(node, 1) for node in data[:7]],
    }
