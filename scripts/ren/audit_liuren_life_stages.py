"""Audit literal stem anchors separately from cyclic rule expansions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/liuren_life_stages_v1"
IMPLEMENTATION = (
    "src/fatebridge/core/metaphysics/liureng_life_stages.py",
    "src/fatebridge/core/metaphysics/liureng.py",
    "src/fatebridge/core/metaphysics/ren_evidence.py",
    "src/fatebridge/core/output_liuren_life.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/services/metaphysics.py",
    "src/fatebridge/data/agent_examples.json",
    "scripts/ren/audit_liuren_life_stages.py",
)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "freeze.json").read_text())
    if {p.name for p in corpus.iterdir()} != set(manifest["files"]) | {"freeze.json"}:
        raise ValueError("Frozen life-stage inventory changed")
    for name, value in manifest["files"].items():
        if sha(corpus / name) != value:
            raise ValueError(f"Frozen life-stage source changed: {name}")
    result: dict[str, Any] = json.loads((corpus / "reference.json").read_text())
    return result


def audit() -> dict[str, Any]:
    ref = reference()
    before = {p: sha(ROOT / p) for p in IMPLEMENTATION}
    from fatebridge.core.metaphysics.liureng_life_stages import (
        build_life_stages,
        life_stage_cycle,
    )

    branches = "子丑寅卯辰巳午未申酉戌亥"
    literal = []
    expansions = []
    placements = []
    for item in ref["anchors"]:
        stem = item["stem"]
        actual = life_stage_cycle(stem)
        for key, stage in (("changsheng", "长生"), ("linguan", "临官"), ("mu", "墓")):
            branch = item[key]
            literal.append(
                dict(
                    stem=stem,
                    branch=branch,
                    expected=stage,
                    actual=actual[branch],
                    matched=actual[branch] == stage,
                )
            )
        # Independent walking expansion of the frozen direction/order clause;
        # these derived labels are not another 120 literal source examples.
        cursor = branches.index(item["changsheng"])
        for stage in ref["stage_order"]:
            branch = branches[cursor]
            expansions.append(
                dict(
                    stem=stem,
                    branch=branch,
                    expected=stage,
                    actual=actual[branch],
                    matched=actual[branch] == stage,
                )
            )
            cursor = (cursor + (1 if item["direction"] == "顺" else -1)) % 12
    for case in ref["placements"]:
        offset = (branches.index(case["sky"]) - branches.index(case["earth"])) % 12
        sky = {b: branches[(i + offset) % 12] for i, b in enumerate(branches)}
        board = build_life_stages(case["stem"], sky)
        match = next(p for p in board["placements"] if p["name"] == case["name"])
        placements.append(
            dict(
                **case,
                actual=match,
                matched=match["matched"]
                and match["sky_branch"] == case["sky"]
                and match["earth_branch"] == case["earth"],
            )
        )
    unchanged = before == {p: sha(ROOT / p) for p in IMPLEMENTATION}
    checks = literal + expansions + placements
    return {
        "audit_id": "liuren_life_stages_v1",
        "literal_anchor_sets": 10,
        "literal_anchor_checks": literal,
        "literal_anchor_match_count": sum(c["matched"] for c in literal),
        "derived_cycle_checks": expansions,
        "derived_cycle_match_count": sum(c["matched"] for c in expansions),
        "source_placement_checks": placements,
        "source_placement_match_count": sum(c["matched"] for c in placements),
        "new_real_world_outcomes": 0,
        "new_astronomical_observations": 0,
        "failures": [c for c in checks if not c["matched"]],
        "source_sha256": ref["source_sha256"],
        "reference_sha256": sha(CORPUS / "freeze.json"),
        "implementation_sha256": before,
        "implementation_unchanged_during_audit": unchanged,
        "selected_excerpt_checks_passed": unchanged
        and all(c["matched"] for c in checks),
        "classical_acceptance_passed": False,
        "goal_complete": False,
        "scope": ref["scope"],
        "limits": ref["limits"],
    }
