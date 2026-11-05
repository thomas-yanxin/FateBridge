"""Reject coordinated stem-output corruptions without inventing source labels."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/jinkou_stem_integrity_v1"
WATCH = (
    "src/fatebridge/core/output_jinkou_stems.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/core/metaphysics/jinkou_stems.py",
    "src/fatebridge/core/metaphysics/jinkou.py",
    "src/fatebridge/core/metaphysics/common.py",
    "src/fatebridge/services/metaphysics.py",
    "scripts/ren/audit_jinkou_stem_integrity.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> tuple[dict[str, Any], dict[str, Any]]:
    frozen = json.loads((corpus / "freeze.json").read_text())
    names = {"faults.json", "diagram-ledger.json"}
    if set(frozen["files"]) != names or {p.name for p in corpus.iterdir()} != names | {
        "freeze.json"
    }:
        raise ValueError("Frozen stem-integrity inventory changed")
    for name in names:
        if sha(corpus / name) != frozen["files"][name]:
            raise ValueError("Frozen stem-integrity labels changed")
    faults = json.loads((corpus / "faults.json").read_text())
    ledger = json.loads((corpus / "diagram-ledger.json").read_text())
    if len(faults["faults"]) != 20 or len({f["id"] for f in faults["faults"]}) != 20:
        raise ValueError("All 20 predeclared faults are required")
    if len(ledger["cases"]) != 64 or len({c["id"] for c in ledger["cases"]}) != 64:
        raise ValueError("All 64 source displays are required")
    source = ledger["existing_source_pages"]
    if sha(ROOT / source["path"]) != source["sha256"]:
        raise ValueError("Original diagram source pages changed")
    return faults, ledger


def corrupt(payload: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(payload)
    for path, value in updates.items():
        parts = path.split(".")
        cursor: Any = result
        for part in parts[:-1]:
            cursor = cursor[int(part)] if isinstance(cursor, list) else cursor[part]
        last = int(parts[-1]) if isinstance(cursor, list) else parts[-1]
        cursor[last] = value
    return result


def audit() -> dict[str, Any]:
    faults, ledger = reference()
    before = {n: sha(ROOT / n) for n in WATCH}
    from pydantic import ValidationError

    from fatebridge.core.output_jinkou_stems import JinkouGanzhiPairFacts
    from fatebridge.services.metaphysics import calculate_jinkou_analysis
    from fatebridge.services.tool_catalog import CATALOG

    spec = next(s for s in CATALOG if s.key == "jinkou")
    assert spec.output_model is not None
    valid = calculate_jinkou_analysis(**faults["business_payload"])
    spec.output_model.model_validate(valid)
    JinkouGanzhiPairFacts.model_validate(faults["pair_anchor"])
    checks = []
    for fault in faults["faults"]:
        business = fault["target"] == "business"
        model = spec.output_model if business else JinkouGanzhiPairFacts
        base = valid if business else faults["pair_anchor"]
        try:
            model.model_validate(corrupt(base, fault["updates"]))
            accepted = True
        except ValidationError:
            accepted = False
        checks.append(
            dict(
                id=fault["id"],
                target=fault["target"],
                expected_acceptance=fault["expected_acceptance"],
                accepted=accepted,
                matched=accepted is fault["expected_acceptance"],
            )
        )
    after = {n: sha(ROOT / n) for n in WATCH}
    if before != after:
        raise ValueError("Stem-integrity source changed during audit")
    return dict(
        reference_sha256=sha(CORPUS / "freeze.json"),
        implementation_sha256=after,
        valid_business_accepted=True,
        valid_literal_pair_accepted=True,
        required_fault_count=20,
        rejected_fault_count=sum(not c["accepted"] for c in checks),
        checks=checks,
        fault_rejection_passed=all(c["matched"] for c in checks),
        diagram_display_count=len(ledger["cases"]),
        required_carried_stem_slots=ledger["required_god_general_slots"],
        literal_carried_stem_labels=0,
        not_printed_slots=ledger["not_printed_slots"],
        diagram_calculation_match_rate=None,
        source_coverage_scope=ledger["scope"],
        new_historical_cases=0,
        new_empirical_outcomes=0,
        model_invocations=0,
        classical_acceptance_passed=False,
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        f"Rejected {result['rejected_fault_count']}/20 predeclared engineering faults"
    )
    return 0 if result["fault_rejection_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
