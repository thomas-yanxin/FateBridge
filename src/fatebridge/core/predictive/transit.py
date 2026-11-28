"""行星过境（Transits）推运法。"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
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


def build_transit_analysis(
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
    max_hits: int | None = None,
    transit_subject: NativeSubject | None = None,
    include_natal_reference: bool = True,
    scan_days: int | None = None,
    high_latitude_fallback: str = "error",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    transit_zone = parse_timezone_name(transit_timezone)
    analysis_utc = utc_calendar(analysis_datetime)
    analysis_local = ZonedCalendar(analysis_utc, transit_zone).require_datetime()
    subject = transit_subject or build_subject(
        name=f"{birth_info.name}-transit",
        local_datetime=analysis_local,
        longitude=transit_longitude,
        latitude=transit_latitude,
        timezone_name=transit_timezone,
        house_system=house_system,
        zodiac_type=zodiac_type,
        high_latitude_fallback=high_latitude_fallback,
    )
    transit_reference = extract_named_points(subject, TRANSIT_POINT_NAMES)
    source_longitudes = extract_named_longitudes(subject, TRANSIT_POINT_NAMES)
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
    all_exact_hits = [hit for hit in hits if hit["orb"] <= exact_orb_limit]
    selected_hits = hits[:max_hits] if max_hits is not None else hits
    selected_exact_hits = (
        all_exact_hits[:max_hits] if max_hits is not None else all_exact_hits
    )
    payload: dict[str, Any] = {
        "calculation_basis": subject.calculation_basis,
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
        "house_emphasis": house_emphasis,
        "hits": selected_hits,
        "hits_total_count": len(hits),
        "exact_hits": selected_exact_hits,
        "exact_hits_total_count": len(all_exact_hits),
    }
    if include_natal_reference:
        payload["natal_reference"] = extract_named_points(
            natal_subject, TRANSIT_POINT_NAMES
        )
    if scan_days is not None:
        tight_orb_limit = min(orb_limit, 1.0)
        transit_timeline: list[dict[str, Any]] = []
        for day_offset in range(scan_days):
            step_utc = analysis_utc.shifted(timedelta(days=day_offset))
            step_zoned = ZonedCalendar(step_utc, transit_zone)
            step_local = step_zoned.require_datetime()
            if day_offset == 0:
                step_hits = hits
            else:
                step_subject = build_subject(
                    name=f"{birth_info.name}-transit-{day_offset}",
                    local_datetime=step_local,
                    longitude=transit_longitude,
                    latitude=transit_latitude,
                    timezone_name=transit_timezone,
                    house_system=house_system,
                    zodiac_type=zodiac_type,
                    high_latitude_fallback=high_latitude_fallback,
                )
                step_hits = collect_aspect_hits(
                    source_longitudes=extract_named_longitudes(
                        step_subject, TRANSIT_POINT_NAMES
                    ),
                    target_longitudes=target_longitudes,
                    orb_limit=tight_orb_limit,
                )
            step_exact_hits = [
                hit for hit in step_hits if hit["orb"] <= exact_orb_limit
            ]
            step_tight_hits = [
                hit for hit in step_hits if hit["orb"] <= tight_orb_limit
            ]
            transit_timeline.append(
                {
                    "day_offset": day_offset,
                    "date": step_zoned.isoformat().split("T", 1)[0],
                    "analysis_datetime": format_local_time_or_utc(step_local),
                    "exact_hits": (
                        step_exact_hits[:max_hits]
                        if max_hits is not None
                        else step_exact_hits
                    ),
                    "exact_hits_total_count": len(step_exact_hits),
                    "tight_hits": (
                        step_tight_hits[:max_hits]
                        if max_hits is not None
                        else step_tight_hits
                    ),
                    "tight_hits_total_count": len(step_tight_hits),
                }
            )
        payload["scan_days"] = scan_days
        payload["tight_orb_limit"] = tight_orb_limit
        payload["transit_timeline"] = transit_timeline
    return payload, hits


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
    max_hits: int | None = None,
    transit_subject: NativeSubject | None = None,
    include_natal_reference: bool = True,
    scan_days: int | None = None,
    high_latitude_fallback: str = "error",
) -> dict[str, Any]:
    payload, _ = build_transit_analysis(
        birth_info,
        natal_subject,
        analysis_datetime=analysis_datetime,
        transit_longitude=transit_longitude,
        transit_latitude=transit_latitude,
        transit_timezone=transit_timezone,
        house_system=house_system,
        zodiac_type=zodiac_type,
        orb_limit=orb_limit,
        max_hits=max_hits,
        transit_subject=transit_subject,
        include_natal_reference=include_natal_reference,
        scan_days=scan_days,
        high_latitude_fallback=high_latitude_fallback,
    )
    return payload
