"""Position-resolved generating intermediaries, not an effective-force verdict.

The 1947 任注滴天髓 通關 chapter distinguishes an observed intermediary
from a usable passage: separation, binding and damage still require judgment.
No root loss, numerical energy or strength label is modified here.
"""

from copy import deepcopy
from itertools import permutations
from typing import Any, Mapping, Tuple

from fatebridge.core.passage_relations import relation_plane
from fatebridge.utils.data import (
    BRANCH_HIDDEN_STEMS,
    DESTRUCTION_CYCLE,
    GENERATION_CYCLE,
    STEM_ELEMENTS,
)

ORDER = ("year", "month", "day", "hour")
SOURCE = {
    "id": "ditian_positioned_passage_v2",
    "title": "任注滴天髓闡微·通關、官殺诸例",
    "author": "任鐵樵增注，李雨田校訂",
    "edition": "李雨田校訂兼發行，上海大東書局經售，1947年4月初版",
    "url": "https://upload.wikimedia.org/wikipedia/commons/d/db/SSID-11335994_%E6%BB%B4%E5%A4%A9%E9%AB%93%E9%97%A1%E5%BE%AE.pdf",
    "source_sha256": "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803",
    "pdf_pages": [197, 198, 199, 200, 215, 216],
    "printed_pages": [55, 56, 57, 58, 73, 74],
}


def build_passage_evidence(
    pillars: Mapping[str, Tuple[str, str]], assessment: Mapping[str, Any]
) -> dict[str, Any]:
    """Read original nodes and supplied remaining roots; do not recalculate.

    Every hidden stem is retained, while the principal-only subset is explicit.
    Mixed-plane and same-column paths are observed separately: the 官殺
    examples explicitly use a day-branch seal to feed its own day stem.
    Geometry alone never makes an observed path an effective passage.
    """
    raw = assessment.get("hidden_stem_ledger")
    ledger = raw if isinstance(raw, list) else None
    relations = assessment.get("relations")
    events = relations if isinstance(relations, list) else None
    nodes: list[dict[str, Any]] = []
    for position in ORDER:
        branch = pillars[position][1]
        for plane, stems in (
            ("stem", (pillars[position][0],)),
            ("hidden", BRANCH_HIDDEN_STEMS[branch]),
        ):
            for rank, stem in enumerate(stems):
                element = STEM_ELEMENTS[stem][0]
                roots = (
                    [
                        r
                        for r in ledger
                        if r["element"] == element.value
                        and (
                            plane == "stem"
                            or (r["pillar"] == position and r["stem"] == stem)
                        )
                    ]
                    if ledger is not None
                    else None
                )
                root_state = (
                    "not_supplied"
                    if roots is None
                    else (
                        "positive_remaining_budget"
                        if any(r["remaining_mass"] > 0 for r in roots)
                        else "no_positive_remaining_budget"
                    )
                )
                local = [e for e in events or [] if position in e.get("positions", [])]
                if events is None:
                    binding = "not_supplied"
                elif any(
                    e.get("status") == "binding"
                    and relation_plane(str(e.get("kind", "")))
                    == ("stem" if plane == "stem" else "branch")
                    for e in local
                ):
                    binding = "binding_recorded"
                elif any(
                    e.get("kind") == "天干合"
                    and plane == "stem"
                    and e.get("status") == "day_master_or_contested_review"
                    for e in local
                ):
                    binding = "pending_combination_review"
                else:
                    binding = "no_binding_recorded"
                nodes.append(
                    {
                        "id": f"{position}:{plane}:{stem}",
                        "pillar": position,
                        "plane": plane,
                        "stem": stem,
                        "branch": branch if plane == "hidden" else None,
                        "hidden_rank": rank if plane == "hidden" else None,
                        "element": element.value,
                        "remaining_root_state": root_state,
                        "binding_state": binding,
                    }
                )
    paths = []
    for a, middle, b in permutations(nodes, 3):
        same_plane = len({a["plane"], middle["plane"], b["plane"]}) == 1
        shared_pillar = len({a["pillar"], middle["pillar"], b["pillar"]}) < 3
        ea, em, eb = (STEM_ELEMENTS[n["stem"]][0] for n in (a, middle, b))
        if not (
            DESTRUCTION_CYCLE[ea] == eb
            and GENERATION_CYCLE[ea] == em
            and GENERATION_CYCLE[em] == eb
        ):
            continue
        i, j, k = (ORDER.index(n["pillar"]) for n in (a, middle, b))
        between = min(i, k) < j < max(i, k)
        adjacent = abs(i - j) == abs(j - k) == 1
        paths.append(
            {
                "from_node": a["id"],
                "via_node": middle["id"],
                "to_node": b["id"],
                "plane": a["plane"] if same_plane else "mixed",
                "elements": [ea.value, em.value, eb.value],
                "positions": [a["pillar"], middle["pillar"], b["pillar"]],
                "principal_hidden_only": same_plane
                and a["plane"] == "hidden"
                and all(n["hidden_rank"] == 0 for n in (a, middle, b)),
                "position_status": (
                    "shared_pillar_step"
                    if shared_pillar
                    else (
                        "adjacent_mediator_between"
                        if between and adjacent
                        else "between_with_gap" if between else "outside_interval"
                    )
                ),
                "all_nodes_have_remaining_roots": (
                    None
                    if any(
                        n["remaining_root_state"] == "not_supplied"
                        for n in (a, middle, b)
                    )
                    else all(
                        n["remaining_root_state"] == "positive_remaining_budget"
                        for n in (a, middle, b)
                    )
                ),
                "binding_states": [n["binding_state"] for n in (a, middle, b)],
                "effective_passage": "not_adjudicated",
            }
        )
    visible_paths = [p for p in paths if p["plane"] == "stem"]
    principal_paths = [p for p in paths if p["principal_hidden_only"]]
    return {
        "method_id": "positioned_generating_intermediaries_v2",
        "source": deepcopy(SOURCE),
        "nodes": nodes,
        "visible_paths": visible_paths,
        "principal_hidden_paths": deepcopy(principal_paths),
        "all_hidden_paths": [p for p in paths if p["plane"] == "hidden"],
        "mixed_paths": [p for p in paths if p["plane"] == "mixed"],
        "summary": {
            "visible_path_count": len(visible_paths),
            "principal_hidden_path_count": len(principal_paths),
            "all_hidden_path_count": sum(p["plane"] == "hidden" for p in paths),
            "mixed_path_count": sum(p["plane"] == "mixed" for p in paths),
            "effective_passage": "not_adjudicated",
            "calculation_effect": "none",
        },
        "scope": "生克链列实际干、全部藏干及位置；本气子集不代替全部藏干。相邻、隔位、越位及同柱步骤分列，跨干支层另列mixed_paths；根预算和合绊沿用同次结果。同柱印生身是可见路径，几何位置仍不自动证明通关、免冲、全局旺衰或成格。",
    }
