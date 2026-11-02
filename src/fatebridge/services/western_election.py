"""
Service surface for 择日 (electional astrology).

Casts a chart for the candidate moment being evaluated and runs the electional
scorer in :mod:`fatebridge.core.astrology_election`.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fatebridge.core.astro.iers_ut1 import use_ut1_source
from fatebridge.core.astrology_election import TOPIC_MASTER, build_election_payload
from fatebridge.core.western_clock_origin import event_wall_datetime
from fatebridge.core.western_event_clock import build_event_subject
from fatebridge.services.snapshot_builders import (
    render_snapshot_text as _render_snapshot_text,
)
from fatebridge.utils.errors import handle_calculation_error
from fatebridge.utils.house_systems import house_system_fields, normalize_house_system


def _json_block(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def calculate_election(
    *,
    candidate_year: int,
    candidate_month: int,
    candidate_day: int,
    candidate_hour: int,
    candidate_minute: int = 0,
    timezone_name: Optional[str] = None,
    longitude: float,
    latitude: float,
    topic_id: str = "marriage",
    name: Optional[str] = None,
    house_system: str = "R",
    zodiac_type: str = "Tropic",
    candidate_calendar: str = "proleptic_gregorian",
    candidate_clock_basis: str = "civil",
    candidate_hour_origin: str = "midnight",
    ut1_source: str = "swiss_delta_t",
) -> Dict[str, Any]:
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
            score_text = (
                f"{payload['score']}/100"
                if payload["score"] is not None
                else f"未完成（已声明条件的范围{payload['score_bounds'][0]}–{payload['score_bounds'][1]}，非概率区间）"
            )
            summary = (
                f"择日（{payload['topic_label']}）：{payload['verdict']}，评分 "
                f"{score_text} — {payload['recommendation']}"
            )
            sections = [
                ("起盘信息", _json_block(context)),
                ("历法日期换算", _json_block(calendar_conversion)),
                ("钟时与物理时刻", _json_block(clock_conversion)),
                (
                    "评分与裁断",
                    _json_block(
                        {
                            "score": payload["score"],
                            "score_bounds": payload["score_bounds"],
                            "score_evidence": payload["score_evidence"],
                            "scoring_policy": payload["scoring_policy"],
                            "verdict": payload["verdict"],
                            "has_hard_block": payload["has_hard_block"],
                            "recommendation": payload["recommendation"],
                            "moon": payload["moon"],
                            "ascendant": payload["ascendant"],
                            "significator": payload["significator"],
                            "dignity_scope": payload["dignity_scope"],
                            "axes": payload["axes"],
                            "calculation_basis": payload["calculation_basis"],
                            "solar_condition_policy": payload["solar_condition_policy"],
                        }
                    ),
                ),
                ("吉凶因子", _json_block(payload["factors"])),
                ("未核算因子", _json_block(payload["unresolved_factors"])),
            ]
            return {
                "analysis_type": "西占择日",
                "engine": "fatebridge-offline",
                "analysis_context": context,
                "calendar_conversion": calendar_conversion,
                "clock_conversion": clock_conversion,
                "election": payload,
                "summary": summary,
                "snapshot_text": _render_snapshot_text(sections),
            }
    except Exception as exc:
        return handle_calculation_error(exc, label)
