"""Versioned source disagreements and their conditional natal consequences.

An observed label is not an alias or a universal modern naming rule. A literal
printed-line alternative does not define Color/Tone/Base or a valid full chart.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from fatebridge.core.human_design import activation_longitude_fraction
from fatebridge.core.human_design_depth import SIDES, depth_reference, line_fixings
from fatebridge.core.human_design_mechanics import VALID_PROFILES
from fatebridge.core.human_design_references import reference_data, reference_sha256


def variant_reference() -> dict[str, Any]:
    return reference_data("source-variants-2026-reference.json")


def variant_reference_sha256() -> str:
    return reference_sha256("source-variants-2026-reference.json")


def printed_lines() -> dict[int, list[dict[str, Any]]]:
    reference = variant_reference()
    rows = reference["printed_line_arcs"]
    if len(rows) != 384 or {(r["gate"], r["line"]) for r in rows} != {
        (gate, line) for gate in range(1, 65) for line in range(1, 7)
    }:
        raise ValueError("Incomplete source line arcs")
    if (
        reference["printed_source"]["pdf_sha256"]
        != depth_reference()["source"]["pdf_sha256"]
    ):
        raise ValueError("Different original source edition")
    for row in rows:
        if any(
            type(row[k]) is not int or not 0 <= row[k] < 1296000
            for k in ("start_arcseconds", "end_arcseconds")
        ):
            raise ValueError("Invalid exact printed arc")
    return {
        g: sorted((r for r in rows if r["gate"] == g), key=lambda r: r["line"])
        for g in range(1, 65)
    }


def compare_name(primary: str, observed: str) -> dict[str, Any]:
    # Match remains literal. This diagnostic never changes the acceptance bit.
    exact = " ".join(primary.upper().split()) == " ".join(observed.upper().split())
    numbered = re.fullmatch(r"(.+) \(([1-4])\)", primary)
    only_number = bool(numbered and numbered[1].upper() == observed.upper())
    return {
        "primary_2001_name": primary,
        "observed_official_name": observed,
        "literal_match": exact,
        "difference_kind": (
            "literal_match"
            if exact
            else (
                "observed_label_omits_variant_number"
                if only_number
                else "different_literal_label"
            )
        ),
        "alias_accepted": False,
    }


def cross_name_evidence(chart: dict[str, Any]) -> dict[str, Any]:
    reference = variant_reference()
    cross = chart["incarnation_cross"]
    matches = [
        r
        for r in reference["observed_cross_labels"]
        if r["angle"] == cross["angle"] and r["gates"] == cross["gates"]
    ]
    names = sorted({r["display_name"] for r in matches})
    return {
        "status": (
            "observed_same_gate_quartet_and_angle"
            if matches
            else "not_observed_in_frozen_cohort"
        ),
        "primary": {"name": cross["name"], **reference["printed_source"]},
        "observed_labels": [compare_name(cross["name"], n) for n in names],
        "observations": deepcopy(matches),
        "observed_sources": deepcopy(reference["observed_cross_label_sources"]),
        "catalog_sha256": variant_reference_sha256(),
        "disagreement_resolved": bool(matches)
        and all(compare_name(cross["name"], n)["literal_match"] for n in names),
        "scope": "只报告冻结官方样本中相同四门及角度的标签；不推断未观测交叉，不替换2001版名称或忽略编号，不把版本差异当作原典整本通过。",
    }


def source_variant_audit() -> dict[str, Any]:
    reference = variant_reference()
    arcs = printed_lines()
    width = reference["dictionary_source"]["line_arcseconds"]
    disagreements = [
        {
            **r,
            "printed_width_arcseconds": (r["end_arcseconds"] - r["start_arcseconds"])
            % 1296000,
            "dictionary_width_arcseconds": width,
        }
        for rows in arcs.values()
        for r in rows
        if (r["end_arcseconds"] - r["start_arcseconds"]) % 1296000 != width
    ]
    names = []
    for row in reference["observed_cross_labels"]:
        primary = depth_reference()["gates"][row["gates"][0] - 1]["cross_identifiers"][
            row["angle"]
        ]
        names.append(
            {"case_id": row["case_id"], **compare_name(primary, row["display_name"])}
        )
    return {
        "method_id": "human_design_source_variant_audit_v1",
        "catalog_sha256": variant_reference_sha256(),
        "printed_line_count": sum(map(len, arcs.values())),
        "line_width_disagreements": disagreements,
        "dictionary_rule": deepcopy(reference["dictionary_source"]),
        "observed_label_count": len(names),
        "literal_name_matches": sum(r["literal_match"] for r in names),
        "name_comparisons": names,
        "publisher_erratum_obtained": False,
        "all_disagreements_resolved": False,
        "scope": "全384印刷弧长与有限官方名称观察的诊断；解释差异的种类不会把失败项计为通过，未取得29门的出版方勘误。",
    }


def line_variant_impact(chart: dict[str, Any]) -> dict[str, Any]:
    arcs = printed_lines()
    differences = []
    conditional = deepcopy(chart["activations"])
    unambiguous = True
    for side in SIDES:
        activations = chart["activations"].get(side, [])
        for index, activation in enumerate(activations):
            longitude = activation_longitude_fraction(activation) * 3600
            row = arcs[activation["gate"]]
            candidates = [
                r["line"]
                for r in row
                if (longitude - r["start_arcseconds"]) % 1296000
                < (r["end_arcseconds"] - r["start_arcseconds"]) % 1296000
            ]
            if len(candidates) != 1:
                unambiguous = False
            else:
                conditional[side][index]["line"] = candidates[0]
            if candidates != [activation["line"]]:
                differences.append(
                    {
                        "calculation_path": f"activations.{side}.{index}",
                        "side": side,
                        "body": activation["body"],
                        "gate": activation["gate"],
                        "longitude": activation["longitude"],
                        **{
                            k: activation[k]
                            for k in ("derived_from", "derivation_source_longitude")
                            if k in activation
                        },
                        "implemented_uniform_line": activation["line"],
                        "printed_line_candidates": candidates,
                        "source_pdf_page_one_based": row[0]["pdf_page_one_based"],
                    }
                )
    changes = []
    pairs = []
    candidate_profile = None
    if differences and unambiguous:
        # Apply all line alternatives together before assessing any consequence.
        selected_fixings = line_fixings(chart["activations"])
        printed_fixings = line_fixings(conditional)
        changes = [
            {
                "calculation_path": a["calculation_path"],
                "implemented_uniform": a,
                "conditional_printed": b,
            }
            for a, b in zip(selected_fixings, printed_fixings)
            if a != b
        ]
        for side in ("personality", "design"):
            by_body = {r["body"]: r for r in conditional.get(side, [])}
            if not {"Sun", "Earth"} <= by_body.keys():
                continue
            sun, earth = by_body["Sun"]["line"], by_body["Earth"]["line"]
            pairs.append(
                {
                    "side": side,
                    "printed_sun_line": sun,
                    "printed_earth_line": earth,
                    "same_line": sun == earth,
                }
            )
        if len(pairs) == 2 and all(r["same_line"] for r in pairs):
            candidate_profile = "/".join(str(r["printed_sun_line"]) for r in pairs)
    paired = len(pairs) == 2 and all(r["same_line"] for r in pairs)
    return {
        "status": (
            "affected" if differences else "no_line_discrepancy_at_returned_longitudes"
        ),
        "activations_checked": sum(map(len, chart["activations"].values())),
        "differences": differences,
        "coordinate_policy": "exact_binary_classification_coordinate_vs_integer_printed_arcseconds_half_open",
        "conditional_printed_line_effects": {
            "status": (
                "not_needed_no_affected_activation"
                if not differences
                else (
                    "inconsistent_printed_sun_earth_lines"
                    if len(pairs) == 2 and not paired
                    else (
                        "conditional_line_only_comparison"
                        if unambiguous
                        else "ambiguous_printed_line_membership"
                    )
                )
            ),
            "changed_fixing_records": changes,
            "sun_earth_pairs": pairs,
            "candidate_profile": candidate_profile,
            "candidate_profile_in_supported_twelve": (
                candidate_profile in VALID_PROFILES if candidate_profile else None
            ),
            "full_alternative_chart_computed": False,
            "color_tone_base_alternative": None,
        },
        "scope": "当前精确黄经对印刷线界；全体变更同时代入线固定，日地不同线时不造完整角色或交叉解释。印刷表未定义非等宽线下的Color/Tone/Base；不改主盘、不认证全部线义或连续时间精度。",
    }


def discrepancy_reading(impacts: dict[str, Any], names: dict[str, Any]) -> str:
    text = "本盘采用56′15″等分线界与2001版交叉名称；29.1／29.2的印刷冲突仍未取得出版方勘误。"
    if impacts["differences"]:
        labels = [
            f"{r['side']} {r['body']}：{r['gate']}.{r['implemented_uniform_line']}→印刷候选{r['printed_line_candidates']}"
            for r in impacts["differences"]
        ]
        text += "当前受影响激活为" + "；".join(labels) + "。"
        if (
            impacts["conditional_printed_line_effects"]["status"]
            == "inconsistent_printed_sun_earth_lines"
        ):
            text += "照搬印刷线界会使同侧日地不同线，不能据此生成一个有效的替代角色或完整解释。"
        text += "条件性线固定差异见同次source_consistency.activation_impacts；未生成替代Color/Tone/Base。"
    else:
        text += "当前激活未落入该印刷分歧区间，不能据此宣称原典整体一致。"
    if names["observed_labels"]:
        text += (
            "冻结官方样本对同四门及角度显示"
            + "／".join(r["observed_official_name"] for r in names["observed_labels"])
            + "；字面匹配与编号差异单列保留。"
        )
    else:
        text += "原19盘未观察到本盘四门及角度名称；新增样本另列，不补造别名。"
    return text
