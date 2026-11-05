"""Audit collated unresolved clauses without promoting hypotheses to truth."""

from __future__ import annotations

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/jinkou_definition_witnesses_v1"
WATCH = (
    "src/fatebridge/core/metaphysics/jinkou_definitions.py",
    "src/fatebridge/core/metaphysics/jinkou.py",
    "src/fatebridge/core/metaphysics/jinkou_stems.py",
    "src/fatebridge/core/metaphysics/common.py",
    "src/fatebridge/core/metaphysics/ren_evidence.py",
    "src/fatebridge/core/output_jinkou_definitions.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/core/output_ren_anchors.py",
    "src/fatebridge/services/metaphysics.py",
    "src/fatebridge/data/jinkou_definition_witnesses.json",
    "src/fatebridge/data/agent_examples.json",
    "scripts/ren/audit_jinkou_definitions.py",
    "uv.lock",
    "pyproject.toml",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> tuple[dict[str, Any], dict[str, Any]]:
    frozen = json.loads((corpus / "freeze.json").read_text())
    names = {
        "readings.json",
        "facts.json",
        "cnts-pages.pdf",
        "waseda-page-index.html",
        "waseda-057.jpg",
        "waseda-058.jpg",
        "waseda-059.jpg",
    }
    if set(frozen["files"]) != names or {p.name for p in corpus.iterdir()} != names | {
        "freeze.json"
    }:
        raise ValueError("Frozen definition witness inventory changed")
    for name in names:
        if sha(corpus / name) != frozen["files"][name]:
            raise ValueError("Frozen definition witness labels changed")
    readings = json.loads((corpus / "readings.json").read_text())
    facts = json.loads((corpus / "facts.json").read_text())
    if [e["pattern_id"] for e in readings["entries"]] != [
        "P52",
        "P53",
        "P56",
        "P57",
        "P58",
        "P59",
    ]:
        raise ValueError("All six unresolved definitions are required")
    return readings, facts


def literal_rows(
    elements: list[str], contents: list[str] | None = None
) -> list[dict[str, Any]]:
    # Literal P59 coordinates; for the Cartesian phase experiment, only the
    # four supplied elements vary. These are not historical reconstructions.
    values = contents or ["辛", "未", "巳", "酉"]
    return [
        dict(
            label=label,
            content=c,
            element=e,
            intrinsic_ganzhi="己未" if i == 1 else None,
        )
        for i, (label, c, e) in enumerate(
            zip(("人元", "贵神", "将神", "地分"), values, elements)
        )
    ]


def audit() -> dict[str, Any]:
    readings, facts = reference()
    before = {p: sha(ROOT / p) for p in WATCH}
    from fatebridge.core.metaphysics.jinkou_definitions import definition_evidence

    base = definition_evidence(
        day_stem="戊",
        hour_branch="辰",
        is_diurnal=True,
        rows=literal_rows(["金", "土", "火", "金"]),
    )
    # Preserve every original frozen field. Newly added full-chapter metadata
    # has its own frozen corpus and audit; it must not rewrite these readings.
    legacy_witnesses = [
        {key: actual[key] for key in original}
        for actual, original in zip(
            base["witnesses"], readings["witnesses"], strict=True
        )
    ]
    if (
        base["entries"] != readings["entries"]
        or legacy_witnesses != readings["witnesses"]
    ):
        raise ValueError(
            "Packaged source readings differ from frozen visual transcription"
        )
    routes = {r["route_id"]: r["stem"] for r in base["ding_routes"]}
    route_match = routes == facts["ding_example"]["routes"]
    night = definition_evidence(
        day_stem="甲",
        hour_branch="寅",
        is_diurnal=False,
        rows=literal_rows(["火", "水", "土", "水"], ["丙", "子", "戌", "子"]),
    )
    pair = night["day_night_candidates"]
    night_match = (
        pair[0]["start_branch"],
        pair[1]["start_branch"],
        pair[0]["god_name"],
        pair[1]["god_name"],
    ) == tuple(
        facts["day_night_example"][k]
        for k in ("day_start", "night_start", "day_god", "night_god")
    )
    counts = {
        pid: dict.fromkeys(facts["hypothesis_required_counts"], 0)
        for pid in ("P52", "P53")
    }
    predicate_leaks = 0
    for elements in product("木火土金水", repeat=4):
        value = definition_evidence(
            day_stem="戊",
            hour_branch="辰",
            is_diurnal=True,
            rows=literal_rows(list(elements)),
        )
        for h in value["cross_generation_hypotheses"]:
            counts[h["pattern_id"]][h["hypothesis_id"]] += h["all_conditions_met"]
            predicate_leaks += h["adjudicated_predicate"] is not None
    count_match = all(c == facts["hypothesis_required_counts"] for c in counts.values())
    after = {p: sha(ROOT / p) for p in WATCH}
    if before != after:
        raise ValueError("Definition implementation changed during audit")
    return dict(
        reference_sha256=sha(CORPUS / "freeze.json"),
        implementation_sha256=after,
        witness_count=2,
        selected_pattern_notes=6,
        reading_annotations=12,
        distinct_selected_text_entries=11,
        new_historical_cases=0,
        original_predicates_adjudicated=0,
        p59_conditional_route_anchor_matched=route_match,
        p56_conditional_day_night_anchor_matched=night_match,
        cartesian_phase_denominator=facts["cartesian_phase_denominator"],
        hypothesis_counts=counts,
        hypothesis_counts_matched=count_match,
        hypotheses_promoted_to_predicates=predicate_leaks,
        engineering_checks_passed=route_match
        and night_match
        and count_match
        and predicate_leaks == 0,
        classical_acceptance_passed=False,
        goal_complete=False,
        model_invocations=0,
        new_empirical_outcomes=0,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit()
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text)
    return 0 if result["engineering_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
