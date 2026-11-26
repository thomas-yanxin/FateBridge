"""Trace the adopted clash proxy without adjudicating classical root force."""

from copy import deepcopy
from typing import Any, Mapping, Sequence

ORDER = ("year", "month", "day", "hour")
SCOPE = "本表复用同次六冲决策。普通六冲仅比较两五行的初始藏干预算总量，包含月支预算倍数；未将季相、透干盖头、任意间接生扶、距离权重或寒暖纳入输赢。具名完整四支通关另列来源分支，不作预算输赢比较；不是见印即免冲。保留系数为工程政策，不等于原典完整有效根力、拔根、发福或吉凶。"


def build_clash_comparison(
    pillars: Mapping[str, tuple[str, str]],
    events: Sequence[Mapping[str, Any]],
    sources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Project decisions actually made; never rerun force on a later ledger."""
    rows = []
    source_ids = set()
    for event in events:
        if event.get("kind") != "六冲":
            continue
        positions = list(event["positions"])
        row: dict[str, Any] = {
            "positions": positions,
            "branches": [pillars[p][1] for p in positions],
            "distance": abs(ORDER.index(positions[0]) - ORDER.index(positions[1])),
            "event_status": event["status"],
            "source_ref": event["source_id"],
            "powers": None,
            "applied_root_retention": None,
        }
        if event["status"] == "resolved_by_combination":
            row["calculation_branch"] = "combination_resolution"
        elif event["status"] == "resolved_by_ordered_generation_path":
            row["calculation_branch"] = "ordered_generation_path_resolution"
            row["intermediary_positions"] = list(event["intermediary_positions"])
        elif "storage_effect" in event:
            row["calculation_branch"] = "storage_movement"
        else:
            row["calculation_branch"] = "initial_hidden_budget"
            row["powers"] = deepcopy(event["power_comparison"]["powers"])
            row["applied_root_retention"] = deepcopy(event["root_multipliers"])
        rows.append(row)
        source_ids.add(event["source_id"])
    return {
        "method_id": "initial_hidden_budget_clash_trace_v1",
        "resource_stage": "before_interactions",
        "included_factors": ["initial_hidden_budgets", "month_budget_multiplier"],
        "not_included_factors": [
            "seasonal_energy_factor",
            "visible_stem_activation",
            "stem_cover",
            "indirect_generation",
            "distance_weight",
            "thermal_receiving_capacity",
        ],
        "events": rows,
        "sources": [deepcopy(s) for s in sources if s["id"] in source_ids],
        "classical_effective_force": "not_adjudicated",
        "scope": SCOPE,
    }
