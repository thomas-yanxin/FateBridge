"""Recheck unchanged v5 against complete 順局/反局 and wider old constraints."""

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
FIXTURE = ROOT / "tests/fixtures/bazi_body_seal_v5_followup_v1"
ORDER = ("year", "month", "day", "hour")
STEMS = set("甲乙丙丁戊己庚辛壬癸")
BRANCHES = set("子丑寅卯辰巳午未申酉戌亥")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(path: Path) -> dict[str, Any]:
    if digest(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError(f"Frozen input changed: {path}")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("Expected an object")
    return value


def normalize(raw: Any) -> tuple[str, ...] | None:
    if isinstance(raw, dict):
        if not all(k in raw for k in ORDER):
            return None
        raw = [raw[k] for k in ORDER]
    if isinstance(raw, str):
        raw = raw.split()
    if not isinstance(raw, list) or len(raw) != 4:
        return None
    values = [
        "".join(v) if isinstance(v, list) and all(isinstance(c, str) for c in v) else v
        for v in raw
    ]
    if all(
        isinstance(v, str) and len(v) == 2 and v[0] in STEMS and v[1] in BRANCHES
        for v in values
    ):
        return tuple(values)
    return None


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    protocol = frozen(FIXTURE / "protocol.json")
    reference = frozen(FIXTURE / "reference.json")
    exposure = frozen(FIXTURE / "prior-exposure.json")
    execution = frozen(FIXTURE / "execution-inputs.json")
    for name, expected in {
        "candidate.py.txt": protocol["candidate_sha256"],
        "capacity-v3.py.txt": protocol["capacity_v3_sha256"],
        "prior-exposure.json": protocol["prior_exposure_sha256"],
        "prior-sources.json.gz": protocol["prior_sources_archive_sha256"],
        "expanded-exposed-regression.json": protocol[
            "expanded_exposed_regression_sha256"
        ],
        "negative-constraints.json": protocol["negative_constraints_sha256"],
        execution["original_first_file"]: execution["original_first_sha256"],
        **reference["source_files"],
    }.items():
        if digest(FIXTURE / name) != expected:
            raise ValueError(f"Source, candidate or prior data changed: {name}")
    if reference["protocol_sha256"] != digest(FIXTURE / "protocol.json"):
        raise ValueError("Wrong source protocol")
    for name, entry in protocol["numerical_dependencies"].items():
        if digest(FIXTURE / entry["archive"]) != entry["sha256"]:
            raise ValueError(f"Numerical dependency changed: {name}")
    archived = json.loads(
        gzip.decompress((FIXTURE / "prior-sources.json.gz").read_bytes())
    )
    seen: dict[tuple[str, ...], list[dict[str, str]]] = {}

    def visit(value: Any, source: str, pointer: str = "") -> None:
        key = normalize(value)
        if key is not None:
            seen.setdefault(key, []).append({"source": source, "pointer": pointer})
        if isinstance(value, dict):
            for k, v in value.items():
                visit(
                    v,
                    source,
                    pointer + "/" + str(k).replace("~", "~0").replace("/", "~1"),
                )
        elif isinstance(value, list):
            for i, v in enumerate(value):
                visit(v, source, pointer + "/" + str(i))

    if set(archived) != set(exposure["source_hashes"]):
        raise ValueError("Prior source inventory differs")
    for name, text in archived.items():
        if hashlib.sha256(text.encode()).hexdigest() != exposure["source_hashes"][name]:
            raise ValueError("Prior archived source changed: " + name)
        visit(json.loads(text), name)
    rebuilt = [{"pillars": list(p), "refs": refs} for p, refs in sorted(seen.items())]
    if rebuilt != exposure["inputs"] or len(rebuilt) != exposure["distinct_inputs"]:
        raise ValueError("Prior input index does not reconstruct from archived sources")
    for case in reference["cases"]:
        key = normalize(case["pillars"])
        if key is None or case["new_nonoverlap_input"] != (key not in seen):
            raise ValueError("Wrong input/novelty annotation")
    return protocol, reference, exposure


def restore(path: Path, protocol: dict[str, Any]) -> Path:
    for name in ("fatebridge", "fatebridge/core", "fatebridge/utils"):
        folder = path / "src" / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "__init__.py").write_text("")
    for name, entry in protocol["numerical_dependencies"].items():
        dest = path / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((FIXTURE / entry["archive"]).read_bytes())
    return path.resolve()


def load_candidate(name: str, path: Path) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = "fatebridge.core"
    sys.modules[name] = module
    exec(compile(path.read_text(), str(path), "exec"), module.__dict__)
    return module


def audit(path: Path) -> dict[str, Any]:
    protocol, reference, _ = load_inputs()
    if any(n.startswith("fatebridge") for n in sys.modules):
        raise RuntimeError("Use a fresh process")
    for name, entry in protocol["numerical_dependencies"].items():
        if digest(path / name) != entry["sha256"]:
            raise ValueError("Restored numerical source differs")
    sys.path.insert(0, str(path / "src"))
    from fatebridge.core.elements import ElementAnalysis

    old = load_candidate("_body_seal_followup_v3", FIXTURE / "capacity-v3.py.txt")
    new = load_candidate("_body_seal_followup_v5", FIXTURE / "candidate.py.txt")
    for name in protocol["numerical_dependencies"]:
        if name.startswith("src/"):
            module = sys.modules[name[4:-3].replace("/", ".")]
            if (
                module.__file__ is None
                or Path(module.__file__).resolve() != path / name
            ):
                raise RuntimeError("Wrong module origin: " + name)
    cache: dict[tuple[str, ...], dict[str, Any]] = {}

    def calculate(raw: Any) -> dict[str, Any]:
        key = normalize(raw)
        if key is None:
            raise ValueError("Incomplete source pillars")
        if key not in cache:
            pillars = {name: (value[0], value[1]) for name, value in zip(ORDER, key)}
            a = ElementAnalysis.analyze_day_master_strength(pillars)["assessment"]
            v3, v5 = old.evaluate(pillars), new.evaluate(pillars)
            cache[key] = {
                "production_v6": a["strength_level"],
                "capacity_v3": v3["strength_level"],
                "hidden_seal_v5": v5["strength_level"],
                "support_share": a["support_share"],
                "v3": v3,
                "v5": v5,
                "structural_decision": a["structural_decision"],
                "hidden_stem_ledger": a["hidden_stem_ledger"],
            }
        return cache[key]

    def observe(case: dict[str, Any]) -> dict[str, Any]:
        actual = calculate(case["pillars"])
        expected = case.get("expected_strength", case.get("expected"))
        matches = {
            k: actual[k] == expected if expected is not None else None
            for k in ("production_v6", "capacity_v3", "hidden_seal_v5")
        }
        return {
            "id": case.get("id"),
            "pillars": case["pillars"],
            "expected_strength": expected,
            "new_nonoverlap_input": case.get("new_nonoverlap_input", False),
            "observed": actual,
            "matches": matches,
            "regression": matches["hidden_seal_v5"] is False
            and (matches["production_v6"] is True or matches["capacity_v3"] is True),
            "v5_specific_gain": matches["hidden_seal_v5"] is True
            and matches["production_v6"] is False
            and matches["capacity_v3"] is False,
        }

    execution = frozen(FIXTURE / "execution-inputs.json")
    original = json.loads((FIXTURE / execution["original_first_file"]).read_text())
    old_groups = {
        name: [observe(c) for c in cases] for name, cases in original["groups"].items()
    }
    old_reproduced = all(
        r["observed"][k] == c["strengths"][k]
        for name, rows in old_groups.items()
        for r, c in zip(rows, original["groups"][name])
        for k in ("production_v6", "capacity_v3", "hidden_seal_v5")
    )
    if not old_reproduced:
        raise RuntimeError("Original first controls not reproduced")
    expanded = json.loads((FIXTURE / "expanded-exposed-regression.json").read_text())
    expanded_rows = [observe(c) for c in expanded["all_records"]]
    new_rows = [observe(c) for c in reference["cases"]]

    def constraint(case: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
        actual = calculate(case["pillars"])
        safe = {
            k: actual[k] not in item["forbidden_strengths"]
            for k in ("production_v6", "capacity_v3", "hidden_seal_v5")
        }
        return {
            "case_id": case.get("id", case.get("case_id")),
            "source": item,
            "pillars": case["pillars"],
            "observed": {k: actual[k] for k in safe},
            "matches": safe,
            "regression": not safe["hidden_seal_v5"]
            and (safe["production_v6"] or safe["capacity_v3"]),
        }

    old_negative = frozen(FIXTURE / "negative-constraints.json")
    old_constraints = [constraint(c, c) for c in old_negative["constraints"]]
    new_constraints = [
        constraint(c, item)
        for c in reference["cases"]
        for item in c["negative_constraints"]
    ]
    fresh = [r for r in new_rows if r["new_nonoverlap_input"]]
    known = [r for r in fresh if r["expected_strength"] is not None]
    gates = {
        "no_old_positive_regression": not any(
            r["regression"] for rows in old_groups.values() for r in rows
        )
        and not any(r["regression"] for r in expanded_rows),
        "no_old_negative_constraint_regression": not any(
            r["regression"] for r in old_constraints
        ),
        "fresh_v5_specific_gain": any(r["v5_specific_gain"] for r in known)
        and not any(r["regression"] for r in fresh),
        "fresh_negative_constraints": not any(r["regression"] for r in new_constraints),
        "full_mechanism_review": False,
    }
    summary = {
        "whole_cohort_cases": len(new_rows),
        "new_nonoverlap_cases": len(fresh),
        "new_known_strength": len(known),
        "new_unknown_strength": len(fresh) - len(known),
        "new_strength_matches": {
            k: sum(r["matches"][k] is True for r in known)
            for k in ("production_v6", "capacity_v3", "hidden_seal_v5")
        },
        "new_v5_specific_gains": [r["id"] for r in known if r["v5_specific_gain"]],
        "new_strength_regressions": [r["id"] for r in fresh if r["regression"]],
        "functional_or_structure_source_claims_retained": len(reference["cases"]),
        "functional_claims_scored_as_correct_from_ordinary_strength": 0,
    }
    return {
        "report_id": "body_seal_v5_shunju_fanju_first_v1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "reference_sha256": digest(FIXTURE / "reference.json"),
        "candidate_sha256": protocol["candidate_sha256"],
        "summary": summary,
        "adoption_gates": gates,
        "new_cases": new_rows,
        "old_original_groups": old_groups,
        "expanded_old_records": expanded_rows,
        "old_negative_constraints": old_constraints,
        "new_negative_constraints": new_constraints,
        "old_first_controls_reproduced": old_reproduced,
        "functional_claim_scope": "All26source claims remain retained in frozen reference; this frozen ordinary-strength trial does not evaluate 從兒/反局 formation, receiving capacity or exact effective rescue. Unknown strength labels never count those claims as matched. Inspect current actual public adjudication separately before any claim of full-source conformity.",
        "adopted": False,
        "production_default_changed": False,
        "full_goal_complete": False,
        "overall_score": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.with_suffix(".sha256").exists():
        raise SystemExit("Output reserved; preserve the first result")
    protocol, _, _ = load_inputs()
    with tempfile.TemporaryDirectory(prefix="bazi-body-seal-followup-") as temp:
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
                    "summary",
                    "adoption_gates",
                    "old_first_controls_reproduced",
                    "adopted",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
