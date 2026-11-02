"""Replay a frozen principal-only passage hypothesis on a predeclared chapter."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_root_force_experiment_v4"
ORDER = ("year", "month", "day", "hour")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_json(path: Path) -> Any:
    if digest(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError(f"Frozen file changed: {path}")
    return json.loads(path.read_text())


def load_frozen() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    protocol = frozen_json(FIXTURE / "protocol.json")
    reference = frozen_json(FIXTURE / "reference.json")
    if reference["protocol_sha256"] != digest(FIXTURE / "protocol.json"):
        raise ValueError("Reference belongs to another protocol")
    if digest(FIXTURE / "candidate.py.txt") != protocol["candidate_sha256"]:
        raise ValueError("Frozen candidate changed")
    for name, expected in {
        **protocol["candidate_files"],
        **reference["source"]["source_files"],
    }.items():
        if digest(FIXTURE / name) != expected:
            raise ValueError(f"Frozen candidate dependency or source changed: {name}")
    development = frozen_json(
        ROOT / "docs/validation/bazi-strength-current-v4-replay.json"
    )
    for group in development["groups"].values():
        if digest(ROOT / group["source"]) != group["source_sha256"]:
            raise ValueError(f"Exposed source changed: {group['source']}")
    for version in (2, 3):
        source = (
            ROOT
            / f"tests/fixtures/bazi_root_force_experiment_v{version}/reference.json"
        )
        previous = frozen_json(source)
        files = previous.get("source", {}).get(
            "source_files", previous.get("source_files", {})
        )
        for name, expected in files.items():
            if digest(source.parent / name) != expected:
                raise ValueError(
                    f"Previous exposed source changed: {source.parent / name}"
                )
        development["groups"][f"previous_v{version}_chapter"] = {
            "source": str(source.relative_to(ROOT)),
            "source_sha256": digest(source),
            "observations": previous["cases"],
        }
    return protocol, reference, development


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    known = [r for r in rows if r["expected_strength"] is not None]
    return {
        "complete_cases": len(rows),
        "adjudicated": len(known),
        "unknown": len(rows) - len(known),
        "baseline_matches": sum(r["baseline_matches"] is True for r in known),
        "previous_v3_matches": sum(r["previous_v3_matches"] is True for r in known),
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
        "v3_regression_ids": [
            r["id"]
            for r in known
            if r["previous_v3_matches"] and not r["candidate_matches"]
        ],
        "new_operator_resolved_ids": [
            r["id"]
            for r in known
            if not r["previous_v3_matches"]
            and r["candidate_matches"]
            and r["observation"]["passage_relief_pairs"]
        ],
        "candidate_mismatch_ids": [
            r["id"] for r in known if not r["candidate_matches"]
        ],
    }


def audit(candidate_root: Path) -> dict[str, Any]:
    protocol, reference, development = load_frozen()
    candidate_root = candidate_root.resolve()
    before = {p: digest(candidate_root / p) for p in protocol["candidate_dependencies"]}
    if before != protocol["candidate_dependencies"]:
        raise ValueError("Candidate numerical dependencies differ from the freeze")
    if any(n.startswith("fatebridge") for n in sys.modules):
        raise RuntimeError("Run before importing FateBridge in a fresh process")
    sys.path.insert(0, str(candidate_root / "src"))
    path = FIXTURE / "candidate.py.txt"
    namespace: dict[str, Any] = {
        "__name__": "_fatebridge_frozen_v4_candidate",
        "__file__": str(path),
    }
    exec(compile(path.read_text(), str(path), "exec"), namespace)
    for name in (
        "core.strength",
        "core.elements",
        "core.complete_bureaus",
        "core.storage_movement",
        "core.classical_roots",
        "core.classical_stages",
        "core.classical_passage",
        "utils.data",
    ):
        module = sys.modules["fatebridge." + name]
        expected = candidate_root / "src/fatebridge" / (name.replace(".", "/") + ".py")
        if module.__file__ is None or Path(module.__file__).resolve() != expected:
            raise RuntimeError(f"Wrong module origin: {name}")
    from fatebridge.utils.data import iter_pillar_gods

    def observe(case: dict[str, Any]) -> dict[str, Any]:
        pillars = {n: tuple(v) for n, v in zip(ORDER, case["pillars"])}
        actual = namespace["evaluate"](pillars)
        expected = case["expected_strength"]
        row = {
            "id": case["id"],
            "pillars": case["pillars"],
            "expected_strength": expected,
            "baseline_matches": (
                actual["baseline_strength"] == expected
                if expected is not None
                else None
            ),
            "previous_v3_matches": (
                actual["previous_v3_strength"] == expected
                if expected is not None
                else None
            ),
            "candidate_matches": (
                actual["strength_level"] == expected if expected is not None else None
            ),
            "observation": actual,
        }
        if "local_count_constraints" in case or "local_visibility_constraints" in case:
            stars = list(iter_pillar_gods(pillars, pillars["day"][0]))
            checks = []
            for constraint in case.get("local_count_constraints", []) + case.get(
                "local_visibility_constraints", []
            ):
                location = constraint.get("location")
                wanted = "地支藏干" if location == "藏干" else location
                observed = sum(
                    s.ten_god.value in constraint["gods"]
                    and (wanted is None or s.location == wanted)
                    for s in stars
                )
                checks.append(
                    {
                        "reference": constraint,
                        "observed_count": observed,
                        "matches": observed == constraint["count"],
                        "quantity_kind": "physical_occurrences_not_force_or_weighted_score",
                    }
                )
            row["local_source_checks"] = checks
        return row

    groups = {}
    for name, group in development["groups"].items():
        rows = [observe(c) for c in group["observations"]]
        groups[name] = {
            "source": group["source"],
            "source_sha256": group["source_sha256"],
            "classification": "exposed development, overlaps retained, not independent fresh evidence",
            "summary": summarize(rows),
            "cases": rows,
        }
    chapter = []
    for case in reference["cases"]:
        row = observe(case)
        for key in ("unseen_input", "prior_exact_pillar_overlaps", "input_consistency"):
            row[key] = case[key]
        chapter.append(row)
    fresh = [r for r in chapter if r["unseen_input"]]
    all_summaries = [g["summary"] for g in groups.values()] + [summarize(chapter)]
    gates = {
        "no_production_matching_label_regression": not any(
            g["regression_ids"] for g in all_summaries
        ),
        "no_previous_v3_matching_label_regression": not any(
            g["v3_regression_ids"] for g in all_summaries
        ),
        "new_passage_operator_resolves_nonoverlap_adjudicated_case": bool(
            summarize(fresh)["new_operator_resolved_ids"]
        ),
        "source_and_secondary_root_review_completed": False,
    }
    after = {p: digest(candidate_root / p) for p in before}
    if after != before:
        raise ValueError("Numerical dependency drift during comparison")
    local = [c for r in chapter for c in r.get("local_source_checks", [])]
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_id": protocol["candidate_id"],
        "candidate_root": str(candidate_root),
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "candidate_source_sha256": digest(path),
        "reference_sha256": digest(FIXTURE / "reference.json"),
        "dependency_sha256_before": before,
        "dependency_sha256_after": after,
        "development_groups": groups,
        "chapter_cases": chapter,
        "chapter_summary": summarize(chapter),
        "nonoverlapping_chapter_summary": summarize(fresh),
        "local_source_checks": {
            "assertions": len(local),
            "matches": sum(c["matches"] for c in local),
            "scope": "Manually frozen local occurrence/visibility claims, not global strength labels, independent cases or effective force validation.",
        },
        "adoption_gates": gates,
        "adoptable": all(gates.values()),
        "production_default_changed": False,
        "classical_acceptance_passed": False,
        "scope": "Complete predeclared 1947 官殺 chapter after candidate freeze. Same-developer annotation, not external expert blinding. All 28 charts, seven adjudicated global labels, 21 unknowns retained. Source glyphs and labels are not adjusted to outcomes. Old capacity gains cannot certify the new passage operator.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Audit outputs are immutable; choose a new path")
    result = audit(args.candidate_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "chapter": result["chapter_summary"],
                "nonoverlap": result["nonoverlapping_chapter_summary"],
                "local_source_checks": result["local_source_checks"],
                "adoption_gates": result["adoption_gates"],
                "adoptable": result["adoptable"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["adoptable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
