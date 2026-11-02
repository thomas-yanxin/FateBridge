"""Test complementary root-capacity witnesses against a frozen complete corpus."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import tempfile
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_mediated_capacity_v1"
ORDER = ("year", "month", "day", "hour")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(name: str) -> dict[str, Any]:
    path = FIXTURE / name
    if digest(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError("Frozen input changed: " + name)
    value: dict[str, Any] = json.loads(path.read_text())
    return value


def load_operator(name: str, filename: str) -> types.ModuleType:
    path = FIXTURE / filename
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(path.read_text(), str(path), "exec"), module.__dict__)
    return module


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    known = [r for r in rows if r["expected_strength"] is not None]
    return {
        "records": len(rows),
        "distinct_inputs": len({tuple(r["pillars"]) for r in rows}),
        "exact_labeled_records": len(known),
        "unknown_records": len(rows) - len(known),
        "matching_records": {
            name: sum(r["grades"][name] == r["expected_strength"] for r in known)
            for name in (
                "production_v6",
                "root_load_v2",
                "capacity_v3",
                "hidden_seal_v5",
                "mediated_v1",
            )
        },
        "improvements": [
            r["key"]
            for r in known
            if r["grades"]["production_v6"]
            != r["expected_strength"]
            == r["grades"]["mediated_v1"]
        ],
        "regressions": [
            r["key"]
            for r in known
            if r["grades"]["production_v6"]
            == r["expected_strength"]
            != r["grades"]["mediated_v1"]
        ],
        "changed_records": [
            r["key"]
            for r in rows
            if r["grades"]["production_v6"] != r["grades"]["mediated_v1"]
        ],
        "remaining_mismatches": [
            r["key"]
            for r in known
            if r["grades"]["mediated_v1"] != r["expected_strength"]
        ],
    }


def audit() -> dict[str, Any]:
    protocol = frozen("protocol.json")
    if digest(FIXTURE / "candidate.py.txt") != protocol["candidate_sha256"]:
        raise ValueError("Candidate changed")
    for name, value in protocol["controls_sha256"].items():
        if digest(FIXTURE / name) != value:
            raise ValueError("Control changed: " + name)
    for key, name in (
        ("baseline_sha256", "baseline314.json.gz"),
        ("negative_constraints_sha256", "negative-constraints.json"),
        ("registry_sha256", "baseline-registry.json"),
        ("exposure_sha256", "exposure.json"),
    ):
        if digest(FIXTURE / name) != protocol[key]:
            raise ValueError("Bound input changed: " + name)
    if any(name.startswith("fatebridge") for name in sys.modules):
        raise RuntimeError("Use a fresh process for the frozen numerical kernel")
    old = json.loads(gzip.decompress((FIXTURE / "baseline314.json.gz").read_bytes()))
    with tempfile.TemporaryDirectory(prefix="bazi-mediated-kernel-") as temporary:
        source = Path(temporary).resolve()
        for name in ("fatebridge", "fatebridge/core", "fatebridge/utils"):
            path = source / "src" / name
            path.mkdir(parents=True, exist_ok=True)
            (path / "__init__.py").write_text("")
        for name, item in protocol["numerical_dependencies"].items():
            archived = FIXTURE / item["archive"]
            if digest(archived) != item["sha256"]:
                raise ValueError("Numeric dependency changed: " + name)
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archived.read_bytes())
        sys.path.insert(0, str(source / "src"))
        from fatebridge.core.elements import ElementAnalysis

        controls = {
            "root_load_v2": load_operator(
                "_mediated_root_load_control", "control-root-load-v2.py.txt"
            ),
            "capacity_v3": load_operator(
                "_mediated_capacity_control", "control-capacity-v3.py.txt"
            ),
            "hidden_seal_v5": load_operator(
                "_mediated_hidden_control", "control-hidden-seal-v5.py.txt"
            ),
            "mediated_v1": load_operator("_mediated_candidate", "candidate.py.txt"),
        }
        for name in protocol["numerical_dependencies"]:
            if name.startswith("src/"):
                module = sys.modules[name[4:-3].replace("/", ".")]
                if (
                    module.__file__ is None
                    or Path(module.__file__).resolve() != source / name
                ):
                    raise RuntimeError("Unexpected numerical source: " + name)
        rows = []
        for group, data in old["groups"].items():
            for record in data["rows"]:
                pillars = {k: (v[0], v[1]) for k, v in zip(ORDER, record["pillars"])}
                assessment = ElementAnalysis.analyze_day_master_strength(pillars)[
                    "assessment"
                ]
                receipts = {
                    k: operator.__dict__["evaluate"](pillars)
                    for k, operator in controls.items()
                }
                rows.append(
                    {
                        "key": group + "/" + record["id"],
                        "group": group,
                        "id": record["id"],
                        "pillars": record["pillars"],
                        "expected_strength": record["expected_strength"],
                        "baseline_full_assessment_reproduced": assessment
                        == record["assessment"],
                        "assessment": assessment,
                        "candidate_receipts": receipts,
                        "grades": {
                            "production_v6": assessment["strength_level"],
                            **{k: v["strength_level"] for k, v in receipts.items()},
                        },
                    }
                )
        constraints = json.loads((FIXTURE / "negative-constraints.json").read_text())
        negatives = []
        for claim in constraints["constraints"]:
            matching = [r for r in rows if r["pillars"] == claim["pillars"]]
            if not matching or any(
                r["grades"] != matching[0]["grades"] for r in matching
            ):
                raise ValueError(
                    "Negative constraint absent or inconsistent: " + claim["id"]
                )
            row = matching[0]
            negatives.append(
                {
                    "claim": claim,
                    "record_keys": [r["key"] for r in matching],
                    "baseline_matches": row["grades"]["production_v6"]
                    not in claim["forbidden_strengths"],
                    "candidate_matches": row["grades"]["mediated_v1"]
                    not in claim["forbidden_strengths"],
                }
            )
        summary = summarize(rows)
        gates = {
            "all_314_full_baselines_reproduced": len(rows) == 314
            and all(r["baseline_full_assessment_reproduced"] for r in rows),
            "no_baseline_label_regression": not summary["regressions"],
            "no_negative_constraint_regression": all(
                not r["baseline_matches"] or r["candidate_matches"] for r in negatives
            ),
            "at_least_one_old_disagreement_improved": bool(summary["improvements"]),
        }
        return {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "protocol_sha256": digest(FIXTURE / "protocol.json"),
            "runner_sha256": digest(Path(__file__)),
            "candidate_sha256": protocol["candidate_sha256"],
            "summary": summary,
            "rows": rows,
            "negative_constraints": negatives,
            "development_gates": gates,
            "development_gate": all(gates.values()),
            "prospective_unit_inspection_allowed_by_development_gate": all(
                gates.values()
            ),
            "adopted": False,
            "production_default_changed": False,
            "independent_source_grade_review": "pending",
            "new_independent_cases": 0,
            "real_world_efficacy": "not_tested",
            "full_goal_complete": False,
            "overall_score": None,
            "scope": "All314exposed development records retained; old gains are zero unseen validation credit. First failure preserved; failed development forbids new-unit inspection and post-result tuning in this study.",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(".gz.sha256").exists():
        parser.error("Refuse to overwrite a retained result")
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
            {
                "summary": report["summary"],
                "development_gates": report["development_gates"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["development_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
