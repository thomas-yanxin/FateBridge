"""Coherent mechanical projections for one sampled chart, never a time oracle.

Gate/line values for every activation and the eight Variable Tones are retained
in their original array order. All calculation paths are local to this snapshot.
Caches live for one comparison only; no caller can poison a later run's results.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fatebridge.core.human_design_bridging import definition_bridging
from fatebridge.core.human_design_circuitry import circuitry_summary
from fatebridge.core.human_design_depth import depth_evidence
from fatebridge.core.human_design_profile import profile_evidence
from fatebridge.core.human_design_variables import variables_from_activations

SIDES = ("personality", "design")
VARIABLE_BODIES = {"Sun", "Earth", "NorthNode", "SouthNode"}
EXPECTED_BODIES = VARIABLE_BODIES | {
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
}
PROJECTION_SCOPE = "本联合快照保留门线、八个Variable Tone及人格日地／交点Color；calculation_path与basis相对本快照。桥接、固定、回路、角色、箭头及Color分类均取同一见证，不拼接名义盘；不含完整黄经，不认证天文真实性、连续稳定或实际心理状态。"


def _activation_projection(chart: dict[str, Any]) -> dict[str, Any]:
    return {
        side: [
            {
                "body": row["body"],
                "gate": row["gate"],
                "line": row["line"],
                **({"tone": row["tone"]} if row["body"] in VARIABLE_BODIES else {}),
                **(
                    {"color": row.get("color")}
                    if side == "personality" and row["body"] in VARIABLE_BODIES
                    else {}
                ),
            }
            for row in chart["activations"][side]
        ]
        for side in SIDES
    }


def _variables(activations: dict[str, Any]) -> dict[str, Any]:
    projected = variables_from_activations(activations)
    for row in projected["arrows"]:
        row.pop("ephemeris_models")
    projected["scope"] = (
        "仅相对于本联合快照的八个实际Tone重建四箭头；后端按外层实际记录核对，完整坐标须按见证与同一星历配置重放。不能拼接其他快照的箭头。"
    )
    return projected


class JointSnapshotCache:
    """Cache by actual dependency: gate union, gate/line matrix and Tone cells."""

    def __init__(self) -> None:
        self.bridges: dict[tuple[int, ...], dict[str, Any]] = {}
        self.depth: dict[tuple[Any, ...], dict[str, Any]] = {}
        self.snapshots: dict[tuple[Any, ...], dict[str, Any]] = {}

    @staticmethod
    def key(chart: dict[str, Any]) -> tuple[Any, ...]:
        return tuple(
            (
                side,
                row["body"],
                (type(row["gate"]).__name__, row["gate"]),
                (type(row["line"]).__name__, row["line"]),
                (
                    (type(row.get("tone")).__name__, row.get("tone"))
                    if row["body"] in VARIABLE_BODIES
                    else None
                ),
                (
                    (type(row.get("color")).__name__, row.get("color"))
                    if side == "personality" and row["body"] in VARIABLE_BODIES
                    else None
                ),
            )
            for side in SIDES
            for row in chart["activations"][side]
        )

    def snapshot(self, chart: dict[str, Any]) -> dict[str, Any]:
        key = self.key(chart)
        if key in self.snapshots:
            return self.snapshots[key]
        projected = _activation_projection(chart)
        gate_key = tuple(
            sorted({row["gate"] for side in SIDES for row in projected[side]})
        )
        line_key = tuple(row[:4] for row in key)
        if gate_key not in self.bridges:
            self.bridges[gate_key] = definition_bridging(chart["bodygraph"])
        if line_key not in self.depth:
            self.depth[line_key] = depth_evidence(chart)
        variables = _variables(projected)
        result: dict[str, Any] = {
            "projection_format": "gate_line_tone_personality_color_v2",
            **{
                k: deepcopy(chart["bodygraph"][k])
                for k in (
                    "type",
                    "subtype",
                    "authority",
                    "strategy",
                    "definition",
                    "channels",
                )
            },
            "activated_gates": list(gate_key),
            "circuitry": circuitry_summary(chart["bodygraph"]["channels"], gate_key),
            "activations": projected,
            "variables": variables,
            "variable_code": variables["code"],
            "definition_bridging": self.bridges[gate_key],
            "depth_evidence": self.depth[line_key],
            "profile_evidence": profile_evidence(chart),
            "scope": PROJECTION_SCOPE,
            **{
                k: deepcopy(chart[k])
                for k in ("profile", "incarnation_cross")
                if k in chart
            },
        }
        self.snapshots[key] = result
        return result


def joint_changes(
    before_snapshot: dict[str, Any], after_snapshot: dict[str, Any]
) -> dict[str, Any]:
    before_bridges, after_bridges = (
        s["definition_bridging"] for s in (before_snapshot, after_snapshot)
    )
    before_fixings, after_fixings = (
        s["depth_evidence"]["line_fixings"] for s in (before_snapshot, after_snapshot)
    )
    changes = {
        "definition_bridging_changed": before_bridges != after_bridges,
        "minimum_bridge_count_changed": before_bridges["minimum_added_gate_count"]
        != after_bridges["minimum_added_gate_count"],
        "minimum_bridge_sets_changed": [
            s["added_gates"] for s in before_bridges["minimum_solutions"]
        ]
        != [s["added_gates"] for s in after_bridges["minimum_solutions"]],
        "line_fixing_changes": [
            {
                "side": a["side"],
                "body": a["body"],
                "before": a,
                "after": b,
                "status_changed": a["status"] != b["status"],
                "fixing_state_changed": a["fixing_state"] != b["fixing_state"],
            }
            for a, b in zip(before_fixings, after_fixings)
            if a != b
        ],
        "variable_tones_changed": [
            a["tone"] for a in before_snapshot["variables"]["arrows"]
        ]
        != [a["tone"] for a in after_snapshot["variables"]["arrows"]],
        "personality_colors_changed": before_snapshot["variables"]["personality_colors"]
        != after_snapshot["variables"]["personality_colors"],
    }
    changes["joint_evidence_summary"] = {
        **{
            k: changes[k]
            for k in (
                "definition_bridging_changed",
                "minimum_bridge_count_changed",
                "minimum_bridge_sets_changed",
                "variable_tones_changed",
                "personality_colors_changed",
            )
        },
        "line_fixing_change_count": len(changes["line_fixing_changes"]),
        "scope": "同一比较中的实际联合投影差异；方案数量相同不代表门集相同，不是误差界或概率。",
    }
    return changes


def position_provenance(chart: dict[str, Any]) -> dict[str, Any]:
    return {
        "tt_epochs": {side: chart["time_scales"][side]["jd_tt"] for side in SIDES},
        "ephemeris_models": {
            side: {
                a["body"]: a["ephemeris_model"]
                for a in chart["activations"][side]
                if "ephemeris_model" in a
            }
            for side in SIDES
        },
        "return_flags": {
            side: {
                a["body"]: a["return_flags"]
                for a in chart["activations"][side]
                if "return_flags" in a
            }
            for side in SIDES
        },
        "scope": "实际计算返回的后端/标志及TT；不含完整坐标，不构成独立天文精度或见证真实性认证。",
    }


def joint_evidence_summary(
    nominal: dict[str, Any], variants: list[dict[str, Any]]
) -> dict[str, Any]:
    baseline = nominal["definition_bridging"]
    original = {tuple(s["added_gates"]) for s in baseline["minimum_solutions"]}
    first_bridge = None
    for index, row in enumerate(variants):
        report = row["value"]["definition_bridging"]
        observed = {tuple(s["added_gates"]) for s in report["minimum_solutions"]}
        if observed != original and first_bridge is None:
            added = sorted(observed - original)
            removed = sorted(original - observed)
            first_bridge = {
                "witness": {
                    k: row["first_observed_witness"][k]
                    for k in (
                        "birth_jd_tt",
                        "design_jd_tt",
                        "birth_utc",
                        "utc_label_status",
                    )
                },
                "full_witness_path": f"time_sensitivity.classification_variants.{index}.first_observed_witness",
                "minimum_added_gate_count": report["minimum_added_gate_count"],
                "minimum_solution_count": report["minimum_solution_count"],
                "added_gate_sets_preview": [list(s) for s in added[:3]],
                "removed_gate_sets_preview": [list(s) for s in removed[:3]],
                "added_gate_set_count": len(added),
                "removed_gate_set_count": len(removed),
                "preview_is_truncated": len(added) > 3 or len(removed) > 3,
            }
    return {
        "status": "sampled_joint_evidence_compared",
        "distinct_joint_projection_count": len(variants),
        "bridge_minimum_gate_count_changed": any(
            row["value"]["definition_bridging"]["minimum_added_gate_count"]
            != baseline["minimum_added_gate_count"]
            for row in variants
        ),
        "bridge_families_changed": first_bridge is not None,
        "line_fixing_evidence_changed": any(
            row["value"]["depth_evidence"]["line_fixings"]
            != nominal["depth_evidence"]["line_fixings"]
            for row in variants
        ),
        "variable_tones_changed": any(
            joint_changes(nominal, row["value"])["variable_tones_changed"]
            for row in variants
        ),
        "personality_colors_changed": any(
            joint_changes(nominal, row["value"])["personality_colors_changed"]
            for row in variants
        ),
        "first_bridge_change": first_bridge,
        "scope": "只汇总已采样联合状态，首次见证不是精确变化边界；同门数同数量的方案也可能不同。预览非完整差异清单，完整方案及线固定读取同一run；不提供连续稳定证明、概率或生时置信度。",
    }
