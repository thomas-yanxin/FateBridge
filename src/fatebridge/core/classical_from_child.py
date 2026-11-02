"""任注順局: screen a distinct 從兒 route without equating it to weak body.

The screen is observable admissibility, not a sufficient formation rule. Actual
hidden stems stay present even where the source calls a hidden force ineffective.
"""

from copy import deepcopy
from typing import Any, Mapping, Tuple

from fatebridge.utils.data import (
    BRANCH_HIDDEN_STEMS,
    DESTRUCTION_CYCLE,
    GENERATION_CYCLE,
    STEM_ELEMENTS,
    get_ten_god,
)

SOURCE = {
    "id": "ditian_ren_shunju_from_child_v1",
    "title": "任注滴天髓闡微·六親論·順局",
    "author": "任鐵樵增注，李雨田校訂兼發行",
    "edition": "上海大東書局經售，1947年4月初版",
    "url": "https://upload.wikimedia.org/wikipedia/commons/d/db/SSID-11335994_%E6%BB%B4%E5%A4%A9%E9%AB%93%E9%97%A1%E5%BE%AE.pdf",
    "pdf_pages": [389, 390, 391, 392, 393, 394, 395],
    "source_sha256": "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803",
}
ORDER = ("year", "month", "day", "hour")


def build_from_child_reference(
    pillars: Mapping[str, Tuple[str, str]],
) -> dict[str, Any]:
    """Keep month carrier, distributed output, wealth and obstructions separate.

    Two distinct output-bearing columns only formalize a presence screen for
    食傷多. It is not a numeric force threshold supplied by the text. A branch's
    subsidiary output alone does not establish 月建食傷 in this version.
    """
    day_stem = pillars["day"][0]
    body = STEM_ELEMENTS[day_stem][0]
    output = GENERATION_CYCLE[body]
    wealth = DESTRUCTION_CYCLE[body]
    seal = next(e for e, generated in GENERATION_CYCLE.items() if generated == body)
    officer = next(
        e for e, controlled in DESTRUCTION_CYCLE.items() if controlled == body
    )
    role_by_element = {
        body: "peer",
        output: "output",
        wealth: "wealth",
        seal: "seal",
        officer: "officer",
    }
    occurrences: list[dict[str, Any]] = []
    for position in ORDER:
        stem, branch = pillars[position]
        if position != "day":
            occurrences.append(
                {
                    "id": position + ".stem",
                    "position": position,
                    "location": "visible",
                    "stem": stem,
                    "branch": branch,
                    "role": role_by_element[STEM_ELEMENTS[stem][0]],
                    "ten_god": get_ten_god(day_stem, stem).value,
                }
            )
        for rank, hidden in enumerate(BRANCH_HIDDEN_STEMS[branch]):
            occurrences.append(
                {
                    "id": f"{position}.hidden.{rank}",
                    "position": position,
                    "location": "hidden",
                    "stem": hidden,
                    "branch": branch,
                    "hidden_rank": rank,
                    "role": role_by_element[STEM_ELEMENTS[hidden][0]],
                    "ten_god": get_ten_god(day_stem, hidden).value,
                }
            )
    output_rows = [r for r in occurrences if r["role"] == "output"]
    wealth_rows = [r for r in occurrences if r["role"] == "wealth"]
    month_anchors = [
        r
        for r in output_rows
        if r["position"] == "month"
        and (r["location"] == "visible" or r.get("hidden_rank") == 0)
    ]
    output_positions = [
        p for p in ORDER if any(r["position"] == p for r in output_rows)
    ]
    visible_obstructions = [
        r
        for r in occurrences
        if r["location"] == "visible" and r["role"] in {"seal", "officer"}
    ]
    hidden_obstructions = [
        r
        for r in occurrences
        if r["location"] == "hidden" and r["role"] in {"seal", "officer"}
    ]
    observations = [
        {
            "id": "month_output_carrier",
            "matched": bool(month_anchors),
            "occurrence_ids": [r["id"] for r in month_anchors],
        },
        {
            "id": "output_in_multiple_columns",
            "matched": len(output_positions) >= 2,
            "occurrence_ids": [r["id"] for r in output_rows],
        },
        {
            "id": "output_generates_present_wealth",
            "matched": bool(wealth_rows),
            "occurrence_ids": [r["id"] for r in wealth_rows],
        },
    ]
    present = all(r["matched"] for r in observations)
    review = present and not visible_obstructions
    status = (
        "requires_force_adjudication"
        if review
        else (
            "observable_obstruction" if present else "observable_prerequisite_not_met"
        )
    )
    return {
        "method_id": "ditian_from_child_presence_screen_v1",
        "status": status,
        "formation_status": "not_adjudicated",
        "ordinary_fuyi_requires_review": review,
        "strength_requirement": "not_a_prerequisite",
        "day_stem": day_stem,
        "occurrences": occurrences,
        "observed_conditions": observations,
        "output_positions": output_positions,
        "visible_obstructions": [r["id"] for r in visible_obstructions],
        "hidden_obstructions": [r["id"] for r in hidden_obstructions],
        "conditional_direction": {
            "if_route_is_formed": {
                "useful_elements": [output.value, wealth.value],
                "avoid_elements": [seal.value, officer.value],
            },
            "peer_elements": [body.value],
            "peer_scope": "比劫不能单独否定从儿，也不一律为喜；须看生食、争财及制合。",
        },
        "pending_conditions": [
            "食伤是否真正成气、财能否承接，不能由出现次数或普通身弱标签代替。",
            "藏印官杀的季候、位置、显隐、冲合和救应；藏干存在不等于作用已成立或已经消失。",
            "月支其他藏干、会合变化及力量不足的情形，未由本筛选完整裁定。",
            "食伤生财实际流通及与其他取用路径的优先关系。",
        ],
        "source": deepcopy(SOURCE),
        "scope": "原注区分成象、从象、伤官；任注另说明从儿不同于从财官。此处只形式化可观察的进入条件及条件喜忌；两柱出现为工程筛选约定，不是古籍力量常数，不证明完整成格或现实预测。未因比劫透出或日主有根排除，也未将藏印官杀抹去。",
    }


def from_child_snapshot_lines(profile: Mapping[str, Any]) -> list[str]:
    """Explain the supplied receipt; do not recalculate or select a structure."""
    ref = profile.get("from_child_reference") or {}
    if not ref.get("ordinary_fuyi_requires_review"):
        return []
    directions = ref["conditional_direction"]["if_route_is_formed"]
    return [
        "任注顺局从儿路径：月柱食伤、食伤分布与财星的可观察条件已见，成气、承接与救应仍待裁定；从儿不以普通身强弱为必要条件。",
        "若从儿成立，条件方向为食伤、财（"
        + "、".join(directions["useful_elements"])
        + "）；印、官杀（"
        + "、".join(directions["avoid_elements"])
        + "）为条件忌。当前普通扶抑列条件参考，未授予全局喜忌。",
    ]
