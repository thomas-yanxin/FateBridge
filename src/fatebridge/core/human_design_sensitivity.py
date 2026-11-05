"""Observed birth-time variants on continuous TT, without stability certificates.

A bounded grid is supplemented by speed-sign-change candidates and observed
multiple dependency transitions. None proves a continuous interval invariant.
"""

from __future__ import annotations

from typing import Any, Callable

from fatebridge.core.human_design import chart_at_tt
from fatebridge.core.human_design_interval_extrema import (
    probe_station_coordinates,
    zero_speed_components,
)
from fatebridge.core.human_design_interval_summary import interval_summary
from fatebridge.core.human_design_joint import (
    JointSnapshotCache,
    joint_changes,
    joint_evidence_summary,
    position_provenance,
)
from fatebridge.core.human_design_mechanics import BODY_IDS
from fatebridge.core.human_design_sample_witness import pack_sample_witnesses
from fatebridge.core.human_design_transition import refine_joint_transitions

LEVELS = ("gate", "line", "color", "tone", "base")
GRID_STEP_SECONDS = 10
STATION_BRACKET_SECONDS = 0.01
SIDES = ("personality", "design")
DERIVED_BODIES = {"Earth", "SouthNode"}
METHOD = "human_design_continuous_TT_coordinate_interval_v2"


def compare_charts(
    first: dict[str, Any],
    second: dict[str, Any],
    *,
    snapshots: JointSnapshotCache | None = None,
    include_snapshots: bool = False,
) -> dict[str, Any]:
    cache = snapshots or JointSnapshotCache()
    before_snapshot, after_snapshot = cache.snapshot(first), cache.snapshot(second)
    before_variable = first.get("variables", {})
    after_variable = second.get("variables", {})
    variables_compared = all(
        v.get("status") == "computed" for v in (before_variable, after_variable)
    )
    return {
        "provenance": {
            "before": position_provenance(first),
            "after": position_provenance(second),
        },
        **joint_changes(before_snapshot, after_snapshot),
        **(
            {
                "selected_structure": before_snapshot,
                "reference_structure": after_snapshot,
            }
            if include_snapshots
            else {}
        ),
        "variables_compared": variables_compared,
        "variable_changed": (
            before_variable.get("code") != after_variable.get("code")
            if variables_compared
            else None
        ),
        "variable_codes": {
            "before": before_variable.get("code"),
            "after": after_variable.get("code"),
        },
        "changed_classifications": [
            key
            for key in ("type", "subtype", "authority", "strategy", "definition")
            if first["bodygraph"][key] != second["bodygraph"][key]
        ],
        "profile_changed": first["profile"] != second["profile"],
        "changed_activations": [
            {
                "side": side,
                "body": a["body"],
                "before": {k: a[k] for k in LEVELS},
                "after": {k: b[k] for k in LEVELS},
            }
            for side in SIDES
            for a, b in zip(first["activations"][side], second["activations"][side])
            if any(a[k] != b[k] for k in LEVELS)
        ],
    }


def _structure(chart: dict[str, Any]) -> dict[str, Any]:
    return JointSnapshotCache().snapshot(chart)


def _witness(chart: dict[str, Any]) -> dict[str, Any]:
    scale = chart["time_scales"]["personality"]
    return {
        "position_provenance": position_provenance(chart),
        "birth_jd_tt": scale["jd_tt"],
        "design_jd_tt": chart["time_scales"]["design"]["jd_tt"],
        "birth_utc": chart["birth_utc"],
        "utc_label_status": scale.get("utc_label_status", "input_civil_label"),
        "future_leap_seconds_assumed_unchanged": scale[
            "future_leap_seconds_assumed_unchanged"
        ],
    }


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
    cache = {center: nominal}

    def at(jd: float) -> dict[str, Any]:
        if jd not in cache:
            cache[jd] = (
                _chart_reader(jd)
                if _chart_reader is not None
                else chart_at_tt(jd, node_mode, require_swiss_files=require_swiss_files)
            )
        return cache[jd]

    def activation(jd: float, side: str, body: str) -> dict[str, Any]:
        return next(a for a in at(jd)["activations"][side] if a["body"] == body)

    for jd in grid:
        at(jd)
    stations = []
    coordinate_candidates = []
    for side in SIDES:
        for body in (
            a["body"]
            for a in nominal["activations"][side]
            if a["body"] not in DERIVED_BODIES
        ):
            for left, right in zip(grid, grid[1:]):
                vleft = activation(left, side, body)["longitude_speed"]
                vright = activation(right, side, body)["longitude_speed"]
                if vleft * vright >= 0:
                    continue
                kind = "maximum" if vleft > 0 else "minimum"
                lo, hi = left, right
                while (hi - lo) * 86400 > STATION_BRACKET_SECONDS:
                    mid = lo + (hi - lo) / 2
                    vmid = activation(mid, side, body)["longitude_speed"]
                    if vmid == 0:
                        lo = hi = mid
                        break
                    if vleft * vmid < 0:
                        hi = mid
                    else:
                        lo = mid
                        vleft = vmid
                candidate = lo + (hi - lo) / 2
                chart = at(candidate)
                a = activation(candidate, side, body)
                stations.append(
                    {
                        "side": side,
                        "body": body,
                        "status": "bracketed_speed_sign_change_candidate",
                        **_witness(chart),
                        "activation_jd_tt": chart["time_scales"][side]["jd_tt"],
                        "longitude": a["longitude"],
                        "longitude_speed": a["longitude_speed"],
                        "ephemeris_model": a["ephemeris_model"],
                        "birth_bracket_width_seconds": (hi - lo) * 86400,
                    }
                )
                coordinate_candidates.append(
                    {
                        "side": side,
                        "body": body,
                        "source": "speed_sign_change",
                        "kind": kind,
                        "coarse_bracket_jd_tt": [left, right],
                        "seed_birth_jd_tt": [candidate, lo, hi],
                    }
                )

    coordinate_assessment = None
    for side in SIDES:
        for body in (
            a["body"]
            for a in nominal["activations"][side]
            if a["body"] not in DERIVED_BODIES
        ):
            for component in zero_speed_components(grid, side, body, activation):
                coordinate_candidates.append(component)
                tt = component["seed_birth_jd_tt"][0]
                chart = at(tt)
                a = activation(tt, side, body)
                stations.append(
                    {
                        "side": side,
                        "body": body,
                        "status": "sampled_zero_speed_component_candidate",
                        **_witness(chart),
                        "activation_jd_tt": chart["time_scales"][side]["jd_tt"],
                        "longitude": a["longitude"],
                        "longitude_speed": a["longitude_speed"],
                        "ephemeris_model": a["ephemeris_model"],
                        "birth_bracket_width_seconds": (
                            component["coarse_bracket_jd_tt"][1]
                            - component["coarse_bracket_jd_tt"][0]
                        )
                        * 86400,
                        "observed_zero_component_jd_tt": component[
                            "observed_zero_component_jd_tt"
                        ],
                    }
                )
    coordinate_assessment = probe_station_coordinates(coordinate_candidates, at, cache)

    transitions = refine_joint_transitions(cache, at)
    samples = [cache[jd] for jd in sorted(cache)]
    snapshots = JointSnapshotCache()
    baseline = snapshots.snapshot(nominal)
    structures: dict[tuple[Any, ...], dict[str, Any]] = {}
    changed_fields: set[str] = set()
    for chart in samples:
        key = snapshots.key(chart)
        if key not in structures:
            structure = snapshots.snapshot(chart)
            structures[key] = {
                "value": structure,
                "first_observed_witness": _witness(chart),
            }
            changed_fields.update(k for k, v in structure.items() if v != baseline[k])
    variants = []
    for side in SIDES:
        for a in nominal["activations"][side]:
            body = a["body"]
            states: dict[tuple[int, ...], dict[str, Any]] = {}
            for chart in samples:
                observed = next(
                    item for item in chart["activations"][side] if item["body"] == body
                )
                signature = tuple(observed[k] for k in LEVELS)
                if signature not in states:
                    states[signature] = {
                        **_witness(chart),
                        **{k: observed[k] for k in LEVELS},
                        "activation_jd_tt": chart["time_scales"][side]["jd_tt"],
                        "longitude": observed["longitude"],
                        "ephemeris_model": observed["ephemeris_model"],
                        **{
                            key: observed[key]
                            for key in ("derived_from", "derivation_source_longitude")
                            if key in observed
                        },
                    }
            if len(states) > 1:
                variants.append(
                    {
                        "side": side,
                        "body": body,
                        "nominal": {k: a[k] for k in LEVELS},
                        "observed_values": {
                            k: sorted({s[i] for s in states})
                            for i, k in enumerate(LEVELS)
                        },
                        "first_observed_witness_per_state": list(states.values()),
                    }
                )
    ends = [at(grid[0]), at(grid[-1])]
    result = {
        "status": "grid_and_station_candidates_compared",
        "evaluation_witnesses": pack_sample_witnesses(samples),
        "method_id": METHOD,
        "plus_minus_minutes": plus_minus_minutes,
        "node_mode": node_mode,
        "interval": {
            "scale": "TT",
            "start": _witness(ends[0]),
            "end": _witness(ends[1]),
            "radius_seconds": radius,
        },
        "sampling": {
            "target_grid_step_seconds": GRID_STEP_SECONDS,
            "maximum_grid_step_seconds": max(
                (b - a) * 86400 for a, b in zip(grid, grid[1:])
            ),
            "grid_sample_count": len(grid),
            "additional_evaluation_count": len(cache) - len(grid),
            "total_evaluation_count": len(cache),
            "station_candidate_bracket_seconds": STATION_BRACKET_SECONDS,
            "continuous_interval_certified": False,
        },
        "comparisons": [
            {
                "birth_utc": c["birth_utc"],
                "witness": _witness(c),
                "snapshot": snapshots.snapshot(c),
                **compare_charts(nominal, c, snapshots=snapshots),
            }
            for c in ends
        ],
        "observed_changed_structure_fields": sorted(changed_fields),
        "classification_variants": list(structures.values()),
        "joint_evidence_summary": joint_evidence_summary(
            baseline, list(structures.values())
        ),
        "joint_transition_refinement": transitions,
        "joint_transition_refinement_summary": transitions["summary"],
        "joint_evidence_cache": {
            "distinct_mechanical_projections": len(snapshots.snapshots),
            "distinct_gate_union_bridge_calculations": len(snapshots.bridges),
            "distinct_gate_line_depth_calculations": len(snapshots.depth),
            "scope": "仅本次调用缓存确定性依赖；不是独立观测样本量或置信度。",
        },
        "activation_variants": variants,
        "activations_checked_per_sample": 26,
        "combination_policy": "每个联合门线细分组合与身体图变体只对其见证时刻成立；不能跨不同时刻合并单门、通道或角色。变体数和采样次数不是概率或生时置信度。",
        "station_candidates": stations,
        "sampled_nonstandard_civil_labels": [
            {
                "side": side,
                **_witness(c),
                "activation_jd_tt": c["time_scales"][side]["jd_tt"],
                "activation_utc": (
                    c["birth_utc"] if side == "personality" else c["design_utc"]
                ),
                "label_status": c["time_scales"][side].get("utc_label_status"),
            }
            for c in samples
            for side in SIDES
            if c["time_scales"][side].get("utc_is_leap_second")
            or (c["birth_utc"] if side == "personality" else c["design_utc"]) is None
        ],
        "ephemeris_models_observed": sorted(
            {
                a["ephemeris_model"]
                for c in samples
                for values in c["activations"].values()
                for a in values
                if a["body"] in BODY_IDS
            }
        ),
        "ephemeris_model_scope": "physical_bodies",
        "nonphysical_factor_models_observed": {
            body: sorted(
                {
                    a["ephemeris_model"]
                    for c in samples
                    for values in c["activations"].values()
                    for a in values
                    if a["body"] == body
                }
            )
            for body in ("Earth", "NorthNode", "SouthNode")
        },
        "sampled_future_leap_seconds_assumed_unchanged": any(
            c["time_scales"][side]["future_leap_seconds_assumed_unchanged"]
            for c in samples
            for side in SIDES
        ),
        "limitation": "10秒TT网格加检测到的速度变号与多依赖变化候选细查；不是连续区间穷尽证明，不能把未观察到变化说成确定稳定。未分开的细区间和预算耗尽显式保留；不能据数值分辨率断言精确同时。候选不认证真实驻留，压缩月球星历可能有微小分段不连续。民用标签1960年采用SOFA、1961-1971年采用IERS冻结UTC规则，1960年前按历史UT1；所有时刻小数位仅是数值表示。",
    }
    if coordinate_assessment is not None:
        result["station_coordinate_extremum_assessment"] = coordinate_assessment
        result["limitation"] = (
            "10秒TT网格加检测到的速度变号、网格零速度及返回黄经极值候选细查；"
            "坐标细查使用出生TT轴，Design另列实际激活TT，速度零值不等于坐标极值。"
            "黄金分割只保留有限观察，不证明单峰或连续穷尽；预算耗尽和方向未定显式保留。"
            + result["limitation"]
        )
    return {**result, "summary": interval_summary(result)}
