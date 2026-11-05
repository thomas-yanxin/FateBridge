"""Keep Jingwei source support and hypothetical arithmetic apart from truth labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/liuren_jingwei_harmony_v1"
PIN = "7a8ed13bb8555a284d050925853a7e705f078abab98121a72e93bcd1efba4327"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def reference(folder: Path = CORPUS) -> dict[str, Any]:
    if sha(folder / "freeze.json") != PIN:
        raise ValueError("Frozen Jingwei review identity changed")
    manifest = json.loads((folder / "freeze.json").read_text())["files"]
    if {p.name for p in folder.iterdir()} != set(manifest) | {"freeze.json"}:
        raise ValueError("Frozen Jingwei review inventory changed")
    for name, digest in manifest.items():
        if sha(folder / name) != digest:
            raise ValueError("Frozen Jingwei review content changed: " + name)
    from tests.ren_source_arithmetic import jingwei_harmony

    if jingwei_harmony(folder) != json.loads((folder / "reference.json").read_text()):
        raise ValueError("Independent source arithmetic differs")
    return {
        key: json.loads((folder / f"{key}.json").read_text())
        for key in ("reference", "readings", "hypotheses", "protocol", "witnesses")
    }


def audit() -> dict[str, Any]:
    review = reference()
    # Validate the original, unchanged source and expectations before imports.
    from scripts.audit_liuren_day_placements import expected_facts
    from scripts.audit_liuren_day_placements import reference as original_reference

    original = original_reference()
    from fatebridge.core.metaphysics.liureng_day_placements import (
        day_placement_patterns,
    )

    implementation = ROOT / "src/fatebridge/core/metaphysics/liureng_day_placements.py"
    before = sha(implementation)
    rows = []
    failures = []
    contexts = review["reference"]["contexts"]
    if len(contexts) != 720 or len(original["contexts"]) != 720:
        raise ValueError("Original or diagnostic cohort changed")
    for diagnostic, old in zip(contexts, original["contexts"], strict=True):
        identity = (diagnostic["day_ganzhi"], diagnostic["sky_by_earth"])
        if identity != (old["day_ganzhi"], old["sky_by_earth"]):
            raise ValueError("Diagnostic and original input identities differ")
        value = day_placement_patterns(*identity)
        expected = expected_facts(old, original["reading"])
        selected = {key: value[key] for key in expected}
        unknowns = [row for row in value["evaluations"] if row["id"] in ("D11", "D12")]
        preserved = len(unknowns) == 2 and all(
            row["definition_adjudicated"] is False
            and row["relation_matches"] is None
            and row["matched"] is None
            for row in unknowns
        )
        row = dict(
            day_ganzhi=old["day_ganzhi"],
            rotation=diagnostic["rotation"],
            hypothetical=diagnostic["hypothetical"],
            original_expected=[r["matched"] for r in expected["evaluations"][-2:]],
            actual=[r["matched"] for r in unknowns],
            original_facts_unchanged=selected == expected,
            production_unknown_preserved=preserved,
            passed=selected == expected and preserved,
        )
        rows.append(row)
        if not row["passed"]:
            failures.append(row)
    if sha(implementation) != before:
        raise ValueError("Production implementation changed during review")
    return dict(
        source_review_pin=PIN,
        implementation_sha256=before,
        source_review=review["readings"],
        source_witnesses=review["witnesses"],
        hypothesis_definitions=review["hypotheses"],
        hypothetical_counts=review["reference"]["candidate_true_counts"],
        disagreements=review["reference"]["disagreements"],
        contexts=720,
        rows=rows,
        failures=failures,
        engineering_guard_passed=not failures,
        new_adjudicated_rules=0,
        new_historical_or_empirical_events=0,
        real_world_prediction="deferred_by_user",
        new_llm_processes=0,
        original_unresolved_ids=["D11", "D12"],
        classical_conformance="not_completed",
        calendar_validation="not_reassessed",
        free_text_fidelity="not_reassessed",
        original_gates=review["protocol"]["gates_unchanged"],
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite an existing audit")
    result = audit()
    with args.output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("contexts", "engineering_guard_passed", "goal_complete")
            }
        )
    )
    return 0 if result["engineering_guard_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
