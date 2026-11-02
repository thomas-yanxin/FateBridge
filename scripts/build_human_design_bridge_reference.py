"""Compile an independent exhaustive union-find oracle from frozen source facts.

No FateBridge module or production channel table is imported. Inputs are a
separately frozen case plan and the 2001 numeric source transcription. Compiler
failure is an error; production results are never used as a fallback reference.
"""

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(plan_path: Path, compiler: str) -> dict:
    plan = json.loads(plan_path.read_text())
    source_path = ROOT / "src/fatebridge/data/human_design/rave-2001-reference.json"
    source = json.loads(source_path.read_text())
    centers = sorted({g["center"] for g in source["gates"]})
    gate_centers = {g["gate"]: centers.index(g["center"]) for g in source["gates"]}
    pairs = sorted(
        {tuple(sorted(pair)) for g in source["gates"] for pair in g["channels"]}
    )
    if len(pairs) != 36 or len(centers) != 9:
        raise ValueError("Frozen source must contain 36 channels and nine centers")
    rows = ["36"] + [f"{a} {b} {gate_centers[a]} {gate_centers[b]}" for a, b in pairs]
    rows.append(str(len(plan["cases"])))
    identifiers = set()
    for case in plan["cases"]:
        if not re.fullmatch(r"[a-z0-9-]+", case["id"]) or case["id"] in identifiers:
            raise ValueError("Invalid or duplicate fixed oracle case identifier")
        identifiers.add(case["id"])
        gates = case["activated_gates"]
        if any(type(g) is not int or not 1 <= g <= 64 for g in gates) or len(
            set(gates)
        ) != len(gates):
            raise ValueError("Invalid frozen gate set")
        rows.append(f"{case['id']} {sum(1 << (g - 1) for g in gates):x}")
    input_text = "\n".join(rows) + "\n"
    c_path = ROOT / "scripts/human_design_bridge_oracle.c"
    version = subprocess.run(
        [compiler, "--version"], check=True, capture_output=True, text=True
    ).stdout.splitlines()[0]
    with tempfile.TemporaryDirectory(prefix="human-design-bridge-oracle-") as folder:
        binary = Path(folder) / "oracle"
        command = [
            compiler,
            "-std=c11",
            "-O3",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(c_path),
            "-o",
            str(binary),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        run = subprocess.run(
            [str(binary)], input=input_text, check=True, capture_output=True, text=True
        )
    observations = [json.loads(line) for line in run.stdout.splitlines()]
    if [r["id"] for r in observations] != [c["id"] for c in plan["cases"]]:
        raise ValueError(
            "Independent oracle returned an incomplete or reordered cohort"
        )
    for row in observations:
        if row["minimum_added_gate_count"] == -1:
            row["minimum_added_gate_count"] = None
        row["minimum_sets"].sort()
    return {
        "method_id": "independent_exhaustive_missing_gate_subsets_union_find_c_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plan_path": plan_path.relative_to(ROOT).as_posix(),
        "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        "oracle_source_path": c_path.relative_to(ROOT).as_posix(),
        "oracle_source_sha256": hashlib.sha256(c_path.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_table_path": source_path.relative_to(ROOT).as_posix(),
        "source_table_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "primary_source": source["source"],
        "compiler": version,
        "compiler_flags": ["-std=c11", "-O3", "-Wall", "-Wextra", "-Werror"],
        "input_text": input_text,
        "input_sha256": hashlib.sha256(input_text.encode()).hexdigest(),
        "raw_output_sha256": hashlib.sha256(run.stdout.encode()).hexdigest(),
        "raw_output": run.stdout,
        "diagnostics": run.stderr.splitlines(),
        "cases": observations,
        "scope": "Exhaustive combinatorial oracle for each fixed active-gate set in the separately transcribed 36-channel graph, through every subset at the first feasible size. Case selection was structural and engine-informed, not blind. No independent astronomy, exhaustive original prose, person/transit forecast or psychological validity claim.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan",
        type=Path,
        default=ROOT / "tests/fixtures/human-design-bridge-plan.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "tests/fixtures/human-design-bridge-oracle.json",
    )
    parser.add_argument("--compiler", default="cc")
    args = parser.parse_args()
    result = build(args.plan.resolve(), args.compiler)
    args.output.write_bytes(
        (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    print(
        json.dumps(
            {
                "cases": len(result["cases"]),
                "subsets_checked": sum(
                    r["candidate_subsets_checked"] for r in result["cases"]
                ),
                "output": str(args.output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
