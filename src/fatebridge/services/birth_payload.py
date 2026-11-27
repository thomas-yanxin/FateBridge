"""Shared public birth-analysis payload, separate from service entry points."""

from __future__ import annotations

from typing import Any

from fatebridge.core.bazi.relations import (
    check_hidden_patterns,
    check_pillar_pair_patterns,
    check_pillar_patterns,
    check_stem_patterns,
)
from fatebridge.services.birth_context import (
    BirthComputationContext,
    build_unknown_hour_coverage,
)
from fatebridge.utils.formatting import (
    create_pillar_dict,
    format_birth_datetime_display,
)


def build_destiny_payload(context: BirthComputationContext) -> dict[str, Any]:
    """Render the clean, structured destiny-analysis payload from a shared birth context."""
    person = context.person
    normalized = context.normalized_birth_time
    birth_datetime = normalized.input_datetime
    corrected = normalized.corrected_datetime
    include_minutes = (
        person.birth_minute != 0 or normalized.applied or corrected.minute != 0
    )

    ea = context.element_analysis
    structure_profile = ea["structure_profile"]
    unknown_hour = bool(getattr(person, "birth_time_unknown", False))
    birth_display = (
        f"{birth_datetime.year:04d}年{birth_datetime.month:02d}月{birth_datetime.day:02d}日 (时辰未知)"
        if unknown_hour
        else format_birth_datetime_display(
            birth_datetime,
            include_minutes=include_minutes,
            include_seconds=person.birth_second is not None,
        )
    )
    normalized_display = (
        None
        if unknown_hour
        else format_birth_datetime_display(
            corrected,
            include_minutes=True,
            include_seconds=person.birth_second is not None,
        )
    )

    payload: dict[str, Any] = {
        "person_info": {
            "name": person.name or "未提供",
            "birth_datetime": birth_display,
            "normalized_birth_datetime": normalized_display,
            "gender": person.gender or "未知",
            "birth_place": person.birth_place or "未提供",
            "birth_timezone": normalized.timezone,
            "birth_longitude": normalized.longitude,
            "zi_hour_policy": context.zi_hour_policy,
            "time_adjustment": normalized.as_dict(),
        },
        "four_pillars": create_pillar_dict(context.birth_pillars),
        "day_master": ea["day_master"],
        "element_distribution": ea["element_distribution"],
        "element_seasonal_phase": ea["element_seasonal_phase"],
        "favorable_elements": ea["favorable_elements"],
        "favorable_elements_status": ea["favorable_elements_status"],
        "avoid_elements": ea["avoid_elements"],
        "ten_gods": ea["ten_gods"],
        "structure_profile": structure_profile,
        "intra_month_duty": context.intra_month_duty,
        "patterns": {
            "harmony": ea["harmony_patterns"],
            "clash": ea["clash_patterns"],
            "stems": check_stem_patterns(context.birth_pillars),
            "hidden": check_hidden_patterns(context.birth_pillars),
            "pillar_relationships": check_pillar_patterns(context.birth_pillars),
            "pillar_pair_relationships": check_pillar_pair_patterns(
                context.birth_pillars
            ),
        },
        "calendar_context": context.birth_calendar_context,
    }
    if unknown_hour:
        payload["coverage"] = build_unknown_hour_coverage(
            birth_datetime.date(),
            normalized.timezone,
            mode="three_pillars_hour_unknown",
            omitted_components=[
                "hour_pillar",
                "hour_ten_gods",
                "hour_shensha",
                "minggong",
                "shengong",
                "dayun_exact_onset_hour",
            ],
        )
    return payload
