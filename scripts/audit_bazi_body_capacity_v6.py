"""Compare unchanged body-capacity hypotheses on three complete source units."""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import tempfile
import types
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_body_capacity_v6"
ORDER = ("year", "month", "day", "hour")


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def frozen(path: Path) -> dict[str, Any]:
    if digest(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError("Frozen data changed: " + str(path))
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("Frozen input must be an object")
    return value


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    protocol, reference, exposure = (
        frozen(FIXTURE / name)
        for name in ("protocol.json", "reference.json", "prior-exposure.json")
    )
    if reference["protocol_sha256"] != digest(FIXTURE / "protocol.json"):
        raise ValueError("Reference uses another protocol")
    if protocol["prior_exposure_sha256"] != digest(FIXTURE / "prior-exposure.json"):
        raise ValueError("Previous exposure changed")
    for name, expected in {
        "candidate-v3.py.txt": protocol["operators"]["capacity_v3_sha256"],
        "candidate-v5.py.txt": protocol["operators"]["hidden_seal_v5_sha256"],
        **reference["source_files"],
    }.items():
        if digest(FIXTURE / name) != expected:
            raise ValueError("Candidate or primary pages changed: " + name)
    for name, entry in protocol["numerical_dependencies"].items():
        if digest(FIXTURE / entry["archive"]) != entry["sha256"]:
            raise ValueError("Frozen numerical dependency changed: " + name)
    if digest(ROOT / exposure["source"]) != exposure["source_sha256"]:
        raise ValueError("Old complete corpus changed")
    seen = {tuple(p) for p in exposure["distinct_inputs"]}
    for case in reference["cases"]:
        if case["new_nonoverlap_input"] != (tuple(case["pillars"]) not in seen):
            raise ValueError("Incorrect exact input overlap")
    if set(reference["source_mechanism_review_before_comparison"]) != set(
        reference["complete_chapters"]
    ):
        raise ValueError("Mechanism review missing a chapter")
    return protocol, reference, exposure


def restore(folder: Path, protocol: dict[str, Any]) -> None:
    folder.mkdir(exist_ok=False)
    for package in ("fatebridge", "fatebridge/core", "fatebridge/utils"):
        p = folder / "src" / package
        p.mkdir(parents=True, exist_ok=True)
        (p / "__init__.py").write_text("")
    for name, entry in protocol["numerical_dependencies"].items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((FIXTURE / entry["archive"]).read_bytes())


def candidate(name: str, file: str) -> types.ModuleType:
    path = FIXTURE / file
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(path.read_text(), str(path), "exec"), module.__dict__)
    return module


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    known = [r for r in rows if r["expected_strength"] is not None]
    return {
        "records": len(rows),
        "known_body": len(known),
        "unknown_body": len(rows) - len(known),
        "matches": {
            k: sum(r["matches"][k] is True for r in known)
            for k in ("production_v6", "capacity_v3", "hidden_seal_v5")
        },
        "v5_regressions_against_baseline": [
            r["id"]
            for r in known
            if r["matches"]["production_v6"] and not r["matches"]["hidden_seal_v5"]
        ],
        "v5_regressions_against_v3": [
            r["id"]
            for r in known
            if r["matches"]["capacity_v3"] and not r["matches"]["hidden_seal_v5"]
        ],
        "v5_specific_gains": [
            r["id"]
            for r in known
            if r["matches"]["hidden_seal_v5"]
            and not r["matches"]["production_v6"]
            and not r["matches"]["capacity_v3"]
        ],
        "v5_changes_against_v3_including_unknowns": [
            r["id"]
            for r in rows
            if r["strengths"]["hidden_seal_v5"] != r["strengths"]["capacity_v3"]
        ],
    }


def audit(
    source_root: Path, additional_exposed_reference: Path | None = None
) -> dict[str, Any]:
    protocol, reference, exposure = load_inputs()
    if any(n.startswith("fatebridge") for n in sys.modules):
        raise RuntimeError("Use a fresh process before importing FateBridge")
    for name, entry in protocol["numerical_dependencies"].items():
        if digest(source_root / name) != entry["sha256"]:
            raise ValueError("Numerical source differs from freeze: " + name)
    sys.path.insert(0, str(source_root / "src"))
    from fatebridge.core.elements import ElementAnalysis

    v3 = candidate("_source_capacity_v3", "candidate-v3.py.txt")
    v5 = candidate("_source_hidden_seal_v5", "candidate-v5.py.txt")
    for name in protocol["numerical_dependencies"]:
        if name.startswith("src/"):
            module = sys.modules[name[4:-3].replace("/", ".")]
            if (
                module.__file__ is None
                or Path(module.__file__).resolve() != (source_root / name).resolve()
            ):
                raise ValueError("Wrong module origin: " + name)
    before = json.loads(gzip.decompress((ROOT / exposure["source"]).read_bytes()))

    def observe(case: dict[str, Any], group: str) -> dict[str, Any]:
        values = case["pillars"]
        pillars = dict(zip(ORDER, map(tuple, values)))
        base = ElementAnalysis.analyze_day_master_strength(pillars)["assessment"]
        a, b = v3.evaluate(pillars), v5.evaluate(pillars)
        if not (
            a["baseline_strength"] == b["baseline_strength"] == base["strength_level"]
        ):
            raise ValueError("Ablation used a different baseline")
        levels = {
            "production_v6": base["strength_level"],
            "capacity_v3": a["strength_level"],
            "hidden_seal_v5": b["strength_level"],
        }
        label = case["expected_strength"]
        return {
            "group": group,
            "id": case["id"],
            "pillars": values,
            "expected_strength": label,
            "strengths": levels,
            "matches": {
                k: None if label is None else v == label for k, v in levels.items()
            },
            "assessment": base,
            "v3": a,
            "v5": b,
            "source_record": case.get("source_record", case),
        }

    groups = {
        g: [observe(c, g) for c in data["rows"]] for g, data in before["groups"].items()
    }
    baseline_reproduced = all(
        row["assessment"] == old["assessment"]
        for g, rows in groups.items()
        for row, old in zip(rows, before["groups"][g]["rows"], strict=True)
    )
    if additional_exposed_reference is not None:
        additional = frozen(additional_exposed_reference)
        groups["additional_exposed_followup"] = [
            observe(c, "additional_exposed_followup") for c in additional["cases"]
        ]
    fresh = [observe(c, "three_complete_units") for c in reference["cases"]]
    groups["three_complete_units"] = fresh
    summaries = {g: summarize(rows) for g, rows in groups.items()}
    fresh_summary = summarize(
        [
            r
            for r, c in zip(fresh, reference["cases"], strict=True)
            if c["new_nonoverlap_input"]
        ]
    )
    forbidden = []
    for group, relative in json.loads(
        (ROOT / "tests/fixtures/bazi_source_corpus_v1/registry.json").read_text()
    )["groups"].items():
        doc = json.loads((ROOT / relative).read_text())
        for claim in doc.get("body_constraints", []) if isinstance(doc, dict) else []:
            row = next(r for r in groups[group] if r["id"] == claim["case_id"])
            forbidden.append(
                {
                    "group": group,
                    "id": row["id"],
                    "source_constraint": claim,
                    "v5_passed": row["strengths"]["hidden_seal_v5"]
                    not in claim["forbidden_strengths"],
                }
            )
    gates = {
        "frozen_production_receipts_reproduce_all_previous_records": baseline_reproduced,
        "no_old_or_new_explicit_label_regression": not any(
            s["v5_regressions_against_baseline"] or s["v5_regressions_against_v3"]
            for s in summaries.values()
        ),
        "all_previous_forbidden_body_constraints_preserved": all(
            r["v5_passed"] for r in forbidden
        ),
        "new_nonoverlap_v5_specific_gain": bool(fresh_summary["v5_specific_gains"]),
        "mechanism_review_completed_before_comparison": bool(
            reference["source_mechanism_review_before_comparison"]
        ),
    }
    result = {
        "study_id": protocol["study_id"],
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "reference_sha256": digest(FIXTURE / "reference.json"),
        "summaries": summaries,
        "fresh_summary": fresh_summary,
        "groups": groups,
        "forbidden_body_checks": forbidden,
        "adoption_gates": gates,
        "numerical_gates_passed": all(gates.values()),
        "adopted": False,
        "production_default_changed": False,
        "old_v5_first_failure_reinterpreted": False,
        "source_labels_changed": False,
        "independent_external_review": "not_completed",
        "new_model_executions": 0,
        "real_world_efficacy": "not_tested",
        "full_goal_complete": False,
        "overall_score": None,
        "scope": "Whole predeclared three-unit extension; exposed old gains stay exposed. Same developer source annotations are not expert blinding. No source body label inferred from biography, wealth, peer count or generic from-structure.",
    }
    if additional_exposed_reference is not None:
        result["additional_exposed_replay"] = {
            "reference": str(additional_exposed_reference),
            "reference_sha256": digest(additional_exposed_reference),
            "new_independent_cases": 0,
            "scope": "Postcomparison coverage replay only. The original first report and original nine-case fresh-gain failure remain unchanged.",
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--additional-exposed-reference", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve prior results")
    protocol, _, _ = load_inputs()
    with tempfile.TemporaryDirectory(prefix="bazi-capacity-v6-") as name:
        folder = Path(name) / "source"
        restore(folder, protocol)
        result = audit(folder, args.additional_exposed_reference)
    raw = (
        json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()
    with args.output.open("xb") as f:
        f.write(gzip.compress(raw, mtime=0))
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(
        digest(args.output) + "\n"
    )
    print(
        json.dumps(
            {"fresh": result["fresh_summary"], "gates": result["adoption_gates"]},
            ensure_ascii=False,
        )
    )
    return 0 if result["numerical_gates_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
