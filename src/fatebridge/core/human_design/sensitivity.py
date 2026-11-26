"""Birth-time uncertainty interval assessment for Human Design charts."""

from __future__ import annotations

from typing import Any, Callable

from fatebridge.core.human_design.time import chart_at_tt

LEVELS = ("gate", "line", "color", "tone", "base")
GRID_STEP_SECONDS = 30
SIDES = ("personality", "design")


def unassessed_interval() -> dict[str, Any]:
    return {"status": "not_assessed", "plus_minus_minutes": 0}


def assess_birth_interval(
    nominal: dict[str, Any],
    plus_minus_minutes: int,
    node_mode: str,
    *,
    require_swiss_files: bool = False,
    _chart_reader: Callable[[float], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if type(plus_minus_minutes) is not int or not 1 <= plus_minus_minutes <= 60:
        raise ValueError("人类图生时范围必须为1至60个整数分钟")
    center = nominal["time_scales"]["personality"]["jd_tt"]
    radius = plus_minus_minutes * 60
    grid = [
        center + offset / 86400
        for offset in range(-radius, radius + 1, GRID_STEP_SECONDS)
    ]
    samples = [
        (
            nominal
            if jd == center
            else (
                _chart_reader(jd)
                if _chart_reader is not None
                else chart_at_tt(jd, node_mode, require_swiss_files=require_swiss_files)
            )
        )
        for jd in grid
    ]
    changed_fields = sorted(
        {
            field
            for chart in samples
            for field in ("type", "subtype", "authority", "strategy", "definition")
            if chart["bodygraph"][field] != nominal["bodygraph"][field]
        }
        | (
            {"profile"}
            if any(c["profile"] != nominal["profile"] for c in samples)
            else set()
        )
        | (
            {"variables"}
            if any(
                c["variables"]["code"] != nominal["variables"]["code"] for c in samples
            )
            else set()
        )
    )
    activation_variants = []
    for side in SIDES:
        for idx, base_act in enumerate(nominal["activations"][side]):
            distinct = []
            seen = set()
            for chart in samples:
                act = chart["activations"][side][idx]
                sig = tuple(act[k] for k in LEVELS)
                if sig not in seen:
                    seen.add(sig)
                    distinct.append({k: act[k] for k in LEVELS})
            if len(distinct) > 1:
                activation_variants.append(
                    {"side": side, "body": base_act["body"], "variants": distinct}
                )
    return {
        "status": (
            "changes_detected"
            if (changed_fields or activation_variants)
            else "stable_on_grid"
        ),
        "plus_minus_minutes": plus_minus_minutes,
        "sample_count": len(samples),
        "step_seconds": GRID_STEP_SECONDS,
        "changed_structure_fields": changed_fields,
        "activation_variants": activation_variants,
    }
