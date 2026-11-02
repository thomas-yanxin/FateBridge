"""Replay the complete registered exposed corpus, including newer failures."""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path
from typing import Any

from fatebridge.core.strength import STRENGTH_METHOD_ID

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fatebridge.validation.bazi_source_corpus import (
    case_strength_constraints,
    digest,
    input_consistency,
    input_index,
    load_registry,
    pillar_values,
    source_cases,
    strength_annotation,
)
from fatebridge.validation.bazi_source_inputs import source_documents
from scripts.audit_bazi_clash_current import audit as public_replay
from scripts.audit_bazi_clash_season_v2 import compare_direction
from scripts.audit_bazi_disagreements import budget_components
from scripts.audit_bazi_seasonal_bureau_v2 import compare_application

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_source_corpus_v9"


def audit(fixture: Path | None = None) -> dict[str, Any]:
    selected_fixture = FIXTURE if fixture is None else fixture
    registry_path = selected_fixture / "registry.json"
    protocol_path = selected_fixture / "protocol.json"
    if (
        digest(protocol_path)
        != protocol_path.with_suffix(".sha256").read_text().strip()
    ):
        raise ValueError("Frozen protocol changed")
    protocol = json.loads(protocol_path.read_text())
    if protocol["registry_sha256"] != digest(registry_path):
        raise ValueError("Protocol references a different registry")
    registry = load_registry(ROOT, registry_path)
    documents, originals, input_revision = source_documents(ROOT, registry)
    replay = public_replay(
        registry["groups"],
        source_view_registry=registry_path if input_revision is not None else None,
    )
    all_rows = []
    claims = []
    counts = {}
    for group, relative in registry["groups"].items():
        document = documents[group]
        cases = source_cases(document)
        original_cases = source_cases(originals[group])
        rows = replay["groups"][group]["rows"]
        for case, original, row in zip(cases, original_cases, rows, strict=True):
            if pillar_values(case) != row["pillars"]:
                raise ValueError("Literal source pillars changed during replay")
            status, expected = strength_annotation(case)
            if expected != row["expected_strength"]:
                raise ValueError("A source label changed during replay")
            row["group"] = group
            row["label_status"] = status
            row["source_record"] = case
            if input_revision is not None:
                row["original_source_record"] = original
            row["input_consistency"] = input_consistency(row["pillars"])
            row["components"] = budget_components(
                row["assessment"], row["pillars"][2][0]
            )
            all_rows.append(row)
        lookup = {r["id"]: r for r in rows}
        if len(lookup) != len(rows):
            raise ValueError("Source case identifier repeated within a group")
        if isinstance(document, dict):
            for kind in (
                "local_clash_labels",
                "body_constraints",
                "clash_application_conditions",
            ):
                for annotation in document.get(kind, []):
                    row = lookup[annotation["case_id"]]
                    if kind == "local_clash_labels":
                        compared = compare_direction(row["assessment"], annotation)
                    elif kind == "clash_application_conditions":
                        compared = compare_application(row["assessment"], annotation)
                    else:
                        compared = {
                            "status": "forbidden_body_labels_only",
                            "matches": row["actual_strength"]
                            not in annotation["forbidden_strengths"],
                            "does_not_assign_an_exact_source_label": True,
                        }
                    claims.append(
                        {
                            "group": group,
                            "kind": kind,
                            "annotation": annotation,
                            **compared,
                        }
                    )
        for case in cases:
            for index, annotation in enumerate(case_strength_constraints(case)):
                row = lookup[case["id"]]
                claims.append(
                    {
                        "group": group,
                        "kind": "body_constraints",
                        "annotation": annotation,
                        "annotation_location": (
                            f"case:{case['id']}/negative_constraints/{index}"
                        ),
                        "status": "forbidden_body_labels_only",
                        "matches": row["actual_strength"]
                        not in annotation["forbidden_strengths"],
                        "does_not_assign_an_exact_source_label": True,
                    }
                )
        counts[group] = {
            "cases": len(rows),
            "body_annotated": sum(r["expected_strength"] is not None for r in rows),
            "body_explicitly_unknown": sum(
                r["label_status"] == "explicitly_unknown_body_strength" for r in rows
            ),
            "body_not_annotated": sum(
                r["label_status"] == "not_annotated_for_body_strength" for r in rows
            ),
            "matches": sum(r["matches"] is True for r in rows),
            "mismatches": sum(r["matches"] is False for r in rows),
        }
    anchors = json.loads((ROOT / registry["original_nineteen_review"]).read_text())[
        "cases"
    ]
    preserved = []
    for anchor in anchors:
        row = next(
            r
            for r in all_rows
            if r["group"] == anchor["baseline_group"] and r["id"] == anchor["id"]
        )
        if (
            row["pillars"] != anchor["pillars"]
            or row["expected_strength"] != anchor["expected_strength"]
        ):
            raise ValueError("Original disagreement was removed or recoded")
        preserved.append(
            {"id": row["id"], "pillars": row["pillars"], "matches": row["matches"]}
        )
    originals = {tuple(r["pillars"]) for r in preserved}
    load_registry(ROOT, registry_path)
    source_documents(ROOT, registry)
    return {
        "protocol_sha256": digest(protocol_path),
        "registry_sha256": digest(registry_path),
        "source_input_revision": input_revision,
        "scope": "Complete registered exposed corpus, no fresh accuracy or authority score; original studies and gates unchanged. This replay does not adjudicate every source formation, conversion, duty stem or source-relative force claim.",
        "group_counts": counts,
        "record_count": len(all_rows),
        "input_index": input_index(all_rows),
        "original_nineteen": preserved,
        "all_distinct_disagreements": replay["distinct_mismatches"],
        "additional_distinct_disagreements": [
            r
            for r in replay["distinct_mismatches"]
            if tuple(r["pillars"]) not in originals
        ],
        "literal_input_consistency_flags": [
            {
                "group": r["group"],
                "id": r["id"],
                "pillars": r["pillars"],
                **r["input_consistency"],
            }
            for r in all_rows
            if not r["input_consistency"]["all_three_modern_checks_match"]
        ],
        "local_and_negative_claims": claims,
        "groups": replay["groups"],
        "source_fingerprints_before": replay["source_fingerprints_before"],
        "source_fingerprints_after": replay["source_fingerprints_after"],
        "source_drift": replay["source_drift"],
        "runner_sha256": digest(Path(__file__)),
        "source_labels_changed": False,
        "production_strength_policy_changed": False,
        "production_strength_policy_changed_scope": "This read-only auditor does not mutate production policy; see the reported current method for the selected algorithm version.",
        "current_strength_method_id": STRENGTH_METHOD_ID,
        "policy_changed_since_frozen_v6": STRENGTH_METHOD_ID
        != "season_root_revelation_relations_v6",
        "new_independent_cases": 0,
        "independent_external_review": "not_completed",
        "classical_acceptance_passed": False,
        "reality_prediction_efficacy": "not_tested",
        "completion_claim": "unproven",
        "overall_score": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-version", choices=("v8", "v9"), default="v9")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve previous results; choose a new output path")
    result = audit(ROOT / f"tests/fixtures/bazi_source_corpus_{args.source_version}")
    encoded = (
        json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as handle:
        handle.write(
            gzip.compress(encoded, mtime=0) if args.output.suffix == ".gz" else encoded
        )
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(
        digest(args.output) + "\n"
    )
    print(
        json.dumps(
            {
                "groups": len(result["groups"]),
                "records": result["record_count"],
                "distinct_inputs": result["input_index"]["distinct_four_pillar_inputs"],
                "original_nineteen_retained": len(result["original_nineteen"]),
                "all_distinct_disagreements": len(result["all_distinct_disagreements"]),
                "additional_distinct_disagreements": len(
                    result["additional_distinct_disagreements"]
                ),
                "source_drift": result["source_drift"],
            },
            ensure_ascii=False,
        )
    )
    return 1 if result["source_drift"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
