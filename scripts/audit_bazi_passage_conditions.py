"""Replay first contradictory receipts and every valid registered passage."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from fatebridge.core.classical_passage import build_passage_evidence
from fatebridge.core.output_classical_passage import ClassicalPassage

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_passage_conditions_v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> Any:
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


def frozen(path: Path) -> Any:
    if digest(path) != Path(str(path) + ".sha256").read_text().split()[0]:
        raise ValueError("Frozen source or first counterexample changed: " + str(path))
    return read(path)


def legacy_contract(before: dict[str, Any]) -> Any:
    name = "_passage_contract_frozen_before_repair"
    module = types.ModuleType(name)
    sys.modules[name] = module
    exec(
        compile(
            before["src/fatebridge/core/output_classical_passage.py"],
            "pre_passage_output.py",
            "exec",
        ),
        module.__dict__,
    )
    return module.__dict__["ClassicalPassage"]


def audit() -> dict[str, Any]:
    protocol = frozen(FIXTURE / "protocol.json")
    before = frozen(FIXTURE / "before-source.json.gz")
    first = frozen(
        ROOT / "docs/validation/bazi-passage-conditions-discovery-first-v1.json.gz"
    )
    examples = frozen(FIXTURE / "counterexamples-first.json.gz")
    source = frozen(FIXTURE / "source-context-first.json")
    if first["mutations"] != examples["mutations"]:
        raise ValueError("First contradictory payloads were rewritten")
    if digest(FIXTURE / "passage-original196-201.pdf") != source["excerpt_sha256"]:
        raise ValueError("Full chapter excerpt changed")
    if digest(FIXTURE / "before-source.json.gz") != protocol["before_source_sha256"]:
        raise ValueError("Frozen original output model changed")
    for name, expected in protocol["preserved_references_sha256"].items():
        if digest(ROOT / name) != expected:
            raise ValueError("Original label, source, gate or corpus changed")
    preserved = [
        n
        for n in before
        if n
        not in {
            "src/fatebridge/core/output_classical_passage.py",
            "docs/validation/bazi-three-axis-requirements.json",
            "uv.lock",
        }
    ]
    for name in preserved:
        if (ROOT / name).read_text() != before[name]:
            raise ValueError(
                "Preserved calculation, original test or helper changed: " + name
            )
    legacy = legacy_contract(before)
    if legacy.model_json_schema() != ClassicalPassage.model_json_schema():
        raise ValueError("Public structural schema unexpectedly changed")
    results = []
    for case in examples["mutations"]:
        legacy.model_validate(case["payload"])
        try:
            ClassicalPassage.model_validate(case["payload"])
        except ValidationError as exc:
            errors = exc.errors(include_url=False, include_context=False)
        else:
            raise ValueError(
                "A first contradictory receipt still passes: " + case["id"]
            )
        results.append(
            dict(
                id=case["id"],
                old_contract_accepted=case["old_contract_accepted"],
                current_contract_rejected=True,
                errors=errors,
            )
        )
    rows = []
    for row in first["rows"]:
        pillars = dict(
            zip(
                ("year", "month", "day", "hour"),
                map(tuple, row["pillars"]),
                strict=True,
            )
        )
        current = build_passage_evidence(pillars, row["assessment"])
        if current != row["passage"]:
            raise ValueError("A valid passage calculation changed: " + row["id"])
        legacy.model_validate(current)
        ClassicalPassage.model_validate(current)
        rows.append(
            dict(
                group=row["group"],
                id=row["id"],
                pillars=row["pillars"],
                all_valid_fields_identical=True,
                old_and_current_contracts_accept=True,
            )
        )
    notes = read(
        ROOT / "tests/fixtures/bazi_focus_validation_v1/source-focus-notes.json"
    )
    original = []
    for note in notes["cases"]:
        row = next(
            r
            for r in first["rows"]
            if r["id"] == note["id"] and r["pillars"] == note["pillars"]
        )
        original.append(
            dict(
                id=note["id"],
                expected_strength=note["original_expected_strength"],
                actual_strength=row["assessment"]["strength_level"],
                source_note=note,
                valid_passage_unchanged=True,
                source_strength_disagreement_remains=row["assessment"]["strength_level"]
                != note["original_expected_strength"],
            )
        )
    return dict(
        recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        runner_sha256=digest(Path(__file__)),
        protocol_sha256=digest(FIXTURE / "protocol.json"),
        current_contract_sha256=digest(
            ROOT / "src/fatebridge/core/output_classical_passage.py"
        ),
        preserved_files=preserved,
        source_context=source,
        first_mutation_results=results,
        artificial_counterexample_count=len(results),
        old_artificial_contradictions_accepted=len(results),
        current_artificial_contradictions_rejected=len(results),
        valid_production_receipt_contradictions_observed_in_initial349=0,
        valid_record_count=len(rows),
        valid_rows=rows,
        original_nineteen=original,
        original_binding_enum_context_gaps=dict(
            pending=first["pending_context_missing_from_binding_enum"],
            other_effects=first["applied_effect_context_missing_from_binding_enum"],
            classification_changed=False,
            scope="Node-event occurrences include repeated source records. These conditions remain an open evidence-expansion issue; no-binding is not a verdict that every source condition is clear.",
        ),
        output_json_schema_unchanged=True,
        production_strength_policy_changed=False,
        new_numeric_calculation_repairs=0,
        new_classical_correct_cases_credited=0,
        effective_passage="not_adjudicated",
        new_model_executions=0,
        independent_expert_acceptance="not_completed",
        real_world_predictive_validity="not_tested",
        full_goal_complete=False,
        overall_score=None,
        scope="Semantic output-contract repair and same-calculation fidelity guards, not an observed production strength repair, independent classic agreement, actual model acceptance or real prediction.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve first results; choose a new output path")
    result = audit()
    encoded = (
        json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()
    with args.output.open("xb") as handle:
        handle.write(gzip.compress(encoded, mtime=0))
    Path(str(args.output) + ".sha256").write_text(digest(args.output) + "\n")
    print(
        json.dumps(
            dict(
                valid_records=result["valid_record_count"],
                artificial_contradictions_rejected=result[
                    "current_artificial_contradictions_rejected"
                ],
                original_nineteen_unresolved=sum(
                    r["source_strength_disagreement_remains"]
                    for r in result["original_nineteen"]
                ),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
