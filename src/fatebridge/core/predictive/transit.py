"""行星过境（Transits）推运法。"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.predictive._common import (
    TRANSIT_POINT_NAMES,
    build_subject,
    collect_aspect_hits,
    extract_named_longitudes,
    extract_named_points,
)
from fatebridge.core.predictive.native_chart import NativeSubject
from fatebridge.utils.civil_time import ZonedCalendar, utc_calendar
from fatebridge.utils.timezones import format_local_time_or_utc, parse_timezone_name


def build_transit_payload(
    birth_info: AstroBirthInfo,
    natal_subject: NativeSubject,
    *,
    analysis_datetime: datetime,
    transit_longitude: float,
    transit_latitude: float,
    transit_timezone: str,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    orb_limit: float = 1.5,
) -> dict[str, Any]:
    analysis_local = ZonedCalendar(
        utc_calendar(analysis_datetime), parse_timezone_name(transit_timezone)
    ).require_datetime()
    transit_subject = build_subject(
        name=f"{birth_info.name}-transit",
        local_datetime=analysis_local,
        longitude=transit_longitude,
        latitude=transit_latitude,
        timezone_name=transit_timezone,
        house_system=house_system,
        zodiac_type=zodiac_type,
    )
    transit_reference = extract_named_points(transit_subject, TRANSIT_POINT_NAMES)
    natal_reference = extract_named_points(natal_subject, TRANSIT_POINT_NAMES)
    source_longitudes = extract_named_longitudes(transit_subject, TRANSIT_POINT_NAMES)
    target_longitudes = extract_named_longitudes(natal_subject, TRANSIT_POINT_NAMES)
    hits = collect_aspect_hits(
        source_longitudes=source_longitudes,
        target_longitudes=target_longitudes,
        orb_limit=orb_limit,
    )
    house_counter = Counter(
        point["house"]
        for key, point in transit_reference.items()
        if key not in {"ascendant", "medium_coeli"} and point.get("house") is not None
    )
    house_emphasis = [
        {
            "house": house,
            "house_label": f"第{house}宫",
            "count": count,
        }
        for house, count in sorted(
            house_counter.items(), key=lambda item: (-item[1], item[0])
        )
    ]
    exact_orb_limit = min(orb_limit, 0.3)
    exact_hits = collect_aspect_hits(
        source_longitudes=source_longitudes,
        target_longitudes=target_longitudes,
        orb_limit=exact_orb_limit,
    )[:12]
    return {
        "calculation_basis": transit_subject.calculation_basis,
        "analysis_datetime": format_local_time_or_utc(analysis_local),
        "location": {
            "longitude": transit_longitude,
            "latitude": transit_latitude,
            "timezone": transit_timezone,
        },
        "orb_limit": orb_limit,
        "exact_orb_limit": exact_orb_limit,
        "sun": transit_reference["sun"],
        "moon": transit_reference["moon"],
        "ascendant": (
            transit_reference["ascendant"] if "Ascendant" in source_longitudes else None
        ),
        "medium_coeli": transit_reference["medium_coeli"],
        "transit_reference": transit_reference,
        "natal_reference": natal_reference,
        "house_emphasis": house_emphasis,
        "hits": hits[:24],
        "exact_hits": exact_hits,
    }
