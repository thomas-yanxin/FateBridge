"""Source-qualified profile partition at the actual paired solar activations.

The ideal88degree point is exact rational geometry, not a substituted native
design Sun. Actual profile and any finite-root disagreement remain separate.
"""

import math
from fractions import Fraction
from typing import Any

METHOD = "human_design_profile_solar_arc_partition_v1"
SOURCE = "https://jovianarchive.com/pages/human-design-dictionary"
FOUNDATION = frozenset({"1/3", "2/4", "3/5", "4/6", "5/1", "6/2"})
TRANSITION = frozenset({"1/4", "2/5", "3/6", "4/1", "5/2", "6/3"})
SCOPE = "只解释本次名义盘人格／设计日地角色与精确88度的理想分区；实际设计太阳保留原生求根结果。术语限于所引公开条目，未裁定Resonances的跨条目用法，也未裁定29.1/29.2印刷界。角宽不代表人群比例、人格强弱或现实因果；未认证完整原典或天文精度。"


def source_facts() -> dict[str, Any]:
    return {
        "line_arcseconds": 3375,
        "foundation_arcseconds": 2925,
        "transition_arcseconds": 450,
        "solar_arc_degrees": 88,
        "foundation_profiles": sorted(FOUNDATION),
        "transition_profiles": sorted(TRANSITION),
        "source_wording_ambiguity": {
            "profile_foundation_term": "Resonances",
            "general_resonance_definition": "same numerical lines in different hexagrams",
            "resolved": False,
            "policy": "Retain both source contexts; no silent replacement with Dissonance or inference that Foundation Profile numbers are equal.",
        },
    }


def ruleset() -> dict[str, Any]:
    return {
        "id": METHOD,
        "version": "1.0.0",
        "author": "FateBridge exact geometry and source-qualified paraphrases",
        "source_kind": "current_official_public_glossary_not_complete_2001_text",
        "sources": {"profile_partition": SOURCE},
        "source_records": [
            {
                "url": SOURCE,
                "html_sha256": "06ca304cf81e32d635b8e9f9f7b24dfa36bb7ad7906e6c0e32d1b6aa524e1f3a",
                "captured_date": "2026-10-25",
                "sections": ["Profile Foundation", "Profile Transitions", "Resonance"],
                "attribution": "Jovian Archive public glossary; undated editorial source, not a publisher-authenticated full manuscript",
            }
        ],
        "scope": SCOPE,
    }


def _ratio(value: Fraction) -> list[str]:
    # Decimal strings survive JSON consumers whose integer type is binary64.
    # A near-zero supplied longitude can require a denominator above2**53.
    return [str(value.numerator), str(value.denominator)]


def classify_profile_solar_arc(personality_longitude: float) -> dict[str, Any]:
    """Classify the supplied binary64 coordinate without subtraction rounding."""
    from fatebridge.core.human_design_mechanics import _rational_activation

    if (
        isinstance(personality_longitude, bool)
        or not isinstance(personality_longitude, (int, float))
        or not math.isfinite(personality_longitude)
    ):
        raise ValueError("Profile partition needs a finite numeric longitude")
    p = Fraction(personality_longitude) % 360
    d = (p - 88) % 360
    p_row, d_row = _rational_activation(p), _rational_activation(d)
    offset = ((p - 302) % Fraction(15, 16)) * 3600
    return {
        "personality_gate": p_row["gate"],
        "personality_line": p_row["line"],
        "ideal_design_gate": d_row["gate"],
        "ideal_design_line": d_row["line"],
        "ideal_profile": f"{p_row['line']}/{d_row['line']}",
        "angular_category": "foundation" if offset < 2925 else "transition",
        "line_offset_arcseconds_ratio": _ratio(offset),
        "ideal_design_longitude_degrees_ratio": _ratio(d),
        "coordinate_scope": "exact_rational88degree_point_from_supplied_personality_binary64_not_native_design_sun",
        "physical_accuracy_certified": False,
    }


def profile_partition_report(chart: dict[str, Any]) -> dict[str, Any]:
    rows, basis = {}, []
    for side in ("personality", "design"):
        selected = [
            (i, a)
            for i, a in enumerate(chart["activations"][side])
            if a["body"] in {"Sun", "Earth"}
        ]
        if len(selected) != 2 or {a["body"] for _, a in selected} != {"Sun", "Earth"}:
            raise ValueError("Incomplete Sun/Earth role basis")
        by_body = {a["body"]: a for _, a in selected}
        if (
            any(
                type(a["line"]) is not int or not 1 <= a["line"] <= 6
                for _, a in selected
            )
            or by_body["Sun"]["line"] != by_body["Earth"]["line"]
        ):
            raise ValueError("Inconsistent Sun/Earth role lines")
        rows[side] = by_body["Sun"]
        for i, a in selected:
            for key in ("body", "longitude", "gate", "line"):
                basis.append({"path": f"activations.{side}.{i}.{key}", "value": a[key]})
    profile = f"{rows['personality']['line']}/{rows['design']['line']}"
    if chart["profile"] != profile or profile not in FOUNDATION | TRANSITION:
        raise ValueError("Actual paired profile mismatch")
    ideal = classify_profile_solar_arc(rows["personality"]["longitude"])
    from fatebridge.core.human_design_mechanics import longitude_activation

    for row in rows.values():
        classified = longitude_activation(row["longitude"])
        if any(row[k] != classified[k] for k in ("gate", "line")):
            raise ValueError("Solar role line differs from actual longitude")
    p, d = (Fraction(rows[s]["longitude"]) % 360 for s in ("personality", "design"))
    residual = (p - d - 88 + 180) % 360 - 180
    agrees = profile == ideal["ideal_profile"]
    return {
        "method_id": METHOD,
        "status": "computed",
        "actual_profile": profile,
        "actual_profile_category": (
            "foundation" if profile in FOUNDATION else "transition"
        ),
        "ideal_partition": ideal,
        "actual_profile_matches_ideal_partition": agrees,
        "comparison_status": (
            "same_role_in_observed_nominal_chart"
            if agrees
            else "observed_role_differs_from_exact_solar_arc_partition"
        ),
        "actual_solar_arc_residual_degrees_ratio": _ratio(residual),
        "source_facts": source_facts(),
        "basis": [{"path": "profile", "value": profile}, *basis],
        "ruleset": ruleset(),
        "scope": SCOPE,
    }


def context_reading(context: dict[str, Any]) -> dict[str, Any]:
    names = {"foundation": "基础区段", "transition": "过渡区段"}
    text = f"本次实际日地角色{context['actual_profile']}，在所引公开分类中属{names[context['actual_profile_category']]}。每线56分15秒，其中前48分45秒为基础区段，后7分30秒为过渡区段。"
    if context["actual_profile_matches_ideal_partition"]:
        text += "实际角色与由人格太阳精确回退88度得到的理想分区一致。"
    else:
        text += f"实际角色与理想88度分区的{context['ideal_partition']['ideal_profile']}不同；保留实际日地线号，分开记录数值求根与理想角度，不改写角色。"
    text += "本项角宽不换算成人群比例；词典Resonances的用法保留原上下文，未据此生成性格或命运结论。"
    return {
        "text": text,
        "time_scope": "本段只解释名义盘；其他时刻和后端须使用各自的完整太阳位置。",
        "basis": [
            {"path": "profile_partition_context." + k, "value": context[k]}
            for k in (
                "actual_profile",
                "actual_profile_category",
                "ideal_partition",
                "actual_profile_matches_ideal_partition",
                "comparison_status",
                "actual_solar_arc_residual_degrees_ratio",
                "source_facts",
            )
        ],
        "source_urls": [SOURCE],
    }


def add_profile_partition_evidence(
    chart: dict[str, Any], evidence: dict[str, Any]
) -> dict[str, Any]:
    context = profile_partition_report(chart)
    evidence["profile_partition_context"] = context
    evidence["rulesets"].append(ruleset())
    evidence["rule_trace"].append(
        {
            "rule_id": METHOD,
            "ruleset_id": METHOD,
            "inputs": {"solar_roles_path": "activations", "profile_path": "profile"},
            "result": {
                "actual_profile": context["actual_profile"],
                "actual_profile_category": context["actual_profile_category"],
                "actual_profile_matches_ideal_partition": context[
                    "actual_profile_matches_ideal_partition"
                ],
            },
            "source_url": SOURCE,
        }
    )
    evidence["interpretation"]["profile_partition_context"] = context_reading(context)
    evidence["interpretation"]["basis"].append("profile_partition_context")
    return evidence
