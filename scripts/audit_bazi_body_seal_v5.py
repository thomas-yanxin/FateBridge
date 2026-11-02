"""Frozen body/seal ablation, including the complete predeclared 假從 chapter.

This study cannot adopt its own hypothesis or rewrite an earlier first result.
"""

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
FIXTURE = ROOT / "tests/fixtures/bazi_root_force_experiment_v5"
ORDER = ("year", "month", "day", "hour")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(path: Path) -> dict[str, Any]:
    if digest(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError(f"Frozen input changed: {path}")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Frozen input must be an object: {path}")
    return value


def load_frozen() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    protocol = frozen(FIXTURE / "protocol.json")
    reference = frozen(FIXTURE / "reference.json")
    exposure = frozen(FIXTURE / "prior-exposure.json")
    if reference["protocol_sha256"] != digest(FIXTURE / "protocol.json"):
        raise ValueError("Wrong reference protocol")
    if protocol["prior_exposure_sha256"] != digest(FIXTURE / "prior-exposure.json"):
        raise ValueError("Changed prior exposure register")
    for name, expected in {
        "candidate.py.txt": protocol["candidate_sha256"],
        "capacity-v3.py.txt": protocol["capacity_v3_sha256"],
        **reference["source_files"],
    }.items():
        if digest(FIXTURE / name) != expected:
            raise ValueError(f"Frozen source or candidate changed: {name}")
    for name, entry in protocol["numerical_dependencies"].items():
        if digest(FIXTURE / entry["archive"]) != entry["sha256"]:
            raise ValueError(f"Frozen dependency changed: {name}")
    if digest(ROOT / exposure["source_result"]) != exposure["source_result_sha256"]:
        raise ValueError("Previous first result changed")
    seen = {tuple(p) for p in exposure["pillars"]}
    for case in reference["cases"]:
        if case["new_nonoverlap_input"] != (tuple(case["pillars"]) not in seen):
            raise ValueError("Incorrect novelty annotation")
    return protocol, reference, exposure


def restore(destination: Path, protocol: dict[str, Any]) -> Path:
    destination.mkdir(exist_ok=False)
    for package in ("fatebridge", "fatebridge/core", "fatebridge/utils"):
        folder = destination / "src" / package
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "__init__.py").write_text("")
    for name, entry in protocol["numerical_dependencies"].items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((FIXTURE / entry["archive"]).read_bytes())
    return destination.resolve()


def candidate(name: str, path: Path) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = "fatebridge.core"
    sys.modules[name] = module
    exec(compile(path.read_text(), str(path), "exec"), module.__dict__)
    return module


def audit(source_root: Path) -> dict[str, Any]:
    protocol, reference, exposure = load_frozen()
    source_root = source_root.resolve()
    if any(name.startswith("fatebridge") for name in sys.modules):
        raise RuntimeError("Use a fresh process before importing FateBridge")
    for name, entry in protocol["numerical_dependencies"].items():
        if digest(source_root / name) != entry["sha256"]:
            raise ValueError(f"Numerical source differs from freeze: {name}")
    sys.path.insert(0, str(source_root / "src"))
    from fatebridge.core.elements import ElementAnalysis
    from fatebridge.utils.data import GENERATION_CYCLE, STEM_ELEMENTS

    old = candidate("_bazi_body_capacity_v3", FIXTURE / "capacity-v3.py.txt")
    new = candidate("_bazi_body_seal_v5", FIXTURE / "candidate.py.txt")
    for name in protocol["numerical_dependencies"]:
        if name.startswith("src/"):
            module = sys.modules[name[4:-3].replace("/", ".")]
            if (
                module.__file__ is None
                or Path(module.__file__).resolve() != source_root / name
            ):
                raise RuntimeError(f"Wrong module origin: {name}")

    previous = json.loads((ROOT / exposure["source_result"]).read_text())

    def observe(case: dict[str, Any]) -> dict[str, Any]:
        pillars = dict(zip(ORDER, map(tuple, case["pillars"])))
        result = ElementAnalysis.analyze_day_master_strength(pillars)["assessment"]
        v3, v5 = old.evaluate(pillars), new.evaluate(pillars)
        assert (
            v3["baseline_strength"]
            == v5["baseline_strength"]
            == result["strength_level"]
        )
        expected = case["expected_strength"]
        levels = {
            "production_v6": result["strength_level"],
            "capacity_v3": v3["strength_level"],
            "hidden_seal_v5": v5["strength_level"],
        }
        body = STEM_ELEMENTS[pillars["day"][0]][0]
        seal = next(e for e, child in GENERATION_CYCLE.items() if child == body)
        previous_baseline = case.get("strengths", {}).get("production_v6")
        return {
            "id": case["id"],
            "pillars": case["pillars"],
            "expected_strength": expected,
            "source_anchor": case.get("source_anchor"),
            "input_consistency": case.get("input_consistency"),
            "new_nonoverlap_input": case.get("new_nonoverlap_input", False),
            "baseline": {
                "method_id": result["method_id"],
                "support_share": result["support_share"],
                "structural_decision": result["structural_decision"],
                "actual_body_root_mass": sum(
                    r["remaining_mass"]
                    for r in result["hidden_stem_ledger"]
                    if r["element"] == body.value
                ),
                "actual_seal_root_mass": sum(
                    r["remaining_mass"]
                    for r in result["hidden_stem_ledger"]
                    if r["element"] == seal.value
                ),
                "hidden_stem_ledger": result["hidden_stem_ledger"],
            },
            "strengths": levels,
            "matches": {
                key: value == expected if expected is not None else None
                for key, value in levels.items()
            },
            "v3": v3,
            "v5": v5,
            "frozen_baseline_same_as_previous_first_v2": (
                result["strength_level"] == previous_baseline["level"]
                and result["support_share"] == previous_baseline["support_share"]
                if previous_baseline is not None
                else None
            ),
        }

    groups = {
        name: [observe(c) for c in cases] for name, cases in previous["groups"].items()
    }
    groups["new_jiacong_whole_chapter"] = [observe(c) for c in reference["cases"]]

    def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
        known = [r for r in rows if r["expected_strength"] is not None]
        return {
            "subjects": len(rows),
            "known_strength": len(known),
            "unknown_strength": len(rows) - len(known),
            "matches": {
                key: sum(r["matches"][key] is True for r in known)
                for key in ("production_v6", "capacity_v3", "hidden_seal_v5")
            },
            "regressions_vs_production": [
                r["id"]
                for r in known
                if r["matches"]["production_v6"] and not r["matches"]["hidden_seal_v5"]
            ],
            "regressions_vs_v3": [
                r["id"]
                for r in known
                if r["matches"]["capacity_v3"] and not r["matches"]["hidden_seal_v5"]
            ],
            "v5_specific_gain_ids": [
                r["id"]
                for r in known
                if r["matches"]["hidden_seal_v5"]
                and not r["matches"]["capacity_v3"]
                and not r["matches"]["production_v6"]
            ],
            "v5_mismatch_ids": [
                r["id"] for r in known if not r["matches"]["hidden_seal_v5"]
            ],
            "v5_changes_from_v3": [
                r["id"]
                for r in rows
                if r["strengths"]["hidden_seal_v5"] != r["strengths"]["capacity_v3"]
            ],
        }

    summaries = {name: summarize(rows) for name, rows in groups.items()}
    fresh = summarize(
        [r for r in groups["new_jiacong_whole_chapter"] if r["new_nonoverlap_input"]]
    )
    old_summaries = [
        v for k, v in summaries.items() if k != "new_jiacong_whole_chapter"
    ]
    gates = {
        "no_exposed_regression": not any(
            s["regressions_vs_production"] or s["regressions_vs_v3"]
            for s in old_summaries
        ),
        "new_v5_specific_gain": bool(fresh["v5_specific_gain_ids"])
        and not fresh["regressions_vs_production"]
        and not fresh["regressions_vs_v3"],
        "mechanism_review_completed_before_comparison": False,
    }
    return {
        "report_id": "body_and_hidden_seal_capacity_first_v5",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "reference_sha256": digest(FIXTURE / "reference.json"),
        "candidate_sha256": protocol["candidate_sha256"],
        "summaries": summaries,
        "fresh_summary": fresh,
        "groups": groups,
        "all_previous_v6_outputs_reproduced": all(
            r["frozen_baseline_same_as_previous_first_v2"] is True
            for name, rows in groups.items()
            if name != "new_jiacong_whole_chapter"
            for r in rows
        ),
        "adoption_gates": gates,
        "adopted": False,
        "production_default_changed": False,
        "full_goal_complete": False,
        "scope": "Single-reader source labels and frozen engineering ablation, not independent expert agreement, full-source acceptance, calibration or reality prediction. Overlapping historical groups are not summed. 新章未出现v5收益不能由旧JH02开发修复替代。",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.with_suffix(".sha256").exists():
        raise SystemExit("Output path is reserved; refuse to overwrite a first result")
    protocol, _, _ = load_frozen()
    with tempfile.TemporaryDirectory(prefix="fatebridge-body-seal-v5-") as temp:
        source = restore(Path(temp) / "frozen", protocol)
        result = audit(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    output.with_suffix(".sha256").write_text(digest(output) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "fresh_summary",
                    "adoption_gates",
                    "all_previous_v6_outputs_reproduced",
                    "adopted",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
