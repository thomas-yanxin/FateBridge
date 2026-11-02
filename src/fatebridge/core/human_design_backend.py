"""Observed full-chart Moshier comparison, including its own solar-arc root."""

from __future__ import annotations

from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.human_design import chart_at_tt
from fatebridge.core.human_design_joint import position_provenance
from fatebridge.core.human_design_sensitivity import LEVELS, SIDES, compare_charts
from fatebridge.core.jpl_ephemeris import configured_jpl_file

SOURCE = "https://www.astro.com/swisseph/swisseph.htm"


def backend_report_base(chart: dict[str, Any], node_mode: str) -> dict[str, Any]:
    return {
        "method_id": "human_design_full_backend_comparison_v1",
        "node_mode": node_mode,
        "reference_backend": "moshier",
        # True only when the complete reference chart was calculated.
        "reference_computation_performed": False,
        "unavailable_reason": None,
        "selected_models": sorted(
            {a["ephemeris_model"] for side in SIDES for a in chart["activations"][side]}
        ),
        "selected_model_scope": "all_factor_computation_models",
        "selected_physical_models": sorted(
            {
                a["ephemeris_model"]
                for side in SIDES
                for a in chart["activations"][side]
                if a["body"] not in {"Earth", "NorthNode", "SouthNode"}
            }
        ),
        "mean_node_flag_scope": (
            "平交点为解析平均要素，其返回SWIEPH/MOSEPH旗标不证明读取了Swiss数据文件，也不构成独立交点模型。"
            if node_mode == "mean"
            else None
        ),
        "selected_provenance": position_provenance(chart),
        "independent_astronomy_certified": False,
        "subdivision_accuracy_certified": False,
        "source_url": SOURCE,
        "target_scope": "太阳和月亮的地心视位置；火星至冥王星采用行星系统质心，非卫星分辨后的星体中心；地球和南交点仍为体系对点。",
        "rows": [],
        "changed_levels": [],
        "joint_evidence_summary": None,
        "mechanical_comparison": None,
        "reference_chart": None,
        "design_time_difference_seconds": None,
        "scope": "同一出生TT、同一交点约定，以实际Moshier后端重算全部激活及其自身88度太阳弧设计时刻。设计盘两侧TT可以不同，差值含求根位移；不与同TT仅替换节点的node_backend_comparison混同。参考不是所选主盘，不按认同感择盘；后端差异不是误差上界、概率或独立认证。平交点仍是解析平均要素。",
    }


def full_backend_report(
    chart: dict[str, Any], alternate: dict[str, Any], node_mode: str
) -> dict[str, Any]:
    """Pure local derivations, also rebuilt by the reading verifier."""
    rows = []
    for side in SIDES:
        for a, b in zip(chart["activations"][side], alternate["activations"][side]):
            rows.append(
                {
                    "side": side,
                    "body": a["body"],
                    "selected_jd_tt": chart["time_scales"][side]["jd_tt"],
                    "reference_jd_tt": alternate["time_scales"][side]["jd_tt"],
                    "selected_longitude": a["longitude"],
                    "reference_longitude": b["longitude"],
                    "difference_arcseconds": abs(
                        (b["longitude"] - a["longitude"] + 180) % 360 - 180
                    )
                    * 3600,
                    "selected": {k: a[k] for k in LEVELS},
                    "reference": {k: b[k] for k in LEVELS},
                    "changed_levels": [k for k in LEVELS if a[k] != b[k]],
                }
            )
    comparison = compare_charts(chart, alternate, include_snapshots=True)
    return {
        **backend_report_base(chart, node_mode),
        "status": "full_backend_compared",
        "reference_computation_performed": True,
        "rows": rows,
        "changed_levels": [
            k for k in LEVELS if any(k in r["changed_levels"] for r in rows)
        ],
        "mechanical_comparison": comparison,
        "joint_evidence_summary": comparison["joint_evidence_summary"],
        "reference_chart": alternate,
        "reference_provenance": position_provenance(alternate),
        "design_time_difference_seconds": (
            alternate["time_scales"]["design"]["jd_tt"]
            - chart["time_scales"]["design"]["jd_tt"]
        )
        * 86400,
    }


def compare_full_backends(chart: dict[str, Any], node_mode: str) -> dict[str, Any]:
    if node_mode not in {"true", "mean"}:
        raise ValueError("node_mode 必须为 true 或 mean")
    base = backend_report_base(chart, node_mode)
    if base["selected_physical_models"] == ["moshier"]:
        return {**base, "status": "same_backend_not_independent"}
    if runtime.swe is None:
        return {
            **base,
            "status": "reference_unavailable",
            "unavailable_reason": "native_reference_unavailable",
        }
    if configured_jpl_file() is not None:
        return {
            **base,
            "status": "reference_disabled_by_strict_jpl_policy",
            "reference_computation_performed": False,
            "unavailable_reason": "jpl_mixed_request",
        }
    try:
        alternate = chart_at_tt(
            chart["time_scales"]["personality"]["jd_tt"], node_mode, backend="moshier"
        )
    except (runtime.swe.Error, RuntimeError):
        return {
            **base,
            "status": "reference_unavailable",
            "unavailable_reason": "native_reference_unavailable",
        }
    return full_backend_report(chart, alternate, node_mode)
