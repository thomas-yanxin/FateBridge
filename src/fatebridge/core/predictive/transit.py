"""行星过境（Transits）推运法。"""

from __future__ import annotations

from ._common import (
    TRANSIT_POINT_NAMES,
    Any,
    AstroBirthInfo,
    Counter,
    Dict,
    build_subject,
    collect_aspect_hits,
    datetime,
    extract_named_longitudes,
    extract_named_points,
    parse_timezone_name,
)


def build_transit_payload(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    analysis_datetime: datetime,
    transit_longitude: float,
    transit_latitude: float,
    transit_timezone: str,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    orb_limit: float = 1.5,
) -> Dict[str, Any]:
    analysis_local = analysis_datetime.astimezone(parse_timezone_name(transit_timezone))
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
    hits = collect_aspect_hits(
        source_longitudes=extract_named_longitudes(
            transit_subject, TRANSIT_POINT_NAMES
        ),
        target_longitudes=extract_named_longitudes(natal_subject, TRANSIT_POINT_NAMES),
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
    exact_hits = [item for item in hits if float(item.get("orb", 99.0)) <= 0.3][:12]
    return {
        "calculation_basis": transit_subject.calculation_basis,
        "analysis_datetime": analysis_local.isoformat(),
        "location": {
            "longitude": transit_longitude,
            "latitude": transit_latitude,
            "timezone": transit_timezone,
        },
        "orb_limit": orb_limit,
        "sun": transit_reference["sun"],
        "moon": transit_reference["moon"],
        "ascendant": transit_reference["ascendant"],
        "medium_coeli": transit_reference["medium_coeli"],
        "transit_reference": transit_reference,
        "natal_reference": natal_reference,
        "house_emphasis": house_emphasis,
        "hits": hits[:24],
        "exact_hits": exact_hits,
    }
