"""Compare the entire 性情 unit after its source annotation freeze."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_mediated_capacity_v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(name: str) -> dict[str, Any]:
    path = FIXTURE / name
    if digest(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError("Frozen source input changed: " + name)
    value: dict[str, Any] = json.loads(path.read_text())
    return value


def audit() -> dict[str, Any]:
    pre = frozen("pre-prospective.json")
    if pre["runner_sha256"] != digest(Path(__file__)):
        raise ValueError("Prospective runner differs from first binding")
    for name, value in pre["inputs"].items():
        if digest(FIXTURE / name) != value:
            raise ValueError("Prospective input differs from first binding: " + name)
    reference = frozen("reference.json")
    freeze = frozen("reference-freeze.json")
    protocol = frozen("protocol.json")
    exposure = frozen("exposure.json")
    if len(reference["cases"]) != freeze["complete_literal_records"]:
        raise ValueError("A chapter record was removed")
    if freeze["reference_sha256"] != digest(FIXTURE / "reference.json"):
        raise ValueError("Annotation changed after freeze")
    if any(name.startswith("fatebridge") for name in sys.modules):
        raise RuntimeError("Use a fresh process")
    path = ROOT / "scripts/audit_bazi_mediated_capacity.py"
    if digest(path) != frozen("pre-development.json")["runner_sha256"]:
        raise ValueError("Use the frozen development runner")
    spec = importlib.util.spec_from_file_location("_mediated_development", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load frozen development runner")
    development = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(development)
    replay = development.__dict__["audit"]()
    old = json.loads(
        gzip.decompress(
            (
                ROOT
                / "docs/validation/bazi-mediated-capacity-development-first-v1.json.gz"
            ).read_bytes()
        )
    )
    if {k: v for k, v in replay.items() if k != "recorded_at_utc"} != {
        k: v for k, v in old.items() if k != "recorded_at_utc"
    }:
        raise ValueError("Development first result not exactly reproduced")
    if not replay["development_gate"]:
        raise ValueError("Development gate did not permit new-unit comparison")
    controls = {
        "root_load_v2": sys.modules["_mediated_root_load_control"],
        "capacity_v3": sys.modules["_mediated_capacity_control"],
        "hidden_seal_v5": sys.modules["_mediated_hidden_control"],
        "mediated_v1": sys.modules["_mediated_candidate"],
    }
    from fatebridge.core.elements import ElementAnalysis

    prior = {tuple(r["pillars"]): r["refs"] for r in exposure["inputs"]}
    rows = []
    for record in reference["cases"]:
        pillars = {
            k: (v[0], v[1]) for k, v in zip(development.ORDER, record["pillars"])
        }
        assessment = ElementAnalysis.analyze_day_master_strength(pillars)["assessment"]
        receipts = {
            k: module.__dict__["evaluate"](pillars) for k, module in controls.items()
        }
        rows.append(
            {
                **record,
                "key": record["id"],
                "prior_exact_input_refs": prior.get(tuple(record["pillars"]), []),
                "nonoverlap_literal_input": tuple(record["pillars"]) not in prior,
                "assessment": assessment,
                "candidate_receipts": receipts,
                "grades": {
                    "production_v6": assessment["strength_level"],
                    **{k: v["strength_level"] for k, v in receipts.items()},
                },
            }
        )
    summary = development.__dict__["summarize"](rows)
    fresh_known = [
        r
        for r in rows
        if r["nonoverlap_literal_input"] and r["expected_strength"] is not None
    ]
    gains = [
        r
        for r in fresh_known
        if r["grades"]["production_v6"]
        != r["expected_strength"]
        == r["grades"]["mediated_v1"]
    ]
    not_v3 = [
        r["id"] for r in gains if r["grades"]["capacity_v3"] != r["expected_strength"]
    ]
    not_root_load = [
        r["id"] for r in gains if r["grades"]["root_load_v2"] != r["expected_strength"]
    ]
    gates = {
        "development_exactly_reproduced_and_passed": True,
        "whole_source_cohort_retained": len(rows) == freeze["complete_literal_records"],
        "no_source_baseline_regression": not summary["regressions"],
        "at_least_one_nonoverlap_gain_over_production": bool(gains),
        "new_cohort_complementarity_beyond_each_control": bool(not_v3)
        and bool(not_root_load),
        "independent_source_grade_mechanism_review": False,
    }
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "candidate_sha256": protocol["candidate_sha256"],
        "reference_sha256": digest(FIXTURE / "reference.json"),
        "pre_prospective_sha256": digest(FIXTURE / "pre-prospective.json"),
        "development_first_reproduced_exactly_except_timestamp": True,
        "development_summary": replay["summary"],
        "summary": summary,
        "nonoverlap_records": sum(r["nonoverlap_literal_input"] for r in rows),
        "nonoverlap_labeled_records": len(fresh_known),
        "nonoverlap_gains": [r["id"] for r in gains],
        "nonoverlap_gains_not_fixed_by_capacity_v3": not_v3,
        "nonoverlap_gains_not_fixed_by_root_load_v2": not_root_load,
        "rows": rows,
        "gates": gates,
        "adopted": False,
        "production_default_changed": False,
        "independent_source_grade_review": "pending",
        "real_world_efficacy": "not_tested",
        "model_pretraining_blindness_established": False,
        "full_goal_complete": False,
        "overall_score": None,
        "scope": "All35native chapter charts and all314exposed development charts retained. Nonoverlap is exact literal input novelty only. Force/thermal/temperament distinctions and source-grade ambiguity retained, no unknown imputation or biographical success scoring. Old candidate failures and new first result remain immutable; counts cannot certify authority.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(".gz.sha256").exists():
        parser.error("Refuse to overwrite a retained first result")
    report = audit()
    with args.output.open("xb") as stream:
        stream.write(
            gzip.compress(
                json.dumps(report, ensure_ascii=False, indent=2).encode(), mtime=0
            )
        )
    with args.output.with_suffix(".gz.sha256").open("x") as stream:
        stream.write(digest(args.output) + "\n")
    print(
        json.dumps(
            {"summary": report["summary"], "gates": report["gates"]}, ensure_ascii=False
        )
    )
    return 0 if all(report["gates"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
