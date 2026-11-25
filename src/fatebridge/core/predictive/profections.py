"""岁运（年主星）推运法（Annual Profections）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fatebridge.core.astro.angle_definitions import is_ascendant_resolved
from fatebridge.core.astro.astrology_tables import RULER_BY_SIGN, SIGNS
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.predictive._common import (
    build_subject,
    collect_aspect_hits,
    extract_reference_longitudes,
    extract_reference_points,
    normalize_sign_name,
    planet_label,
    resolve_last_birthday,
    resolve_local_birthday_anniversary,
    sign_label,
)
from fatebridge.core.predictive.native_chart import NativeSubject
from fatebridge.utils.civil_time import ZonedCalendar, utc_calendar
from fatebridge.utils.timezones import format_local_time_or_utc, parse_timezone_name


def monthly_profection_segment(
    year_start: datetime, year_end: datetime, month_offset: int
) -> tuple[datetime, datetime]:
    """Return the [start, end) of the ``month_offset``-th equal twelfth.

    Divide elapsed UTC time into twelfths, then display in the starting zone.
    Derive each boundary from the full interval so microsecond rounding never
    accumulates and the last boundary remains exactly ``year_end``.
    """
    year = ZonedCalendar.from_datetime(year_start)
    span = utc_calendar(year_end).elapsed_since(year.utc)
    start = year.utc.shifted(span * month_offset / 12)
    end = year.utc.shifted(span * (month_offset + 1) / 12)
    return (
        ZonedCalendar(start, year.zone).require_datetime(),
        ZonedCalendar(end, year.zone).require_datetime(),
    )


def monthly_profection_index(
    year_start: datetime, year_end: datetime, moment: datetime
) -> int:
    """Index (0–11) of the equal-twelfth segment that contains ``moment``."""
    instant = utc_calendar(moment)
    for index in range(11, 0, -1):
        start, _ = monthly_profection_segment(year_start, year_end, index)
        if instant >= utc_calendar(start):
            return index
        else:
            pass
    return 0


def build_annual_profection_payload(
    birth_info: AstroBirthInfo,
    natal_subject: NativeSubject,
    *,
    analysis_datetime: datetime,
) -> dict[str, Any]:
    anniversary = resolve_last_birthday(birth_info, analysis_datetime=analysis_datetime)
    analysis_datetime = anniversary.analysis_datetime
    last_birthday = anniversary.start
    age_years_int = anniversary.nominal_year - birth_info.local_datetime.year
    activated_house = (age_years_int % 12) + 1

    next_birthday = resolve_local_birthday_anniversary(
        birth_info.local_datetime,
        anniversary.nominal_year + 1,
        tzinfo=last_birthday.tzinfo,
        clock_policy="compatible",
    )
    months_since_birthday = monthly_profection_index(
        last_birthday, next_birthday, analysis_datetime
    )
    monthly_house = ((activated_house - 1 + months_since_birthday) % 12) + 1

    payload: dict[str, Any] = {
        "age_years": age_years_int,
        "year_start": last_birthday.isoformat(),
        "year_end": next_birthday.isoformat(),
        "calculation_options": {
            "annual_basis": "civil_birth_anniversary",
            "monthly_basis": "equal_UTC_twelfths",
            "anniversary_clock_policy": "compatible",
            "timezone": birth_info.timezone,
        },
        "activated_house": activated_house,
        "activated_sign": None,
        "activated_sign_label": None,
        "lord": None,
        "lord_label": None,
        "monthly_house": monthly_house,
        "monthly_sign": None,
        "monthly_sign_label": None,
    }
    if not is_ascendant_resolved(natal_subject):
        payload.update(
            status="underdetermined_ascendant",
            ascendant_resolved=False,
            unavailable_reason="ascendant_required_for_profection_sign_and_lord",
        )
        return payload
    else:
        pass

    asc_sign = normalize_sign_name(natal_subject.ascendant.sign)
    asc_index = SIGNS.index(asc_sign)
    activated_sign = SIGNS[(asc_index + activated_house - 1) % 12]
    lord = RULER_BY_SIGN[activated_sign]
    monthly_sign = SIGNS[(asc_index + monthly_house - 1) % 12]
    payload.update(
        activated_sign=activated_sign,
        activated_sign_label=sign_label(activated_sign),
        lord=lord,
        lord_label=planet_label(lord),
        monthly_sign=monthly_sign,
        monthly_sign_label=sign_label(monthly_sign),
    )
    return payload


def build_monthly_profections_payload(
    *,
    annual_house: int,
    asc_sign: str | None,
    year_start: datetime,
    year_end: datetime,
    analysis_datetime: datetime,
) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    asc_index = SIGNS.index(asc_sign) if asc_sign is not None else None
    instant = utc_calendar(analysis_datetime)
    for month_offset in range(12):
        start, end = monthly_profection_segment(year_start, year_end, month_offset)
        house = ((annual_house - 1 + month_offset) % 12) + 1
        entry: dict[str, Any] = {
            "month_index": month_offset + 1,
            "house": house,
            "house_label": f"第{house}宫",
            "sign": None,
            "sign_label": None,
            "lord": None,
            "lord_label": None,
            "start": format_local_time_or_utc(start),
            "end": format_local_time_or_utc(end),
            "active": utc_calendar(start) <= instant < utc_calendar(end),
        }
        if asc_index is not None:
            sign_name = SIGNS[(asc_index + house - 1) % 12]
            ruler = RULER_BY_SIGN[sign_name]
            entry.update(
                sign=sign_name,
                sign_label=sign_label(sign_name),
                lord=ruler,
                lord_label=planet_label(ruler),
            )
        else:
            entry["status"] = "underdetermined_ascendant"
        timeline.append(entry)
    return timeline


def build_given_year_payload(
    birth_info: AstroBirthInfo,
    natal_subject: NativeSubject,
    *,
    analysis_datetime: datetime,
    annual_profection: dict[str, Any],
    return_longitude: float,
    return_latitude: float,
    return_timezone: str,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
) -> dict[str, Any]:
    anniversary = resolve_last_birthday(
        birth_info,
        analysis_datetime=analysis_datetime,
    )
    analysis_local = anniversary.analysis_datetime
    last_birthday = anniversary.start
    year_end = resolve_local_birthday_anniversary(
        birth_info.local_datetime,
        anniversary.nominal_year + 1,
        tzinfo=last_birthday.tzinfo,
        clock_policy="compatible",
    )
    zone = parse_timezone_name(return_timezone)
    analysis_local = ZonedCalendar(
        utc_calendar(analysis_local), zone
    ).require_datetime()
    last_birthday = ZonedCalendar(utc_calendar(last_birthday), zone).require_datetime()
    year_end = ZonedCalendar(utc_calendar(year_end), zone).require_datetime()
    given_year_subject = build_subject(
        name=f"{birth_info.name}-given-year",
        local_datetime=analysis_local,
        longitude=return_longitude,
        latitude=return_latitude,
        timezone_name=return_timezone,
        house_system=house_system,
        zodiac_type=zodiac_type,
    )
    natal_asc_resolved = is_ascendant_resolved(natal_subject)
    given_year_asc_resolved = is_ascendant_resolved(given_year_subject)
    monthly_profections = build_monthly_profections_payload(
        annual_house=annual_profection["activated_house"],
        asc_sign=(
            normalize_sign_name(natal_subject.ascendant.sign)
            if natal_asc_resolved
            else None
        ),
        year_start=last_birthday,
        year_end=year_end,
        analysis_datetime=analysis_local,
    )
    source_longitudes = extract_reference_longitudes(given_year_subject)
    target_longitudes = extract_reference_longitudes(natal_subject)
    hits = collect_aspect_hits(
        source_longitudes=source_longitudes,
        target_longitudes=target_longitudes,
        orb_limit=1.5,
    )
    reference = extract_reference_points(given_year_subject)
    payload: dict[str, Any] = {
        "analysis_datetime": format_local_time_or_utc(analysis_local),
        "year_start": format_local_time_or_utc(last_birthday),
        "year_end": format_local_time_or_utc(year_end),
        "sun": reference["sun"],
        "moon": reference["moon"],
        "ascendant": reference["ascendant"],
        "medium_coeli": reference["medium_coeli"],
        "annual_profection": annual_profection,
        "monthly_profections": monthly_profections,
        "hits": hits[:8],
        "location": {
            "longitude": return_longitude,
            "latitude": return_latitude,
            "timezone": return_timezone,
        },
    }
    if not natal_asc_resolved or not given_year_asc_resolved:
        payload.update(
            status="underdetermined_ascendant",
            natal_ascendant_resolved=natal_asc_resolved,
            ascendant_resolved=given_year_asc_resolved,
            unavailable_reason="ascendant_required_for_profection_signs_and_ascendant_hits",
        )
    else:
        pass
    return payload
