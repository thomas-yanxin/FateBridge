"""Wealth-root positions and source-scoped food/wealth prerequisites.

Root categories themselves live in classical_roots. This module records the
actual roots of revealed wealth and the unresolved force/formation conditions
of 《秘本子平真诠》PDF76–78, without fitting global strength to known cases.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

from fatebridge.core.classical import determine_monthly_structure, twelve_life_stage
from fatebridge.utils.data import (
    BRANCH_HIDDEN_STEMS,
    DESTRUCTION_CYCLE,
    STEM_ELEMENTS,
    Polarity,
    TenGod,
    get_ten_god,
    iter_pillar_gods,
)

Pillars = Mapping[str, Tuple[str, str]]
ORDER = ("year", "month", "day", "hour")


def hidden_roots(stem: str, pillars: Pillars) -> List[Dict[str, Any]]:
    """Actual matching hidden stems, keeping rank and physical position."""
    return [
        {
            "pillar": name,
            "branch": pillars[name][1],
            "stem": hidden,
            "hidden_rank": rank,
            "kind": "same_stem" if hidden == stem else "same_element",
        }
        for name in ORDER
        for rank, hidden in enumerate(BRANCH_HIDDEN_STEMS[pillars[name][1]])
        if STEM_ELEMENTS[hidden][0] == STEM_ELEMENTS[stem][0]
    ]


def wealth_rule_context(pillars: Pillars) -> Dict[str, Any]:
    """Month-command role, visible wealth roots and unresolved force conditions.

    食神生财 is considered only with the selected month-command 食神 anchor;
    visible co-occurrence alone is not promoted to a formed pattern.
    """
    day = pillars["day"][0]
    wealth_element = DESTRUCTION_CYCLE[STEM_ELEMENTS[day][0]]
    monthly = determine_monthly_structure(dict(pillars), day)
    selected = monthly["structure_god"]
    visible_wealth = []
    for name in ORDER:
        stem = pillars[name][0]
        if name == "day" or STEM_ELEMENTS[stem][0] != wealth_element:
            continue
        roots = hidden_roots(stem, pillars)
        phase_references = [
            {"pillar": n, "branch": pillars[n][1], "phase": "长生"}
            for n in ORDER
            if STEM_ELEMENTS[stem][1] == Polarity.YIN
            and twelve_life_stage(stem, pillars[n][1]) == "长生"
        ]
        visible_wealth.append(
            {
                "pillar": name,
                "stem": stem,
                "ten_god": get_ten_god(day, stem).value,
                "hidden_roots": roots,
                "phase_references": phase_references,
                "root_condition": (
                    "hidden_root_observed"
                    if roots
                    else (
                        "phase_root_requires_review"
                        if phase_references
                        else "no_root_observed"
                    )
                ),
            }
        )
    food_stars = [
        {
            "pillar": e.pillar,
            "stem": e.char,
            "location": e.location,
            "ten_god": e.ten_god.value,
        }
        for e in iter_pillar_gods(pillars, day)
        if e.ten_god in (TenGod.FOOD_GOD, TenGod.HURT_OFFICER)
    ]
    source_path = selected["ten_god"] == "食神"
    return {
        "method_id": "ziping_wealth_root_prerequisites_v1",
        "source_ref": "ziping_prerequisites_v1:food_wealth",
        "source_locator": "论食神 PDF76–78；论墓库刑冲之说 PDF43–45",
        "month_command_role": {
            "stem": selected["stem"],
            "ten_god": selected["ten_god"],
            "role": "月令格局用神候选，非扶抑有利五行",
        },
        "path": (
            "food_generates_wealth_prerequisites"
            if source_path
            else "wealth_root_review_only"
        ),
        "food_hurt_positions": food_stars,
        "visible_wealth": visible_wealth,
        "checks": {
            "food_month_anchor": "matched" if source_path else "not_applicable",
            "wealth_revealed": "matched" if visible_wealth else "not_observed",
            "revealed_wealth_hidden_root": (
                "matched"
                if any(w["hidden_roots"] for w in visible_wealth)
                else (
                    "requires_phase_root_review"
                    if any(w["phase_references"] for w in visible_wealth)
                    else "not_observed"
                )
            ),
            "body_food_wealth_relative_force": "unknown",
            "obstruction_rescue_and_formation": "unknown",
        },
        "formation_status": "not_adjudicated",
        "scope": "财根位置与原典路径的有限条件；不由财有根推出富贵，不把库支或六冲当进财事件。",
    }
