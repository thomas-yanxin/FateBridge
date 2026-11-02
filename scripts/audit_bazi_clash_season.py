"""Replay a frozen seasonal clash hypothesis; never tune or adopt it here."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import types
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_clash_season_v1"
ORDER = ("year", "month", "day", "hour")
GROUPS = {
    "legacy": "tests/fixtures/bazi-strength-reference.json",
    "original": "tests/fixtures/bazi_classical_v1/cases.json",
    "hurt": "tests/fixtures/bazi_strength_expansion_v1/reference.json",
    "root": "tests/fixtures/bazi_root_force_experiment_v1/reference.json",
    "neutrality": "tests/fixtures/bazi_root_force_experiment_v2/reference.json",
    "passage": "tests/fixtures/bazi_root_force_experiment_v3/reference.json",
    "new_dizhi": "tests/fixtures/bazi_clash_season_v1/reference.json",
}
RUNNER_ARCHIVES = {
    "scripts/audit_bazi_clash_season.py": "tests/fixtures/bazi_clash_season_v1/first-runner.py.txt",
    "scripts/audit_bazi_clash_season_v2.py": "tests/fixtures/bazi_clash_season_v2/first-runner.py.txt",
}


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def frozen_json(path: Path) -> Any:
    if digest(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError(f"Frozen hash mismatch: {path.name}")
    return json.loads(path.read_text())


def verify_frozen_input(root: Path, relative: str, expected: str) -> None:
    """Resolve only historical runner code, never source data or numeric inputs."""
    if digest(root / relative) == expected:
        return
    archive = RUNNER_ARCHIVES.get(relative)
    if archive is None or digest(root / archive) != expected:
        raise ValueError(f"First-run contract changed: {relative}")


def load_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    protocol = frozen_json(FIXTURE / "protocol.json")
    reference = frozen_json(FIXTURE / "reference.json")
    if digest(FIXTURE / "protocol.json") != reference["protocol_sha256"]:
        raise ValueError("Reference does not belong to this protocol")
    if digest(FIXTURE / "candidate-core.py.txt") != protocol["candidate_sha256"]:
        raise ValueError("Candidate source changed")
    if (
        digest(FIXTURE / "source-chapter.pdf")
        != reference["source"]["source_chapter_sha256"]
    ):
        raise ValueError("Original source chapter changed")
    before = frozen_json(FIXTURE / "pre-first-run.json")
    for relative, expected in before["frozen_files"].items():
        verify_frozen_input(ROOT, relative, expected)
    return protocol, reference


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    known = [r for r in rows if r["expected_strength"] is not None]
    return {
        "cases": len(rows),
        "adjudicated": len(known),
        "unknown": len(rows) - len(known),
        "baseline_matched": sum(r["baseline_matches"] is True for r in known),
        "candidate_matched": sum(r["candidate_matches"] is True for r in known),
        "resolved": [r["id"] for r in known if r["resolved"]],
        "regressions": [r["id"] for r in known if r["regressed"]],
        "changed_unknowns": [
            r["id"] for r in rows if r["expected_strength"] is None and r["changed"]
        ],
    }


def local_comparison(
    result: dict[str, Any], annotation: dict[str, Any]
) -> dict[str, Any]:
    pair = set(annotation["positions"])
    events = [
        e
        for e in result["relations"]
        if e["kind"] == "六冲" and set(e["positions"]) == pair
    ]
    if len(events) != 1:
        return {"status": "not_comparable", "matches": None}
    event = events[0]
    values = event.get("root_multipliers")
    if not values or len(set(values.values())) != 2:
        return {
            "status": "not_comparable",
            "event_status": event["status"],
            "matches": None,
        }
    weaker = min(values, key=values.__getitem__)
    return {
        "status": "compared",
        "weaker_position": weaker,
        "matches": weaker == annotation["weaker_position"],
        "root_multipliers": values,
    }


def audit(candidate_root: Path) -> dict[str, Any]:
    protocol, reference = load_contract()
    candidate_root = candidate_root.resolve()
    expected = protocol["candidate_dependencies"]
    before = {p: digest(candidate_root / p) for p in expected}
    if before != expected:
        raise ValueError("Numerical dependencies differ from the frozen hypothesis")
    sys.path.insert(0, str(candidate_root / "src"))
    strength = importlib.import_module("fatebridge.core.strength")
    elements = importlib.import_module("fatebridge.core.elements")
    imported_file = strength.__file__
    if (
        imported_file is None
        or Path(imported_file).resolve()
        != (candidate_root / "src/fatebridge/core/strength.py").resolve()
    ):
        raise ValueError("Imported a different source tree")
    name = "fatebridge.core._frozen_seasonal_clash"
    candidate = types.ModuleType(name)
    candidate.__package__ = "fatebridge.core"
    candidate.__file__ = str(FIXTURE / "candidate-core.py.txt")
    sys.modules[name] = candidate
    exec(
        compile(Path(candidate.__file__).read_text(), candidate.__file__, "exec"),
        candidate.__dict__,
    )
    if asdict(strength.DEFAULT_POLICY) != asdict(candidate.DEFAULT_POLICY):
        raise ValueError("Candidate altered the policy coefficients")
    groups, all_rows, outputs = {}, [], {}
    for group, relative in GROUPS.items():
        document = json.loads((ROOT / relative).read_text())
        cases = (
            document
            if isinstance(document, list)
            else document["cases"] + document.get("additional_cases", [])
        )
        rows = []
        for case in cases:
            raw = case["pillars"]
            values = [raw[k] for k in ORDER] if isinstance(raw, dict) else raw
            pillars = dict(zip(ORDER, map(tuple, values)))
            phases = elements.ElementAnalysis.seasonal_phases(pillars["month"][1])
            baseline = strength._evaluate(pillars, phases, strength.DEFAULT_POLICY)
            proposed = candidate._evaluate(pillars, phases, candidate.DEFAULT_POLICY)
            label = case.get(
                "expected_strength", case.get("adjudication", {}).get("strength")
            )
            b, c = baseline["strength_level"], proposed["strength_level"]
            row = {
                "group": group,
                "id": case["id"],
                "pillars": ["".join(v) for v in values],
                "expected_strength": label,
                "baseline": baseline,
                "candidate": proposed,
                "baseline_matches": b == label if label is not None else None,
                "candidate_matches": c == label if label is not None else None,
                "resolved": label is not None and b != label and c == label,
                "regressed": label is not None and b == label and c != label,
                "changed": b != c,
            }
            rows.append(row)
            outputs[(group, case["id"])] = (baseline, proposed)
        groups[group] = {
            "source": relative,
            "source_sha256": digest(ROOT / relative),
            **summarize(rows),
            "rows": rows,
        }
        all_rows += rows
    local = []
    for annotation in reference["local_clash_labels"]:
        baseline, proposed = outputs[("new_dizhi", annotation["case_id"])]
        b, c = (local_comparison(result, annotation) for result in (baseline, proposed))
        local.append(
            {
                "source_annotation": annotation,
                "baseline": b,
                "candidate": c,
                "resolved": b["matches"] is False and c["matches"] is True,
                "regressed": b["matches"] is True and c["matches"] is False,
            }
        )
    fresh = [
        r
        for r in groups["new_dizhi"]["rows"]
        if not next(c for c in reference["cases"] if c["id"] == r["id"])[
            "prior_exact_pillar_overlaps"
        ]
    ]
    gates = {
        "no_matching_body_label_regression": not any(r["regressed"] for r in all_rows),
        "new_nonoverlap_body_or_local_clash_improvement": any(
            r["resolved"] for r in fresh
        )
        or any(r["resolved"] for r in local),
        "no_new_local_clash_regression": not any(r["regressed"] for r in local),
    }
    after = {p: digest(candidate_root / p) for p in expected}
    if after != before:
        raise ValueError("Numerical sources changed while the comparison ran")
    return {
        "candidate_id": protocol["candidate_id"],
        "candidate_root": str(candidate_root),
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "reference_sha256": digest(FIXTURE / "reference.json"),
        "candidate_sha256": digest(FIXTURE / "candidate-core.py.txt"),
        "numerical_dependencies_before": before,
        "numerical_dependencies_after": after,
        "numerical_dependency_drift": [],
        "groups": groups,
        "new_local_clash_comparisons": local,
        "adoption_gates": gates,
        "numerical_gates_passed": all(gates.values()),
        "production_default_changed": False,
        "classical_acceptance_passed": False,
        "overall_score": None,
        "scope": "Frozen experiment, all source examples and unknowns retained. "
        "Source premise and relative-force judgment still need review even if "
        "numeric gates pass. No coefficient tuning or automatic adoption; "
        "engineering, body labels, local clash labels and real-world efficacy "
        "are distinct. Group counts overlap and are never summed as accuracy.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists; preserve the earlier result and choose a new path")
    result = audit(args.candidate_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(
        json.dumps(
            {
                "groups": {
                    k: {field: value for field, value in v.items() if field != "rows"}
                    for k, v in result["groups"].items()
                },
                "adoption_gates": result["adoption_gates"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["numerical_gates_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
