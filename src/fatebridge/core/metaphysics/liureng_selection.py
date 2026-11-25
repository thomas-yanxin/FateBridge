"""Derive the four lessons, selected transmissions and their classifications."""

from typing import Any

from fatebridge.core.metaphysics.common import (
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    SIX_CLASH_BRANCHES,
    SIX_HARM_BRANCHES,
    SIX_HARMONY_BRANCHES,
    branch_element_text,
    liuqin_against_day,
    stem_element_text,
)
from fatebridge.core.metaphysics.liureng_life_stages import build_life_stages
from fatebridge.core.metaphysics.liureng_patterns import classify_transmission_pattern
from fatebridge.core.metaphysics.liureng_transmissions import (
    STEM_HOUSES,
    select_transmissions,
)
from fatebridge.utils.data import HEAVENLY_STEMS


def _branch_relation(
    left_branch: str,
    right_branch: str,
    *,
    same_label: str = "同支",
) -> str:
    if left_branch == right_branch:
        return same_label
    else:
        pass
    if SIX_HARMONY_BRANCHES.get(left_branch) == right_branch:
        return "六合"
    else:
        pass
    if SIX_CLASH_BRANCHES.get(left_branch) == right_branch:
        return "六冲"
    else:
        pass
    if SIX_HARM_BRANCHES.get(left_branch) == right_branch:
        return "六害"
    else:
        pass
    return "平"


def _liureng_judge_lesson(
    *,
    upper_branch: str,
    lower_branch: str,
    day_branch: str,
    relation: str,
) -> tuple[str, str, str, str]:
    with_day = _branch_relation(upper_branch, day_branch, same_label="比和")
    with_lower = _branch_relation(upper_branch, lower_branch, same_label="伏吟")

    # 大六壬课体判断以"上下"关系为主：伏吟=上下同位，返吟=上下相冲，六合=上下合。
    # 上神与日支的关系只作辅参，不应单独触发 返吟/六合 类型，否则会把
    # "上下六合、上神冲日" 这种组合误判为返吟。
    if with_lower == "伏吟":
        return "伏吟", "上神与下神同位，伏吟取象。", with_day, with_lower
    else:
        pass
    if with_lower == "六冲":
        return "返吟", "上神与下神相冲，取返吟往复之象。", with_day, with_lower
    else:
        pass
    if with_lower == "六害":
        return "六害", "上下见六害关系；这不是九宗门涉害取传。", with_day, with_lower
    else:
        pass
    if relation == "官鬼":
        return "官鬼", "上神与日干为官鬼关系，不代替九宗门取传。", with_day, with_lower
    else:
        pass
    if with_lower == "六合":
        return (
            "六合",
            "上下六合；刑、破等关系另列，不据合独断成局。",
            with_day,
            with_lower,
        )
    else:
        pass
    return (
        "课内关系",
        "本课关系供取传参照，不单独决定课体或发用。",
        with_day,
        with_lower,
    )


def _liureng_upper_lower_relation(upper_branch: str, lower_branch: str) -> str:
    upper_element = branch_element_text(upper_branch)
    lower_element = (
        stem_element_text(lower_branch)
        if lower_branch in HEAVENLY_STEMS
        else branch_element_text(lower_branch)
    )
    if upper_element == lower_element:
        return "比和"
    else:
        pass
    if ELEMENT_CONTROLS[upper_element] == lower_element:
        return "上克下"
    else:
        pass
    if ELEMENT_CONTROLS[lower_element] == upper_element:
        return "下贼上"
    else:
        pass
    if ELEMENT_GENERATES[upper_element] == lower_element:
        return "上生下"
    else:
        pass
    # The five-element cycle leaves only lower-generates-upper at this point.
    return "下生上"


def derive_selection(day_ganzhi: str, sky_to_earth: dict[str, str]) -> dict[str, Any]:
    """One domain derivation for the producer and output consistency checks."""
    day_stem, day_branch = day_ganzhi[0], day_ganzhi[1]
    day_element = stem_element_text(day_stem)
    day_stages = build_life_stages(day_stem, sky_to_earth)["stage_by_branch"]
    day_stem_house = STEM_HOUSES[day_stem]
    lesson_1_lower = day_stem_house
    lesson_1_upper = sky_to_earth[lesson_1_lower]
    lesson_2_lower = lesson_1_upper
    lesson_2_upper = sky_to_earth[lesson_2_lower]
    lesson_3_lower = day_branch
    lesson_3_upper = sky_to_earth[lesson_3_lower]
    lesson_4_lower = lesson_3_upper
    lesson_4_upper = sky_to_earth[lesson_4_lower]
    lesson_specs = [
        # (lower, upper, anchor_branch)：一/二课 以日干寄宫为 anchor；三/四课 以日支为 anchor。
        (lesson_1_lower, lesson_1_upper, day_stem_house),
        (lesson_2_lower, lesson_2_upper, day_stem_house),
        (lesson_3_lower, lesson_3_upper, day_branch),
        (lesson_4_lower, lesson_4_upper, day_branch),
    ]
    four_lessons: list[dict[str, Any]] = []
    for lesson_index, (lower_branch, upper_branch, anchor_branch) in enumerate(
        lesson_specs, start=1
    ):
        relation = liuqin_against_day(day_element, branch_element_text(upper_branch))
        style_hint, style_basis, with_day, with_lower = _liureng_judge_lesson(
            upper_branch=upper_branch,
            lower_branch=lower_branch,
            day_branch=day_branch,
            relation=relation,
        )
        four_lessons.append(
            {
                "index": lesson_index,
                "upper_branch": upper_branch,
                "upper_day_stem_life_stage": day_stages[upper_branch],
                "lower_branch": lower_branch,
                "anchor_branch": anchor_branch,
                "text": f"{upper_branch}加{day_stem if lesson_index == 1 else lower_branch}",
                "relation": relation,
                "upper_lower_relation": _liureng_upper_lower_relation(
                    upper_branch,
                    day_stem if lesson_index == 1 else lower_branch,
                ),
                "relations": {
                    "with_day_branch": with_day,
                    "with_lower_branch": with_lower,
                },
                "style_hint": style_hint,
                "style_basis": style_basis,
                "use_candidate": False,
            }
        )

    rule_trace: list[dict[str, Any]] = []
    (
        style,
        style_detail,
        transmission_method,
        transmission_branches,
        selected_lesson_index,
    ) = select_transmissions(
        day_stem, day_branch, sky_to_earth, four_lessons, trace=rule_trace
    )
    classification = classify_transmission_pattern(
        day_ganzhi=day_ganzhi,
        style=style,
        detail=style_detail,
        method=transmission_method,
        lessons=four_lessons,
        transmissions=transmission_branches,
        selected_lesson=selected_lesson_index,
    )
    style_detail = classification["detail"]
    transmission_method = classification["transmission_method"]
    initial_lesson = next(
        (lesson for lesson in four_lessons if lesson["index"] == selected_lesson_index),
        None,
    )
    if initial_lesson is not None:
        initial_lesson["use_candidate"] = True
    else:
        pass
    return {
        "four_lessons": four_lessons,
        "board_style": style,
        "board_style_detail": style_detail,
        "classification": classification,
        "transmission_method": transmission_method,
        "branches": transmission_branches,
        "selected_lesson_index": selected_lesson_index,
        "selected_lesson_relation": (
            initial_lesson.get("upper_lower_relation") if initial_lesson else None
        ),
        "rule_trace": rule_trace,
    }
