"""Profile/line structure from actual paired activations and public source facts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fatebridge.core.human_design_mechanics import RULESET_VERSION
from fatebridge.core.human_design_references import reference_data, reference_sha256

LINE_THEMES = {
    1: "调查与建立基础",
    2: "自然熟悉与独处空间",
    3: "经验试错与调整",
    4: "关系网络与影响",
    5: "实际解决问题与外界期待",
    6: "观察、整合与示范",
}
GEOMETRIES = {
    "right": {"label": "右角／个人历程", "source_term": "Personal Destiny"},
    "juxtaposition": {"label": "并列结构", "source_term": "Fixed Fate"},
    "left": {"label": "左角／人际交会", "source_term": "Transpersonal Karma"},
}
SCOPE = "人格/设计、上下卦、角色角度是体系内的不同分类，不是已测量的意识状态、能力、性格或命运结局；本命角色不随年龄改号。引用相对于本次结果或该联合快照。"


def profile_reference() -> dict[str, Any]:
    return reference_data("profile-2026-reference.json")


def profile_reference_sha256() -> str:
    return reference_sha256("profile-2026-reference.json")


def profile_evidence(chart: dict[str, Any]) -> dict[str, Any]:
    """Never invent a line, invert P/D order or infer geometry from trigram."""
    reference = profile_reference()
    sources = [s["url"] for s in reference["sources"].values()]
    base = {
        "profile": chart.get("profile"),
        "source_catalog_sha256": profile_reference_sha256(),
        "source_urls": sources,
        "scope": SCOPE,
        "ruleset": {
            "id": "human_design_profile_structure_v1",
            "version": RULESET_VERSION,
            "author": "FateBridge (structured evidence and paraphrases)",
            "source_author": reference["author"],
            "source_catalog_id": reference["method_id"],
        },
    }
    sides = []
    try:
        for side, polarity in (("personality", "conscious"), ("design", "unconscious")):
            rows = chart["activations"][side]
            pair = [(i, a) for i, a in enumerate(rows) if a["body"] in {"Sun", "Earth"}]
            if len(pair) != 2 or {a["body"] for _, a in pair} != {"Sun", "Earth"}:
                return {**base, "status": "incomplete_paired_line_basis"}
            values = [a["line"] for _, a in pair]
            if (
                any(type(v) is not int or not 1 <= v <= 6 for v in values)
                or values[0] != values[1]
            ):
                return {**base, "status": "inconsistent_paired_line_basis"}
            line = values[0]
            sides.append(
                {
                    "side": side,
                    "line": line,
                    "traditional_polarity": polarity,
                    "archetype": reference["line_archetypes"][str(line)],
                    "theme": LINE_THEMES[line],
                    "trigram": (
                        "lower"
                        if line in reference["trigram_lines"]["lower"]
                        else "upper"
                    ),
                    "basis": [
                        {"path": f"activations.{side}.{i}.line", "value": a["line"]}
                        for i, a in pair
                    ],
                }
            )
    except (KeyError, TypeError, AttributeError):
        return {**base, "status": "incomplete_paired_line_basis"}
    expected = f"{sides[0]['line']}/{sides[1]['line']}"
    match = next((r for r in reference["profiles"] if r["profile"] == expected), None)
    if match is None or chart.get("profile") != expected:
        return {**base, "status": "inconsistent_profile_combination"}
    angle = match["angle"]
    if (
        "incarnation_cross" in chart
        and chart["incarnation_cross"].get("angle") != angle
    ):
        return {**base, "status": "inconsistent_profile_cross_angle"}
    sixth = [r["side"] for r in sides if r["line"] == 6]
    return {
        **base,
        "status": "computed",
        "lines": sides,
        "geometry": {
            "angle": angle,
            **GEOMETRIES[angle],
            "source_url": reference["sources"]["profile"]["url"],
        },
        "sixth_line_process": {
            "applicable": bool(sixth),
            "affected_sides": sixth,
            "phase_assignment_status": (
                "not_assessed_in_natal_profile_evidence"
                if sixth
                else "not_applicable_no_sixth_profile_line"
            ),
            "current_phase": None,
            "computed_return_dates": None,
            "traditional_phase_order": (
                [
                    "experience_before_saturn_return",
                    "observation_between_saturn_and_kiron_returns",
                    "role_model_after_kiron_return",
                ]
                if sixth
                else []
            ),
            "source_cycle_markers": (
                deepcopy(reference["sixth_line_cycle_markers"]) if sixth else None
            ),
            "source_url": reference["sources"]["six_lines"]["url"] if sixth else None,
            "scope": "只有角色中的第六线触发本说明；普通星体或任一门的第六线不能冒充第六线角色。教学近似年龄不是已求出的行星回归时刻，不按30/50岁生日或当前年龄分配阶段，也不将6线改为3线。",
        },
    }


def profile_brief(evidence: dict[str, Any]) -> str:
    if evidence["status"] != "computed":
        return "本次人格/设计日地线号或角度依据不完整或不一致，不能补造角色主题。"
    p, d = evidence["lines"]
    return f"人生角色{evidence['profile']}：人格侧{p['line']}线为{p['theme']}，设计侧{d['line']}线为{d['theme']}；整体属{evidence['geometry']['label']}。这是传统角色分类，不是现实人格测验或事件概率。"


def profile_reading(evidence: dict[str, Any]) -> str:
    brief = profile_brief(evidence)
    if evidence["status"] != "computed":
        return brief
    p, d = evidence["lines"]
    trigrams = {"lower": "下卦", "upper": "上卦"}
    result = (
        brief
        + f"人格为传统conscious侧（{trigrams[p['trigram']]}），设计为传统unconscious侧（{trigrams[d['trigram']]}），不据此判断已测量的心理意识状态。上下卦与角色角度分别判定。"
    )
    if evidence["profile"] == "4/6":
        result += "4与6均属上卦，整体仍为右角，不能改标左角。"
    elif evidence["profile"] == "4/1":
        result += "4/1单独归并列结构；Fixed Fate为原有类别名，不表示现实结局不可改变。"
    if evidence["sixth_line_process"]["applicable"]:
        result += "含第六线的传统三阶段说明；本命角色证据不分配现阶段或改变角色数字。可选周期交会另见cycle_summary，出生起点及多次交会取舍未由原始资料裁定。"
    return result
