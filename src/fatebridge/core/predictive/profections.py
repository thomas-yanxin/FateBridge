"""岁运（年主星）推运法（Annual Profections）。"""

from __future__ import annotations

from datetime import timezone

from ._common import (
    RULER_BY_SIGN,
    SIGNS,
    Any,
    AstroBirthInfo,
    Dict,
    List,
    build_subject,
    calculate_age_years_int,
    collect_aspect_hits,
    datetime,
    extract_reference_longitudes,
    normalize_sign_name,
    parse_timezone_name,
    planet_label,
    point_to_dict,
    resolve_local_birthday_anniversary,
    sign_label,
)


def monthly_profection_segment(
    year_start: datetime, year_end: datetime, month_offset: int
) -> tuple[datetime, datetime]:
    """Return the [start, end) of the ``month_offset``-th equal twelfth.

    Divide elapsed UTC time into twelfths, then display in the starting zone.
    Derive each boundary from the full interval so microsecond rounding never
    accumulates and the last boundary remains exactly ``year_end``.
    """
    start_utc = year_start.astimezone(timezone.utc)
    span = year_end.astimezone(timezone.utc) - start_utc
    start = start_utc + span * month_offset / 12
    end = start_utc + span * (month_offset + 1) / 12
    return start.astimezone(year_start.tzinfo), end.astimezone(year_start.tzinfo)


def monthly_profection_index(
    year_start: datetime, year_end: datetime, moment: datetime
) -> int:
    """Index (0–11) of the equal-twelfth segment that contains ``moment``."""
    instant = moment.astimezone(timezone.utc)
    for index in range(11, 0, -1):
        start, _ = monthly_profection_segment(year_start, year_end, index)
        if instant >= start.astimezone(timezone.utc):
            return index
    return 0


def build_annual_profection_payload(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    analysis_datetime: datetime,
) -> Dict[str, Any]:
    analysis_datetime, last_birthday = resolve_last_birthday(
        birth_info, analysis_datetime=analysis_datetime
    )
    age_years_int = calculate_age_years_int(birth_info, analysis_datetime)
    asc_sign = normalize_sign_name(natal_subject.ascendant.sign)
    asc_index = SIGNS.index(asc_sign)
    activated_house = (age_years_int % 12) + 1
    activated_sign = SIGNS[(asc_index + activated_house - 1) % 12]
    lord = RULER_BY_SIGN[activated_sign]

    next_birthday = resolve_local_birthday_anniversary(
        birth_info.local_datetime,
        last_birthday.year + 1,
        tzinfo=last_birthday.tzinfo,
    )
    months_since_birthday = monthly_profection_index(
        last_birthday, next_birthday, analysis_datetime
    )
    monthly_house = ((activated_house - 1 + months_since_birthday) % 12) + 1
    monthly_sign = SIGNS[(asc_index + monthly_house - 1) % 12]

    return {
        "activated_house": activated_house,
        "activated_sign": activated_sign,
        "activated_sign_label": sign_label(activated_sign),
        "lord": lord,
        "lord_label": planet_label(lord),
        "monthly_house": monthly_house,
        "monthly_sign": monthly_sign,
        "monthly_sign_label": sign_label(monthly_sign),
    }


def resolve_last_birthday(
    birth_info: AstroBirthInfo,
    *,
    analysis_datetime: datetime,
) -> tuple[datetime, datetime]:
    analysis_local = analysis_datetime.astimezone(
        parse_timezone_name(birth_info.timezone)
    )
    birthday_this_year = resolve_local_birthday_anniversary(
        birth_info.local_datetime,
        analysis_local.year,
        tzinfo=analysis_local.tzinfo,
    )
    if analysis_local < birthday_this_year:
        last_birthday = resolve_local_birthday_anniversary(
            birth_info.local_datetime,
            analysis_local.year - 1,
            tzinfo=analysis_local.tzinfo,
        )
    else:
        last_birthday = birthday_this_year
    return analysis_local, last_birthday


def build_monthly_profections_payload(
    *,
    annual_house: int,
    asc_sign: str,
    year_start: datetime,
    year_end: datetime,
    analysis_datetime: datetime,
) -> List[Dict[str, Any]]:
    timeline: List[Dict[str, Any]] = []
    asc_index = SIGNS.index(asc_sign)
    instant = analysis_datetime.astimezone(timezone.utc)
    for month_offset in range(12):
        start, end = monthly_profection_segment(year_start, year_end, month_offset)
        house = ((annual_house - 1 + month_offset) % 12) + 1
        sign_name = SIGNS[(asc_index + house - 1) % 12]
        ruler = RULER_BY_SIGN[sign_name]
        timeline.append(
            {
                "month_index": month_offset + 1,
                "house": house,
                "house_label": f"第{house}宫",
                "sign": sign_name,
                "sign_label": sign_label(sign_name),
                "lord": ruler,
                "lord_label": planet_label(ruler),
                "start": start.isoformat(),
                "end": end.isoformat(),
                "active": start.astimezone(timezone.utc)
                <= instant
                < end.astimezone(timezone.utc),
            }
        )
    return timeline


def build_given_year_payload(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    analysis_datetime: datetime,
    annual_profection: Dict[str, Any],
    return_longitude: float,
    return_latitude: float,
    return_timezone: str,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
) -> Dict[str, Any]:
    analysis_local, last_birthday = resolve_last_birthday(
        birth_info,
        analysis_datetime=analysis_datetime,
    )
    year_end = resolve_local_birthday_anniversary(
        birth_info.local_datetime,
        last_birthday.year + 1,
        tzinfo=last_birthday.tzinfo,
    )
    zone = parse_timezone_name(return_timezone)
    analysis_local = analysis_local.astimezone(zone)
    last_birthday = last_birthday.astimezone(zone)
    year_end = year_end.astimezone(zone)
    given_year_subject = build_subject(
        name=f"{birth_info.name}-given-year",
        local_datetime=analysis_local,
        longitude=return_longitude,
        latitude=return_latitude,
        timezone_name=return_timezone,
        house_system=house_system,
        zodiac_type=zodiac_type,
    )
    monthly_profections = build_monthly_profections_payload(
        annual_house=annual_profection["activated_house"],
        asc_sign=normalize_sign_name(natal_subject.ascendant.sign),
        year_start=last_birthday,
        year_end=year_end,
        analysis_datetime=analysis_local,
    )
    hits = collect_aspect_hits(
        source_longitudes=extract_reference_longitudes(given_year_subject),
        target_longitudes=extract_reference_longitudes(natal_subject),
        orb_limit=1.5,
    )
    return {
        "analysis_datetime": analysis_local.isoformat(),
        "year_start": last_birthday.isoformat(),
        "year_end": year_end.isoformat(),
        "sun": point_to_dict("Sun", given_year_subject.sun),
        "moon": point_to_dict("Moon", given_year_subject.moon),
        "ascendant": point_to_dict("Ascendant", given_year_subject.ascendant),
        "medium_coeli": point_to_dict(
            "Medium_Coeli",
            given_year_subject.medium_coeli,
        ),
        "annual_profection": annual_profection,
        "monthly_profections": monthly_profections,
        "hits": hits[:8],
        "location": {
            "longitude": return_longitude,
            "latitude": return_latitude,
            "timezone": return_timezone,
        },
    }
