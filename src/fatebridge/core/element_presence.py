"""Unweighted, position-aware occurrence facts for three distinct chart planes."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Tuple

from fatebridge.utils.data import BRANCH_HIDDEN_STEMS, STEM_ELEMENTS, Element

ORDER = ("year", "month", "day", "hour")
SOURCE = {
    "id": "dtcw1947_element_presence_scope_v1",
    "author": "任鐵樵增注；李雨田校訂",
    "title": "任注滴天髓闡微·形象",
    "edition": "上海大東書局1947年4月初版",
    "url": "https://upload.wikimedia.org/wikipedia/commons/d/db/SSID-11335994_%E6%BB%B4%E5%A4%A9%E9%AB%93%E9%97%A1%E5%BE%AE.pdf",
    "pdf_pages": [127, 128],
    "printed_pages": [77, 78],
    "source_sha256": "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803",
}


def build_element_presence(pillars: Mapping[str, Tuple[str, str]]) -> dict[str, Any]:
    """List actual stems, principal hidden qi and all hidden qi without force votes.

    Include the day stem in visible occurrences. Principal hidden occurrences
    are a subset of all hidden occurrences and must never be added a second time.
    A physical hidden occurrence remains listed after clash/combination analysis.
    """
    visible, hidden = [], []
    for position in ORDER:
        stem, branch = pillars[position]
        visible.append(
            {"pillar": position, "stem": stem, "element": STEM_ELEMENTS[stem][0].value}
        )
        for rank, concealed in enumerate(BRANCH_HIDDEN_STEMS[branch]):
            hidden.append(
                {
                    "pillar": position,
                    "stem": concealed,
                    "branch": branch,
                    "hidden_rank": rank,
                    "element": STEM_ELEMENTS[concealed][0].value,
                }
            )

    def plane(occurrences: list[dict[str, Any]]) -> dict[str, Any]:
        found = {o["element"] for o in occurrences}
        return {
            "occurrences": occurrences,
            "present_elements": [e.value for e in Element if e.value in found],
            "absent_elements": [e.value for e in Element if e.value not in found],
        }

    present = {o["element"] for o in visible + hidden}
    return {
        "method_id": "physical_element_presence_planes_v1",
        "source": deepcopy(SOURCE),
        "visible_stems": plane(visible),
        "principal_hidden_stems": plane(
            [o.copy() for o in hidden if o["hidden_rank"] == 0]
        ),
        "all_hidden_stems": plane(hidden),
        "all_listed_elements": [e.value for e in Element if e.value in present],
        "absent_from_all_listed": [e.value for e in Element if e.value not in present],
        "source_phrase_scope": "not_adjudicated",
        "calculation_effect": "none",
        "scope": "按同次原局列实物出现，含日干；本气是全部藏干的子集，三层不相加。出现不等于旺、有力、有效通关或成格；刑冲合不删除原录。原典无、不杂须按作者语境另审，不由某层缺项推出全局缺失。",
    }
