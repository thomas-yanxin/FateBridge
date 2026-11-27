"""Cast and render a Western horary chart."""

from __future__ import annotations

from typing import Any

from fatebridge.core.astro.astrology_horary import (
    CATEGORY_LABELS_ZH,
    HOUSE_BY_CATEGORY,
    build_horary_payload,
)
from fatebridge.core.astro.iers_ut1 import use_ut1_source
from fatebridge.core.astro.lilly_orbs import DEFAULT_ORB_PROFILE, full_orbs
from fatebridge.core.western_clock_origin import event_wall_datetime
from fatebridge.core.western_event_clock import build_event_subject
from fatebridge.utils.errors import handle_calculation_error
from fatebridge.utils.house_systems import house_system_fields, normalize_house_system


def calculate_horary(
    *,
    question_year: int,
    question_month: int,
    question_day: int,
    question_hour: int,
    question_minute: int = 0,
    question_second: int = 0,
    timezone_name: str | None = None,
    longitude: float,
    latitude: float,
    category: str = "general",
    name: str | None = None,
    house_system: str = "R",
    zodiac_type: str = "Tropic",
    orb_profile: str = DEFAULT_ORB_PROFILE,
    radicality_context: dict[str, Any] | None = None,
    question_calendar: str = "proleptic_gregorian",
    question_clock_basis: str = "civil",
    question_hour_origin: str = "midnight",
    ut1_source: str = "swiss_delta_t",
    turned_from_house: int | None = None,
    turned_house: int | None = None,
    include_inactive_fortitude_rows: bool = False,
) -> dict[str, Any]:
    """按提问时刻核算相位、月亮事件与原典条件的核验状态。"""
    label = "卜卦证据"
    try:
        with use_ut1_source(ut1_source):
            if category not in HOUSE_BY_CATEGORY:
                raise ValueError("未知的卜卦类别；请使用公开 category 枚举")
            full_orbs(orb_profile)
            house_system = normalize_house_system(house_system)
            question_local, calendar_conversion, hour_origin_conversion = (
                event_wall_datetime(
                    question_year,
                    question_month,
                    question_day,
                    question_hour,
                    question_minute,
                    question_calendar,
                    question_hour_origin,
                    second=question_second,
                )
            )
            subject, clock_conversion = build_event_subject(
                name=name or "卜卦盘",
                local_datetime=question_local,
                longitude=longitude,
                latitude=latitude,
                timezone_name=timezone_name,
                clock_basis=question_clock_basis,
                house_system=house_system,
                zodiac_type=zodiac_type,
            )
            clock_conversion.update(
                input_hour_origin=question_hour_origin,
                hour_origin_conversion=hour_origin_conversion,
            )
            payload = build_horary_payload(
                subject,
                category=category,
                orb_profile=orb_profile,
                radicality_context=radicality_context,
                clock_basis=question_clock_basis,
                turned_from_house=turned_from_house,
                turned_house=turned_house,
                include_inactive_fortitude_rows=include_inactive_fortitude_rows,
            )

            context = {
                "tool": label,
                "question_datetime": question_local.isoformat(),
                "input_calendar": calendar_conversion["input_calendar"],
                "input_date": calendar_conversion["input_date"],
                "timezone": clock_conversion["effective_civil_timezone"],
                "input_clock_basis": question_clock_basis,
                "ut1_source": ut1_source,
                "input_hour_origin": question_hour_origin,
                "chart_timezone": clock_conversion["chart_timezone"],
                "category": category,
                "category_label": CATEGORY_LABELS_ZH[category],
                "location": {"longitude": longitude, "latitude": latitude},
                **house_system_fields(house_system),
                "zodiac_type": zodiac_type,
                "orb_profile": orb_profile,
                "radicality_context": payload["radicality"]["reported_context"],
                "engine": "fatebridge-offline",
            }
            summary = f"卜卦（{payload['category_label']}），所问宫位为第{payload['quesited_house']}宫。"
            return {
                "analysis_type": "西占卜卦",
                "engine": "fatebridge-offline",
                "analysis_context": context,
                "calendar_conversion": calendar_conversion,
                "clock_conversion": clock_conversion,
                "horary_chart": payload,
                "summary": summary,
            }
    except Exception as exc:
        return handle_calculation_error(exc, label)
