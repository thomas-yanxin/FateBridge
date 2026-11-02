"""Exact counterfactual bridge sets in the fixed 36-channel graph.

Cost is the number of distinct absent gates, not the sum of edge weights.
Uniform-cost search grows a connected region from one original component.
Every minimum bridge has a spanning tree rooted there, so its edges admit a
frontier-growth order. After every state at the first goal cost is processed,
all minimum gate sets have been enumerated. This is a graph result conditional
on the input gates and channel table, not a forecast of a person or transit.
"""

from __future__ import annotations

import heapq
from typing import Any

from fatebridge.core.human_design_mechanics import (
    CHANNELS,
    GATE_CENTER,
    RULESET_ID,
    RULESET_VERSION,
    _components,
)

SOURCE_URL = "https://jovianarchive.com/pages/understanding-definition-in-human-design"
METHOD_ID = "human_design_distinct_missing_gate_uniform_cost_v1"


def _gate_mask(gates: set[int]) -> int:
    return sum(1 << (gate - 1) for gate in gates)


def _gate_list(mask: int) -> list[int]:
    return [gate for gate in range(1, 65) if mask & (1 << (gate - 1))]


def definition_bridging(graph: dict[str, Any]) -> dict[str, Any]:
    """Connect all original components, allowing formerly undefined centers."""
    active = set(graph["activated_gates"])
    groups = graph["definition"]["components"]
    if groups != _components(active):
        raise ValueError("桥接输入的定义分组与实际完整通道不一致")
    names = sorted(set(GATE_CENTER.values()))
    center_bits = {name: 1 << index for index, name in enumerate(names)}
    edges = [
        (
            _gate_mask({a, b}),
            center_bits[GATE_CENTER[a]],
            center_bits[GATE_CENTER[b]],
        )
        for a, b, _ in CHANNELS
    ]
    adjacency: dict[int, list[tuple[int, int]]] = {
        bit: [] for bit in center_bits.values()
    }
    for gates, a, b in edges:
        adjacency[a].append((gates, b))
        adjacency[b].append((gates, a))
    active_mask = _gate_mask(active)
    required = sum(center_bits[c] for group in groups for c in group)
    start = sum(center_bits[c] for c in groups[0]) if groups else 0

    def reachable(mask: int) -> int:
        known = start
        pending = [bit for bit in center_bits.values() if bit & start]
        while pending:
            for gates, neighbor in adjacency[pending.pop()]:
                if not known & neighbor and mask & gates == gates:
                    known |= neighbor
                    pending.append(neighbor)
        return known

    def witness(added: list[int]) -> dict[str, Any]:
        augmented = active | set(added)
        new_groups = _components(augmented)
        merged = [
            [index for index, group in enumerate(groups) if set(group) <= set(new)]
            for new in new_groups
        ]
        return {
            "added_gates": added,
            "newly_completed_channel_ids": [
                f"{a}-{b}"
                for a, b, _ in CHANNELS
                if {a, b} <= augmented and not {a, b} <= active
            ],
            "result_components": new_groups,
            "merged_original_component_indices": [g for g in merged if len(g) > 1],
            "connects_all_original_components": any(
                len(g) == len(groups) for g in merged
            ),
        }

    local_merges = [
        witness([gate]) for gate in graph["definition"]["single_gate_bridges"]
    ]
    best: int | None = None
    solutions: list[list[int]] = []
    expanded = 0
    seen = {0}
    if len(groups) > 1:
        pending = [(0, 0)]
        while pending:
            count, added = heapq.heappop(pending)
            if best is not None and count > best:
                break
            expanded += 1
            region = reachable(active_mask | added)
            if region & required == required:
                best = count
                solutions.append(_gate_list(added))
                continue
            for gates, a, b in edges:
                if bool(region & a) == bool(region & b):
                    continue
                candidate = added | (gates & ~active_mask)
                if candidate in seen:
                    continue
                cost = candidate.bit_count()
                if best is not None and cost > best:
                    continue
                seen.add(candidate)
                heapq.heappush(pending, (cost, candidate))
        if best is None:
            raise ValueError("完整通道图中未找到连接原定义分组的桥接方案")
    solutions.sort()
    witnesses = [witness(added) for added in solutions]
    if any(not row["connects_all_original_components"] for row in witnesses):
        raise ValueError("最小桥接见证未连接全部原定义分组")
    return {
        "method_id": METHOD_ID,
        "status": (
            "computed_exact_graph_minimum"
            if best is not None
            else "not_applicable_no_split"
        ),
        "original_components": groups,
        "original_component_count": len(groups),
        "single_gate_merges": local_merges,
        "minimum_added_gate_count": best,
        "minimum_solution_count": len(witnesses),
        "minimum_solutions": witnesses,
        "minimum_solutions_preview": [
            {
                key: row[key]
                for key in (
                    "added_gates",
                    "newly_completed_channel_ids",
                    "connects_all_original_components",
                )
            }
            for row in witnesses[:3]
        ],
        "preview_is_truncated": len(witnesses) > 3,
        "all_minimum_solutions_enumerated": best is not None,
        "search": {
            "expanded_states": expanded,
            "distinct_generated_states": len(seen) if best is not None else 0,
            "cost": "distinct_added_gates",
        },
        "source_url": SOURCE_URL,
        "ruleset": {
            "id": RULESET_ID,
            "version": RULESET_VERSION,
            "author": "FateBridge graph algorithm; graph source: Ra Uru Hu / Jovian Archive, 2001",
            "source_url": SOURCE_URL,
            "graph_source_url": "https://www.myhumandesign.be/downloads/Rave-I%27Ching.pdf",
        },
        "source_scope": "官方页面支持定义分组及门/通道桥接概念；最少不同门数及全部等量最小方案是FateBridge图论分析，不是原典的事件或择伴规则。",
        "scope": "固定本命激活与36通道表下的假设连接；允许经原来未定义的中心连接，按不同新增门数求全部等量最小方案。原单门列表可仅合并部分分组。新增门不是本命激活、他人资料、未来行运或心理需要，不改变原类型、权威或定义。",
    }


def bridging_reading(report: dict[str, Any]) -> str:
    if report["status"] == "not_applicable_no_split":
        return f"本次有{report['original_component_count']}组已定义中心，未形成分离定义，桥接分析不适用。"
    return (
        f"本次有{report['original_component_count']}组分离定义；在固定通道表下，"
        f"使这些原有分组连通最少需假设增加{report['minimum_added_gate_count']}个不同门，"
        f"共有{report['minimum_solution_count']}组等量最小方案。"
        "单门局部合并不保证整盘连通；假设门不代表他人、未来行运或心理需要，也不改变原盘。"
    )
