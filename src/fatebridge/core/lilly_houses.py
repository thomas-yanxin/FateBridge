"""Separate Lilly's house facts from roles and incomplete judgement claims."""

from __future__ import annotations

from typing import Any, Callable

from fatebridge.core.lilly_orbs import SOURCE_URL

_HOUSE_ORDER = (1, 10, 7, 4, 11, 5, 9, 3, 2, 8, 6, 12)
_HOUSE_POINTS = {
    1: 5,
    10: 5,
    7: 4,
    4: 4,
    11: 4,
    2: 3,
    5: 3,
    9: 2,
    3: 1,
    12: -5,
    8: -2,
    6: -2,
}


def house_condition(
    occupied_house: int | None, house_system: str | None, zodiac_type: str | None
) -> dict[str, Any]:
    if occupied_house is not None and occupied_house not in _HOUSE_ORDER:
        raise ValueError("Occupied house must be 1..12 or unknown")
    return {
        "occupied_house": occupied_house,
        "house_class": (
            None
            if occupied_house is None
            else (
                "angular"
                if occupied_house in {1, 10, 7, 4}
                else "succedent" if occupied_house in {11, 2, 8, 5} else "cadent"
            )
        ),
        "p48_strength_rank": (
            None if occupied_house is None else _HOUSE_ORDER.index(occupied_house) + 1
        ),
        "p48_rank_condition": "Ordinal comparison only when two planets are otherwise equally dignified; not sorted by p115 points or a probability",
        "p115_house_points": (
            None if occupied_house is None else _HOUSE_POINTS[occupied_house]
        ),
        "points_scope": "House row only; not the complete accidental dignity/debility table or a summed judgement",
        "assignment_policy": "Literal selected-chart occupied house only; the separate house_assignment receipt evaluates p33 cusp virtue. Geometric occupancy is not overwritten by that policy; full historical assignment variants remain unverified",
        "house_system": house_system,
        "zodiac_type": zodiac_type,
        "source_method_scope": (
            "selected_regiomontanus_tropical_house_facts"
            if house_system == "R" and zodiac_type in {"Tropic", "Tropical"}
            else "other_or_unknown_chart_method_not_original_edition_acceptance"
        ),
        "source_url": SOURCE_URL,
        "source_pages": [48, 50, 115],
        "full_original_text_acceptance": False,
    }


def _all(values: list[bool | None]) -> bool | None:
    return False if False in values else None if None in values else True


def _nearest_lunar_contact(
    history: dict[str, Any], *, past: bool
) -> tuple[dict[str, Any] | None, bool | None]:
    """Order only nonoverlapping crossing brackets in the declared window."""
    side = "past" if past else "future"
    events = [
        e
        for e in history.get("events", [])
        if e["kind"] == "contact" and "Moon" in e["bodies"]
    ]
    rows = [
        e
        for e in events
        if e.get("topology") == "crossing" and e["epoch_relation"] == side
    ]
    if not rows:
        return None, None
    row = (max if past else min)(rows, key=lambda e: e["root_bracket_tt"][0])
    lo, hi = row["root_bracket_tt"]
    if (
        any(e["epoch_relation"] == "question_boundary" for e in events)
        or any(
            e is not row
            and e["root_bracket_tt"][0] <= hi
            and lo <= e["root_bracket_tt"][1]
            for e in events
        )
        or any(
            e.get("topology") != "crossing"
            and e["epoch_relation"] == side
            and (
                e["root_bracket_tt"][1] >= lo if past else e["root_bracket_tt"][0] <= hi
            )
            for e in events
        )
        or any("Moon" in u["bodies"] for u in history.get("unresolved_intervals", []))
    ):
        return row, None
    return row, True


def dwelling_clause(
    states: dict[str, dict[str, Any]],
    querent: str,
    quesited: str,
    history: dict[str, Any],
    event_paths: dict[str, Any],
    phase: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any] | None],
) -> dict[str, Any]:
    """P126-127 rejects dwelling alone; compute named necessary subconditions.

    The Moon's last/next physical contacts and current separating/applying rays
    are checked separately from the stricter p126 reception/path conditions.
    Passing this finite subset does not certify full historical translation.
    """
    occupied = states[quesited].get("occupied_house")
    in_first = None if occupied is None else occupied == 1
    distinct = len({querent, quesited, "Moon"}) == 3
    prior = following = None
    last_source = next_target = separates = applies = None
    available = (
        history.get("status") == "computed"
        and history.get("constant_velocity_projection") is False
    )
    if available and distinct:
        prior, prior_order = _nearest_lunar_contact(history, past=True)
        following, following_order = _nearest_lunar_contact(history, past=False)
        last_source = (
            None
            if prior_order is not True or prior is None
            else quesited in prior["bodies"]
        )
        next_target = (
            None
            if following_order is not True or following is None
            else querent in following["bodies"]
        )
        source_phase = phase(states["Moon"], states[quesited])
        target_phase = phase(states["Moon"], states[querent])
        separates = (
            None
            if source_phase is None
            or prior is None
            or source_phase["phase"] == "unavailable"
            else source_phase["phase"] == "separating"
            and source_phase["aspect"] == prior["aspect"]
        )
        applies = (
            None
            if target_phase is None
            or following is None
            or target_phase["phase"] == "unavailable"
            else target_phase["phase"] == "applying"
            and target_phase["aspect"] == following["aspect"]
        )
    lunar_sequence = (
        _all([last_source, next_target, separates, applies]) if distinct else None
    )
    premise = _all([in_first, lunar_sequence])
    indexes = [
        i
        for i, p in enumerate(event_paths.get("paths", []))
        if p["mode"] == "translation" and p["actors"] == [quesited, "Moon", querent]
    ]
    if in_first is False:
        reading = "所问主星实际不在第一宫，第126–127页这一居宫条款的前提未满足；其他路径须分别核对。"
    elif in_first is None:
        reading = (
            "所问主星实际落宫未知，不能用它主掌的宫位代替落宫，居宫条款尚不能核定。"
        )
    elif lunar_sequence is True:
        reading = "所问主星实际落第一宫；在声明的事件窗口内，月亮上一接触来自所问主星、下一接触指向问者主星，当前对应黄经一端出相、一端入相。这些必要子条件支持该条传统解读，完整传光、阻碍与成事判断仍待核验。"
    elif lunar_sequence is False:
        reading = "所问主星实际落第一宫，但声明窗口内的月亮传递子条件未满足；Lilly明确不接受仅凭居宫断成，其他路径须另查。"
    else:
        reading = "所问主星实际落第一宫，月亮传递子条件仍未知；不能把缺失历史、边界歧义或角色重合当作传光成立，也不能仅凭居宫断成。"
    return {
        "rule_id": "lilly_1647_p126_127_dwelling_necessary_conditions_v1",
        "source_url": SOURCE_URL,
        "source_pages": [126, 127],
        "quesited_occupied_house": occupied,
        "quesited_in_first_house": in_first,
        "dwelling_alone_sufficient": False,
        "distinct_lunar_transfer_actors": distinct,
        "moon_last_contact_is_quesited": last_source,
        "moon_next_contact_is_querent": next_target,
        "moon_separating_from_prior_source_ray_now": separates,
        "moon_applying_to_next_recipient_ray_now": applies,
        "lunar_sequence_subconditions_satisfied": lunar_sequence,
        "named_necessary_conditions_satisfied": premise,
        "prior_lunar_contact": prior,
        "next_lunar_contact": following,
        "matching_p126_event_path_indexes": indexes,
        "event_history_status": history.get("status", "unavailable"),
        "event_history_unavailable_reason": history.get("unavailable_reason"),
        "event_history_window_tt": history.get("window_tt"),
        "event_history_completeness_scope": history.get("completeness_scope"),
        "scope": "Question-epoch literal occupancy and last/next seven-planet longitude contacts in declared finite history; no missing contact inferred, no complete source translation, reception-epoch, obstruction or reality acceptance",
        "conditional_reading_zh": reading,
        "full_judgement_accepted": False,
        "full_original_text_acceptance": False,
    }
