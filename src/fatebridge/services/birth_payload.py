"""Shared public birth-analysis payload, separate from service entry points."""

from typing import Any, Dict

from fatebridge.core.bazi_branch_facts import (
    check_clash_patterns,
    check_harmony_patterns,
)
from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.bazi_pattern_facts import (
    analyze_special_patterns,
    check_hidden_patterns,
    check_pillar_pair_patterns,
    check_pillar_patterns,
)
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

    harmony_patterns = check_harmony_patterns(context.birth_pillars)
    clash_patterns = check_clash_patterns(context.birth_pillars)
    stem_patterns = BaZiRules.check_stem_patterns(context.birth_pillars)
    hidden_patterns = check_hidden_patterns(context.birth_pillars)
    pillar_patterns = check_pillar_patterns(context.birth_pillars)
    pillar_pair_patterns = check_pillar_pair_patterns(context.birth_pillars)
    special_pattern_metadata = analyze_special_patterns(
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
    structure_profile["evidence_chain"] = build_natal_evidence(
        context.birth_pillars, context.element_analysis["day_master"]
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
                include_seconds=person.birth_second is not None,
            ),
            "normalized_birth_datetime": format_birth_datetime_display(
                corrected_birth_datetime,
                include_minutes=True,
                include_seconds=person.birth_second is not None,
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
            "strength": context.element_analysis["day_master"]["engineering_index"][
                "strength_level"
            ],
            "engineering_index": context.element_analysis["day_master"][
                "engineering_index"
            ],
            "classical_adjudication": context.element_analysis["day_master"][
                "classical_adjudication"
            ],
            "assessment": context.element_analysis["day_master"]["assessment"],
        },
        "element_distribution": context.element_analysis["day_master"][
            "element_distribution"
        ],
        "element_distribution_basis": context.element_analysis["day_master"][
            "element_distribution_basis"
        ],
        "element_seasonal_phase": context.element_analysis["day_master"][
            "element_seasonal_phase"
        ],
        "favorable_elements": structure_profile["useful_elements"],
        "favorable_elements_status": structure_profile["assessment_status"],
        "engineering_favorable_elements": context.element_analysis[
            "engineering_favorable_elements"
        ],
        "ten_gods": context.element_analysis["ten_gods"],
        "structure_profile": structure_profile,
        "patterns": {
            "harmony": harmony_patterns,
            "clash": clash_patterns,
            "stems": stem_patterns,
            "hidden": hidden_patterns,
            "pillar_relationships": pillar_patterns,
            "pillar_pair_relationships": pillar_pair_patterns,
            "special": special_patterns,
        },
        "calendar_context": context.birth_calendar_context,
    }
