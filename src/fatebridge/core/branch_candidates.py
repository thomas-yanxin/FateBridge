"""Observe existing v8 branch candidate geometry and supplied screening receipts.

This sidecar never applies a relation, transfers a budget or recalculates force.
"""

from itertools import combinations
from typing import Any, Mapping, Sequence

from fatebridge.utils.data import (
    BRANCH_COMBINATION_ELEMENT,
    BRANCH_SEASONAL_COMBINATIONS,
    BRANCH_TRIPLE_COMBINATIONS,
    BUREAU_ELEMENT,
    TRIPLE_COMBINATION_PEAK,
)

ORDER = ("year", "month", "day", "hour")
METHOD_ID = "branch_combination_candidate_inventory_v1"
CURRENT_METHOD = "season_root_revelation_relations_v8"
KNOWN_SCREEN_METHODS = frozenset(
    {
        CURRENT_METHOD,
        "season_root_revelation_relations_v9",
        "season_root_revelation_relations_v10",
        "season_root_revelation_relations_v11",
        "season_root_revelation_relations_v12",
    }
)
KINDS = {"三会", "三合", "六合", "半合"}
KNOWN_STATUSES = {
    "三会": {"binding", "conditioned_transformation", "contested_or_clashed"},
    "三合": {"binding", "conditioned_transformation", "contested_or_clashed"},
    "六合": {
        "binding",
        "conditioned_transformation",
        "contested_or_clashed",
        "same_target_affiliation_only",
    },
    "半合": {"contested", "partial_tendency"},
    "六冲": {
        "active",
        "resolved_by_combination",
        "resolved_by_ordered_generation_path",
    },
    "刑": {"active", "resolved_by_combination"},
    "自刑": {"active"},
    "天干合": {"binding", "day_master_or_contested_review"},
}


def candidate_id(kind: str, target: str, positions: Sequence[str]) -> str:
    return "bc1:" + kind + ":" + target + ":" + "-".join(positions)


def geometric_candidates(branches: Mapping[str, str]) -> list[dict[str, Any]]:
    """Current catalogue only: all full groups, literal pairs and peak half-pairs."""
    specs: list[dict[str, Any]] = []

    def add(kind: str, target: str, positions: Sequence[str]) -> None:
        specs.append(
            {
                "id": candidate_id(kind, target, positions),
                "kind": kind,
                "target": target,
                "positions": list(positions),
                "branches": [branches[p] for p in positions],
            }
        )

    for kind, groups in (
        ("三会", BRANCH_SEASONAL_COMBINATIONS),
        ("三合", BRANCH_TRIPLE_COMBINATIONS),
    ):
        for group, bureau in groups.items():
            seats = [p for p in ORDER if branches[p] in group]
            if {branches[p] for p in seats} == set(group):
                add(kind, BUREAU_ELEMENT[bureau].value, seats)
    for pair in combinations(ORDER, 2):
        target = BRANCH_COMBINATION_ELEMENT.get(frozenset(branches[p] for p in pair))
        if target is not None:
            add("六合", target.value, pair)
    for group, bureau in BRANCH_TRIPLE_COMBINATIONS.items():
        peak = TRIPLE_COMBINATION_PEAK[group]
        for pair in combinations(ORDER, 2):
            observed = {branches[p] for p in pair}
            if len(observed) == 2 and peak in observed and observed < set(group):
                add("半合", BUREAU_ELEMENT[bureau].value, pair)
    return specs


def build_branch_combination_candidates(
    pillars: Mapping[str, tuple[str, str]], assessment: Mapping[str, Any]
) -> dict[str, Any]:
    """Reconstruct screen facts from same-run receipts, without changing them.

    The v8 half screen runs after full-group/pair decisions, before half effects.
    Its clashed set is exactly active 六冲 seats; its claimed set is exactly
    successful full-group/pair seats. Unknown methods never inherit this rule.
    """
    branches = {p: pillars[p][1] for p in ORDER}
    raw = assessment.get("relations")
    events = raw if isinstance(raw, list) else None
    full_events = events is not None and all(
        isinstance(e, dict)
        and e.get("kind") in KNOWN_STATUSES
        and e.get("status") in KNOWN_STATUSES[e["kind"]]
        and isinstance(e.get("positions"), list)
        and all(p in ORDER for p in e["positions"])
        for e in events
    )
    identified = assessment.get("method_id") in KNOWN_SCREEN_METHODS and full_events
    claimed = (
        {
            p
            for e in events or []
            if isinstance(e, dict)
            and e.get("kind") in {"三会", "三合", "六合"}
            and e.get("status") in {"binding", "conditioned_transformation"}
            for p in e["positions"]
        }
        if identified
        else None
    )
    clashed = (
        {
            p
            for e in events or []
            if isinstance(e, dict)
            and e.get("kind") == "六冲"
            and e.get("status") == "active"
            for p in e["positions"]
        }
        if identified
        else None
    )
    specs = geometric_candidates(branches)
    full = [r for r in specs if r["kind"] in {"三会", "三合"}]
    rows = []
    for spec in specs:
        matching = [
            i
            for i, e in enumerate(events or [])
            if isinstance(e, dict)
            and e.get("kind") == spec["kind"]
            and e.get("positions") == spec["positions"]
            and e.get("target") == spec["target"]
        ]
        containers = [
            r["id"]
            for r in full
            if spec["kind"] in {"六合", "半合"}
            and set(spec["positions"]) <= set(r["positions"])
        ]
        claimed_blockers = (
            [p for p in spec["positions"] if p in claimed]
            if claimed is not None and spec["kind"] == "半合"
            else ([] if identified else None)
        )
        clashed_blockers = (
            [p for p in spec["positions"] if p in clashed]
            if clashed is not None and spec["kind"] == "半合"
            else ([] if identified else None)
        )
        decision = "not_assessed"
        if matching:
            decision = "recorded_event"
        elif identified:
            if (
                spec["kind"] == "六合"
                and abs(
                    ORDER.index(spec["positions"][0])
                    - ORDER.index(spec["positions"][1])
                )
                != 1
            ):
                decision = "outside_current_adjacency"
            elif spec["kind"] == "六合" and containers:
                decision = "contained_in_complete_bureau"
            elif spec["kind"] == "半合" and (claimed_blockers or clashed_blockers):
                decision = "suppressed_before_half_evaluation"
            else:
                decision = "unclassified_unrecorded"
        rows.append(
            {
                **spec,
                "screen_decision": decision,
                "actual_event_refs": (
                    [f"assessment.relations:{i}" for i in matching]
                    if events is not None
                    else None
                ),
                "current_statuses": (
                    [events[i]["status"] for i in matching]
                    if events is not None
                    else None
                ),
                "claimed_blockers": claimed_blockers,
                "clashed_blockers": clashed_blockers,
                "contained_in_complete_candidate_ids": containers,
            }
        )
    return {
        "method_id": METHOD_ID,
        "strength_method_id": assessment.get("method_id"),
        "effects_status": "supplied" if events is not None else "not_supplied",
        "source_relation_count": len(events) if events is not None else None,
        "screen_status": "reconstructed_v8" if identified else "not_identified",
        "pre_half_claimed_positions": (
            [p for p in ORDER if p in claimed] if claimed is not None else None
        ),
        "pre_half_clashed_positions": (
            [p for p in ORDER if p in clashed] if clashed is not None else None
        ),
        "branches_by_position": branches,
        "candidates": rows,
        "effective_combination": "not_adjudicated",
        "calculation_effect": "none",
        "scope": "仅列现有v8三会、三合、六合与含旺支半合的字面候选，不是所有流派关系。候选、当前筛选与实际事件分列；无事件不等于关系不存在。半合筛选前的已占用和活动六冲位置只从同次v8回执还原；未知方法或未给回执保持未知。元数据不增加预算、不改原事件、根量、旺衰或司令，也不裁定有效通关、成格或现实结果。",
    }
