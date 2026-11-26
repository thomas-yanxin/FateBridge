"""Activated gates, center definition and source-qualified hanging terminology.

Rules and source identities are fixed code constants, like the mechanics they
classify. No additional runtime JSON reader or post-import file hashing is used.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from fatebridge.core.human_design.human_design_mechanics import (
    CHANNELS,
    GATE_CENTER,
)
from fatebridge.utils.json_values import same_value as _same_value

METHOD = "human_design_gate_activation_context_v1"
SCOPE = "按实际激活门与完整通道区分定义中心内的active和未定义中心内的dormant；activated仍指本命已激活。悬挂门保留公开资料的宽窄口径。仅解释各自联合见证，不计算人际或行运定义，不认证心理、基因、中微子或现实因果；不是完整384线线义。"


def source_records() -> list[dict[str, str]]:
    return [
        {
            "id": "dictionary",
            "attribution": "Jovian Archive current public glossary; undated, not a2001manuscript",
            "captured_date": "2026-10-25",
        },
        {
            "id": "broad_hanging",
            "attribution": "Ryan Hanna,2025-11-12; author bio describes AI-assisted writing and analyst review; not Ra's original manuscript",
            "captured_date": "2026-10-25",
        },
        {
            "id": "narrow_hanging",
            "attribution": "Ryan Hanna,2026-09-28; author bio describes AI-assisted writing and analyst review; not Ra's original manuscript",
            "captured_date": "2026-10-25",
        },
    ]


def ruleset() -> dict[str, Any]:
    return {
        "id": METHOD,
        "version": "1.0.0",
        "author": "FateBridge implementation of source-qualified public definitions",
        "source_kind": "current_official_public_glossary_and_reviewed_articles",
        "source_records": source_records(),
        "scope": SCOPE,
    }


def classify_gate_context(
    personality: Iterable[int], design: Iterable[int]
) -> dict[str, Any]:
    p, d = set(personality), set(design)
    if any(type(g) is not int or g not in GATE_CENTER for g in p | d):
        raise ValueError("Gate context requires integer gate numbers1..64")
    active = p | d
    pairs = sorted({tuple(sorted((a, b))) for a, b, _ in CHANNELS})
    complete = {edge for edge in pairs if set(edge) <= active}
    linked = {g for edge in complete for g in edge}
    defined = {GATE_CENTER[g] for g in linked}
    unpaired = active - linked
    rows = []
    for gate in sorted(active):
        in_defined = GATE_CENTER[gate] in defined
        rows.append(
            {
                "gate": gate,
                "center": GATE_CENTER[gate],
                "center_status": "defined" if in_defined else "undefined",
                "expression": (
                    "active_in_defined_center"
                    if in_defined
                    else "dormant_in_undefined_center"
                ),
                "channel_completion": (
                    "in_completed_channel" if gate in linked else "unpaired"
                ),
                "source_sides": [
                    s
                    for s, gates in (("personality", p), ("design", d))
                    if gate in gates
                ],
                "completed_channel_pairs": [
                    list(e) for e in pairs if gate in e and e in complete
                ],
                "uncompleted_channel_pairs": [
                    list(e) for e in pairs if gate in e and e not in complete
                ],
            }
        )
    return {
        "activated_gates": sorted(active),
        "active_in_defined_centers": sorted(
            g for g in active if GATE_CENTER[g] in defined
        ),
        "dormant_in_undefined_centers": sorted(
            g for g in active if GATE_CENTER[g] not in defined
        ),
        "broad_unpaired_activated_gates": sorted(unpaired),
        "defined_center_hanging_gates": sorted(
            g for g in unpaired if GATE_CENTER[g] in defined
        ),
        "gates": rows,
    }


def _context(value: dict[str, Any], path: str) -> dict[str, Any]:
    sides = value["activations"]
    context = classify_gate_context(
        (a["gate"] for a in sides["personality"]), (a["gate"] for a in sides["design"])
    )
    graph = value.get("bodygraph", value)
    expected_pairs = sorted(
        {
            tuple(edge)
            for row in context["gates"]
            for edge in row["completed_channel_pairs"]
        }
    )
    actual_pairs = sorted({tuple(sorted(c["gates"])) for c in graph["channels"]})
    if not _same_value(actual_pairs, expected_pairs):
        raise ValueError("Gate context channels disagree with actual activations")
    prefix = path + "." if path else ""
    basis = [
        {"path": f"{prefix}activations.{side}.{i}.gate", "value": a["gate"]}
        for side in ("personality", "design")
        for i, a in enumerate(sides[side])
    ]
    channel_path = prefix + (
        "bodygraph.channels" if "bodygraph" in value else "channels"
    )
    basis.append({"path": channel_path, "value": graph["channels"]})
    return {
        "source_snapshot_path": path or "$",
        **context,
        "basis": basis,
    }


def gate_context_report(chart: dict[str, Any]) -> dict[str, Any]:
    nominal = _context(chart, "")
    witnesses = []
    excluded = {
        "interpretation",
        "rulesets",
        "rule_trace",
        "source_consistency",
        "depth_evidence",
        "gate_activation_context",
        "basis",
        "clock_evidence",
    }

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            if value.get("projection_format") == "gate_line_tone_personality_color_v2":
                witnesses.append(_context(value, path))
                return
            if "bodygraph" in value and "activations" in value:
                witnesses.append(_context(value, path))
            # JSON object order is not semantic; source arrays keep theirs.
            for key in sorted(value):
                if key not in excluded:
                    walk(value[key], f"{path}.{key}" if path else key)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, f"{path}.{i}")

    for key in (
        "node_convention_comparison",
        "node_backend_comparison",
        "ephemeris_backend_comparison",
        "time_sensitivity",
    ):
        if key in chart:
            walk(chart[key], key)
    return {
        "method_id": METHOD,
        "ruleset": ruleset(),
        "nominal": nominal,
        "witnesses": witnesses,
        "context_count": 1 + len(witnesses),
        "hanging_gate_terminology": {
            "existing_bodygraph_hanging_gates": "broad_unpaired_activated_gates",
            "broad_source": "broad_hanging",
            "defined_center_only_source": "narrow_hanging",
            "status": "both_public_usages_retained_no_silent_redefinition",
        },
        "scope": SCOPE,
    }


def context_reading(report: dict[str, Any]) -> dict[str, Any]:
    c = report["nominal"]

    def gates(key: str) -> str:
        return "、".join(map(str, c[key])) or "无"

    text = (
        f"本名义盘有{len(c['activated_gates'])}个本命激活门。定义中心内的active门为{gates('active_in_defined_centers')}；"
        f"未定义中心内的休眠激活门为{gates('dormant_in_undefined_centers')}。休眠仍属于本命已激活，不表示缺门、能力低或心理缺陷。"
        f"既有hanging_gates采用宽口径，列无任何完整通道的激活门{gates('broad_unpaired_activated_gates')}；"
        f"其中定义中心内的悬挂门为{gates('defined_center_hanging_gates')}。公开资料也使用只指后一组的窄口径，这里同时保留。"
        "这些类别由各自见证的通道和中心决定；未计算实际行运或他人连接，不从单门推断已定义通道。"
    )
    return {
        "text": text,
        "time_scope": "本段只解释名义盘；其他联合见证逐项见gate_activation_context.witnesses，不能把名义中心状态拼到另一TT或后端。",
        "basis": [
            {"path": "gate_activation_context.nominal." + key, "value": c[key]}
            for key in (
                "activated_gates",
                "active_in_defined_centers",
                "dormant_in_undefined_centers",
                "broad_unpaired_activated_gates",
                "defined_center_hanging_gates",
            )
        ],
    }


def add_gate_context_evidence(
    chart: dict[str, Any], evidence: dict[str, Any]
) -> dict[str, Any]:
    report = gate_context_report(chart)
    evidence["gate_activation_context"] = report
    evidence["interpretation"]["gate_activation_context"] = context_reading(report)
    evidence["rulesets"].append(ruleset())
    evidence["rule_trace"].append(
        {
            "rule_id": METHOD,
            "ruleset_id": METHOD,
            "inputs": {
                "activation_path": "activations",
                "channel_path": "bodygraph.channels",
            },
            "result": {
                "context_path": "gate_activation_context",
                "context_count": report["context_count"],
            },
        }
    )
    return evidence
