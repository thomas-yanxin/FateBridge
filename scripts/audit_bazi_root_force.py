"""Replay the frozen source experiment without changing the production default.

Exit status tests only the predeclared experimental adoption conditions. It is
not a score for calendar, complete classical acceptance or interpretation.
"""

from __future__ import annotations

import argparse
import builtins
import hashlib
import importlib.machinery
import importlib.util
import json
import runpy
import sys
import types
from pathlib import Path
from typing import Any

from audit_bazi_strength_expansion import input_consistency

from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.strength import DEFAULT_POLICY, _evaluate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_root_force_experiment_v1"
BASELINE_ARCHIVE = ROOT / "docs/validation/bazi-root-force-strength-baseline-v2.py.txt"
STRENGTH_DEPENDENCY = "src/fatebridge/core/strength.py"
HISTORICAL_HELPERS = (
    "src/fatebridge/core/classical_stages.py",
    "src/fatebridge/core/classical_roots.py",
)
ORDER = ("year", "month", "day", "hour")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen(
    allow_environment_drift: bool = False,
    historical_replay: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    reference = FIXTURE / "reference.json"
    if digest(reference) != reference.with_suffix(".sha256").read_text().strip():
        raise ValueError("Source annotations changed after freeze")
    protocol = json.loads((FIXTURE / "protocol.json").read_text())
    if digest(FIXTURE / "candidate.py.txt") != protocol["candidate_source_sha256"]:
        raise ValueError("Experimental candidate changed after freeze")
    dependencies = json.loads((FIXTURE / "dependencies.json").read_text())
    first = ROOT / "docs/validation/bazi-root-force-first-v1.json"
    if first.exists():
        if digest(first) != first.with_suffix(".sha256").read_text().strip():
            raise ValueError("First comparison changed after freeze")
        recorded = json.loads(first.read_text())
        if (
            recorded["reference_sha256"] != digest(reference)
            or recorded["protocol_sha256"] != digest(FIXTURE / "protocol.json")
            or recorded["dependency_fingerprints"] != dependencies
        ):
            raise ValueError("Experiment inputs changed after freeze of first result")
    changed = {
        p: {"frozen_sha256": h, "current_sha256": digest(ROOT / p)}
        for p, h in dependencies.items()
        if digest(ROOT / p) != h
    }
    allowed = {"uv.lock"} if allow_environment_drift else set()
    if historical_replay:
        if digest(BASELINE_ARCHIVE) != dependencies[STRENGTH_DEPENDENCY]:
            raise ValueError(
                "Historical baseline archive differs from frozen dependency"
            )
        allowed.add(STRENGTH_DEPENDENCY)
        for relative in HISTORICAL_HELPERS:
            archived = FIXTURE / "historical_dependencies" / relative
            if digest(archived) != dependencies[relative]:
                raise ValueError(
                    "Historical helper archive differs from frozen dependency"
                )
            allowed.add(relative)
    # A historical replay binds the exact original source below; it never
    # runs changed production code as if the old experiment were still valid.
    # Every other dependency remains hash-checked, and strict mode is default.
    if set(changed) - allowed:
        raise ValueError(f"Frozen experiment dependency changed: {list(changed)}")
    return json.loads(reference.read_text()), protocol, changed


def development_cases() -> list[dict[str, Any]]:
    """Existing labels are development evidence, never fresh unseen cases."""
    rows = []
    data = json.loads(
        (ROOT / "tests/fixtures/bazi-strength-reference.json").read_text()
    )
    for c in data["cases"]:
        rows.append(
            {
                "id": c["id"],
                "pillars": [c["pillars"][p] for p in ORDER],
                "expected_strength": c["expected_strength"],
            }
        )
    data = json.loads(
        (ROOT / "tests/fixtures/bazi_classical_v1/cases.json").read_text()
    )
    for c in data:
        if c["adjudication"]["strength"] is not None:
            rows.append(
                {
                    "id": c["id"],
                    "pillars": c["pillars"],
                    "expected_strength": c["adjudication"]["strength"],
                }
            )
    data = json.loads(
        (ROOT / "tests/fixtures/bazi_strength_expansion_v1/reference.json").read_text()
    )
    rows.extend(data["cases"])
    return rows


def historical_candidate() -> tuple[Any, Any, Any]:
    """Bind frozen imports in a private namespace, leaving production intact."""
    frozen_modules: dict[str, Any] = {}

    def frozen_import(
        name: str,
        globals: Any = None,
        locals: Any = None,
        fromlist: Any = (),
        level: int = 0,
    ) -> Any:
        if level == 0 and name in frozen_modules and fromlist:
            return frozen_modules[name]
        return builtins.__import__(name, globals, locals, fromlist, level)

    for public_name, source in [
        ("fatebridge.core.strength", BASELINE_ARCHIVE),
        *[
            ("fatebridge.core." + Path(p).stem, FIXTURE / "historical_dependencies" / p)
            for p in HISTORICAL_HELPERS
        ],
    ]:
        private_name = (
            "fatebridge.core._root_force_historical_" + public_name.rsplit(".", 1)[1]
        )
        module = types.ModuleType(private_name)
        module.__package__ = "fatebridge.core"
        module.__file__ = str(source)
        module.__dict__["__builtins__"] = {
            **vars(builtins),
            "__import__": frozen_import,
        }
        sys.modules[private_name] = module
        exec(compile(source.read_bytes(), str(source), "exec"), module.__dict__)
        frozen_modules[public_name] = module
    baseline = frozen_modules["fatebridge.core.strength"]

    source = FIXTURE / "candidate.py.txt"
    namespace: dict[str, Any] = {
        "__name__": "frozen_root_force_candidate_v1",
        "__file__": str(source),
        "__builtins__": {**vars(builtins), "__import__": frozen_import},
    }
    # Execute the unmodified, hash-verified candidate bytes. Only its import
    # binding differs; no labels, decisions, thresholds or code are rewritten.
    exec(compile(source.read_bytes(), str(source), "exec"), namespace)
    return baseline._evaluate, baseline.DEFAULT_POLICY, namespace["evaluate"]


def audit(
    allow_environment_drift: bool = False, historical_replay: bool = False
) -> dict[str, Any]:
    reference, protocol, environment_drift = load_frozen(
        allow_environment_drift, historical_replay
    )
    if historical_replay:
        baseline_evaluate, policy, candidate = historical_candidate()
    else:
        baseline_evaluate, policy = _evaluate, DEFAULT_POLICY
        candidate = runpy.run_path(str(FIXTURE / "candidate.py.txt"))["evaluate"]

    def observe(values: list[str], expected: str | None) -> dict[str, Any]:
        pillars = dict(zip(ORDER, map(tuple, values)))
        phases = ElementAnalysis.seasonal_phases(pillars["month"][1])
        baseline = baseline_evaluate(pillars, phases, policy)
        experiment = candidate(pillars, phases, policy)
        b, c = baseline["strength_level"], experiment["strength_level"]
        return {
            "pillars": values,
            "input_consistency": input_consistency(values),
            "baseline": b,
            "candidate": c,
            "support_share": baseline["support_share"],
            "expected_strength": expected,
            "baseline_matches": b == expected if expected is not None else None,
            "candidate_matches": c == expected if expected is not None else None,
            "regression": expected is not None and b == expected and c != expected,
            "root_capacity": experiment["candidate_root_capacity"],
            "baseline_structural_decision": baseline["structural_decision"],
        }

    development = []
    exposed = development_cases()
    exposed_inputs = {tuple(c["pillars"]): c["id"] for c in exposed}
    for c in exposed:
        development.append(
            {"id": c["id"], **observe(c["pillars"], c["expected_strength"])}
        )
    prospective = []
    for c in reference["cases"]:
        variants = [
            {
                "variant_id": "primary_scan",
                **observe(c["pillars"], c["expected_strength"]),
            }
        ]
        for v in c.get("transcription_variants", []):
            variants.append(
                {
                    "variant_id": v["variant_id"],
                    **observe(v["pillars"], c["expected_strength"]),
                }
            )
        known_overlap = exposed_inputs.get(tuple(c["pillars"]))
        prospective.append(
            {
                "id": c["id"],
                "source_pdf_pages": c["source_pdf_pages"],
                "expected_strength": c["expected_strength"],
                "label_kind": c["label_kind"],
                "known_development_overlap": known_overlap,
                "variants": variants,
                "baseline_matches_all_variants": (
                    all(v["baseline_matches"] for v in variants)
                    if c["expected_strength"] is not None
                    else None
                ),
                "candidate_matches_all_variants": (
                    all(v["candidate_matches"] for v in variants)
                    if c["expected_strength"] is not None
                    else None
                ),
                "regression_in_any_variant": any(v["regression"] for v in variants),
            }
        )
    new = [r for r in prospective if r["expected_strength"] is not None]
    unresolved = [r["id"] for r in new if not r["candidate_matches_all_variants"]]
    conditions = {
        "resolves_known_disagreement": any(
            not r["baseline_matches"] and r["candidate_matches"] for r in development
        ),
        "no_development_regression": not any(r["regression"] for r in development),
        "no_new_source_regression": not any(
            r["regression_in_any_variant"] for r in new
        ),
        "frozen_candidate_and_dependencies_verified": not environment_drift,
    }
    result = {
        "method_id": "root_capacity_frozen_experiment_v1",
        "reference_sha256": digest(FIXTURE / "reference.json"),
        "source_sha256": reference["source_sha256"],
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "candidate_source_sha256": protocol["candidate_source_sha256"],
        "dependency_fingerprints": json.loads(
            (FIXTURE / "dependencies.json").read_text()
        ),
        "development_summary": {
            "total": len(development),
            "baseline_matches": sum(r["baseline_matches"] for r in development),
            "candidate_matches": sum(r["candidate_matches"] for r in development),
            "regressions": sum(r["regression"] for r in development),
            "evidence_kind": "known development labels, not held-out validation",
        },
        "prospective_summary": {
            "complete_cases": len(prospective),
            "adjudicated_cases": len(new),
            "unknown_labels": len(prospective) - len(new),
            "baseline_matches": sum(r["baseline_matches_all_variants"] for r in new),
            "candidate_matches": sum(r["candidate_matches_all_variants"] for r in new),
            "regressions": sum(r["regression_in_any_variant"] for r in new),
            "known_development_overlaps": sum(
                r["known_development_overlap"] is not None for r in prospective
            ),
            "unresolved_candidate_cases": unresolved,
            "variant_denominator": "Count each source case once; adjudicable variants must all match. Variants and input inconsistencies remain visible.",
            "evidence_kind": "same-developer prospective source annotation; exposed after first comparison, not external blind validation",
        },
        "adoption_conditions": conditions,
        "predeclared_adoption_conditions_passed": all(conditions.values()),
        "production_default_changed": False,
        "full_classical_acceptance": False,
        "development_cases": development,
        "prospective_cases": prospective,
        "scope": "Predeclared experimental comparison only. Unknown source labels are not successes. Adoption conditions do not certify complete force, formation, calendar, explanatory fidelity or real-world prediction.",
    }
    if environment_drift:
        result["environment_drift"] = environment_drift
    if historical_replay:
        result["replay_mode"] = "verified_historical_strength_not_current_production"
        result["historical_baseline_sha256"] = digest(BASELINE_ARCHIVE)
        result["historical_helper_sha256"] = {
            p: digest(FIXTURE / "historical_dependencies" / p)
            for p in HISTORICAL_HELPERS
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--historical-replay",
        action="store_true",
        help="Replay the hash-verified original strength source without replacing production imports",
    )
    parser.add_argument(
        "--allow-environment-drift",
        action="store_true",
        help="Report a changed uv.lock explicitly; other core changes still fail unless the original strength archive is selected with --historical-replay; adoption stays unverified",
    )
    parser.add_argument(
        "--freeze-first-result",
        action="store_true",
        help="Create an immutable first-result copy; refuse to overwrite it",
    )
    args = parser.parse_args()
    first = ROOT / "docs/validation/bazi-root-force-first-v1.json"
    if args.freeze_first_result and first.exists():
        raise ValueError("First comparison already exists; do not overwrite history")
    if args.output.resolve() in {
        first.resolve(),
        first.with_suffix(".sha256").resolve(),
    }:
        raise ValueError(
            "Use a separate replay output; the first-result path is reserved"
        )
    if args.freeze_first_result and (
        args.allow_environment_drift or args.historical_replay
    ):
        raise ValueError("First-result freeze requires the exact frozen environment")
    result = audit(args.allow_environment_drift, args.historical_replay)
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(raw)
    if args.freeze_first_result:
        first.write_bytes(raw)
        first.with_suffix(".sha256").write_text(hashlib.sha256(raw).hexdigest() + "\n")
    summary = result["prospective_summary"]
    print(json.dumps(summary, ensure_ascii=False))
    print(f"Experimental adoption conditions: {result['adoption_conditions']}")
    return 0 if result["predeclared_adoption_conditions_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
