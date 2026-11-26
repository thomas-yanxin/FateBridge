"""A same-target outside pair does not alone invalidate a complete formation.

The sources recognize formation membership, not numeric transfer coefficients.
An affiliate contributes no separate binding, transformation or physical root.
"""

from itertools import combinations
from typing import Any, Mapping, Sequence, TypeVar

from fatebridge.utils.data import BRANCH_CONFLICTS, Element

POLICY = "complete_same_target_affiliation_v1"
SOURCE = {
    "id": "complete_same_target_affiliation_primary_v1",
    "title": "子平真詮·論正官宣參國例；任注滴天髓闡微·方局、母象",
    "references": [
        {"pdf_pages": [24, 25, 66]},
        {"pdf_pages": [140, 141, 144, 145, 146, 424]},
    ],
    "scope": "完整局与同气外支相容的工程形式化；有直接六冲或仅两六合争用不适用。不是转化系数、从格、有效通关或现实预测的认证。",
}

Target = TypeVar("Target", str, Element)


def partition_affiliations(
    candidates: Sequence[tuple[str, tuple[str, ...], Target]],
    branches: Mapping[str, str],
) -> tuple[list[tuple[str, tuple[str, ...], Target]], list[dict[str, Any]]]:
    """Keep full seats unchanged; return outside pairs as zero-effect receipts.

    Candidates have already passed the ordinary completeness and adjacency
    checks. The direct-clash guard is evaluated before combination protection;
    this rule cannot manufacture protection to dismiss a real clash.
    """
    active: list[tuple[str, tuple[str, ...], Target]] = []
    affiliations: list[dict[str, Any]] = []
    full = [c for c in candidates if c[0] in {"三会", "三合"}]
    for candidate in candidates:
        kind, positions, target = candidate
        primary = None
        if kind == "六合":
            for formation in full:
                _, seats, element = formation
                if (
                    target != element
                    or not set(positions) & set(seats)
                    or set(positions) <= set(seats)
                ):
                    continue
                union = set(positions) | set(seats)
                if any(
                    BRANCH_CONFLICTS[branches[a]] == branches[b]
                    for a, b in combinations(union, 2)
                ):
                    continue
                primary = formation
                break
        if primary is None:
            active.append(candidate)
            continue
        primary_kind, seats, _ = primary
        target_text = target.value if isinstance(target, Element) else target
        affiliations.append(
            {
                "kind": kind,
                "positions": list(positions),
                "target": target_text,
                "status": "same_target_affiliation_only",
                "membership_policy": POLICY,
                "primary_formation": {
                    "kind": primary_kind,
                    "positions": list(seats),
                    "target": target_text,
                },
                "outside_positions": [p for p in positions if p not in seats],
                "additional_budget": 0.0,
                "calculation_effect": "none",
                "source_id": SOURCE["id"],
            }
        )
    return active, affiliations
