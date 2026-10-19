"""Shared public birth-analysis payload, separate from service entry points."""

from typing import Any, Dict

from fatebridge.core.rules import BaZiRules
from fatebridge.services.birth_context import BirthComputationContext
from fatebridge.utils.formatting import (
    create_pillar_dict,
    format_birth_datetime_display,
)


def build_destiny_payload(context: BirthComputationContext) -> Dict[str, Any]:
    """Render the public destiny-analysis payload from a shared birth context."""
    person = context.person
    normalized_birth_time = context.normalized_birth_time
    birth_datetime = normalized_birth_time.input_datetime
    corrected_birth_datetime = normalized_birth_time.corrected_datetime
    include_minutes = (
        person.birth_minute != 0
        or normalized_birth_time.applied
        or corrected_birth_datetime.minute != 0
    )

    harmony_patterns = BaZiRules.check_harmony_patterns(context.birth_pillars)
    clash_patterns = BaZiRules.check_clash_patterns(context.birth_pillars)
    stem_patterns = BaZiRules.check_stem_patterns(context.birth_pillars)
    hidden_patterns = BaZiRules.check_hidden_patterns(context.birth_pillars)
    pillar_patterns = BaZiRules.check_pillar_patterns(context.birth_pillars)
    fu_yin_fan_yin = BaZiRules.check_fu_yin_fan_yin(context.birth_pillars)
    special_pattern_metadata = BaZiRules.analyze_special_patterns(
        context.birth_pillars,
        corrected_birth_datetime.hour,
    )
    structure_profile = BaZiRules.build_structure_profile(
        pillars=context.birth_pillars,
        element_analysis=context.element_analysis,
        harmony_patterns=harmony_patterns,
        clash_patterns=clash_patterns,
        special_patterns=special_pattern_metadata,
    )
    special_patterns = {
        **special_pattern_metadata,
        "recognized_structures": structure_profile["recognized_structures"],
        "metadata": special_pattern_metadata,
    }

    return {
        "person_info": {
            "name": person.name or "未提供",
            "birth_datetime": format_birth_datetime_display(
                birth_datetime,
                include_minutes=include_minutes,
            ),
            "normalized_birth_datetime": format_birth_datetime_display(
                corrected_birth_datetime,
                include_minutes=True,
            ),
            "gender": person.gender or "未知",
            "birth_place": person.birth_place or "未提供",
            "birth_timezone": normalized_birth_time.timezone,
            "birth_longitude": normalized_birth_time.longitude,
            "time_adjustment": normalized_birth_time.as_dict(),
        },
        "four_pillars": create_pillar_dict(context.birth_pillars),
        "day_master": {
            "stem": context.birth_pillars["day"][0],
            "element": context.element_analysis["day_master"]["day_element"],
            "polarity": context.element_analysis["day_master"]["day_polarity"],
            "strength": context.element_analysis["day_master"]["strength_level"],
            "assessment": context.element_analysis["day_master"]["assessment"],
        },
        "element_distribution": context.element_analysis["day_master"][
            "element_distribution"
        ],
        "element_distribution_adjusted": context.element_analysis["day_master"].get(
            "element_distribution_adjusted"
        ),
        "element_relations": context.element_analysis["day_master"].get(
            "element_relations", []
        ),
        "element_distribution_basis": context.element_analysis["day_master"].get(
            "element_distribution_basis"
        ),
        "element_seasonal_phase": context.element_analysis["day_master"].get(
            "element_seasonal_phase"
        ),
        "favorable_elements": structure_profile.get("useful_elements", []),
        "ten_gods": context.element_analysis["ten_gods"],
        "structure_profile": structure_profile,
        "patterns": {
            "harmony": harmony_patterns,
            "clash": clash_patterns,
            "stems": stem_patterns,
            "hidden": hidden_patterns,
            "pillar_relationships": pillar_patterns,
            "fu_yin_fan_yin": fu_yin_fan_yin,
            "special": special_patterns,
        },
        "calendar_context": context.birth_calendar_context,
    }
