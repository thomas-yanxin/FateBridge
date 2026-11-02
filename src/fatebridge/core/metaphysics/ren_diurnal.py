"""Record a table-selection policy without fabricating stellar observations."""

from __future__ import annotations

from typing import Any

from ...utils.data import EARTHLY_BRANCHES

DAY_BRANCHES = "卯辰巳午未申"


def resolve_diurnal(hour_branch: str, explicit: bool | None = None) -> dict[str, Any]:
    if hour_branch not in EARTHLY_BRANCHES:
        raise ValueError("昼夜选择需要有效占时时支")
    if explicit is not None and type(explicit) is not bool:
        raise ValueError("is_diurnal 必须是布尔选择或省略")
    selected = explicit if explicit is not None else hour_branch in DAY_BRANCHES
    return {
        "method_id": "ren_diurnal_selection_provenance_v1",
        "hour_branch": hour_branch,
        "explicit_choice": explicit,
        "is_diurnal": selected,
        "selection_source": (
            "explicit_parameter" if explicit is not None else "hour_branch_convention"
        ),
        "fixed_day_branches": list(DAY_BRANCHES),
        "stellar_visibility_observed": None,
        "astronomical_boundary_computed": False,
        "solar_altitude_threshold_degrees": None,
        "basis": (
            f"显式选择{'昼贵' if selected else '夜贵'}（is_diurnal={'true' if selected else 'false'}），占时时支{hour_branch}。"
            if explicit is not None
            else f"按占时时支{hour_branch}及卯至申昼、酉至寅夜的约定选择{'昼贵' if selected else '夜贵'}。"
        ),
        "scope": "仅记录起贵人所用昼夜选择；未记录现场星象可见性，未计算星出星没，也未将日出日落或曙暮光高度当作原典判界。",
    }
