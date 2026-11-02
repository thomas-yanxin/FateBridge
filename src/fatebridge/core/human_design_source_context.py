"""Observe source-named graph relations without deciding their worldly effects."""

from __future__ import annotations

from collections import deque
from copy import deepcopy

from fatebridge.core.human_design_line_reading import EMPHASIS
from fatebridge.core.human_design_mechanics import CHANNELS, GATE_CENTER


def _graph(chart: dict) -> tuple[list[dict], list[dict]]:
    activations = [
        {
            "path": f"activations.{side}.{i}",
            "body": a["body"],
            "gate": a["gate"],
            "line": a["line"],
        }
        for side in ("personality", "design")
        for i, a in enumerate(chart["activations"][side])
    ]
    active = {a["gate"] for a in activations}
    expected = {frozenset((a, b)) for a, b, _ in CHANNELS if {a, b} <= active}
    channels = chart["bodygraph"]["channels"]
    if (
        {frozenset(c["gates"]) for c in channels} != expected
        or len(channels) != len(expected)
        or any(c["centers"] != [GATE_CENTER[g] for g in c["gates"]] for c in channels)
    ):
        raise ValueError("Source context channel and activation witnesses disagree")
    return activations, channels


def _direct(gates: list[int], activations: list[dict], channels: list[dict]) -> dict:
    if len(gates) != 2 or sorted(gates) not in [sorted((a, b)) for a, b, _ in CHANNELS]:
        raise ValueError("Unsupported source-named channel")
    witnesses = [
        {"path": f"bodygraph.channels.{i}", "value": deepcopy(c)}
        for i, c in enumerate(channels)
        if set(c["gates"]) == set(gates)
    ]
    return {
        "model_id": "direct_named_channel",
        "channel_gates": list(gates),
        "observed_in_this_chart": bool(witnesses),
        "channel_witnesses": witnesses,
        "gate_activation_witnesses": [
            deepcopy(a) for a in activations if a["gate"] in gates
        ],
    }


def _root_path(channels: list[dict]) -> dict:
    # Use actual complete-channel edges. A separately defined Root is insufficient.
    queue: deque[tuple[str, list[int]]] = deque([("sacral", [])])
    visited = {"sacral"}
    path = None
    while queue:
        center, edges = queue.popleft()
        if center == "root":
            path = edges
            break
        for i, channel in enumerate(channels):
            if center not in channel["centers"]:
                continue
            other = next(c for c in channel["centers"] if c != center)
            if other not in visited:
                visited.add(other)
                queue.append((other, [*edges, i]))
    return {
        "model_id": "sacral_root_connected_component",
        "centers": ["sacral", "root"],
        "observed_in_this_chart": path is not None,
        "channel_witnesses": [
            {"path": f"bodygraph.channels.{i}", "value": deepcopy(channels[i])}
            for i in path or []
        ],
        "all_complete_channel_gates": [list(c["gates"]) for c in channels],
    }


def bind_source_context(annotation: dict, chart: dict, fixing: dict) -> dict:
    """Private pure binding; the service verifies the complete original first."""
    key = f"{fixing['gate']}.{fixing['line']}"
    if key != annotation["key"]:
        raise ValueError("Wrong source-context reference key")
    activations, channels = _graph(chart)
    models = annotation["observation_models"]
    if models not in (
        ["direct_named_channel"],
        ["direct_named_channel", "sacral_root_connected_component"],
    ):
        raise ValueError("Unsupported source observation models")
    observations = [_direct(annotation["named_channel_gates"], activations, channels)]
    if "sacral_root_connected_component" in models:
        observations.append(_root_path(channels))
    role = annotation["source_role"]
    if role not in ("exaltation", "line_intro"):
        raise ValueError("Unsupported source clause role")
    emphasized = (
        role in EMPHASIS[fixing["fixing_state"]] if role == "exaltation" else None
    )
    result = {
        "source_annotation": deepcopy(annotation),
        "observation_scope": "this_retained_complete_natal_chart_context_only",
        "observations": observations,
        "selected_source_interpretation": None,
        "source_applicability_satisfied": None,
        "source_interpretation_resolved": False,
        "actual_fixing_state": fixing["fixing_state"],
        "fixing_emphasizes_clause_polarity": emphasized,
        "scope_is_named_clause_only": True,
        "world_qualifiers_assessed": False,
        "biological_effect_assessed": False,
        "composite_or_transit_context_assessed": False,
        "source_permanence_inferred": False,
        "converse_inferred": False,
        "outcome_guaranteed": False,
        "full_line_semantics_accepted": False,
    }
    if key == "42.1":
        text = (
            "原文上升段的‘特别是在’为侧重措辞，不是必要或充分条件。"
            f"此上下文直接42–53完整通道={observations[0]['observed_in_this_chart']}，"
            f"骶骨至根部连通={observations[1]['observed_in_this_chart']}；"
            "两种观察并列，原典具体拓扑口径未解决，资源有余也未核验。"
        )
    else:
        label = "引导语" if role == "line_intro" else "上升段限定句"
        text = f"原文{label}涉及{'–'.join(map(str, annotation['named_channel_gates']))}连接；" + (
            "此上下文观察到完整通道。"
            if observations[0]["observed_in_this_chart"]
            else "此上下文未观察到完整通道，不反推现实效果不存在。"
        )
        if key == "6.3":
            text += "该句不专属于上升极性；生物结果未评估，不据盘图推断生育结果。"
        if key == "7.2":
            text += "被选择与社会影响未评估。"
        if key == "12.6":
            text += "社会形式改变、当前情绪清晰度及行动时机未评估。"
        if annotation["source_explicitly_says_permanent"] is False:
            text += "该句未明说永久性；本次只观察此盘，不扩展为永久性断言。"
    result["reading"] = (
        text + "结构观察不改变实际固定状态，不保证现实结果；完整爻义尚未验收。"
    )
    return result
