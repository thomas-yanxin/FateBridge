"""Separate branch-season membership from the supplied numeric phase gate."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Tuple

from fatebridge.core.element_presence import SOURCE as BOOK_SOURCE
from fatebridge.utils.data import (
    BRANCH_ELEMENTS,
    BRANCH_SEASONAL_COMBINATIONS,
    BUREAU_ELEMENT,
)

ORDER = ("year", "month", "day", "hour")
SOURCE = {
    **BOOK_SOURCE,
    "id": "dtcw1947_branch_bureau_season_scope_v1",
    "title": "任注滴天髓闡微·方局·八格（季支与本气、北方水势）",
    "pdf_pages": [138, 139, 147, 160],
}
SOURCE.pop("printed_pages")  # These references cross printed volumes.
KNOWN_PHASE_GATES = {
    "season_root_revelation_relations_v5",
    "season_root_revelation_relations_v6",
    "season_root_revelation_relations_v7",
    "season_root_revelation_relations_v8",
    "season_root_revelation_relations_v9",
    "season_root_revelation_relations_v10",
    "season_root_revelation_relations_v11",
    "season_root_revelation_relations_v12",
}


def build_bureau_season_reference(
    pillars: Mapping[str, Tuple[str, str]], assessment: Mapping[str, Any]
) -> dict[str, Any]:
    """Do not recompute a missing assessment or replace its relation decisions."""
    month = pillars["month"][1]
    group, bureau = next(
        (group, name)
        for group, name in BRANCH_SEASONAL_COMBINATIONS.items()
        if month in group
    )
    group_element = BUREAU_ELEMENT[bureau].value
    phases = assessment.get("seasonal_phases")
    method = assessment.get("method_id")
    events = assessment.get("relations")
    rows = None
    if isinstance(events, list):
        rows = []
        for event in events:
            if event.get("kind") != "三会":
                continue
            target, positions = event["target"], event["positions"]
            flag = event.get("season_supports")
            matches_group = target == group_element
            rows.append(
                {
                    "positions": list(positions),
                    "target_element": target,
                    "month_is_member": "month" in positions,
                    "month_in_target_branch_group": matches_group,
                    "calculated_target_phase": (
                        phases.get(target) if isinstance(phases, dict) else None
                    ),
                    "supplied_season_support_flag": flag,
                    "supplied_relation_status": event["status"],
                    "criteria_differ": (
                        flag != matches_group if isinstance(flag, bool) else None
                    ),
                    "classical_transformation": "not_adjudicated",
                }
            )
    return {
        "method_id": "month_branch_group_and_supplied_phase_gate_v1",
        "source": deepcopy(SOURCE),
        "month_branch": month,
        "principal_branch_element": BRANCH_ELEMENTS[month][0].value,
        "branch_seasonal_group": "".join(
            b for b in "寅卯辰巳午未申酉戌亥子丑" if b in group
        ),
        "branch_group_element": group_element,
        "strength_method_id": method,
        "calculated_phases": deepcopy(phases) if isinstance(phases, dict) else None,
        "combination_gate_basis": (
            "supplied_phase_equals_wang"
            if method in KNOWN_PHASE_GATES
            else "method_not_identified"
        ),
        "combination_observations": rows,
        "source_force_adjudication": "not_adjudicated",
        "calculation_effect": "none",
        "scope": "月支本气、寅卯辰等三会季支归组、同次工程季相及实际合化门槛分别保留；观察数组为同次三会事件。已识别v5/v6/v7/v8的season_supports只表示化神相位是否为旺，不等于季支归组；完整同类会局的结构判级不等于已经完全成化。门槛不同不证明已成化或应取哪种旺衰。缺少同次相位/事件保持未提供，不重算补齐；不据此改变司令、时柱、根预算或现行旺衰。",
    }
