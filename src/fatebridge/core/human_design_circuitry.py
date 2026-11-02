"""Completed-channel circuitry with separate Integration topology and evidence."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Sequence

from fatebridge.core.human_design_circuit_topology import topology_completion
from fatebridge.core.human_design_references import reference_data, reference_sha256

INTEGRATION_PAIRS = {(10, 20), (10, 57), (20, 34), (34, 57)}
INTEGRATION_GATES = {10, 20, 34, 57}
CIRCUIT_GROUP = {
    "individual_knowing": "individual",
    "individual_centering": "individual",
    "collective_understanding": "collective",
    "collective_sensing": "collective",
    "tribal_ego": "tribal",
    "tribal_defense": "tribal",
    "integration": "individual",
}
# Short source-attributed themes, not copied line/channel readings or traits.
CIRCUIT_THEME = {
    "individual_knowing": "个体回路的独特领会与表达，以赋能为主题。",
    "individual_centering": "个体回路的自我方向与实践，以赋能为主题。",
    "collective_understanding": "集体逻辑回路强调检验模式，以分享为主题。",
    "collective_sensing": "集体感知回路强调经验与回顾，以分享为主题。",
    "tribal_ego": "部落意志回路涉及交换、承诺与资源，以支持为主题。",
    "tribal_defense": "部落防御回路涉及延续与照顾，以支持为主题。",
    "integration": "整合四通道单列，主题为当下的自我赋能与自我保存。",
}


def circuit_reference() -> dict[str, Any]:
    return reference_data("circuitry-2026-reference.json")


def circuit_group_reference() -> dict[str, Any]:
    return reference_data("circuit-group-2026-reference.json")


def circuit_group_reference_sha256() -> str:
    return reference_sha256("circuit-group-2026-reference.json")


def circuitry_summary(
    channels: Sequence[dict[str, Any]], active_gates: Iterable[int]
) -> dict[str, Any]:
    counts = Counter(channel["circuit"] for channel in channels)
    unknown = set(counts) - set(CIRCUIT_GROUP)
    if unknown:
        raise ValueError("未支持的人类图通道回路分类")
    circuits = [
        {
            "id": circuit,
            "group": CIRCUIT_GROUP[circuit],
            "channel_ids": [ch["id"] for ch in channels if ch["circuit"] == circuit],
            "channel_count": counts[circuit],
            "meaning": CIRCUIT_THEME[circuit],
        }
        for circuit in sorted(counts)
    ]
    integration = [
        ch["id"] for ch in channels if tuple(sorted(ch["gates"])) in INTEGRATION_PAIRS
    ]
    adjacent = [
        ch["id"]
        for ch in channels
        if tuple(sorted(ch["gates"])) in {(10, 34), (20, 57)}
    ]
    return {
        "topology_completion": topology_completion(channels),
        "defined_channel_count": len(channels),
        "circuits": circuits,
        "group_channel_counts": {
            group: sum(counts[c] for c, g in CIRCUIT_GROUP.items() if g == group)
            for group in ("individual", "collective", "tribal")
        },
        "group_membership": {
            "method_id": circuit_group_reference()["method_id"],
            "source_url": circuit_group_reference()["sources"]["dictionary"]["url"],
            "source_catalog_sha256": circuit_group_reference_sha256(),
            "integration_group": "individual",
            "integration_is_separately_reported_subset": True,
            "scope": "整合四通道属于个体回路群，同时保留单独拓扑。三群计数构成完整通道的互斥划分；整合小计已含在individual中，不能再次相加。",
        },
        "integration": {
            "activated_gates": sorted(set(active_gates) & INTEGRATION_GATES),
            "completed_channel_ids": integration,
            "all_four_channels_complete": len(integration) == 4,
            "adjacent_individual_channel_ids": adjacent,
        },
        "source_url": circuit_reference()["group_source"]["url"],
        "integration_source_url": circuit_reference()["source"]["url"],
        "scope": "只统计完整定义通道；三大回路群计数包含整合的个体归属，另列整合子集。数量不是主导人格、能力强弱、概率或现实预测。",
    }


def audit_circuit_groups(channels: Sequence[tuple[int, int, str]]) -> dict[str, Any]:
    """Check implementation membership against independently captured facts."""
    reference = circuit_group_reference()
    memberships = [
        (circuit, group)
        for group, circuits in reference["groups"].items()
        for circuit in circuits
    ]
    expected = dict(memberships)
    complete = len(expected) == len(memberships) == 7
    rows = [
        {
            "circuit": circuit,
            "source_group": group,
            "implemented_group": CIRCUIT_GROUP.get(circuit),
            "matched": CIRCUIT_GROUP.get(circuit) == group,
        }
        for circuit, group in memberships
    ]
    represented = {circuit for _, _, circuit in channels}
    all_supported = set(CIRCUIT_GROUP) == set(expected) == represented
    counts = Counter(CIRCUIT_GROUP.get(circuit) for _, _, circuit in channels)
    partitioned = None not in counts and sum(
        counts[group] for group in reference["groups"]
    ) == len(channels)
    passed = (
        complete and all_supported and partitioned and all(r["matched"] for r in rows)
    )
    return {
        "status": (
            "bounded_public_group_membership_match"
            if passed
            else "mismatch_or_incomplete"
        ),
        "memberships_checked": len(rows),
        "memberships_matched": sum(r["matched"] for r in rows),
        "memberships": rows,
        "all_channel_group_counts": {
            group: counts[group] for group in reference["groups"]
        },
        "group_counts_partition_complete_channels": partitioned,
        "source_catalog_sha256": circuit_group_reference_sha256(),
        "source_url": reference["sources"]["dictionary"]["url"],
        "scope": "只核对回路至回路群归属。36通道的群计数以当前通道分类为条件；其中30条回路分类仍是两端门标签推断，不升级为独立通道原页认证。",
    }


def audit_channel_circuits(
    channels: Sequence[tuple[int, int, str]], gate_rows: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """Keep six direct classifications separate from endpoint-label inference."""
    direct = {
        tuple(row["gates"]): row["circuit"]
        for row in circuit_reference()["coupled_channels"]
    }
    rows = {row["gate"]: row for row in gate_rows}
    label_map = {
        "Knowing": "individual_knowing",
        "Centering": "individual_centering",
        "Understanding": "collective_understanding",
        "Sensing": "collective_sensing",
        "Ego": "tribal_ego",
        "Defence": "tribal_defense",
    }
    expected_pairs = {tuple(pair) for row in gate_rows for pair in row["channels"]}
    discrepancies = []
    direct_checked = inferred_checked = matched = 0
    for a, b, actual in channels:
        pair = tuple(sorted((a, b)))
        if pair in direct:
            expected = direct[pair]
            kind = "explicit_official_channel_classification"
            direct_checked += 1
        else:
            first = rows.get(a, {}).get("gate_circuit_label")
            second = rows.get(b, {}).get("gate_circuit_label")
            expected = (
                label_map.get(first)
                if isinstance(first, str) and first == second
                else None
            )
            kind = "inferred_from_matching_2001_endpoint_gate_labels"
            inferred_checked += 1
        if expected == actual:
            matched += 1
        else:
            discrepancies.append(
                {
                    "gates": list(pair),
                    "implemented": actual,
                    "source_expected": expected,
                    "evidence_kind": kind,
                }
            )
    pair_sets_equal = {tuple(sorted((a, b))) for a, b, _ in channels} == expected_pairs
    return {
        "status": (
            "bounded_public_source_match"
            if not discrepancies
            and pair_sets_equal
            and direct_checked == 6
            and inferred_checked == 30
            else "mismatch_or_incomplete"
        ),
        "channels_checked": len(channels),
        "channels_matched": matched,
        "direct_classifications_checked": direct_checked,
        "endpoint_inferences_checked": inferred_checked,
        "channel_pair_sets_equal": pair_sets_equal,
        "discrepancies": discrepancies,
        "direct_source_url": circuit_reference()["source"]["url"],
        "direct_source_sha256": circuit_reference()["source"]["download_sha256"],
        "scope": "6条由官方文章直接列明；其余30条仅以原典两端门标签作一致性推断，不能冒称36条全部获得独立通道分类原页复核。",
    }
