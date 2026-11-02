"""Expanded official observations, with exact edition differences retained."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fatebridge.core.human_design_depth import depth_reference
from fatebridge.core.human_design_references import reference_data, reference_sha256
from fatebridge.core.human_design_source_variants import compare_name


def cross_coverage_reference() -> dict[str, Any]:
    return reference_data("cross-coverage-2026-reference.json")


def cross_coverage_sha256() -> str:
    return reference_sha256("cross-coverage-2026-reference.json")


def expanded_cross_audit() -> dict[str, Any]:
    ref = cross_coverage_reference()
    rows = []
    for r in ref["observations"]:
        primary = depth_reference()["gates"][r["gates"][0] - 1]["cross_identifiers"][
            r["angle"]
        ]
        rows.append(
            {"case_id": r["case_id"], **compare_name(primary, r["display_name"])}
        )
    strata = {(r["gates"][0], r["angle"]) for r in ref["observations"]}
    wanted = {
        (gate, angle)
        for gate in range(1, 65)
        for angle in ("right", "juxtaposition", "left")
    }
    return {
        "method_id": ref["method_id"],
        "catalog_sha256": cross_coverage_sha256(),
        "cohort_sha256": ref["cohort_sha256"],
        "observations_checked": len(rows),
        "gate_angle_strata_checked": len(strata),
        "all_192_gate_angle_strata_observed": strata == wanted,
        "literal_name_matches": sum(r["literal_match"] for r in rows),
        "name_comparisons": rows,
        "course_list_disagreement": deepcopy(ref["course_list_disagreement"]),
        "all_disagreements_resolved": False,
        "scope": "新增193个1980年虚构输入的官方观察，覆盖64门×三角度；逐项保留字面失败。原19盘及15项失败不替换。不是全部出生盘、原典线义、全历法精度或现实预测认证。",
    }


def expanded_cross_evidence(chart: dict[str, Any]) -> dict[str, Any]:
    cross = chart["incarnation_cross"]
    ref = cross_coverage_reference()
    matching = [
        r
        for r in ref["observations"]
        if r["gates"] == cross["gates"] and r["angle"] == cross["angle"]
    ]
    labels = sorted({r["display_name"] for r in matching})
    course = ref["course_list_disagreement"]
    affected = any(r["case_id"] == course["official_chart_case_id"] for r in matching)
    return {
        "method_id": "human_design_official_cross_labels_v1",
        "status": (
            "observed_same_quartet_and_angle"
            if matching
            else "not_observed_in_expanded_cohort"
        ),
        "primary_2001_name": cross["name"],
        "primary_name_retained": True,
        "observed_labels": [compare_name(cross["name"], name) for name in labels],
        "observations": deepcopy(matching),
        "course_list_disagreement": deepcopy(course) if affected else None,
        "catalog_sha256": cross_coverage_sha256(),
        "source_url": ref["source"]["url"],
        "source_publisher": ref["source"]["publisher"],
        "observations_fixture_sha256": ref["source"]["observation_fixture_sha256"],
        "plan_sha256": ref["source"]["plan_sha256"],
        "full_source_acceptance_passed": False,
        "scope": "仅报告新增193盘的同四门、同角度观察；保留2001名、拒绝别名及事件预言。覆盖192门角组合不认证全部生时、角色细节或星历口径。",
    }


def expanded_cross_reading(record: dict[str, Any]) -> str:
    text = f"本盘2001原典名称为{record['primary_2001_name']}。"
    labels = record["observed_labels"]
    if labels:
        text += (
            "新增官方样本对同四门及角度显示"
            + "／".join(r["observed_official_name"] for r in labels)
            + "；"
        )
        text += (
            "此名称字面一致。"
            if all(r["literal_match"] for r in labels)
            else "字面或编号仍有差异，保留原典名称，不作别名归并。"
        )
    else:
        text += "新增官方样本未观察到本盘四门及角度，不补造名称映射。"
    if record["course_list_disagreement"]:
        text += "官方课程页列16/6｜63/64，同次冻结官方盘显示16/9｜63/64；课程列项与日地对宫关系冲突，未取得出版方勘误，不用该列项改写本盘激活。"
    return (
        text
        + "新增193盘覆盖192个门角组合，仍是有限虚构输入；本段不代表完整线义、任意自由文本或现实预测验收。"
    )
