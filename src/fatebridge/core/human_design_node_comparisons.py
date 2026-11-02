"""Minimal native node witnesses and deterministic counterfactual mechanics.

Reconstruction verifies internal relationships without asking the ephemeris to
produce the answer again. A supplied witness is not an authenticated sky record.
"""

from __future__ import annotations

import math
from typing import Any

from fatebridge.core.astro.profiles import ANALYTICAL_MEAN_NODE_MODEL
from fatebridge.core.human_design_mechanics import (
    bodygraph,
    longitude_activation,
    opposite_activation,
)
from fatebridge.core.human_design_provenance import position_flag_model
from fatebridge.core.human_design_sensitivity import SIDES, compare_charts
from fatebridge.core.human_design_variables import variables_from_activations

CONVENTION_SCOPE = "显式展示交点约定影响；不以更符合自我描述为由选择口径。"
NODE_SOURCE = "https://www.astro.com/swisseph/swisseph.htm"


def node_reference_witness(chart: dict[str, Any]) -> dict[str, Any]:
    return {
        side: {
            "jd_tt": chart["time_scales"][side]["jd_tt"],
            **{
                key: next(
                    a for a in chart["activations"][side] if a["body"] == "NorthNode"
                )[key]
                for key in ("longitude", "longitude_speed", "return_flags")
            },
        }
        for side in SIDES
    }


def reconstruct_node_reference(
    selected: dict[str, Any],
    witness: dict[str, Any],
    node_mode: str,
    *,
    required_model: str | None = None,
    require_swiss_files: bool = False,
) -> dict[str, Any]:
    if node_mode not in {"true", "mean"} or set(witness) != set(SIDES):
        raise ValueError("Invalid node reference convention or sides")
    reference = {**selected, "activations": {}}
    for side in SIDES:
        row = witness[side]
        if (
            set(row) != {"jd_tt", "longitude", "longitude_speed", "return_flags"}
            or any(
                type(row[k]) is not float or not math.isfinite(row[k])
                for k in ("jd_tt", "longitude", "longitude_speed")
            )
            or row["jd_tt"] != selected["time_scales"][side]["jd_tt"]
            or not 0 <= row["longitude"] < 360
        ):
            raise ValueError("Node reference is malformed or detached from selected TT")
        native = position_flag_model(row["return_flags"])
        if (required_model is not None and native != required_model) or (
            require_swiss_files and native != "swieph"
        ):
            raise ValueError("Node reference flag violates the requested source")
        provenance = {
            "longitude_speed": row["longitude_speed"],
            "return_flags": row["return_flags"],
            "native_return_flag_model": native,
            "ephemeris_model": (
                ANALYTICAL_MEAN_NODE_MODEL if node_mode == "mean" else native
            ),
        }
        reference["activations"][side] = [
            (
                {
                    "body": a["body"],
                    **provenance,
                    **(
                        opposite_activation(row["longitude"])
                        if a["body"] == "SouthNode"
                        else longitude_activation(row["longitude"])
                    ),
                    **(
                        {"derived_from": "NorthNode"}
                        if a["body"] == "SouthNode"
                        else {}
                    ),
                }
                if a["body"] in {"NorthNode", "SouthNode"}
                else a
            )
            for a in selected["activations"][side]
        ]
    reference["bodygraph"] = bodygraph(
        (a["gate"] for a in reference["activations"]["personality"]),
        (a["gate"] for a in reference["activations"]["design"]),
    )
    reference["variables"] = variables_from_activations(reference["activations"])
    return reference


def node_convention_report(
    selected: dict[str, Any], reference: dict[str, Any], node_mode: str
) -> dict[str, Any]:
    if node_mode not in {"true", "mean"}:
        raise ValueError("Invalid selected node mode")
    return {
        "selected": node_mode,
        "alternative": "mean" if node_mode == "true" else "true",
        **compare_charts(selected, reference, include_snapshots=True),
        "reference_node_positions": node_reference_witness(reference),
        "scope": CONVENTION_SCOPE,
    }


def node_comparison_reading(chart: dict[str, Any]) -> str:
    convention = chart["node_convention_comparison"]
    backend = chart["node_backend_comparison"]
    names = {"true": "真交点", "mean": "平交点"}
    text = (
        f"本盘采用{names[convention['selected']]}，并在同一人格／设计TT下与{names[convention['alternative']]}对照；"
        f"已列出{len(convention['changed_activations'])}项门至Base细分有变化的激活。"
        "口径不能按更符合自我描述来挑选。"
    )
    status = backend["status"]
    if status in {"cross_backend_compared", "same_backend_not_independent"}:
        maximum = max(r["difference_arcseconds"] for r in backend["rows"])
        text += (
            f"同TT、仅替换节点后端的四项南北交点对照，最大观测差为{maximum:.6g}角秒。"
        )
        if status == "same_backend_not_independent":
            text += "所选与对照均为Moshier，不能据此声称独立后端验证。"
        else:
            text += "这是所列后端间的差值，不能当作真实位置误差上界。"
    elif status == "analytic_mean_node_not_cross_validated":
        text += "平交点沿用同一解析模型，切换星历旗标不产生独立的平交点模型验收。"
    elif status == "reference_disabled_by_strict_jpl_policy":
        text += "显式JPL配置下，附加Moshier节点对照未执行，不能补造其差值。"
    elif status == "reference_unavailable":
        text += "节点后端对照不可用，未取得该项差值；缺项不代表两者一致。"
    else:
        raise ValueError("Unknown node comparison outcome")
    return (
        text
        + "节点对照只替换节点；整盘后端重排及其独立设计根另见ephemeris_backend_comparison。见证与本地重建不认证原生调用真实性、天文精度、完整原典或现实预测。"
    )
