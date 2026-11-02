"""Compare a frozen local 五合 candidate without turning unknowns into success."""

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
FIXTURE = ROOT / "tests/fixtures/bazi_stem_transformation_v1"
ORDER = ("year", "month", "day", "hour")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(path: Path) -> Any:
    if digest(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError(f"Frozen input changed: {path}")
    return json.loads(path.read_text())


def restore_frozen_numerical_source(destination: Path) -> Path:
    """Restore only the closed numerical import graph, never copy live kernels."""
    protocol = frozen(FIXTURE / "protocol.json")
    destination.mkdir(parents=True, exist_ok=False)
    for package in ("fatebridge", "fatebridge/core", "fatebridge/utils"):
        directory = destination / "src" / package
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "__init__.py").write_text("")
    for name, receipt in protocol["candidate_dependencies"].items():
        archive = FIXTURE / receipt["archive"]
        if digest(archive) != receipt["sha256"]:
            raise ValueError(f"Archived dependency changed: {name}")
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read_bytes())
    return destination


def audit(candidate_root: Path = ROOT) -> dict[str, Any]:
    candidate_root = candidate_root.resolve()
    protocol = frozen(FIXTURE / "protocol.json")
    reference = frozen(FIXTURE / "reference.json")
    if reference["protocol_sha256"] != digest(FIXTURE / "protocol.json"):
        raise ValueError("Reference belongs to another protocol")
    for path, receipt in protocol["candidate_dependencies"].items():
        if digest(candidate_root / path) != receipt["sha256"]:
            raise ValueError(f"Numerical dependency changed: {path}")
        if digest(FIXTURE / receipt["archive"]) != receipt["sha256"]:
            raise ValueError(f"Archived dependency changed: {path}")
    if digest(FIXTURE / "baseline-v5.py.txt") != protocol["baseline_sha256"]:
        raise ValueError("Baseline changed")
    for name, expected in reference["source_files"].items():
        if digest(FIXTURE / name) != expected:
            raise ValueError(f"Source changed: {name}")
    if any(name.startswith("fatebridge") for name in sys.modules):
        raise RuntimeError("Replay in a fresh process before importing FateBridge")
    sys.path.insert(0, str(candidate_root / "src"))
    # Baseline and candidate use the same unmodified physical-token dependencies.
    from fatebridge.core.elements import ElementAnalysis
    from fatebridge.core.strength import DEFAULT_POLICY, _evaluate

    for source in protocol["candidate_dependencies"]:
        if not source.startswith("src/") or not source.endswith(".py"):
            continue
        module = sys.modules[source[4:-3].replace("/", ".")]
        if (
            module.__file__ is None
            or Path(module.__file__).resolve() != candidate_root / source
        ):
            raise RuntimeError(f"Wrong module origin: {source}")

    baseline = types.ModuleType("_bazi_frozen_stem_baseline")
    baseline.__package__ = "fatebridge.core"
    sys.modules[baseline.__name__] = baseline
    path = FIXTURE / "baseline-v5.py.txt"
    exec(compile(path.read_text(), str(path), "exec"), baseline.__dict__)

    def observe(case: dict[str, Any]) -> dict[str, Any]:
        pillars = dict(zip(ORDER, map(tuple, case["pillars"])))
        phases = ElementAnalysis.seasonal_phases(pillars["month"][1])
        results = {
            "baseline": baseline._evaluate(pillars, phases, baseline.DEFAULT_POLICY),
            "precise_binding": _evaluate(
                pillars,
                phases,
                DEFAULT_POLICY,
                stem_effect_mode="precise_binding_only_v1",
            ),
            "candidate": _evaluate(
                pillars,
                phases,
                DEFAULT_POLICY,
                stem_effect_mode="non_day_transformation_v1",
            ),
        }
        # The legacy public behavior is also checked against its byte-frozen kernel.
        if _evaluate(pillars, phases, DEFAULT_POLICY) != results["baseline"]:
            raise ValueError(f"Legacy behavior changed for {case['id']}")
        pair_checks = []
        for claim in case.get("local_conversion", []):
            decision = next(
                (
                    d
                    for d in results["candidate"]["stem_effects"]["decisions"]
                    if d["positions"] == claim["positions"]
                ),
                None,
            )
            applicable = (
                decision is not None
                and decision["conditions"]["unique_adjacent_non_day_pair"]
            )
            expected = claim["expected_converted"]
            observed = (
                decision["status"] == "conditioned_transformation"
                if decision is not None and applicable
                else None
            )
            pair_checks.append(
                {
                    **claim,
                    "applicable": applicable,
                    "observed_converted": observed,
                    "matches": (
                        observed == expected
                        if expected is not None and applicable
                        else None
                    ),
                }
            )
        expected = case["expected_strength"]
        return {
            "id": case["id"],
            "pillars": case["pillars"],
            "expected_strength": expected,
            "strength_matches": {
                k: r["strength_level"] == expected if expected is not None else None
                for k, r in results.items()
            },
            "observed": {
                k: {
                    "strength": r["strength_level"],
                    "support_share": r["support_share"],
                    "effective_elements": r["effective_elements"],
                }
                for k, r in results.items()
            },
            "source_checks": pair_checks,
            "stem_effects": results["candidate"]["stem_effects"],
            "physical_roots_unchanged": all(
                results["baseline"][k] == results["candidate"][k]
                for k in (
                    "hidden_stem_ledger",
                    "branch_budgets",
                    "roots",
                    "combination_contributions",
                )
            ),
            "new_nonoverlap_input": case.get("new_nonoverlap_input", False),
        }

    groups = {}
    development = json.loads(
        (ROOT / "docs/validation/bazi-strength-current-v4-replay.json").read_text()
    )
    for name, group in development["groups"].items():
        if digest(ROOT / group["source"]) != group["source_sha256"]:
            raise ValueError(f"Exposed source changed: {group['source']}")
        groups[name] = [observe(c) for c in group["observations"]]
    for version in (2, 3, 4):
        previous = frozen(
            ROOT
            / f"tests/fixtures/bazi_root_force_experiment_v{version}/reference.json"
        )
        groups[f"exposed_v{version}"] = [observe(c) for c in previous["cases"]]
    # A transparent corrected replay, never a replacement for the original first score.
    corrections = frozen(
        ROOT / "tests/fixtures/bazi_classical_corrections_v1/errata.json"
    )
    corrected = json.loads(json.dumps(previous["cases"]))
    for correction in corrections["corrections"]:
        next(c for c in corrected if c["id"] == correction["case_id"])[
            correction["field"]
        ] = correction["corrected_value"]
    groups["exposed_v4_postcomparison_correction"] = [observe(c) for c in corrected]
    groups["new_heju_whole_chapter"] = [observe(c) for c in reference["cases"]]

    def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
        known = [r for r in rows if r["expected_strength"] is not None]
        pairs = [p for r in rows for p in r["source_checks"]]
        return {
            "subjects": len(rows),
            "known_strength": len(known),
            "unknown_strength": len(rows) - len(known),
            "strength_matches": {
                k: sum(r["strength_matches"][k] is True for r in known)
                for k in ("baseline", "precise_binding", "candidate")
            },
            "regression_ids": [
                r["id"]
                for r in known
                if r["strength_matches"]["baseline"]
                and not r["strength_matches"]["candidate"]
            ],
            "resolved_ids": [
                r["id"]
                for r in known
                if not r["strength_matches"]["baseline"]
                and r["strength_matches"]["candidate"]
            ],
            "all_five_combination_pairs": len(pairs),
            "source_known_conversion": sum(
                p["expected_converted"] is not None for p in pairs
            ),
            "applicable_known_pairs": sum(
                p["expected_converted"] is not None and p["applicable"] for p in pairs
            ),
            "source_matches": sum(p["matches"] is True for p in pairs),
            "source_mismatches": sum(p["matches"] is False for p in pairs),
            "known_positive_matches": sum(
                p["expected_converted"] is True and p["matches"] is True for p in pairs
            ),
            "known_negative_matches": sum(
                p["expected_converted"] is False and p["matches"] is True for p in pairs
            ),
        }

    summaries = {n: summarize(rows) for n, rows in groups.items()}
    fresh = [r for r in groups["new_heju_whole_chapter"] if r["new_nonoverlap_input"]]
    fresh_summary = summarize(fresh)
    gates = {
        "no_strength_regression": not any(
            g["regression_ids"] for g in summaries.values()
        ),
        "fresh_explicit_positive_and_negative": fresh_summary["known_positive_matches"]
        > 0
        and fresh_summary["known_negative_matches"] > 0
        and fresh_summary["source_mismatches"] == 0,
        "fresh_conversion_operator_gain": fresh_summary["known_positive_matches"] > 0,
        "manual_source_and_effect_review": False,
    }
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "reference_sha256": digest(FIXTURE / "reference.json"),
        "candidate_dependencies": protocol["candidate_dependencies"],
        "summaries": summaries,
        "groups": groups,
        "gates": gates,
        "adopted": False,
        "full_classical_acceptance": False,
        "real_world_efficacy_established": False,
        "scope": "First comparison of a frozen conservative local operator. Unknown or unsupported pairs are not successes. Original and corrected exposed figures retained separately. No free-text or predictive efficacy certification.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; frozen first results are reserved")
    if args.candidate_root is not None:
        report = audit(args.candidate_root)
    else:
        with tempfile.TemporaryDirectory(prefix="fatebridge-stem-v1-") as temporary:
            candidate = restore_frozen_numerical_source(Path(temporary) / "candidate")
            report = audit(candidate)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    args.output.with_suffix(".sha256").write_text(digest(args.output) + "\n")
    print(
        json.dumps(
            {
                "summaries": report["summaries"],
                "gates": report["gates"],
                "adopted": report["adopted"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
