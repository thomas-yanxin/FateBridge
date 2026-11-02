"""Source identifiers, line polarities and reproducible natal fixing evidence.

The catalogue contains factual labels/planet assignments, not reproduced line
readings. A fixing is a traditional polarity, never a quality or health score.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from fatebridge.core.human_design_additional_polarities import (
    evidence as additional_polarity_evidence,
)
from fatebridge.core.human_design_additional_polarities import (
    facts_for,
    triggered_basis,
)
from fatebridge.core.human_design_references import reference_data

FIXING_SOURCE = "https://jovianarchive.com/blogs/chart-interpretations-components/line-fixing-in-human-design-exaltation-detriment-and-juxtaposition"
NODE_SOURCE = "https://humandesignsystem.com/archive/newsletters/0402.pdf"
NODES = {"NorthNode", "SouthNode"}
SIDES = ("personality", "design")
BODY_NAMES = dict(
    zip(
        (
            "Sun",
            "Earth",
            "Moon",
            "NorthNode",
            "SouthNode",
            "Mercury",
            "Venus",
            "Mars",
            "Jupiter",
            "Saturn",
            "Uranus",
            "Neptune",
            "Pluto",
        ),
        (
            "太阳",
            "地球",
            "月亮",
            "北交点",
            "南交点",
            "水星",
            "金星",
            "火星",
            "木星",
            "土星",
            "天王星",
            "海王星",
            "冥王星",
        ),
    )
)


def fixing_reading(record: Dict[str, Any]) -> str:
    """Explain this activation's actual mechanism, without inventing line prose."""
    side = {"personality": "人格", "design": "设计"}[record["side"]]
    text = f"{side}{BODY_NAMES[record['body']]}位于{record['gate']}.{record['line']}。"
    kind = record["polarity_kind"]
    if kind == "no_planet_polarity":
        text += "2001原典该线未列极性星体，本次不补造固定极性。"
    else:
        poles = [
            label + "：" + BODY_NAMES[record[role + "_planet"]]
            for role, label in (("exaltation", "上升极性"), ("detriment", "下降极性"))
            if record[role + "_planet"] is not None
        ]
        text += "原典列出" + "；".join(poles) + "。"
        for basis in record.get("additional_polarity_basis", []):
            role = {"exaltation": "上升极性", "detriment": "下降极性"}[basis["role"]]
            text += f"该线正文另将{BODY_NAMES[basis['additional_planet']]}列入{role}（PDF第{basis['source_pdf_page_one_based']}页），本次触发包含这一附加依据。"
        if kind == "unitary":
            text += "这是原典单极性类别，须另查本盘是否实际触发。"
        state = record["fixing_state"]
        text += {
            "exaltation": "本盘触发上升极性。",
            "detriment": "本盘触发下降极性。",
            "juxtaposition": "本盘两极均被触发，保留juxtaposition；此处不是4/1角色的交叉角度。",
            "unfixed": "本命双侧未发现指定星体在同门或谐振门触发；不表示未来行运或与他人互动也不会触发。",
        }[state]
        for role, label in (("exaltation", "上升"), ("detriment", "下降")):
            for source in record["fixing_planets"][role]:
                relation = {
                    "same_line": "同门同线",
                    "same_gate_other_line": "同门其他线",
                    "harmonic_gate": "通道另一端的谐振门",
                }[source["relation"]]
                source_side = {"personality": "人格", "design": "设计"}[source["side"]]
                text += f"{label}依据为{source_side}{BODY_NAMES[source['body']]} {source['gate']}.{source['line']}（{relation}，{source['calculation_path']}）。"
    if record["recipient_kind"] == "node_activation":
        text += "交点位置可接受固定；交点本身不充当固定其他位置的星体。"
    return (
        text
        + "极性不表示吉凶、能力高低或现实事件结果；这里只解释固定机制，未提供该线完整原典线义。"
    )


def fixing_summary_reading(depth: Dict[str, Any]) -> str:
    summary = depth["fixing_summary"]
    counts = summary["fixing_state_counts"]
    labels = {
        "exaltation": "上升极性触发",
        "detriment": "下降极性触发",
        "juxtaposition": "两极同时触发",
        "unfixed": "本命未触发",
        "not_applicable_no_planet_polarity": "原典无极性星体",
    }
    parts = [f"{label}{counts.get(state, 0)}处" for state, label in labels.items()]
    return (
        f"本盘{summary['activation_count']}个位置逐项核对固定机制："
        + "，".join(parts)
        + f"。其中{summary['node_recipient_count']}个交点位置也接受核对，但交点不充当固定星体。"
        + "逐项说明见depth_evidence.line_fixings各项reading；原典单极性类别不等于本盘实际触发，完整384线线义尚未验收。"
    )


def depth_reference() -> Dict[str, Any]:
    return reference_data("rave-2001-depth.json")


def cross_identifier(personality_sun_gate: int, angle: str) -> Dict[str, Any]:
    row = depth_reference()["gates"][personality_sun_gate - 1]
    if row["gate"] != personality_sun_gate or angle not in row["cross_identifiers"]:
        raise ValueError("轮回交叉目录的门号或角度无效")
    return {
        "name": row["cross_identifiers"][angle],
        "name_status": "primary_2001_angle_identifier",
        "source_pdf_page_one_based": row["pdf_pages_one_based"][0],
        "source_url": depth_reference()["source"]["url"],
        "interpretation_scope": "原典名称索引；不把名称解释为事件预言、职业定命或医学含义。",
    }


def line_fixings(activations: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    reference = depth_reference()
    result = []
    side_items = [(side, activations[side]) for side in SIDES if side in activations]
    if len(side_items) != len(activations):
        raise ValueError("Unknown activation side")
    # JSON object order is not semantic. Recipient and donor *arrays* keep their
    # actual indices; only the two named sides have a fixed traversal order.
    for side, items in side_items:
        for index, activation in enumerate(items):
            gate, line = activation["gate"], activation["line"]
            row = reference["gates"][gate - 1]
            polarity = row["line_polarities"][line - 1]
            additional = facts_for(gate, line)
            harmonics = {
                b if a == gate else a
                for a, b in (c["gates"] for c in row["channel_identifiers"])
            }
            triggers: Dict[str, List[Dict[str, Any]]] = {
                "exaltation": [],
                "detriment": [],
            }
            # Martin Grassinger, June 1997 newsletter p2: nodes do not fix
            # other lines. This excludes donors, not node recipients, whose
            # visible official polarity markers are independently frozen.
            for role in triggers:
                planets = {polarity[role + "_planet"]} - {None}
                planets.update(
                    f["additional_planet"] for f in additional if f["role"] == role
                )
                if not planets:
                    continue
                for source_side, sources in side_items:
                    for source_index, source in enumerate(sources):
                        if source["body"] not in planets or source["body"] in NODES:
                            continue
                        if source["gate"] not in harmonics | {gate}:
                            continue
                        relation = (
                            "same_line"
                            if source["gate"] == gate and source["line"] == line
                            else (
                                "same_gate_other_line"
                                if source["gate"] == gate
                                else "harmonic_gate"
                            )
                        )
                        triggers[role].append(
                            {
                                "side": source_side,
                                "body": source["body"],
                                "gate": source["gate"],
                                "line": source["line"],
                                "relation": relation,
                                "calculation_path": f"activations.{source_side}.{source_index}",
                            }
                        )
            if polarity["polarity_kind"] == "no_planet_polarity":
                state = "not_applicable_no_planet_polarity"
            elif triggers["exaltation"] and triggers["detriment"]:
                state = "juxtaposition"
            elif triggers["exaltation"]:
                state = "exaltation"
            elif triggers["detriment"]:
                state = "detriment"
            else:
                state = "unfixed"
            if polarity["polarity_kind"] != "dual":
                status = (
                    "unitary_polarity"
                    if polarity["polarity_kind"] == "unitary"
                    else "no_planet_polarity_in_source"
                )
            else:
                status = state
            result.append(
                {
                    "side": side,
                    "body": activation["body"],
                    "gate": gate,
                    "line": line,
                    "calculation_path": f"activations.{side}.{index}",
                    "gate_name": row["name"],
                    "source_pdf_page_one_based": row["pdf_pages_one_based"][1],
                    **{key: value for key, value in polarity.items() if key != "line"},
                    "status": status,
                    "fixing_state": state,
                    "recipient_kind": (
                        "node_activation"
                        if activation["body"] in NODES
                        else "planet_activation"
                    ),
                    "fixing_planets": triggers,
                    "fixing_rule_id": "jovian_2026_same_gate_and_harmonic_natal_v2",
                    "scope": "本命双侧激活的固定依据；未加入他人或行运，极性不表示人的优劣。",
                }
            )
            basis = triggered_basis(additional, triggers)
            if basis:
                result[-1]["additional_polarity_basis"] = basis
            result[-1]["reading"] = fixing_reading(result[-1])
    return result


def depth_evidence(chart: Dict[str, Any]) -> Dict[str, Any]:
    reference = depth_reference()
    channels = []
    for actual in chart["bodygraph"]["channels"]:
        pairs = sorted(actual["gates"])
        row = reference["gates"][pairs[0] - 1]
        match = next(c for c in row["channel_identifiers"] if c["gates"] == pairs)
        channels.append(
            {
                "gates": pairs,
                "name": match["name"],
                "source_pdf_page_one_based": row["pdf_pages_one_based"][0],
            }
        )
    fixings = line_fixings(chart["activations"])
    return {
        "line_fixings": fixings,
        "additional_polarity_sources": additional_polarity_evidence(),
        "additional_polarity_summary": {
            "matched_recipient_count": sum(
                "additional_polarity_basis" in r for r in fixings
            ),
            "recipients": [
                {
                    **{
                        k: r[k]
                        for k in (
                            "side",
                            "body",
                            "gate",
                            "line",
                            "status",
                            "fixing_state",
                            "calculation_path",
                        )
                    },
                    "additional_polarity_basis": r["additional_polarity_basis"],
                    "additional_donors": [
                        t
                        for basis in r["additional_polarity_basis"]
                        for t in r["fixing_planets"][basis["role"]]
                        if t["body"] == basis["additional_planet"]
                    ],
                }
                for r in fixings
                if "additional_polarity_basis" in r
            ],
            "full_line_meanings_accepted": False,
            "scope": "仅汇总本盘实际使用两项正文附加星体的记录；原符号星体及全部触发仍见line_fixings。不是完整384线语义、原生真实性或现实效度验收。",
        },
        "fixing_summary": {
            "activation_count": len(fixings),
            "fixing_state_counts": dict(
                sorted(Counter(r["fixing_state"] for r in fixings).items())
            ),
            "source_polarity_kind_counts": dict(
                sorted(Counter(r["polarity_kind"] for r in fixings).items())
            ),
            "node_recipient_count": sum(
                r["recipient_kind"] == "node_activation" for r in fixings
            ),
            "complete_line_meanings_accepted": False,
        },
        "fixing_policy": {
            "rule_id": "jovian_2026_same_gate_and_harmonic_natal_v2",
            "node_donors_allowed": False,
            "node_recipients_assessed": True,
            "node_donor_exclusion_author": "Martin Grassinger",
            "node_donor_exclusion_pdf_page_one_based": 2,
            "source_polarity_kind_is_not_trigger_state": True,
            "scope": "仅本命双侧指定星体的同门或谐振门触发；保留所有触发位置。完整线义、行运及合盘不在本次固定机制解释范围。",
        },
        "channel_identifiers": channels,
        "source_url": reference["source"]["url"],
        "source_pdf_sha256": reference["source"]["pdf_sha256"],
        "fixing_rule_source": FIXING_SOURCE,
        "node_fixing_exclusion_source": NODE_SOURCE,
        "scope": "64门、36通道、192交叉名称和384线的极性星体事实索引；不包含原典全部线义。",
    }
