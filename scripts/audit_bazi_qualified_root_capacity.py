"""Frozen multi-root/no-visible-peer hypothesis: full development or source trial."""

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
FIXTURE = ROOT / "tests/fixtures/bazi_qualified_root_capacity_v1"
ORDER = ("year", "month", "day", "hour")
STEMS, BRANCHES = set("甲乙丙丁戊己庚辛壬癸"), set("子丑寅卯辰巳午未申酉戌亥")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(name: str) -> dict[str, Any]:
    path = FIXTURE / name
    if digest(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError("Frozen input changed: " + name)
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("Frozen input must be an object: " + name)
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


def load_inputs() -> dict[str, Any]:
    protocol = frozen("protocol.json")
    exposure = frozen("prior-exposure.json")
    negative = frozen("negative-constraints.json")
    expected = {
        "candidate.py.txt": protocol["candidate_sha256"],
        "capacity-v3.py.txt": protocol["capacity_v3_sha256"],
        "hidden-seal-v5.py.txt": protocol["hidden_seal_v5_sha256"],
        "exposed-corpus.json.gz": protocol["exposed_corpus_sha256"],
        "prior-exposure.json": protocol["prior_registry_sha256"],
        "prior-sources.json.gz": protocol["prior_archive_sha256"],
        "negative-constraints.json": protocol["negative_constraints_sha256"],
    }
    expected.update(
        {r["archive"]: r["sha256"] for r in protocol["numerical_dependencies"].values()}
    )
    for name, value in expected.items():
        if digest(FIXTURE / name) != value:
            raise ValueError("Candidate, numerical dependency or data changed: " + name)
    archive = json.loads(
        gzip.decompress((FIXTURE / "prior-sources.json.gz").read_bytes())
    )
    if set(archive) != set(exposure["source_hashes"]):
        raise ValueError("Prior source inventory differs")
    rebuilt: dict[tuple[str, ...], list[dict[str, str]]] = {}

    def visit(value: Any, source: str, pointer: str = "") -> None:
        key = normalize(value)
        if key is not None:
            rebuilt.setdefault(key, []).append({"source": source, "pointer": pointer})
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

    for name, text in archive.items():
        if hashlib.sha256(text.encode()).hexdigest() != exposure["source_hashes"][name]:
            raise ValueError("Archived source changed: " + name)
        visit(json.loads(text), name)
    values = [{"pillars": list(k), "refs": v} for k, v in sorted(rebuilt.items())]
    if values != exposure["inputs"] or len(values) != exposure["distinct_inputs"]:
        raise ValueError("Prior exposure does not reconstruct exactly")
    corpus = json.loads(
        gzip.decompress((FIXTURE / "exposed-corpus.json.gz").read_bytes())
    )
    return {
        "protocol": protocol,
        "exposure": exposure,
        "corpus": corpus,
        "negative": negative,
    }


def load_candidate(name: str, path: Path) -> types.ModuleType:
    value = types.ModuleType(name)
    value.__file__ = str(path)
    value.__package__ = "fatebridge.core"
    sys.modules[name] = value
    exec(compile(path.read_text(), str(path), "exec"), value.__dict__)
    return value


def audit(stage: str) -> dict[str, Any]:
    inputs = load_inputs()
    protocol, corpus = inputs["protocol"], inputs["corpus"]
    if any(name.startswith("fatebridge") for name in sys.modules):
        raise RuntimeError("Use a fresh process for the frozen numerical kernel")
    with tempfile.TemporaryDirectory(prefix="bazi-qualified-roots-") as temp:
        source = Path(temp).resolve()
        for name in ("fatebridge", "fatebridge/core", "fatebridge/utils"):
            p = source / "src" / name
            p.mkdir(parents=True, exist_ok=True)
            (p / "__init__.py").write_text("")
        for name, item in protocol["numerical_dependencies"].items():
            p = source / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes((FIXTURE / item["archive"]).read_bytes())
        sys.path.insert(0, str(source / "src"))
        from fatebridge.core.elements import ElementAnalysis

        modules = {
            "capacity_v3": load_candidate(
                "_root_capacity_v3", FIXTURE / "capacity-v3.py.txt"
            ),
            "hidden_seal_v5": load_candidate(
                "_root_capacity_v5", FIXTURE / "hidden-seal-v5.py.txt"
            ),
            "qualified_roots": load_candidate(
                "_qualified_roots_v1", FIXTURE / "candidate.py.txt"
            ),
        }
        for name in protocol["numerical_dependencies"]:
            if not name.startswith("src/"):
                continue
            module = sys.modules[name[4:-3].replace("/", ".")]
            if (
                module.__file__ is None
                or Path(module.__file__).resolve() != source / name
            ):
                raise RuntimeError("Wrong imported source: " + name)
        cache: dict[tuple[str, ...], dict[str, Any]] = {}

        def calculate(raw: Any) -> dict[str, Any]:
            key = normalize(raw)
            if key is None:
                raise ValueError("Incomplete literal pillars")
            if key not in cache:
                pillars = {k: (v[0], v[1]) for k, v in zip(ORDER, key)}
                a = ElementAnalysis.analyze_day_master_strength(pillars)["assessment"]
                control = {
                    name: value.evaluate(pillars) for name, value in modules.items()
                }
                cache[key] = {
                    "assessment": a,
                    "grades": {
                        "production_v6": a["strength_level"],
                        **{k: v["strength_level"] for k, v in control.items()},
                    },
                    "candidate_receipts": control,
                }
            return cache[key]

        rows = []
        for group, data in corpus["groups"].items():
            for old in data["rows"]:
                actual = calculate(old["pillars"])
                if actual["assessment"] != old["assessment"]:
                    raise RuntimeError("Baseline receipt changed: " + old["id"])
                expected = old["expected_strength"]
                matches = {
                    k: v == expected if expected is not None else None
                    for k, v in actual["grades"].items()
                }
                rows.append(
                    {
                        "group": group,
                        "id": old["id"],
                        "pillars": old["pillars"],
                        "expected_strength": expected,
                        "observed": actual,
                        "matches": matches,
                    }
                )
        negatives = []
        for c in inputs["negative"]["constraints"]:
            grades = calculate(c["pillars"])["grades"]
            negatives.append(
                {
                    **c,
                    "grades": grades,
                    "matches": {
                        k: v not in c["forbidden_strengths"] for k, v in grades.items()
                    },
                }
            )
        known = [r for r in rows if r["expected_strength"] is not None]
        gains = [
            r
            for r in known
            if r["matches"]["qualified_roots"] and not r["matches"]["production_v6"]
        ]
        regressions = [
            r
            for r in known
            if r["matches"]["production_v6"] and not r["matches"]["qualified_roots"]
        ]
        negative_regressions = [
            r
            for r in negatives
            if r["matches"]["production_v6"] and not r["matches"]["qualified_roots"]
        ]
        result = {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "protocol_sha256": digest(FIXTURE / "protocol.json"),
            "candidate_sha256": protocol["candidate_sha256"],
            "baseline_full_objects_reproduced": len(rows),
            "development_summary": {
                "records": len(rows),
                "different_inputs": len(cache),
                "declared_strength_records": len(known),
                "baseline_matching_records": sum(
                    r["matches"]["production_v6"] is True for r in known
                ),
                "candidate_matching_records": sum(
                    r["matches"]["qualified_roots"] is True for r in known
                ),
                "gain_records": [
                    {k: r[k] for k in ("group", "id", "pillars", "expected_strength")}
                    for r in gains
                ],
                "regressions": [
                    {k: r[k] for k in ("group", "id", "pillars", "expected_strength")}
                    for r in regressions
                ],
                "new_independent_credit": 0,
            },
            "development_gate": not regressions and not negative_regressions,
            "development_rows": rows,
            "negative_constraints": negatives,
            "adopted": False,
            "production_default_changed": False,
            "classical_acceptance_passed": False,
            "full_goal_complete": False,
            "overall_score": None,
        }
        if stage != "development":
            raise ValueError(
                "Prospective runner not yet frozen; preserve development result first"
            )
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("development",), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    checksum = Path(str(output) + ".sha256")
    if output.exists() or checksum.exists():
        raise SystemExit("Output reserved; preserve first result")
    result = audit(args.stage)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(
        gzip.compress(
            (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode(), mtime=0
        )
    )
    checksum.write_text(digest(output) + "\n")
    print(
        json.dumps(
            {
                "summary": result["development_summary"],
                "development_gate": result["development_gate"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
