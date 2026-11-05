"""Observed node-backend differences at the selected chart's exact TT epochs.

The comparison changes only the node backend. It is neither an independent
astronomical oracle nor a full chart recalculated with another ephemeris.
"""

from __future__ import annotations

import math
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.human_design_mechanics import (
    bodygraph,
    longitude_activation,
    opposite_activation,
)
from fatebridge.core.human_design_natal_sources import observe_native_source
from fatebridge.core.human_design_node_comparisons import node_reference_witness
from fatebridge.core.human_design_provenance import position_flag_model
from fatebridge.core.human_design_sensitivity import LEVELS, SIDES, compare_charts
from fatebridge.core.human_design_variables import variables_from_activations
from fatebridge.core.jpl_ephemeris import configured_jpl_file

NODE_SOURCE = "https://www.astro.com/swisseph/swisseph.htm"


def node_backend_base(chart: dict[str, Any], node_mode: str) -> dict[str, Any]:
    """Retain selected results and expose an actual Moshier node comparison.

    Mean nodes are analytical elements: selecting another ephemeris flag does
    not create an independent mean-node model. No remote data are fetched.
    """
    if node_mode not in {"true", "mean"}:
        raise ValueError("node_mode 必须为 true 或 mean")
    report: dict[str, Any] = {
        "method_id": "human_design_observed_node_backend_comparison_v1",
        "node_mode": node_mode,
        "reference_backend": "moshier",
        "source_url": NODE_SOURCE,
        "published_difference": {
            "jpl_vs_moshier_true_node_approximate_max_arcseconds": 70,
            "jpl_vs_swiss_true_node_approximate_max_arcseconds": 0.1,
            "kind": "publisher_reported_approximate_differences_not_per_chart_error_bounds",
        },
        "independent_astronomy_certified": False,
        "subdivision_accuracy_certified": False,
        "rows": [],
        "reference_node_positions": None,
        "joint_evidence_summary": None,
        "changed_levels": [],
        "scope": "仅在所选人格/设计TT时刻替换交点后端，其他激活及太阳弧求根保持所选结果；不是另一后端的完整重排。后端相同或吻合不证明细分准确，差值不是实际误差上界或概率；两种交点约定另见node_convention_comparison。",
    }
    return report


def compare_node_backends(chart: dict[str, Any], node_mode: str) -> dict[str, Any]:
    report = node_backend_base(chart, node_mode)
    if node_mode == "mean":
        return {
            **report,
            "status": "analytic_mean_node_not_cross_validated",
            "reference_backend": None,
            "mechanical_comparison": None,
        }
    if runtime.swe is None:
        return {
            **report,
            "status": "reference_unavailable",
            "mechanical_comparison": None,
        }
    if configured_jpl_file() is not None:
        return {
            **report,
            "status": "reference_disabled_by_strict_jpl_policy",
            "reference_computation_performed": False,
            "unavailable_reason": "jpl_mixed_request",
            "mechanical_comparison": None,
        }
    alternate = {**chart, "activations": {}}
    for side in SIDES:
        jd_tt = chart["time_scales"][side]["jd_tt"]
        try:
            coordinates, flags = runtime.ephemeris_call(
                "calc",
                jd_tt,
                runtime.swe.TRUE_NODE,
                runtime.swe.FLG_MOSEPH | runtime.swe.FLG_SPEED,
            )
        except (runtime.swe.Error, RuntimeError):
            return {
                **report,
                "status": "reference_unavailable",
                "mechanical_comparison": None,
                "unavailable_side": side,
            }
        try:
            native_model = position_flag_model(flags)
        except ValueError:
            native_model = None
        if native_model != "moshier" or not all(
            math.isfinite(float(coordinates[i])) for i in (0, 3)
        ):
            return {
                **report,
                "status": "reference_unavailable",
                "mechanical_comparison": None,
                "unavailable_side": side,
            }
        observe_native_source("NorthNode", jd_tt, flags, role="node_reference")
        alternate["activations"][side] = []
        for selected in chart["activations"][side]:
            body = selected["body"]
            if body not in {"NorthNode", "SouthNode"}:
                alternate["activations"][side].append(selected)
                continue
            source_longitude = float(coordinates[0]) % 360
            activation = (
                opposite_activation(source_longitude)
                if body == "SouthNode"
                else longitude_activation(source_longitude)
            )
            reference = {
                **selected,
                **activation,
                "longitude_speed": float(coordinates[3]),
                "return_flags": int(flags),
                "ephemeris_model": "moshier",
                "native_return_flag_model": "moshier",
            }
            if body == "SouthNode":
                reference["derived_from"] = "NorthNode"
            alternate["activations"][side].append(reference)
    return node_backend_report(chart, alternate, node_mode)


def node_backend_report(
    chart: dict[str, Any], alternate: dict[str, Any], node_mode: str
) -> dict[str, Any]:
    report = node_backend_base(chart, node_mode)
    rows = []
    for side in SIDES:
        jd_tt = chart["time_scales"][side]["jd_tt"]
        for selected, reference in zip(
            chart["activations"][side], alternate["activations"][side]
        ):
            body = selected["body"]
            if body not in {"NorthNode", "SouthNode"}:
                continue
            flags = reference["return_flags"]
            longitude = reference["longitude"]
            rows.append(
                {
                    "side": side,
                    "body": body,
                    "jd_tt": jd_tt,
                    "selected_backend": selected["ephemeris_model"],
                    "selected_return_flags": selected["return_flags"],
                    "reference_backend": "moshier",
                    "reference_return_flags": int(flags),
                    "selected_longitude": selected["longitude"],
                    "reference_longitude": longitude,
                    "difference_arcseconds": abs(
                        (longitude - selected["longitude"] + 180) % 360 - 180
                    )
                    * 3600,
                    "selected": {level: selected[level] for level in LEVELS},
                    "reference": {level: reference[level] for level in LEVELS},
                    "changed_levels": [
                        level for level in LEVELS if selected[level] != reference[level]
                    ],
                    "selected_tone_orientation": selected["tone_orientation"],
                    "reference_tone_orientation": reference["tone_orientation"],
                }
            )
    alternate["bodygraph"] = bodygraph(
        (a["gate"] for a in alternate["activations"]["personality"]),
        (a["gate"] for a in alternate["activations"]["design"]),
    )
    alternate["variables"] = variables_from_activations(alternate["activations"])

    comparison = compare_charts(chart, alternate, include_snapshots=True)
    selected_structure = comparison.pop("selected_structure")
    reference_structure = comparison.pop("reference_structure")
    return {
        **report,
        "status": (
            "cross_backend_compared"
            if any(row["selected_backend"] != "moshier" for row in rows)
            else "same_backend_not_independent"
        ),
        "rows": rows,
        "reference_node_positions": node_reference_witness(alternate),
        "changed_levels": [
            level
            for level in LEVELS
            if any(level in row["changed_levels"] for row in rows)
        ],
        "mechanical_comparison": comparison,
        "selected_structure": selected_structure,
        "reference_structure": reference_structure,
        "joint_evidence_summary": comparison["joint_evidence_summary"],
    }
