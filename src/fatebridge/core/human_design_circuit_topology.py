"""Source-listed circuit sets and actual all-channel completion.

The attributed scan is a factual witness, not an authenticated publisher master.
Its conflicting Defense motor heading is retained rather than used to define
centers. Connected graph components and complete source circuits are distinct.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Sequence

from fatebridge.core.human_design_references import (
    reference_data,
    reference_sha256,
)

NAMES = {
    "individual_knowing": "个体知晓回路",
    "individual_centering": "个体归心回路",
    "collective_understanding": "集体逻辑回路",
    "collective_sensing": "集体感知回路",
    "tribal_ego": "部落意志回路",
    "tribal_defense": "部落防御回路",
    "integration": "整合四通道拓扑",
}


def topology_reference() -> dict[str, Any]:
    return reference_data("circuit-pages-1996-reference.json")


def topology_reference_sha256() -> str:
    return reference_sha256("circuit-pages-1996-reference.json")


def topology_completion(channels: Sequence[dict[str, Any]]) -> dict[str, Any]:
    defined = {tuple(sorted(c["gates"])) for c in channels}
    result = []
    for source in topology_reference()["topologies"]:
        pairs = sorted(tuple(sorted(p)) for p in source["image_read_listed_gate_pairs"])
        actual = [p for p in pairs if p in defined]
        missing = [p for p in pairs if p not in defined]
        result.append(
            {
                "id": source["id"],
                "kind": (
                    "integration_channels"
                    if source["id"] == "integration"
                    else "circuit"
                ),
                "required_channel_ids": [f"{p[0]}-{p[1]}" for p in pairs],
                "defined_channel_ids": [f"{p[0]}-{p[1]}" for p in actual],
                "missing_channel_ids": [f"{p[0]}-{p[1]}" for p in missing],
                "all_channels_defined": not missing,
                "source_pdf_page_one_based": source["pdf_page_one_based"],
                "source_printed_page": source["printed_page"],
            }
        )
    return {
        "method_id": "human_design_source_topology_completion_v1",
        "topologies": result,
        "fully_defined_circuit_ids": [
            r["id"]
            for r in result
            if r["kind"] == "circuit" and r["all_channels_defined"]
        ],
        "integration_all_four_defined": next(
            r["all_channels_defined"] for r in result if r["id"] == "integration"
        ),
        "source_catalog_sha256": topology_reference_sha256(),
        "source_url": topology_reference()["source"]["url"],
        "source_author": topology_reference()["source"]["author"],
        "source_revision": topology_reference()["source"]["revision"],
        "source_kind": topology_reference()["source"]["source_kind"],
        "publisher_master_authenticity_certified": False,
        "scope": "六个回路与单列整合拓扑的通道集合核对；单一定义只要求中心群连通，不等于某回路全部通道齐全。缺项不指定需要寻找的人或行动，完整度不评价人的完整程度或现实能力。",
    }


def topology_reading(completion: dict[str, Any]) -> str:
    parts = []
    for row in completion["topologies"]:
        count, total = len(row["defined_channel_ids"]), len(row["required_channel_ids"])
        state = (
            "全部通道齐全"
            if row["all_channels_defined"]
            else ("未定义其中通道" if not count else "部分通道已定义")
        )
        parts.append(f"{NAMES[row['id']]}已定义{count}/{total}条，{state}")
    return (
        "；".join(parts)
        + "。这里逐项比较通道集合，单一定义表示中心群连通，不能替代全回路核对。整合四通道单列，其相邻的10-34和20-57分别归归心与知晓回路。"
        "来源为署名Ra、1996年修订的公开镜像扫描本，未认证出版方母版。防御页的运动中心标题与列出通道所对应中心存在未解决分歧；中心、类型和权威仍按本盘实际通道端点计算。"
    )


def audit_archival_channel_pages(
    channels: Sequence[tuple[int, int, str]],
    gate_rows: Sequence[dict[str, Any]],
    motors: Iterable[str],
) -> dict[str, Any]:
    reference = topology_reference()
    expected = {
        tuple(sorted(p)): row["id"]
        for row in reference["topologies"]
        for p in row["image_read_listed_gate_pairs"]
    }
    actual = {tuple(sorted((a, b))): circuit for a, b, circuit in channels}
    comparisons = [
        {
            "gates": list(p),
            "source_topology": circuit,
            "implemented_topology": actual.get(p),
            "matched": actual.get(p) == circuit,
        }
        for p, circuit in sorted(expected.items())
    ]
    centers = {
        r["gate"]: {"heart": "ego"}.get(
            r["center"].lower().replace(" ", "_"), r["center"].lower().replace(" ", "_")
        )
        for r in gate_rows
    }
    disagreement = reference["other_source_disagreements"][0]
    required = {g for pair in disagreement["listed_channel_gate_pairs"] for g in pair}
    missing_endpoint_facts = sorted(required - set(centers))
    induced = sorted({centers[g] for g in required if g in centers} & set(motors))
    return {
        "status": (
            "bounded_archival_assignments_match_with_other_unresolved_label"
            if expected == actual and len(expected) == 36 and not missing_endpoint_facts
            else "mismatch_or_incomplete"
        ),
        "channels_checked": len(expected),
        "channels_matched": sum(r["matched"] for r in comparisons),
        "source_pair_sets_equal": set(expected) == set(actual),
        "comparisons": comparisons,
        "ocr_digit_disagreements_retained": sum(
            len(t["ocr_disagreements"]) for t in reference["topologies"]
        ),
        "source_label_disagreements": [
            {
                **deepcopy(disagreement),
                "computed_endpoint_motor_centers": induced,
                "missing_endpoint_gate_facts": missing_endpoint_facts,
                "endpoint_observation_reproduced": induced
                == disagreement["endpoint_implied_motor_centers"],
            }
        ],
        "source_url": reference["source"]["url"],
        "source_author": reference["source"]["author"],
        "source_revision": reference["source"]["revision"],
        "source_kind": reference["source"]["source_kind"],
        "source_pdf_sha256": reference["source"]["pdf_sha256"],
        "source_catalog_sha256": topology_reference_sha256(),
        "publisher_master_authenticity_certified": False,
        "all_source_disagreements_resolved": False,
        "scope": "36项扫描页直接门对观察，另保留OCR与运动中心标签分歧；旧6项官方分类及30项端点推断仍各自保留，不把此镜像核对改称出版方母版认证。",
    }
