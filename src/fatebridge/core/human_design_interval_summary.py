"""Small field-bound interval summaries, distinct from continuous stability."""

from typing import Any


def interval_summary(report: dict[str, Any]) -> dict[str, Any]:
    assessed = report["status"] != "not_assessed"
    result = {
        "status": report["status"],
        "plus_minus_minutes": report["plus_minus_minutes"],
        "evaluated_full_charts": (
            report["sampling"]["total_evaluation_count"] if assessed else 0
        ),
        "changed_activation_count": (
            len(report["activation_variants"]) if assessed else None
        ),
        "changed_joint_fields": (
            report["observed_changed_structure_fields"] if assessed else None
        ),
        "station_candidates": len(report["station_candidates"]) if assessed else None,
        "unresolved_multiple_dependency_brackets": (
            report["joint_transition_refinement_summary"][
                "unresolved_multiple_dependency_brackets"
            ]
            if assessed
            else None
        ),
        "physical_models": report["ephemeris_models_observed"] if assessed else None,
        "future_leap_seconds_assumed_unchanged": (
            report["sampled_future_leap_seconds_assumed_unchanged"]
            if assessed
            else None
        ),
        "continuous_interval_certified": False,
        "native_execution_authenticated": False,
        "scope": "区间样本的实际计数和观察到的变化，不是独立样本量、概率、出生钟认证或连续稳定性；未评估时不作稳定判断。",
    }
    if "station_coordinate_extremum_assessment" in report:
        probes = report["station_coordinate_extremum_assessment"]
        result["coordinate_extremum_probes"] = probes["probe_count"]
        result["coordinate_probe_budget_exhausted"] = probes["budget_exhausted"]
        result["coordinate_probe_unresolved_directions"] = sum(
            p["status"] == "direction_not_inferred" for p in probes["probes"]
        )
    return result


def unassessed_interval() -> dict[str, Any]:
    result = {
        "status": "not_assessed",
        "plus_minus_minutes": 0,
        "joint_evidence_summary": None,
        "observed_changed_structure_fields": None,
        "sampling": None,
        "joint_evidence_cache": None,
        "joint_transition_refinement": None,
        "joint_transition_refinement_summary": None,
        "evaluation_witnesses": None,
    }
    return {**result, "summary": interval_summary(result)}


def interval_reading(summary: dict[str, Any]) -> str:
    if summary["status"] == "not_assessed":
        return "本次未请求出生时间范围评估，说明只针对名义时刻；不能据此声称出生钟已核实或附近时刻的结果稳定。"
    changes = summary["changed_joint_fields"]
    joint = (
        ("联合门线／八个Tone投影变化字段为" + "、".join(changes) + "。")
        if changes
        else "已列样本未观察到联合门线／八个Tone投影变化；这不覆盖所有Color／Base变化，更不证明整个连续区间稳定。"
    )
    candidates = (
        f"{summary['station_candidates']}个速度变号或网格零速度候选，"
        f"补查{summary['coordinate_extremum_probes']}个返回黄经极值候选。"
        f"坐标细查预算{'已耗尽' if summary['coordinate_probe_budget_exhausted'] else '未耗尽'}，"
        f"{summary['coordinate_probe_unresolved_directions']}个候选方向未定；速度零值不认证坐标极值。"
        if "coordinate_extremum_probes" in summary
        else f"{summary['station_candidates']}个速度变号候选。"
    )
    return (
        f"本次按出生名义时刻正负{summary['plus_minus_minutes']}分钟，保留{summary['evaluated_full_charts']}次双时刻整盘求值（含名义盘）；"
        f"观察到{summary['changed_activation_count']}项激活细分变化、"
        + candidates
        + joint
        + f"仍有{summary['unresolved_multiple_dependency_brackets']}个多依赖细区间未分开，不能据数值分辨率声称精确同时。"
        + "全部原生求值与同次联合见证可回放核对；这不认证原生执行或星历误差，有限采样不是连续穷尽，次数和变体数不是概率，也不能跨样本拼盘。"
    )
