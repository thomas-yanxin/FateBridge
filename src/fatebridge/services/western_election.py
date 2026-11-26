"""Cast and render a Western electional chart."""

from __future__ import annotations

from typing import Any

from fatebridge.core.astro.astrology_election import (
    TOPIC_MASTER,
    build_election_payload,
)
from fatebridge.core.astro.iers_ut1 import use_ut1_source
from fatebridge.core.western_clock_origin import event_wall_datetime
from fatebridge.core.western_event_clock import build_event_subject
from fatebridge.utils.errors import handle_calculation_error
from fatebridge.utils.house_systems import house_system_fields, normalize_house_system


def calculate_election(
    *,
    candidate_year: int,
    candidate_month: int,
    candidate_day: int,
    candidate_hour: int,
    candidate_minute: int = 0,
    candidate_second: int = 0,
    timezone_name: str | None = None,
    longitude: float,
    latitude: float,
    topic_id: str = "marriage",
    name: str | None = None,
    house_system: str = "R",
    zodiac_type: str = "Tropic",
    candidate_calendar: str = "proleptic_gregorian",
    candidate_clock_basis: str = "civil",
    candidate_hour_origin: str = "midnight",
    ut1_source: str = "swiss_delta_t",
) -> dict[str, Any]:
    """评估某候选时刻对某类用事（结婚/开业/签约等非医疗活动）是否吉利。"""
    label = "择日"
    try:
        with use_ut1_source(ut1_source):
            if topic_id not in TOPIC_MASTER:
                raise ValueError("未知的择日主题；请使用公开 topic_id 枚举")
            house_system = normalize_house_system(house_system)
            candidate_local, calendar_conversion, hour_origin_conversion = (
                event_wall_datetime(
                    candidate_year,
                    candidate_month,
                    candidate_day,
                    candidate_hour,
                    candidate_minute,
                    candidate_calendar,
                    candidate_hour_origin,
                    second=candidate_second,
                )
            )
            subject, clock_conversion = build_event_subject(
                name=name or "择日盘",
                local_datetime=candidate_local,
                longitude=longitude,
                latitude=latitude,
                timezone_name=timezone_name,
                clock_basis=candidate_clock_basis,
                house_system=house_system,
                zodiac_type=zodiac_type,
            )
            clock_conversion.update(
                input_hour_origin=candidate_hour_origin,
                hour_origin_conversion=hour_origin_conversion,
            )
            payload = build_election_payload(subject, topic_id=topic_id)

            context = {
                "tool": label,
                "candidate_datetime": candidate_local.isoformat(),
                "input_calendar": calendar_conversion["input_calendar"],
                "input_date": calendar_conversion["input_date"],
                "timezone": clock_conversion["effective_civil_timezone"],
                "input_clock_basis": candidate_clock_basis,
                "ut1_source": ut1_source,
                "input_hour_origin": candidate_hour_origin,
                "chart_timezone": clock_conversion["chart_timezone"],
                "topic_id": topic_id,
                "topic_label": payload["topic_label"],
                "location": {"longitude": longitude, "latitude": latitude},
                **house_system_fields(house_system),
                "zodiac_type": zodiac_type,
                "engine": "fatebridge-offline",
            }
            summary = f"择日（{payload['topic_label']}）候选盘，已核对星体及所选条件。"
            return {
                "analysis_type": "西占择日",
                "engine": "fatebridge-offline",
                "analysis_context": context,
                "calendar_conversion": calendar_conversion,
                "clock_conversion": clock_conversion,
                "election": payload,
                "summary": summary,
            }
    except Exception as exc:
        return handle_calculation_error(exc, label)
