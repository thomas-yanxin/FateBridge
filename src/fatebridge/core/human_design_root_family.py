"""Actual complete design charts at additional observed numeric root candidates."""

from typing import Any

from fatebridge.core.human_design_joint import JointSnapshotCache, joint_changes
from fatebridge.core.human_design_mechanics import positions_at_tt
from fatebridge.core.human_design_native_positions import (
    decode_native_positions,
    pack_native_positions,
)
from fatebridge.core.human_design_root_interpretations import (
    candidate_chart,
    root_interpretations,
)

SCOPE = "仅对本次有限太阳邻点中实际观测的符号括区/零值候选逐TT计算完整设计激活和解释，保留名义人格盘与原选根。候选来自原数值函数，不是物理误差区间或多个真实出生/设计时刻；不认证连续根数量、唯一性或现实事件，不拼接候选。"
LEVELS = ("gate", "line", "color", "tone", "base")


def family_summary(value: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "status": value["status"] if value else "no_multiple_numeric_contact_observed",
        "actual_epoch_count": value["actual_epoch_count"] if value else 0,
        "candidate_tt": [row["jd_tt"] for row in value["candidates"]] if value else [],
        "any_activation_subdivision_change": (
            value["any_activation_subdivision_change"] if value else False
        ),
        "unique_physical_root_certified": False,
    }


def candidate_times(solver: dict[str, Any]) -> list[float]:
    lattice = solver["numerical_precision"]["local_solar_lattice"]
    return (
        [lattice["samples"][i]["jd_tt"] for i in lattice["candidate_epoch_indices"]]
        if lattice["multiple_numeric_contacts_observed"]
        else []
    )


def derive_family(
    solver: dict[str, Any],
    personality: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    node_mode: str,
    raw: list[dict[str, Any]],
    *,
    require_swiss_files: bool = False,
    physical_backend_policy: str = "auto",
) -> dict[str, Any] | None:
    times = candidate_times(solver)
    if not times:
        if raw:
            raise ValueError("Invented local root family")
        return None
    if len(raw) != len(times):
        raise ValueError("Missing actual numeric root candidate")
    cache = JointSnapshotCache()
    baseline = cache.snapshot(candidate_chart(personality, selected))
    solar = {
        r["jd_tt"]: r["sun_longitude"]
        for r in solver["numerical_precision"]["local_solar_lattice"]["samples"]
    }
    candidates = []
    for index, (tt, entry) in enumerate(zip(times, raw, strict=True)):
        if (
            set(entry) != {"jd_tt", "native_positions", "source_role"}
            or type(entry["jd_tt"]) is not float
            or entry["jd_tt"] != tt
            or entry["source_role"]
            != (
                "activation"
                if tt == solver["design_jd_tt"]
                else "root_bracket_activation"
            )
        ):
            raise ValueError("Detached root family epoch")
        rows = decode_native_positions(
            entry["native_positions"],
            node_mode,
            require_swiss_files=require_swiss_files,
            physical_backend_policy=physical_backend_policy,
        )
        if rows[0]["longitude"] != solar[tt]:
            raise ValueError("Root family Sun differs from observed function")
        if tt == solver["design_jd_tt"] and rows != selected:
            raise ValueError("Root family selected chart changed")
        snapshot = cache.snapshot(candidate_chart(personality, rows))
        changes = [
            {
                "body": a["body"],
                "levels": [k for k in LEVELS if a[k] != b[k]],
                "selected": {k: a[k] for k in LEVELS},
                "candidate": {k: b[k] for k in LEVELS},
            }
            for a, b in zip(selected, rows, strict=True)
            if any(a[k] != b[k] for k in LEVELS)
        ]
        interpretation = root_interpretations(
            personality,
            [selected, rows],
            comparison_epochs=(solver["design_jd_tt"], tt),
            family_candidate_index=index,
        )
        candidates.append(
            {
                **entry,
                "activation_changes_from_selected": changes,
                "snapshot": snapshot,
                "changes_from_selected": joint_changes(baseline, snapshot),
                "comparison_basis": interpretation["comparison_basis"],
                "interpretation_from_selected": interpretation,
            }
        )
    return {
        "status": "all_observed_candidate_epochs_assessed",
        "candidates": candidates,
        "actual_epoch_count": len(candidates),
        "any_activation_subdivision_change": any(
            c["activation_changes_from_selected"] for c in candidates
        ),
        "continuous_root_count_certified": False,
        "unique_physical_root_certified": False,
        "native_execution_authenticated": False,
        "scope": SCOPE,
    }


def assess_family(
    solver: dict[str, Any],
    personality: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    node_mode: str,
    *,
    require_swiss_files: bool,
    backend: str,
) -> dict[str, Any] | None:
    known = {
        r["jd_tt"]: r
        for r in solver["numerical_precision"]["design_body_endpoint_assessment"][
            "evaluations"
        ]
    }
    raw = []
    for tt in candidate_times(solver):
        if tt in known:
            entry = {**known[tt]}
        else:
            positions = positions_at_tt(
                tt,
                node_mode,
                require_swiss_files=require_swiss_files,
                backend=backend,
                source_role="root_bracket_activation",
            )
            entry = {
                "jd_tt": tt,
                "native_positions": pack_native_positions(
                    [{"body": body, **row} for body, row in positions.items()]
                ),
                "source_role": "root_bracket_activation",
            }
        raw.append(entry)
    return derive_family(
        solver,
        personality,
        selected,
        node_mode,
        raw,
        require_swiss_files=require_swiss_files,
    )
