"""
Service surface for 择日 (electional astrology).

Casts a chart for the candidate moment being evaluated and runs the electional
scorer in :mod:`fatebridge.core.astrology_election`.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from fatebridge.core.astrology_election import TOPIC_MASTER, build_election_payload
from fatebridge.core.predictive._common import build_subject
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
    timezone_name: str = "+08:00",
    longitude: float,
    latitude: float,
    topic_id: str = "marriage",
    name: Optional[str] = None,
    house_system: str = "R",
    zodiac_type: str = "Tropic",
) -> Dict[str, Any]:
    """评估某候选时刻对某类用事（结婚/开业/签约等非医疗活动）是否吉利。"""
    label = "择日"
    try:
        if topic_id not in TOPIC_MASTER:
            raise ValueError("未知的择日主题；请使用公开 topic_id 枚举")
        house_system = normalize_house_system(house_system)
        candidate_local = datetime(
            candidate_year,
            candidate_month,
            candidate_day,
            candidate_hour,
            candidate_minute,
        )
        subject = build_subject(
            name=name or "择日盘",
            local_datetime=candidate_local,
            longitude=longitude,
            latitude=latitude,
            timezone_name=timezone_name,
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        payload = build_election_payload(subject, topic_id=topic_id)

        context = {
            "tool": label,
            "candidate_datetime": candidate_local.isoformat(),
            "timezone": timezone_name,
            "topic_id": topic_id,
            "topic_label": payload["topic_label"],
            "location": {"longitude": longitude, "latitude": latitude},
            **house_system_fields(house_system),
            "zodiac_type": zodiac_type,
            "engine": "fatebridge-offline",
        }
        summary = (
            f"择日（{payload['topic_label']}）：{payload['verdict']}，评分 "
            f"{payload['score']}/100 — {payload['recommendation']}"
        )
        sections = [
            ("起盘信息", _json_block(context)),
            (
                "评分与裁断",
                _json_block(
                    {
                        "score": payload["score"],
                        "verdict": payload["verdict"],
                        "has_hard_block": payload["has_hard_block"],
                        "recommendation": payload["recommendation"],
                        "moon": payload["moon"],
                        "ascendant": payload["ascendant"],
                        "significator": payload["significator"],
                    }
                ),
            ),
            ("吉凶因子", _json_block(payload["factors"])),
        ]
        return {
            "analysis_type": "西占择日",
            "engine": "fatebridge-offline",
            "analysis_context": context,
            "election": payload,
            "summary": summary,
            "snapshot_text": _render_snapshot_text(sections),
        }
    except Exception as exc:
        return handle_calculation_error(exc, label)
