"""Replay the frozen v2 capacity hypothesis without changing production rules.

An exposed development improvement cannot satisfy the fresh-label adoption gate.
The candidate root must contain the exact numerical dependencies in the protocol.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_root_force_experiment_v2"
ORDER = ("year", "month", "day", "hour")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_json(path: Path) -> Any:
    if digest(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError(f"Frozen file changed: {path.name}")
    return json.loads(path.read_text())


def load_frozen() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    protocol = frozen_json(FIXTURE / "protocol.json")
    reference = frozen_json(FIXTURE / "reference.json")
    if reference["protocol_sha256"] != digest(FIXTURE / "protocol.json"):
        raise ValueError("Reference belongs to a different protocol")
    if protocol["candidate_source_sha256"] != digest(FIXTURE / "candidate.py.txt"):
        raise ValueError("Frozen candidate changed")
    for name, expected in reference["source_files"].items():
        if digest(FIXTURE / name) != expected:
            raise ValueError(f"Frozen source changed: {name}")
    development = frozen_json(
        ROOT / "docs/validation/bazi-strength-current-v4-replay.json"
    )
    for group in development["groups"].values():
        if digest(ROOT / group["source"]) != group["source_sha256"]:
            raise ValueError(f"Exposed development corpus changed: {group['source']}")
    return protocol, reference, development


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    known = [r for r in rows if r["expected_strength"] is not None]
    return {
        "complete_cases": len(rows),
        "adjudicated": len(known),
        "unknown": len(rows) - len(known),
        "baseline_matches": sum(r["baseline_matches"] is True for r in known),
        "candidate_matches": sum(r["candidate_matches"] is True for r in known),
        "changed_ids": [r["id"] for r in rows if r["observation"]["changed"]],
        "resolved_ids": [
            r["id"]
            for r in known
            if not r["baseline_matches"] and r["candidate_matches"]
        ],
        "regression_ids": [
            r["id"]
            for r in known
            if r["baseline_matches"] and not r["candidate_matches"]
        ],
        "candidate_mismatch_ids": [
            r["id"] for r in known if not r["candidate_matches"]
        ],
    }


def audit(candidate_root: Path) -> dict[str, Any]:
    protocol, reference, development = load_frozen()
    candidate_root = candidate_root.resolve()

    def dependency_hashes() -> dict[str, str]:
        return {
            p: digest(candidate_root / p) for p in protocol["candidate_dependencies"]
        }

    before = dependency_hashes()
    if before != protocol["candidate_dependencies"]:
        raise ValueError("Candidate numerical dependencies differ from the freeze")
    if "fatebridge.core.strength" in sys.modules:
        raise RuntimeError("Run in a fresh process before importing any candidate")
    sys.path.insert(0, str(candidate_root / "src"))
    namespace: dict[str, Any] = {}
    candidate = FIXTURE / "candidate.py.txt"
    exec(compile(candidate.read_text(), str(candidate), "exec"), namespace)
    # Assert the numerical modules came from the supplied copy, not the editable
    # installation's checkout or another task's simultaneously changing modules.
    for module in (
        "core.strength",
        "core.elements",
        "core.storage_movement",
        "core.classical_roots",
        "core.classical_stages",
        "utils.data",
    ):
        module_file = sys.modules["fatebridge." + module].__file__
        if module_file is None:
            raise RuntimeError(f"Candidate module has no source file: {module}")
        loaded = Path(module_file).resolve()
        expected = (
            candidate_root / "src/fatebridge" / (module.replace(".", "/") + ".py")
        )
        if loaded != expected:
            raise RuntimeError(f"Unexpected candidate module: {module}")

    def observe(case: dict[str, Any]) -> dict[str, Any]:
        values = case["pillars"]
        pillars = {p: tuple(v) for p, v in zip(ORDER, values)}
        actual = namespace["evaluate"](pillars)
        label = case["expected_strength"]
        return {
            "id": case["id"],
            "pillars": values,
            "expected_strength": label,
            "baseline_matches": actual["baseline_strength"] == label if label else None,
            "candidate_matches": actual["strength_level"] == label if label else None,
            "observation": actual,
        }

    groups = {}
    for name, group in development["groups"].items():
        rows = [observe(c) for c in group["observations"]]
        groups[name] = {
            "source": group["source"],
            "source_sha256": group["source_sha256"],
            "classification": "exposed development; not unseen validation",
            "summary": summarize(rows),
            "cases": rows,
        }
    chapter = []
    for case in reference["cases"]:
        row = observe(case)
        row["prior_exact_pillar_overlaps"] = case["prior_exact_pillar_overlaps"]
        row["unseen_input"] = case["unseen_input"]
        chapter.append(row)
    fresh = [r for r in chapter if r["unseen_input"]]
    fresh_summary = summarize(fresh)
    development_regressions = [
        i for group in groups.values() for i in group["summary"]["regression_ids"]
    ]
    gates = {
        "no_exposed_matching_label_regression": not development_regressions,
        "nonoverlap_adjudicated_branch_change": any(
            r["expected_strength"] is not None and r["observation"]["changed"]
            for r in fresh
        ),
        "nonoverlap_adjudicated_improvement": bool(fresh_summary["resolved_ids"]),
        "no_nonoverlap_adjudicated_regression": not fresh_summary["regression_ids"],
        "source_and_survival_adoption_review_completed": False,
    }
    after = dependency_hashes()
    if before != after:
        raise ValueError("Numerical dependency drift during comparison")
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_id": protocol["candidate_id"],
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "candidate_source_sha256": digest(candidate),
        "reference_sha256": digest(FIXTURE / "reference.json"),
        "candidate_root": str(candidate_root),
        "dependency_sha256_before": before,
        "dependency_sha256_after": after,
        "numerical_dependency_drift": [],
        "development_groups": groups,
        "chapter_summary": summarize(chapter),
        "chapter_cases": chapter,
        "nonoverlapping_chapter_summary": fresh_summary,
        "adoption_gates": gates,
        "adoptable": all(gates.values()),
        "production_default_changed": False,
        "classical_acceptance_passed": False,
        "scope": "A frozen development hypothesis and its first named-chapter comparison. The only explicit new-chapter label is an exposed overlap. Unknown labels stay unknown. Counts across exposed groups are not deduplicated or added into an accuracy score. Web transcription lacks a verified scan edition and independent expert collation. Neither gate mechanics nor development matches establish complete classical or real-world validity.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Audit outputs are immutable; choose a new output path")
    result = audit(args.candidate_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "development": {
                    name: group["summary"]
                    for name, group in result["development_groups"].items()
                },
                "chapter": result["chapter_summary"],
                "nonoverlap": result["nonoverlapping_chapter_summary"],
                "adoptable": result["adoptable"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["adoptable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
