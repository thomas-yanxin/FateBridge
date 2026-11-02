"""Reject contradictory ledger claims without changing original pattern labels."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/jinkou_pattern_integrity_v1"
IMPLEMENTATION = (
    "src/fatebridge/core/output_ren_patterns.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/core/metaphysics/jinkou_patterns.py",
    "scripts/audit_jinkou_pattern_integrity.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    frozen = json.loads((corpus / "freeze.json").read_text())
    if {p.name for p in corpus.iterdir()} != set(frozen["files"]) | {"freeze.json"}:
        raise ValueError("Frozen pattern-integrity inventory changed")
    for name, digest in frozen["files"].items():
        if sha(corpus / name) != digest:
            raise ValueError("Frozen pattern-integrity reference changed")
    data: dict[str, Any] = json.loads((corpus / "reference.json").read_text())
    if sha(ROOT / data["source_reference"]) != data["source_reference_sha256"]:
        raise ValueError("Original 64-case reference changed")
    if (
        data["catalog_ids"] != [f"P{i:02}" for i in range(1, 65)]
        or len(data["faults"]) != 20
    ):
        raise ValueError("Complete integrity probe inventory required")
    return data


def prior() -> Any:
    spec = importlib.util.spec_from_file_location(
        "integrity_prior", ROOT / "scripts/audit_jinkou_patterns.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def corrupt(board: dict[str, Any], name: str) -> dict[str, Any]:
    data = copy.deepcopy(board)
    ledger = data["evaluations"]
    positive = next(r for r in ledger if r["matched"] is True)
    negative = next(r for r in ledger if r["matched"] is False)
    unknown = next(r for r in ledger if r["matched"] is None)
    if name == "catalog_count_63":
        data["catalog_count"] = 63
    elif name == "drop_ledger_entry":
        ledger.pop()
    elif name == "duplicate_ledger_id":
        ledger[-1] = copy.deepcopy(ledger[0])
    elif name == "missing_ledger_id":
        ledger[0].pop("id")
    elif name == "missing_ledger_verdict":
        ledger[0].pop("matched")
    elif name == "empty_ledger":
        data["evaluations"] = []
    elif name == "evaluated_count_wrong":
        data["evaluated_rule_count"] -= 1
    elif name == "matched_count_wrong":
        data["evaluation_counts"]["matched"] += 1
    elif name == "unresolved_count_wrong":
        data["evaluation_counts"]["unresolved"] -= 1
    elif name == "positive_list_omission":
        data["matched"] = [r for r in data["matched"] if r["id"] != positive["id"]]
    elif name == "positive_list_false_addition":
        data["matched"].append(copy.deepcopy(negative))
    elif name == "positive_list_duplicate":
        data["matched"].append(copy.deepcopy(data["matched"][0]))
    elif name == "positive_metadata_conflict":
        data["matched"][0]["condition"] = "private-wrong-value"
    elif name == "unresolved_omission":
        data["unresolved"] = [r for r in data["unresolved"] if r["id"] != unknown["id"]]
    elif name == "unresolved_false_addition":
        data["unresolved"].append(copy.deepcopy(negative))
    elif name == "unresolved_duplicate":
        data["unresolved"].append(copy.deepcopy(data["unresolved"][0]))
    elif name == "unresolved_metadata_conflict":
        data["unresolved"][0]["reason"] = "private-wrong-value"
    elif name == "unknown_match_id":
        data["matched"][0]["id"] = "P65"
    elif name == "unknown_unresolved_id":
        data["unresolved"][0]["id"] = "P00"
    elif name == "complete_conformance_true":
        data["complete_classical_conformance"] = True
    else:
        raise ValueError(f"Unknown frozen fault {name}")
    return data


def baseline() -> dict[str, Any]:
    module = prior()
    source = module.load_reference()
    from fatebridge.core.metaphysics.jinkou import GUISHEN_IDENTITIES
    from fatebridge.core.metaphysics.jinkou_patterns import structural_patterns

    rows = module.literal_rows(source["cases"][5], GUISHEN_IDENTITIES)
    return structural_patterns(rows, day_ganzhi=source["cases"][5]["day"])


def audit() -> dict[str, Any]:
    ref = reference()
    before = {n: sha(ROOT / n) for n in IMPLEMENTATION}
    from pydantic import ValidationError

    from fatebridge.core.metaphysics.jinkou import GUISHEN_IDENTITIES
    from fatebridge.core.metaphysics.jinkou_patterns import structural_patterns
    from fatebridge.core.output_chinese import JinkouPatterns

    data = baseline()
    faults = []
    for name in ref["faults"]:
        try:
            JinkouPatterns.model_validate(corrupt(data, name))
            rejected = False
        except ValidationError:
            rejected = True
        faults.append(dict(name=name, rejected=rejected))
    module = prior()
    accepted, errors = [], []
    for case in module.load_reference()["cases"]:
        rows = module.literal_rows(case, GUISHEN_IDENTITIES)
        board = structural_patterns(rows, day_ganzhi=case["day"] or "甲子")
        try:
            JinkouPatterns.model_validate(board)
            accepted.append(case["id"])
        except ValidationError as exc:
            errors.append(dict(id=case["id"], error=str(exc)))
    stable = before == {n: sha(ROOT / n) for n in IMPLEMENTATION}
    return dict(
        audit_id="jinkou_pattern_integrity_v1",
        reference_sha256=sha(CORPUS / "freeze.json"),
        implementation_sha256=before,
        implementation_unchanged_during_audit=stable,
        corruption_probe_count=len(faults),
        rejected_corruption_probes=sum(r["rejected"] for r in faults),
        corruption_probes=faults,
        unaltered_original_case_outputs=64,
        unaltered_outputs_accepted=len(accepted),
        validation_errors=errors,
        scope=ref["scope"],
        selected_integrity_checks_passed=stable
        and not errors
        and len(accepted) == 64
        and all(r["rejected"] for r in faults),
        classical_acceptance_passed=False,
        free_text_semantic_acceptance_passed=False,
        goal_complete=False,
        model_invocations=0,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        {
            k: result[k]
            for k in (
                "corruption_probe_count",
                "rejected_corruption_probes",
                "unaltered_outputs_accepted",
                "selected_integrity_checks_passed",
                "goal_complete",
            )
        }
    )
    return 0 if result["selected_integrity_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
