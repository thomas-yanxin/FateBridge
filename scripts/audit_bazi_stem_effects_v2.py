"""Replay the frozen month-principal alternative on two whole source chapters."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_stem_transformation_v2"
ORDER = ("year", "month", "day", "hour")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(path: Path) -> Any:
    if digest(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError(f"Frozen input changed: {path}")
    return json.loads(path.read_text())


def load_frozen() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    protocol = frozen(FIXTURE / "protocol.json")
    reference = frozen(FIXTURE / "reference.json")
    if reference["protocol_sha256"] != digest(FIXTURE / "protocol.json"):
        raise ValueError("Wrong reference protocol")
    for name, expected in {
        "candidate.py.txt": protocol["candidate_sha256"],
        "baseline-v6.py.txt": protocol["baseline_v6_sha256"],
        **reference["source_files"],
    }.items():
        if digest(FIXTURE / name) != expected:
            raise ValueError(f"Frozen source or candidate changed: {name}")
    for name, entry in protocol["numerical_dependencies"].items():
        if digest(FIXTURE / entry["archive"]) != entry["sha256"]:
            raise ValueError(f"Frozen dependency changed: {name}")
    earlier = ROOT / protocol["prior_exposure"]["all_prior_106_distinct_inputs"]
    if digest(earlier) != protocol["prior_exposure"]["first_v1_result_sha256"]:
        raise ValueError("Previous first result changed")
    development = frozen(FIXTURE / "development-local-conversion.json")
    return protocol, reference, development


def restore(destination: Path, protocol: dict[str, Any]) -> Path:
    destination.mkdir(parents=True, exist_ok=False)
    for package in ("fatebridge", "fatebridge/core", "fatebridge/utils"):
        folder = destination / "src" / package
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "__init__.py").write_text("")
    for name, entry in protocol["numerical_dependencies"].items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((FIXTURE / entry["archive"]).read_bytes())
    return destination.resolve()


def module_from_file(path: Path, name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = "fatebridge.core"
    sys.modules[name] = module
    exec(compile(path.read_text(), str(path), "exec"), module.__dict__)
    return module


def audit(candidate_root: Path) -> dict[str, Any]:
    protocol, reference, development = load_frozen()
    candidate_root = candidate_root.resolve()
    if any(name.startswith("fatebridge") for name in sys.modules):
        raise RuntimeError("Use a fresh process before importing FateBridge")
    before = {p: digest(candidate_root / p) for p in protocol["numerical_dependencies"]}
    if before != {
        p: r["sha256"] for p, r in protocol["numerical_dependencies"].items()
    }:
        raise ValueError("Numerical source differs from freeze")
    sys.path.insert(0, str(candidate_root / "src"))
    from fatebridge.core.classical_roots import classify_classical_root
    from fatebridge.core.elements import ElementAnalysis
    from fatebridge.core.strength import DEFAULT_POLICY, _evaluate

    for name in protocol["numerical_dependencies"]:
        if name.startswith("src/") and name.endswith(".py"):
            loaded = sys.modules[name[4:-3].replace("/", ".")]
            if (
                loaded.__file__ is None
                or Path(loaded.__file__).resolve() != candidate_root / name
            ):
                raise RuntimeError(f"Wrong module origin: {name}")
    candidate = module_from_file(
        FIXTURE / "candidate.py.txt", "_bazi_stem_v2_candidate"
    )
    kernel = module_from_file(FIXTURE / "baseline-v6.py.txt", "_bazi_stem_v2_kernel")
    kernel.__dict__["evaluate_stem_effects"] = candidate.__dict__[
        "evaluate_stem_effects"
    ]
    prior = json.loads(
        (ROOT / protocol["prior_exposure"]["all_prior_106_distinct_inputs"]).read_text()
    )
    explicit = {r["id"]: r for r in development["exposed_source_labels"]}

    def observe(case: dict[str, Any]) -> dict[str, Any]:
        pillars = dict(zip(ORDER, map(tuple, case["pillars"])))
        phases = ElementAnalysis.seasonal_phases(pillars["month"][1])
        results = {
            "production_v6": _evaluate(
                pillars,
                phases,
                DEFAULT_POLICY,
                stem_effect_mode="precise_binding_only_v1",
            ),
            "candidate_v1": _evaluate(
                pillars,
                phases,
                DEFAULT_POLICY,
                stem_effect_mode="non_day_transformation_v1",
            ),
            "candidate_v2": kernel._evaluate(
                pillars,
                phases,
                kernel.DEFAULT_POLICY,
                stem_effect_mode="non_day_transformation_v1",
            ),
        }
        claims = list(case.get("local_conversion", []))
        if case["id"] in explicit:
            claims.append(explicit[case["id"]])
        # Earlier first output already retains source-authored known/unknown
        # pair references separately from its observed fields.
        if "source_checks" in case:
            claims.extend(
                {
                    k: p[k]
                    for k in ("positions", "expected_converted", "source_anchor")
                    if k in p
                }
                for p in case["source_checks"]
            )
        checks = []
        for claim in claims:
            observations = {}
            for key, result in results.items():
                decision = next(
                    (
                        d
                        for d in result["stem_effects"]["decisions"]
                        if d["positions"] == claim["positions"]
                    ),
                    None,
                )
                applicable = bool(
                    decision is not None
                    and decision["conditions"]["unique_adjacent_non_day_pair"]
                )
                actual = (
                    decision["status"] == "conditioned_transformation"
                    if decision is not None and applicable
                    else None
                )
                expected = claim["expected_converted"]
                observations[key] = {
                    "applicable": applicable,
                    "converted": actual,
                    "matches": (
                        actual == expected
                        if applicable and expected is not None
                        else None
                    ),
                }
            checks.append({"reference": claim, "observations": observations})
        expected = case["expected_strength"]
        return {
            "id": case["id"],
            "pillars": case["pillars"],
            "expected_strength": expected,
            "new_nonoverlap_input": case.get("new_nonoverlap_input", False),
            "source_checks": checks,
            "strengths": {
                k: {
                    "level": r["strength_level"],
                    "support_share": r["support_share"],
                    "matches": (
                        r["strength_level"] == expected
                        if expected is not None
                        else None
                    ),
                }
                for k, r in results.items()
            },
            "v2_stem_effects": results["candidate_v2"]["stem_effects"],
            "physical_budget_unchanged": all(
                results["production_v6"][key] == results["candidate_v2"][key]
                for key in (
                    "hidden_stem_ledger",
                    "roots",
                    "branch_budgets",
                    "combination_contributions",
                )
            ),
        }

    def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
        known = [r for r in rows if r["expected_strength"] is not None]
        pairs = [p for r in rows for p in r["source_checks"]]
        eligible = [
            p
            for p in pairs
            if p["reference"]["expected_converted"] is not None
            and p["observations"]["candidate_v2"]["applicable"]
        ]
        return {
            "subjects": len(rows),
            "known_strength": len(known),
            "unknown_strength": len(rows) - len(known),
            "strength_matches": {
                k: sum(r["strengths"][k]["matches"] is True for r in known)
                for k in ("production_v6", "candidate_v1", "candidate_v2")
            },
            "regression_ids": [
                r["id"]
                for r in known
                if r["strengths"]["production_v6"]["matches"]
                and not r["strengths"]["candidate_v2"]["matches"]
            ],
            "candidate_v2_mismatch_ids": [
                r["id"] for r in known if not r["strengths"]["candidate_v2"]["matches"]
            ],
            "physical_pairs_retained": len(pairs),
            "source_known_pairs": sum(
                p["reference"]["expected_converted"] is not None for p in pairs
            ),
            "applicable_source_known_pairs": len(eligible),
            "known_positive_matches": sum(
                p["reference"]["expected_converted"] is True
                and p["observations"]["candidate_v2"]["matches"] is True
                for p in eligible
            ),
            "known_negative_matches": sum(
                p["reference"]["expected_converted"] is False
                and p["observations"]["candidate_v2"]["matches"] is True
                for p in eligible
            ),
            "local_mismatches": sum(
                p["observations"]["candidate_v2"]["matches"] is False for p in eligible
            ),
            "local_v2_gains_vs_v1": sum(
                p["observations"]["candidate_v1"]["matches"] is False
                and p["observations"]["candidate_v2"]["matches"] is True
                for p in eligible
            ),
        }

    groups = {
        name: [observe(c) for c in cases] for name, cases in prior["groups"].items()
    }
    groups["new_jiahua_suiyun_whole_chapters"] = [
        observe(c) for c in reference["cases"]
    ]
    summaries = {name: summarize(rows) for name, rows in groups.items()}
    fresh = [
        r
        for r in groups["new_jiahua_suiyun_whole_chapters"]
        if r["new_nonoverlap_input"]
    ]
    summary = summarize(fresh)
    gates = {
        "no_explicit_strength_regression": not any(
            s["regression_ids"] for s in summaries.values()
        ),
        "fresh_local_positive_and_negative": summary["known_positive_matches"] > 0
        and summary["known_negative_matches"] > 0
        and summary["local_mismatches"] == 0,
        "fresh_causal_operator_gain": summary["known_positive_matches"] > 0,
        "complete_source_review": False,
    }
    if before != {p: digest(candidate_root / p) for p in before}:
        raise ValueError("Source changed during comparison")
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "reference_sha256": digest(FIXTURE / "reference.json"),
        "summaries": summaries,
        "groups": groups,
        "adoption_gates": gates,
        "adopted": False,
        "cross_layer_negative": {
            "source": reference["timing_source_observations"][0],
            "candidate_supports_scope": False,
            "predicted_converted": None,
            "counted_as_success": False,
        },
        "separate_actual_root_fact": {
            "source": reference["timing_source_observations"][1],
            "observed": classify_classical_root("丁", "酉"),
            "scope": "Already implemented actual-root fact, not a conversion gain or independent strength label.",
        },
        "production_default_changed": False,
        "full_classical_acceptance": False,
        "full_goal_complete": False,
        "later_source_corrections": {
            "reference_status": "historical_first_labels_not_current_source_truth",
            "errata": "tests/fixtures/bazi_classical_corrections_v2/errata.json",
            "corrected_exposed_replay": "tests/fixtures/bazi_classical_corrections_v2/corrected-exposed-replay.json",
            "boundary_review": "tests/fixtures/bazi_stem_transformation_v2/boundary-review-supplement.json",
            "scope": "Later full-passage reading changes exposed GS12 conversion True to False; corrected development result is2/3, not this historical first score. Source boundary511 adds theory only. Original first records remain immutable.",
        },
        "scope": "Preserved first comparison: whole predeclared chapters, unsupported day-master/remote/cross-layer cases not successes. Gains on exposed 合局 are development repairs only.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Existing outputs are reserved; never overwrite a first result")
    protocol, _, _ = load_frozen()
    with tempfile.TemporaryDirectory(prefix="bazi-stem-v2-") as folder:
        report = audit(restore(Path(folder) / "candidate", protocol))
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    args.output.with_suffix(".sha256").write_text(digest(args.output) + "\n")
    print(
        json.dumps(
            {
                "summaries": report["summaries"],
                "gates": report["adoption_gates"],
                "adopted": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
