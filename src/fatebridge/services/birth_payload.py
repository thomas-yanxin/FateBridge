"""Shared public birth-analysis payload, separate from service entry points."""

from __future__ import annotations

from typing import Any

from fatebridge.core.bazi.relations import (
    check_hidden_patterns,
    check_pillar_pair_patterns,
    check_pillar_patterns,
    check_stem_patterns,
)
from fatebridge.services.birth_context import BirthComputationContext
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

    return {
        "person_info": {
            "name": person.name or "未提供",
            "birth_datetime": format_birth_datetime_display(
                birth_datetime,
                include_minutes=include_minutes,
                include_seconds=person.birth_second is not None,
            ),
            "normalized_birth_datetime": format_birth_datetime_display(
                corrected,
                include_minutes=True,
                include_seconds=person.birth_second is not None,
            ),
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
