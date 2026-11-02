"""Link supplied relation receipts to passage nodes without adjudicating force."""

from copy import deepcopy
from typing import Any, Mapping

from fatebridge.core.branch_candidates import build_branch_combination_candidates

ORDER = ("year", "month", "day", "hour")
BRANCH_KINDS = frozenset({"三会", "三合", "六冲", "六合", "刑", "半合", "自刑"})


def relation_plane(kind: str) -> str:
    if kind == "天干合":
        return "stem"
    return "branch" if kind in BRANCH_KINDS else "unclassified"


def build_passage_relation_context(
    passage: Mapping[str, Any],
    assessment: Mapping[str, Any],
    *,
    pillars: Mapping[str, tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Copy every event; root carriers come only from the supplied root ledger.

    A visible stem's roots can be in another pillar. A hidden node belongs to
    its own physical branch. Neither relation occurrence nor an engineering
    event status proves usable classical passage or a real-world consequence.
    """
    raw = assessment.get("relations")
    events = (
        [
            {
                "id": f"assessment.relations:{i}",
                "plane": relation_plane(event["kind"]),
                "receipt": deepcopy(event),
            }
            for i, event in enumerate(raw)
        ]
        if isinstance(raw, list)
        else None
    )
    ledger = assessment.get("hidden_stem_ledger")
    inventory = (
        build_branch_combination_candidates(pillars, assessment)
        if pillars is not None
        else None
    )
    nodes = []
    for node in passage["nodes"]:
        visible = node["plane"] == "stem"
        carriers = (
            [node["pillar"]]
            if not visible
            else (
                [
                    p
                    for p in ORDER
                    if any(
                        r["pillar"] == p and r["element"] == node["element"]
                        for r in ledger
                    )
                ]
                if isinstance(ledger, list)
                else None
            )
        )
        nodes.append(
            {
                "node_id": node["id"],
                **(
                    {
                        "potential_branch_candidate_refs": (
                            [
                                r["id"]
                                for r in inventory["candidates"]
                                if set(carriers) & set(r["positions"])
                            ]
                            if carriers is not None
                            else None
                        )
                    }
                    if inventory is not None
                    else {}
                ),
                "visible_relation_refs": (
                    []
                    if not visible
                    else (
                        [
                            e["id"]
                            for e in events
                            if e["plane"] == "stem"
                            and node["pillar"] in e["receipt"]["positions"]
                        ]
                        if events is not None
                        else None
                    )
                ),
                "root_carrier_scope": (
                    "physical_hidden_branch"
                    if not visible
                    else (
                        "supplied_element_root_ledger"
                        if carriers is not None
                        else "not_supplied"
                    )
                ),
                "root_carrier_positions": carriers,
                "root_relation_refs": (
                    [
                        e["id"]
                        for e in events
                        if e["plane"] == "branch"
                        and set(carriers) & set(e["receipt"]["positions"])
                    ]
                    if events is not None and carriers is not None
                    else None
                ),
            }
        )
    return {
        "method_id": "same_assessment_passage_relations_v1",
        **(
            {"branch_combination_candidates": inventory}
            if inventory is not None
            else {}
        ),
        "passage_source_id": passage["source"]["id"],
        "relations_status": "supplied" if events is not None else "not_supplied",
        "source_relation_count": len(events) if events is not None else None,
        "events": events,
        "unclassified_event_refs": (
            [e["id"] for e in events if e["plane"] == "unclassified"]
            if events is not None
            else None
        ),
        "nodes": nodes,
        "effective_passage": "not_adjudicated",
        "calculation_effect": "none",
        "scope": "逐项保留同次assessment.relations原回执，含争合、半合、条件转化和零效果；状态是工程模型记录，不是原典效力裁定。透干合与支中载体关系分列，透干的支关系沿用已给同五行根账本，保留零剩余根所在柱；藏干只连自身支。未供账本或关系为未知，空列表才表示已给范围无记录。no_binding_recorded不表示条件全清；未知关系种类另列，不猜层。旧路径及根预算不变，不据此认定通关、免冲、成格或现实结果。",
    }
